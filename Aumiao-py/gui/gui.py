# ruff: noqa: {code}
import sys  # noqa: I001
import ctypes
import numpy as np

from PyQt5.QtWidgets import *  # noqa: F403
from PyQt5.QtGui import *  # noqa: F403
from PyQt5.QtCore import *  # noqa: F403
from src import *  # noqa: F403

from scipy.ndimage import convolve

# 高斯核（5x5）
gaussian_kernel = np.array([
	[0.003, 0.013, 0.022, 0.013, 0.003],
	[0.013, 0.059, 0.097, 0.059, 0.013],
	[0.022, 0.097, 0.159, 0.097, 0.022],
	[0.013, 0.059, 0.097, 0.059, 0.013],
	[0.003, 0.013, 0.022, 0.013, 0.003],
])


def apply_gaussian_blur(image: QImage):
	"""这个暂时不用"""
	# 将 QImage 转换为 NumPy 数组
	width = image.width()
	height = image.height()
	image_data = image.convertToFormat(QImage.Format_RGBA8888)
	buffer = image_data.bits().asstring(image_data.byteCount())
	# buffer = image.bits().asstring(image.byteCount())
	# buffer : PyQt5.sip.voidptr = image_data.constBits() # type: ignore
	# buffer.setsize(height * width * 4)
	img_array = np.frombuffer(buffer, dtype=np.uint8).reshape(image.height(), image.width(), 4)
	# img_array = np.frombuffer(buffer, dtype=np.uint8).reshape((height, width, 4)) # type: ignore

	# 分离颜色通道
	red = img_array[:, :, 0]
	green = img_array[:, :, 1]
	blue = img_array[:, :, 2]

	# 应用高斯核卷积
	blurred_red = convolve(red, gaussian_kernel, mode="constant", cval=0.0)
	blurred_green = convolve(green, gaussian_kernel, mode="constant", cval=0.0)
	blurred_blue = convolve(blue, gaussian_kernel, mode="constant", cval=0.0)

	# 合并通道
	blurred_red = blurred_red.astype(np.uint8)
	blurred_green = blurred_green.astype(np.uint8)
	blurred_blue = blurred_blue.astype(np.uint8)
	img_array[:, :, 0] = blurred_red
	img_array[:, :, 1] = blurred_green
	img_array[:, :, 2] = blurred_blue

	# 创建新的 QImage
	result_image = QImage(img_array.data, width, height, width * 4, QImage.Format_RGBA8888)
	return result_image


def apply_gaussian_blur_manual(image: QImage):
	width = image.width()
	height = image.height()
	new_image = QImage(width, height, QImage.Format_RGBA8888)

	for x in range(width):
		for y in range(height):
			total_red = 0
			total_green = 0
			total_blue = 0
			count = 0

			for dx in range(-2, 3):
				for dy in range(-2, 3):
					nx = x + dx
					ny = y + dy

					if 0 <= nx < width and 0 <= ny < height:
						color = image.pixelColor(nx, ny)
						weight = gaussian_kernel[dx + 2][dy + 2]
						total_red += color.red() * weight
						total_green += color.green() * weight
						total_blue += color.blue() * weight
						count += weight  # 累加权重

			avg_red = round(total_red / count)
			avg_green = round(total_green / count)
			avg_blue = round(total_blue / count)

			new_image.setPixelColor(x, y, QColor(avg_red, avg_green, avg_blue))

	return new_image


class MainWindow(QMainWindow):  # noqa: F405
	def update(self) -> None:
		"""更新"""
		self.paintBackground()

	def __init__(self: QWidget, parent=None) -> None:
		super().__init__(parent)

		self.setGeometry(100, 100, 400, 300)
		# 子窗口内容
		central_widget = QWidget()
		layout = QVBoxLayout(central_widget)
		self.setCentralWidget(central_widget)

		# 启用模糊效果
		# hwnd = self.winId()  # 获取窗口句柄
		# self.enable_gaussian_blur(hwnd)
		self.backgroundColor = QColor(255, 255, 255, 0)  # 设置背景颜色为透明
		self.background_image = None

		self.isLogin: bool = False

		self.setWindowTitle("毛毡工具")
		self.setGeometry(100, 100, 400, 300)

		self.layout: QVBoxLayout = QVBoxLayout()

		self.login_button: QPushButton = QPushButton("登录")  # noqa: F405
		self.login_button.clicked.connect(self.login)
		self.layout.addWidget(self.login_button)

		self.clear_comments_button: QPushButton = QPushButton("清除评论")  # noqa: F405
		self.clear_comments_button.clicked.connect(self.clear_comments)
		self.layout.addWidget(self.clear_comments_button)

		self.clear_red_point_button: QPushButton = QPushButton("清除邮箱红点")  # noqa: F405
		self.clear_red_point_button.clicked.connect(self.clear_red_point)
		self.layout.addWidget(self.clear_red_point_button)

		self.reply_work_button: QPushButton = QPushButton("自动回复")  # noqa: F405
		self.reply_work_button.clicked.connect(self.reply_work)
		self.layout.addWidget(self.reply_work_button)

		self.logout_button: QPushButton = QPushButton("登出")  # noqa: F405
		self.logout_button.clicked.connect(self.logout)
		self.layout.addWidget(self.logout_button)

		self.central_widget = QWidget()  # noqa: F405
		self.central_widget.setLayout(self.layout)
		self.setCentralWidget(self.central_widget)

		self.set_button_disabled(self.isLogin)

		# self.central_widget : QLabel = QLabel(self)

		# 创建一个定时器并连接到update方法
		# self.timer = QTimer()
		# self.timer.timeout.connect(self.update)
		# self.timer.start(1000)  # 每秒更新一次

	def paintBackground(self):
		"""暂时不用"""
		painter = QPainter(self)
		screen = QApplication.primaryScreen()
		self.background_image = screen.grabWindow(0).copy(self.x(), self.y(), self.width(), self.height())  # .scaled(self.width(), self.height())

		# 绘制背景图像
		painter.drawPixmap(0, 0, self.background_image)

		# 应用高斯模糊
		image = self.background_image.toImage()

		for x in range(image.width()):
			for y in range(image.height()):
				total_red = 0
				total_green = 0
				total_blue = 0
				count = 0
				for i in range(-1, 2):
					for j in range(-1, 2):
						if 0 <= x + i < image.width() and 0 <= y + j < image.height():
							color = image.pixelColor(x + i, y + j)
							total_red += color.red()
							total_green += color.green()
							total_blue += color.blue()
							count += 1
				avg_red = total_red // count
				avg_green = total_green // count
				avg_blue = total_blue // count
				image.setPixelColor(x, y, QColor(avg_red, avg_green, avg_blue))

		self.background_image.convertFromImage(image)

		# 绘制模糊后的图像
		painter.drawPixmap(0, 0, self.background_image)

	def enable_gaussian_blur(self, hwnd):
		# 创建 Direct2D 高斯模糊效果
		d2d_factory = ctypes.windll.d2d1.D2D1CreateFactory(
			ctypes.c_uint(0),  # D2D1_FACTORY_TYPE_SINGLE_THREADED
			ctypes.c_void_p(),  # CLSID_D2D1Factory
		)

		d2d_context = ctypes.windll.d2d1.D2D1CreateDeviceContext(
			ctypes.c_void_p(),  # ID2D1Device
			ctypes.c_void_p(),  # ID2D1DeviceContext
		)

		gaussian_blur_effect = ctypes.windll.d2d1.D2D1CreateEffect(
			ctypes.c_void_p(),  # ID2D1EffectFactory
			ctypes.c_void_p(),  # CLSID_D2D1GaussianBlur
		)

		# 设置高斯模糊参数
		ctypes.windll.d2d1.ID2D1Effect_SetValue(
			gaussian_blur_effect,
			ctypes.c_int(0),  # D2D1_GAUSSIANBLUR_PROP_STANDARD_DEVIATION
			ctypes.c_float(3.0),  # 标准差
		)

		# 应用高斯模糊效果
		ctypes.windll.d2d1.ID2D1DeviceContext_SetEffect(
			d2d_context,
			gaussian_blur_effect,
			ctypes.c_void_p(),  # ID2D1Image
		)

		# 释放资源
		ctypes.windll.d2d1.ID2D1Effect_Release(gaussian_blur_effect)
		ctypes.windll.d2d1.ID2D1DeviceContext_Release(d2d_context)
		ctypes.windll.d2d1.ID2D1Factory_Release(d2d_factory)

	def set_button_disabled(self, is_disabled: bool) -> None:
		"""设置按钮是否可用"""
		self.login_button.setEnabled(not is_disabled)
		self.clear_comments_button.setEnabled(is_disabled)
		self.clear_red_point_button.setEnabled(is_disabled)
		self.reply_work_button.setEnabled(is_disabled)
		self.logout_button.setEnabled(is_disabled)

	def login(self) -> None:
		"""登录"""
		identity, ok1 = QInputDialog.getText(self, "登录", "请输入用户名:")  # noqa: F405
		if ok1 and identity:
			password, ok2 = QInputDialog.getText(self, "登录", "请输入密码:", QLineEdit.EchoMode.Password)  # noqa: F405
			if ok2 and password:
				try:
					community.Login().login_token(identity=identity, password=password)  # noqa: F405
					_data = user.Obtain().get_data_details()  # noqa: F405
					account_data_manager = data.DataManager()  # noqa: F405
					account_data_manager.update(
						{
							"ACCOUNT_DATA": {
								"identity": identity,
								"password": "******",
								"id": _data["id"],
								"nickname": _data["nickname"],
								"create_time": _data["create_time"],
								"description": _data["description"],
								"author_level": _data["author_level"],
							},
						},
					)
					QMessageBox.information(self, "成功", "登录成功")  # noqa: F405
					self.isLogin = True
					self.set_button_disabled(self.isLogin)
				except Exception as e:
					QMessageBox.critical(self, "错误", f"登录失败: {e}")  # noqa: F405

	def clear_comments(self) -> None:
		"""清除评论"""
		source, ok = QInputDialog.getItem(self, "清除评论", "请输入来源类型:", ["work", "post"], 0, False)  # noqa: F405, FBT003
		if ok and source:
			action_type, ok = QInputDialog.getItem(self, "清除评论", "请输入操作类型:", ["ads", "duplicates", "blacklist"], 0, False)  # noqa: F405, FBT003
			if ok and action_type:
				try:
					client.Motion().clear_comments(source=source, action_type=action_type)  # type: ignore  # noqa: F405, PGH003
					QMessageBox.information(self, "成功", "评论清除成功")  # noqa: F405
				except Exception as e:
					QMessageBox.critical(self, "错误", f"清除评论失败: {e}")  # noqa: F405

	def clear_red_point(self) -> None:
		"""清除邮箱红点"""
		method, ok = QInputDialog.getItem(self, "清除邮箱红点", "请输入方法:", ["nemo", "web"], 0, False)  # noqa: F405
		if ok and method:
			try:
				client.Motion().clear_red_point(method=method)  # type: ignore  # noqa: F405, PGH003
				QMessageBox.information(self, "成功", "邮箱红点清除成功")  # noqa: F405
			except Exception as e:
				QMessageBox.critical(self, "错误", f"清除邮箱红点失败: {e}")  # noqa: F405

	def reply_work(self) -> None:
		"""自动回复"""
		try:
			client.Motion().reply_work()  # noqa: F405
			QMessageBox.information(self, "成功", "自动回复成功")  # noqa: F405
		except Exception as e:
			QMessageBox.critical(self, "错误", f"自动回复失败: {e}")  # noqa: F405

	def logout(self) -> None:
		"""登出"""
		method, ok = QInputDialog.getItem(self, "登出", "请输入方法:", ["web"], 0, False)  # noqa: F405, FBT003
		if ok and method:
			try:
				community.Login().logout(method=method)  # type: ignore # noqa: F405
				QMessageBox.information(self, "成功", "登出成功")  # noqa: F405
				self.isLogin = False
				self.set_button_disabled(self.isLogin)
			except Exception as e:
				QMessageBox.critical(self, "错误", f"登出失败: {e}")  # noqa: F405


def mainWindows() -> None:
	app = QApplication(sys.argv)  # noqa: F405
	window = MainWindow()
	window.show()
	sys.exit(app.exec())


if __name__ == "__main__":
	mainWindows()
