import sys
from collections.abc import Callable
from typing import ParamSpec, TypeVar, overload

# 假设的模块导入(根据实际项目结构调整)
from src import client, community, data, user

T = TypeVar("T")  # 泛型类型变量
P = ParamSpec("P")  # 参数规格变量


class ColorConfig:
	"""颜色配置管理"""

	COMMENT = "\033[38;5;245m"  # 中灰色 - 辅助说明
	ERROR = "\033[38;5;203m"  # 浅红色 - 错误提示
	MENU_ITEM = "\033[38;5;183m"  # 薰衣草紫 - 菜单项
	MENU_TITLE = "\033[38;5;80m"  # 青绿色 - 菜单标题
	PROMPT = "\033[38;5;75m"  # 淡蓝色 - 输入提示
	RESET = "\033[0m"  # 重置样式
	STATUS = "\033[38;5;228m"  # 浅黄色 - 状态信息
	SUCCESS = "\033[38;5;114m"  # 淡绿色 - 成功提示
	SEPARATOR = f"{PROMPT}══════════════════════════════════════════════════════════{RESET}"


class InputValidator:
	"""输入验证工具类"""

	@staticmethod
	def validate_choice(input_str: str, valid_choices: list[str]) -> bool:
		return input_str in valid_choices

	@staticmethod
	def validate_number(input_str: str, min_val: int | None = None, max_val: int | None = None) -> bool:
		"""验证数字输入"""
		try:
			num = int(input_str)
			if min_val is not None and num < min_val:
				return False
			if max_val is not None and num > max_val:
				return False
			return True
		except ValueError:
			return False

	@overload
	@staticmethod
	def get_valid_input(
		prompt: str,
		input_type: Callable[[str], T] = str,
		validation: None = None,
	) -> T: ...

	@overload
	@staticmethod
	def get_valid_input(
		prompt: str,
		input_type: Callable[[str], T],
		validation: Callable[P, bool],
		*args: P.args,
		**kwargs: P.kwargs,
	) -> T: ...

	@staticmethod
	def get_valid_input(
		prompt: str,
		input_type: Callable[[str], T] = str,
		validation: Callable[P, bool] | None = None,
		*args: P.args,
		**kwargs: P.kwargs,
	) -> T:
		"""获取有效用户输入

		Args:
		    prompt: 输入提示信息
		    input_type: 输入类型转换函数,如str, int, float等
		    validation: 验证函数,可以返回bool或Literal[True]
		    **kwargs: 传递给验证函数的额外参数

		Returns:
		    转换并验证后的输入值,类型与input_type的返回类型一致
		"""
		while True:
			try:
				user_input = input(f"{ColorConfig.PROMPT}↳ {prompt}{ColorConfig.RESET}").strip()
				converted_input = input_type(user_input)  # 类型: T

				if validation and not validation(converted_input, **kwargs):
					raise ValueError

				return converted_input  # 返回类型: T

			except ValueError:
				print(f"{ColorConfig.ERROR}无效输入,请重新输入{ColorConfig.RESET}")


class MenuSystem:
	"""菜单系统核心类"""

	def __init__(self) -> None:
		self.validator = InputValidator()
		self._setup_menus()

	def _setup_menus(self) -> None:
		"""初始化菜单配置"""
		self.main_menu = {
			"1": ("用户登录", self._handle_login),
			"2": ("清除评论", self._handle_clear_comments),
			"3": ("清除红点提醒", self._handle_clear_red_point),
			"4": ("自动回复", self._handle_auto_reply),
			"5": ("账户登出", self._handle_logout),
			"6": ("处理举报", self._handle_report),
			"7": ("状态查询", self._handle_status_check),
			"8": ("下载小说", self._handle_download_fiction),
			"9": ("退出系统", self._handle_exit),
			"1106": ("隐藏功能", self._handle_hidden_features),
		}

		self.hidden_menu = {"1": ("自动点赞", self._handle_auto_like), "2": ("学生管理", self._handle_student_management)}

	@staticmethod
	def print_header(text: str) -> None:
		"""打印带样式的标题"""
		print(f"\n{ColorConfig.SEPARATOR}")
		print(f"{ColorConfig.MENU_TITLE}{text:^60}{ColorConfig.RESET}")
		print(f"{ColorConfig.SEPARATOR}\n")

	def display_menu(self, menu_config: dict[str, tuple[str, Callable]], title: str = "") -> None:
		"""显示菜单界面"""
		if title:
			self.print_header(title)

		for key, (text, _) in menu_config.items():
			color = ColorConfig.MENU_ITEM if key != "9" else ColorConfig.RESET
			print(f"{color}{key}. {text}{ColorConfig.RESET}")

	def clear_screen(self) -> None:
		"""清屏操作"""
		print("\033c", end="")

	def pause(self) -> None:
		"""暂停等待用户确认"""
		input(f"\n{ColorConfig.PROMPT}⏎ 按回车键继续...{ColorConfig.RESET}")

	# ========== 主菜单功能处理方法 ==========
	def _handle_login(self) -> None:
		"""处理用户登录"""
		try:
			self.print_header("用户登录")
			identity = self.validator.get_valid_input("请输入用户名: ")
			password = self.validator.get_valid_input("请输入密码: ")

			# 调用登录接口
			community.Login().login_token(identity=identity, password=password)
			user_data = user.Obtain().get_data_details()

			# 更新账户数据
			account_data_manager = data.DataManager()
			account_data_manager.update(
				{
					"ACCOUNT_DATA": {
						"identity": identity,
						"password": "******",
						"id": user_data["id"],
						"nickname": user_data["nickname"],
						"create_time": user_data["create_time"],
						"description": user_data["description"],
						"author_level": user_data["author_level"],
					},
				},
			)
			print(f"{ColorConfig.SUCCESS}登录成功!欢迎 {user_data['nickname']}{ColorConfig.RESET}")

		except Exception as e:
			print(f"{ColorConfig.ERROR}登录失败: {e}{ColorConfig.RESET}")

	def _handle_clear_comments(self) -> None:
		"""处理清除评论"""
		try:
			self.print_header("清除评论")
			source = self.validator.get_valid_input("来源类型 (work/post): ", validation=self.validator.validate_choice, valid_choices=["work", "post"])
			action_type = self.validator.get_valid_input(
				input_type=str,
				prompt="操作类型 (ads/duplicates/blacklist): ",
				validation=self.validator.validate_choice,
				valid_choices=["ads", "duplicates", "blacklist"],
			)

			client.Motion().clear_comments(source=source, action_type=action_type)
			print(f"{ColorConfig.SUCCESS}已成功清除 {source} 的 {action_type} 评论{ColorConfig.RESET}")

		except Exception as e:
			print(f"{ColorConfig.ERROR}清除评论失败: {e}{ColorConfig.RESET}")

	def _handle_clear_red_point(self) -> None:
		"""处理清除红点"""
		try:
			self.print_header("清除红点提醒")
			method = self.validator.get_valid_input("方法 (nemo/web): ", validation=self.validator.validate_choice, valid_choices=["nemo", "web"])

			client.Motion().clear_red_point(method=method)
			print(f"{ColorConfig.SUCCESS}已成功清除 {method} 红点提醒{ColorConfig.RESET}")

		except Exception as e:
			print(f"{ColorConfig.ERROR}清除红点失败: {e}{ColorConfig.RESET}")

	def _handle_auto_reply(self) -> None:
		"""处理自动回复"""
		try:
			self.print_header("自动回复")
			client.Motion().reply_work()
			print(f"{ColorConfig.SUCCESS}已成功执行自动回复{ColorConfig.RESET}")
		except Exception as e:
			print(f"{ColorConfig.ERROR}自动回复失败: {e}{ColorConfig.RESET}")

	def _handle_logout(self) -> None:
		"""处理账户登出"""
		try:
			self.print_header("账户登出")
			method = self.validator.get_valid_input("方法 (web): ", validation=self.validator.validate_choice, valid_choices=["web"])

			community.Login().logout(method=method)
			print(f"{ColorConfig.SUCCESS}已成功登出账户{ColorConfig.RESET}")

		except Exception as e:
			print(f"{ColorConfig.ERROR}登出失败: {e}{ColorConfig.RESET}")

	def _handle_report(self) -> None:
		"""处理举报"""
		try:
			self.print_header("处理举报")
			client.Motion().judgement_login()

			admin_id = self.validator.get_valid_input("管理员ID: ", input_type=int, validation=self.validator.validate_number, min_val=1)

			client.Motion().handle_report(admin_id=admin_id)
			print(f"{ColorConfig.SUCCESS}已成功处理举报{ColorConfig.RESET}")

		except Exception as e:
			print(f"{ColorConfig.ERROR}处理举报失败: {e}{ColorConfig.RESET}")

	def _handle_status_check(self) -> None:
		"""处理状态查询"""
		try:
			self.print_header("账户状态查询")
			status = client.Motion().get_account_status()
			print(f"{ColorConfig.STATUS}当前账户状态: {status}{ColorConfig.RESET}")
		except Exception as e:
			print(f"{ColorConfig.ERROR}获取账户状态失败: {e}{ColorConfig.RESET}")

	def _handle_download_fiction(self) -> None:
		"""处理小说下载"""
		try:
			self.print_header("下载小说")
			fiction_id = self.validator.get_valid_input("小说ID: ", input_type=int, validation=self.validator.validate_number, min_val=1)

			client.Motion().download_fiction(fiction_id=fiction_id)
			print(f"{ColorConfig.SUCCESS}小说下载完成{ColorConfig.RESET}")

		except Exception as e:
			print(f"{ColorConfig.ERROR}下载小说失败: {e}{ColorConfig.RESET}")

	def _handle_exit(self) -> None:
		"""处理程序退出"""
		print(f"\n{ColorConfig.SUCCESS}感谢使用,再见!{ColorConfig.RESET}")
		sys.exit(0)

	# ========== 隐藏功能处理方法 ==========
	def _handle_hidden_features(self) -> None:
		"""处理隐藏功能菜单"""
		self.print_header("隐藏功能")
		self.display_menu(self.hidden_menu)

		sub_choice = self.validator.get_valid_input("操作选择: ", validation=self.validator.validate_choice, valid_choices=list(self.hidden_menu.keys()))

		self.hidden_menu[sub_choice][1]()

	def _handle_auto_like(self) -> None:
		"""处理自动点赞"""
		try:
			self.print_header("自动点赞")
			user_id = self.validator.get_valid_input("训练师ID: ", input_type=int, validation=self.validator.validate_number, min_val=1)

			client.Motion().chiaroscuro_chronicles(user_id=user_id)
			print(f"{ColorConfig.SUCCESS}自动点赞操作完成{ColorConfig.RESET}")

		except Exception as e:
			print(f"{ColorConfig.ERROR}自动点赞失败: {e}{ColorConfig.RESET}")

	def _handle_student_management(self) -> None:
		"""处理学生管理"""
		try:
			self.print_header("学生管理")
			mode = self.validator.get_valid_input("模式 (delete/create): ", validation=self.validator.validate_choice, valid_choices=["delete", "create"])

			limit = self.validator.get_valid_input("数量: ", input_type=int, validation=self.validator.validate_number, min_val=1)

			client.Motion().batch_handle_account(method=mode, limit=limit)
			print(f"{ColorConfig.SUCCESS}已成功处理 {limit} 个学生账户{ColorConfig.RESET}")

		except Exception as e:
			print(f"{ColorConfig.ERROR}学生管理操作失败: {e}{ColorConfig.RESET}")


def enable_vt_mode() -> None:
	"""启用Windows VT模式"""
	if sys.platform == "win32":
		from ctypes import windll

		kernel32 = windll.kernel32
		kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)


def main() -> None:
	"""主程序入口"""
	enable_vt_mode()
	client.Index().index()  # 初始化客户端

	menu_system = MenuSystem()

	while True:
		menu_system.clear_screen()
		menu_system.display_menu(menu_system.main_menu, "主菜单")

		choice = menu_system.validator.get_valid_input("请输入操作编号: ", validation=menu_system.validator.validate_choice, valid_choices=list(menu_system.main_menu.keys()))

		# 执行对应功能
		menu_system.main_menu[choice][1]()
		menu_system.pause()


if __name__ == "__main__":
	try:
		main()
	except KeyboardInterrupt:
		print(f"\n{ColorConfig.ERROR}程序被用户中断{ColorConfig.RESET}")
	finally:
		input(f"\n{ColorConfig.PROMPT}⏎ 按回车键退出程序{ColorConfig.RESET}")
