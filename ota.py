import requests
import brotli
import json
import sqlite3
import os
import PIL.Image as Image

def updateCharacterIndexListByURL(url):
    print("开始尝试更新CharacterIndexList。来源：%s" % url)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36',
        'Referer': 'https://redive.estertion.win/api.htm',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.9',
        'Accept-Encoding': 'br',
        'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh-TW;q=0.7,zh;q=0.6,ja;q=0.5',
        'Accept-Charset': "UTF-8"
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = brotli.decompress(response.content)
            savedBinFile = open("CharData//Database.db", "wb")
            savedBinFile.write(data)
            savedBinFile.close()
            connection = sqlite3.connect("CharData//Database.db")
            unitDataCursor = connection.cursor().execute("SELECT a.* FROM unit_skill_data b, unit_data a WHERE a.unit_id = b.unit_id AND a.unit_id < 400000")
            characterIndexList = []
            for row in unitDataCursor:
                characterIndexList.append({"unit_id": row[0], "unit_name": row[1]})
            characterIndexListJsonFile = open("CharData//characterIndexList.json", 'w', encoding='utf-8')
            json.dump(characterIndexList, characterIndexListJsonFile, ensure_ascii=False)
            characterIndexListJsonFile.close()
        print("成功更新CharacterIndexList。来源：%s" % url)
        return None
    except Exception as e:
        print(e)
        print("updateCharacterIndexListByURL失败")
        return None

def updateAssetsByCharacterIndexList(characterIndexList):
    SixCharIDList = []
    try: 
        connection = sqlite3.connect("CharData//Database.db")
        unitDataCursor = connection.cursor().execute("SELECT * from unlock_rarity_6 where unlock_flag = 1")
        for row in unitDataCursor:
            SixCharIDList.append(str(row[0])[:4])
    except:
        print("没有获取到六星角色信息。")
    
    def checkIfMissingSix(charId):
        flag = False
        if charId in SixCharIDList:
            if not os.path.exists(os.path.join("CharData", "%s61.webp" % charId)):
                flag = True
        return flag
        
    print("开始尝试更新角色图像。")
    for entry in characterIndexList:
        charId = str(entry["unit_id"])[:4]
        __missingOne = not os.path.exists(os.path.join("CharData", "%s11.webp" % charId))
        __missingThree = not os.path.exists(os.path.join("CharData", "%s31.webp" % charId))
        __missingSix = checkIfMissingSix(charId)
        if __missingOne or __missingThree or __missingSix:
            print("发现%s(id:%s)的头像文件缺失，尝试重新获取" % (entry["unit_name"], entry["unit_id"]))
            webpURLOne = "https://redive.estertion.win/icon/unit/%s11.webp" % charId
            webpURLThree = "https://redive.estertion.win/icon/unit/%s31.webp" % charId
            webpURLSix = "https://redive.estertion.win/icon/unit/%s61.webp" % charId
            try:
                if __missingOne:
                    print("尝试获取%s(id:%s)的一星头像文件（url: %s)" % (entry["unit_name"], entry["unit_id"], webpURLOne))
                    webpContentOne = requests.get(webpURLOne)
                    if webpContentOne.status_code == 200:
                        with open(os.path.join("CharData", "%s11.webp" % charId), 'wb') as file:
                            file.write(webpContentOne.content)
                            print("成功下载角色头像（角色名：%s, 角色id：%s，角色头像星级：1)" % (entry["unit_name"], entry["unit_id"]))
                if __missingThree:
                    print("尝试获取%s(id:%s)的三星头像文件（url: %s)" % (entry["unit_name"], entry["unit_id"], webpURLThree))
                    webpContentThree = requests.get(webpURLThree)
                    if webpContentThree.status_code == 200:
                        with open(os.path.join("CharData", "%s31.webp" % charId), 'wb') as file:
                            file.write(webpContentThree.content)
                            print("成功下载角色头像（角色名：%s, 角色id：%s，角色头像星级：3)" % (entry["unit_name"], entry["unit_id"]))
                if __missingSix:
                    print("尝试获取%s(id:%s)的六星头像文件（url: %s)" % (entry["unit_name"], entry["unit_id"], webpURLSix))
                    webpContentSix = requests.get(webpURLSix)
                    if webpContentSix.status_code == 200:
                        with open(os.path.join("CharData", "%s61.webp" % charId), 'wb') as file:
                            file.write(webpContentSix.content)
                            print("成功下载角色头像（角色名：%s, 角色id：%s, 角色头像星级：6)" % (entry["unit_name"], entry["unit_id"]))
            except Exception as e:
                print("尝试获取%s（id:%s)头像文件失败(FlagOne:%s, FlagThree:%s, FlagSix:%s)" % (entry["unit_name"], entry["unit_id"], __missingOne, __missingThree, __missingSix))
    print("更新角色图像完成。")

def generateRefImageByCharacterIndexList(characterIndexList):
    print("开始尝试拼接头像生成refImage。")
    refImagePath = os.path.join("CharData", "refImage.png")
    refImage = Image.new('RGBA', (len(characterIndexList) * (60+2) * 3, 62))
    for index in range(len(characterIndexList)):
        charId = str(characterIndexList[index]['unit_id'])[:4]
        try:
            icon_imageOne = Image.open(os.path.join("CharData", "%s11.webp" % charId)).resize((60, 60), Image.ANTIALIAS)
            coordinateImageOne = ((2+3*62*index, 2))
            refImage.paste(icon_imageOne, coordinateImageOne)
            icon_imageThree = Image.open(os.path.join("CharData", "%s31.webp" % charId)).resize((60, 60), Image.ANTIALIAS)
            coordinateImageThree = ((64+3*62*index, 2))
            refImage.paste(icon_imageThree, coordinateImageThree)
            icon_imageSix = Image.open(os.path.join("CharData", "%s61.webp" % charId)).resize((60, 60), Image.ANTIALIAS)
            coordinateImageSix = ((126+3*62*index, 2))
            refImage.paste(icon_imageSix, coordinateImageSix)
        except Exception as e:
            print("图片粘贴失败, 可能是没有成功下载到文件。Exception: %s" % e)
    refImage.save(refImagePath)
    print("成功更新refImage")

def devMain():
    url = "https://redive.estertion.win/db/redive_cn.db.br"
    updateCharacterIndexListByURL(url)
    characterIndexListJsonFile = open("CharData//characterIndexList.json",'r',encoding='utf-8')
    characterIndexList = json.load(characterIndexListJsonFile)
    
    
    updateAssetsByCharacterIndexList(characterIndexList)
    generateRefImageByCharacterIndexList(characterIndexList)

if __name__ == "__main__":
    # 直接执行则为开发模式入口
    devMain()