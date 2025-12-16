import sys
from PyQt5.QtWidgets import QLineEdit,QApplication, QWidget,QLabel, QVBoxLayout, QTableWidget, QTableWidgetItem, QComboBox, QPushButton, QCheckBox, QMessageBox,QHBoxLayout,QDialog,QTextEdit, QMenuBar, QMenu
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIntValidator
import random
import scriptgeneration
import sharecode
import json
from pathlib import Path
import webbrowser
import ota
import nameget
from PyQt5.QtCore import QThread, pyqtSignal
import requests  # 添加到文件顶部的imports中
import specialgenerat
import re
def get_version():
    try:
        install_path = Path(__file__).parent / "install"
        with open(install_path / "interface.json", "r", encoding="utf-8") as f:
            interface = json.load(f)
        return interface.get("version", "unknown")
    except:
        return "unknown"


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.is_setting_input = False
        self.is_text_mode = False  # 模式标志：False为表格，True为文本
        self.initUI()

    def initUI(self):
        self.setWindowTitle('轴输入窗口')
        self.setGeometry(100, 100, 1000, 600)

        # 添加菜单栏
        self.menu_bar = QMenuBar(self)

        # 添加模式切换菜单
        mode_menu = QMenu('模式切换', self)
        self.menu_bar.addMenu(mode_menu)
        self.switch_mode_action = mode_menu.addAction('切换为单次UB/开关SET模式')
        self.switch_mode_action.triggered.connect(self.switch_mode)

        # 添加脚本管理菜单
        script_menu = QMenu('脚本管理', self)
        self.menu_bar.addMenu(script_menu)
        
        manage_action = script_menu.addAction('管理脚本')
        manage_action.triggered.connect(self.show_script_manager)
        
        # 添加更新菜单
        #update_menu = QMenu('更新(不使用自动选人无需更新)', self)
        #self.menu_bar.addMenu(update_menu)
        
        
        
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
        update_action = share_menu.addAction('更新角色列表')
        update_action.triggered.connect(self.update_character_list)
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

        # 创建角色输入布局
        self.char_layout = QHBoxLayout()
        self.char_label = QLabel("使用角色：")
        self.char_input = QLineEdit()
        self.char_input.setPlaceholderText("无需自动选人可不填写,默认借第一位,可使用昵称")
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
        self.setLayout(self.layout)

    def switch_mode(self):
        if not self.is_text_mode:
            self.table.hide()
            self.text_edit.show()
            self.char_input.clear()
            self.char_input.setPlaceholderText("必须按顺序填写角色名,与轴中名字必须一一对应,且用空格隔开")
            self.is_text_mode = True
        else:
            self.text_edit.hide()
            self.table.show()
            self.char_input.clear()
            self.char_input.setPlaceholderText("无需自动选人可不填写,默认借第一位,可使用昵称")
            self.is_text_mode = False
            
    def add_row(self, button_row_index=None):
    # 如果没有指定行，从按钮信号中获取行
        
        sender_button = self.sender()  # 获取信号的发出者
        if self.is_setting_input:
            button_row_index = self.table.rowCount() - 1
        elif sender_button:
            button_row_index = self.table.indexAt(sender_button.parent().pos()).row()
            print(button_row_index,"s")
        else:
            button_row_index = self.table.rowCount() - 1  # 默认最后一行
            print(button_row_index)
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
        sender_button = self.sender()  # 获取信号的发出者
        if sender_button:
            button_row_index = self.table.indexAt(sender_button.parent().pos()).row()
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
            slider.setValue(0)   # 初始为 0
            slider.setTickPosition(QSlider.TicksBelow)
            slider.setTickInterval(1)

            value_label = QLabel("0")
            value_label.setFixedWidth(20)
            value_label.setText(str(values[i]))
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
            namelist=self.char_input.text()
            if not namelist.strip():
                QMessageBox.warning(self, "警告", "请填写角色名或昵称")
                return
            namelist = namelist.split(' ')
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
            aa,bb=self.output_content()
            bb=self.char_input.text()
            self.autosave(f"{stepname}#{aa}#{bb}")
            # 生成脚本
            specialgenerat.generation(stepname, stepfile=content, namelist=td, speed=self.speed)
            msg = QMessageBox()
            msg.setText('已生成单次UB脚本')
            msg.setIcon(QMessageBox.Information)
            msg.exec_()
            return
        
        output_text = []
        for i, (t, tp, s) in enumerate(content):
            if i == 0 :
                output_text.append((f"{int(t[:-2])}:{t[-2:]}", tp, s,td.get(i,0.015)))
            else:
                prev_status = content[i-1][2]
                status_diff =  [x != y for x, y in zip(s, prev_status)]
                output_text.append((f"{int(t[:-2])}:{t[-2:]}", tp, status_diff,td.get(i,0.015)))
        input_text = self.input_box.text()
        char=self.char_input.text()
        if char and input_text:
            boss=int(input_text[1])
            normalizename=nameget.rewrite(input_text,char,boss)
            #弹窗展示该参数
            msg1 = QMessageBox()
            msg1.setText(f'确认角色:'+normalizename)
            msg1.setIcon(QMessageBox.Information)
            msg1.exec_()
        stepname=input_text if input_text.strip() else f"{random.randint(100,999)}"
        if int(self.offsetX):
            stepname=f"{self.offsetX}{stepname}"
        code=sharecode.to_share(content,td)
        self.autosave(f"{stepname}:{char}:{code}")
        scriptgeneration.generation(stepname=stepname,stepfile=output_text)
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
            # TODO: 生成分享码
            name1 = self.input_box.text() if self.input_box.text().strip() else f"{random.randint(100,999)}"
            aa,bb=self.output_content()
            bb=self.char_input.text()
            dialog = QDialog(self)
            dialog.setWindowTitle('分享码')
            layout = QVBoxLayout()
            text_edit = QTextEdit(dialog)
            text_edit.setReadOnly(True)
            text_edit.setText(f"{name1}#{aa}#{bb}")
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
            char = self.char_input.text()
            if char:
                text_edit.setText(f"{stepname}:{char}:{code}")
            else:
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
                if not self.is_text_mode:
                    self.switch_mode()
                # 解析单次UB分享码
                stepname, content, td = a.split('#')
                self.text_edit.setPlainText(content)
                self.input_box.setText(stepname)
                self.char_input.setText(td)
                namelist = td.split(' ')
                specialgenerat.generation(stepname, stepfile=content, namelist=namelist)
                # TODO: 解析内容并生成脚本
                QMessageBox.information(self, "提示", f"已生成")
                return
            else:
                # 自动切换到开关SET模式
                if self.is_text_mode:
                    self.switch_mode()
                # ...existing code...
                if ":" in a:
                    a = a.split(":")
                    if len(a) == 2:
                        c, t = sharecode.from_share(a[1])
                        self.input_box.setText(a[0])
                    elif len(a) == 3:
                        c, t = sharecode.from_share(a[2])
                        self.char_input.setText(a[1])
                        self.input_box.setText(a[0])
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
                
            QMessageBox.information(self, '成功', f'已删除脚本：{script_name}')
        except Exception as e:
            QMessageBox.warning(self, '错误', f'删除脚本失败：{str(e)}')

    def update_character_list(self):
        # 开始提示
        QMessageBox.information(self, '提示', '开始下载请勿关闭窗口,可能需要数分钟和科学上网')
        
        # 创建并启动下载线程
        self.ota_thread = OtaThread()
        self.ota_thread.finished.connect(self._on_download_complete)
        self.ota_thread.start()

    def _on_download_complete(self):
        # 完成提示
        QMessageBox.information(self, '提示', '角色更新完成')

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

    def process_text(self,text, namelist):
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

                        # 如果已有同名脚本则跳过
                        if stepname in existing_scripts:
                            skip_count += 1
                            continue

                        namelist = td.split(' ')
                        try:
                            # 生成单次UB脚本
                            specialgenerat.generation(stepname, stepfile=content, namelist=namelist)
                            success_count += 1
                            existing_scripts.add(stepname)
                        except Exception as e:
                            print(f"生成单次UB脚本失败: {line}, 错误: {e}")
                            continue
                    else:
                        parts = line.split(':')
                        if len(parts) < 2:
                            continue

                        script_name = parts[0]

                        # 检查是否存在同名脚本
                        if script_name in existing_scripts:
                            skip_count += 1
                            continue

                        # 根据共享码格式调用相应的处理逻辑
                        try:
                            if len(parts) == 2:
                                c, t = sharecode.from_share(parts[1])
                            elif len(parts) == 3:
                                c, t = sharecode.from_share(parts[2])
                            else:
                                # 不认识的格式，跳过
                                continue
                        except Exception as e:
                            print(f"解析共享码失败: {line}, 错误: {e}")
                            continue

                        # 生成 SET 脚本
                        stepname = script_name
                        try:
                            scriptgeneration.generation(stepname=stepname, stepfile=self.format_content(c, t))
                            success_count += 1
                            existing_scripts.add(script_name)
                        except Exception as e:
                            print(f"生成SET脚本失败: {line}, 错误: {e}")
                            continue
                    
                except Exception as e:
                    print(f"处理共享码失败: {line}, 错误: {str(e)}")
                    continue

            # 显示处理结果
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
        output_text = []
        for i, (t, tp, s) in enumerate(content):
            if i == 0:
                output_text.append((f"{int(t[:-2])}:{t[-2:]}", tp, s, td.get(i, 0.015)))
            else:
                prev_status = content[i-1][2]
                status_diff = [x != y for x, y in zip(s, prev_status)]
                output_text.append((f"{int(t[:-2])}:{t[-2:]}", tp, status_diff, td.get(i, 0.015)))
        return output_text
class OtaThread(QThread):
    finished = pyqtSignal()
    
    def run(self):
        try:
            ota.devMain()
            self.finished.emit()
        except Exception as e:
            # 异常处理可以根据需要添加
            pass

    
if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())