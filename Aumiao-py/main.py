import logging
import sys
from collections.abc import Callable
from ctypes import windll
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Literal, TypeVar, cast

# 导入项目模块(请根据实际项目结构调整)
from src import client, community, user, whale

# 常量定义
MAX_MENU_KEY_LENGTH = 2  # 替换魔法值2,解决PLR2004
T = TypeVar("T")

# 初始化日志(使用logger实例而非root logger,解决LOG015)
logger = logging.getLogger(__name__)
logging.basicConfig(
	filename="app.log",
	level=logging.ERROR,
	format="%(asctime)s - %(levelname)s - %(message)s",  # cSpell:ignore levelname
)

# 颜色常量
COLOR_CODES = {
	"COMMENT": "\033[38;5;245m",  # 辅助说明
	"ERROR": "\033[38;5;203m",  # 错误提示
	"MENU_ITEM": "\033[38;5;183m",  # 菜单项
	"MENU_TITLE": "\033[38;5;80m",  # 菜单标题
	"PROMPT": "\033[38;5;75m",  # 输入提示
	"RESET": "\033[0m",  # 重置样式
	"STATUS": "\033[38;5;228m",  # 状态信息
	"SUCCESS": "\033[38;5;114m",  # 成功提示
}

# 延迟加载分隔符
SEPARATOR: str | None = None


@dataclass
class MenuOption:
	"""菜单选项类"""

	name: str
	handler: Callable
	require_auth: bool = False


T = TypeVar("T")


def get_separator() -> str:
	"""获取分隔符,延迟初始化"""
	global SEPARATOR  # noqa: PLW0603
	if SEPARATOR is None:
		SEPARATOR = f"{COLOR_CODES['PROMPT']}══════════════════════════════════════════════════════════{COLOR_CODES['RESET']}"
	return SEPARATOR


def print_header(text: str) -> None:
	"""打印装饰头部"""
	separator = get_separator()
	print(f"\n{separator}")
	print(f"{COLOR_CODES['MENU_TITLE']}{text:^60}{COLOR_CODES['RESET']}")
	print(f"{separator}\n")


def enable_vt_mode() -> None:
	"""启用Windows虚拟终端模式"""
	if sys.platform == "win32":
		try:
			kernel32 = windll.kernel32
			kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
		except OSError:
			logger.exception("启用VT模式失败")
			print(f"{COLOR_CODES['ERROR']}警告: 无法启用虚拟终端模式,颜色显示可能不正常{COLOR_CODES['RESET']}")


def get_valid_input(
	prompt: str,
	valid_options: set[T],
	cast_type: Callable[[str], T] = str,  # 明确类型转换函数的注解
) -> T:
	"""获取有效输入并进行类型转换验证"""
	while True:
		try:
			value_str = input(prompt)
			# 进行类型转换
			value = cast_type(value_str)

			# 检查是否在有效选项中
			if value in valid_options:
				return value

			print(f"{COLOR_CODES['ERROR']}无效输入,请重试。有效选项: {valid_options}{COLOR_CODES['RESET']}")

		except ValueError:
			print(f"{COLOR_CODES['ERROR']}格式错误,请输入{cast_type.__name__}类型的值{COLOR_CODES['RESET']}")
		except Exception as e:
			print(f"{COLOR_CODES['ERROR']}发生错误: {e!s}{COLOR_CODES['RESET']}")


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

	def get_account_id(self) -> int | None:
		"""获取账户ID"""
		return self.account_data.get("ACCOUNT_DATA", {}).get("id")


def login(account_data_manager: AccountDataManager) -> None:
	"""用户登录处理"""
	print_header("用户登录")
	identity = input(f"{COLOR_CODES['PROMPT']}↳ 请输入用户名: {COLOR_CODES['RESET']}")
	password = input(f"{COLOR_CODES['PROMPT']}↳ 请输入密码: {COLOR_CODES['RESET']}")

	try:
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
		print(f"{COLOR_CODES['SUCCESS']}登录成功! 欢迎 {data_['nickname']}{COLOR_CODES['RESET']}")
	except Exception:
		logger.exception("登录失败")
		print(f"{COLOR_CODES['ERROR']}登录失败,请检查账号密码{COLOR_CODES['RESET']}")


# 修复装饰器类型标注,移除Any类型
def require_login(func: Callable[[AccountDataManager], None]) -> Callable[[AccountDataManager], None]:
	"""登录检查装饰器"""

	def wrapper(account_data_manager: AccountDataManager) -> None:
		if not account_data_manager.is_logged_in:
			print(f"{COLOR_CODES['ERROR']}请先登录!{COLOR_CODES['RESET']}")
			return None
		return func(account_data_manager)

	return wrapper


@require_login
def clear_comments(_account_data_manager: AccountDataManager) -> None:
	"""清除评论"""
	print_header("清除评论")
	source = get_valid_input(f"{COLOR_CODES['PROMPT']}↳ 请输入来源类型 (work/post): {COLOR_CODES['RESET']}", {"work", "post"})
	action_type = get_valid_input(f"{COLOR_CODES['PROMPT']}↳ 请输入操作类型 (ads/duplicates/blacklist): {COLOR_CODES['RESET']}", {"ads", "duplicates", "blacklist"})

	source = cast("Literal['work', 'post']", source)
	action_type = cast("Literal['ads', 'duplicates', 'blacklist']", action_type)

	try:
		client.Motion().clear_comments(source=source, action_type=action_type)
		print(f"{COLOR_CODES['SUCCESS']}已成功清除 {source} 的 {action_type} 评论{COLOR_CODES['RESET']}")
	except Exception:
		logger.exception("清除评论失败")
		print(f"{COLOR_CODES['ERROR']}清除评论失败{COLOR_CODES['RESET']}")


@require_login
def clear_red_point(_account_data_manager: AccountDataManager) -> None:
	"""清除红点提醒"""
	print_header("清除红点提醒")
	method = get_valid_input(f"{COLOR_CODES['PROMPT']}↳ 请输入方法 (nemo/web): {COLOR_CODES['RESET']}", {"nemo", "web"})

	method = cast("Literal['nemo', 'web']", method)

	try:
		client.Motion().clear_red_point(method=method)
		print(f"{COLOR_CODES['SUCCESS']}已成功清除 {method} 红点提醒{COLOR_CODES['RESET']}")
	except Exception:
		logger.exception("清除红点失败")
		print(f"{COLOR_CODES['ERROR']}清除红点失败{COLOR_CODES['RESET']}")


@require_login
def reply_work(_account_data_manager: AccountDataManager) -> None:
	"""自动回复作品"""
	print_header("自动回复")
	try:
		client.Motion().reply_work()
		print(f"{COLOR_CODES['SUCCESS']}已成功执行自动回复{COLOR_CODES['RESET']}")
	except Exception:
		logger.exception("自动回复失败")
		print(f"{COLOR_CODES['ERROR']}自动回复失败{COLOR_CODES['RESET']}")


def handle_report(_account_data_manager: AccountDataManager) -> None:
	"""处理举报"""
	print_header("处理举报")
	try:
		client.Motion().judgement_login()
		judgment_data = whale.AuthManager().fetch_user_dashboard_data()

		print(f"{COLOR_CODES['SUCCESS']}登录成功! 欢迎 {judgment_data['admin']['username']}{COLOR_CODES['RESET']}")
		admin_id: int = judgment_data["admin"]["id"]

		client.Motion().handle_report(admin_id=admin_id)
		print(f"{COLOR_CODES['SUCCESS']}已成功处理举报{COLOR_CODES['RESET']}")
	except Exception:
		logger.exception("处理举报失败")
		print(f"{COLOR_CODES['ERROR']}处理举报失败{COLOR_CODES['RESET']}")


@require_login
def check_account_status(_account_data_manager: AccountDataManager) -> None:
	"""检查账户状态"""
	print_header("账户状态查询")
	try:
		status = client.Motion().get_account_status()
		print(f"{COLOR_CODES['STATUS']}当前账户状态: {status}{COLOR_CODES['RESET']}")
	except Exception:
		logger.exception("查询账户状态失败")
		print(f"{COLOR_CODES['ERROR']}查询账户状态失败{COLOR_CODES['RESET']}")


def download_fiction(_account_data_manager: AccountDataManager) -> None:
	"""下载小说"""
	print_header("下载小说")
	try:
		fiction_id = int(input(f"{COLOR_CODES['PROMPT']}↳ 请输入小说ID: {COLOR_CODES['RESET']}"))
		client.Motion().download_fiction(fiction_id=fiction_id)
		print(f"{COLOR_CODES['SUCCESS']}小说下载完成{COLOR_CODES['RESET']}")
	except ValueError:
		print(f"{COLOR_CODES['ERROR']}请输入有效的数字ID{COLOR_CODES['RESET']}")
	except Exception:
		logger.exception("下载小说失败")
		print(f"{COLOR_CODES['ERROR']}下载小说失败{COLOR_CODES['RESET']}")


@require_login
def generate_nemo_code(_account_data_manager: AccountDataManager) -> None:
	"""生成喵口令"""
	print_header("生成喵口令")
	try:
		work_id = int(input(f"{COLOR_CODES['PROMPT']}↳ 请输入作品编号: {COLOR_CODES['RESET']}"))
		client.Motion().generate_nemo_code(work_id=work_id)
		print(f"{COLOR_CODES['SUCCESS']}生成完成{COLOR_CODES['RESET']}")
	except ValueError:
		print(f"{COLOR_CODES['ERROR']}请输入有效的数字ID{COLOR_CODES['RESET']}")
	except Exception:
		logger.exception("生成喵口令失败")
		print(f"{COLOR_CODES['ERROR']}生成喵口令失败{COLOR_CODES['RESET']}")


@require_login
def upload_files(_account_data_manager: AccountDataManager) -> None:
	"""上传文件"""
	print_header("上传文件")
	print(f"{COLOR_CODES['COMMENT']}上传方法说明: {COLOR_CODES['RESET']}")
	print(f"{COLOR_CODES['COMMENT']}- codemao: 上传到static域名 (需要登录){COLOR_CODES['RESET']}")
	print(f"{COLOR_CODES['COMMENT']}- pgaot: 上传到bcmcdn域名{COLOR_CODES['RESET']}")  # cSpell:ignore bcmcdn

	try:
		method = get_valid_input(f"{COLOR_CODES['PROMPT']}↳ 请输入方法 (pgaot/codemao): {COLOR_CODES['RESET']}", {"pgaot", "codemao"})

		file_path = Path(input(f"{COLOR_CODES['PROMPT']}↳ 请输入文件或文件夹路径: {COLOR_CODES['RESET']}"))

		if not file_path.exists():
			print(f"{COLOR_CODES['ERROR']}文件或路径不存在{COLOR_CODES['RESET']}")
			return

		method = cast("Literal['pgaot', 'codemao']", method)
		client.Motion().upload_file(method=method, file_path=file_path)
		print(f"{COLOR_CODES['SUCCESS']}文件上传成功{COLOR_CODES['RESET']}")
	except Exception:
		logger.exception("文件上传失败")
		print(f"{COLOR_CODES['ERROR']}文件上传失败{COLOR_CODES['RESET']}")


@require_login
def logout(_account_data_manager: AccountDataManager) -> None:
	"""用户登出"""
	print_header("账户登出")
	method = get_valid_input(f"{COLOR_CODES['PROMPT']}↳ 请输入方法 (web): {COLOR_CODES['RESET']}", {"web"})

	method = cast("Literal['web']", method)

	try:
		community.AuthManager().logout(method)
		_account_data_manager.clear()
		print(f"{COLOR_CODES['SUCCESS']}已成功登出账户{COLOR_CODES['RESET']}")
	except Exception:
		logger.exception("登出失败")
		print(f"{COLOR_CODES['ERROR']}登出失败{COLOR_CODES['RESET']}")


@require_login
def handle_hidden_features(_account_data_manager: AccountDataManager) -> None:
	"""处理隐藏功能"""
	print_header("隐藏功能")
	print(f"{COLOR_CODES['COMMENT']}1. 自动点赞")
	print(f"{COLOR_CODES['COMMENT']}2. 学生管理")
	print(f"{COLOR_CODES['COMMENT']}3. 账号提权{COLOR_CODES['RESET']}")

	try:
		sub_choice = input(f"{COLOR_CODES['PROMPT']}↳ 操作选择: {COLOR_CODES['RESET']}")

		if sub_choice == "1":
			user_id = int(input(f"{COLOR_CODES['PROMPT']}↳ 训练师ID: {COLOR_CODES['RESET']}"))
			client.Motion().chiaroscuro_chronicles(user_id=user_id)
			print(f"{COLOR_CODES['SUCCESS']}自动点赞完成{COLOR_CODES['RESET']}")
		elif sub_choice == "2":
			mode = get_valid_input(f"{COLOR_CODES['PROMPT']}↳ 模式 (delete/create): {COLOR_CODES['RESET']}", {"delete", "create"})
			# 显式转换为Literal类型,解决类型不匹配问题
			mode = cast("Literal['delete', 'create']", mode)
			limit = int(input(f"{COLOR_CODES['PROMPT']}↳ 数量: {COLOR_CODES['RESET']}"))
			client.Motion().batch_handle_account(method=mode, limit=limit)
			print(f"{COLOR_CODES['SUCCESS']}学生管理完成{COLOR_CODES['RESET']}")
		elif sub_choice == "3":
			real_name = input(f"{COLOR_CODES['PROMPT']}↳ 输入姓名: {COLOR_CODES['RESET']}")
			client.Motion().celestial_maiden_chronicles(real_name=real_name)
			print(f"{COLOR_CODES['SUCCESS']}账号提权完成{COLOR_CODES['RESET']}")
		else:
			print(f"{COLOR_CODES['ERROR']}无效选择{COLOR_CODES['RESET']}")
	except ValueError:
		print(f"{COLOR_CODES['ERROR']}请输入有效的数字{COLOR_CODES['RESET']}")
	except Exception:
		logger.exception("隐藏功能执行失败")
		print(f"{COLOR_CODES['ERROR']}隐藏功能执行失败{COLOR_CODES['RESET']}")


def main() -> None:
	"""主程序入口"""
	enable_vt_mode()

	client.Index().index()
	account_data_manager = AccountDataManager()

	menu_options = {
		"1": MenuOption(name="用户登录", handler=partial(login, account_data_manager), require_auth=False),
		"2": MenuOption(name="清除评论", handler=partial(clear_comments, account_data_manager), require_auth=True),
		"3": MenuOption(name="清除红点", handler=partial(clear_red_point, account_data_manager), require_auth=True),
		"4": MenuOption(name="自动回复", handler=partial(reply_work, account_data_manager), require_auth=True),
		"5": MenuOption(name="账户登出", handler=partial(logout, account_data_manager), require_auth=True),
		"6": MenuOption(name="处理举报", handler=partial(handle_report, account_data_manager), require_auth=False),
		"7": MenuOption(name="状态查询", handler=partial(check_account_status, account_data_manager), require_auth=True),
		"8": MenuOption(name="下载小说", handler=partial(download_fiction, account_data_manager), require_auth=False),
		"9": MenuOption(name="生成口令", handler=partial(generate_nemo_code, account_data_manager), require_auth=True),
		"10": MenuOption(name="上传文件", handler=partial(upload_files, account_data_manager), require_auth=True),
		"11": MenuOption(name="退出系统", handler=lambda: print(f"\n{COLOR_CODES['SUCCESS']}感谢使用, 再见!{COLOR_CODES['RESET']}"), require_auth=False),
		"1106": MenuOption(name="隐藏功能", handler=partial(handle_hidden_features, account_data_manager), require_auth=True),
	}

	while True:
		print_header("主菜单")

		for key, option in menu_options.items():
			if key.isdigit() and len(key) <= MAX_MENU_KEY_LENGTH:
				color = COLOR_CODES["MENU_ITEM"]
				if option.require_auth and not account_data_manager.is_logged_in:
					color = COLOR_CODES["COMMENT"]
				print(f"{color}{key}. {option.name}{COLOR_CODES['RESET']}")

		choice = input(f"\n{COLOR_CODES['PROMPT']}↳ 请输入操作编号 (1-11): {COLOR_CODES['RESET']}")

		if choice in menu_options:
			option = menu_options[choice]

			if option.require_auth and not account_data_manager.is_logged_in:
				print(f"{COLOR_CODES['ERROR']}该操作需要登录!{COLOR_CODES['RESET']}")
				if input(f"{COLOR_CODES['PROMPT']}是否立即登录? (y/n): {COLOR_CODES['RESET']}".lower()) == "y":
					login(account_data_manager)
				else:
					continue

			try:
				option.handler()
			except Exception:
				logger.exception("菜单操作失败")
				print(f"{COLOR_CODES['ERROR']}操作失败{COLOR_CODES['RESET']}")

			if choice == "11":
				break
		else:
			print(f"{COLOR_CODES['ERROR']}无效的输入, 请重新选择{COLOR_CODES['RESET']}")

		input(f"\n{COLOR_CODES['PROMPT']}⏎ 按回车键继续...{COLOR_CODES['RESET']}")


if __name__ == "__main__":
	try:
		main()
	except KeyboardInterrupt:
		print(f"\n{COLOR_CODES['ERROR']}程序被用户中断{COLOR_CODES['RESET']}")
	except Exception:
		logger.exception("程序发生未处理异常")
		print(f"\n{COLOR_CODES['ERROR']}程序发生错误{COLOR_CODES['RESET']}")
	finally:
		input(f"\n{COLOR_CODES['PROMPT']}⏎ 按回车键退出程序{COLOR_CODES['RESET']}")
