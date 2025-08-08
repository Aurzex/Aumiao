from typing import Literal

from src.utils import acquire
from src.utils.decorator import singleton


@singleton
class OverseaDataClient:
	"""海外平台数据访问客户端"""

	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()

	def fetch_tiger_accounts(self) -> dict:
		"""获取Tiger账号信息"""
		response = self._client.send_request(endpoint="https://oversea-api.code.game/tiger/accounts", method="GET")
		return response.json()

	def fetch_platform_config(self) -> dict:
		"""获取平台配置信息"""
		response = self._client.send_request(endpoint="https://oversea-api.code.game/config", method="GET")
		return response.json()


class UserActionHandler:
	"""用户操作处理器"""

	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()

	def register_with_email(self, email: str, password: str, pid: str = "LHnQoPMr", language: Literal["en"] = "en") -> bool:
		"""
		通过邮箱注册账号

		Args:
			email: 用户邮箱
			password: 账号密码
			pid: 产品ID,默认"LHnQoPMr"
			language: 语言,目前仅支持"en"

		Returns:
			注册成功返回True,否则返回False
		"""
		payload = {"email": email, "language": language, "password": password, "pid": pid}
		response = self._client.send_request(endpoint="https://oversea-api.code.game/tiger/accounts/register/email", method="POST", payload=payload)
		return response.status_code == acquire.HTTPSTATUS.CREATED.value

	def authenticate_with_credentials(self, identity: str, password: str, pid: str = "LHnQoPMr") -> bool:
		"""
		使用账号密码登录

		Args:
			identity: 身份标识(邮箱或用户名)
			password: 账号密码
			pid: 产品ID,默认"LHnQoPMr"

		Returns:
			登录成功返回True,否则返回False
		"""
		payload = {"identity": identity, "password": password, "pid": pid}
		response = self._client.send_request(endpoint="https://oversea-api.code.game/tiger/accounts/login", method="POST", payload=payload)
		return response.status_code == acquire.HTTPSTATUS.OK.value
