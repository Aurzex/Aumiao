from collections.abc import Generator
from typing import Literal

from src.utils import acquire, tool
from src.utils.acquire import HTTPSTATUS
from src.utils.decorator import singleton


@singleton
class Routine:
	# 初始化方法,创建CodeMaoClient和CodeMaoProcess对象
	def __init__(self) -> None:
		self.acquire = acquire.CodeMaoClient()
		self.tool_process = tool.CodeMaoProcess()

	# 登录方法,传入用户名、密码、key和code,发送POST请求,更新cookies
	def login(self, username: str, password: str, key: int, code: str) -> None:
		data = {"username": username, "password": password, "key": key, "code": code}
		response = self.acquire.send_request(endpoint="https://api-whale.codemao.cn/admins/login", method="POST", payload=data)
		self.acquire.update_cookies(response.cookies)

	# 登出方法,发送DELETE请求,返回状态码是否为204
	def logout(self) -> bool:
		response = self.acquire.send_request(endpoint="https://api-whale.codemao.cn/admins/logout", method="DELETE", payload={})
		return response.status_code == HTTPSTATUS.NO_CONTENT

	# 获取数据信息方法,发送GET请求,返回json数据
	def get_data_info(self) -> dict:
		response = self.acquire.send_request(endpoint="https://api-whale.codemao.cn/admins/info", method="GET")
		return response.json()

	def set_token(self, token: str) -> None:
		self.acquire.headers["Authorization"] = f"Bearer {token}"


@singleton
class Obtain:
	def __init__(self) -> None:
		# 初始化获取数据客户端
		self.acquire = acquire.CodeMaoClient()
		# 初始化工具处理
		self.tool_process = tool.CodeMaoProcess()

	# 获取编程作品举报
	def get_work_report(
		self,
		types: Literal["KITTEN", "BOX2", "ALL"],
		status: Literal["TOBEDONE", "DONE", "ALL"],
		method: Literal["admin_id", "work_user_id", "work_id"] | None = None,
		target_id: int | None = None,
		limit: int | None = 15,
	) -> Generator:
		# 构造请求参数
		params = {"type": types, "status": status, method: target_id, "offset": 0, "limit": 15}
		# 获取数据
		return self.acquire.fetch_data(endpoint="https://api-whale.codemao.cn/reports/works/search", params=params, limit=limit)

	# 获取评论举报
	def get_comment_report(
		self,
		types: Literal["ALL", "KITTEN", "BOX2", "FICTION", "COMIC", "WORK_SUBJECT"],
		status: Literal["TOBEDONE", "DONE", "ALL"],
		method: Literal["admin_id", "comment_user_id", "comment_id"] | None = None,
		target_id: int | None = None,
		limit: int | None = 15,
	) -> Generator[dict]:
		params = {"source": types, "status": status, method: target_id, "offset": 0, "limit": 15}
		# url可以为https://api-whale.codemao.cn/reports/comments/search
		# 或者https://api-whale.codemao.cn/reports/comments
		return self.acquire.fetch_data(endpoint="https://api-whale.codemao.cn/reports/comments/search", params=params, limit=limit)

	# 获取帖子举报
	def get_post_report(
		self,
		status: Literal["TOBEDONE", "DONE", "ALL"],
		method: Literal["post_id"] | None = None,
		target_id: int | None = None,
		limit: int | None = 15,
	) -> Generator[dict]:
		params = {"status": status, method: target_id, "offset": 0, "limit": 15}
		return self.acquire.fetch_data(endpoint="https://api-whale.codemao.cn/reports/posts", params=params, limit=limit)

	# 获取讨论区举报
	def get_discussion_report(
		self,
		status: Literal["TOBEDONE", "DONE", "ALL"],
		method: Literal["post_id"] | None = None,
		target_id: int | None = None,
		limit: int | None = 15,
	) -> Generator[dict]:
		params = {"status": status, method: target_id, "offset": 0, "limit": 15}
		return self.acquire.fetch_data(endpoint="https://api-whale.codemao.cn/reports/posts/discussions", params=params, limit=limit)


class Motion:
	def __init__(self) -> None:
		self.acquire = acquire.CodeMaoClient()

	# created_at是举报时间,updated_at是处理时间

	# 处理帖子举报
	def handle_post_report(self, report_id: int, admin_id: int, status: Literal["PASS", "DELETE", "MUTE_SEVEN_DAYS", "MUTE_THREE_MONTHS"]) -> bool:
		response = self.acquire.send_request(
			endpoint=f"https://api-whale.codemao.cn/reports/posts/{report_id}",
			method="PATCH",
			payload={"admin_id": admin_id, "status": status},
		)
		return response.status_code == HTTPSTATUS.NO_CONTENT

	# 处理讨论区举报
	def handle_discussion_report(self, report_id: int, admin_id: int, status: Literal["PASS", "DELETE", "MUTE_SEVEN_DAYS", "MUTE_THREE_MONTHS"]) -> bool:
		response = self.acquire.send_request(
			endpoint=f"https://api-whale.codemao.cn/reports/posts/discussions/{report_id}",
			method="PATCH",
			payload={"admin_id": admin_id, "status": status},
		)
		return response.status_code == HTTPSTATUS.NO_CONTENT

	# 处理评论举报
	def handle_comment_report(self, report_id: int, admin_id: int, status: Literal["PASS", "DELETE", "MUTE_SEVEN_DAYS", "MUTE_THREE_MONTHS"]) -> bool:
		response = self.acquire.send_request(
			endpoint=f"https://api-whale.codemao.cn/reports/comments/{report_id}",
			method="PATCH",
			payload={"admin_id": admin_id, "status": status},
		)
		return response.status_code == HTTPSTATUS.NO_CONTENT

	# 处理作品举报
	def handle_work_report(self, report_id: int, admin_id: int, status: Literal["PASS", "DELETE", "UNLOAD"]) -> bool:
		response = self.acquire.send_request(
			endpoint=f"https://api-whale.codemao.cn/reports/works/{report_id}",
			method="PATCH",
			payload={"admin_id": admin_id, "status": status},
		)
		return response.status_code == HTTPSTATUS.NO_CONTENT
