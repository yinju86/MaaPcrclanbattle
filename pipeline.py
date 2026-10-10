"""生成 MaaFramework pipeline。

原为 scriptgeneration.py（开关SET模式）与 specialgenerat.py（单次UB模式）两个文件，
各自用 f-string 拼一整套几乎相同的 JSON，且都存在各自一份的偏移解码与写盘逻辑。
现合并于此：

- 两种模式共用 _split_offset / _entry_nodes / _finish_node / _save_and_register
- 拼装方式由「拼 f-string 再 json.loads」改为直接构造 dict，去掉了原先依赖
  replace('True','true')、replace('\\n','') 以及末尾字符串替换补尾节点的做法

注：坐标 / 延时 / 阈值等数值均沿用原实现中的字面值，未做提取或改名。
"""

import json
import os


def _split_offset(stepname):
    """解析轴名前 5 位的 UB 偏移标记。

    返回 (去掉标记后的轴名, 五个号位的 UB 亮条 x 坐标)。
    """
    offsetX = [0, 0, 0, 0, 0]
    if len(stepname) >= 5 and stepname[:5].isdigit():
        for i in range(5):
            digit = int(stepname[i])
            result = digit * 10
            if result > 60:
                result -= 100
            offsetX[i] = result
        stepname = stepname[5:]
    ubflag = [310 + offsetX[0], 470 + offsetX[1], 630 + offsetX[2],
              790 + offsetX[3], 950 + offsetX[4]]
    return stepname, ubflag


def _entry_nodes(stepname, first_node, start_tip=None):
    """开场节点：entry / start / start0 / start2 / autoc / ljfdc / ljfd / autoo。

    first_node: ljfdc / ljfd 之后跳转的第一个节点名
                SET 模式为 {stepname}tc_0，单次UB 模式为 {stepname}0
    start_tip : 单次UB 模式在 start 节点额外给出提示，SET 模式为 None
    """
    nodes = {}

    nodes[f"{stepname}entry"] = {
        "next": [f"{stepname}start", f"{stepname}start0"],
    }

    start = {
        "recognition": "TemplateMatch",
        "threshold": [0.9],
        "template": ["start.png"],
    }
    if start_tip:
        start["focus"] = True
        start["focus_tip"] = start_tip
    start["action"] = "Click"
    start["next"] = [f"{stepname}start0"]
    nodes[f"{stepname}start"] = start

    nodes[f"{stepname}start0"] = {
        "recognition": "TemplateMatch",
        "threshold": [0.9],
        "template": ["start0.png"],
        "action": "Click",
        "pre_delay": 100,
        "post_delay": 15,
        "rate_limit": 30,
        "timeout": 500000,
        "next": [f"{stepname}start2", f"{stepname}autoc", f"{stepname}autoo"],
    }

    nodes[f"{stepname}start2"] = {
        "recognition": "TemplateMatch",
        "threshold": [0.9],
        "template": ["start2.png"],
        "action": "Click",
        "pre_delay": 100,
        "post_delay": 15,
        "rate_limit": 30,
        "timeout": 500000,
        "next": [f"{stepname}autoc", f"{stepname}autoo"],
    }

    nodes[f"{stepname}autoc"] = {
        "recognition": "TemplateMatch",
        "template": ["auto.png"],
        "roi": [1170, 510, 100, 100],
        "threshold": [0.9],
        "action": "Click",
        "pre_delay": 800,
        "post_delay": 15,
        "rate_limit": 30,
        "next": [f"{stepname}ljfdc", f"{stepname}ljfd"],
    }

    nodes[f"{stepname}ljfdc"] = {
        "recognition": "TemplateMatch",
        "template": ["ljfd.png"],
        "threshold": [0.9],
        "action": "Click",
        "pre_delay": 800,
        "post_delay": 15,
        "rate_limit": 30,
        "next": [first_node],
    }

    nodes[f"{stepname}ljfd"] = {
        "recognition": "TemplateMatch",
        "template": ["ljfdo.png"],
        "threshold": [0.9],
        "action": "DoNothing",
        "pre_delay": 20,
        "post_delay": 15,
        "rate_limit": 30,
        "next": [first_node],
    }

    nodes[f"{stepname}autoo"] = {
        "recognition": "TemplateMatch",
        "template": ["autoo.png"],
        "roi": [1170, 510, 100, 100],
        "threshold": [0.85],
        "action": "DoNothing",
        "pre_delay": 15,
        "post_delay": 15,
        "rate_limit": 30,
        "next": [f"{stepname}ljfdc", f"{stepname}ljfd"],
    }

    return nodes


def _finish_node(expected):
    """收尾节点：等待倒计时走到 expected 后点击退出。

    action 沿用原实现的小写 "click"。
    """
    return {
        "recognition": "OCR",
        "roi": [1075, 20, 48, 27],
        "expected": [expected],
        "pre_delay": 15,
        "rate_limit": 30,
        "timeout": 20000,
        "next": [],
        "action": "click",
        "target": [1170, 22, 55, 24],
    }


def _save_and_register(stepname, nodes):
    """写 resource/pipeline/{stepname}.json，并向 interface.json 注册同名 task。"""
    os.makedirs('resource/pipeline', exist_ok=True)
    with open(f'resource/pipeline/{stepname}.json', 'w', encoding='utf-8') as json_file:
        json.dump(nodes, json_file, indent=4, ensure_ascii=False)

    with open('interface.json', 'r', encoding='utf-8') as json_file:
        interface_data = json.load(json_file)

    if not any(task.get('name') == stepname for task in interface_data.get('task', [])):
        interface_data['task'].append({
            "name": f"{stepname}",
            "entry": f"{stepname}entry",
        })
        with open('interface.json', 'w', encoding='utf-8') as json_file:
            json.dump(interface_data, json_file, indent=4, ensure_ascii=False)

    return nodes


def restore_status(stepfile):
    """根据stepfile还原原始status列表，输出O/X字符串"""
    result = []
    current_status = [False] * 6  # 初始状态全为False

    for _, _, status_diff, _ in stepfile:
        # 第一行直接使用status_diff作为状态
        if not result:
            result.append(status_diff)
            current_status = list(status_diff)
        else:
            # 根据status_diff更新current_status
            for i in range(len(current_status)):
                if status_diff[i]:
                    current_status[i] = not current_status[i]
            result.append(list(current_status))

    # 将布尔值列表转换为O/X字符串，在第5位后添加' auto'
    return [''.join('O' if x else 'X' for x in status[:5]) + ' auto' + ('开' if status[5] else '关') for status in result]


def generate_set_pipeline(stepname, stepfile):
    """开关SET模式。

    stepfile: [(时间, 号位, 状态差分, 延时秒), ...]
    """
    stepname, ubflag = _split_offset(stepname)
    sss = restore_status(stepfile)
    total = len(stepfile)
    finish = f"{stepname}p"

    nodes = _entry_nodes(stepname, first_node=f"{stepname}tc_0")

    # 收尾节点 expected 取最后一行的目标时点
    expected_time = '0:01'
    for i, (t, tp, s, tdelay) in enumerate(stepfile):
        # 焦点提示里的下一个待识别时点
        if i < total - 1:
            t1 = stepfile[i + 1][0]
        else:
            t2 = stepfile[i][0]
            t1 = '0:02' if t2 != '0:01' else '0:01'
        expected_time = t1
        next_step = f"{stepname}tc_{i + 1}" if i < total - 1 else finish

        if tp != '6':
            nodes[f"{stepname}tc_{i}"] = {
                "recognition": "OCR",
                "post_delay": tdelay * 1000,
                "roi": [1075, 20, 48, 27],
                "focus": True,
                "focus_tip": f"已识别{t},等待{int(tp)}号位ub",
                "expected": [t],
                "pre_delay": 15,
                "rate_limit": 30,
                "timeout": 500000,
                "next": [f"{stepname}tpc_{i}"],
                "action": "DoNothing",
            }
            nodes[f"{stepname}btpc_{i}"] = {
                "recognition": "ColorMatch",
                "roi": [ubflag[int(tp) - 1], 695, 40, 5],
                "action": "DoNothing",
                "count": 199,
                "upper": [80, 240, 255],
                "lower": [30, 195, 210],
                "rate_limit": 30,
                "timeout": 500000,
                "next": [f"{stepname}tpc_{i}"],
            }
            nodes[f"{stepname}tpc_{i}"] = {
                "threshold": 0.90,
                "recognition": "TemplateMatch" if int(tp) != 0 else "DirectHit",
                "roi": [ubflag[int(tp) - 1], 687, 25, 20],
                "focus": True,
                "focus_tip": [f"预计点击后状态为{sss[i]}", f"等待识别{t1}"],
                "action": "DoNothing",
                "template": ["aub.png"],
                "pre_delay": 50,
                "post_delay": 50,
                "rate_limit": 100,
                "timeout": 500000,
                "next": [f"{stepname}c1_{i}", f"{stepname}c2_{i}", f"{stepname}c3_{i}",
                         f"{stepname}c4_{i}", f"{stepname}c5_{i}", f"{stepname}c6_{i}",
                         next_step],
            }
            # 1~5 号位 UB 点击位；注意 x 坐标在原实现中并不等距
            positions = [300, 460, 660, 780, 940]
            for k in range(5):
                nodes[f"{stepname}c{k + 1}_{i}"] = {
                    "recognition": "DirectHit",
                    "pre_delay": 15,
                    "post_delay": 15,
                    "enabled": bool(s[k]),
                    "action": "Click",
                    "target": [positions[k], 550, 50, 50],
                    "rate_limit": 30,
                    "timeout": 500000,
                    "next": [f"{stepname}c{n}_{i}" for n in range(k + 2, 7)] + [next_step],
                }
            # 6 号位为 auto 开关
            nodes[f"{stepname}c6_{i}"] = {
                "recognition": "DirectHit",
                "pre_delay": 15,
                "post_delay": 15,
                "enabled": bool(s[5]),
                "action": "Click",
                "target": [1195, 537, 30, 30],
                "rate_limit": 30,
                "timeout": 500000,
                "next": [next_step],
            }
        else:
            nodes[f"{stepname}tc_{i}"] = {
                "recognition": "OCR",
                "post_delay": tdelay * 1000,
                "roi": [1075, 20, 48, 27],
                "focus": True,
                "focus_tip": f"已识别{t},自动点击卡帧按钮",
                "expected": [t],
                "pre_delay": 15,
                "rate_limit": 30,
                "timeout": 500000,
                "next": [f"{stepname}tpc_{i}"],
                "action": "DoNothing",
            }
            nodes[f"{stepname}tpc_{i}"] = {
                "threshold": 0.90,
                "recognition": "TemplateMatch",
                "focus": True,
                "focus_tip": ["自行目压,目押结束解除暂停"],
                "action": "Click",
                "template": ["kz.png"],
                "pre_delay": 50,
                "post_delay": 50,
                "rate_limit": 100,
                "timeout": 5000000,
                "next": [next_step],
            }

    nodes[finish] = _finish_node(expected_time)
    return _save_and_register(stepname, nodes)


def generate_single_ub_pipeline(stepname, stepfile, namelist, speed=200):
    """单次UB模式。

    stepfile: 指令串，支持 数字(点击UB) / a+数字(开auto) / d+数字(延时)
              / s+三位数(等倒计时) / k(卡帧)，反斜杠与斜杠会被忽略
    namelist: 五个角色名，与位置顺序一一对应
    """
    stepname, ubflag = _split_offset(stepname)

    nodes = _entry_nodes(stepname, first_node=f"{stepname}0",
                         start_tip="注意关闭属性动画和多目标动画")

    i = 0
    j = 0
    while i < len(stepfile):
        c = stepfile[i]
        if c.isdigit():
            n = int(c)
            name = namelist[n - 1]
            nodes[f"{stepname}{j}"] = {
                "recognition": "DirectHit",
                "pre_delay": 300,
                "post_delay": 500,
                "action": "Click",
                "focus": True,
                "focus_tip": f"点击{name}",
                "target": [140 + n * 160, 550, 50, 50],
                "rate_limit": 1000,
                "timeout": 500000,
                "next": [f"{stepname}{j}done"],
            }
            nodes[f"{stepname}{j}done"] = {
                "threshold": 0.5,
                "recognition": "TemplateMatch",
                "roi": [200 + 160 * n, 505, 50, 50],
                "inverse": True,
                "action": "DoNothing",
                "template": ["mfd.png"],
                "pre_delay": speed,
                "post_delay": speed,
                "rate_limit": 2 * speed,
                "timeout": 500000,
                "next": [f"{stepname}{j}_done"],
            }
            nodes[f"{stepname}{j}_done"] = {
                "threshold": 0.5,
                "recognition": "TemplateMatch",
                "roi": [200 + 160 * n, 505, 50, 50],
                "focus": True,
                "focus_tip": f"{name}已ub",
                "inverse": True,
                "action": "DoNothing",
                "template": ["mfd.png"],
                "pre_delay": speed,
                "post_delay": speed,
                "rate_limit": 2 * speed,
                "timeout": 500000,
                "next": [f"{stepname}{j + 1}"],
            }
            i += 1
            j += 1
        elif c in ('a', 'A') and i + 1 < len(stepfile) and stepfile[i + 1].isdigit():
            n = int(stepfile[i + 1])
            name = namelist[n - 1]
            nodes[f"{stepname}{j}"] = {
                "recognition": "DirectHit",
                "pre_delay": speed,
                "post_delay": speed,
                "action": "Click",
                "focus": True,
                "focus_tip": f"开auto,等待{name}自动ub",
                "target": [1195, 537, 30, 30],
                "rate_limit": speed * 3,
                "timeout": 500000,
                "next": [f"{stepname}{j}check"],
            }
            nodes[f"{stepname}{j}check"] = {
                "threshold": 0.90,
                "recognition": "TemplateMatch",
                "roi": [ubflag[n - 1], 687, 25, 20],
                "focus": True,
                "focus_tip": f"{name}已自动ub",
                "action": "DoNothing",
                "template": ["aub.png"],
                "pre_delay": speed,
                "post_delay": speed,
                "rate_limit": speed * 3,
                "timeout": 500000,
                "next": [f"{stepname}{j}done"],
            }
            nodes[f"{stepname}{j}done"] = {
                "recognition": "DirectHit",
                "pre_delay": speed,
                "post_delay": speed * 2,
                "action": "Click",
                "focus": True,
                "focus_tip": "关auto",
                "target": [1195, 537, 30, 30],
                "rate_limit": speed * 3,
                "timeout": 500000,
                "next": [f"{stepname}{j + 1}"],
            }
            i += 2
            j += 1
        elif c in ('d', 'D') and i + 1 < len(stepfile) and stepfile[i + 1].isdigit():
            t = int(stepfile[i + 1])
            nodes[f"{stepname}{j}"] = {
                "recognition": "DirectHit",
                "pre_delay": 15,
                "post_delay": t * 1000,
                "rate_limit": 1000,
                "timeout": 500000,
                "action": "DoNothing",
                "next": [f"{stepname}{j + 1}"],
            }
            i += 2
            j += 1
        elif c in ('s', 'S') and i + 3 < len(stepfile) and all(x.isdigit() for x in stepfile[i + 1:i + 4]):
            tp = f"{stepfile[i + 1]}:{stepfile[i + 2:i + 4]}"
            nodes[f"{stepname}{j}"] = {
                "recognition": "OCR",
                "post_delay": 15,
                "roi": [1075, 20, 48, 27],
                "focus": True,
                "focus_tip": f"已识别{tp}",
                "expected": [tp],
                "pre_delay": 15,
                "rate_limit": 30,
                "timeout": 500000,
                "action": "DoNothing",
                "next": [f"{stepname}{j + 1}"],
            }
            i += 4
            j += 1
        elif c == 'k':
            nodes[f"{stepname}{j}"] = {
                "recognition": "OCR",
                "threshold": 0.75,
                "action": "Click",
                "expected": ["卡帧|菜单"],
                "pre_delay": speed,
                "post_delay": speed,
                "rate_limit": 100,
                "timeout": 5000000,
                "next": [f"{stepname}{j}_e"],
            }
            nodes[f"{stepname}{j}_e"] = {
                "recognition": "OCR",
                "threshold": 0.75,
                "focus": True,
                "focus_tip": ["自行目压,目押完毕点击 设定"],
                "action": "Click",
                "expected": ["卡帧|菜单"],
                "pre_delay": speed,
                "post_delay": speed,
                "rate_limit": 100,
                "timeout": 5000000,
                "next": [f"{stepname}{j}gb"],
            }
            nodes[f"{stepname}{j}gb"] = {
                "recognition": "TemplateMatch",
                "pre_delay": speed,
                "post_delay": speed,
                "template": ["gb.png"],
                "action": "Click",
                "next": [f"{stepname}{j}done"],
            }
            nodes[f"{stepname}{j}done"] = {
                "recognition": "TemplateMatch",
                "pre_delay": speed,
                "post_delay": speed * 3,
                "template": ["fh.png"],
                "action": "Click",
                "next": [f"{stepname}{j + 1}"],
            }
            i += 1
            j += 1
        elif c in ('\\', '/'):
            i = i + 1
        else:
            raise KeyError(f"Invalid character '{c}' in stepfile at position {i}")

    nodes[f"{stepname}{j}"] = _finish_node("0:01")
    return _save_and_register(stepname, nodes)
