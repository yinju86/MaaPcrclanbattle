import json
import pygtrie
import os
import cv2
def loadlist():
    with open("CharData\\CHARA_NAME.json", 'r', encoding='utf-8') as f:
        chara_name_str = json.load(f)
    roster=pygtrie.CharTrie()
    for idx, names in chara_name_str.items():
        for n in names:
            if n not in roster:
                roster[n] = idx
            else:
                print(n,idx)
    all_name_list = roster.keys()
    return all_name_list,roster
def parse_team(namestr):
    team = []
    all_name_list,roster=loadlist()
    while namestr:
        item = roster.longest_prefix(namestr)
        if not item:
            namestr = namestr[1:].lstrip()
        else:
            team.append(item.value)
            namestr = namestr[len(item.key):].lstrip()
    return team

def find_file_in_subdirs(target_filename, current_directory="."):
    """
    在当前文件夹及其子文件夹中查找特定文件名。

    :param target_filename: 要查找的文件名（包括扩展名）。
    :param current_directory: 起始搜索的目录，默认为当前目录。
    :return: 如果找到，返回文件的完整路径；如果未找到，返回 None。
    """
    for root, dirs, files in os.walk(current_directory):
        if target_filename in files:
            return True
    return False

def rewrite(sname,namestr,boss):
    namelist=[]
    with open("reference.json", 'r', encoding='utf-8') as f:
        reference = json.load(f)
    star=False
    if "一星花凛" in namestr:
        namestr=namestr.replace("一星花凛","花凛")
        star=True
    
    numlist=parse_team(namestr)    
    if len(numlist)!=5:
        return ""
    with open("CharData\\characterIndexList.json", 'r', encoding='utf-8') as f:
        json_data = json.load(f)
    

    reference[f"click_boss{boss}"]["enable"]=True
    result_dict = {item["unit_id"]: item["unit_name"] for item in json_data}
    for i,charnum in enumerate(numlist):
        text=result_dict[int(charnum+"01")]
        namelist.append(text)
        text0=text[0]
        reference[f"input_text_{i+1}"]["input_text"]=text0
        reference[f"find{i+1}"]["focus_tip"]= [f"选角色{text}"]
        if find_file_in_subdirs(f"{charnum}61.webp"):
            process_and_save_image(f"CharData\\{charnum}61.webp",f"resource\\image\\{charnum}61.jpg")
            reference[f"find{i+1}"]["template"]=[f'{charnum}61.jpg']
        elif str(charnum)=="1185" and star:
            process_and_save_image(f"CharData\\{charnum}11.webp",f"resource\\image\\{charnum}11.jpg")
            reference[f"find{i+1}"]["template"]=[f'{charnum}11.jpg']
        else:
            process_and_save_image(f"CharData\\{charnum}31.webp",f"resource\\image\\{charnum}31.jpg")
            reference[f"find{i+1}"]["template"]=[f'{charnum}31.jpg']
    updated_data = {}

    for key, value in reference.items():
        # 修改第一层名字
        new_key = f"{sname}{key}"
        
        # 深拷贝 value，避免修改原数据
        new_value = value.copy()

        # 修改 "next" 字段中的内容
        if "next" in new_value:
            new_value["next"] = [f"{sname}{item}" for item in new_value["next"]]

        updated_data[new_key] = new_value
    os.makedirs('resource/pipeline', exist_ok=True)
    with open(f'resource\\pipeline\\{sname}选人.json', 'w', encoding='utf-8') as f:
        json.dump(updated_data, f, indent=4, ensure_ascii=False)
    with open('interface.json', 'r', encoding='utf-8') as json_file:
        data = json.load(json_file)


    new_task = {
    "name": f"{sname}选人",
    "entry": f"{sname}click_adventure"
    }
    data['task'].append(new_task)


    with open('interface.json', 'w', encoding='utf-8') as json_file:
        json.dump(data, json_file, indent=4, ensure_ascii=False)
    
    return ''.join(namelist)

def process_and_save_image(input_path: str, output_path: str):
    """
    输入图片路径和输出路径，
    如果输出路径的文件已存在，则直接返回；否则处理图片并保存。

    处理步骤：
    1. 裁剪图片的15%-85%区域（删除边缘）。
    2. 保持高宽比缩放图片至高度为40像素。
    3. 保存至输出路径。
    
    Args:
        input_path (str): 输入图片路径。
        output_path (str): 输出图片路径。
    """
    # 检查输出路径是否存在文件
    if os.path.exists(output_path):
        print(f"Output file '{output_path}' already exists. Skipping processing.")
        return

    # 读取输入图片
    image = cv2.imread(input_path)
    if image is None:
        raise ValueError(f"Input file '{input_path}' could not be read. Please check the path.")

    # 获取图片的高和宽
    height, width = image.shape[:2]

    # 计算裁剪范围（15%-85%）
    h_start, h_end = int(0.15 * height), int(0.85 * height)
    w_start, w_end = int(0.15 * width), int(0.85 * width)

    # 裁剪图片
    cropped_image = image[h_start:h_end, w_start:w_end]

    # 计算缩放后的宽度，保持高宽比，高度固定为40像素
    new_height = 60
    aspect_ratio = cropped_image.shape[1] / cropped_image.shape[0]
    new_width = int(new_height * aspect_ratio)

    # 缩放图片
    resized_image = cv2.resize(cropped_image, (new_width, new_height), interpolation=cv2.INTER_AREA)

    # 保存图片到输出路径
    cv2.imwrite(output_path, resized_image)



if __name__=="__main__":
    rewrite('C3',"暴击弓生菜亚里沙春妈圣优妮",3)