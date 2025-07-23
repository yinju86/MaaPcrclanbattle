import json
import os


def generation(stepname,stepfile):
    sss=restore_status(stepfile)
    ubflag=[310,470,630,790,950]
    output_s=f'''{{
    "{stepname}start": {{
    "recognition": "TemplateMatch",
    "threshold": [
    0.95
    ],
    "template": [
    "start.png"
    ],
    "action": "Click",
    "next": [
    "{stepname}start0"
    ]
    }},"{stepname}start0": {{
    "recognition": "TemplateMatch",
    "threshold": [
    0.95
    ],
    "template": [
    "start0.png"
    ],
    "action": "Click","pre_delay":100,"post_delay":15,"rate_limit":30,"timeout":500000,"next": [
    "{stepname}start2","{stepname}autoc","{stepname}autoo"
    ]
    }},"{stepname}start2": {{
    "recognition": "TemplateMatch",
    "threshold": [
    0.95
    ],
    "template": [
    "start2.png"
    ],
    "action": "Click","pre_delay":100,"post_delay":15,"rate_limit":30,"timeout":500000,"next": [
    "{stepname}autoc","{stepname}autoo"
    ]
    }},"{stepname}autoc": {{
    "recognition": "TemplateMatch",
    "template": [
    "auto.png"
    ],
    "roi": [
    1170,
    510,
    100,
    100
    ],
    "threshold": [
    0.95
    ],
    "action": "Click","pre_delay":800,"post_delay":15,"rate_limit":30,
    "next": ["{stepname}ljfdc","{stepname}ljfd"]}},
    "{stepname}ljfdc": {{
    "recognition": "TemplateMatch",
    "template": [
    "ljfd.png"
    ],
    "threshold": [
    0.95
    ],
    "action": "Click","pre_delay":800,"post_delay":15,"rate_limit":30,
    "next": ["{stepname}tc_0"]}},
    "{stepname}ljfd": {{
    "recognition": "TemplateMatch",
    "template": [
    "ljfdo.png"
    ],
    "threshold": [
    0.95
    ],
    "action": "DoNothing","pre_delay":20,"post_delay":15,"rate_limit":30,
    "next": ["{stepname}tc_0"]}},
    "{stepname}autoo": {{
    "recognition": "TemplateMatch",
    "template": [
    "autoo.png"
    ],
    "roi": [
    1170,
    510,
    100,
    100
    ],
    "threshold": [
    0.85
    ],
    "action": "DoNothing","pre_delay":15,"post_delay":15,"rate_limit":30,
    "next": ["{stepname}ljfdc","{stepname}ljfd"]}},
    '''
    for i in range(len(stepfile)):
        t,tp,s,tdelay=stepfile[i]
        if i<len(stepfile)-1:
            t1=stepfile[i+1][0]
        else:
            t2=stepfile[i][0]
            t1='0:02' if t2!='0:01' else '0:01'
        if tp!='6':
            output_s= output_s+f'''"{stepname}tc_{i}": {{
    "recognition": "OCR",
    "post_delay":{tdelay*1000},
    "roi": [
    1075,
    20,
    48,
    27
    ],
    "focus":true,
    "focus_tip":"已识别{t}",
    "expected": [
    "{t}"
    ],"pre_delay":15,"rate_limit":30,"timeout":500000,"next": [
    "{stepname}tpc_{i}"
    ],
    "action": "DoNothing"
    }},"{stepname}btpc_{i}": {{
    "recognition": "ColorMatch",
    "roi": [

    {ubflag[int(tp)-1]},
    695,
    40,
    5

    ],
    "action": "DoNothing",
    "count":199,
    "upper": [

    80,
    240,
    255

    ],
    "lower": [

    30,
    195,
    210

    ],"rate_limit":30,"timeout":500000,"next": [
    "{stepname}tpc_{i}"
    ]
    }},"{stepname}tpc_{i}": {{
    "threshold": 0.90,
    "recognition": "{"TemplateMatch" if int(tp) !=0 else "DirectHit"}",
    "roi": [

    {ubflag[int(tp)-1]},
        687,
        25,
        20

    ],
    "focus":true,
    "focus_tip":["预计点击后状态为{sss[i]}","等待识别{t1}"],
    "action": "DoNothing",
    "template": [
        "aub.png"
    ],"pre_delay":50,"post_delay":50,"rate_limit":100,"timeout":500000,"next": [
    "{stepname}c1_{i}","{stepname}c2_{i}","{stepname}c3_{i}","{stepname}c4_{i}","{stepname}c5_{i}","{stepname}c6_{i}","{stepname}tc_{i+1}"
    ]
    }},"{stepname}c1_{i}": {{
    "recognition": "DirectHit","pre_delay":15,"post_delay":15,
    "enabled":{s[0]},
    "action": "Click",
    "target": [
    300,
    550,
    50,
    50
    ],"rate_limit":30,"timeout":500000,"next": [
    "{stepname}c2_{i}","{stepname}c3_{i}","{stepname}c4_{i}","{stepname}c5_{i}","{stepname}c6_{i}","{stepname}tc_{i+1}"
    ]
    }},"{stepname}c2_{i}": {{
    "recognition": "DirectHit","pre_delay":15,"post_delay":15,
    "enabled":{s[1]},
    "action": "Click",
    "target": [
    460,
    550,
    50,
    50
    ],"rate_limit":30,"timeout":500000,"next": [
    "{stepname}c3_{i}","{stepname}c4_{i}","{stepname}c5_{i}","{stepname}c6_{i}","{stepname}tc_{i+1}"
    ]
    }},"{stepname}c3_{i}": {{
    "recognition": "DirectHit","pre_delay":15,"post_delay":15,
    "enabled":{s[2]},
    "action": "Click",
    "target": [
    660,
    550,
    50,
    50
    ],"rate_limit":30,"timeout":500000,"next": [
    "{stepname}c4_{i}","{stepname}c5_{i}","{stepname}c6_{i}","{stepname}tc_{i+1}"]
    }},"{stepname}c4_{i}": {{
    "recognition": "DirectHit","pre_delay":15,"post_delay":15,
    "enabled":{s[3]},
    "action": "Click",
    "target": [
    780,
    550,
    50,
    50
    ],"rate_limit":30,"timeout":500000,"next": [
    "{stepname}c5_{i}","{stepname}c6_{i}","{stepname}tc_{i+1}"]
    }},"{stepname}c5_{i}": {{
    "recognition": "DirectHit","pre_delay":15,"post_delay":15,
    "enabled":{s[4]},
    "action": "Click",
    "target": [
    940,
    550,
    50,
    50
    ],"rate_limit":30,"timeout":500000,"next": ["{stepname}c6_{i}","{stepname}tc_{i+1}"]
    }},"{stepname}c6_{i}": {{
    "recognition": "DirectHit","pre_delay":15,"post_delay":15,
    "enabled":{s[5]},
    "action": "Click",
    "target": [
    1195,
    537,
    30,
    30
    ],"rate_limit":30,"timeout":500000,"next": ["{stepname}tc_{i+1}"]
    }},
    '''
        else:
            output_s= output_s+f'''"{stepname}tc_{i}": {{
    "recognition": "OCR",
    "post_delay":{tdelay*1000},
    "roi": [
    1075,
    20,
    48,
    27
    ],
    "focus":true,
    "focus_tip":"已识别{t}",
    "expected": [
    "{t}"
    ],"pre_delay":15,"rate_limit":30,"timeout":500000,"next": [
    "{stepname}tpc_{i}"
    ],
    "action": "DoNothing"
    }},"{stepname}tpc_{i}": {{
    "threshold": 0.90,
    "recognition": "TemplateMatch",
    
    "focus":true,
    "focus_tip":["自行目压"],
    "action": "Click",
    "template": [
        "kz.png"
    ],"pre_delay":50,"post_delay":50,"rate_limit":100,"timeout":5000000,
    "next": ["{stepname}tc_{i+1}"]
    }},
    '''
    output_s=output_s.replace(f',"{stepname}tc_{len(stepfile)}"',f',"{stepname}p"').replace(f'''"timeout":500000,"next": ["{stepname}tc_{len(stepfile)}"]
    }},''',f'''"timeout":500000,"next": ["{stepname}p"]
    }},"{stepname}p":{{"recognition": "OCR",
    "roi": [
    1075,
    20,
    48,
    27
    ],
    "expected": ["{t1}"],"pre_delay": 15,"rate_limit":30,"timeout":20000,"next": [],
    "action": "click","target": [
    1170,
    22,
    55,
    24
    ]
    }}}}''').replace('\n', '').replace('False', 'false').replace('True', 'true').replace("\t", "").strip()

    data = json.loads(output_s)

    # 在保存文件前创建目录
    os.makedirs('resource/pipeline', exist_ok=True)
    
    # 保存为 JSON 文件
    with open(f'resource/pipeline/{stepname}.json', 'w',encoding='utf-8') as json_file:
        json.dump(data, json_file, indent=4, ensure_ascii=False)
    with open('interface.json', 'r', encoding='utf-8') as json_file:
        interface_data = json.load(json_file)

    # 检查是否有同名 task，若有则跳过追加和写入
    if not any(task.get('name') == stepname for task in interface_data.get('task', [])):
        new_task = {
            "name": f"{stepname}",
            "entry": f"{stepname}start"
        }
        interface_data['task'].append(new_task)
        with open('interface.json', 'w', encoding='utf-8') as json_file:
            json.dump(interface_data, json_file, indent=4, ensure_ascii=False)

    

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

    
