import sys
from PIL import ImageGrab  # 在 macOS 和 Windows 上都有效
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget

class ScreenshotApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        # 创建中央小部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建中央小部件的布局
        layout = QVBoxLayout(central_widget)

        # 创建截图按钮
        screenshot_button = QPushButton("Take Screenshot")
        screenshot_button.clicked.connect(self.takeScreenshot)

        layout.addWidget(screenshot_button)

    def takeScreenshot(self):
        # 使用 Pillow 来让用户自行框选区域并截图
        screenshot = ImageGrab.grabclipboard()
        if screenshot is not None:
            screenshot.save("screenshot.png")
        else:
            print("No screenshot data available from clipboard.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ScreenshotApp()
    window.show()
    sys.exit(app.exec())
