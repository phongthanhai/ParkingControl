import sys
from PyQt5.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout

app = QApplication(sys.argv)
window = QWidget()
window.setWindowTitle("Test")
layout = QVBoxLayout()

label = QLabel("If i see this PyQt works")
layout.addWidget(label)

window.setLayout(layout)
window.resize(300,100)
window.show()

sys.exit(app.exec_())
