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
        self.is_setting_input=False
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle('轴输入窗口')
        self.setGeometry(100, 100, 1000, 600)

        # 添加菜单栏
        self.menu_bar = QMenuBar(self)
        
        # 添加脚本管理菜单
        script_menu = QMenu('脚本管理', self)
        self.menu_bar.addMenu(script_menu)
        
        manage_action = script_menu.addAction('管理脚本')
        manage_action.triggered.connect(self.show_script_manager)
        
        # 添加更新菜单
        update_menu = QMenu('更新(初次使用务必更新)', self)
        self.menu_bar.addMenu(update_menu)
        
        update_action = update_menu.addAction('更新角色列表')
        update_action.triggered.connect(self.update_character_list)
        
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

        self.layout = QVBoxLayout()
        self.layout.setMenuBar(self.menu_bar)  # 将菜单栏添加到布局中

        self.table = QTableWidget()
        self.table.setColumnCount(5)  # 时间、时点、状态、操作
        self.table.setHorizontalHeaderLabels(['时间', '?号位UB后', '状态', '操作','延时(秒)'])
        #self.table.setRowCount(1)  # 初始有一行

        self.add_row()  # 添加初始行
        item = QTableWidgetItem("初始状态")
        
        self.table.setItem(0,0,item)

        self.layout.addWidget(self.table)
        
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
        self.share_layout.addWidget(self.label2)
        self.share_layout.addWidget(self.share_box)
        self.share_layout.addWidget(self.sharein_button)
        self.layout.addLayout(self.input_layout)
        
        self.layout.addWidget(self.output_button)
        self.layout.addWidget(self.share_button)
        self.layout.addLayout(self.share_layout)
        self.setLayout(self.layout)

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


    def output_content(self):
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
                time_point = 6
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
            if time_point == 6:
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
        # 创建自定义的对话框
        c,t=self.output_content()
        code=sharecode.to_share(c,t)
        dialog = QDialog(self)
        dialog.setWindowTitle('分享码')
        
        # 创建垂直布局
        layout = QVBoxLayout()
        
        # 分享码文本框
        text_edit = QTextEdit(dialog)
        text_edit.setReadOnly(True)  # 设置为只读模式，防止用户编辑
        input_text = self.input_box.text()
        stepname=input_text if input_text.strip() else f"{random.randint(100,999)}"
        char=self.char_input.text()
        if char:
            text_edit.setText(f"{stepname}:{char}:{code}")
        else:
            text_edit.setText(f"{stepname}:{code}")  # 设置要显示的文本
        layout.addWidget(text_edit)
        
        # 添加共享网址提示
        url_label = QLabel('共享网址：<a href="https://docs.qq.com/sheet/DU2NHdnlNalFqdVZz">https://docs.qq.com/sheet/DU2NHdnlNalFqdVZz</a>')
        url_label.setOpenExternalLinks(True)  # 允许点击链接
        url_label.setTextFormat(Qt.RichText)  # 使用富文本格式以支持链接
        layout.addWidget(url_label)
        
        dialog.setLayout(layout)
        dialog.exec_()
    def genbyshare(self):
        a=self.share_box.text()
        try:
            if ":" in a:
                a=a.split(":")
                if len(a)==2:
                    c,t=sharecode.from_share(a[1])
                    self.input_box.setText(a[0])
                elif len(a)==3:
                    c,t=sharecode.from_share(a[2])
                    self.char_input.setText(a[1])
                    self.input_box.setText(a[0])
                self.set_input(c,t)
            else:
                c,t=sharecode.from_share(a)
                self.set_input(c,t)
            self.usecontent(c,t)
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
            
            # 清空轴名输入
            self.input_box.clear()
            
            # 重置余刀剩余时间
            self.remaining_time_input.setText("130")
            
            # 清空分享码
            self.share_box.clear()

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