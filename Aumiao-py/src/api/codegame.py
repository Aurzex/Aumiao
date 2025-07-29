from typing import Literal

from src.utils import acquire
from src.utils.decorator import singleton


@singleton
class DataFetcher:
	def __init__(self) -> None:
		self.acquire = acquire.CodeMaoClient()

	def get_account_tiger(self) -> dict:
		response = self.acquire.send_request(endpoint="https://oversea-api.code.game/tiger/accounts", method="GET")
		return response.json()

	def get_config(self) -> dict:
		response = self.acquire.send_request(endpoint="https://oversea-api.code.game/config", method="GET")
		return response.json()


class UserAction:
	def __init__(self) -> None:
		self.acquire = acquire.CodeMaoClient()

	def send_register_email(self, email: str, password: str, pid: str = "LHnQoPMr", language: Literal["en"] = "en") -> bool:
		data = {"email": email, "language": language, "password": password, "pid": pid}
		response = self.acquire.send_request(endpoint="https://oversea-api.code.game/tiger/accounts/register/email", method="POST", payload=data)
		return response.status_code == acquire.HTTPSTATUS.CREATED.value

	def login(self, identity: str, password: str, pid: str = "LHnQoPMr") -> bool:
		data = {"identity": identity, "password": password, "pid": pid}
		response = self.acquire.send_request(endpoint="https://oversea-api.code.game/tiger/accounts/login", method="POST", payload=data)
		return response.status_code == acquire.HTTPSTATUS.OK.value
