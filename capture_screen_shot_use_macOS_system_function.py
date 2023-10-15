import subprocess
#from io import BytesIO
from PIL import Image
from google.cloud import vision_v1
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget
import os

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
        screenshot_button = QPushButton("Take Screenshot and Analyze Text")
        screenshot_button.clicked.connect(self.takeScreenshotAndAnalyze)

        layout.addWidget(screenshot_button)

    def takeScreenshotAndAnalyze(self):
        subprocess.run(["screencapture", "-i", "screenshot.png"])

        # 读取截图文件
        with open("screenshot.png", "rb") as image_file:
            image_data = image_file.read()

        # 使用 Google Cloud Vision 分析图像
        client = vision_v1.ImageAnnotatorClient()
        image = vision_v1.Image(content=image_data)
        response = client.text_detection(image=image)

        # 提取文本检测结果
        texts = response.text_annotations
        for text in texts:
            print(f"Detected text: {text.description}")

if __name__ == "__main__":
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = "manifest-surfer-400014-b04707cc60d4.json"
    app = QApplication([])
    window = ScreenshotApp()
    window.show()
    app.exec()
