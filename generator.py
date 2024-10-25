import sys
from PyQt5.QtWidgets import QLineEdit,QApplication, QWidget,QLabel, QVBoxLayout, QTableWidget, QTableWidgetItem, QComboBox, QPushButton, QCheckBox, QFileDialog, QMessageBox,QHBoxLayout,QDialog,QTextEdit
from PyQt5.QtCore import Qt
import random
import scriptgeneration
import sharecode

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('轴输入窗口')
        self.setGeometry(100, 100, 1000, 600)

        self.layout = QVBoxLayout()

        self.table = QTableWidget()
        self.table.setColumnCount(5)  # 时间、时点、状态、操作
        self.table.setHorizontalHeaderLabels(['时间', '?号位UB后', '状态', '操作','延时(秒)'])
        #self.table.setRowCount(1)  # 初始有一行

        self.add_row()  # 添加初始行
        item = QTableWidgetItem("初始状态")
        
        self.table.setItem(0,0,item)

        self.layout.addWidget(self.table)
        self.input_layout = QHBoxLayout()
        self.label = QLabel("轴名：")
        self.input_box = QLineEdit()
        self.input_layout.addWidget(self.label)
        self.input_layout.addWidget(self.input_box)
        self.output_button = QPushButton('生成脚本')
        self.output_button.clicked.connect(self.gen1)
        self.share_layout = QHBoxLayout()
        self.label2 = QLabel("分享码：")
        self.share_box = QLineEdit()
        self.share_button= QPushButton('一键分享')
        self.share_button.clicked.connect(self.show_popup)
        self.sharein_button= QPushButton('读取分享')
        self.sharein_button.clicked.connect(self.gen2)
        self.share_layout.addWidget(self.label2)
        self.share_layout.addWidget(self.share_box)
        self.share_layout.addWidget(self.sharein_button)
        self.layout.addLayout(self.input_layout)
        
        self.layout.addWidget(self.output_button)
        self.layout.addWidget(self.share_button)
        self.layout.addLayout(self.share_layout)
        self.setLayout(self.layout)
    def add_row(self):
        row_index = self.table.rowCount()
        self.table.insertRow(row_index)
        # 时间列
        time_input = QTableWidgetItem()
        time_input.setData(Qt.EditRole, '001')
        self.table.setItem(row_index, 0, time_input)

        # 时点列
        time_point_combo = QComboBox()
        for i in range(0, 6):
            time_point_combo.addItem(str(i))
        self.table.setCellWidget(row_index, 1, time_point_combo)
        # 延时列
        timed_input = QTableWidgetItem()
        timed_input.setData(Qt.EditRole, 0.0)
        self.table.setItem(row_index, 4, timed_input)
        # 状态列
        
        status_layout = QWidget()
        status_layout_layout = QHBoxLayout(status_layout)
        status_layout_layout.setContentsMargins(0, 0, 0, 0)
        status_layout_layout.setSpacing(0)
        status_checkboxes = []
        for i in range(1, 6):
            checkbox = QCheckBox(str(i)+"    ")
            status_layout_layout.addWidget(checkbox)
            status_checkboxes.append(checkbox)
        checkbox = QCheckBox('A')
        status_layout_layout.addWidget(checkbox)
        status_checkboxes.append(checkbox)
        self.table.setCellWidget(row_index, 2, status_layout)
        
        if row_index > 0:
            previous_row_status_layout = self.table.cellWidget(row_index - 1, 2)
            previous_row_status_layout_layout = previous_row_status_layout.layout()
            for i in range(previous_row_status_layout_layout.count()):
                previous_checkbox = previous_row_status_layout_layout.itemAt(i).widget()
                current_checkbox = status_checkboxes[i]
                current_checkbox.setChecked(previous_checkbox.isChecked())

        # 操作列
        add_button = QPushButton('添加')
        add_button.clicked.connect(self.add_row)
        self.table.setCellWidget(row_index, 3, add_button)
        self.table.setColumnWidth(2, 300)
    def output_content(self):
        content = []
        td = {}
        for row in range(self.table.rowCount()):
            time = self.table.item(row, 0).text().replace("初始状态","126")
            time_point = self.table.cellWidget(row, 1).currentText()
            value = float(self.table.item(row, 4).text())  # 假设第五列是文本格式，可以转换为浮点数
            if value != 0:
                td[row] = value # 行号从1开始，值为非零的内容
            status = []
            status_layout = self.table.cellWidget(row, 2)
            for checkbox in status_layout.findChildren(QCheckBox):
                status.append(checkbox.isChecked())
            content.append((time, time_point,status))
        return content,td
    
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
        stepname=input_text if input_text.strip() else f"{random.randint(100,999)}"
        code=sharecode.to_share(content,td)
        self.autosave(f"{stepname}:{code}")
        scriptgeneration.generation(stepname=stepname,stepfile=output_text)
        msg = QMessageBox()
        msg.setText(f'已生成脚本 "{stepname}"')
        msg.setIcon(QMessageBox.Information)
        msg.exec_()
    def gen1(self):
        try:
            c,t=self.output_content()
            self.usecontent(c,t)
        except Exception as e:
            msg = QMessageBox()
            msg.setText(f'发生错误{e}')
            msg.setIcon(QMessageBox.Information)
            msg.exec_()
        
    def show_popup(self):
        # 创建自定义的对话框
        c,t=self.output_content()
        code=sharecode.to_share(c,t)
        dialog = QDialog(self)
        dialog.setWindowTitle('分享码')
        text_edit = QTextEdit(dialog)
        text_edit.setReadOnly(True)  # 设置为只读模式，防止用户编辑
        input_text = self.input_box.text()
        stepname=input_text if input_text.strip() else f"{random.randint(100,999)}"
        text_edit.setText(f"{stepname}:{code}")  # 设置要显示的文本
        # 设置布局
        layout = QVBoxLayout()
        layout.addWidget(text_edit)
        dialog.setLayout(layout)
        # 显示对话框
        dialog.exec_()
    def gen2(self):
        a=self.share_box.text()
        try:
            if ":" in a:
                a=a.split(":")
                c,t=sharecode.from_share(a[1])
                self.input_box.setText(a[0])
            else:
                c,t=sharecode.from_share(a)
            self.usecontent(c,t)
        except Exception as e:
            msg = QMessageBox()
            msg.setText(f'分享码有误或使用方法错误{e}')
            msg.setIcon(QMessageBox.Information)
            msg.exec_()
    def autosave(self,content):
    # 使用 'a' 模式打开文件，追加写入
        with open("自动保存的分享码.txt", 'a', encoding='utf-8') as file:
        # 写入字符串到文件末尾，并换行
            file.write(content + '\n')
    
if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())