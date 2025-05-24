import sys
from typing import Any, Literal, cast

from src import *  # noqa: F403

# Constants for color codes (moved to top level for better organization)
COLOR_CODES = {
	"COMMENT": "\033[38;5;245m",  # Medium gray - auxiliary instructions
	"ERROR": "\033[38;5;203m",  # Light red - error messages (coral-like)
	"MENU_ITEM": "\033[38;5;183m",  # Lavender purple - menu items
	"MENU_TITLE": "\033[38;5;80m",  # Teal - menu titles (lake-like)
	"PROMPT": "\033[38;5;75m",  # Light blue - input prompts (sky-like)
	"RESET": "\033[0m",  # Reset styles
	"STATUS": "\033[38;5;228m",  # Light yellow - status info (moonlight-like)
	"SUCCESS": "\033[38;5;114m",  # Light green - success messages (sprout-like)
}

SEPARATOR = f"{COLOR_CODES['PROMPT']}══════════════════════════════════════════════════════════{COLOR_CODES['RESET']}"


def enable_vt_mode() -> None:
	"""Enable virtual terminal mode on Windows for ANSI color support."""
	if sys.platform == "win32":
		from ctypes import windll  # noqa: PLC0415

		kernel32 = windll.kernel32
		kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)


def print_header(text: str) -> None:
	"""Print a decorated header with centered text."""
	print(f"\n{SEPARATOR}")
	print(f"{COLOR_CODES['MENU_TITLE']}{text:^60}{COLOR_CODES['RESET']}")
	print(f"{SEPARATOR}\n")


def login(account_data_manager: Any) -> dict[str, dict]:  # noqa: ANN401
	"""Handle user login and return account data."""
	print_header("用户登录")
	identity = input(f"{COLOR_CODES['PROMPT']}↳ 请输入用户名: {COLOR_CODES['RESET']}")
	password = input(f"{COLOR_CODES['PROMPT']}↳ 请输入密码: {COLOR_CODES['RESET']}")

	community.Login().login_token(identity=identity, password=password)  # noqa: F405
	data_ = user.Obtain().get_data_details()  # noqa: F405

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
	print(f"{COLOR_CODES['SUCCESS']}登录成功!欢迎 {data_['nickname']}{COLOR_CODES['RESET']}")
	return account_data


def clear_comments() -> None:
	"""Clear comments based on source and action type."""
	valid_sources = {"work", "post"}
	valid_actions = {"ads", "duplicates", "blacklist"}

	print_header("清除评论")
	source = input(f"{COLOR_CODES['PROMPT']}↳ 请输入来源类型 (work/post): {COLOR_CODES['RESET']}").lower()
	action_type = input(f"{COLOR_CODES['PROMPT']}↳ 请输入操作类型 (ads/duplicates/blacklist): {COLOR_CODES['RESET']}").lower()
	source = cast("Literal['work', 'post']", source)
	action_type = cast("Literal['ads', 'duplicates', 'blacklist']", source)
	if source not in valid_sources or action_type not in valid_actions:
		print(f"{COLOR_CODES['ERROR']}无效的输入,请检查选项是否正确{COLOR_CODES['RESET']}")
		return

	client.Motion().clear_comments(source=source, action_type=action_type)  # noqa: F405
	print(f"{COLOR_CODES['SUCCESS']}已成功清除 {source} 的 {action_type} 评论{COLOR_CODES['RESET']}")


def clear_red_point() -> None:
	"""Clear notification red dots using specified method."""
	valid_methods = {"nemo", "web"}

	print_header("清除红点提醒")
	method = input(f"{COLOR_CODES['PROMPT']}↳ 请输入方法 (nemo/web): {COLOR_CODES['RESET']}").lower()

	if method not in valid_methods:
		print(f"{COLOR_CODES['ERROR']}无效的输入,请使用 nemo 或 web 方法{COLOR_CODES['RESET']}")
		return
	method = cast("Literal['nemo', 'web']", method)
	client.Motion().clear_red_point(method=method)  # noqa: F405
	print(f"{COLOR_CODES['SUCCESS']}已成功清除 {method} 红点提醒{COLOR_CODES['RESET']}")


def reply_work() -> None:
	"""Automatically reply to works."""
	print_header("自动回复")
	client.Motion().reply_work()  # noqa: F405
	print(f"{COLOR_CODES['SUCCESS']}已成功执行自动回复{COLOR_CODES['RESET']}")


def handle_report() -> None:
	"""Handle reports with admin privileges."""
	print_header("处理举报")
	client.Motion().judgement_login()  # noqa: F405
	admin_id = int(input(f"{COLOR_CODES['PROMPT']}↳ 请输入管理员ID: {COLOR_CODES['RESET']}"))
	client.Motion().handle_report(admin_id=admin_id)  # noqa: F405
	print(f"{COLOR_CODES['SUCCESS']}已成功处理举报{COLOR_CODES['RESET']}")


def check_account_status() -> None:
	"""Check and display account status."""
	print_header("账户状态查询")
	status = client.Motion().get_account_status()  # noqa: F405
	print(f"{COLOR_CODES['STATUS']}当前账户状态: {status}{COLOR_CODES['RESET']}")


def download_fiction() -> None:
	"""Download fiction by ID."""
	print_header("下载小说")
	fiction_id = int(input(f"{COLOR_CODES['PROMPT']}↳ 请输入小说链接: {COLOR_CODES['RESET']}"))
	client.Motion().download_fiction(fiction_id=fiction_id)  # noqa: F405
	print(f"{COLOR_CODES['SUCCESS']}小说下载完成{COLOR_CODES['RESET']}")


def logout() -> None:
	"""Log out from the system."""
	valid_methods = {"web"}

	print_header("账户登出")
	method = input(f"{COLOR_CODES['PROMPT']}↳ 请输入方法 (web): {COLOR_CODES['RESET']}").lower()

	if method not in valid_methods:
		print(f"{COLOR_CODES['ERROR']}无效的输入,目前仅支持 web 登出方式{COLOR_CODES['RESET']}")
		return
	method = cast("Literal['web', 'app']", method)
	community.Login().logout(method=method)  # noqa: F405
	print(f"{COLOR_CODES['SUCCESS']}已成功登出账户{COLOR_CODES['RESET']}")


def handle_hidden_features() -> None:
	"""Process hidden menu features."""
	print("\n隐藏功能\n1.自动点赞\n2.学生管理")
	sub_choice = input("操作选择: ")

	if sub_choice == "1":
		user_id = int(input("训练师ID: "))
		client.Motion().chiaroscuro_chronicles(user_id=user_id)  # noqa: F405
	elif sub_choice == "2":
		mode = input("模式 删除学生/创建学生(delete/create): ")
		limit = int(input("数量: "))
		mode = cast("Literal['create', 'delete']", mode)
		client.Motion().batch_handle_account(method=mode, limit=limit)  # noqa: F405
	else:
		print("无效输入")


def main() -> None:
	"""Main application entry point."""
	enable_vt_mode()
	client.Index().index()  # noqa: F405

	account_data_manager = data.DataManager()  # noqa: F405

	menu_options = {
		"1": ("用户登录", lambda: login(account_data_manager)),
		"2": ("清除评论", clear_comments),
		"3": ("邮箱已读", clear_red_point),
		"4": ("自动回复", reply_work),
		"5": ("账户登出", logout),
		"6": ("处理举报", handle_report),
		"7": ("状态查询", check_account_status),
		"8": ("下载小说", download_fiction),
		"9": ("退出系统", lambda: print(f"\n{COLOR_CODES['SUCCESS']}感谢使用,再见!{COLOR_CODES['RESET']}")),
		"1106": ("隐藏功能", handle_hidden_features),
	}

	while True:
		print_header("主菜单")
		for key, (label, _) in menu_options.items():
			if key.isdigit() and len(key) == 1:  # Only show main menu options
				print(f"{COLOR_CODES['MENU_ITEM']}{key}. {label}")

		choice = input(f"\n{COLOR_CODES['PROMPT']}↳ 请输入操作编号 (1-9): {COLOR_CODES['RESET']}")

		if choice in menu_options:
			action = menu_options[choice][1]
			try:
				action()
				if choice == "9":  # Exit condition
					break
			except Exception as e:
				print(f"{COLOR_CODES['ERROR']}操作失败: {e}{COLOR_CODES['RESET']}")
		else:
			print(f"{COLOR_CODES['ERROR']}无效的输入,请重新选择{COLOR_CODES['RESET']}")

		input(f"\n{COLOR_CODES['PROMPT']}⏎ 按回车键继续...{COLOR_CODES['RESET']}")


if __name__ == "__main__":
	try:
		main()
	except KeyboardInterrupt:
		print(f"\n{COLOR_CODES['ERROR']}程序被用户中断{COLOR_CODES['RESET']}")
	finally:
		input(f"\n{COLOR_CODES['PROMPT']}⏎ 按回车键退出程序{COLOR_CODES['RESET']}")
