import json
import os



def generation(stepname,stepfile,namelist,speed):
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
    "next": ["{stepname}0"]}},
    "{stepname}ljfd": {{
    "recognition": "TemplateMatch",
    "template": [
    "ljfdo.png"
    ],
    "threshold": [
    0.95
    ],
    "action": "DoNothing","pre_delay":20,"post_delay":15,"rate_limit":30,
    "next": ["{stepname}0"]}},
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

    actions = []
    i = 0
    j=0
    s = stepfile
    while i < len(s):
        c = s[i]
        if c.isdigit():
            n = int(c)
            actions.append(f'''"{stepname}{j}": {{
    "recognition": "DirectHit","pre_delay":300,"post_delay":500,
    "action": "Click",
    "focus":true,
    "focus_tip":"点击{namelist[n-1]}",
    "target": [
    {140+n*160},
    550,
    50,
    50
    ],"rate_limit":1000,"timeout":500000,"next": [
    "{stepname}{j}done"
    ]
    }},''')
            actions.append(f''' "{stepname}{j}done":{{
    "threshold": 0.5,
    "recognition": "TemplateMatch",
    "roi": [

    {200+160*n},
        505,
        50,
        50

    ],
    "inverse": true,
    "action": "DoNothing",
    "template": [
        "mfd.png"
    ],"pre_delay":{speed},"post_delay":{speed},"rate_limit":{2*speed},"timeout":500000,"next": [
    "{stepname}{j}_done"
    ]
    }},''')
            actions.append(f''' "{stepname}{j}_done":{{
    "threshold": 0.5,
    "recognition": "TemplateMatch",
    "roi": [

    {200+160*n},
        505,
        50,
        50

    ],
    "focus":true,
    "focus_tip":"{namelist[n-1]}已ub",
    "inverse": true,
    "action": "DoNothing",
    "template": [
        "mfd.png"
    ],"pre_delay":{speed},"post_delay":{speed},"rate_limit":{2*speed},"timeout":500000,"next": [
    "{stepname}{j+1}"
    ]
    }},''')
            i += 1
            j+= 1
        elif c in ('a', 'A') and i + 1 < len(s) and s[i+1].isdigit():
            n = int(s[i+1])
            actions.append(f'''"{stepname}{j}": 
                           {{
    "recognition": "DirectHit","pre_delay":{speed},"post_delay":{speed},
    "action": "Click",
    "focus":true,
    "focus_tip":"开auto,等待{namelist[n-1]}自动ub",
    "target": [
    1195,
    537,
    30,
    30
    ],"rate_limit":{speed*3},"timeout":500000,"next": ["{stepname}{j}check"]
    }},''')
            actions.append(f'''"{stepname}{j}check": {{
                           "threshold": 0.90,
    "recognition": "TemplateMatch",
    "roi": [
    {ubflag[n-1]},
        687,
        25,
        20
    ],
    "focus":true,
    "focus_tip":"{namelist[n-1]}已自动ub",
    "action": "DoNothing",
    "template": [
        "aub.png"
    ],"pre_delay":{speed},"post_delay":{speed},"rate_limit":{speed*3},"timeout":500000,"next": [
    "{stepname}{j}done"
    ]
                            }},''')
            actions.append(f'''"{stepname}{j}done": {{
    "recognition": "DirectHit","pre_delay":{speed},"post_delay":{speed*2},
    "action": "Click",
    "focus":true,
    "focus_tip":"关auto",
    "target": [
    1195,
    537,
    30,
    30
    ],"rate_limit":{speed*3},"timeout":500000,"next": ["{stepname}{j+1}"]
    }},''')
            i += 2
            j+= 1
        elif c in ('d', 'D') and i + 1 < len(s) and s[i+1].isdigit():
            t = int(s[i+1])
            actions.append(f'"{stepname}{j}": {{ "recognition": "DirectHit", "pre_delay": 15, "post_delay": {t*1000},  "rate_limit": 1000, "timeout": 500000, "action": "DoNothing", "next": ["{stepname}{j+1}"] }},')

            i += 2
            j+=1
        elif c in ('s', 'S') and i + 3 < len(s) and all(x.isdigit() for x in s[i+1:i+4]):
            tp = str(s[i+1])+':'+ str(s[i+2:i+4])
            actions.append(f'''"{stepname}{j}":
                            {{
                             "recognition": "OCR",
    "post_delay":15,
    "roi": [
    1075,
    20,
    48,
    27
    ],
    "focus":true,
    "focus_tip":"已识别{tp}",
    "expected": [
    "{tp}"
    ],"pre_delay":15,"rate_limit":30,"timeout":500000,
    "action": "DoNothing"
    ,"next": ["{stepname}{j+1}"]
                              }},''')
            i += 4
            j += 1
        elif c == 'k':
            actions.append(f'''"{stepname}{j}": 
                           {{ "recognition": "TemplateMatch", "threshold": 0.75, 
                           "action": "Click", "template": ["kz.png"], "pre_delay": {speed}, "post_delay": {speed}, "rate_limit": 100, "timeout": 5000000,
                            "next": ["{stepname}{j}_e"] 
                           }},''')
            actions.append(f'''"{stepname}{j}_e": 
                           {{ "recognition": "TemplateMatch", "threshold": 0.75, "focus": true, "focus_tip": ["自行目压,目押完毕点击 设定"], 
                           "action": "Click", "template": ["kz.png"], "pre_delay": {speed}, "post_delay": {speed}, "rate_limit": 100, "timeout": 5000000,
                            "next": ["{stepname}{j}gb"] 
                           }},''')
            actions.append(f'"{stepname}{j}gb": {{ "recognition": "TemplateMatch", "pre_delay": {speed}, "post_delay": {speed},"template": ["gb.png"], "action": "Click", "next": ["{stepname}{j}done"] }},')
            actions.append(f'"{stepname}{j}done": {{ "recognition": "TemplateMatch", "pre_delay": {speed}, "post_delay": {speed*3},"template": ["fh.png"], "action": "Click", "next": ["{stepname}{j+1}"] }},')
            i += 1
            j += 1
        elif c == '\\'or c=='/':
            i=i + 1
        else:
            raise KeyError(f"Invalid character '{c}' in stepfile at position {i}")
    actions.append(f'''"{stepname}{j}":  {{"recognition": "OCR",
    "roi": [
    1075,
    20,
    48,
    27
    ],
    "expected": ["0:01"],"pre_delay": 15,"rate_limit":30,"timeout":20000,"next": [],
    "action": "click","target": [
    1170,
    22,
    55,
    24
    ]
    }}''')

    output_s += "\n".join(actions)
    output_s += "\n}"

    data = json.loads(output_s)

    # 在保存文件前创建目录
    os.makedirs('resource/pipeline', exist_ok=True)
    
    # 保存为 JSON 文件
    with open(f'resource/pipeline/{stepname}.json', 'w',encoding='utf-8') as json_file:
        json.dump(data, json_file, indent=4, ensure_ascii=False)
    with open('interface.json', 'r', encoding='utf-8') as json_file:
        data = json.load(json_file)


    new_task = {
    "name": f"{stepname}",
    "entry": f"{stepname}start"
    }
    data['task'].append(new_task)


    with open('interface.json', 'w', encoding='utf-8') as json_file:
        json.dump(data, json_file, indent=4, ensure_ascii=False)
    return output_s

if __name__ == "__main__":
    stepfile = '''s114k1254435123s05935423a13542143532143k23313452315425433154234512335a142s029353253a14254324352331a453243124a512513244513253451234251435244351235a4254a124451254'''
     # Example stepfile, replace with actual stepfile
    namelist=['雪','狐','N','水','春']
    generation('5手动', stepfile,namelist)  # Example usage, replace with actual stepfile