# -*- coding: utf-8 -*-

import io
import os
import sys
import cv2
import html
import subprocess
import numpy as np 
from io import BytesIO
from PIL import ImageGrab, Image
from PySide6.QtGui import QPalette, QColor, QFontMetrics, QIcon
from PySide6.QtWidgets import QMainWindow, QMessageBox, QApplication, QPushButton, QHBoxLayout, QWidget
from PySide6.QtCore import Signal, QTimer, QProcess, QSize, Property, QObject, QEasingCurve, QPropertyAnimation
from google.cloud import vision_v1
from google.cloud import translate_v2 as translate
from google.oauth2 import service_account

from settings import *
from config_handler import *


# 設置 GCP 參數
client_vision = None
client_translate = None


def set_google_vision():
    global client_vision
    # 初始化Google Cloud Vision API客戶端
    client_vision = vision_v1.ImageAnnotatorClient() 

def set_google_translation():
    global client_translate
    # 初始化Google Cloud Translation API客戶端
    client_translate = translate.Client()   


# create icon scale signal
class IconScaler(QObject):
    icon_size_changed = Signal(QSize)

    def __init__(self):
        super().__init__()
        self._icon_size = QSize(32, 32)

    @Property(QSize, notify=icon_size_changed)
    def icon_size(self):
        return self._icon_size

    @icon_size.setter
    def icon_size(self, size):
        self._icon_size = size
        self.icon_size_changed.emit(size)

# create button scale class and add the animations when cursor hover、press、release the button
class ScalableButton(QPushButton):
    def __init__(self, name, icon_path, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.icon_path = icon_path
        self.icon_scaler = IconScaler()
        self.is_pressed = False

        # 创建一个属性动画
        self.animation = QPropertyAnimation(self.icon_scaler, b"icon_size")
        self.animation.setDuration(200)  # 动画持续时间（毫秒）
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)  # 使用适合的缓动曲线

        # 连接 icon_size_changed 信号以更新按钮的图标大小
        self.icon_scaler.icon_size_changed.connect(self.updateIconSize)

        # 连接 pressed 信号和 released 信号以执行缩小和恢复操作
        self.pressed.connect(self.onButtonPressed)
        self.released.connect(self.onButtonReleased)

        self.setObjectName(name)  # 设置按钮的对象名称

        # 创建初始图标
        self.createIcon(icon_path)

        # 连接按钮的点击信号到自定义槽函数
        #self.clicked.connect(self.onButtonClicked)

    def createIcon(self, path):
        # 创建一个图标
        icon = QIcon(path)

        # 设置图标到按钮
        self.setIcon(icon)

        # 设置初始图标大小
        self.setIconSize(self.icon_scaler.icon_size)

    def onButtonPressed(self):
        # 鼠标按下按钮，缩小图标并更改为新图标（如果有）
        self.animateIconSize(QSize(28, 28))
        self.is_pressed = True

    def onButtonReleased(self):
        # 鼠标释放按钮，恢复原始图标大小
        self.is_pressed = False
        self.createIcon(self.icon_path)
        self.animateIconSize(QSize(40, 40))

    # def onButtonClicked(self):
    #     # 当按钮被点击时，执行其他函数
    #     print(f"{self.objectName()} clicked")

    def enterEvent(self, event):
        # 鼠标进入按钮，放大图标
        if not self.is_pressed:  # 仅当按钮未按下时放大
            self.animateIconSize(QSize(40, 40))

    def leaveEvent(self, event):
        # 鼠标离开按钮，还原原始图标大小
        if not self.is_pressed:  # 仅当按钮未按下时还原
            self.animateIconSize(QSize(32, 32))

    def animateIconSize(self, target_size):
        self.animation.setStartValue(self.icon_scaler.icon_size)
        self.animation.setEndValue(target_size)
        self.animation.start()

    def updateIconSize(self, size):
        self.setIconSize(size)


class MainMenuWindow(QMainWindow):
    def __init__(self, config_handler):
        global client_vision, client_translate

        if getattr(sys, 'frozen', False):
            # 应用程序被打包
            app_dir = sys._MEIPASS
        else:
            app_dir = os.path.dirname(os.path.abspath(__file__))

        self.app_dir = app_dir

        super().__init__()

        # read config file
        self.config_handler = config_handler

        # set private member
        self._frequency = ""
        self._google_credentials = ""

        # 設置 capturing state 顯示計時器
        self.capturing_system_state_timer = QTimer(self)
        self.capturing_system_state_timer.timeout.connect(self.update_system_state)
        self.system_state_flag = True

        # Set the title
        self.setWindowTitle("Main Control Windows")

        # Set the window background color to black
        main_window_palette = QPalette()
        main_window_palette.setColor(QPalette.Window, QColor(10, 10, 10))
        self.setPalette(main_window_palette)

        # Set the window opacity
        self.setWindowOpacity(0.95)

        # Set the window geometry
        screen_geometry = QApplication.primaryScreen().geometry()
        self.setGeometry(screen_geometry.x() + (screen_geometry.width() // 3) * 2, 
                         screen_geometry.y() + screen_geometry.height() // 4,
                         screen_geometry.width() // 5, screen_geometry.height() // 2.5)
         # Set a fixed size
        self.setFixedSize(screen_geometry.width() // 5, screen_geometry.height() // 2.5)
        
        # Create a button to add the screen capture window
        #self.add_window_button = QPushButton("", self)
        new_file_path = os.path.join(self.app_dir, "img/ui/desktop_windows_white_24dp.svg")
        self.add_window_button = ScalableButton("add_window_button", new_file_path)
        self.add_window_button.setToolTip("新增螢幕擷取視窗")
        # 使用样式表自定义按钮的外观
        self.add_window_button.setStyleSheet(
            "QPushButton {"
            "    background-color: rgba(0, 0, 0, 0);"
            "    color: rgb(58, 134, 255);"
            #"    border: 2px solid rgb(58, 134, 255);"
            "    border-radius: 8px;"
            "}"
            "QPushButton:hover {"
            "    background-color: QLinearGradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #488EF7, stop: 1 #3478F6);"
            "    border: none;"
            "    color: white;"
            "}"
            "QPushButton:pressed {"
            "    background-color: QLinearGradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #3879E3, stop: 1 #2D66EA);"
            "    border: none;"
            "    color: white;"
            "}"
        )

        # set icon to add_capture_window_button
        # add_capture_window_path = "img/ui/screenshot_monitor_white_24dp.svg"
        # add_capture_window_icon = QIcon(add_capture_window_path)
        # self.add_window_button.setIcon(add_capture_window_icon)
        # self.add_window_button.setIconSize(QSize(32, 32))  # Scale the icon size
        self.add_window_button.setMinimumSize(45, 45)  # Set the minimum size for the button to ensure the icon fits

        self.add_window_button.clicked.connect(self.add_or_check_screen_capture_window)

        # Create a capturing button to start screen capture
        #self.action_button = QPushButton("", self)
        new_file_path = os.path.join(self.app_dir, "img/ui/radio_button_unchecked_white_24dp.svg")
        self.action_button = ScalableButton("action_button", new_file_path)
        self.action_button.setToolTip("開始擷取畫面")
        self.action_button.setStyleSheet(
            "QPushButton {"
            "    background-color: rgba(0, 0, 0, 0);"
            "    color: rgb(58, 134, 255);"
            #"    border: 2px solid rgb(58, 134, 255);"
            "    border-radius: 8px;"
            "}"
            "QPushButton:hover {"
            "    background-color: QLinearGradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #488EF7, stop: 1 #3478F6);"
            "    border: none;"
            "    color: white;"
            "}"
            "QPushButton:pressed {"
            "    background-color: QLinearGradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #3879E3, stop: 1 #2D66EA);"
            "    border: none;"
            "    color: white;"
            "}"
        )

        # set icon to action_button
        # action_icon_path = "img/ui/radio_button_unchecked_white_24dp.svg"
        # action_icon = QIcon(action_icon_path)
        # self.action_button.setIcon(action_icon)
        # self.action_button.setIconSize(QSize(32, 32))  # Scale the icon size
        self.action_button.setMinimumSize(45, 45)  # Set the minimum size for the button to ensure the icon fits

        self.action_button.clicked.connect(self.toggle_capture)
        self.capturing = False  # Track capturing state

        # Create a button to capture the screenshot
        new_file_path = os.path.join(self.app_dir, "img/ui/screenshot_monitor_white_24dp.svg")
        self.screenshot_button = ScalableButton("add_window_button", new_file_path)
        self.screenshot_button.setToolTip("螢幕截圖")
        # 使用样式表自定义按钮的外观
        self.screenshot_button.setStyleSheet(
            "QPushButton {"
            "    background-color: rgba(0, 0, 0, 0);"
            "    color: rgb(58, 134, 255);"
            #"    border: 2px solid rgb(58, 134, 255);"
            "    border-radius: 8px;"
            "}"
            "QPushButton:hover {"
            "    background-color: QLinearGradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #488EF7, stop: 1 #3478F6);"
            "    border: none;"
            "    color: white;"
            "}"
            "QPushButton:pressed {"
            "    background-color: QLinearGradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #3879E3, stop: 1 #2D66EA);"
            "    border: none;"
            "    color: white;"
            "}"
        )

        # set icon to add_capture_window_button
        # add_capture_window_path = "img/ui/screenshot_monitor_white_24dp.svg"
        # add_capture_window_icon = QIcon(add_capture_window_path)
        # self.add_window_button.setIcon(add_capture_window_icon)
        # self.add_window_button.setIconSize(QSize(32, 32))  # Scale the icon size
        self.screenshot_button.setMinimumSize(45, 45)  # Set the minimum size for the button to ensure the icon fits

        self.screenshot_button.clicked.connect(self.capture_screenshot)

        # Create a button to pin the window on the toppest
        # self.pin_button = QPushButton("", self)
        new_file_path = os.path.join(self.app_dir, "img/ui/near_me_disabled_white_24dp.svg")
        self.pin_button = ScalableButton("pin_button", new_file_path)
        self.pin_button.setToolTip("取消釘選")
        self.pin_button.setStyleSheet(
            "QPushButton {"
            "    background-color: rgba(0, 0, 0, 0);"
            "    color: rgb(58, 134, 255);"
            #"    border: 2px solid rgb(58, 134, 255);"
            "    border-radius: 8px;"
            "}"
            "QPushButton:hover {"
            "    background-color: QLinearGradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #488EF7, stop: 1 #3478F6);"
            "    border: none;"
            "    color: white;"
            "}"
            "QPushButton:pressed {"
            "    background-color: QLinearGradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #3879E3, stop: 1 #2D66EA);"
            "    border: none;"
            "    color: white;"
            "}"
        )

        # set icon to pin_button
        # pin_icon_path = "img/ui/near_me_disabled_white_24dp.svg"
        # pin_icon = QIcon(pin_icon_path)
        # self.pin_button.setIcon(pin_icon)
        # self.pin_button.setIconSize(QSize(32, 32))  # Scale the icon size
        self.pin_button.setMinimumSize(45, 45)  # Set the minimum size for the button to ensure the icon fits

        self.pin_button.clicked.connect(self.pin_on_top)
        self.is_pined = True  # Track pining state

        # Create a button to open settings window
        # self.settings_button = QPushButton("", self)
        new_file_path = os.path.join(self.app_dir, "img/ui/settings_white_24dp.svg")
        self.settings_button = ScalableButton("settings_button", new_file_path)
        self.settings_button.setToolTip("設定")
        self.settings_button.setStyleSheet(
            "QPushButton {"
            "    background-color: rgba(0, 0, 0, 0);"
            "    color: rgb(58, 134, 255);"
            #"    border: 2px solid rgb(58, 134, 255);"
            "    border-radius: 8px;"
            "}"
            "QPushButton:hover {"
            "    background-color: QLinearGradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #488EF7, stop: 1 #3478F6);"
            "    border: none;"
            "    color: white;"
            "}"
            "QPushButton:pressed {"
            "    background-color: QLinearGradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #3879E3, stop: 1 #2D66EA);"
            "    border: none;"
            "    color: white;"
            "}"
        )

        # set icon to settings_button
        # settings_icon_path = "img/ui/settings_white_24dp.svg"
        # settings_icon = QIcon(settings_icon_path)
        # self.settings_button.setIcon(settings_icon)
        # self.settings_button.setIconSize(QSize(32, 32))  # Scale the icon size
        self.settings_button.setMinimumSize(45, 45)  # Set the minimum size for the button to ensure the icon fits

        # connect button to show_settings funciton
        self.settings_button.clicked.connect(self.show_settings)

        # Set button backgrounds to transparent
        #self.add_window_button.setStyleSheet('QPushButton {background-color: transparent; color: red;}')
        # self.add_window_button.setStyleSheet('QPushButton {background-color: white; color: red;}')
        # self.action_button.setStyleSheet('QPushButton {background-color: white; color: red;}')
        # self.pin_button.setStyleSheet('QPushButton {background-color: white; color: red;}')
        # self.settings_button.setStyleSheet('QPushButton {background-color: white; color: red;}')

        # 創建用於顯示 google credential憑證狀態 的 QLabel
        self.google_credential_state = QLabel("Google 憑證：", self)
        self.google_credential_state.setAutoFillBackground(False)  # 设置背景颜色為透明
        self.google_credential_state.setStyleSheet("color: white;")  # 設置文字顏色為白色

        # 創建用於顯示 目前程式系統狀態 的 QLabel
        self.system_state = QLabel("系統狀態： 已停止擷取", self)
        self.system_state.setAutoFillBackground(False)  # 设置背景颜色為透明
        self.system_state.setStyleSheet("color: white;")  # 設置文字顏色為白色

        # 創建一條水平線以隔開 label
        self.line = QFrame()
        self.line.setFrameShape(QFrame.HLine)
        self.line.setFrameShadow(QFrame.Sunken)
        self.line.setLineWidth(1)  # 設置線條寬度為 2px

        # 创建用于显示OCR识别文本的QLabel
        self.ocr_label = QLabel("OCR Recognized Text:", self)
        self.ocr_label.setAutoFillBackground(False)  # 设置背景颜色為透明
        self.ocr_label.setStyleSheet("color: white;")  # 設置文字顏色為白色
        self.ocr_text_label = QLabel("", self)
        self.ocr_text_label.setStyleSheet("background-color: rgb(50, 50, 50); border-radius: 10px;")
        self.ocr_text_label.setAutoFillBackground(True)  # 允许设置背景颜色
        self.ocr_text_label.setContentsMargins(10, 10, 10, 10)  # 設置距離最左、最右、最上、最下的內邊距為 10px
        self.ocr_text_label.setWordWrap(True)  # 启用自动换行

        # 创建用于显示翻译后文本的QLabel
        self.translation_label = QLabel("Translation:", self)
        self.translation_label.setStyleSheet("color: white;")  # 設置文字顏色為白色
        self.translation_label.setAutoFillBackground(False)  # 设置背景颜色為透明
        self.translation_text_label = QLabel("", self)
        self.translation_text_label.setAutoFillBackground(True)  # 允许设置背景颜色
        self.translation_text_label.setStyleSheet("background-color: rgb(50, 50, 50); border-radius: 10px;")
        self.translation_text_label.setContentsMargins(10, 10, 10, 10)  # 設置距離最左、最右、最上、最下的內邊距為 10px
        self.translation_text_label.setWordWrap(True)  # 启用自动换行

        # 設置 ocr_lable 和 ocr_translation_label 的字體大小與粗細度
        font = QFont()
        font.setPointSize(16)
        font.setBold(True) # 設置粗體
        self.ocr_label.setFont(font)
        self.translation_label.setFont(font)

        # 設置 google_credential_state 和 system_state 的字體大小和粗細度
        state_font = QFont()
        state_font.setPointSize(12)
        state_font.setBold(True) # 設置粗體
        self.google_credential_state.setFont(state_font)
        self.system_state.setFont(state_font)

        # Calculate the height based on font size
        # Set the height of ocr_label, translation_label, google_credential_state, system_state to match font size
        font_metrics = QFontMetrics(font)
        state_font_metrics = QFontMetrics(state_font)
        label_height = font_metrics.height()
        state_label_height = state_font_metrics.height()
        self.ocr_label.setFixedHeight(label_height)
        self.translation_label.setFixedHeight(label_height)
        self.google_credential_state.setFixedHeight(state_label_height)
        self.system_state.setFixedHeight(state_label_height)

        # 创建一个QPalette对象来设置 OCR_result_text 的背景及文字颜色
        self.text_label_palette = QPalette()
        self.text_label_palette.setColor(QPalette.Window, QColor(50, 50, 50))  # 设置背景颜色为浅灰色

        # 讀取 config file 中的 text_font_size
        text_font_size = self.config_handler.get_font_size()
        self.update_text_font_size(text_font_size)

        # 讀取 config file 中的 text_font_color
        text_font_color = self.config_handler.get_font_color()
        self.update_text_font_color(text_font_color)

        # 讀取 config file 中的 capture_frequency
        frequency = self.config_handler.get_capture_frequency()
        self.update_recognition_frequency(frequency)

        # Create a vertical layout
        layout = QVBoxLayout()

        # 设置左侧的按钮为固定大小且靠左
        # self.add_window_button.setFixedSize(100, 30)  # 调整按钮的大小
        # self.action_button.setFixedSize(100, 30)
        # self.pin_button.setFixedSize(100, 30)

        # 设置右侧按钮为固定大小且靠右
        #self.settings_button.setFixedSize(100, 30)

        # Create a horizontal layout for add_window_button, action_button, pin_button, settings_button
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.add_window_button)
        button_layout.addWidget(self.action_button)
        button_layout.addWidget(self.screenshot_button)
        button_layout.addWidget(self.pin_button)
        button_layout.addStretch(1)  # 弹簧项，推动右边的按钮靠右
        button_layout.addWidget(self.settings_button)


        # Create a horizontal layout for google_credential_state, system_state
        system_state_layout = QHBoxLayout()
        system_state_layout.addWidget(self.google_credential_state)
        system_state_layout.addWidget(self.system_state)

        # Add the horizontal button layout and system state layout to the vertical layout
        layout.addLayout(button_layout)
        layout.addLayout(system_state_layout)

        # Add the horizontal line to the vertical layout to seperate the system_state_layout and ocr_label
        layout.addWidget(self.line)

        # Add ocr_label and translation_label to the layout
        layout.addWidget(self.ocr_label)
        layout.addWidget(self.ocr_text_label)
        layout.addWidget(self.translation_label)
        layout.addWidget(self.translation_text_label)

        # Create a QWidget as a container for the layout
        widget = QWidget(self)
        widget.setLayout(layout)

        # Add the QWidget to the main window
        self.setCentralWidget(widget)

        # 设置窗口标志，使其始终显示在最上面
        self.setWindowFlags(Qt.WindowStaysOnTopHint)

        # Initialize the attribute
        self.screen_capture_window = None 

        # 設定Google Cloud金鑰環境變數
        if self.config_handler.get_google_credential_path() != "":
            google_key_file_path = self.config_handler.get_google_credential_path()
            self.check_google_credential_state(google_key_file_path)
            
        else:      
            # set timer for messagebox delayed show
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.show_message_box)
            self.delayed_show_message_box()

            # set only setting button enabled
            for button in [self.add_window_button, self.action_button, self.screenshot_button, self.pin_button]:
                button.setEnabled(False)

            # 設置 google_credential_label
            self.google_credential_state.setText("Google 憑證： <font color='red'>無設置憑證</font> ")


    def check_google_credential_state(self, google_key_file_path):
        if os.path.exists(google_key_file_path):
            try:
                credentials = service_account.Credentials.from_service_account_file(google_key_file_path)
                # Create a client for Google Translation
                client_translate = translate.Client(credentials=credentials)
                translation = client_translate.translate('Hello', target_language='es')

                # 設置 GCP credentials 和初始化 google.vision 和 google.translation 
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = google_key_file_path
                self._google_credentials = google_key_file_path
                set_google_vision()
                set_google_translation()

                # 設置 google_credential_label
                self.google_credential_state.setText("Google 憑證： <font color='green'>憑證有效</font> ")

                # set all button enabled
                for button in [self.add_window_button, self.action_button, self.screenshot_button, self.pin_button, self.settings_button]:
                    button.setEnabled(True)

            except Exception as e:
                # 設置 google_credential_label
                self.google_credential_state.setText("Google 憑證： <font color='red'>憑證無效</font> ")

                # set only setting button enabled
                for button in [self.add_window_button, self.action_button, self.screenshot_button, self.pin_button]:
                    button.setEnabled(False)
                self.settings_button.setEnabled(True)
        else:
            # 設置 google_credential_label
            self.google_credential_state.setText("Google 憑證： <font color='red'>無設置憑證</font> ")

            # set only setting button enabled
            for button in [self.add_window_button, self.action_button, self.screenshot_button, self.pin_button]:
                button.setEnabled(False)
            self.settings_button.setEnabled(True)

    def delayed_show_message_box(self):
        # 启动定时器，延迟一定时间后显示消息框
        self.timer.start(500)  # 这里设置延迟时间为 0.5 秒（500毫秒）

    def show_message_box(self):
        # 停止计时器
        self.timer.stop()
        # 创建消息框
        msg_box = QMessageBox()
        msg_box.setWindowTitle("Information")
        msg_box.setText("Welcome to this APP. \n"
            "Please go to 'Settings' -> 'System' -> 'Set Google Credentials' "
            "to configure Google credentials before using the app.")
        msg_box.setIcon(QMessageBox.Information)
        # 设置消息框始终显示在最顶部
        msg_box.setWindowFlags(msg_box.windowFlags() | Qt.WindowStaysOnTopHint)
        # 显示消息框
        msg_box.exec()

        screenshot = ImageGrab.grab(bbox=(self.geometry().x(), self.geometry().y(),
                                                self.geometry().x() + self.geometry().width(),
                                                self.geometry().y() + self.geometry().height()))
        
    def toggle_capture(self):
        if self.capturing:
            self.stop_capture()
        else:
            self.start_capture()

    def capture_screenshot(self):
        screenshot_path = os.path.join(self.app_dir, "screenshot.png")
        subprocess.run(["screencapture", "-i", screenshot_path])

        if os.path.exists(screenshot_path):
            # 打开截图文件并转换为灰度图像
            with Image.open(screenshot_path) as img:
                img_gray = img.convert("L")
                img_bytes = BytesIO()
                img_gray.save(img_bytes, format="PNG")
                image_data = img_bytes.getvalue()

            # 使用Google Cloud Vision API進行文字辨識
            image = vision_v1.Image(content=image_data)
            response = client_vision.text_detection(image=image)
            texts = response.text_annotations

            # 提取辨識到的文字
            if texts:
                detected_text = texts[0].description

                # 设置OCR识别文本
                main_capturing_window.ocr_text_label.setText(detected_text)
    
                # 將辨識的文字按行分割
                lines = detected_text.replace("\n", "")

                # Google 翻譯
                target_language = "zh-TW"  # 將此替換為你想要的目標語言代碼（例如：英文 --> en, 繁體中文 --> zh-TW）
                translated_lines = client_translate.translate(lines, target_language=target_language)

                # Unescape HTML entities
                unescape_translated_text = html.unescape(translated_lines["translatedText"])

                # 將翻譯後的行重新組合成一個帶有換行的字符串
                translated_text_with_newlines = unescape_translated_text.replace("。", "。\n").replace('？', '？\n').replace('！', '！\n')  # 以句點和問號為換行分界點
                main_capturing_window.translation_text_label.setText(translated_text_with_newlines)
                #main_capturing_window.translation_text_label.setText(unescape_translated_text)  # 完全不以句點和問號為換行分界點
            else:
                pass

            # delete screenshot image
            os.remove(screenshot_path)

    def pin_on_top(self):
        if self.is_pined:
            self.is_pined = False
            new_file_path = os.path.join(self.app_dir, "img/ui/near_me_white_24dp.svg")
            self.pin_button.createIcon(new_file_path)
            self.pin_button.setToolTip("釘選在最上層")

            # set icon to pin_button (pin_diasabled)
            # pin_icon_path = "img/ui/near_me_white_24dp.svg"
            # pin_icon = QIcon(pin_icon_path)
            # self.pin_button.setIcon(pin_icon)
            # self.pin_button.setIconSize(QSize(32, 32))  # Scale the icon size
            # self.pin_button.setMinimumSize(40, 40)  # Set the minimum size for the button to ensure the icon fits

            # 移除screen_capture_window的最上层标志
            self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
            self.show()
        else:
            self.is_pined = True
            new_file_path = os.path.join(self.app_dir, "img/ui/near_me_disabled_white_24dp.svg")
            self.pin_button.createIcon(new_file_path)
            self.pin_button.setToolTip("取消釘選")

            # set icon to pin_button (pin_diasabled)
            # pin_icon_path = "img/ui/near_me_disabled_white_24dp.svg"
            # pin_icon = QIcon(pin_icon_path)
            # self.pin_button.setIcon(pin_icon)
            # self.pin_button.setIconSize(QSize(32, 32))  # Scale the icon size
            # self.pin_button.setMinimumSize(40, 40)  # Set the minimum size for the button to ensure the icon fits

            # 恢复screen_capture_window的最上层标志
            self.setWindowFlag(Qt.WindowStaysOnTopHint)
            self.show()

    def show_settings(self):
        # disabled all button
        for button in [self.add_window_button, self.action_button, self.screenshot_button, self.pin_button, self.settings_button]:
            button.setEnabled(False)

        # main_window 切换成無框窗口
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.show()

        # 如果screen_capture_window存在, 一併切换成無框窗口
        if hasattr(self, 'screen_capture_window') and self.screen_capture_window:
            self.screen_capture_window.setWindowFlags(Qt.FramelessWindowHint)
            self.screen_capture_window.show()

        self.settings_window = SettingsWindow(self.config_handler)
        self.settings_window.setting_window_closed.connect(self.set_main_and_capture_window_frame_window_back)
        self.settings_window.exec()

        # enabled all button
        for button in [self.add_window_button, self.action_button, self.screenshot_button, self.pin_button, self.settings_button]:
            button.setEnabled(True)

        # main_window 切换成有框窗口
        self.setWindowFlags(Qt.Window)
        # 恢复main_capture_window的最上层标志
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.show()

        # 如果screen_capture_window存在, 一併切换成有框窗口
        if hasattr(self, 'screen_capture_window') and self.screen_capture_window:
            self.screen_capture_window.setWindowFlags(Qt.Window)
            # 恢复screen_capture_window的最上层标志
            self.screen_capture_window.setWindowFlag(Qt.WindowStaysOnTopHint)
            self.screen_capture_window.show()

        # for button in [self.add_window_button, self.action_button, self.pin_button, self.settings_button]:
        #     button.setEnabled(False)

        # # main_window 切换成無框窗口
        # self.setWindowFlags(Qt.FramelessWindowHint)
        # self.show()
        # print("show settings main window")

        # # 如果screen_capture_window存在, 一併切换成無框窗口
        # if hasattr(self, 'screen_capture_window') and self.screen_capture_window:
        #     self.screen_capture_window.setWindowFlags(Qt.FramelessWindowHint)
        #     self.screen_capture_window.show()

    def update_text_font_size(self, new_font_size):
        # 在这里应用新的文本字体大小
        font = QFont()
        font.setPointSize(new_font_size)
        font.setBold(True) # 設置粗體
        self.ocr_text_label.setFont(font)
        self.translation_text_label.setFont(font)

    def update_text_font_color(self, new_font_color):
        # 在这里应用新的文本字體顏色
        self.ocr_text_label.setStyleSheet(f"background-color: rgb(50, 50, 50); border-radius: 10px; color: {new_font_color};")
        self.translation_text_label.setStyleSheet(f"background-color: rgb(50, 50, 50); border-radius: 10px; color: {new_font_color};")
        # self.text_label_palette.setColor(QPalette.WindowText, QColor(new_font_color))  # 设置文字颜色为白色
        # #self.ocr_text_label.setPalette(self.text_label_palette)
        # self.translation_text_label.setPalette(self.text_label_palette)

    def update_recognition_frequency(self, new_frequency):
        # Update Frequency
        self._frequency = new_frequency

    def update_google_credential(self, new_google_credential):
        # Update google credential
        self._google_credentials = new_google_credential
        self.check_google_credential_state(self._google_credentials)

    def add_or_check_screen_capture_window(self):
        # Check if a screen capture window is already open
        if hasattr(self, 'screen_capture_window') and self.screen_capture_window:
            QMessageBox.warning(self, "Warning", "You already have the Screen Capture Window open.")
        else:
            # Create and show the screen capture window
            self.screen_capture_window = ScreenCaptureWindow()
            self.screen_capture_window.closed.connect(self.handle_screen_capture_window_closed)
            self.screen_capture_window.show()
        
    def start_capture(self):
        if hasattr(self, 'screen_capture_window') and self.screen_capture_window:
            self.capturing = True 
            new_file_path = os.path.join(self.app_dir, "img/ui/radio_button_checked_white_24dp.svg")
            self.action_button.createIcon(new_file_path)
            self.action_button.setToolTip("停止擷取畫面")

            # set icon to action_button (stop capturing icon)
            # action_icon_path = "img/ui/radio_button_checked_white_24dp.svg"
            # action_icon = QIcon(action_icon_path)
            # self.action_button.setIcon(action_icon)
            # self.action_button.setIconSize(QSize(32, 32))  # Scale the icon size

            self.action_button.clicked.disconnect()
            self.action_button.clicked.connect(self.stop_capture)

            self.screen_capture_window.start_capture()

            self.add_window_button.setEnabled(False)
            self.screenshot_button.setEnabled(False)
            self.settings_button.setEnabled(False)

            # 移除screen_capture_window的最上层标志
            self.screen_capture_window.setWindowFlag(Qt.WindowStaysOnTopHint, False)
            self.screen_capture_window.show()

            # 設置 system_state_label: capturing
            self.update_system_state()
            self.capturing_system_state_timer.start(1000) # 每 1 秒更新一次 system_state_label 顯示狀態
        else:
            QMessageBox.warning(self, "Warning", "You haven't opened the Screen Capture Window yet.")

    def update_system_state(self):
        if self.system_state_flag:
            self.system_state.setText("系統狀態： <font color='red'>&nbsp;&nbsp;●&nbsp;擷取中</font> ")
        else:
            self.system_state.setText("系統狀態： <font color='red'>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;擷取中</font> ")
        self.system_state_flag = not self.system_state_flag  # 讓下一次顯示另一種狀態

    def stop_capture(self):
        if hasattr(self, 'screen_capture_window') and self.screen_capture_window:
            # 將 system_state_label 改為 已停止擷取
            self.system_state.setText("系統狀態： 已停止擷取")
            self.capturing_system_state_timer.stop()

            self.capturing = False
            new_file_path = os.path.join(self.app_dir, "img/ui/radio_button_unchecked_white_24dp.svg")
            self.action_button.createIcon(new_file_path)
            self.action_button.setToolTip("開始擷取畫面")

            # set icon to action_button (stop capturing icon)
            # action_icon_path = "img/ui/radio_button_unchecked_white_24dp.svg"
            # action_icon = QIcon(action_icon_path)
            # self.action_button.setIcon(action_icon)
            # self.action_button.setIconSize(QSize(32, 32))  # Scale the icon size

            self.action_button.clicked.disconnect()
            self.action_button.clicked.connect(self.toggle_capture)

            self.screen_capture_window.stop_capture()

            self.add_window_button.setEnabled(True)
            self.screenshot_button.setEnabled(True)
            self.settings_button.setEnabled(True)

            # 恢复screen_capture_window的最上层标志
            self.screen_capture_window.setWindowFlag(Qt.WindowStaysOnTopHint)
            self.screen_capture_window.show()

    def set_main_and_capture_window_frame_window_back(self):
        # 讀取 config file 中的 text_font_size
        text_font_size = self.config_handler.get_font_size()
        text_font_color = self.config_handler.get_font_color()
        frequency = self.config_handler.get_capture_frequency()
        self.update_text_font_size(text_font_size)
        self.update_text_font_color(text_font_color)
        self.update_recognition_frequency(frequency)

        google_credential = self.config_handler.get_google_credential_path()
        self.check_google_credential_state(google_credential)

    def handle_screen_capture_window_closed(self):
        # Slot to handle the screen capture window being closed
        self.screen_capture_window = None

    def get_frequncy(self):
        return self._frequency

    def closeEvent(self, event):
        # Check if the screen_capture_window is open and close it
        if self.screen_capture_window is not None:
            self.screen_capture_window.close()
        
        event.accept()

class ScreenCaptureWindow(QMainWindow):
    # Define a custom signal
    closed = Signal()
  
    def __init__(self):

        if getattr(sys, 'frozen', False):
            # 应用程序被打包
            app_dir = sys._MEIPASS
        else:
            app_dir = os.path.dirname(os.path.abspath(__file__))

        self.app_dir = app_dir

        super().__init__()

        # 定義一個變數用來比較前一張已辨識的圖片
        self.previous_image = None
  
        # set the title
        self.setWindowTitle("Screen Capture region")

        # Set the window background color to black
        capture_window_palette = QPalette()
        capture_window_palette.setColor(QPalette.Window, QColor(40, 40, 40))
        self.setPalette(capture_window_palette)

        # 設置視窗的特明度
        self.setWindowOpacity(0.7)

        # 创建一个水平布局管理器
        layout = QHBoxLayout()
  
        # setting  the geometry of window
        screen_geometry = QApplication.primaryScreen().geometry()

        # set x, y coordinate & width, height
        start_x_position = screen_geometry.left() + screen_geometry.width() // 4
        start_y_position = screen_geometry.top() + screen_geometry.height() // 2
        screen_width = screen_geometry.width() // 3
        screen_height = screen_geometry.height() // 4
        self.setGeometry(start_x_position, start_y_position, screen_width, screen_height)

        # plot the border of the window
        self.border_frame = QFrame(self)
        self.border_frame.setFrameShape(QFrame.Box)
        self.border_frame.setStyleSheet('QFrame { border: 3px solid red; border-radius: 10px;}')

        # 将边界线条添加到布局管理器
        layout.addWidget(self.border_frame)

        # 创建一个 widget 以容纳布局管理器
        container_widget = QWidget(self)
        container_widget.setLayout(layout)

        # 将 widget 设置为主窗口的中心部件
        self.setCentralWidget(container_widget)
        
        # 擷取倒數計時器
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.capture_screen)
        
        # 设置窗口标志，使其始终显示在最上面
        self.setWindowFlags(Qt.WindowStaysOnTopHint)


    def resizeEvent(self, event):
        # 在窗口大小变化时调整边界线条的位置
        super().resizeEvent(event)
        self.adjustBorderPosition()

    def adjustBorderPosition(self):
        # 获取窗口的新大小
        new_width = self.width()
        new_height = self.height()

        # 调整边界线条的位置
        self.border_frame.setGeometry(0, 0, new_width, new_height)

    def start_capture(self):
        self.previous_image = None  # clear the previous_image content before start capture
        match main_capturing_window.get_frequncy():
            case "高 (1 秒)":
                self.timer.start(1000)  # Capture every 1000 milliseconds (1 second)

            case "標準 (2 秒)":
                self.timer.start(2000)  # Capture every 2000 milliseconds (2 second)

            case "慢 (3 秒)":
                self.timer.start(3000)  # Capture every 3000 milliseconds (3 second)

            case "非常慢 (5 秒)":
                self.timer.start(5000)  # Capture every 5000 milliseconds (5 second)

        # 更改窗口透明度和边界线条
        self.setWindowOpacity(0)
        self.border_frame.hide()

        # 切换为无框窗口
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.show()

    def stop_capture(self):
        self.timer.stop()
        #self.force_update_timer.stop()
        QMessageBox.information(self, "Info", "Screen capture stopped.")

        # 恢复窗口透明度和边界线条
        self.setWindowOpacity(0.7)
        self.border_frame.show()

        # 切换回有框窗口
        self.setWindowFlags(Qt.Window)
        self.show()

    def capture_screen(self):
        global capture_start

        if self.isVisible():
            # Capture the screen content within the window's geometry
            screenshot = ImageGrab.grab(bbox=(self.geometry().x(), self.geometry().y(),
                                                self.geometry().x() + self.geometry().width(),
                                                self.geometry().y() + self.geometry().height()))
            
            # 在每次执行 OCR 之前比较图像相似度
            if self.is_similar_to_previous(screenshot):
                pass
            else:
                # Perform OCR using Google Cloud Vision on the screenshot
                self.perform_ocr(screenshot)


    def is_similar_to_previous(self, current_image):
        # 将当前图像与上一次捕获的图像进行相似度比较
        if self.previous_image is not None:
            # 將PIL圖像轉換為OpenCV格式
            previous_cv = cv2.cvtColor(np.array(self.previous_image), cv2.COLOR_RGB2BGR)
            current_cv = cv2.cvtColor(np.array(current_image), cv2.COLOR_RGB2BGR)

            # 將圖像轉換為灰度圖像
            previous_gray = cv2.cvtColor(previous_cv, cv2.COLOR_BGR2GRAY)
            current_gray = cv2.cvtColor(current_cv, cv2.COLOR_BGR2GRAY)
            """
            # 將灰度圖像進行二值化處理
            _, previous_binary = cv2.threshold(previous_gray, 128, 255, cv2.THRESH_BINARY)
            _, current_binary = cv2.threshold(current_gray, 128, 255, cv2.THRESH_BINARY)
            """

            # 使用OpenCV的相似度比较方法
            result = cv2.matchTemplate(current_gray, previous_gray, cv2.TM_CCOEFF_NORMED)

            # 获取最大匹配值
            max_similarity = np.max(result)

            if max_similarity == 1.0:
                check_result = cv2.matchTemplate(previous_cv, current_cv, cv2.TM_CCOEFF_NORMED)
                check_max_similarity = np.max(check_result)

                if check_max_similarity == 0.0:
                    return False # 与上一次图像不相似
                else:
                    return True # 与上一次图像相似
            else:
                # 设定相似度阈值，可以根据具体需求调整
                similarity_threshold = 0.95  # 这里设定一个普通的阈值

                if max_similarity >= similarity_threshold:
                    return True  # 与上一次图像相似
                else:
                    return False  # 与上一次图像不相似

    def closeEvent(self, event):
        # Stop the timer when the screen capture window is closed
        self.timer.stop()
        event.accept()
        self.closed.emit()  # Emit the signal when the window is closed

    def perform_ocr(self, screenshot):
        global client_vision, client_translate

        # 保存当前图像作为上一次捕获的图像
        self.previous_image = screenshot.copy()

        # 將PIL圖像轉換為OpenCV格式
        screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

        # 將圖像轉換為灰度圖像
        gray_image = cv2.cvtColor(screenshot_cv, cv2.COLOR_BGR2GRAY)

        # 將OpenCV格式的二值化圖像轉換為PIL格式
        binary_image_pil = Image.fromarray(gray_image)

        """
        # 將灰度圖像進行二值化處理
        _, binary_image = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY)
        cv2.imwrite("binary.png", binary_image)

        # 將OpenCV格式的二值化圖像轉換為PIL格式
        binary_image_pil = Image.fromarray(binary_image)

        # 保存二值化圖像到緩衝區
        binary_image_buffer = io.BytesIO()
        binary_image_pil.save(binary_image_buffer, format='PNG')
        screenshot_bytes = binary_image_buffer.getvalue()
        """

        # Save the screenshot to an in-memory buffer as a PNG image
        binary_image_buffer = io.BytesIO()
        binary_image_pil.save(binary_image_buffer, format='PNG')
        screenshot_bytes = binary_image_buffer.getvalue()

        """
        # Save the screenshot to an in-memory buffer as a PNG image
        image_buffer = io.BytesIO()
        screenshot.save(image_buffer, format='PNG')
        screenshot_bytes = image_buffer.getvalue()
        """


        # 使用Google Cloud Vision API進行文字辨識
        image = vision_v1.Image(content=screenshot_bytes)
        response = client_vision.text_detection(image=image)
        texts = response.text_annotations

        # 提取辨識到的文字
        if texts:
            detected_text = texts[0].description

            # 设置OCR识别文本
            main_capturing_window.ocr_text_label.setText(detected_text)
 
            # 將辨識的文字按行分割
            lines = detected_text.replace("\n", "")

            # Google 翻譯
            target_language = "zh-TW"  # 將此替換為你想要的目標語言代碼（例如：英文 --> en, 繁體中文 --> zh-TW）
            translated_lines = client_translate.translate(lines, target_language=target_language)

            # Unescape HTML entities
            unescape_translated_text = html.unescape(translated_lines["translatedText"])

            # 將翻譯後的行重新組合成一個帶有換行的字符串
            translated_text_with_newlines = unescape_translated_text.replace("。", "。\n").replace('？', '？\n').replace('！', '！\n')  # 以句點和問號為換行分界點
            main_capturing_window.translation_text_label.setText(translated_text_with_newlines)
            #main_capturing_window.translation_text_label.setText(unescape_translated_text)  # 完全不以句點和問號為換行分界點
            
        else:
            pass


if __name__ == "__main__":

    # read config file class
    config_handler = ConfigHandler()
    config_handler.read_config_file()

    # create pyside6 app
    App = QApplication(sys.argv)
    
    # Create the screen capture window and the main capturing control window
    main_capturing_window = MainMenuWindow(config_handler)

    # Show the windows
    main_capturing_window.show()
    
    # start the app
    sys.exit(App.exec())
  