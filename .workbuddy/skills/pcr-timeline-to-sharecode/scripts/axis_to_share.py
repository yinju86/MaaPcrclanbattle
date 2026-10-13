#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PCR 会战轴表 <-> 分享码 转换。

编码规则与 MaaPcrclanbattle 仓库的 sharecode.py 完全一致（此处内联一份，
让 skill 脱离仓库也能独立运行）：
    每行 -> [时间3位][时点1位][6位状态压成2位十进制] -> 6位十进制 -> base62 定长3字符
    全轴首尾相接，末尾用 '!' 接延时表 "行号-延时,行号-延时"

输出前会用反向解码做自检，逐行比对不一致就直接报错退出，不产出错误的码。
"""
import argparse
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

CHARSET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
MAX_3CHAR = 62 ** 3 - 1  # 238327，超过则 zfill(3) 定宽失效


# ---------------------------------------------------------------- 编码 / 解码
def _to_base62(num):
    if num == 0:
        return "0"
    out = []
    while num > 0:
        out.append(CHARSET[num % 62])
        num //= 62
    return "".join(reversed(out))


def _from_base62(s):
    num = 0
    for ch in s:
        num = num * 62 + CHARSET.index(ch)
    return num


def to_share(rows, td=None):
    """rows: [(time3str, tp_str, [6 bool])] -> 分享码字符串"""
    td = td or {}
    parts = []
    for t, tp, status in rows:
        bits = "".join("1" if b else "0" for b in status)
        combined = f"{t}{tp}{int(bits, 2):02d}".zfill(6)
        parts.append(_to_base62(int(combined)).zfill(3))
    body = "".join(parts)
    tail = ",".join(f"{k}-{v}" for k, v in td.items())
    return body + "!" + tail


def from_share(code):
    """分享码 -> (rows, td)；只解 body，td 解析失败会让调用方看到异常"""
    body, _, tail = code.partition("!")
    if tail and "!" in tail:      # 兼容多段，只取第一段延时表
        tail = tail.split("!")[0]
    rows = []
    for i in range(0, len(body), 3):
        n = _from_base62(body[i:i + 3])
        entry = str(n).zfill(6)
        bits = f"{int(entry[4:]):06b}"
        rows.append((entry[:3], entry[3], [b == "1" for b in bits]))
    td = {}
    if tail:
        for item in tail.split(","):
            k, v = item.rsplit("-", 1)
            td[int(k)] = float(v) if "." in v else int(v)
    return rows, td


# ---------------------------------------------------------------- 输入解析
def parse_state(text):
    """'oxooo' / 'OOOOX' / 'o x o o o' -> 5 个 bool；o/O/1/开 视为开"""
    s = text.replace(" ", "").replace("　", "").lower()
    out = []
    for ch in s:
        if ch in "o1x":
            out.append(ch != "x")
        elif ch == "开":
            out.append(True)
        elif ch == "关":
            out.append(False)
        else:
            raise ValueError(f"状态串 {text!r} 含无法识别的字符 {ch!r}")
    if len(out) != 5:
        raise ValueError(f"状态串 {text!r} 应有 5 位，实际 {len(out)} 位")
    return out


def build_rows(spec):
    """把 JSON spec 转成 (rows, td, name)"""
    party = spec.get("party") or []
    slot = {name: i + 1 for i, name in enumerate(party)}
    name = spec.get("name", "")
    rows, td = [], {}

    for idx, r in enumerate(spec["rows"]):
        # --- 时间 ---
        time = str(r.get("time", "")).strip()
        if r.get("initial"):
            time = "124"                      # 「初始状态」的内部编码
        if len(time) != 3 or not time.isdigit():
            raise ValueError(f"第 {idx} 行时间 {time!r} 必须是 3 位数字")
        v = int(time)
        if not (1 <= v <= 59 or 100 <= v <= 130):
            raise ValueError(f"第 {idx} 行时间 {time} 超出合法范围（001-059 / 100-130）")

        # --- 时点：触发角色对应的号位 ---
        if r.get("time_point") is not None:
            tp = int(r["time_point"])
        else:
            trigger = r.get("trigger")
            if r.get("stuck"):                # 卡帧
                tp = 6
            elif not trigger or trigger in "-_/无":
                tp = 0                        # 普攻后 / 无 UB 触发
            else:
                if trigger not in slot:
                    raise ValueError(
                        f"第 {idx} 行触发角色 {trigger!r} 不在队伍里，"
                        f"已知：{list(slot)}")
                tp = slot[trigger]
        if not 0 <= tp <= 6:
            raise ValueError(f"第 {idx} 行时点 {tp} 超出 0-6")

        # --- 状态 + auto ---
        status = parse_state(r["state"])
        status.append(bool(r.get("auto", False)))

        rows.append((time, str(tp), status))
        if r.get("delay"):
            td[idx] = float(r["delay"])

    return rows, td, name


def parse_simple_text(text):
    """简写文本 -> spec dict。

    # name: D3 37546W
    # party: 生菜 水猪妹 若菜 水猫妹 诗夏
    124 -        oxooo  -
    109 生菜     oooox  -
    057 生菜     xxxoo  A
    003 水猪妹   xxooo  A  0.1
    """
    spec = {"name": "", "party": [], "rows": []}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        if line.startswith("#"):
            key, _, val = line[1:].partition(":")
            key, val = key.strip().lower(), val.strip()
            if key == "name":
                spec["name"] = val
            elif key == "party":
                spec["party"] = val.split()
            continue

        cols = line.split()
        if len(cols) < 3:
            raise ValueError(f"无法解析行：{raw!r}（至少要有 时间 / 触发 / 状态 三列）")
        time, trigger, state = cols[0], cols[1], cols[2]
        auto = False
        delay = None
        for extra in cols[3:]:
            if extra.upper() == "A":
                auto = True
            elif extra in ("-", "_", "/", "关"):   # 显式写「关 auto」
                continue
            else:
                try:
                    delay = float(extra)
                except ValueError:
                    raise ValueError(f"无法解析附加列 {extra!r}（只认 A 或数字延时）")

        row = {"time": time, "state": state, "auto": auto}
        if trigger in ("-", "_", "/", "无"):
            row["trigger"] = None
        elif trigger in ("卡帧", "卡"):
            row["stuck"] = True
        else:
            row["trigger"] = trigger
        if delay is not None:
            row["delay"] = delay
        spec["rows"].append(row)
    return spec


# ================================================================ 单次UB模式
# 指令串语法（与 pipeline.generate_single_ub_pipeline 的解析状态机一致）：
#   N      点击 N 号位角色的 UB（1-5）
#   aN     开 auto 等 N 号位自动 UB，结束自动关 auto
#   dN     延时 N 秒
#   sMSS   等倒计时到 M:SS（s + 1位分 + 2位秒）
#   k      卡帧（人工目押）
#   \ /    忽略


def validate_ub(inst):
    """按 pipeline 的状态机走一遍，非法字符/断码直接报错。"""
    i, steps = 0, []
    while i < len(inst):
        c = inst[i]
        if c.isdigit():
            if not 1 <= int(c) <= 5:
                raise ValueError(f"位置 {i}: 号位 {c} 不存在（1-5）")
            steps.append(("click", int(c)))
            i += 1
        elif c in "aA" and i + 1 < len(inst) and inst[i + 1].isdigit():
            if not 1 <= int(inst[i + 1]) <= 5:
                raise ValueError(f"位置 {i}: aN 的号位 {inst[i + 1]} 不存在（1-5）")
            steps.append(("auto", int(inst[i + 1])))
            i += 2
        elif c in "dD" and i + 1 < len(inst) and inst[i + 1].isdigit():
            steps.append(("delay", int(inst[i + 1])))
            i += 2
        elif c in "sS" and i + 3 < len(inst) and all(x.isdigit() for x in inst[i + 1:i + 4]):
            steps.append(("wait", f"{inst[i + 1]}:{inst[i + 2:i + 4]}"))
            i += 4
        elif c == "k":
            steps.append(("stuck", None))
            i += 1
        elif c in "\\/":
            i += 1
        else:
            raise ValueError(f"位置 {i}: 非法字符 {c!r}（合法：1-5 / aN / dN / sMSS / k）")
    return steps


def explain_ub(inst, party):
    """指令串 -> 人话列表"""
    def who(n):
        return party[n - 1] if n <= len(party) else f"{n}号"

    out = []
    for kind, val in validate_ub(inst):
        if kind == "click":
            out.append(f"点击{who(val)}的UB")
        elif kind == "auto":
            out.append(f"开auto等{who(val)}自动UB，完自动关")
        elif kind == "delay":
            out.append(f"延时{val}秒")
        elif kind == "wait":
            out.append(f"等倒计时 {val}")
        else:
            out.append("卡帧（人工目押）")
    return out


def parse_ub_text(text):
    """轴图操作列文本 -> (name, party, 指令串)。

    行格式（时间列可选！）：
      M:SS [操作...]   -> 生成 s 指令 + 操作
      [操作...]        -> 只有操作，挂在上一个等待之后
      -                -> 本行只等时间（如 BOSS UB）

    时间列大多只是给人看的参考：指令串里的 s 只出现在需要重新校准
    倒计时的「段落起点」，同一时段内的连续操作不再逐行等时间。

    操作写法：
      角色名           -> 点击该角色 UB
      角色名AUTO       -> 开 auto 等该角色自动 UB（完自动关）
      卡帧 / 押 / 目押  -> k（人工目押）
      延时N            -> dN
    """
    name, party, inst = "", [], []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        if line.startswith("#"):
            key, _, val = line[1:].partition(":")
            key, val = key.strip().lower(), val.strip()
            if key == "name":
                name = val
            elif key == "party":
                party = val.split()
            continue

        cols = line.split()
        ops = cols
        if ":" in cols[0]:
            m, _, ss = cols[0].partition(":")
            if m.isdigit() and ss.isdigit() and len(ss) == 2:
                inst.append(f"s{m}{ss}")
                ops = cols[1:]
            else:
                raise ValueError(f"时间 {cols[0]!r} 应为 M:SS 格式（如 1:14）")

        for op in ops:
            if op in ("-", "无"):
                continue
            if op in ("卡帧", "卡", "押", "目押", "唱名"):
                inst.append("k")
                continue
            auto = False
            if op.upper().endswith("AUTO"):
                auto = True
                op = op[:-4]
            if op[:-1].isdigit() and op[-1] in "秒sS":
                inst.append(f"d{op[:-1]}")
                continue
            if op in ("延时", ""):
                continue
            if op not in party:
                raise ValueError(f"操作 {op!r} 不在队伍里，已知：{party}")
            n = party.index(op) + 1
            inst.append(f"a{n}" if auto else str(n))
    return name, party, "".join(inst)


def ub_share_code(name, party, inst, namelist_override=None):
    """拼成 轴名#指令串#角色名 三段码"""
    names = namelist_override or party
    if len(names) != 5:
        raise ValueError(f"角色名必须 5 个，实际 {len(names)}")
    return f"{name}#{inst}#{' '.join(names)}"

def verify(rows, td, code):
    """反向解码自检：逐行逐项比对，返回错误列表"""
    got_rows, got_td = from_share(code)
    errs = []
    if len(got_rows) != len(rows):
        errs.append(f"行数不一致：编码 {len(rows)} 行，解码 {len(got_rows)} 行")
        return errs
    for i, ((t1, tp1, s1), (t2, tp2, s2)) in enumerate(zip(rows, got_rows)):
        if (t1, tp1, s1) != (t2, tp2, s2):
            errs.append(f"第 {i} 行往返不一致：{t1}/{tp1}/{s1} -> {t2}/{tp2}/{s2}")
    if got_td != td:
        errs.append(f"延时表往返不一致：{td} -> {got_td}")
    for i, (t, tp, _s) in enumerate(rows):
        if int(f"{t}{tp}63") > MAX_3CHAR:
            errs.append(f"第 {i} 行数值 {t}{tp}63 超出 base62 三字符上限 {MAX_3CHAR}")
    return errs


def show(rows, td, party=None):
    print(f"{'#':<4}{'时间':<8}{'时点':<6}{'1 2 3 4 5':<12}{'auto':<6}{'延时'}")
    for i, (t, tp, s) in enumerate(rows):
        pat = " ".join("o" if b else "x" for b in s[:5])
        who = ""
        if party and tp.isdigit() and 1 <= int(tp) <= 5:
            who = party[int(tp) - 1]
        tp_show = "卡帧" if tp == "6" else tp
        if who:
            tp_show = f"{tp}({who})"
        print(f"{i:<4}{t:<8}{tp_show:<12}{pat:<12}"
              f"{'开' if s[5] else '关':<6}{td.get(i, '')}")


def main():
    ap = argparse.ArgumentParser(description="PCR 轴表 <-> 分享码")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--json", help="JSON 轴表文件（开关SET）")
    g.add_argument("--text", help="简写文本轴表文件（开关SET）")
    g.add_argument("--ub-text", help="简写文本轴表文件（单次UB）")
    g.add_argument("--decode", help="要解码的分享码（自动识别 SET / 单UB）")
    ap.add_argument("--no-verify", action="store_true", help="跳过往返自检")
    args = ap.parse_args()

    if args.decode:
        if "#" in args.decode:
            name, inst, tail = args.decode.split("#")
            party = tail.split()
            print(f"类型：单次UB   轴名：{name}")
            print(f"角色：{party}")
            print(f"指令共 {len(inst)} 字符，语法校验通过")
            print()
            for n, line in enumerate(explain_ub(inst, party), 1):
                print(f"{n:<4}{line}")
            return 0
        rows, td = from_share(args.decode)
        print(f"类型：开关SET   行数 = {len(rows)}   td = {td}")
        print()
        show(rows, td)
        return 0

    if args.ub_text:
        text = open(args.ub_text, encoding="utf-8").read()
        name, party, inst = parse_ub_text(text)
        steps = validate_ub(inst)          # 语法自检，非法即抛
        code = ub_share_code(name, party, inst)
        print(f"语法自检：{len(steps)} 个指令，全部合法 ✓")
        print()
        for n, line in enumerate(explain_ub(inst, party), 1):
            print(f"{n:<4}{line}")
        print()
        print(f"轴名：{name or '(未填写)'}")
        print(f"分享码：{code}")
        return 0

    if args.json:
        spec = json.loads(open(args.json, encoding="utf-8").read())
    else:
        spec = parse_simple_text(open(args.text, encoding="utf-8").read())

    rows, td, name = build_rows(spec)
    code = to_share(rows, td)

    if not args.no_verify:
        errs = verify(rows, td, code)
        if errs:
            print("自检失败，未产出分享码：", file=sys.stderr)
            for e in errs:
                print("  - " + e, file=sys.stderr)
            return 1
        print("自检：往返一致 ✓")

    print()
    show(rows, td, spec.get("party"))
    print()
    print(f"轴名：{name or '(未填写)'}")
    print(f"分享码：{name}:{code}" if name else f"分享码：{code}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
