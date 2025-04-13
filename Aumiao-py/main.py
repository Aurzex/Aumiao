from src import *  # noqa: F403


def login() -> None:
	"""尝试登录并获取数据"""
	try:
		# 输入用户名
		identity = input("请输入用户名: ")
		# 输入密码
		password = input("请输入密码: ")
		# 登录并获取数据
		community.Login().login_token(identity=identity, password=password)  # noqa: F405
		_data = user.Obtain().get_data_details()  # noqa: F405
		# 使用 update 方法更新字典中的数据
		account_data_manager = data.DataManager()  # noqa: F405
		account_data_manager.update(
			{
				"ACCOUNT_DATA": {
					"identity": identity,
					"password": "******",  # 不建议存储密码
					"id": _data["id"],
					"nickname": _data["nickname"],
					"create_time": _data["create_time"],
					"description": _data["description"],
					"author_level": _data["author_level"],
				},
			},
		)
	except Exception as e:
		print(f"登录失败: {e}")


def clear_comments() -> None:
	"""尝试执行清除评论的操作"""
	try:
		source = input("请输入来源类型 (work/post): ")
		action_type = input("请输入操作类型 (ads/duplicates/blacklist): ")
		# 判断输入是否有效
		if source not in ["work", "post"] or action_type not in ["ads", "duplicates", "blacklist"]:
			print("无效的输入")
			return
		# 调用Motion类的clear_comments方法,清除评论
		client.Motion().clear_comments(source=source, action_type=action_type)  # type: ignore  # noqa: F405, PGH003
	except Exception as e:
		print(f"清除评论失败: {e}")


def clear_red_point() -> None:
	"""尝试执行清除红点操作"""
	try:
		method = input("请输入方法 (nemo/web): ")
		# 判断输入是否有效
		if method not in ["nemo", "web"]:
			print("无效的输入")
			return
		# 调用Motion类的clear_red_point方法,传入方法参数
		client.Motion().clear_red_point(method=method)  # type: ignore  # noqa: F405, PGH003
	except Exception as e:
		# 如果出现异常,则输出清除邮箱红点失败的信息
		print(f"清除邮箱红点失败: {e}")


def reply_work() -> None:
	"""尝试执行自动回复操作"""
	try:
		client.Motion().reply_work()  # noqa: F405
	except Exception as e:
		print(f"自动回复失败: {e}")


def handle_report() -> None:
	"""尝试执行处理举报操作"""
	try:
		token = input("请输入 Authorization: ")
		whale.Routine().set_token(token=token)  # noqa: F405
		admin_id = int(input("请输入管理员ID: "))
		client.Motion().handle_report(admin_id=admin_id)  # noqa: F405
	except Exception as e:
		print(f"处理举报失败: {e}")


def check_account_status() -> None:
	"""尝试查看账户状态"""
	try:
		status = client.Motion().get_account_status()  # noqa: F405
		print(f"账户状态: {status}")
	except Exception as e:
		print(f"获取账户状态失败: {e}")


def logout() -> None:
	"""尝试执行登出操作"""
	try:
		method = input("请输入方法 (web): ")
		if method != "web":
			print("无效的输入")
			return
		# 调用community.Login().logout()方法,传入method参数
		community.Login().logout(method=method)  # noqa: F405
	# 捕获异常,并输出错误信息
	except Exception as e:
		print(f"登出失败: {e}")


def main() -> None:
	"""主函数"""
	client.Index().index()  # noqa: F405
	while True:
		print("\n请选择操作:")
		print("1. 登录")
		print("2. 清除评论")
		print("3. 清除邮箱红点")
		print("4. 自动回复")
		print("5. 登出")
		print("6. 处理举报")
		print("7. 查看账户状态")
		print("8. 退出")

		choice = input("请输入选择 (1-8): ")
		print("*" * 50)

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
			break
		else:
			print("无效的选择, 请重新输入")


if __name__ == "__main__":
	main()
	input("按任意键退出")
