import sys
from PyQt5.QtWidgets import QLineEdit,QApplication, QWidget,QLabel, QVBoxLayout, QTableWidget, QTableWidgetItem, QComboBox, QPushButton, QCheckBox, QFileDialog, QMessageBox,QHBoxLayout
from PyQt5.QtCore import Qt
import random
import scriptgeneration


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('轴输入窗口')
        self.setGeometry(100, 100, 800, 600)

        self.layout = QVBoxLayout()

        self.table = QTableWidget()
        self.table.setColumnCount(4)  # 时间、时点、状态、操作
        self.table.setHorizontalHeaderLabels(['时间', '?号位UB后', '状态', '操作'])
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
        self.output_button = QPushButton('输出脚本')
        self.output_button.clicked.connect(self.output_content)
        self.layout.addLayout(self.input_layout)
        self.layout.addWidget(self.output_button)

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
        for i in range(1, 6):
            time_point_combo.addItem(str(i))
        self.table.setCellWidget(row_index, 1, time_point_combo)

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
        for row in range(self.table.rowCount()):
            time = self.table.item(row, 0).text()
            time_point = self.table.cellWidget(row, 1).currentText()
            status = []
            status_layout = self.table.cellWidget(row, 2)
            for checkbox in status_layout.findChildren(QCheckBox):
                status.append(checkbox.isChecked())
            content.append((time, time_point,status))

        output_text = []
        for i, (t, tp, s) in enumerate(content):
            if i == 0 and t=="初始状态":
                output_text.append(('1:26', tp, s))
            elif i == 0 :
                output_text.append((f"{int(t[:-2])}:{t[-2:]}", tp, s))
            else:
                prev_status = content[i-1][2]
                status_diff =  [x != y for x, y in zip(s, prev_status)]
                output_text.append((f"{int(t[:-2])}:{t[-2:]}", tp, status_diff))
        
        input_text = self.input_box.text()
        stepname=input_text if input_text.strip() else f"{random.randint(100,999)}"
        scriptgeneration.generation(stepname=stepname,stepfile=output_text)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())