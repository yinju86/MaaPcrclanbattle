import sys
from PyQt5.QtWidgets import QLineEdit,QApplication, QWidget,QLabel, QVBoxLayout, QTableWidget, QTableWidgetItem, QComboBox, QPushButton, QCheckBox, QMessageBox,QHBoxLayout,QDialog,QTextEdit, QMenuBar, QMenu, QActionGroup, QFileDialog
from PyQt5.QtCore import Qt, QPoint, QThread, pyqtSignal, QBuffer, QIODevice, QTimer
from PyQt5.QtGui import QIntValidator, QImage, QPixmap, QKeySequence
import random
import base64
import sharecode
import json
from pathlib import Path
import webbrowser
import requests  # 添加到文件顶部的imports中
import pipeline
from pipeline import build_set_steps
import re
import cli  # 程序目录 / 版本号 / 命令行接口，GUI 与 CLI 共用同一份
from cli import app_dir, get_version


def parse_namelist(text):
    """按空白切分角色名，返回列表。

    无参 split() 会把连续多个空格视作单个分隔符并丢弃空片段，
    避免 "雪  狐" 这类输入切出空串导致角色名与位置错位。
    """
    return text.split()


# ================================================================ AI 模式
# 接口配置存在程序目录下的 ai_config.json（含明文 API Key，已加进 .gitignore）
AI_CONFIG_PATH = app_dir() / "ai_config.json"

# 默认走 DeepSeek：OpenAI 兼容格式，base_url 不需要带 /v1，
# 代码会自动补 /chat/completions。deepseek-flash 原生支持图片输入，
# 直接吃 image_url 的 base64 data URL，无需另开 vision 专用模型。
DEFAULT_AI_CONFIG = {
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-flash",
    "api_key": "",
    "auto_generate": True,
}


def load_ai_config():
    """读本地配置；缺项或空串一律退回默认值（默认 DeepSeek）。

    放在模块级是为了让命令行接口（cli.py）不依赖界面也能取到配置。
    """
    config = dict(DEFAULT_AI_CONFIG)
    try:
        stored = json.loads(AI_CONFIG_PATH.read_text(encoding="utf-8"))
        if isinstance(stored, dict):
            for key, value in stored.items():
                # 空串当作「没配过」，否则把输入框清空一次就再也回不到默认值
                if isinstance(value, str) and not value.strip():
                    continue
                config[key] = value
    except Exception:
        pass
    return config

# 轴图上这些字眼在指令串里都是同一个意思：k（卡帧目押）
# 整串里出现就算（这些词不可能是角色名的一部分）
UB_FRAME_WORDS = ("卡帧", "目押", "押跳秒", "唱名", "速压破甲")
# 只出现在括号备注里才算：轴图上写「黑骑（速压破甲）」时，那格要的是卡帧目押，
# 不是点黑骑的 UB。放宽到「押 / 破甲 / 速压」是因为备注写法很随意。
UB_FRAME_WORDS_IN_NOTE = ("押", "破甲", "速压", "唱名", "卡帧", "目押")

# 拆操作串用的分隔符：模型有时会把一格里的多条操作写成「A - B」
UB_OP_SEPARATORS = r"[\s\-–—、,，/]+"


def split_ub_ops(text):
    """按分隔符拆一格里的多条操作，但括号内部的不算分隔符。

    「克*2(38-37)」里的连字符必须整体保留：一旦拆成「克*2(38」和「37)」，
    哪一条都归一不了，整条轴会卡在报错上。
    """
    parts, buf, depth = [], [], 0
    for ch in str(text):
        if ch in "(（":
            depth += 1
        elif ch in ")）":
            depth = max(0, depth - 1)
        elif depth == 0 and re.fullmatch(UB_OP_SEPARATORS, ch):
            if buf:
                parts.append("".join(buf))
                buf = []
            continue
        buf.append(ch)
    if buf:
        parts.append("".join(buf))
    return [piece.strip() for piece in parts if piece.strip()]


# 可接受的图片扩展名（剪贴板与拖拽都按它过滤）
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")

AI_PROMPT = """你是《公主连结 Re:Dive》会战轴图的识别助手。用户给你一张轴图，你把它转成结构化 JSON。

【输出要求】
只输出一个 JSON 对象。不要输出任何解释文字，不要用 markdown 代码块包起来。

【第一步：判断轴的类型】
- 图上有「状态 / 开关」列（形如 xOOXX 的 5 位串，外加一个单独的 auto 开关列）→ type 填 "set"
- 操作列是「角色名 / XX AUTO / BOSS UB / 卡帧」这类流水账，没有开关列 → type 填 "ub"

【两种类型共用的 party 字段（最容易错，务必按这个来）】
party 是队伍 1→5 号位的角色名，必须按图左侧队伍头像行**从左到右**的顺序填：
- 最左边那个敌方 / BOSS 头像不算，从它右边第一个头像开始才是 1 号位
- 头像下面通常只有属性、等级，没有名字，要靠头像认角色
- 标题、文件名、备注里那串名字的顺序**经常和号位顺序不一样**，
  绝对不要直接拿标题里的顺序当 party
- 实在认不出某个头像是谁时，从标题里没被用到的名字里挑一个补上

【type = set 的输出格式】
{"type":"set","name":"轴名","party":["1号位","2号位","3号位","4号位","5号位"],
 "rows":[{"time":"124","trigger":null,"state":"xOOXX","auto":true,"delay":null}]}
- time：三位数字。图上写 1:11 就填 "111"，写 56 就填 "056"；「开局 / 初始状态」固定填 "124"
- trigger：照抄该行标注的触发角色的原名。
  只有这一格是空的、或写的是「普攻后 / 无 UB」这类没有角色名的，才填 null；
  写的是「BOSS」就照抄 "BOSS"
- state：5 位字符串，O 表示开、X 表示关，从左到右依次是 1→5 号位，必须恰好 5 位
- auto：图上单独标注的「开 / 关」，布尔值
- delay：只有图上明示了秒数才填数字，否则填 null

【type = ub 的输出格式】
{"type":"ub","name":"轴名","party":["1号位","2号位","3号位","4号位","5号位"],
 "rows":[{"time":"1:21","ops":["克(AUTO)","瓜智(115 AUTO)"]},{"ops":["克"]}]}
- time：**绝大多数行都不要写 time**，只在这两种行写：
    · 整条轴的第一行
    · 紧跟在「BOSS UB」那一行之后、第一个带操作的行
  写 time 会让脚本停下来死等倒计时读到那个秒数，写多了会卡死；
  其余行一律省略 time 字段（图上的秒数列是给人看的参考，不用逐行抄）
- ops：**把「操作」那一格的内容原样照抄下来，一个字都不要改、不要省、不要自己翻译**：
    · 括号要保留：看到「瓜智(48 AUTO)」就抄 "瓜智(48 AUTO)"，不要改写成 "瓜智AUTO"
    · 连点要保留：看到「克*2(38-37)」就抄 "克*2(38-37)"，不要拆成两条
    · 里面的数字要保留，即使看起来像伤害数字
    · 一格写成「火电 - 瓜智 - 克(56)」这种带「-」的，拆成三条："火电"、"瓜智"、"克(56)"
    · 「卡帧 / 目押 / 押跳秒 / 唱名 / 速压破甲」这些字眼也原样抄下来，不要换成别的写法
    · 「BOSS UB」这一格不产生操作 → ops 填 []
    · 只抄「操作」列；「伤害」「说明」「备注」「贴图区」列的文字一律不要抄进来
    · 图上几行就输出几行，不要跳过行，也不要把两行并成一行

【通用】
- 字段不确定时宁可不填，绝对不要编造
- 时间、角色名、开关状态必须与图上完全一致
- 不要自己把角色名换成数字，也不要自己把「卡帧 / 速压破甲」翻译成 k——
  这些和括号里的内容都由程序解析，你只管如实照抄"""


def image_from_clipboard():
    """从剪贴板取图，返回 (QImage, 文件路径或 None)；取不到返回 (None, None)。

    先试图片本身（截图工具、Win+Shift+S 都会以图片形式落进剪贴板），
    再试剪贴板里是不是「复制的图片文件」。
    """
    clipboard = QApplication.clipboard()
    if clipboard is None:
        return None, None
    mime = clipboard.mimeData()
    if mime is not None:
        try:
            if mime.hasImage():
                image = clipboard.image()
                if image is not None and not image.isNull():
                    return image, None
        except Exception:
            pass
        try:
            if mime.hasUrls():
                for url in mime.urls():
                    path = url.toLocalFile()
                    if path and Path(path).suffix.lower() in IMAGE_SUFFIXES:
                        image = QImage(path)
                        if not image.isNull():
                            return image, path
        except Exception:
            pass
    return None, None


def encode_image(image, max_side=2000):
    """QImage -> (PNG bytes, mime)。超过 max_side 先等比缩小，避免请求体过大。"""
    if image.width() > max_side or image.height() > max_side:
        image = image.scaled(max_side, max_side, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data()), "image/png"


def parse_ai_json(text):
    """从模型回复里抠出第一个完整的 JSON 对象。

    模型经常套一层 ```json 代码块，或者在 JSON 前后加一两句解释，
    所以不能直接 json.loads。
    """
    body = str(text or "").strip()
    body = re.sub(r"^```[a-zA-Z0-9_]*\s*", "", body)
    body = re.sub(r"\s*```\s*$", "", body)
    start = body.find("{")
    if start < 0:
        raise ValueError("模型没有返回 JSON 内容")
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(body)):
        ch = body[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(body[start:i + 1])
    raise ValueError("模型返回的 JSON 不完整")


class ImageDropLabel(QLabel):
    """图片区域：支持拖拽放入、Ctrl+V 粘贴、点击选择文件。"""

    imageDropped = pyqtSignal(QImage)

    PLACEHOLDER = ("把轴图拖到这里，或直接按 Ctrl+V 粘贴截图\n（也可以点下面的「选择图片」）")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(220)
        self.setWordWrap(True)
        self._source = None
        self._path = None
        self._show_placeholder()

    # ---------------- 对外接口 ----------------
    def sourceImage(self):
        return self._source

    def sourcePath(self):
        return self._path

    def setImage(self, image, path=None):
        """载入一张 QImage；返回是否成功。"""
        if image is None or image.isNull():
            return False
        self._source = image
        self._path = path
        self._refresh()
        self.imageDropped.emit(image)
        return True

    def clearImage(self):
        self._source = None
        self._path = None
        self.setPixmap(QPixmap())
        self._show_placeholder()

    # ---------------- 内部 ----------------
    def _show_placeholder(self):
        self.setPixmap(QPixmap())
        self.setText(self.PLACEHOLDER)
        self.setStyleSheet(
            "QLabel{border:2px dashed #a0a6ad;border-radius:6px;color:#8a9098;"
            "background:#fafbfc;padding:8px;}")

    def _refresh(self):
        if self._source is None:
            self._show_placeholder()
            return
        self.setText("")
        self.setStyleSheet("QLabel{border:2px solid #4a90d9;border-radius:6px;background:#ffffff;}")
        box_w = max(80, self.width() - 12)
        box_h = max(80, self.height() - 12)
        pixmap = QPixmap.fromImage(self._source).scaled(
            box_w, box_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.setPixmap(pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh()

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Paste):
            self.pasteFromClipboard()
            return
        super().keyPressEvent(event)

    def pasteFromClipboard(self):
        image, path = image_from_clipboard()
        if image is None:
            QMessageBox.warning(self, "提示",
                                "剪贴板里没有图片。\n请先用截图工具（Win+Shift+S / 微信截图）截取轴图，再按 Ctrl+V。")
            return False
        return self.setImage(image, path)

    def dragEnterEvent(self, event):
        mime = event.mimeData()
        if mime.hasImage() or mime.hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        mime = event.mimeData()
        if mime.hasUrls():
            for url in mime.urls():
                path = url.toLocalFile()
                if path and Path(path).suffix.lower() in IMAGE_SUFFIXES:
                    image = QImage(path)
                    if not image.isNull():
                        self.setImage(image, path)
                        event.acceptProposedAction()
                        return
        if mime.hasImage():
            image = QImage(mime.imageData())
            if not image.isNull():
                self.setImage(image)
                event.acceptProposedAction()


def is_deepseek_endpoint(base_url, model):
    """判断是不是 DeepSeek（官方域名或模型名里带 deepseek）。

    DeepSeek 的 chat 接口默认开着「思考模式」，而识别轴图是纯感知任务：
    实测 1920x547 的轴图，默认模式下推理 token 会把 max_tokens 整个吃光
    （finish_reason=length、reasoning_tokens=max_tokens），正文 content 为空，
    识别必然失败。所以要显式带 thinking=disabled 关掉它。
    这个字段别的厂商不认，只在 DeepSeek 上带，避免污染通用请求体。
    """
    return "deepseek" in f"{base_url} {model}".lower()


def request_ai_detection(base_url, model, api_key, image_bytes, mime):
    """调 OpenAI 兼容的对话接口识别轴图，返回解析好的识别结果 dict。

    抽成模块级函数是为了让界面线程和命令行接口走同一套请求逻辑
    （含 DeepSeek 关思考模式等修复），避免两边各自演化。
    """
    url = base_url.rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"
    b64 = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "model": model,
        "temperature": 0,
        "max_tokens": 8000,
        "messages": [
            {"role": "system", "content": AI_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": "识别这张轴图，按要求输出 JSON。"},
                {"type": "image_url",
                 "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ]},
        ],
    }
    if is_deepseek_endpoint(base_url, model):
        # 关掉思考模式，否则推理 token 会把 max_tokens 吃光、正文为空
        payload["thinking"] = {"type": "disabled"}
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    response = requests.post(url, json=payload, headers=headers, timeout=180)
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code}：{response.text[:400]}")
    data = response.json()
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = message.get("content")
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") for part in content if isinstance(part, dict))
    content = (content or "").strip()
    if not content:
        # 只拿到思考过程、没有正文，是最容易踩的一脚，报清楚原因
        usage = data.get("usage") or {}
        details = usage.get("completion_tokens_details") or {}
        raise RuntimeError(
            "模型只返回了思考过程、没有正文"
            f"（finish_reason={choice.get('finish_reason')}，"
            f"reasoning_tokens={details.get('reasoning_tokens')}，"
            f"max_tokens={payload['max_tokens']}）。"
            "把 max_tokens 调大或换用能关闭思考的模型再试。")
    return parse_ai_json(content)


class AIDetectThread(QThread):
    """后台调用 OpenAI 兼容的对话接口识别轴图，避免阻塞界面。"""

    succeeded = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, base_url, model, api_key, image_bytes, mime, parent=None):
        super().__init__(parent)
        self.base_url = base_url
        self.model = model
        self.api_key = api_key
        self.image_bytes = image_bytes
        self.mime = mime

    def run(self):
        try:
            self.succeeded.emit(request_ai_detection(
                self.base_url, self.model, self.api_key,
                self.image_bytes, self.mime))
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")



class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.is_setting_input = False
        self.is_text_mode = False  # 模式标志：False为表格，True为文本
        self.mode = "set"          # "set" / "ub" / "ai" 三种模式
        self.mode_actions = {}
        self.ai_last_result = None    # 最近一次识别结果（改队伍顺序时重新套用）
        self.ai_thread = None
        self._ai_party_syncing = False
        self.initUI()

    def initUI(self):
        self.setWindowTitle('轴输入窗口')
        self.setGeometry(100, 100, 1000, 600)

        # 添加菜单栏
        self.menu_bar = QMenuBar(self)

        # 添加模式切换菜单（三种模式互斥勾选）
        mode_menu = QMenu('模式切换', self)
        self.menu_bar.addMenu(mode_menu)
        self.mode_group = QActionGroup(self)
        self.mode_group.setExclusive(True)
        for label, mode_name in (('开关SET模式', 'set'),
                                 ('单次UB模式', 'ub'),
                                 ('AI识别模式', 'ai')):
            action = mode_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(mode_name == 'set')
            action.triggered.connect(
                lambda checked=False, m=mode_name: self._set_mode(m))
            self.mode_group.addAction(action)
            self.mode_actions[mode_name] = action

        # 添加脚本管理菜单
        script_menu = QMenu('脚本管理', self)
        self.menu_bar.addMenu(script_menu)
        
        manage_action = script_menu.addAction('管理脚本')
        manage_action.triggered.connect(self.show_script_manager)
        
        help_menu = QMenu('帮助', self)
        self.menu_bar.addMenu(help_menu)
        
        readme_action = help_menu.addAction('使用说明')
        readme_action.triggered.connect(self.open_readme)
        about_action = help_menu.addAction('关于')
        about_action.triggered.connect(self.show_about)

        # 添加清空内容菜单
        clear_menu = QMenu('清空内容', self)
        self.menu_bar.addMenu(clear_menu)
        
        clear_action = clear_menu.addAction('清空所有内容')
        clear_action.triggered.connect(self.clear_all_content)

        # 添加获取共享轴菜单
        share_menu = QMenu('获取在线内容', self)
        self.menu_bar.addMenu(share_menu)
        
        get_share_action = share_menu.addAction('获取在线轴')
        get_share_action.triggered.connect(self.get_shared_scripts)
        self.layout = QVBoxLayout()
        self.layout.setMenuBar(self.menu_bar)  # 将菜单栏添加到布局中
        speed_menu = QMenu('识别速度', self)
        self.menu_bar.addMenu(speed_menu)
        self.speed = 200  # 初始值为200

        fast_action = speed_menu.addAction('快速识别')
        fast_action.triggered.connect(lambda: self.set_speed(100))
        medium_action = speed_menu.addAction('中速识别')
        medium_action.triggered.connect(lambda: self.set_speed(200))
        slow_action = speed_menu.addAction('慢速识别')
        slow_action.triggered.connect(lambda: self.set_speed(300))

        ub_menu = self.menu_bar.addMenu("UB偏移")
        offset_action = ub_menu.addAction("偏移量设置")
        self.offsetX="00000"
        offset_action.triggered.connect(self.open_ub_offset_dialog)

        # 开关SET模式控件
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(['时间', '?号位UB后', '状态', '操作', '延时(秒)'])
        self.add_row()
        item = QTableWidgetItem("初始状态")
        self.table.setItem(0, 0, item)
        self.layout.addWidget(self.table)

        # 单次UB控件（初始隐藏）
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText('''在这里输入单次UB的文本内容，格式为：
按顺序填写ub角色,支持角色名或数字(角色位置顺序),
避免使用511等带数字名称和与指令字母冲突内容
支持指令(不要加号):
a+角色名---auto开
d+一位数---delay延时(秒)
s+三位数---等待游戏内倒计时至至该秒数
k---卡帧,卡帧结束请自行set后点击设定键''')
        self.text_edit.hide()
        self.layout.addWidget(self.text_edit)

        # 创建角色输入布局（仅单次UB模式使用，SET模式下整体隐藏）
        self.char_layout = QHBoxLayout()
        self.char_label = QLabel("使用角色：")
        self.char_input = QLineEdit()
        self.char_input.setPlaceholderText("必须按顺序填写角色名,与轴中名字必须一一对应,且用空格隔开")
        self.char_layout.addWidget(self.char_label)
        self.char_layout.addWidget(self.char_input)
        
        # 轴名输入布局
        self.input_layout = QHBoxLayout()
        self.label = QLabel("轴名：")
        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("前两位必须为boss编号,如E5,D4")
        self.input_layout.addWidget(self.label)
        self.input_layout.addWidget(self.input_box)
        
        # 添加到主布局
        self.layout.addLayout(self.char_layout)
        self.layout.addLayout(self.input_layout)

        # 添加余刀剩余时间标签和输入框
        self.remaining_time_label = QLabel("余刀剩余时间：")
        self.remaining_time_input = QLineEdit()
        self.remaining_time_input.setValidator(QIntValidator(21, 130))  # 限制输入范围为21-130
        self.remaining_time_input.setText("130") 
        self.remaining_time_input.setFixedWidth(50)  # 设置输入框的固定宽度
        self.input_layout.addWidget(self.remaining_time_label)
        self.input_layout.addWidget(self.remaining_time_input)

        self.output_button = QPushButton('生成脚本')
        self.output_button.clicked.connect(self.genbymanual)
        self.share_layout = QHBoxLayout()
        self.label2 = QLabel("分享码：")
        self.share_box = QLineEdit()
        self.share_button= QPushButton('一键分享')
        self.share_button.clicked.connect(self.show_popup)
        self.sharein_button= QPushButton('读取分享')
        self.sharein_button.clicked.connect(self.genbyshare)

        # 添加不生成脚本复选框
        self.no_script_checkbox = QCheckBox('不生成脚本')
        self.no_script_checkbox.setChecked(False)

        # 创建一个水平布局来放置生成脚本和一键分享按钮
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.output_button)
        button_layout.addWidget(self.share_button)
        self.layout.addLayout(button_layout)

        self.share_layout.addWidget(self.label2)
        self.share_layout.addWidget(self.share_box)
        self.share_layout.addWidget(self.sharein_button)
        self.share_layout.addWidget(self.no_script_checkbox)
        self.layout.addLayout(self.share_layout)

        # AI 识别面板（放在表格/文本区之后、角色输入之前）
        self._build_ai_panel()
        self.layout.insertWidget(2, self.ai_panel)

        self.setLayout(self.layout)
        self._set_mode('set')  # 初始为SET模式，并同步各模式控件的可见性

    # ============================================================ AI 识别模式
    def _build_ai_panel(self):
        self.ai_panel = QWidget()
        outer = QVBoxLayout(self.ai_panel)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        # 接口地址
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("接口地址："))
        self.ai_base_url = QLineEdit()
        self.ai_base_url.setPlaceholderText(
            "OpenAI 兼容接口，默认 https://api.deepseek.com")
        row1.addWidget(self.ai_base_url)
        outer.addLayout(row1)

        # 模型 + API Key
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("模型："))
        self.ai_model = QLineEdit()
        self.ai_model.setPlaceholderText(
            "需要支持图片输入，默认 deepseek-flash；也可填 gpt-4o / qwen-vl-max")
        row2.addWidget(self.ai_model)
        row2.addWidget(QLabel("API Key："))
        self.ai_api_key = QLineEdit()
        self.ai_api_key.setEchoMode(QLineEdit.Password)
        self.ai_api_key.setPlaceholderText("留空则不带鉴权头")
        row2.addWidget(self.ai_api_key)
        self.ai_key_toggle = QPushButton("显示")
        self.ai_key_toggle.setCheckable(True)
        self.ai_key_toggle.setFixedWidth(48)
        self.ai_key_toggle.toggled.connect(
            lambda on: self.ai_api_key.setEchoMode(
                QLineEdit.Normal if on else QLineEdit.Password))
        row2.addWidget(self.ai_key_toggle)
        outer.addLayout(row2)

        # 队伍号位
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("队伍号位顺序："))
        self.ai_party = QLineEdit()
        self.ai_party.setPlaceholderText(
            "识别后自动填入，按 1→5 号位、空格分隔。SET 模式的「时点」靠它推算，"
            "改了这里会自动重算")
        row3.addWidget(self.ai_party)
        outer.addLayout(row3)

        # 图片区
        self.ai_image = ImageDropLabel()
        self.ai_image.imageDropped.connect(self._on_ai_image_changed)
        outer.addWidget(self.ai_image)

        # 按钮行
        row4 = QHBoxLayout()
        self.ai_paste_btn = QPushButton("粘贴图片(Ctrl+V)")
        self.ai_paste_btn.clicked.connect(self._paste_image)
        self.ai_pick_btn = QPushButton("选择图片…")
        self.ai_pick_btn.clicked.connect(self._pick_image)
        self.ai_clear_btn = QPushButton("清空图片")
        self.ai_clear_btn.clicked.connect(self._clear_image)
        self.ai_detect_btn = QPushButton("识别并填充")
        self.ai_detect_btn.clicked.connect(self._start_ai_detect)
        self.ai_auto_generate = QCheckBox("识别后自动生成脚本")
        row4.addWidget(self.ai_paste_btn)
        row4.addWidget(self.ai_pick_btn)
        row4.addWidget(self.ai_clear_btn)
        row4.addWidget(self.ai_detect_btn)
        row4.addWidget(self.ai_auto_generate)
        outer.addLayout(row4)

        self.ai_status = QLabel("")
        self.ai_status.setWordWrap(True)
        outer.addWidget(self.ai_status)

        # ---- 配置读写：改完 600ms 落盘一次，避免每敲一个字都写文件 ----
        self._ai_save_timer = QTimer(self)
        self._ai_save_timer.setSingleShot(True)
        self._ai_save_timer.setInterval(600)
        self._ai_save_timer.timeout.connect(self._save_ai_config)

        self._ai_apply_timer = QTimer(self)
        self._ai_apply_timer.setSingleShot(True)
        self._ai_apply_timer.setInterval(400)
        self._ai_apply_timer.timeout.connect(self._reapply_ai_result)

        config = self._load_ai_config()
        self.ai_base_url.setText(config.get("base_url", ""))
        self.ai_model.setText(config.get("model", ""))
        self.ai_api_key.setText(config.get("api_key", ""))
        self.ai_auto_generate.setChecked(bool(config.get("auto_generate", True)))

        for widget in (self.ai_base_url, self.ai_model, self.ai_api_key):
            widget.textChanged.connect(self._schedule_ai_config_save)
        self.ai_auto_generate.toggled.connect(self._schedule_ai_config_save)
        self.ai_party.textChanged.connect(self._schedule_ai_reapply)

    def _load_ai_config(self):
        return load_ai_config()

    def _schedule_ai_config_save(self, *args):
        self._ai_save_timer.start()

    def _save_ai_config(self):
        config = {
            "base_url": self.ai_base_url.text().strip(),
            "model": self.ai_model.text().strip(),
            "api_key": self.ai_api_key.text().strip(),
            "auto_generate": self.ai_auto_generate.isChecked(),
        }
        try:
            AI_CONFIG_PATH.write_text(
                json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            print("保存 AI 配置失败:", exc)

    def _set_ai_status(self, text, error=False):
        self.ai_status.setText(text)
        self.ai_status.setStyleSheet(
            "color:#c0392b;" if error else "color:#2c7a3f;")

    def _on_ai_image_changed(self, image):
        self._set_ai_status(
            f"已载入图片 {image.width()}×{image.height()}，点「识别并填充」开始。")

    def _paste_image(self):
        image, path = image_from_clipboard()
        if image is None:
            self._set_ai_status("剪贴板里没有图片。", error=True)
            QMessageBox.warning(
                self, "提示",
                "剪贴板里没有图片。\n请先用截图工具（Win+Shift+S / 微信截图）截取轴图，再按 Ctrl+V。")
            return
        self.ai_image.setImage(image, path)

    def _pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择轴图", "",
            "图片 (*.png *.jpg *.jpeg *.webp *.bmp *.gif)")
        if not path:
            return
        image = QImage(path)
        if image.isNull():
            QMessageBox.warning(self, "提示", "这个文件读不出图片内容。")
            return
        self.ai_image.setImage(image, path)

    def _clear_image(self):
        self.ai_image.clearImage()
        self.ai_last_result = None
        self._set_ai_status("")

    def _start_ai_detect(self):
        if self.ai_thread is not None and self.ai_thread.isRunning():
            return
        base_url = self.ai_base_url.text().strip()
        model = self.ai_model.text().strip()
        if not base_url or not model:
            QMessageBox.warning(self, "提示", "请先填写接口地址和模型名称。")
            return
        image = self.ai_image.sourceImage()
        if image is None:
            QMessageBox.warning(self, "提示", "请先粘贴或选择一张轴图。")
            return

        image_bytes, mime = encode_image(image)
        self.ai_detect_btn.setEnabled(False)
        self.ai_detect_btn.setText("识别中…")
        self._set_ai_status(
            f"正在请求 {model}（图片 {len(image_bytes) // 1024} KB）…")

        self.ai_thread = AIDetectThread(
            base_url, model, self.ai_api_key.text().strip(),
            image_bytes, mime, self)
        self.ai_thread.succeeded.connect(self._on_ai_ok)
        self.ai_thread.failed.connect(self._on_ai_fail)
        self.ai_thread.finished.connect(self._on_ai_finished)
        self.ai_thread.start()

    def _on_ai_finished(self):
        self.ai_detect_btn.setEnabled(True)
        self.ai_detect_btn.setText("识别并填充")

    def _on_ai_ok(self, result):
        try:
            summary = self._apply_ai_result(
                result, regenerate=self.ai_auto_generate.isChecked())
        except Exception as exc:
            self._on_ai_fail(f"结果无法套用：{exc}")
            return
        kind = "开关SET" if str(result.get("type", "")).lower() == "set" else "单次UB"
        name = str(result.get("name") or "").strip() or "(未识别到轴名)"
        message = (f"识别完成：{kind} 轴「{name}」，{summary}。\n"
                   f"分享码已填入下方「分享码」框，可直接复制或点「一键分享」。")
        if kind == "开关SET":
            # 轴图上没有号位数字，时点只能靠队伍号位顺序推；这一步最容易错，
            # 所以明确提示用户核对一次（改上面那个框会自动重算）。
            message += ("\nSET 的「时点」是按上面的「队伍号位顺序」推算的，"
                        "这里最容易错，请和游戏内的站位核对一下；"
                        "不对就直接改那个输入框，分享码会自动重算。")
        self._set_ai_status(message)

    def _on_ai_fail(self, message):
        self._set_ai_status(f"识别失败：{message}", error=True)
        QMessageBox.warning(self, "AI 识别失败", message)

    def _schedule_ai_reapply(self, *args):
        if self._ai_party_syncing or self.ai_last_result is None:
            return
        self._ai_apply_timer.start()

    def _reapply_ai_result(self):
        if self.ai_last_result is None or self._ai_party_syncing:
            return
        try:
            # sync_party=False：这次就是要用「用户手改过的队伍顺序」重算，
            # 不能拿上次识别结果里的 party 又盖回去。
            summary = self._apply_ai_result(
                self.ai_last_result, regenerate=False, sync_party=False)
        except Exception as exc:
            self._set_ai_status(f"按新队伍顺序重算失败：{exc}", error=True)
            return
        self._set_ai_status(f"已按新的队伍号位顺序重算：{summary}。分享码已更新。")

    def _ai_party_list(self):
        return parse_namelist(self.ai_party.text())

    def _sync_party_field(self, names):
        """把识别到的队伍写进输入框；期间屏蔽重算，避免自己触发自己。"""
        names = [str(x).strip() for x in (names or []) if str(x).strip()]
        if not names:
            return
        if self.ai_party.text().strip() == " ".join(names):
            return
        self._ai_party_syncing = True
        self.ai_party.setText(" ".join(names))
        self._ai_party_syncing = False

    @staticmethod
    def _parse_state(state):
        """状态串 -> bool 列表。接受 o/O/1/开 与 x/X/0/关，允许 5 位或 6 位（含 auto）。"""
        if state is None:
            raise ValueError("识别结果里缺少状态串")
        text = re.sub(r"[\s\u3000]+", "", str(state))
        bits = []
        for ch in text:
            if ch in ("o", "O", "1", "开", "√", "是"):
                bits.append(True)
            elif ch in ("x", "X", "0", "关", "×"):
                bits.append(False)
            else:
                raise ValueError(f"状态串里出现无法识别的字符「{ch}」")
        if len(bits) not in (5, 6):
            raise ValueError(f"状态串应为 5 位（或 6 位含 auto），实际 {len(bits)} 位")
        return bits

    @staticmethod
    def _normalize_set_time(value, initial=False):
        """时间 -> 三位数字字符串。支持 "1:11"、"111"、"56"、"初始状态"。"""
        text = str(value if value is not None else "").strip()
        if text in ("", "初始状态", "开局") and initial:
            return "124"
        if ":" in text:
            minute, _, second = text.partition(":")
            if not minute.strip().isdigit() or not second.strip().isdigit():
                raise ValueError(f"时间「{value}」无法识别")
            text = f"{int(minute)}{int(second):02d}"
        if text.isdigit():
            if len(text) == 1:
                text = "00" + text
            elif len(text) == 2:
                text = "0" + text
        if len(text) != 3 or not text.isdigit():
            raise ValueError(f"时间「{value}」无法识别（应为 3 位数字或 M:SS）")
        return text

    @staticmethod
    def _normalize_ub_time(value):
        """倒计时 -> 'MSS' 三位数字，如 1:21 -> '121'。"""
        text = str(value if value is not None else "").strip().lstrip("sS")
        if ":" in text:
            minute, _, second = text.partition(":")
            return f"{int(minute)}{int(second):02d}"
        if text.isdigit():
            return text.zfill(3)
        raise ValueError(f"倒计时「{value}」无法识别（应为 M:SS）")

    @staticmethod
    def _normalize_ub_op(op, party):
        """轴图上的一个操作 -> 文本区能识别的写法。

        文本区沿用 process_text 的约定（角色名 / 角色名AUTO / k / d数字），
        所以这里只做「同义词归一」，不做角色名到数字的替换。
        """
        text = str(op if op is not None else "").strip()
        if not text or text in ("-", "—", "无", "空"):
            return ""
        # 模型直接给了指令串
        if text in ("k", "K"):
            return "k"
        # BOSS UB 这类不是操作。模型经常把 BOSS 行抄成 ops:["UB"] 或 "BOSS"，
        # 只在「一个汉字都没有」时才这样判定，免得把角色名当垃圾丢掉。
        if not re.search(r"[\u4e00-\u9fff]", text):
            letters = re.sub(r"[^A-Za-z]", "", text).lower()
            if letters in ("boss", "ub", "bossub", "ubboss"):
                return ""
        # 延时
        match = re.fullmatch(r"(?:延时|延迟|delay)\s*(\d+)", text, re.I)
        if match:
            return "d" + match.group(1)
        match = re.fullmatch(r"(\d+)\s*[秒sS]", text)
        if match:
            return "d" + match.group(1)

        # AUTO 可能写在括号里（轴图上有「瓜智(115 AUTO)」这种），
        # 所以要在删括号之前先在原文里找一次
        auto = "auto" in text.lower()
        note = " ".join(re.findall(r"[\(（]([^\)）]*)[\)）]", text))
        core = re.sub(r"[\(（][^\)）]*[\)）]", "", text).strip()
        core = re.sub(r"(?i)auto$", "", core).strip()

        # 卡帧类字眼。放在角色名判断之前，否则「黑骑（速压破甲）」会被当成点黑骑
        if (any(word in text for word in UB_FRAME_WORDS)
                or any(word in note for word in UB_FRAME_WORDS_IN_NOTE)):
            return "k"
        # 「克*2」这类连点写法
        match = re.fullmatch(r"(.+?)\s*[*×xX]\s*(\d+)", core)
        if match and match.group(1).strip() in party:
            name = match.group(1).strip()
            times = max(1, int(match.group(2)))
            return " ".join([name + ("AUTO" if auto else "")] * times)
        if core in party:
            return core + ("AUTO" if auto else "")
        if re.fullmatch(r"[0-9aAkKsSdD]+", core):
            return core
        raise ValueError(f"操作「{op}」不在队伍号位里：{party}")

    @staticmethod
    def _build_set_rows(rows_json, party):
        """SET：识别结果 -> set_input() 需要的 (rows, td)。

        纯函数（不碰控件），所以标成静态方法，命令行接口可以直接复用。
        """
        slot = {name: index + 1 for index, name in enumerate(party)}
        rows, td = [], {}
        for index, row in enumerate(rows_json):
            time = MainWindow._normalize_set_time(row.get("time"), initial=(index == 0))
            time_point = row.get("time_point")
            if time_point is None:
                trigger = str(row.get("trigger") or "").strip()
                lowered = trigger.lower()
                if row.get("stuck") or trigger in ("卡帧", "卡", "卡帧目押"):
                    time_point = 6
                # 「普攻后 / 无 UB / BOSS UB」这类都不是角色触发的行，时点记 0。
                # BOSS 用「包含」判断，免得「BOSS UB」「boss」等写法漏网。
                elif (trigger in ("", "-", "_", "/", "无", "普攻后")
                      or "boss" in lowered or trigger.startswith("普攻")):
                    time_point = 0
                elif trigger in slot:
                    time_point = slot[trigger]
                else:
                    raise ValueError(
                        f"第 {index + 1} 行的触发角色「{trigger}」不在队伍号位里：{party}")
            time_point = str(int(time_point))
            bits = MainWindow._parse_state(row.get("state"))
            if len(bits) == 5:
                bits.append(bool(row.get("auto")))
            rows.append((time, time_point, bits))
            delay = row.get("delay")
            if delay not in (None, "", 0, "0"):
                td[index] = float(delay)
        return rows, td

    @staticmethod
    def _build_ub_lines(rows_json, party):
        """单次UB：识别结果 -> 文本区要显示的若干行（纯函数，命令行也复用）。"""
        lines, unknown = [], []
        for row in rows_json:
            pieces = []
            if row.get("time") not in (None, ""):
                pieces.append("s" + MainWindow._normalize_ub_time(row.get("time")))
            ops = row.get("ops")
            if ops is None:
                ops = row.get("op") or []
            if isinstance(ops, str):
                ops = parse_namelist(ops)
            for op in ops:
                # 一格里的多条操作，模型可能写成「黑骑（速压破甲）- 星猫」，
                # 这里先按分隔符拆开，再逐条归一。括号里的「-」不能当分隔符，
                # 否则 克*2(38-37) 会被切成两条废串。
                for piece in split_ub_ops(op):
                    try:
                        converted = MainWindow._normalize_ub_op(piece, party)
                    except ValueError:
                        # 攒起来一起报，省得用户改一个又冒出下一个
                        unknown.append(piece)
                        continue
                    if converted:
                        pieces.append(converted)
            if pieces:
                lines.append(" ".join(pieces))
        if unknown:
            listed = "、".join(dict.fromkeys(unknown))
            raise ValueError(
                f"这些操作认不出来：{listed}。多半是队伍号位顺序不对，"
                "改上面的「队伍号位顺序」后会自动重算")
        if not lines:
            raise ValueError("识别结果里一条操作都没有")
        return lines

    def _apply_ai_result(self, result, regenerate=False, sync_party=True):
        """把识别结果填进界面并切到对应模式，返回一句摘要。"""
        rows_json = result.get("rows") or []
        if not rows_json:
            raise ValueError("识别结果里没有任何行")
        name = str(result.get("name") or "").strip()
        if sync_party:
            self._sync_party_field(result.get("party"))
        party = self._ai_party_list()
        self.ai_last_result = result

        if str(result.get("type", "")).lower() == "set":
            rows, td = self._build_set_rows(rows_json, party)
            self._set_mode("set")
            if name:
                self.input_box.setText(name)
            self.set_input(rows, td)
            code = sharecode.to_share(rows, td)
            self.share_box.setText(f"{name}:{code}" if name else code)
            if regenerate:
                self.usecontent(rows, td)
            return f"{len(rows)} 行"

        # 单次UB
        if len(party) != 5:
            raise ValueError(f"单次UB 需要 5 个角色名，本次识别到 {len(party)} 个")
        lines = self._build_ub_lines(rows_json, party)
        self._set_mode("ub")
        if name:
            self.input_box.setText(name)
        self.char_input.setText(" ".join(party))
        self.text_edit.setPlainText("\n".join(lines))
        instruction = self.process_text("\n".join(lines), party)
        self.share_box.setText(f"{name}#{instruction}#{' '.join(party)}")
        if regenerate:
            self.usecontent(None, {})
        return f"{len(lines)} 行 / 指令 {len(instruction)} 字符"

    def _set_mode(self, mode):
        """切换模式：mode 取 "set" / "ub" / "ai"。

        原先是表格 / 文本两态，靠 is_text_mode 布尔量表示；加入 AI 模式后
        统一走这里，并把 is_text_mode 作为「是否单次UB」的派生量同步维护，
        这样原有那些判断 is_text_mode 的代码路径不用改动。
        """
        if mode not in ("set", "ub", "ai"):
            mode = "set"
        if mode != "ub":
            self.char_input.clear()
        self.mode = mode
        self.is_text_mode = (mode == "ub")
        self.table.setVisible(mode == "set")
        self.text_edit.setVisible(mode == "ub")
        self.ai_panel.setVisible(mode == "ai")
        self.char_label.setVisible(mode == "ub")
        self.char_input.setVisible(mode == "ub")
        for name, action in self.mode_actions.items():
            action.setChecked(name == mode)

    def keyPressEvent(self, event):
        """AI 模式下按 Ctrl+V 直接粘贴剪贴板里的图。

        放在窗口级是为了「焦点不在图片区时也能粘贴」；焦点在输入框里时
        QLineEdit 会自己消费掉 Ctrl+V，不会走到这里。
        """
        if self.mode == "ai" and event.matches(QKeySequence.Paste):
            self._paste_image()
            return
        super().keyPressEvent(event)

    def sender_row(self, sender_button):
        """由按钮反查它所在的行号，无法确定时返回 -1。

        原先是 indexAt(sender.parent().pos()).row()，有两个隐患：
        1. indexAt 要求 x/y 同时命中某个单元格，列宽被拖动或出现水平滚动时
           会返回 -1，且它有时钳位到第 0 行而不是失败，属于静默算错；
        2. sender.parent() 假定按钮之上只有一层容器，操作中途多包一层 QWidget
           就拿不到 viewport 坐标（实测第 4 行会被算成第 0 行）。

        改成先把按钮原点映射到 viewport 再取纵坐标：映射会逐级穿过所有父容器，
        不关心嵌套了几层；rowAt 只看 y，不再受列宽与水平滚动影响。
        """
        if sender_button is None:
            return -1
        viewport = self.table.viewport()
        if not viewport.isAncestorOf(sender_button):
            return -1
        return self.table.rowAt(sender_button.mapTo(viewport, QPoint(0, 0)).y())

    def add_row(self, button_row_index=None):
    # 如果没有指定行，从按钮信号中获取行

        sender_button = self.sender()  # 获取信号的发出者
        if self.is_setting_input:
            button_row_index = self.table.rowCount() - 1
        elif sender_button:
            button_row_index = self.sender_row(sender_button)
        else:
            button_row_index = -1  # 没有来源时统一走下面的兜底
        if button_row_index < 0:
            # 行号算不出来就追加到末尾，而不是退化成 insertRow(0)
            button_row_index = self.table.rowCount() - 1
        self.table.insertRow(button_row_index + 1)

        # 时间列
        time_input = QTableWidgetItem()
        time_input.setData(Qt.EditRole, '001')
        self.table.setItem(button_row_index + 1, 0, time_input)

        # 时点列
        time_point_combo = QComboBox()
        for i in range(0, 7):
            display_text = "卡帧" if i == 6 else str(i)
            time_point_combo.addItem(display_text)
        self.table.setCellWidget(button_row_index + 1, 1, time_point_combo)

        # 延时列
        timed_input = QTableWidgetItem()
        timed_input.setData(Qt.EditRole, 0.0)
        self.table.setItem(button_row_index + 1, 4, timed_input)

        # 状态列
        status_layout = QWidget()
        status_layout_layout = QHBoxLayout(status_layout)
        status_layout_layout.setContentsMargins(0, 0, 0, 0)
        status_layout_layout.setSpacing(0)
        status_checkboxes = []
        for i in range(1, 6):
            checkbox = QCheckBox(str(i) + "    ")
            status_layout_layout.addWidget(checkbox)
            status_checkboxes.append(checkbox)
        checkbox = QCheckBox('A')
        status_layout_layout.addWidget(checkbox)
        status_checkboxes.append(checkbox)
        self.table.setCellWidget(button_row_index + 1, 2, status_layout)

        # 复制被点击行的状态设定
        if button_row_index >= 0:
            previous_row_status_layout = self.table.cellWidget(button_row_index, 2)
            if previous_row_status_layout is not None:
                previous_row_status_layout_layout = previous_row_status_layout.layout()
                for i in range(previous_row_status_layout_layout.count()):
                    previous_checkbox = previous_row_status_layout_layout.itemAt(i).widget()
                    current_checkbox = status_checkboxes[i]
                    current_checkbox.setChecked(previous_checkbox.isChecked())

        # 操作列
        operation_layout = QWidget()
        operation_layout_layout = QHBoxLayout(operation_layout)
        operation_layout_layout.setContentsMargins(0, 0, 0, 0)
        operation_layout_layout.setSpacing(0)

        add_button = QPushButton('添加')
        add_button.clicked.connect(self.add_row)  # 无需传递索引，动态获取
        operation_layout_layout.addWidget(add_button)

        delete_button = QPushButton('删除')
        delete_button.clicked.connect(self.delete_row)  # 无需传递索引，动态获取
        operation_layout_layout.addWidget(delete_button)

        self.table.setCellWidget(button_row_index + 1, 3, operation_layout)
        self.table.setColumnWidth(2, 300)

    def delete_row(self):
        # sender_row 取不到行时返回 -1，下面的判断会让它安静地什么都不做，
        # 不会误删第 0 行。
        button_row_index = self.sender_row(self.sender())
        if button_row_index > 0:  # 确保第一行不可删除
            self.table.removeRow(button_row_index)
    def open_ub_offset_dialog(self):
        from PyQt5.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout,
            QLabel, QSlider, QPushButton
        )
        from PyQt5.QtCore import Qt

        dialog = QDialog(self)
        dialog.setWindowTitle("UB 偏移量设置")
        dialog.setModal(True)

        main_layout = QVBoxLayout(dialog)
        offset_str = getattr(self, "offsetX", "00000")
        values = []

        if len(offset_str) == 5 and offset_str.isdigit():
            for ch in offset_str:
                v = int(ch)
                if v >= 6:
                    v -= 10
                values.append(v)
        else:
            values = [0] * 5
        sliders = []

        # 5 个位置
        for i in range(5):
            row = QHBoxLayout()

            label = QLabel(f"{i+1}号位")
            label.setFixedWidth(40)

            slider = QSlider(Qt.Horizontal)
            slider.setRange(-4, 5)
            slider.setValue(values[i])
            slider.setTickPosition(QSlider.TicksBelow)
            slider.setTickInterval(1)

            value_label = QLabel(str(values[i]))
            value_label.setFixedWidth(20)

            slider.valueChanged.connect(
                lambda v, lab=value_label: lab.setText(str(v))
            )

            sliders.append(slider)

            row.addWidget(label)
            row.addWidget(slider)
            row.addWidget(value_label)

            main_layout.addLayout(row)

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        ok_btn = QPushButton("确定")
        cancel_btn = QPushButton("取消")

        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)

        main_layout.addLayout(btn_layout)

        # ===== 确定按钮逻辑 =====
        def on_ok():
            result = []
            for s in sliders:
                v = s.value()
                if v < 0:
                    v += 10     # 负数 +10
                result.append(str(v))

            self.offsetX = "".join(result)
            dialog.accept()

        ok_btn.clicked.connect(on_ok)
        cancel_btn.clicked.connect(dialog.reject)

        dialog.exec_()

    def output_content(self):
        if self.is_text_mode:
            text = self.text_edit.toPlainText()
            namelist = self.char_input.text()
            if not namelist.strip():
                QMessageBox.warning(self, "警告", "请填写角色名或昵称")
                return
            namelist = parse_namelist(namelist)
            if len(namelist) !=5:
                QMessageBox.warning(self, "警告", "角色名数量不正确，请确保填写5个角色名")
                return
            text = self.process_text(text, namelist)
            return text,namelist
        else:
            content = []
            td = {}
            
            # 读取输入框的值并计算差值
            remaining_time = int(self.remaining_time_input.text())
            time_difference = 130 - remaining_time
            if time_difference>30:
                time_difference=time_difference-40

            for row in range(self.table.rowCount()):
                time_item = self.table.item(row, 0)
                time = time_item.text().replace("初始状态", "124")
                
                # 将时间值转换为秒数
                time_value = int(time)
                if 1 <= time_value <= 59:
                    time_in_seconds = time_value
                elif 100 <= time_value <= 130:
                    time_in_seconds = (time_value - 100) + 60
                
                # 减去差值
                adjusted_time_in_seconds = time_in_seconds - time_difference
                
                # 如果调整后的时间小于1秒，则跳过该行
                if adjusted_time_in_seconds < 1:
                    continue
                
                # 将秒数转换回时间格式
                if adjusted_time_in_seconds <= 59:
                    adjusted_time = f"{adjusted_time_in_seconds:03}"
                else:
                    adjusted_time = str(adjusted_time_in_seconds + 40)
                time_point = self.table.cellWidget(row, 1).currentText()
                if time_point == "卡帧":
                    time_point = '6'
                value = float(self.table.item(row, 4).text())
                if value != 0:
                    td[row] = value  # 行号从1开始，值为非零的内容
                status = []
                status_layout = self.table.cellWidget(row, 2)
                for checkbox in status_layout.findChildren(QCheckBox):
                    status.append(checkbox.isChecked())
                content.append((adjusted_time, time_point, status))
            
            return content, td
    
    def usecontent(self,content,td={}):
        if self.is_text_mode:
            stepname = self.input_box.text()
            # output_content() 返回 (处理后的指令串, 5个角色名列表)
            stepfile, namelist = self.output_content()
            if int(self.offsetX):
                stepname=f"{self.offsetX}{stepname}"
            # 分享码第三段存空格分隔的原始角色名串，供 # 格式解析
            self.autosave(f"{stepname}#{stepfile}#{' '.join(namelist)}")
            # 生成脚本要用列表，传字符串会让 namelist[n-1] 退化成单个字符
            pipeline.generate_single_ub_pipeline(stepname, stepfile=stepfile, namelist=namelist, speed=self.speed)
            msg = QMessageBox()
            msg.setText('已生成单次UB脚本')
            msg.setIcon(QMessageBox.Information)
            msg.exec_()
            return
        
        output_text = build_set_steps(content, td)
        input_text = self.input_box.text()
        stepname=input_text if input_text.strip() else f"{random.randint(100,999)}"
        if int(self.offsetX):
            stepname=f"{self.offsetX}{stepname}"
        code=sharecode.to_share(content,td)
        self.autosave(f"{stepname}:{code}")
        pipeline.generate_set_pipeline(stepname=stepname, stepfile=output_text)
        msg = QMessageBox()
        msg.setText(f'已生成脚本 "{stepname}"')
        msg.setIcon(QMessageBox.Information)
        msg.exec_()
    def genbymanual(self):
        try:

            c,t=self.output_content()
            self.usecontent(c,t)



        except Exception as e:
             msg = QMessageBox()
             msg.setText(f'发生错误{e}')
             msg.setIcon(QMessageBox.Information)
             msg.exec_()
    def set_input(self, content, td):
        self.is_setting_input = True
        self.table.setRowCount(0)  # Clear existing rows
        for index, (time, time_point, status) in enumerate(content):
            self.add_row()  # Add a new row
            self.table.item(index, 0).setText(time)  # Set time
            if time_point == '6':
                time_point = "卡帧"
            self.table.cellWidget(index, 1).setCurrentText(time_point)  # Set time point
            timed_input = self.table.item(index, 4)
            timed_input.setText(str(td.get(index, 0.0)))  # Set delay, default to 0.0 if not in td
            # Set status checkboxes
            status_layout = self.table.cellWidget(index, 2)
            for i, checkbox in enumerate(status_layout.findChildren(QCheckBox)):
                checkbox.setChecked(status[i])  # Set checkbox state
        self.is_setting_input = False
    def show_popup(self):
        if self.is_text_mode:
            # 单次UB分享逻辑，留空待补充
            text = self.text_edit.toPlainText()
            name1 = self.input_box.text() if self.input_box.text().strip() else f"{random.randint(100,999)}"
            content, namelist = self.output_content()
            if int(self.offsetX):
                name1=f"{self.offsetX}{name1}"
            dialog = QDialog(self)
            dialog.setWindowTitle('分享码')
            layout = QVBoxLayout()
            text_edit = QTextEdit(dialog)
            text_edit.setReadOnly(True)
            text_edit.setText(f"{name1}#{content}#{' '.join(namelist)}")
            layout.addWidget(text_edit)
            dialog.setLayout(layout)
            dialog.exec_()
        else:
            c,t=self.output_content()
            code=sharecode.to_share(c,t)
            dialog = QDialog(self)
            dialog.setWindowTitle('分享码')
            layout = QVBoxLayout()
            text_edit = QTextEdit(dialog)
            text_edit.setReadOnly(True)
            input_text = self.input_box.text()
            stepname = input_text if input_text.strip() else f"{random.randint(100,999)}"
            if int(self.offsetX):
                stepname=f"{self.offsetX}{stepname}"
            text_edit.setText(f"{stepname}:{code}")
            layout.addWidget(text_edit)
            url_label = QLabel('共享网址：<a href="https://docs.qq.com/sheet/DU2NHdnlNalFqdVZz">https://docs.qq.com/sheet/DU2NHdnlNalFqdVZz</a>')
            url_label.setOpenExternalLinks(True)
            url_label.setTextFormat(Qt.RichText)
            layout.addWidget(url_label)
            dialog.setLayout(layout)
            dialog.exec_()

    def genbyshare(self):
        a = self.share_box.text()
        try:
            if '#' in a:
                # 自动切换到单次UB
                self._set_mode("ub")
                # 解析单次UB分享码
                stepname, content, td = a.split('#')
                if len(stepname) >= 5 and stepname[:5].isdigit():
                    self.offsetX = stepname[:5]
                    stepname = stepname[5:]
                self.text_edit.setPlainText(content)
                self.input_box.setText(stepname)
                self.char_input.setText(td)
                namelist = parse_namelist(td)
                if len(namelist) != 5:
                    raise ValueError(f"角色名数量应为5个，实际为{len(namelist)}个")
                pipeline.generate_single_ub_pipeline(stepname, stepfile=content, namelist=namelist)
                QMessageBox.information(self, "提示", f"已生成")
                return
            else:
                # 自动切换到开关SET模式
                # 必须直接指定目标模式：从 AI 模式进来时 is_text_mode 是 False，
                # 靠它判断「要不要切」会以为已经在 SET 模式，结果表格填好了界面还停在 AI 面板
                self._set_mode("set")
                # ...existing code...
                if ":" in a:
                    parts = a.split(":")
                    # 分享码永远在最后一段，兼容历史格式 "轴名:角色:码" / "轴名::码"
                    c, t = sharecode.from_share(parts[-1])
                    stepname = parts[0]
                    if len(stepname) >= 5 and stepname[:5].isdigit():
                        self.offsetX = stepname[:5]
                        stepname = stepname[5:]
                    self.input_box.setText(stepname)
                    self.set_input(c, t)
                else:
                    c, t = sharecode.from_share(a)
                    self.set_input(c, t)
                self.usecontent(c, t)
                if self.no_script_checkbox.isChecked():
                    stepname = self.input_box.text() if self.input_box.text().strip() else f"{random.randint(100,999)}"
                    pipeline_path = Path('resource/pipeline') / f'{stepname}.json'
                    if pipeline_path.exists():
                        pipeline_path.unlink()
                    try:
                        with open('interface.json', 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        # 检查是否有同名 task
                        if any(task.get('name') == stepname for task in data.get('task', [])):
                            # 已有同名，跳过写入
                            pass
                        else:
                            data['task'] = [task for task in data['task'] if task.get('name') != stepname]
                            with open('interface.json', 'w', encoding='utf-8') as f:
                                json.dump(data, f, indent=4, ensure_ascii=False)
                    except:
                        pass
        except Exception as e:
            msg = QMessageBox()
            msg.setText(f'分享码有误或使用方法错误{e}')
            msg.setIcon(QMessageBox.Information)
            msg.exec_()
    def autosave(self, content):
        # 使用 'a' 模式打开文件，追加写入
        with open("自动保存的分享码.txt", 'a', encoding='utf-8') as file:
            # 写入字符串到文件尾，并换行
            file.write(content + '\n')

    
    def show_about(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('关于')
        dialog.setFixedSize(400, 200)  # 设置固定窗口大小
        layout = QVBoxLayout()
        
        # 使用QTextEdit替代QLabel以支持文本复制
        content = QTextEdit()
        content.setReadOnly(True)  # 设置只读
        content.setHtml(
            f'<div style="text-align: center;">'
            f'<h2>PCR会战SET轴脚本生成工具</h2>'
            f'<p>版本号: {get_version()}</p>'
            f'<p>分享码: <a href="https://docs.qq.com/sheet/DU2NHdnlNalFqdVZz">https://docs.qq.com/sheet/DU2NHdnlNalFqdVZz</a></p>'
            f'<p>Github: <a href="https://github.com/yinju86/MaaPcrclanbattle">https://github.com/yinju86/MaaPcrclanbattle</a></p>'
            f'<p>QQ群: 532774716</p>'
            f'</div>'
        )
        content.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                border: none;
            }
            QScrollBar {
                width: 0px;
                height: 0px;
            }
        """)  # 设置透明背景并隐藏滚动条
        content.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # 禁用垂直滚动条
        content.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # 禁用水平滚动条
        layout.addWidget(content)
        
        # 添加确定按钮并居中
        button_layout = QHBoxLayout()
        ok_button = QPushButton("确定")
        ok_button.setFixedWidth(100)  # 设置按钮宽度
        ok_button.clicked.connect(dialog.accept)
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        dialog.exec_()

    def open_readme(self):
        try:
            readme_path = Path(__file__).parent / "README.md"
            if (readme_path.exists()):
                webbrowser.open(str(readme_path))
            else:
                msg = QMessageBox()
                msg.setText('未找到README文件')
                msg.setIcon(QMessageBox.Warning)
                msg.exec_()
        except Exception as e:
            msg = QMessageBox()
            msg.setText(f'打开README时发生错误：{str(e)}')
            msg.setIcon(QMessageBox.Warning)
            msg.exec_()

    def show_script_manager(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('脚本管理')
        dialog.setFixedSize(400, 500)
        layout = QVBoxLayout()
        
        # 创建脚本列表
        script_list = QTableWidget()
        script_list.setColumnCount(2)
        script_list.setHorizontalHeaderLabels(['脚本名称', '操作'])
        script_list.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(script_list)
        
        try:
            # 读取 interface.json
            with open('interface.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                tasks = data.get('task', [])
                
                script_list.setRowCount(len(tasks))
                for row, task in enumerate(tasks):
                    name = task.get('name', '')
                    script_list.setItem(row, 0, QTableWidgetItem(name))
                    
                    # 添加删除按钮
                    delete_btn = QPushButton('删除')
                    delete_btn.clicked.connect(lambda checked, n=name: self.delete_script(n, script_list))
                    script_list.setCellWidget(row, 1, delete_btn)
        except Exception as e:
            QMessageBox.warning(dialog, '错误', f'读取脚本列表失败：{str(e)}')
        
        dialog.setLayout(layout)
        dialog.exec_()

    def delete_script(self, script_name, script_list):
        try:
            # 删除 pipeline 文件
            pipeline_path = Path('resource/pipeline') / f'{script_name}.json'
            if pipeline_path.exists():
                pipeline_path.unlink()
            
            # 更新 interface.json
            with open('interface.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 过滤掉要删除的脚本
            data['task'] = [task for task in data['task'] if task.get('name') != script_name]
            
            with open('interface.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            
            # 刷新列表
            for row in range(script_list.rowCount()):
                if script_list.item(row, 0).text() == script_name:
                    script_list.removeRow(row)
                    break
        except Exception as e:
            QMessageBox.warning(self, '错误', f'删除脚本失败：{str(e)}')

    def clear_all_content(self):
        # 弹出确认对话框
        reply = QMessageBox.question(self, '确认', 
                                   '是否确定清空所有内容?',
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            # 清空表格
            self.table.setRowCount(0)
            self.add_row()  # 添加初始行
            item = QTableWidgetItem("初始状态")
            self.table.setItem(0, 0, item)
            
            # 清空角色输入
            self.char_input.clear()
            self.text_edit.clear()  # 清空文本编辑器
            # 清空轴名输入
            self.input_box.clear()
            
            # 重置余刀剩余时间
            self.remaining_time_input.setText("130")
            
            # 清空分享码
            self.share_box.clear()

            # 清空 AI 识别区（图片与上次识别结果）
            self.ai_image.clearImage()
            self.ai_party.clear()
            self.ai_last_result = None
            self._set_ai_status("")

    @staticmethod
    def process_text(text, namelist):
        # 1. 替换角色名为数字
        for idx, name in enumerate(namelist, 1):
            text = text.replace(name, str(idx))
        # 2. 替换正则 (\d)\s？–?\(？auto\) 为 a$1
        # 支持多种括号和空格
        text = re.sub(r'(\d)\s*[-–－]?\s*[\(\（]?[aA][uU][tT][oO][\)\）]?', r'a\1', text)
        # 3. 删除所有括号及括号内内容
        text = re.sub(r'[\(\（][^\)\）]*[\)\）]', '', text)
        # 4. 删除所有空格和换行
        text = re.sub(r'\s+', '', text)
        text = re.sub(r'\n', '', text)
        text = re.sub(r'[、\-–－]', '', text)
        return text

    def get_shared_scripts(self):
        try:
            # 发送请求获取共享轴数据
            url = "https://gist.githubusercontent.com/yinju86/c9b79ca9910bb8f853c6f0addc94f9a6/raw/sharecode.txt"
            response = requests.get(url, timeout=10)
            response.encoding = 'utf-8'
            
            if response.status_code != 200:
                raise Exception("网络请求失败")

            # 获取现有脚本名称列表
            existing_scripts = set()
            try:
                with open('interface.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for task in data.get('task', []):
                        existing_scripts.add(task.get('name', ''))
            except:
                existing_scripts = set()

            # 处理每一行共享码
            success_count = 0
            skip_count = 0
            for line in response.text.strip().split('\n'):
                if not line.strip():
                    continue
                    
                try:
                    # 支持两种分享格式：包含 '#' 的单次UB分享码，以及以 ':' 分隔的 SET 分享码
                    if '#' in line:
                        # 单次UB 分享码，格式与 genbyshare() 中处理逻辑一致：stepname#content#namelist
                        try:
                            stepname, content, td = line.split('#')
                        except ValueError:
                            # 格式不对，跳过
                            print(f"单次UB分享码格式错误: {line}")
                            continue

                        # 处理offsetX标识后再进行对比
                        compare_name = stepname
                        if len(stepname) >= 5 and stepname[:5].isdigit():
                            compare_name = stepname[5:]
                        
                        # 如果已有同名脚本则跳过
                        if compare_name in existing_scripts:
                            skip_count += 1
                            continue

                        namelist = parse_namelist(td)
                        if len(namelist) != 5:
                            print(f"单次UB分享码角色名数量错误（应为5个）: {line}")
                            continue
                        try:
                            # 生成单次UB脚本
                            pipeline.generate_single_ub_pipeline(stepname, stepfile=content, namelist=namelist)
                            success_count += 1
                            existing_scripts.add(compare_name)
                        except Exception as e:
                            print(f"生成单次UB脚本失败: {line}, 错误: {e}")
                            continue
                    else:
                        parts = line.split(':')
                        if len(parts) < 2:
                            continue

                        script_name = parts[0]

                        # 处理offsetX标识后再进行对比
                        compare_name = script_name
                        if len(script_name) >= 5 and script_name[:5].isdigit():
                            compare_name = script_name[5:]

                        # 检查是否存在同名脚本
                        if compare_name in existing_scripts:
                            skip_count += 1
                            continue

                        # 根据共享码生成 SET 脚本（码永远在最后一段，兼容历史格式）
                        try:
                            c, t = sharecode.from_share(parts[-1])
                        except Exception as e:
                            print(f"解析共享码失败: {line}, 错误: {e}")
                            continue

                        # 生成 SET 脚本
                        stepname = script_name
                        try:
                            pipeline.generate_set_pipeline(stepname=stepname, stepfile=self.format_content(c, t))
                            success_count += 1
                            existing_scripts.add(compare_name)
                        except Exception as e:
                            print(f"生成SET脚本失败: {line}, 错误: {e}")
                            continue
                    
                except Exception as e:
                    print(f"处理共享码失败: {line}, 错误: {str(e)}")
                    continue

            # 仅当成功生成脚本数大于0时才弹窗
            if success_count > 0:
                msg = QMessageBox()
                msg.setWindowTitle('处理结果')
                msg.setText(f'成功生成 {success_count} 个脚本\n跳过 {skip_count} 个已存在的脚本')
                msg.setIcon(QMessageBox.Information)
                msg.exec_()
            
        except Exception as e:
            msg = QMessageBox()
            msg.setText(f'获取共享轴失败：{str(e)}')
            msg.setIcon(QMessageBox.Warning)
            msg.exec_()
    def set_speed(self, value):
        self.speed = value
        QMessageBox.information(self, "识别速度", f"已设置为{'快速' if value==100 else '中速' if value==200 else '慢速'}识别（{value}）\n计算机性能差的推荐使用快速识别")
    def format_content(self, content, td):
        return build_set_steps(content, td)
if __name__ == '__main__':
    # 带命令行参数时走无界面接口（cli.py），方便脚本/其它程序调用 exe；
    # 不带参数才是打开图形界面。判断放在创建 QApplication 之前，
    # 这样命令行调用完全不碰 Qt。
    if cli.is_cli_invocation(sys.argv[1:]):
        sys.exit(cli.main(sys.argv[1:]))

    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())