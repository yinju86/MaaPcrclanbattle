import json


def generation(stepname,stepfile):
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
    "action": "Click","rate_limit":30,"timeout":500000,"next": [
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
    "action": "Click","rate_limit":30,"timeout":500000,"next": [
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
    "action": "Click","pre_delay":500,"post_delay":15,"rate_limit":30,
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
    "next": ["{stepname}tc_0"]
    }},
    '''
    for i in range(len(stepfile)):
        t,tp,s,tdelay=stepfile[i]
        output_s= output_s+f'''"{stepname}tc_{i}": {{
    "recognition": "OCR",
    "post_delay":{tdelay*1000},
    "roi": [
    1075,
    20,
    48,
    27
    ],
    "expected": [
    "{t}"
    ],"rate_limit":30,"timeout":500000,"next": [
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
    "action": "DoNothing",
    "template": [
        "aub.png"
    ],"rate_limit":500,"timeout":500000,"next": [
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
    output_s=output_s.replace(f',"{stepname}tc_{len(stepfile)}"',f',"{stepname}p"').replace(f'''"timeout":500000,"next": ["{stepname}tc_{len(stepfile)}"]
    }},''',f'''"timeout":500000,"next": ["{stepname}p"]
    }},"{stepname}p":{{"recognition": "OCR",
    "roi": [
    1075,
    20,
    48,
    27
    ],
    "expected": ["0:02"],"pre_delay": 15,"rate_limit":30,"timeout":20000,"next": [],
    "action": "click","target": [
    1170,
    22,
    55,
    24
    ]
    }}}}''').replace('\n', '').replace('False', 'false').replace('True', 'true').replace("\t", "").strip()
    data = json.loads(output_s)

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

    
