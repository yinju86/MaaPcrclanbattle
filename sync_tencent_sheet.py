#!/usr/bin/env python3
"""从腾讯文档公开分享页同步会战轴分享码（免登录、纯标准库）。

为什么需要它
    MaaPcrclanbattle 的「获取在线轴」原先拉的是人工维护的 GitHub gist。
    本脚本直接从腾讯文档表格取数，把人工中转环节去掉。
    既可作为命令行工具单独跑，也可被 generator.py 直接 import。

原理
    公开分享的表格页会把整表文本注入 HTML 里的 flyweight.texts 池。
    一个单元格若含多种字符格式，文本会被切成多个 **相邻** 的段，
    所以要按分享码语法把碎片拼回去。判据来自 sharecode.py：

    SET 码  `轴名:base62!延时表`
        · base62 主体长度必须是 3 的倍数
        · 解码后每行第 4 位（时点）只能是 0~5
        · 延时表形如 `5-0.5,7-0.5`
    UB 码   `轴名#指令串#角色名`
        · 有两个 #；指令串只由 1-5 a d s k 组成

用法（命令行）
    python sync_tencent_sheet.py                       # 自动跟随当月工作表
    python sync_tencent_sheet.py -o sharecode.txt      # 写文件
    python sync_tencent_sheet.py --json out.json       # 带元数据的结构化输出
    python sync_tencent_sheet.py --expect ''            # 不校验工作表名

用法（作为模块）
    import sync_tencent_sheet as sts
    codes, meta = sts.fetch_codes()                    # codes: [{type,name,code,...}]

坑
    1. 请求**不要**带 `?tab=` 参数：带不带都不影响渲染结果，反而更容易拿到空壳。
    2. 表格只会为「上次打开」的工作表（页面里 hidden=false 的那张）下发数据，
       URL 参数无法切换——所以脚本会校验「当前渲染的是不是当月」，不是就报错。
    3. 空壳页是偶发的（约 350KB 才有数据），fetch_pool 里已带重试。
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime

DOC_ID = "DU2NHdnlNalFqdVZz"          # 默认表格：set轴分享码分享
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

CHARSET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
DELAY_RE = re.compile(r"^\d+-\d+(?:\.\d+)?(?:,\d+-\d+(?:\.\d+)?)*$")
UB_INSTR_RE = re.compile(r"^[0-9adsk]+$")

CN_MONTH = "一二三四五六七八九十"


class TabMismatch(Exception):
    """当前渲染的工作表不是期望的那张。"""

    def __init__(self, want: str, got: str):
        self.want, self.got = want, got
        super().__init__(
            f"当前渲染的是「{got}」，不是期望的「{want}」。\n"
            f"腾讯文档只会为「上次打开」的工作表下发数据，URL 参数切不过去。\n"
            f"请先在浏览器里打开「{want}」，或等它成为默认工作表。")


# --------------------------------------------------------------------------- #
# 当月工作表名
# --------------------------------------------------------------------------- #
def month_tab_names(now: datetime | None = None) -> list[str]:
    """当月工作表可能的命名写法，按优先级排列。

    表里历史命名并不统一（`26年10月` / `2026年4月` / `十月`），所以多备几种。
    """
    now = now or datetime.now()
    m = now.month
    cn = CN_MONTH[m - 1] if m <= 10 else ("十一" if m == 11 else "十二")
    return [
        f"{now:%y}年{m}月",      # 26年10月
        f"{now:%Y}年{m}月",      # 2026年10月
        f"{now:%y}年{m:02d}月",
        f"{now:%Y}年{m:02d}月",
        f"{cn}月",               # 十月
    ]


def pick_current_tab(tabs: list[dict], now: datetime | None = None) -> dict | None:
    """在 tab 清单里找「当月」那张。找不到返回 None。"""
    now = now or datetime.now()
    by_name = {t["name"]: t for t in tabs}
    for cand in month_tab_names(now):
        if cand in by_name:
            return by_name[cand]
    # 退一步：名字里带「10月」且不含「历史」的
    suffix = f"{now.month}月"
    for t in tabs:
        if suffix in t["name"] and "历史" not in t["name"]:
            return t
    return None


# --------------------------------------------------------------------------- #
# 取页面
# --------------------------------------------------------------------------- #
def fetch(doc_id: str, retries: int = 3, timeout: int = 30) -> str:
    url = f"https://docs.qq.com/sheet/{doc_id}"
    last = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "zh-CN,zh;q=0.9",
            })
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception as exc:                      # noqa: BLE001
            last = exc
            if attempt < retries:
                time.sleep(attempt * 2)
    raise RuntimeError(f"获取页面失败：{last}")


def extract_pool(raw: str) -> list[str]:
    """从页面里取出 flyweight.texts 字符串池。"""
    u = urllib.parse.unquote(raw)
    i = u.find('"texts":[')
    if i < 0:
        raise RuntimeError(
            "页面里没有找到 texts 数据池——多半是拿到了不含数据的空壳页。"
            "请确认表格是「获得链接的人可查看」，并重试。")
    s = i + len('"texts":')
    depth, end = 0, s
    for k in range(s, len(u)):
        if u[k] == "[":
            depth += 1
        elif u[k] == "]":
            depth -= 1
            if depth == 0:
                end = k + 1
                break
    return json.loads(u[s:end])


def parse_tabs(raw: str) -> list[dict]:
    """解析工作表清单：[{id, name, active}]。"""
    u = urllib.parse.unquote(raw)
    pat = re.compile(
        r'\{"id":"(?P<id>[0-9a-zA-Z]+)","name":"(?P<name>[^"]*)"'
        r',"hidden":(?P<hidden>true|false)')
    return [{
        "id": m.group("id"),
        "name": html.unescape(m.group("name")),
        "active": m.group("hidden") == "false",
    } for m in pat.finditer(u)]


def fetch_pool(doc_id: str, retries: int = 4) -> tuple[str, list[dict], list[str]]:
    """取页面并解析；空壳页会重试（实测有概率返回空壳）。"""
    last = None
    for attempt in range(1, retries + 1):
        raw = fetch(doc_id, retries=1)
        try:
            return raw, parse_tabs(raw), extract_pool(raw)
        except RuntimeError as exc:
            last = exc
            if attempt < retries:
                time.sleep(attempt * 1.5)
    raise RuntimeError(str(last))


# --------------------------------------------------------------------------- #
# 校验
# --------------------------------------------------------------------------- #
def decode_rows(b62: str) -> list[str] | None:
    if not b62 or len(b62) % 3 or any(c not in CHARSET for c in b62):
        return None
    rows = []
    for i in range(0, len(b62), 3):
        num = 0
        for c in b62[i:i + 3]:
            num = num * 62 + CHARSET.index(c)
        rows.append(str(num).zfill(6))
    return rows


def valid_set(b62: str) -> bool:
    rows = decode_rows(b62)
    if not rows:
        return False
    for r in rows:
        if r[3] not in "012345":          # 时点只能是 0~5
            return False
        if not r[:3].isdigit() or int(r[:3]) > 999:
            return False
    return True


def valid_ub(instr: str) -> bool:
    return bool(instr) and bool(UB_INSTR_RE.match(instr))


# 轴名标签：表格里每个分享码单元格写成「轴名标签 + 码体」连在一起的一整串，
# 例如 `D5光物理35696w#...#...`、`D1浮城-开关set-42302w:...`。
# 编辑器的富文本分段会把标签和码体切成相邻的两段，所以码名前要补回标签。
LABEL_RE = re.compile(r"^[dD]\d")


def _is_label(seg: str) -> bool:
    """判断某一段是否是轴名标签（`D5光物理`、`D1浮城-开关` 这种）。"""
    s = seg.strip()
    return (bool(s) and len(s) <= 20
            and not any(c in s for c in ":#!")
            and bool(LABEL_RE.match(s)))


def _is_role_tail(seg: str) -> bool:
    """判断某一段是否还是 UB 码尾部被切开的角色名列表。"""
    s = seg.strip()
    if not s or len(s) > 40 or any(c in s for c in ":#!"):
        return False
    if LABEL_RE.match(s) or any(c.isdigit() for c in s):
        return False
    tokens = s.split()
    return bool(tokens) and len(tokens) <= 5 and all(len(t) <= 8 for t in tokens)


def _with_label(pool: list[str], i: int, taken_until: int, name: str) -> str:
    """把紧邻在码体前面、且未被上一个码占用的轴名标签补回名字前。"""
    if not name or LABEL_RE.match(name):
        return name                      # 名字自带 `D1`/`D5` 前缀，无需再补
    if i - 1 <= taken_until:             # 前一段属于上一个码，不是标签
        return name
    prev = pool[i - 1]
    if not _is_label(prev):
        return name
    label = prev.strip()
    # 表里多数是紧贴写法（`D5光物理35696w`、`D1浮城-开关set-...`），统一不加空格
    return f"{label}{name}"


# --------------------------------------------------------------------------- #
# 碎片重组
# --------------------------------------------------------------------------- #
def rebuild(pool: list[str]) -> tuple[list[dict], list[str]]:
    """把 texts 池里的碎片拼回分享码。返回 (码列表, 警告列表)。"""
    codes: list[dict] = []
    warns: list[str] = []
    n = len(pool)
    i = 0
    taken_until = -1            # 上一个码吃掉的最后一段，避免把码尾当成轴名标签

    while i < n:
        seg = pool[i]

        # ---------------- SET：轴名:base62!延时 ----------------
        if ":" in seg and not seg.startswith("#"):
            axis, _, rest = seg.partition(":")
            rest = rest.lstrip(":")        # 表格里偶尔写成 `D1-42700::码`
            # `!` 可能就落在起始段里，先切开，免得被字符集检查挡掉
            inline_delay = None
            if "!" in rest:
                rest, _, inline_delay = rest.partition("!")
            if rest and all(c in CHARSET for c in rest) and axis.strip():
                body_parts, delay, j = [rest], inline_delay, i
                if delay is None:
                    while j + 1 < n:
                        j += 1
                        nxt = pool[j]
                        if "!" in nxt:
                            head, _, tail = nxt.partition("!")
                            body_parts.append(head)
                            delay = tail
                            break
                        if not all(c in CHARSET for c in nxt):
                            break          # 撞到中文/空格，说明码到此为止
                        body_parts.append(nxt)
                # 延时表被切开时要补齐，例如 `2-` + `0.2,5-0.2`
                if delay:
                    while j + 1 < n and not DELAY_RE.match(delay):
                        nxt2 = pool[j + 1]
                        if all(c in CHARSET or c in ".,-" for c in nxt2):
                            j += 1
                            delay += nxt2
                        else:
                            break
                if delay and not DELAY_RE.match(delay):
                    # 延时表拼不出合法格式时仍保留原文（表里数据是权威），但要提醒
                    warns.append(f"段 [{i}] {axis!r} 的延时表格式异常：{delay!r}")

                body = "".join(body_parts)
                if valid_set(body):
                    name = _with_label(pool, i, taken_until, axis.strip())
                    codes.append({
                        "type": "set",
                        "name": name,
                        "code": f"{name}:{body}" + (f"!{delay}" if delay is not None else ""),
                        "base62_len": len(body),
                        "rows": len(body) // 3,
                        "delay": delay or "",
                        "segments": list(range(i, j + 1)),
                    })
                    taken_until = j
                    i = j + 1
                    continue
                if body_parts:
                    warns.append(f"段 [{i}] {axis!r} 疑似 SET 码但校验未通过（len={len(body)}）")

        # ---------------- UB：轴名#指令#角色 ----------------
        if "#" in seg:
            started_empty = seg.startswith("#")
            head, _, instr = seg.partition("#")
            name = head.strip()
            if started_empty and not name:
                for k in range(i - 1, max(-1, i - 6), -1):
                    if "#" not in pool[k] and ":" not in pool[k]:
                        name = pool[k].strip()
                        break
            elif name:
                name = _with_label(pool, i, taken_until, name)
            parts, names, j, closed = [instr], "", i, False
            while j + 1 < n:
                j += 1
                nxt = pool[j]
                if "#" in nxt:
                    mid, _, tail = nxt.partition("#")
                    parts.append(mid)
                    names = tail
                    closed = True
                    break
                if not UB_INSTR_RE.match(nxt):
                    break
                parts.append(nxt)
            # 角色名列表也可能被切开，例如 `#sls 菲欧` + `hcw 花女仆 圣姐`
            if closed:
                extra, k = [], j
                while len(names.split()) + len(extra) < 5 and k + 1 < n:
                    if not _is_role_tail(pool[k + 1]):
                        break
                    k += 1
                    extra.extend(pool[k].split())
                if extra:
                    names = " ".join(([names] if names else []) + extra)
                    j = k
            instr_full = "".join(parts)
            if closed and valid_ub(instr_full):
                role_names = names.split()
                codes.append({
                    "type": "ub",
                    "name": name,
                    "code": f"{name}#{instr_full}#{names}",
                    "instr_len": len(instr_full),
                    "roles": role_names,
                    "segments": list(range(i, j + 1)),
                })
                if len(role_names) != 5:
                    warns.append(
                        f"段 [{i}] {name!r} 的角色名是 {len(role_names)} 个（正常应为 5 个），"
                        "原表可能没写全")
                taken_until = j
                i = j + 1
                continue

        i += 1

    return codes, warns


# --------------------------------------------------------------------------- #
# 高层接口（给 generator.py 用）
# --------------------------------------------------------------------------- #
def fetch_codes(doc_id: str = DOC_ID, expect: str | None = None,
                now: datetime | None = None) -> tuple[list[dict], dict]:
    """取码并校验工作表。

    expect=None  自动跟随当月（推荐）
    expect=""    不校验，拿到哪张算哪张
    expect=name  必须是指定名字

    返回 (codes, meta)。工作表面名对不上时抛 TabMismatch。
    """
    raw, tabs, pool = fetch_pool(doc_id)
    active = next((t for t in tabs if t["active"]), None)
    active_name = active["name"] if active else ""

    want = expect
    if want is None:
        cur = pick_current_tab(tabs, now)
        want = cur["name"] if cur else ""

    if want and active_name != want:
        raise TabMismatch(want, active_name)

    codes, warns = rebuild(pool)
    meta = {
        "doc_id": doc_id,
        "tab": active,
        "tabs_total": len(tabs),
        "expected": want,
        "pool_size": len(pool),
        "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "warnings": warns,
    }
    return codes, meta


def render_text(codes: list[dict]) -> str:
    return "\n".join(c["code"] for c in codes) + ("\n" if codes else "")


# --------------------------------------------------------------------------- #
# 命令行
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="从腾讯文档公开分享页同步会战轴分享码",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-d", "--doc-id", default=DOC_ID, help="表格 ID（URL 里 /sheet/ 后面那段）")
    ap.add_argument("--expect", default=None,
                    help="指定工作表名；留空自动跟随当月；传 '' 则不校验")
    ap.add_argument("-o", "--out", help="把分享码写到这个文件")
    ap.add_argument("--json", metavar="FILE", help="把带元数据的结果写成 JSON")
    ap.add_argument("--strict", action="store_true", help="出现警告时退出码为 1")
    ap.add_argument("--quiet", action="store_true", help="只输出结果，不打报告")
    args = ap.parse_args(argv)

    def say(*a):
        if not args.quiet:
            print(*a, file=sys.stderr)

    try:
        codes, meta = fetch_codes(args.doc_id, args.expect)
    except TabMismatch as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    except Exception as exc:                          # noqa: BLE001
        print(f"错误：{exc}", file=sys.stderr)
        return 1

    active = meta["tab"]
    say(f"工作表 {meta['tabs_total']} 张，当前渲染：{active['name'] if active else '未知'}")
    set_n = sum(1 for c in codes if c["type"] == "set")
    say(f"texts 池 {meta['pool_size']} 段 → 还原 {len(codes)} 条码"
        f"（SET {set_n} / UB {len(codes) - set_n}）")
    for w in meta["warnings"]:
        say(f"  ⚠ {w}")

    text = render_text(codes)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        say(f"已写入 {args.out}")
    else:
        sys.stdout.write(text)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({**meta, "total": len(codes), "codes": codes},
                      fh, ensure_ascii=False, indent=2)
        say(f"已写入 {args.json}")

    if not codes:
        print("错误：没有还原出任何分享码（页面结构可能已变）", file=sys.stderr)
        return 1
    if meta["warnings"] and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
