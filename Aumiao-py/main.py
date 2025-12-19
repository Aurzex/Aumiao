import logging
import platform
import sys
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial, wraps
from pathlib import Path
from typing import Any, Literal, TypeVar, cast

from src import auth, user, whale
from src.core.base import Index
from src.core.compile import decompile_work
from src.core.deepser import CodeMaoTool
from src.core.process import FileProcessor, ReportAuthManager
from src.core.services import FileUploader, MillenniumEntanglement, Motion, Report
from src.utils import data, plugin, tool

# 常量定义
T = TypeVar("T")
AUI = "jkslnlkqrljojqlkrlkqqljpjqrkqs"  # cSpell:ignore jkslnlkqrljojqlkrlkqqljpjqrkqs
logger = logging.getLogger(__name__)


@dataclass
class AppConfig:
	"""应用配置类"""

	MAX_MENU_KEY_LENGTH: int = 2
	LOG_LEVEL: str = "ERROR"
	LOG_FORMAT: str = "%(asctime)s - %(levelname)s - %(message)s"  # cSpell:ignore levelname
	LOG_FILE: str = "app.log"
	# 菜单相关常量
	MENU_ITEMS: dict[str, tuple[str, bool, bool]] = None  # type: ignore  # noqa: PGH003

	def __post_init__(self) -> None:
		"""初始化菜单配置"""
		# 菜单配置: (名称, 需要登录, 是否可见)
		self.MENU_ITEMS = {
			"01": ("用户登录", False, True),
			"02": ("账户登出", True, True),
			"03": ("状态查询", True, True),
			"04": ("清除评论", True, True),
			"05": ("清除红点", True, True),
			"06": ("自动回复", True, True),
			"07": ("处理举报", True, True),
			"08": ("下载小说", False, True),
			"09": ("上传文件", True, True),
			"10": ("上传历史", False, True),
			"11": ("编译作品", False, True),
			"12": ("生成口令", True, True),
			"13": ("插件管理", False, True),
			"14": ("助手对话", True, True),
			"00": ("退出系统", False, True),
			"1106": ("隐藏功能", True, False),
		}


config = AppConfig()
printer = tool.Printer()


@dataclass
class MenuOption:
	"""菜单选项类"""

	name: str
	handler: Callable[[], None]
	require_auth: bool = False
	visible: bool = True


def setup_logging() -> None:
	"""配置日志系统 - 优化配置"""
	logging.basicConfig(
		filename=config.LOG_FILE,
		level=getattr(logging, config.LOG_LEVEL),
		format=config.LOG_FORMAT,
		encoding="utf-8",
	)
	# 可选:添加控制台日志输出
	console_handler = logging.StreamHandler()
	console_handler.setLevel(logging.ERROR)
	formatter = logging.Formatter(config.LOG_FORMAT)
	console_handler.setFormatter(formatter)
	logger = logging.getLogger()
	logger.addHandler(console_handler)


def enable_vt_mode() -> None:
	"""启用Windows虚拟终端模式"""
	if platform.system() == "Windows":
		from ctypes import windll  # noqa: PLC0415

		try:
			kernel32 = windll.kernel32
			kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
		except OSError:
			logger.exception("启用VT模式失败")
			print(printer.color_text("警告: 无法启用虚拟终端模式,颜色显示可能不正常", "ERROR"))


def handle_errors(func: Callable[..., Any]) -> Callable[..., Any]:
	"""统一错误处理装饰器 - 性能优化"""

	@wraps(func)
	def wrapper(*args: Any, **kwargs: Any) -> Any | None:
		try:
			return func(*args, **kwargs)
		except ValueError as ve:
			print(printer.color_text(f"输入错误: {ve}", "ERROR"))
		except Exception as e:
			logger.exception("%s 执行失败", func.__name__)
			print(printer.color_text(f"操作失败: {e}", "ERROR"))

	return wrapper


class AccountDataManager:
	"""账户数据管理类 - 性能优化"""

	def __init__(self) -> None:
		self._account_data: dict[str, dict] = {}
		self._token: str = ""
		self._is_logged_in = False

	@property
	def account_data(self) -> dict[str, dict]:
		return self._account_data

	@property
	def token(self) -> str:
		return self._token

	@token.setter
	def token(self, value: str) -> None:
		self._token = value

	@property
	def is_logged_in(self) -> bool:
		return self._is_logged_in

	def update(self, data: dict[str, dict]) -> None:
		"""更新账户数据 - 避免不必要的数据复制"""
		self._account_data = data
		self._is_logged_in = True

	def clear(self) -> None:
		"""清除账户数据 - 快速清空"""
		self._account_data.clear()
		self._token = ""
		self._is_logged_in = False

	def get_account_id(self) -> str | None:
		"""获取账户ID - 优化字典访问"""
		account_data = self._account_data.get("ACCOUNT_DATA", {})
		return account_data.get("id")


def print_account_info(account_data: dict) -> None:
	"""显示账户详细信息"""
	info = account_data.get("ACCOUNT_DATA", {})
	print(printer.color_text(f"登录成功! 欢迎 {info.get('nickname', '未知用户')}", "SUCCESS"))
	print(printer.color_text(f"用户ID: {info.get('id', 'N/A')}", "COMMENT"))
	print(printer.color_text(f"创作等级: {info.get('author_level', 'N/A')}", "COMMENT"))


@handle_errors
def login(account_data_manager: AccountDataManager) -> None:
	"""用户登录处理"""
	printer.print_header("用户登录")
	identity = printer.prompt_input("请输入用户名")
	password = printer.prompt_input("请输入密码")
	response = auth.AuthManager().login(identity=identity, password=password)
	data_ = user.UserDataFetcher().fetch_account_details()
	account_data = {
		"ACCOUNT_DATA": {
			"identity": identity,
			"password": "******",
			"id": data_["id"],
			"nickname": data_["nickname"],
			"create_time": data_["create_time"],
			"description": data_["description"],
			"author_level": data_["author_level"],
		},
	}
	account_data_manager.update(account_data)
	data.DataManager().update(account_data)
	account_data_manager.token = response["data"]["auth"]["token"]
	print_account_info(account_data)


def require_login(func: Callable[..., Any]) -> Callable[..., Any]:
	"""登录检查装饰器"""

	@wraps(func)
	def wrapper(account_data_manager: AccountDataManager, *args: Any, **kwargs: Any) -> Any | None:
		if not account_data_manager.is_logged_in:
			print(printer.color_text("请先登录!", "ERROR"))
			return None
		return func(account_data_manager, *args, **kwargs)

	return wrapper


def get_positive_int_input(prompt: str, max_value: int | None = None) -> int:
	"""获取正整数输入 - 复用现有的 get_valid_input"""
	return printer.get_valid_input(prompt=prompt, cast_type=int, validator=lambda x: x > 0 and (max_value is None or x <= max_value))


def get_enum_input(prompt: str, valid_options: set[str]) -> str:
	"""获取枚举值输入 - 复用现有的 get_valid_input"""
	return printer.get_valid_input(prompt, valid_options=valid_options)


@handle_errors
@require_login
def clear_comments(_account_data_manager: AccountDataManager) -> None:
	"""清除评论 - 优化验证逻辑"""
	printer.print_header("清除评论")
	source = get_enum_input("请输入来源类型", {"work", "post"})
	action_type = get_enum_input("请输入操作类型", {"ads", "duplicates", "blacklist"})
	source = cast("Literal['work', 'post']", source)
	action_type = cast("Literal['ads', 'duplicates', 'blacklist']", action_type)
	Motion().clear_comments(source=source, action_type=action_type)
	print(printer.color_text(f"已成功清除 {source} 的 {action_type} 评论", "SUCCESS"))


@handle_errors
@require_login
def clear_red_point(_account_data_manager: AccountDataManager) -> None:
	"""清除红点提醒"""
	printer.print_header("清除红点提醒")
	method = get_enum_input("请输入方法", {"nemo", "web"})
	method = cast("Literal['nemo', 'web']", method)
	Motion().clear_red_point(method=method)
	print(printer.color_text(f"已成功清除 {method} 红点提醒", "SUCCESS"))


@handle_errors
@require_login
def reply_work(_account_data_manager: AccountDataManager) -> None:
	"""自动回复作品"""
	printer.print_header("自动回复")
	Motion().execute_auto_reply_work()
	print(printer.color_text("已成功执行自动回复", "SUCCESS"))


@handle_errors
def handle_report(_account_data_manager: AccountDataManager) -> None:
	"""处理举报"""
	printer.print_header("处理举报")
	ReportAuthManager().execute_admin_login()
	judgment_data = whale.AuthManager().fetch_user_dashboard_data()
	print(printer.color_text(f"登录成功! 欢迎 {judgment_data['admin']['username']}", "SUCCESS"))
	admin_id: int = judgment_data["admin"]["id"]
	Report().execute_report_handle(admin_id=admin_id)
	print(printer.color_text("已成功处理举报", "SUCCESS"))


@handle_errors
@require_login
def check_account_status(_account_data_manager: AccountDataManager) -> None:
	"""检查账户状态"""
	printer.print_header("账户状态查询")
	status = Motion().get_account_status()
	print(printer.color_text(f"当前账户状态: {status}", "STATUS"))


@handle_errors
def download_fiction(_account_data_manager: AccountDataManager) -> None:
	"""下载小说"""
	printer.print_header("下载小说")
	fiction_id = get_positive_int_input("请输入小说ID")
	Motion().execute_download_fiction(fiction_id=fiction_id)
	print(printer.color_text("小说下载完成", "SUCCESS"))


@handle_errors
@require_login
def generate_nemo_code(_account_data_manager: AccountDataManager) -> None:
	"""生成喵口令"""
	printer.print_header("生成喵口令")
	work_id = get_positive_int_input("请输入作品编号")
	Motion().generate_nemo_code(work_id=work_id)
	print(printer.color_text("生成完成", "SUCCESS"))


@handle_errors
def print_history(_account_data_manager: AccountDataManager) -> None:
	"""上传历史"""
	printer.print_header("上传历史")
	FileProcessor().print_upload_history()
	print(printer.color_text("查看完成", "SUCCESS"))


@handle_errors
@require_login
def upload_files(_account_data_manager: AccountDataManager) -> None:
	"""上传文件"""
	printer.print_header("上传文件")
	print(printer.color_text("上传方法说明: \n", "INFO"))
	print(printer.color_text("编程猫于10月22日对对象存储进行限制", "INFO"))
	print(printer.color_text("关闭了文件上传接口, 并更换域名*.codemao.cn -> *.bcmcdn.com", "INFO"))  # cSpell:ignore bcmcdn
	print(printer.color_text("因此现在只能使用codemao选项, 然而保着收集api的原则, 过时的api不会删除, 只标记为弃用\n", "INFO"))
	print(printer.color_text("- codemao: 上传到bcmcdn域名", "PROMPT"))  # cSpell:ignore bcmcdn
	print(printer.color_text("- codegame: 上传到static域名", "COMMENT"))
	print(printer.color_text("- pgaot: 上传到static域名", "COMMENT"))
	method = get_enum_input("请输入方法", {"pgaot", "codemao", "codegame"})
	file_path_str = printer.prompt_input("请输入文件或文件夹路径")
	file_path = Path(file_path_str.strip())
	if file_path.exists():
		file_path = file_path.resolve()
		print(printer.color_text(f"使用路径: {file_path}", "COMMENT"))
	else:
		print(printer.color_text("文件或路径不存在", "ERROR"))
		return
	method = cast("Literal['pgaot', 'codemao','codegame']", method)
	url = FileUploader().upload_file(method=method, file_path=file_path)
	print(f"保存地址: {url}")
	print(printer.color_text("文件上传成功", "SUCCESS"))


@handle_errors
@require_login
def logout(account_data_manager: AccountDataManager) -> None:
	"""用户登出"""
	printer.print_header("账户登出")
	method = get_enum_input("请输入方法", {"web"})
	method = cast("Literal['web']", method)
	auth.AuthManager().execute_logout(method)
	account_data_manager.clear()
	print(printer.color_text("已成功登出账户", "SUCCESS"))


@handle_errors
def plugin_manager(_account_data_manager: AccountDataManager) -> None:
	"""插件管理"""
	printer.print_header("插件管理")
	plugin_manager = plugin.LazyPluginManager(data.PathConfig.PLUGIN_PATH)
	console = plugin.PluginConsole(plugin_manager)
	console.run()


@handle_errors
def decompile_works(_account_data_manager: AccountDataManager) -> None:
	"""编译作品"""
	printer.print_header("编译作品")
	work_id = get_positive_int_input("请输入作品ID")
	output_path = decompile_work(work_id)
	print(printer.color_text(f"✓ 反编译完成: {output_path}", "SUCCESS"))


@handle_errors
@require_login
def interactive_chat(account_data_manager: AccountDataManager) -> None:
	"""AI聊天"""
	printer.print_header("AI聊天")
	token = account_data_manager.token
	CodeMaoTool().interactive_chat(token)


@handle_errors
@require_login
def handle_hidden_features(_account_data_manager: AccountDataManager) -> None:
	"""处理隐藏功能.仅管理员可访问"""
	encrypted_result = tool.Encrypt().decrypt(AUI)
	decrypted_str = "".join(str(item) for item in encrypted_result) if isinstance(encrypted_result, list) else str(encrypted_result)
	user_input = printer.prompt_input("请输入验证码")
	if user_input not in decrypted_str:
		return
	printer.print_header("隐藏功能")
	print(printer.color_text("1. 自动点赞", "COMMENT"))
	print(printer.color_text("2. 学生管理", "COMMENT"))
	print(printer.color_text("3. 账号提权", "COMMENT"))
	sub_choice = get_enum_input("操作选择", {"1", "2", "3"})
	if sub_choice == "1":
		user_id = get_positive_int_input("训练师ID")
		MillenniumEntanglement().batch_like_content(user_id=user_id, content_type="work")
		print(printer.color_text("自动点赞完成", "SUCCESS"))
	elif sub_choice == "2":
		mode = get_enum_input("模式", {"delete", "create", "token"})
		mode = cast("Literal['delete', 'create','token']", mode)
		limit = get_positive_int_input("数量", max_value=100)
		MillenniumEntanglement().manage_edu_accounts(action_type=mode, limit=limit)
		print(printer.color_text("学生管理完成", "SUCCESS"))
	elif sub_choice == "3":
		real_name = printer.prompt_input("输入姓名")
		MillenniumEntanglement().upgrade_to_teacher(real_name=real_name)
		print(printer.color_text("账号提权完成", "SUCCESS"))


def exit_program(_account_data_manager: AccountDataManager) -> None:
	"""退出程序"""
	print(printer.color_text("感谢使用, 再见!", "SUCCESS"))
	sys.exit(0)


class MenuSystem:
	"""菜单系统管理类"""

	def __init__(self, account_data_manager: AccountDataManager) -> None:
		self.account_data_manager = account_data_manager
		self.menu_options = self._build_menu_options()

	def _build_menu_options(self) -> dict[str, MenuOption]:
		"""动态构建菜单选项"""
		handlers = {
			"01": login,
			"02": logout,
			"03": check_account_status,
			"04": clear_comments,
			"05": clear_red_point,
			"06": reply_work,
			"07": handle_report,
			"08": download_fiction,
			"09": upload_files,
			"10": print_history,
			"11": decompile_works,
			"12": generate_nemo_code,
			"13": plugin_manager,
			"14": interactive_chat,
			"00": exit_program,
			"1106": handle_hidden_features,
		}
		menu_options = {}
		for key, (name, require_auth, visible) in config.MENU_ITEMS.items():
			if key in handlers:
				menu_options[key] = MenuOption(name=name, handler=partial(handlers[key], self.account_data_manager), require_auth=require_auth, visible=visible)
		return menu_options

	def display(self) -> None:
		"""显示菜单 - 高性能版本"""
		printer.print_header("主菜单")
		# 预计算格式字符串减少重复计算
		menu_format = f"{{:>{config.MAX_MENU_KEY_LENGTH}}}. {{}}"
		for key, option in self.menu_options.items():
			if not option.visible:
				continue
			# 格式化菜单文本
			menu_text = menu_format.format(key, option.name)
			# 选择颜色
			color_type = "COMMENT" if (option.require_auth and not self.account_data_manager.is_logged_in) else "MENU_ITEM"
			print(printer.color_text(menu_text, color_type))

	def handle_choice(self, choice: str) -> bool:
		"""处理菜单选择,返回是否继续运行"""
		if choice not in self.menu_options:
			print(printer.color_text("无效的输入, 请重新选择", "ERROR"))
			return True
		option = self.menu_options[choice]
		# 登录检查
		if option.require_auth and not self.account_data_manager.is_logged_in:
			print(printer.color_text("该操作需要登录!", "ERROR"))
			if printer.prompt_input("是否立即登录? (y/n)").lower() == "y":
				login(self.account_data_manager)
			return True
		# 执行处理器
		option.handler()
		return choice != "00"  # 选择退出时返回False

	def get_valid_choices(self) -> set[str]:
		"""获取有效的菜单选项"""
		return {key for key, option in self.menu_options.items() if option.visible}


def pause_for_continue() -> None:
	"""暂停等待继续"""
	input(f"\n{printer.color_text('⏎ 按回车键继续...', 'PROMPT')}")


def handle_keyboard_interrupt() -> None:
	"""处理键盘中断"""
	print(f"\n{printer.color_text('程序被用户中断', 'ERROR')}")


def handle_unexpected_error() -> None:
	"""处理未预期错误"""
	logger.error("程序发生未处理异常")
	print(f"\n{printer.color_text('程序发生错误', 'ERROR')}")


def prompt_exit() -> None:
	"""提示退出"""
	input(f"\n{printer.color_text('⏎ 按回车键退出程序', 'PROMPT')}")


def get_menu_choice(_menu_system: MenuSystem) -> str:
	"""获取菜单选择 - 优化输入处理"""
	return printer.prompt_input("请输入操作编号")


def run_main_loop(menu_system: MenuSystem) -> None:
	"""运行主循环"""
	while True:
		menu_system.display()
		choice = get_menu_choice(menu_system)
		if not menu_system.handle_choice(choice):
			break
		pause_for_continue()


def main() -> None:
	"""主程序入口 - 优化流程控制"""
	enable_vt_mode()
	setup_logging()
	Index().index()
	account_data_manager = AccountDataManager()
	menu_system = MenuSystem(account_data_manager)
	try:
		run_main_loop(menu_system)
	except KeyboardInterrupt:
		handle_keyboard_interrupt()
	except Exception:
		handle_unexpected_error()
	finally:
		prompt_exit()


if __name__ == "__main__":
	main()
