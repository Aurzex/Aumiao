from src import *  # noqa: F403

# 颜色代码定义
COLOR_PROMPT = "\033[1;34m"  # 蓝色加粗-输入提示
COLOR_SUCCESS = "\033[1;32m"  # 绿色加粗-成功提示
COLOR_ERROR = "\033[1;31m"  # 红色加粗-错误提示
COLOR_MENU_TITLE = "\033[1;36m"  # 青色加粗-菜单标题
COLOR_MENU_ITEM = "\033[1;35m"  # 紫色加粗-菜单项
COLOR_STATUS = "\033[1;33m"  # 黄色加粗-状态信息
COLOR_RESET = "\033[0m"  # 重置样式

# 装饰线符号
SEPARATOR = f"{COLOR_PROMPT}══════════════════════════════════════════════════════════{COLOR_RESET}"


def print_header(text: str) -> None:
	"""打印带装饰的标题"""
	print(f"\n{SEPARATOR}")
	print(f"{COLOR_MENU_TITLE}{text:^60}{COLOR_RESET}")
	print(f"{SEPARATOR}\n")


def login() -> None:
	"""尝试登录并获取数据"""
	try:
		print_header("用户登录")
		identity = input(f"{COLOR_PROMPT}↳ 请输入用户名: {COLOR_RESET}")
		password = input(f"{COLOR_PROMPT}↳ 请输入密码: {COLOR_RESET}")

		community.Login().login_token(identity=identity, password=password)  # noqa: F405
		data_ = user.Obtain().get_data_details()  # noqa: F405

		account_data_manager = data.DataManager()  # noqa: F405
		account_data_manager.update(
			{
				"ACCOUNT_DATA": {
					"identity": identity,
					"password": "******",
					"id": data_["id"],
					"nickname": data_["nickname"],
					"create_time": data_["create_time"],
					"description": data_["description"],
					"author_level": data_["author_level"],
				},
			},
		)
		print(f"{COLOR_SUCCESS}✅ 登录成功！欢迎 {data_['nickname']}{COLOR_RESET}")

	except Exception as e:
		print(f"{COLOR_ERROR}❌ 登录失败: {e}{COLOR_RESET}")


def clear_comments() -> None:
	"""尝试执行清除评论的操作"""
	try:
		print_header("清除评论")
		source = input(f"{COLOR_PROMPT}↳ 请输入来源类型 (work/post): {COLOR_RESET}").lower()
		action_type = input(f"{COLOR_PROMPT}↳ 请输入操作类型 (ads/duplicates/blacklist): {COLOR_RESET}").lower()

		if source not in {"work", "post"} or action_type not in {"ads", "duplicates", "blacklist"}:
			print(f"{COLOR_ERROR}⚠ 无效的输入，请检查选项是否正确{COLOR_RESET}")
			return

		client.Motion().clear_comments(source=source, action_type=action_type)  # type: ignore  # noqa: F405, PGH003
		print(f"{COLOR_SUCCESS}✅ 已成功清除 {source} 的 {action_type} 评论{COLOR_RESET}")

	except Exception as e:
		print(f"{COLOR_ERROR}❌ 清除评论失败: {e}{COLOR_RESET}")


def clear_red_point() -> None:
	"""尝试执行清除红点操作"""
	try:
		print_header("清除红点提醒")
		method = input(f"{COLOR_PROMPT}↳ 请输入方法 (nemo/web): {COLOR_RESET}").lower()

		if method not in {"nemo", "web"}:
			print(f"{COLOR_ERROR}⚠ 无效的输入，请使用 nemo 或 web 方法{COLOR_RESET}")
			return

		client.Motion().clear_red_point(method=method)  # type: ignore  # noqa: F405, PGH003
		print(f"{COLOR_SUCCESS}✅ 已成功清除 {method} 红点提醒{COLOR_RESET}")

	except Exception as e:
		print(f"{COLOR_ERROR}❌ 清除红点失败: {e}{COLOR_RESET}")


def reply_work() -> None:
	"""尝试执行自动回复操作"""
	try:
		print_header("自动回复")
		client.Motion().reply_work()  # noqa: F405
		print(f"{COLOR_SUCCESS}✅ 已成功执行自动回复{COLOR_RESET}")
	except Exception as e:
		print(f"{COLOR_ERROR}❌ 自动回复失败: {e}{COLOR_RESET}")


def handle_report() -> None:
	"""尝试执行处理举报操作"""
	try:
		print_header("处理举报")
		token = input(f"{COLOR_PROMPT}↳ 请输入 Authorization: {COLOR_RESET}")
		whale.Routine().set_token(token=token)  # noqa: F405

		admin_id = int(input(f"{COLOR_PROMPT}↳ 请输入管理员ID: {COLOR_RESET}"))
		client.Motion().handle_report(admin_id=admin_id)  # noqa: F405
		print(f"{COLOR_SUCCESS}✅ 已成功处理举报{COLOR_RESET}")

	except Exception as e:
		print(f"{COLOR_ERROR}❌ 处理举报失败: {e}{COLOR_RESET}")


def check_account_status() -> None:
	"""尝试查看账户状态"""
	try:
		print_header("账户状态查询")
		status = client.Motion().get_account_status()  # noqa: F405
		print(f"{COLOR_STATUS}🔄 当前账户状态: {status}{COLOR_RESET}")
	except Exception as e:
		print(f"{COLOR_ERROR}❌ 获取账户状态失败: {e}{COLOR_RESET}")


def logout() -> None:
	"""尝试执行登出操作"""
	try:
		print_header("账户登出")
		method = input(f"{COLOR_PROMPT}↳ 请输入方法 (web): {COLOR_RESET}").lower()

		if method != "web":
			print(f"{COLOR_ERROR}⚠ 无效的输入，目前仅支持 web 登出方式{COLOR_RESET}")
			return

		community.Login().logout(method=method)  # noqa: F405
		print(f"{COLOR_SUCCESS}✅ 已成功登出账户{COLOR_RESET}")

	except Exception as e:
		print(f"{COLOR_ERROR}❌ 登出失败: {e}{COLOR_RESET}")


def main() -> None:
	"""主函数"""
	client.Index().index()  # noqa: F405
	while True:
		print_header("主菜单")
		print(f"{COLOR_MENU_ITEM}1. 用户登录")
		print("2. 清除评论")
		print("3. 清除红点提醒")
		print("4. 自动回复")
		print("5. 账户登出")
		print("6. 处理举报")
		print("7. 状态查询")
		print(f"8. 退出系统{COLOR_RESET}")

		choice = input(f"\n{COLOR_PROMPT}↳ 请输入操作编号 (1-8): {COLOR_RESET}")

		if choice == "1":
			login()
		elif choice == "2":
			clear_comments()
		elif choice == "3":
			clear_red_point()
		elif choice == "4":
			reply_work()
		elif choice == "5":
			logout()
		elif choice == "6":
			handle_report()
		elif choice == "7":
			check_account_status()
		elif choice == "8":
			print(f"\n{COLOR_SUCCESS}👋 感谢使用，再见！{COLOR_RESET}")
			break
		else:
			print(f"{COLOR_ERROR}⚠ 无效的输入，请重新选择{COLOR_RESET}")

		input(f"\n{COLOR_PROMPT}⏎ 按回车键继续...{COLOR_RESET}")


if __name__ == "__main__":
	main()
	input(f"\n{COLOR_PROMPT}⏎ 按回车键退出程序{COLOR_RESET}")
