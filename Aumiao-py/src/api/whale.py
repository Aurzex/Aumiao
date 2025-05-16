from collections.abc import Generator
from pathlib import Path
from typing import Literal

from src.utils import acquire, data, file, tool
from src.utils.acquire import HTTPSTATUS
from src.utils.decorator import singleton

from . import community

CAPTCHA_DIR: Path = data.CURRENT_DIR / "captcha"
CAPTCHA_DIR.mkdir(parents=True, exist_ok=True)
CAPTCHA_IMG_DIR: Path = CAPTCHA_DIR / f"{tool.TimeUtils().current_timestamp()}.jpg"


@singleton
class Routine:
	def __init__(self) -> None:
		self.acquire = acquire.CodeMaoClient()

	def login(self, username: str, password: str, key: int, code: str) -> dict:
		data = {"username": username, "password": password, "key": key, "code": code}
		response = self.acquire.send_request(endpoint="https://api-whale.codemao.cn/admins/login", method="POST", payload=data)
		return response.json()
		# self.acquire.update_cookies(response.cookies)

	def logout(self) -> bool:
		response = self.acquire.send_request(endpoint="https://api-whale.codemao.cn/admins/logout", method="DELETE", payload={})
		return response.status_code == HTTPSTATUS.NO_CONTENT.value

	def get_captcha(self) -> None:
		timestamp = community.Obtain().get_timestamp()["data"]
		response = self.acquire.send_request(endpoint=f"https://api-whale.codemao.cn/admins/captcha/{timestamp}", method="GET", log=False)
		if response.status_code == acquire.HTTPSTATUS.OK.value:
			file.CodeMaoFile().file_write(path=CAPTCHA_IMG_DIR, content=response.content, method="wb")
			print(f"请到{CAPTCHA_DIR}查看验证码")
		else:
			print(f"获取验证码失败, 错误代码{response.status_code}")

	def get_data_info(self) -> dict:
		response = self.acquire.send_request(endpoint="https://api-whale.codemao.cn/admins/info", method="GET")
		return response.json()

	def set_token(self, token: str) -> None:
		self.acquire.switch_account(token, "judgement")
		# self.acquire.headers["Authorization"] = f"Bearer {token}"


@singleton
class Obtain:
	def __init__(self) -> None:
		self.acquire = acquire.CodeMaoClient()

	# 获取编程作品举报
	def get_work_report(
		self,
		types: Literal["KITTEN", "BOX2", "ALL"],
		status: Literal["TOBEDONE", "DONE", "ALL"],
		method: Literal["admin_id", "work_user_id", "work_id"] | None = None,
		target_id: int | None = None,
		limit: int | None = 15,
	) -> Generator:
		params = {"type": types, "status": status, method: target_id, "offset": 0, "limit": 15}
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
		return response.status_code == HTTPSTATUS.NO_CONTENT.value

	# 处理讨论区举报
	def handle_discussion_report(self, report_id: int, admin_id: int, status: Literal["PASS", "DELETE", "MUTE_SEVEN_DAYS", "MUTE_THREE_MONTHS"]) -> bool:
		response = self.acquire.send_request(
			endpoint=f"https://api-whale.codemao.cn/reports/posts/discussions/{report_id}",
			method="PATCH",
			payload={"admin_id": admin_id, "status": status},
		)
		return response.status_code == HTTPSTATUS.NO_CONTENT.value

	# 处理评论举报
	def handle_comment_report(self, report_id: int, admin_id: int, status: Literal["PASS", "DELETE", "MUTE_SEVEN_DAYS", "MUTE_THREE_MONTHS"]) -> bool:
		response = self.acquire.send_request(
			endpoint=f"https://api-whale.codemao.cn/reports/comments/{report_id}",
			method="PATCH",
			payload={"admin_id": admin_id, "status": status},
		)
		return response.status_code == HTTPSTATUS.NO_CONTENT.value

	# 处理作品举报
	def handle_work_report(self, report_id: int, admin_id: int, status: Literal["PASS", "DELETE", "UNLOAD"]) -> bool:
		response = self.acquire.send_request(
			endpoint=f"https://api-whale.codemao.cn/reports/works/{report_id}",
			method="PATCH",
			payload={"admin_id": admin_id, "status": status},
		)
		return response.status_code == HTTPSTATUS.NO_CONTENT.value
