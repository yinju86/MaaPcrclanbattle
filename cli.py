#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MaaPcrclanbattle 的命令行接口（无界面）。

打包成 generator.exe 之后这个接口同样可用，方便脚本或其它程序调用 exe：

    generator.exe decode "D4 34067W:wgpsXuql8ezlbxgaMK!"
    generator.exe import "D4 34067W:wgpsXuql8ezlbxgaMK!" --out .\\install
    generator.exe image 轴图.png --out .\\install
    generator.exe version

不带任何参数运行时仍然是图形界面（见 generator.py 的 `__main__`）。

两点说明：

1. 本模块刻意不 import PyQt5 —— 只有 `image` 子命令需要（而且是延迟导入），
   所以 `decode` / `import` 可以脱离 Qt、在无界面的环境里跑。
2. 打包成 exe 后 `__file__` 指向 PyInstaller 解包出来的临时目录（退出即删），
   所以 `app_dir()` / `get_version()` 这两个「东西在哪儿」的判断也放在这里，
   由 GUI（generator.py）一起复用。
"""

import argparse
import json
import os
import sys
from pathlib import Path

import pipeline
import sharecode

# 每个子命令都可用的公共参数
_COMMON = argparse.ArgumentParser(add_help=False)
_COMMON.add_argument(
    "--report", metavar="FILE",
    help="把输出同时写一份到该文件（打包成 exe 后从没有控制台的地方调用时用）")

# ub 分享码第三段没写角色名时的占位，与工具内部「1 号位」的叫法一致
_DEFAULT_PARTY = ["1", "2", "3", "4", "5"]

# ---------------------------------------------------------------- 输出
_REPORT_LINES = []


def _emit(text=""):
    """打印一行，同时记下来供 --report 落地。

    打包成 GUI 程序（pyinstaller -w）时 sys.stdout 可能是 None，
    这时唯一的输出通道就是 --report，所以这里不能直接调 print。
    """
    _REPORT_LINES.append(text)
    stream = sys.stdout
    if stream is None:
        return
    try:
        stream.write(text + "\n")
        stream.flush()
    except Exception:
        pass


def _emit_lines(lines):
    for line in lines:
        _emit(line)


def _write_report(path):
    if not path:
        return
    try:
        target = Path(path).expanduser()
        target.write_text("\n".join(_REPORT_LINES) + "\n", encoding="utf-8")
        _emit(f"输出已另存：{target.resolve()}")
    except Exception as exc:
        _emit(f"（写 --report 失败：{exc}）")


def _setup_stdout():
    """尽量把标准输出切成 UTF-8，免得 Windows 控制台用 GBK 打不出中文。"""
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _ensure_console():
    """pyinstaller -w 打出来的 GUI 程序默认没有控制台。

    从命令行调用时试着附到父进程的控制台，这样 print 的输出能被看到；
    附不上（从资源管理器或别的 GUI 程序调用）就静默跳过，
    此时用 --report 把结果写到文件。
    """
    if sys.stdout is not None and sys.stderr is not None:
        return
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        if not ctypes.windll.kernel32.AttachConsole(-1):
            return
        sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace")
        sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace")
    except Exception:
        pass


# ---------------------------------------------------------------- 程序位置
def app_dir():
    """程序所在目录。

    打包成 exe 后是 exe 的位置（resource/ 与 interface.json 就在旁边），
    而不是 PyInstaller 解包出来的临时目录。
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_version():
    """版本号写在 interface.json 里（install.py 打包时会写进去）。

    打包后 exe 与 interface.json 同目录；源码运行时在 install/ 子目录，
    两处都试一下。
    """
    for path in (app_dir() / "interface.json",
                 app_dir() / "install" / "interface.json"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                version = json.load(f).get("version")
            if version:
                return version
        except Exception:
            continue
    return "unknown"


class CliError(Exception):
    """能直接展示给用户的错误。"""


# ---------------------------------------------------------------- 分享码
def split_share_code(text):
    """拆分享码，返回 `(kind, 轴名, payload)`。

    - kind == "ub"：`轴名#指令串#五个角色名`，payload = (指令串, 角色名列表)
    - kind == "set"：`轴名:base62码!延时表`，payload = (码, 前五位偏移)

    SET 的历史格式是 `轴名:角色:码`，所以码永远取最后一段。
    轴名前五位若是纯数字，是 UB 亮条偏移标记（生成脚本时要原样带回去）。
    """
    raw = (text or "").strip().strip('"').strip("'").strip()
    if not raw:
        raise CliError("分享码是空的")

    if "#" in raw:
        parts = raw.split("#")
        if len(parts) < 2 or not parts[1].strip():
            raise CliError("单次UB分享码应形如「轴名#指令串#五个角色名」")
        names = parts[2].split() if len(parts) > 2 and parts[2].strip() else []
        names = names or list(_DEFAULT_PARTY)
        if len(names) != 5:
            raise CliError(
                f"单次UB分享码第三段应有 5 个角色名，实际 {len(names)} 个：{' '.join(names)}")
        return "ub", parts[0].strip(), (parts[1].strip(), names)

    name, _, code = raw.rpartition(":")
    name, code = name.strip(), code.strip()
    if not code:
        raise CliError("分享码是空的")
    offset = ""
    if len(name) >= 5 and name[:5].isdigit():
        offset, name = name[:5], name[5:].strip()
    return "set", name, (code, offset)


def validate_ub(inst, names):
    """按 pipeline 的语法走一遍指令串，顺手查号位越界。返回步骤列表。"""
    try:
        steps = pipeline.parse_ub_steps(inst)
    except KeyError as exc:
        raise CliError(f"指令串里有无法识别的字符：{exc}") from None
    if not steps:
        raise CliError("指令串里一条操作都没有")
    for kind, value in steps:
        if kind in ("click", "auto") and not 1 <= value <= len(names):
            raise CliError(f"指令串里的号位 {value} 超出队伍范围（1-{len(names)}）")
    return steps


def _party_name(names, number):
    """号位 -> 角色名；第三段只写了数字时叫「N 号位」。"""
    if 1 <= number <= len(names):
        name = str(names[number - 1]).strip()
        if name and not name.isdigit():
            return name
    return f"{number} 号位"


# ---------------------------------------------------------------- 渲染
def render_set(rows, td, name=None):
    """SET 行 -> 可读轴表。"""
    lines = []
    if name is not None:
        lines.append(f"类型：开关SET    轴名：{name or '(未命名)'}")
    lines.append(f"行数：{len(rows)}    延时表：{td or '{}'}")
    lines.append("")
    lines.append("  #    时间        原码   时点   1 2 3 4 5   auto  延时")
    lines.append("  " + "-" * 58)
    for i, (t, time_point, status) in enumerate(rows):
        marks = " ".join("o" if bit else "x" for bit in status[:5])
        auto = "开" if len(status) > 5 and status[5] else "关"
        # 124 是工具内部「初始状态」的记号，仅开局那一行作此显示
        when = "初始状态" if (i == 0 and t == "124") else f"{int(t[:-2])}:{t[-2:]}"
        lines.append(f"  {i:<4} {when:<10} {t:<5} {time_point:<5} "
                     f"{marks:<11} {auto:<5} {td.get(i, '')}")
    return lines


def render_ub(inst, names, name=None, steps=None):
    """单次UB 指令串 -> 可读操作流水。"""
    if steps is None:
        steps = validate_ub(inst, names)
    lines = []
    if name is not None:
        lines.append(f"类型：单次UB    轴名：{name or '(未命名)'}")
    lines.append("队伍：" + "  ".join(f"{i}={n}" for i, n in enumerate(names, 1)))
    lines.append(f"指令串：{inst}")
    lines.append(f"共 {len(steps)} 条操作：")
    lines.append("")
    for index, (kind, value) in enumerate(steps, 1):
        if kind == "click":
            text = f"点击 {_party_name(names, value)} 的 UB"
        elif kind == "auto":
            text = f"开 auto 等 {_party_name(names, value)} 自动 UB，完了自动关"
        elif kind == "delay":
            text = f"延时 {value} 秒"
        elif kind == "wait":
            text = f"等倒计时读到 {value}"
        else:
            text = "卡帧（人工目押）"
        lines.append(f"  {index:<4}{text}")
    return lines


def render_share_code(text):
    """分享码 -> 可读轴表（自动识别 SET / 单次UB）。"""
    kind, name, payload = split_share_code(text)
    if kind == "ub":
        inst, names = payload
        return render_ub(inst, names, name)
    code, offset = payload
    try:
        rows, td = sharecode.from_share(code)
    except Exception as exc:
        raise CliError(
            f"分享码解不开（{type(exc).__name__}: {exc}）—— 确认是从工具里复制的完整码，"
            "没有多字漏字。") from None
    if not rows:
        raise CliError("分享码里一行内容都没有")
    lines = render_set(rows, td, name)
    # 分享码本身没有校验和，被截断也会"解成功"却解出一条错误的轴，
    # 这里用一个最便宜的判据（正文必须是 3 的倍数）提醒一下。
    body = code.split("!")[0]
    if len(body) % 3:
        lines.insert(0, f"注意：正文 {len(body)} 个字符不是 3 的倍数，"
                        "分享码可能被截断或漏字，下面的轴表未必正确。")
    if offset:
        lines.insert(1, f"UB 偏移标记：{offset}（生成脚本时会原样带回去）")
    return lines


# ---------------------------------------------------------------- 生成脚本
def _enter_out_dir(out):
    """切到输出目录；不指定时用 exe 所在目录（resource/ 就在那儿）。"""
    target = Path(out).expanduser() if out else app_dir()
    try:
        target = target.resolve()
        target.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise CliError(f"输出目录不可用：{target}（{exc}）") from None
    os.chdir(target)
    return target


def _check_workspace():
    """生成脚本要读改 interface.json，缺了就早报错，别等 FileNotFoundError。"""
    if not Path("interface.json").is_file():
        raise CliError(
            "当前目录下没有 interface.json —— 请在 MaaPcrclanbattle 安装目录里运行，"
            "或用 --out 指定安装目录；若在源码仓库里调试，"
            "先把 assets/interface.json 复制一份到根目录。")


def _generate(kind, name, payload, speed):
    """调 pipeline 落盘，返回写出的脚本路径。"""
    _check_workspace()
    if kind == "set":
        rows, td = payload
        steps = pipeline.build_set_steps(rows, td)
        return pipeline.generate_set_pipeline(name, steps)
    inst, names = payload
    return pipeline.generate_single_ub_pipeline(
        name, stepfile=inst, namelist=names, speed=speed)


def _validate_speed(speed):
    if speed <= 0:
        raise CliError(f"识别速度应为正整数，实际 {speed}")
    return speed


# ---------------------------------------------------------------- 子命令
def _cmd_decode(args):
    _emit_lines(render_share_code(args.code))


def _cmd_import(args):
    kind, name, payload = split_share_code(args.code)
    if not name:
        name = "未命名轴"
    _emit_lines(render_share_code(args.code))

    # 先按分享码里的内容准备好生成参数（顺带把明显的错误拦下来）
    if kind == "set":
        code, offset = payload
        rows, td = sharecode.from_share(code)
        stepname = (offset + name) if offset else name
        generate_payload = (rows, td)
    else:
        inst, names = payload
        validate_ub(inst, names)
        stepname = name
        generate_payload = (inst, names)

    if args.no_script:
        _emit("")
        _emit("（--no-script：只解码，没有生成脚本）")
        return

    speed = _validate_speed(args.speed)
    target = _enter_out_dir(args.out)
    script_path = _generate(kind, stepname, generate_payload, speed)

    _emit("")
    _emit(f"输出目录：{target}")
    _emit(f"生成脚本：{script_path}（已注册到 interface.json）")


def _cmd_image(args):
    import generator  # 延迟导入：只有这条路需要 Qt

    image_path = Path(args.image).expanduser()
    if not image_path.is_file():
        raise CliError(f"找不到图片：{image_path}")
    data = image_path.read_bytes()
    if not data:
        raise CliError(f"图片是空的：{image_path}")
    if len(data) > 4 * 1024 * 1024:
        _emit(f"提示：图片有 {len(data) / 1048576:.1f} MB，偏大，可能较慢或被接口拒绝。")

    mime = {
        "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
        "bmp": "image/bmp", "webp": "image/webp", "gif": "image/gif",
    }.get(image_path.suffix.lower().lstrip("."), "image/png")

    config = generator.load_ai_config()
    if not str(config.get("api_key") or "").strip():
        _emit("提示：ai_config.json 里没有 API Key，接口可能拒绝。"
              "先在图形界面的 AI 模式里配好接口与 Key，再来调用这个接口。")
    _emit(f"正在识别 {image_path.name}（{config.get('model')} @ {config.get('base_url')}）…")

    result = generator.request_ai_detection(
        config.get("base_url", ""), config.get("model", ""),
        config.get("api_key", ""), data, mime)

    kind = str(result.get("type", "")).strip().lower()
    if kind not in ("set", "ub"):
        raise CliError(f"模型返回的 type 是「{kind}」，既不是 set 也不是 ub")
    name = str(result.get("name") or "").strip() or "未命名轴"
    party = [str(x).strip() for x in (result.get("party") or []) if str(x).strip()]
    rows_json = result.get("rows") or []
    if not rows_json:
        raise CliError("模型没有返回任何行")

    if kind == "set":
        rows, td = generator.MainWindow._build_set_rows(rows_json, party)
        code = f"{name}:{sharecode.to_share(rows, td)}"
        _emit("")
        _emit_lines(render_set(rows, td, name))
    else:
        if len(party) != 5:
            raise CliError(f"单次UB 需要 5 个角色名，模型给了 {len(party)} 个：{' '.join(party)}")
        lines = generator.MainWindow._build_ub_lines(rows_json, party)
        inst = generator.MainWindow.process_text("\n".join(lines), party)
        validate_ub(inst, party)
        code = f"{name}#{inst}#{' '.join(party)}"
        _emit("")
        _emit_lines(render_ub(inst, party, name))

    _emit("")
    _emit(f"分享码：{code}")
    _emit("注意：轴图上的「队伍号位顺序」是模型按头像行推的，SET 的时点全由它决定，"
          "请人工核对一遍。")

    if args.no_script:
        _emit("（--no-script：没有生成脚本）")
        return
    speed = _validate_speed(args.speed)
    target = _enter_out_dir(args.out)
    payload = (rows, td) if kind == "set" else (inst, party)
    script_path = _generate(kind, name, payload, speed)
    _emit(f"输出目录：{target}")
    _emit(f"生成脚本：{script_path}（已注册到 interface.json）")


def _cmd_version(_args):
    _emit(f"MaaPcrclanbattle {get_version()}")


# ---------------------------------------------------------------- 入口
SUBCOMMANDS = ("decode", "import", "image", "version")
ROOT_FLAGS = ("-h", "--help", "-V", "--version")


def is_cli_invocation(argv):
    """判断这次启动是命令行调用还是打开图形界面。

    只看第一个参数：是子命令或根级开关就走 CLI，其余（含无参数）都进 GUI。
    """
    if not argv:
        return False
    return argv[0] in ROOT_FLAGS or argv[0] in SUBCOMMANDS


def build_parser():
    parser = argparse.ArgumentParser(
        prog="generator",
        description="MaaPcrclanbattle 命令行接口：分享码 <-> 轴表，并生成 Maa 脚本。"
                    "不带参数运行则打开图形界面。",
        epilog="示例：\n"
               "  generator.exe decode \"D4 34067W:wgpsXuql8ezlbxgaMK!\"\n"
               "  generator.exe import \"码\" --out .\\install\n"
               "  generator.exe image 轴图.png\n",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-V", "--version", action="store_true", help="打印版本号")
    sub = parser.add_subparsers(dest="command", metavar="<命令>")

    p = sub.add_parser("decode", parents=[_COMMON], help="把分享码解成可读轴表")
    p.add_argument("code", help="分享码（SET 用 : 分隔，单次UB 用 # 分隔）")

    p = sub.add_parser("import", parents=[_COMMON], help="导入分享码并生成 Maa 脚本")
    p.add_argument("code", help="分享码")
    p.add_argument("--out", metavar="DIR", help="输出目录（默认程序所在目录）")
    p.add_argument("--speed", type=int, default=200,
                   help="识别速度，默认 200（100 快速 / 200 中速 / 300 慢速）")
    p.add_argument("--no-script", action="store_true", help="只解码，不生成脚本")

    p = sub.add_parser("image", parents=[_COMMON], help="调 AI 识别轴图并生成 Maa 脚本")
    p.add_argument("image", help="轴图文件路径")
    p.add_argument("--out", metavar="DIR", help="输出目录（默认程序所在目录）")
    p.add_argument("--speed", type=int, default=200,
                   help="识别速度，默认 200（100 快速 / 200 中速 / 300 慢速）")
    p.add_argument("--no-script", action="store_true", help="只识别，不生成脚本")

    sub.add_parser("version", parents=[_COMMON], help="打印版本号")
    return parser


def main(argv):
    _ensure_console()
    _setup_stdout()

    parser = build_parser()
    args = parser.parse_args(argv)

    if getattr(args, "version", False) or args.command == "version":
        _cmd_version(args)
        _write_report(getattr(args, "report", None))
        return 0
    if not args.command:
        parser.print_help()
        return 0

    try:
        if args.command == "decode":
            _cmd_decode(args)
        elif args.command == "import":
            _cmd_import(args)
        elif args.command == "image":
            _cmd_image(args)
        else:
            parser.error(f"未知命令：{args.command}")
    except CliError as exc:
        _emit(f"错误：{exc}")
        _write_report(args.report)
        return 2
    except Exception as exc:
        _emit(f"失败：{type(exc).__name__}: {exc}")
        _write_report(args.report)
        return 1

    _write_report(args.report)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
