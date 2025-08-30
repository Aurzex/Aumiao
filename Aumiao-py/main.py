import logging
import platform
import sys
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Literal, TypeVar, cast

from src import client, community, user, whale
from src.utils import data, plugin, tool

# 常量定义
MAX_MENU_KEY_LENGTH = 2
T = TypeVar("T")
AUI = "jkslnlkqrljojqlkrlkqqljpjqrkqs"  # cSpell:ignore jkslnlkqrljojqlkrlkqqljpjqrkqs
logger = logging.getLogger(__name__)
logging.basicConfig(
	filename="app.log",
	level=logging.ERROR,
	format="%(asctime)s - %(levelname)s - %(message)s",  # cSpell:ignore levelname
)
printer = tool.Printer()


@dataclass
class MenuOption:
	"""菜单选项类"""

	name: str
	handler: Callable[[], None]  # 更精确的类型注解
	require_auth: bool = False
	visible: bool = True  # 控制是否显示在菜单中


def enable_vt_mode() -> None:
	"""启用Windows虚拟终端模式"""
	if platform.system() == "Windows":
		# 基于系统, 判断是否需要引入ctypes库
		from ctypes import windll  # noqa: PLC0415

		try:
			kernel32 = windll.kernel32
			kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
		except OSError:
			logger.exception("启用VT模式失败")
			print(printer.color_text("警告: 无法启用虚拟终端模式,颜色显示可能不正常", "ERROR"))


def handle_errors(func: Callable) -> Callable:
	"""统一错误处理装饰器"""

	def wrapper(*args: ..., **kwargs: ...) -> object | None:
		try:
			return func(*args, **kwargs)
		except ValueError as ve:
			print(printer.color_text(f"输入错误: {ve}", "ERROR"))
		except Exception as e:
			logger.exception(f"{func.__name__} 执行失败")  # noqa: G004
			print(printer.color_text(f"操作失败: {e}", "ERROR"))

	return wrapper


class AccountDataManager:
	"""账户数据管理类"""

	def __init__(self) -> None:
		self.account_data: dict[str, dict] = {}
		self.is_logged_in = False

	def update(self, data: dict[str, dict]) -> None:
		"""更新账户数据"""
		self.account_data = data
		self.is_logged_in = True

	def clear(self) -> None:
		"""清除账户数据"""
		self.account_data = {}
		self.is_logged_in = False

	def get_account_id(self) -> str | None:
		"""获取账户ID"""
		return self.account_data.get("ACCOUNT_DATA", {}).get("id")


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
	community.AuthManager().authenticate_with_token(identity=identity, password=password)
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
	print_account_info(account_data)


# 修复装饰器类型标注,移除Any类型
def require_login(func: Callable[[AccountDataManager], None]) -> Callable[[AccountDataManager], None]:
	"""登录检查装饰器"""

	def wrapper(account_data_manager: AccountDataManager) -> None:
		if not account_data_manager.is_logged_in:
			print(printer.color_text("请先登录!", "ERROR"))
			return None
		return func(account_data_manager)

	return wrapper


@handle_errors
@require_login
def clear_comments(account_data_manager: AccountDataManager) -> None:  # noqa: ARG001
	"""清除评论"""
	printer.print_header("清除评论")
	source = printer.get_valid_input("请输入来源类型 (work/post)", {"work", "post"})
	action_type = printer.get_valid_input("请输入操作类型 (ads/duplicates/blacklist)", {"ads", "duplicates", "blacklist"})
	source = cast("Literal['work', 'post']", source)
	action_type = cast("Literal['ads', 'duplicates', 'blacklist']", action_type)
	client.Motion().clear_comments(source=source, action_type=action_type)
	print(printer.color_text(f"已成功清除 {source} 的 {action_type} 评论", "SUCCESS"))


@handle_errors
@require_login
def clear_red_point(account_data_manager: AccountDataManager) -> None:  # noqa: ARG001
	"""清除红点提醒"""
	printer.print_header("清除红点提醒")
	method = printer.get_valid_input("请输入方法 (nemo/web)", {"nemo", "web"})
	method = cast("Literal['nemo', 'web']", method)
	client.Motion().clear_red_point(method=method)
	print(printer.color_text(f"已成功清除 {method} 红点提醒", "SUCCESS"))


@handle_errors
@require_login
def reply_work(account_data_manager: AccountDataManager) -> None:  # noqa: ARG001
	"""自动回复作品"""
	printer.print_header("自动回复")
	client.Motion().execute_auto_reply_work()
	print(printer.color_text("已成功执行自动回复", "SUCCESS"))


@handle_errors
def handle_report(account_data_manager: AccountDataManager) -> None:  # noqa: ARG001
	"""处理举报"""
	printer.print_header("处理举报")
	client.ReportAuthManager().execute_admin_login()
	judgment_data = whale.AuthManager().fetch_user_dashboard_data()
	print(printer.color_text(f"登录成功! 欢迎 {judgment_data['admin']['username']}", "SUCCESS"))
	admin_id: int = judgment_data["admin"]["id"]
	client.ReportProcessor().execute_report_handle(admin_id=admin_id)
	print(printer.color_text("已成功处理举报", "SUCCESS"))


@handle_errors
@require_login
def check_account_status(account_data_manager: AccountDataManager) -> None:  # noqa: ARG001
	"""检查账户状态"""
	printer.print_header("账户状态查询")
	status = client.Motion().get_account_status()
	print(printer.color_text(f"当前账户状态: {status}", "STATUS"))


@handle_errors
def download_fiction(account_data_manager: AccountDataManager) -> None:  # noqa: ARG001
	"""下载小说"""
	printer.print_header("下载小说")
	fiction_id = printer.get_valid_input(
		"请输入小说ID",
		cast_type=int,
		validator=lambda x: x > 0,  # 确保ID为正数
	)
	client.Motion().execute_download_fiction(fiction_id=fiction_id)
	print(printer.color_text("小说下载完成", "SUCCESS"))


@handle_errors
@require_login
def generate_nemo_code(account_data_manager: AccountDataManager) -> None:  # noqa: ARG001
	"""生成喵口令"""
	printer.print_header("生成喵口令")
	work_id = printer.get_valid_input(
		"请输入作品编号",
		cast_type=int,
		validator=lambda x: x > 0,  # 确保ID为正数
	)
	client.Motion().generate_nemo_code(work_id=work_id)
	print(printer.color_text("生成完成", "SUCCESS"))


@handle_errors
def print_history(account_data_manager: AccountDataManager) -> None:  # noqa: ARG001
	"""上传历史"""
	printer.print_header("上传历史")
	client.FileUploader().print_upload_history()
	print(printer.color_text("查看完成", "SUCCESS"))


@handle_errors
@require_login
def upload_files(account_data_manager: AccountDataManager) -> None:  # noqa: ARG001
	"""上传文件"""
	printer.print_header("上传文件")
	print(printer.color_text("上传方法说明: ", "COMMENT"))
	print(printer.color_text("- codemao: 上传到bcmcdn域名", "COMMENT"))
	print(printer.color_text("- codegame: 上传到static域名", "COMMENT"))
	print(printer.color_text("- pgaot: 上传到static域名", "COMMENT"))  # cSpell:ignore bcmcdn
	method = printer.get_valid_input("请输入方法 (pgaot/codemao/codegame)", {"pgaot", "codemao", "codegame"})
	file_path_str = printer.prompt_input("请输入文件或文件夹路径")
	file_path = Path(file_path_str.strip())
	if file_path.exists():
		file_path = file_path.resolve()  # 解析为绝对路径
		print(printer.color_text(f"使用路径: {file_path}", "COMMENT"))
	else:
		print(printer.color_text("文件或路径不存在", "ERROR"))
		return
	method = cast("Literal['pgaot', 'codemao','codegame']", method)
	url = client.FileUploader().upload_file(method=method, file_path=file_path)
	print(f"保存地址: {url}")
	print(printer.color_text("文件上传成功", "SUCCESS"))


@handle_errors
@require_login
def logout(account_data_manager: AccountDataManager) -> None:
	"""用户登出"""
	printer.print_header("账户登出")
	method = printer.get_valid_input("请输入方法 (web)", {"web"})
	method = cast("Literal['web']", method)
	community.AuthManager().execute_logout(method)
	account_data_manager.clear()
	print(printer.color_text("已成功登出账户", "SUCCESS"))


@handle_errors
def plugin_manager(account_data_manager: AccountDataManager) -> None:  # noqa: ARG001
	printer.print_header("插件管理")
	plugin_manager = plugin.LazyPluginManager(data.PLUGIN_PATH)
	console = plugin.PluginConsole(plugin_manager)
	console.run()


@handle_errors
@require_login
def handle_hidden_features(_account_data_manager: AccountDataManager) -> None:
	"""处理隐藏功能.仅管理员可访问"""
	# if account_data_manager.get_account_id() not in tool.Encrypt().decrypt(AUI):  # pyright: ignore[reportOperatorIssue]
	# 	return
	if printer.prompt_input("") not in tool.Encrypt().decrypt(AUI):  # pyright: ignore[reportOperatorIssue]
		return
	printer.print_header("隐藏功能")
	print(printer.color_text("1. 自动点赞", "COMMENT"))
	print(printer.color_text("2. 学生管理", "COMMENT"))
	print(printer.color_text("3. 账号提权", "COMMENT"))
	sub_choice = printer.get_valid_input("操作选择", valid_options={"1", "2", "3"})
	if sub_choice == "1":
		user_id = printer.get_valid_input("训练师ID", cast_type=int, validator=lambda x: x > 0)
		client.MillenniumEntanglement().execute_chiaroscuro_chronicles(user_id=user_id, method="work")
		print(printer.color_text("自动点赞完成", "SUCCESS"))
	elif sub_choice == "2":
		mode = printer.get_valid_input("模式 (delete/create/token)", {"delete", "create", "token"})
		# 显式转换为Literal类型,解决类型不匹配问题
		mode = cast("Literal['delete', 'create','token']", mode)
		limit = printer.get_valid_input(
			"数量",
			cast_type=int,
			valid_options=range(1, 101),  # 限制1-100的范围
			validator=lambda x: x > 0,
		)
		client.MillenniumEntanglement().execute_batch_handle_account(method=mode, limit=limit)
		print(printer.color_text("学生管理完成", "SUCCESS"))
	elif sub_choice == "3":
		real_name = printer.prompt_input("输入姓名")
		client.MillenniumEntanglement().execute_celestial_maiden_chronicles(real_name=real_name)
		print(printer.color_text("账号提权完成", "SUCCESS"))


def exit_program(_account_data_manager: AccountDataManager) -> None:
	"""退出程序"""
	print(printer.color_text("感谢使用, 再见!", "SUCCESS"))
	sys.exit(0)


def display_menu(menu_options: dict[str, MenuOption], account_data_manager: AccountDataManager) -> None:
	"""显示菜单.根据登录状态和可见性控制显示"""
	printer.print_header("主菜单")
	for key, option in menu_options.items():
		if not option.visible:
			continue
		color = tool.COLOR_CODES["MENU_ITEM"]
		if option.require_auth and not account_data_manager.is_logged_in:
			color = tool.COLOR_CODES["COMMENT"]
		print(f"{color}{key.rjust(MAX_MENU_KEY_LENGTH)}. {option.name}{tool.COLOR_CODES['RESET']}")


def main() -> None:
	"""主程序入口"""
	enable_vt_mode()
	client.Index().index()
	account_data_manager = AccountDataManager()
	menu_options = {
		"01": MenuOption(name="用户登录", handler=partial(login, account_data_manager), require_auth=False),
		"02": MenuOption(name="清除评论", handler=partial(clear_comments, account_data_manager), require_auth=True),
		"03": MenuOption(name="清除红点", handler=partial(clear_red_point, account_data_manager), require_auth=True),
		"04": MenuOption(name="自动回复", handler=partial(reply_work, account_data_manager), require_auth=True),
		"05": MenuOption(name="账户登出", handler=partial(logout, account_data_manager), require_auth=True),
		"06": MenuOption(name="处理举报", handler=partial(handle_report, account_data_manager), require_auth=False),
		"07": MenuOption(name="状态查询", handler=partial(check_account_status, account_data_manager), require_auth=True),
		"08": MenuOption(name="下载小说", handler=partial(download_fiction, account_data_manager), require_auth=False),
		"09": MenuOption(name="生成口令", handler=partial(generate_nemo_code, account_data_manager), require_auth=True),
		"10": MenuOption(name="上传文件", handler=partial(upload_files, account_data_manager), require_auth=True),
		"11": MenuOption(name="上传历史", handler=partial(print_history, account_data_manager), require_auth=False),
		"12": MenuOption(name="插件管理", handler=partial(plugin_manager, account_data_manager), require_auth=False),
		"00": MenuOption(name="退出系统", handler=partial(exit_program, account_data_manager), require_auth=False),
		"1106": MenuOption(
			name="隐藏功能",
			handler=partial(handle_hidden_features, account_data_manager),
			require_auth=True,
			visible=False,  # 可以根据需要设置为False完全隐藏
		),
	}
	while True:
		display_menu(menu_options, account_data_manager)
		choice = printer.prompt_input("请输入操作编号 (01-12)")
		if choice in menu_options:
			option = menu_options[choice]
			if option.require_auth and not account_data_manager.is_logged_in:
				print(printer.color_text("该操作需要登录!", "ERROR"))
				if printer.prompt_input("是否立即登录? (y/n)").lower() == "y":
					login(account_data_manager)
				else:
					continue
			option.handler()
		else:
			print(printer.color_text("无效的输入, 请重新选择", "ERROR"))
		input(f"\n{printer.color_text('⏎ 按回车键继续...', 'PROMPT')}")


if __name__ == "__main__":
	try:
		main()
	except KeyboardInterrupt:
		print(f"\n{printer.color_text('程序被用户中断', 'ERROR')}")
	except Exception:
		logger.exception("程序发生未处理异常")
		print(f"\n{printer.color_text('程序发生错误', 'ERROR')}")
	finally:
		input(f"\n{printer.color_text('⏎ 按回车键退出程序', 'PROMPT')}")
# "POST_COMMENT",
# "POST_COMMENT_DELETE_FEEDBACK",
# "POST_DELETE_FEEDBACK",
# "POST_DISCUSSION_LIKED",
# "POST_REPLY",
# "POST_REPLY_AUTHOR",
# "POST_REPLY_REPLY",
# "POST_REPLY_REPLY_AUTHOR",
# "POST_REPLY_REPLY_FEEDBACK",
# "WORK_COMMENT",路人a评论{user}的作品
# "WORK_DISCUSSION_LIKED",
# "WORK_LIKE",
# "WORK_REPLY",路人a评论{user}在某个作品的评论
# "WORK_REPLY_AUTHOR",路人a回复{user}作品下路人b的某条评论
# "WORK_REPLY_REPLY",路人a回复{user}作品下路人b/a的评论下{user}的回复
# "WORK_REPLY_REPLY_AUTHOR",路人a回复{user}作品下路人b/a对某条评论的回复
# "WORK_REPLY_REPLY_FEEDBACK",路人a回复{user}在某个作品下发布的评论的路人b/a的回复
# "WORK_SHOP_REPL"
# "WORK_SHOP_USER_LEAVE",
