import hashlib
import time
from random import randint
from typing import Any, Literal, cast

from src.utils import acquire, data, tool
from src.utils.decorator import singleton


def fetch_current_timestamp(client: acquire.CodeMaoClient) -> dict:
	"""获取当前服务器时间戳"""
	response = client.send_request(endpoint="/coconut/clouddb/currentTime", method="GET")
	return response.json()


@singleton
class AuthManager:
	"""
	用户登录管理器
	提供四种登录方式:简单密码登录、安全密码登录、token登录、cookie登录
	"""

	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()
		self.tool = tool
		self.setting = data.SettingManager().data

	def login(
		self,
		identity: str | None = None,
		password: str | None = None,
		token: str | None = None,
		cookies: str | None = None,
		pid: str = "65edCTyg",
		status: Literal["judgement", "average", "edu"] = "average",
		prefer_method: Literal["auto", "simple_password", "secure_password", "token", "cookies"] = "auto",
	) -> dict[str, Any]:
		"""
		整合登录方法
		参数:
			identity: 用户身份标识(手机号/邮箱)
			password: 用户密码
			token: 用户token
			cookies: 用户cookies字符串
			pid: 请求的PID,默认为"65edCTyg"
			status: 账号状态类型
			prefer_method: 优先使用的登录方式,auto为自动选择
		返回:
			登录结果信息
		"""
		# 自动选择登录方式
		if prefer_method == "auto":
			prefer_method = self._determine_login_method(token, cookies, identity, password)
		try:
			return self._execute_login(prefer_method, identity, password, token, cookies, pid, status)
		except Exception as e:
			print(f"登录失败: {e}")
			# 如果首选方式失败,尝试备用方式
			if prefer_method != "simple_password" and identity and password:
				print("尝试使用简单密码登录作为备用方案...")
				return self._authenticate_with_simple_password(identity, password, pid, status)
			raise

	@staticmethod
	def _determine_login_method(
		token: str | None,
		cookies: str | None,
		identity: str | None,
		password: str | None,
	) -> Literal["simple_password", "secure_password", "token", "cookies"]:
		"""确定登录方式"""
		if token:
			return "token"
		if cookies:
			return "cookies"
		if identity and password:
			return "secure_password"  # 默认使用安全密码登录流程
		msg = "缺少必要的登录凭据"
		raise ValueError(msg)

	def _execute_login(
		self,
		method: Literal["simple_password", "secure_password", "token", "cookies"],
		identity: str | None,
		password: str | None,
		token: str | None,
		cookies: str | None,
		pid: str,
		status: Literal["judgement", "average", "edu"],
	) -> dict[str, Any]:
		"""执行登录操作"""
		login_methods = {
			"simple_password": lambda: self._authenticate_with_simple_password(cast("str", identity), cast("str", password), pid, status),
			"secure_password": lambda: self._authenticate_with_secure_password(cast("str", identity), cast("str", password), pid, status),
			"token": lambda: self._login_with_token(cast("str", token), status),
			"cookies": lambda: self._login_with_cookies(cast("str", cookies), status),
		}
		if method in login_methods:
			return login_methods[method]()
		msg = f"不支持的登录方式: {method}"
		raise ValueError(msg)

	def _login_with_token(self, token: str, status: Literal["judgement", "average", "edu"]) -> dict[str, Any]:
		"""使用现有token直接登录"""
		if not token:
			msg = "Token不能为空"
			raise ValueError(msg)
		# 验证token有效性并获取完整认证信息
		auth_details = self.fetch_auth_details(token)
		self._client.switch_identity(token=token, identity=status)
		return {"success": True, "method": "token", "token": token, "auth_details": auth_details, "message": "Token登录成功"}

	def _login_with_cookies(self, cookies: str, status: Literal["judgement", "average", "edu"]) -> dict[str, Any]:
		"""使用cookies登录"""
		if not cookies:
			msg = "Cookies不能为空"
			raise ValueError(msg)
		result = self._authenticate_with_cookies(cookies, status)
		if result is False:
			msg = "Cookie登录失败"
			raise ValueError(msg)
		return {"success": True, "method": "cookies", "message": "Cookie登录成功"}

	def _authenticate_with_simple_password(
		self,
		identity: str,
		password: str,
		pid: str = "65edCTyg",
		status: Literal["judgement", "average", "edu"] = "average",
	) -> dict[str, Any]:
		"""简单密码登录 - 使用直接密码验证流程"""
		if not identity or not password:
			msg = "用户名和密码不能为空"
			raise ValueError(msg)
		self._client.switch_identity(token="", identity="blank")
		response = self._client.send_request(
			endpoint="/tiger/v3/web/accounts/login",
			method="POST",
			payload={
				"identity": identity,
				"password": password,
				"pid": pid,
			},
		)
		response_data = response.json()
		self._client.switch_identity(token=response_data["auth"]["token"], identity=status)
		return {"success": True, "method": "simple_password", "data": response_data, "message": "简单密码登录成功"}

	def _authenticate_with_secure_password(
		self,
		identity: str,
		password: str,
		pid: str = "65edCTyg",
		status: Literal["judgement", "average", "edu"] = "average",
	) -> dict[str, Any]:
		"""安全密码登录 - 使用带验证流程的密码登录"""
		if not identity or not password:
			msg = "用户名和密码不能为空"
			raise ValueError(msg)
		timestamp = fetch_current_timestamp(self._client)["data"]
		response = self._get_login_ticket(identity=identity, timestamp=timestamp, pid=pid)
		ticket = response["ticket"]
		resp = self._get_login_security_info(identity=identity, password=password, ticket=ticket, pid=pid)
		self._client.switch_identity(token=resp["auth"]["token"], identity=status)
		return {"success": True, "method": "secure_password", "data": resp, "message": "安全密码登录成功"}

	def _authenticate_with_cookies(
		self,
		cookies: str,
		status: Literal["judgement", "average", "edu"] = "average",
	) -> bool | None:
		"""cookie登录实现"""
		try:
			cookie_dict = dict([item.split("=", 1) for item in cookies.split("; ")])
		except (KeyError, ValueError) as err:
			print(f"Cookie格式错误: {err}")
			return False
		self._client.send_request(
			endpoint=self.setting.PARAMETER.cookie_check_url,
			method="POST",
			payload={},
			headers={**self._client.headers, "cookie": cookies},
		)
		self._client.switch_identity(token=cookie_dict["authorization"], identity=status)
		return None

	def fetch_auth_details(self, token: str) -> dict[str, Any]:
		"""获取认证详情"""
		token_ca = {"authorization": token}
		cookie_str = self.tool.DataConverter().convert_cookie(token_ca)
		headers = {**self._client.headers, "cookie": cookie_str}
		response = self._client.send_request(method="GET", endpoint="/web/users/details", headers=headers)
		auth = dict(response.cookies)
		return {**token_ca, **auth}

	def execute_logout(self, method: Literal["web", "app"]) -> bool:
		"""执行登出操作"""
		response = self._client.send_request(
			endpoint=f"/tiger/v3/{method}/accounts/logout",
			method="POST",
			payload={},
		)
		return response.status_code == acquire.HTTPStatus.NO_CONTENT.value

	def _get_login_security_info(
		self,
		identity: str,
		password: str,
		ticket: str,
		pid: str = "65edCTyg",
		agreement_ids: list[int] | None = None,
	) -> dict[str, Any]:
		"""获取登录安全信息"""
		if agreement_ids is None:
			agreement_ids = [-1]
		data = {
			"identity": identity,
			"password": password,
			"pid": pid,
			"agreement_ids": agreement_ids,
		}
		response = self._client.send_request(
			endpoint="/tiger/v3/web/accounts/login/security",
			method="POST",
			payload=data,
			headers={**self._client.headers, "x-captcha-ticket": ticket},
		)
		return response.json()

	def _get_login_ticket(
		self,
		identity: str | int,
		timestamp: int,
		scene: str | None = None,
		pid: str = "65edCTyg",
		device_id: str | None = None,
	) -> dict[str, Any]:
		"""获取登录票据"""
		data = {
			"identity": identity,
			"scene": scene,
			"pid": pid,
			"deviceId": device_id,
			"timestamp": timestamp,
		}
		response = self._client.send_request(
			endpoint="https://open-service.codemao.cn/captcha/rule/v3",
			method="POST",
			payload=data,
		)
		return response.json()


class CloudAuthenticator:
	"""云服务认证管理器"""

	CLIENT_SECRET = "pBlYqXbJDu"  # noqa: S105

	def __init__(self, authorization_token: str | None = None) -> None:
		self.authorization_token = authorization_token
		self.client_id = self._generate_client_id()
		self.time_difference = 0

	@staticmethod
	def _generate_client_id(length: int = 8) -> str:
		"""生成客户端ID"""
		chars = "abcdefghijklmnopqrstuvwxyz0123456789"
		return "".join(chars[randint(0, 35)] for _ in range(length))

	def get_calibrated_timestamp(self) -> int:
		"""获取校准后的时间戳"""
		if self.time_difference == 0:
			server_time = fetch_current_timestamp(self._client)["data"]
			local_time = int(time.time())
			self.time_difference = local_time - server_time
		return int(time.time()) - self.time_difference

	def generate_x_device_auth(self) -> dict[str, str | int]:
		"""生成设备认证信息"""
		timestamp = self.get_calibrated_timestamp()
		sign_str = f"{self.CLIENT_SECRET}{timestamp}{self.client_id}"
		sign = hashlib.sha256(sign_str.encode()).hexdigest().upper()
		return {"sign": sign, "timestamp": timestamp, "client_id": self.client_id}

	@property
	def _client(self) -> acquire.CodeMaoClient:
		"""获取客户端实例的兼容性属性"""
		# 这里需要根据实际情况调整,确保能获取到客户端实例
		return acquire.CodeMaoClient()
