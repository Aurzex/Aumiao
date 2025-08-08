from collections.abc import Generator
from pathlib import Path
from typing import Literal

from requests.cookies import RequestsCookieJar

from src.utils import acquire, data, file, tool
from src.utils.acquire import HTTPSTATUS
from src.utils.decorator import singleton

CAPTCHA_DIR: Path = data.CURRENT_DIR / "captcha"
CAPTCHA_DIR.mkdir(parents=True, exist_ok=True)


@singleton
class AuthManager:
	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()
		self._captcha_img_path = CAPTCHA_DIR / f"{tool.TimeUtils().current_timestamp()}.jpg"

	def authenticate_user(self, username: str, password: str, key: int, code: str) -> dict:
		payload = {"username": username, "password": password, "key": key, "code": code}
		response = self._client.send_request(endpoint="https://api-whale.codemao.cn/admins/login", method="POST", payload=payload)
		return response.json()

	def terminate_session(self) -> bool:
		response = self._client.send_request(endpoint="https://api-whale.codemao.cn/admins/logout", method="DELETE")
		return response.status_code == HTTPSTATUS.NO_CONTENT.value

	def fetch_verification_captcha(self, timestamp: int) -> RequestsCookieJar:
		response = self._client.send_request(endpoint=f"https://api-whale.codemao.cn/admins/captcha/{timestamp}", method="GET", log=False)
		if response.status_code == HTTPSTATUS.OK.value:
			file.CodeMaoFile().file_write(path=self._captcha_img_path, content=response.content, method="wb")
			print(f"请到 {CAPTCHA_DIR} 查看验证码")
		else:
			print(f"获取验证码失败, 错误代码{response.status_code}")
		return response.cookies

	def fetch_user_dashboard_data(self) -> dict:
		response = self._client.send_request(endpoint="https://api-whale.codemao.cn/admins/info", method="GET")
		return response.json()

	def configure_authentication_token(self, token: str) -> None:
		self._client.switch_account(token, "judgement")


@singleton
class ReportFetcher:
	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()

	def fetch_work_reports_gen(
		self,
		report_type: Literal["KITTEN", "BOX2", "ALL"],
		status: Literal["TOBEDONE", "DONE", "ALL"],
		filter_type: Literal["admin_id", "work_user_id", "work_id"] | None = None,
		target_id: int | None = None,
		limit: int | None = 15,
		offset: int = 0,
	) -> Generator[dict]:
		params = {"type": report_type, "status": status, filter_type: target_id, "offset": offset, "limit": 15}
		return self._client.fetch_data(endpoint="https://api-whale.codemao.cn/reports/works/search", params=params, limit=limit)

	def fetch_comment_reports_gen(
		self,
		source_type: Literal["ALL", "KITTEN", "BOX2", "FICTION", "COMIC", "WORK_SUBJECT"],
		status: Literal["TOBEDONE", "DONE", "ALL"],
		filter_type: Literal["admin_id", "comment_user_id", "comment_id"] | None = None,
		target_id: int | None = None,
		limit: int | None = 15,
		offset: int = 0,
	) -> Generator[dict]:
		params = {"source": source_type, "status": status, filter_type: target_id, "offset": offset, "limit": 15}
		return self._client.fetch_data(endpoint="https://api-whale.codemao.cn/reports/comments/search", params=params, limit=limit)

	def fetch_post_reports_gen(
		self,
		status: Literal["TOBEDONE", "DONE", "ALL"],
		filter_type: Literal["post_id"] | None = None,
		target_id: int | None = None,
		limit: int | None = 15,
		offset: int = 0,
	) -> Generator[dict]:
		params = {"status": status, filter_type: target_id, "offset": offset, "limit": 15}
		return self._client.fetch_data(endpoint="https://api-whale.codemao.cn/reports/posts", params=params, limit=limit)

	def fetch_discussion_reports_gen(
		self,
		status: Literal["TOBEDONE", "DONE", "ALL"],
		filter_type: Literal["post_id"] | None = None,
		target_id: int = 15,
		limit: int | None = 15,
		offset: int = 0,
	) -> Generator[dict]:
		params = {"status": status, filter_type: target_id, "offset": offset, "limit": 15}
		return self._client.fetch_data(endpoint="https://api-whale.codemao.cn/reports/posts/discussions", params=params, limit=limit)


class ReportHandler:
	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()

	def execute_process_post_report(self, report_id: int, admin_id: int, resolution: Literal["PASS", "DELETE", "MUTE_SEVEN_DAYS", "MUTE_THREE_MONTHS"]) -> bool:
		response = self._client.send_request(
			endpoint=f"https://api-whale.codemao.cn/reports/posts/{report_id}",
			method="PATCH",
			payload={"admin_id": admin_id, "status": resolution},
		)
		return response.status_code == HTTPSTATUS.NO_CONTENT.value

	def execute_process_discussion_report(self, report_id: int, admin_id: int, resolution: Literal["PASS", "DELETE", "MUTE_SEVEN_DAYS", "MUTE_THREE_MONTHS"]) -> bool:
		response = self._client.send_request(
			endpoint=f"https://api-whale.codemao.cn/reports/posts/discussions/{report_id}",
			method="PATCH",
			payload={"admin_id": admin_id, "status": resolution},
		)
		return response.status_code == HTTPSTATUS.NO_CONTENT.value

	def execute_process_comment_report(self, report_id: int, admin_id: int, resolution: Literal["PASS", "DELETE", "MUTE_SEVEN_DAYS", "MUTE_THREE_MONTHS"]) -> bool:
		response = self._client.send_request(
			endpoint=f"https://api-whale.codemao.cn/reports/comments/{report_id}",
			method="PATCH",
			payload={"admin_id": admin_id, "status": resolution},
		)
		return response.status_code == HTTPSTATUS.NO_CONTENT.value

	def execute_process_work_report(self, report_id: int, admin_id: int, resolution: Literal["PASS", "DELETE", "UNLOAD"]) -> bool:
		response = self._client.send_request(
			endpoint=f"https://api-whale.codemao.cn/reports/works/{report_id}",
			method="PATCH",
			payload={"admin_id": admin_id, "status": resolution},
		)
		return response.status_code == HTTPSTATUS.NO_CONTENT.value
