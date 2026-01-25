import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from http import HTTPStatus
from random import randint
from typing import Any, Literal

from aumiao.utils import acquire, data, file, tool
from aumiao.utils.decorator import singleton


# ==================== 基础数据结构和枚举 ====================
class LoginMethod(Enum):
	"""登录方法枚举"""

	SIMPLE_PASSWORD = "simple_password"
	SECURE_PASSWORD = "secure_password"
	TOKEN = "token"
	COOKIES = "cookies"
	ADMIN_TOKEN = "admin_token"
	ADMIN_PASSWORD = "admin_password"


class UserRole(Enum):
	"""用户角色枚举"""

	USER = "user"
	ADMIN = "admin"


class AccountStatus(Enum):
	"""账号状态枚举"""

	JUDGEMENT = "judgement"
	AVERAGE = "average"
	EDU = "edu"


@dataclass
class LoginCredentials:
	"""登录凭证数据类"""

	identity: str = ""
	password: str = ""
	token: str = ""
	cookies: str = ""
	pid: str = "65edCTyg"
	status: AccountStatus = AccountStatus.AVERAGE
	role: UserRole = UserRole.USER


@dataclass
class LoginResult:
	"""登录结果数据类"""

	success: bool
	method: LoginMethod
	message: str
	token: str = ""
	data: dict[str, Any] = field(default_factory=dict)
	auth_details: dict[str, Any] | None = None


# ==================== 辅助函数 ====================
def fetch_current_timestamp(client: acquire.CodeMaoClient) -> int:
	"""获取当前服务器时间戳"""
	response = client.send_request(endpoint="/coconut/clouddb/currentTime", method="GET")
	return response.json()["data"]


def determine_login_method(token: str | None, cookies: str | None, identity: str | None, password: str | None) -> LoginMethod:
	"""确定登录方法"""
	if token:
		return LoginMethod.TOKEN
	if cookies:
		return LoginMethod.COOKIES
	if identity and password:
		return LoginMethod.SECURE_PASSWORD
	msg = "缺少必要的登录凭据"
	raise ValueError(msg)


def parse_cookies(cookies_str: str) -> dict[str, str]:
	"""解析 cookies 字符串"""
	try:
		return dict(item.strip().split("=", 1) for item in cookies_str.split(";"))
	except ValueError as e:
		msg = f"Cookie 格式错误: {e}"
		raise ValueError(msg)  # noqa: B904


# ==================== 认证处理器 ====================
class AuthProcessor:
	"""认证处理器, 负责具体的认证逻辑"""

	CLIENT_SECRET = "pBlYqXbJDu"

	def __init__(self, client: acquire.CodeMaoClient) -> None:
		self.client = client
		self.tool = tool
		self.setting = data.SettingManager().data
		self.captcha_img_path = data.PathConfig().CAPTCHA_FILE_PATH

	def fetch_auth_details(self, token: str) -> dict[str, Any]:
		"""获取认证详情"""
		token_ca = {"authorization": token}
		cookie_str = self.tool.DataConverter().convert_cookie(token_ca)
		headers = {**self.client.headers, "cookie": cookie_str}
		response = self.client.send_request(
			method="GET",
			endpoint="/web/users/details",
			headers=headers,
		)
		auth = dict(response.cookies)
		return {**token_ca, **auth}

	def get_login_security_info(self, identity: str, password: str, ticket: str, pid: str = "65edCTyg") -> dict[str, Any]:
		"""获取登录安全信息"""
		data = {
			"identity": identity,
			"password": password,
			"pid": pid,
			"agreement_ids": [-1],
		}
		response = self.client.send_request(
			endpoint="/tiger/v3/web/accounts/login/security",
			method="POST",
			payload=data,
			headers={**self.client.headers, "x-captcha-ticket": ticket},
		)
		return response.json()

	def get_login_ticket(self, identity: str, timestamp: int, pid: str = "65edCTyg") -> dict[str, Any]:
		"""获取登录票据"""
		data = {
			"identity": identity,
			"pid": pid,
			"timestamp": timestamp,
		}
		response = self.client.send_request(
			endpoint="https://open-service.codemao.cn/captcha/rule/v3",
			method="POST",
			payload=data,
		)
		return response.json()

	def authenticate_admin_user(self, username: str, password: str, key: int, code: str) -> dict[str, Any]:
		"""管理员用户认证"""
		payload = {"username": username, "password": password, "key": key, "code": code}
		response = self.client.send_request(
			endpoint="https://api-whale.codemao.cn/admins/login",
			method="POST",
			payload=payload,
		)
		return response.json()

	def fetch_admin_captcha(self, timestamp: int) -> Any:
		"""获取管理员验证码"""
		response = self.client.send_request(
			endpoint=f"https://api-whale.codemao.cn/admins/captcha/{timestamp}",
			method="GET",
			log=False,
		)
		if response.status_code == HTTPStatus.OK.value:
			file.CodeMaoFile().file_write(
				path=self.captcha_img_path,
				content=response.content,
				method="wb",
			)
			print(f"验证码已保存至: {self.captcha_img_path}")
		else:
			print(f"获取验证码失败, 错误代码: {response.status_code}")
		return response.cookies


# ==================== 登录处理器 ====================
class LoginHandler:
	"""登录处理器, 负责执行具体的登录操作"""

	def __init__(self, client: acquire.CodeMaoClient, processor: AuthProcessor) -> None:
		self.client = client
		self.processor = processor
		self.tool = tool

	def handle_simple_password(self, identity: str, password: str, pid: str, status: AccountStatus) -> LoginResult:
		"""处理简单密码登录"""
		self.client.switch_identity(token="", identity="blank")
		response = self.client.send_request(
			endpoint="/tiger/v3/web/accounts/login",
			method="POST",
			payload={"identity": identity, "password": password, "pid": pid},
		)
		response_data = response.json()
		self.client.switch_identity(token=response_data["auth"]["token"], identity=status.value)
		return LoginResult(success=True, method=LoginMethod.SIMPLE_PASSWORD, message="简单密码登录成功", data=response_data)

	def handle_secure_password(self, identity: str, password: str, pid: str, status: AccountStatus) -> LoginResult:
		"""处理安全密码登录"""
		timestamp = fetch_current_timestamp(self.client)
		ticket_response = self.processor.get_login_ticket(identity, timestamp, pid)
		ticket = ticket_response["ticket"]
		response = self.processor.get_login_security_info(identity, password, ticket, pid)
		self.client.switch_identity(token=response["auth"]["token"], identity=status.value)
		return LoginResult(success=True, method=LoginMethod.SECURE_PASSWORD, message="安全密码登录成功", data=response)

	def handle_token(self, token: str, status: AccountStatus) -> LoginResult:
		"""处理 token 登录"""
		auth_details = self.processor.fetch_auth_details(token)
		self.client.switch_identity(token=token, identity=status.value)
		return LoginResult(success=True, method=LoginMethod.TOKEN, message="Token 登录成功", token=token, auth_details=auth_details)

	def handle_cookies(self, cookies: str, status: AccountStatus) -> LoginResult:
		"""处理 cookies 登录"""
		cookie_dict = parse_cookies(cookies)
		self.client.send_request(
			endpoint=self.processor.setting.PARAMETER.cookie_check_url,
			method="POST",
			payload={},
			headers={**self.client.headers, "cookie": cookies},
		)
		self.client.switch_identity(token=cookie_dict["authorization"], identity=status.value)
		return LoginResult(success=True, method=LoginMethod.COOKIES, message="Cookie 登录成功")

	def handle_admin_token(self, token: str) -> LoginResult:
		"""处理管理员 token 登录"""
		if not token:
			token = input("请输入 Authorization Token:")
		self.client.switch_identity(token=token, identity="judgement")
		return LoginResult(success=True, method=LoginMethod.ADMIN_TOKEN, message="管理员 Token 登录成功", token=token)

	def handle_admin_password(self, username: str | None, password: str | None) -> LoginResult:
		"""处理管理员密码登录"""
		username_input = username or input("请输入用户名:")
		password_input = password or input("请输入密码:")
		while True:
			timestamp = self.tool.TimeUtils().current_timestamp(13)
			print("正在获取验证码...")
			self.processor.fetch_admin_captcha(timestamp)
			captcha = input("请输入验证码:")
			response = self.processor.authenticate_admin_user(username_input, password_input, timestamp, captcha)
			if "token" in response:
				self.client.switch_identity(token=response["token"], identity="judgement")
				return LoginResult(success=True, method=LoginMethod.ADMIN_PASSWORD, message="管理员账密登录成功", token=response["token"])
			print(f"登录失败: {response.get('error_msg', ' 未知错误 ')}")
			if response.get("error_code") in {"Admin-Password-Error@Community-Admin", "Param-Invalid@Common"}:
				username_input = input("请输入用户名:")
				password_input = input("请输入密码:")


# ==================== 主认证管理器 ====================
@singleton
class AuthManager:
	"""
	统一认证管理器
	支持普通用户和管理员两种角色的登录
	"""

	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()
		self._processor = AuthProcessor(self._client)
		self._handler = LoginHandler(self._client, self._processor)
		self._current_credentials: LoginCredentials | None = None

	def login(
		self,
		identity: str = "",
		password: str = "",
		token: str = "",
		cookies: str = "",
		pid: str = "65edCTyg",
		status: Literal["judgement", "average", "edu"] = "average",
		role: Literal["user", "admin"] = "user",
		prefer_method: str | None = None,
	) -> LoginResult:
		"""
		统一的登录接口
		参数:
			identity: 用户身份标识
			password: 用户密码
			token: 用户 token
			cookies: 用户 cookies 字符串
			pid: 请求的 PID
			status: 账号状态类型
			role: 用户角色
			prefer_method: 优先使用的登录方式
		返回:
			登录结果
		"""
		credentials = LoginCredentials(identity=identity, password=password, token=token, cookies=cookies, pid=pid, status=AccountStatus(status), role=UserRole(role))
		self._current_credentials = credentials
		if credentials.role == UserRole.ADMIN:
			return self._admin_login(credentials, prefer_method)
		return self._user_login(credentials, prefer_method)

	def _user_login(self, credentials: LoginCredentials, prefer_method: str | None) -> LoginResult:
		"""用户登录"""
		method = self._get_user_login_method(credentials, prefer_method)
		if method == LoginMethod.SIMPLE_PASSWORD:
			return self._handler.handle_simple_password(credentials.identity, credentials.password, credentials.pid, credentials.status)
		if method == LoginMethod.SECURE_PASSWORD:
			return self._handler.handle_secure_password(credentials.identity, credentials.password, credentials.pid, credentials.status)
		if method == LoginMethod.TOKEN:
			return self._handler.handle_token(credentials.token, credentials.status)
		if method == LoginMethod.COOKIES:
			return self._handler.handle_cookies(credentials.cookies, credentials.status)
		msg = f"不支持的登录方式: {method}"
		raise ValueError(msg)

	def _admin_login(self, credentials: LoginCredentials, prefer_method: str | None) -> LoginResult:
		"""管理员登录"""
		method = self._get_admin_login_method(credentials, prefer_method)
		if method == LoginMethod.ADMIN_TOKEN:
			return self._handler.handle_admin_token(credentials.token)
		if method == LoginMethod.ADMIN_PASSWORD:
			return self._handler.handle_admin_password(credentials.identity, credentials.password)
		msg = f"不支持的管理员登录方式: {method}"
		raise ValueError(msg)

	@staticmethod
	def _get_user_login_method(credentials: LoginCredentials, prefer_method: str | None) -> LoginMethod:
		"""获取用户登录方法"""
		if prefer_method:
			return LoginMethod(prefer_method)
		return determine_login_method(credentials.token, credentials.cookies, credentials.identity, credentials.password)

	@staticmethod
	def _get_admin_login_method(credentials: LoginCredentials, prefer_method: str | None) -> LoginMethod:
		"""获取管理员登录方法"""
		if prefer_method:
			return LoginMethod(prefer_method)
		return LoginMethod.ADMIN_TOKEN if credentials.token else LoginMethod.ADMIN_PASSWORD

	def execute_logout(self, method: Literal["web", "app"]) -> bool:
		"""执行用户登出"""
		response = self._client.send_request(
			endpoint=f"/tiger/v3/{method}/accounts/logout",
			method="POST",
			payload={},
		)
		return response.status_code == acquire.HTTPStatus.NO_CONTENT.value

	def admin_logout(self) -> bool:
		"""管理员登出"""
		response = self._client.send_request(
			endpoint="https://api-whale.codemao.cn/admins/logout",
			method="DELETE",
		)
		return response.status_code == HTTPStatus.NO_CONTENT.value

	def fetch_admin_dashboard_data(self) -> dict[str, Any]:
		"""获取用户仪表板数据"""
		response = self._client.send_request(
			endpoint="https://api-whale.codemao.cn/admins/info",
			method="GET",
		)
		return response.json()

	def configure_authentication_token(self, token: str, identity: str = "judgement") -> None:
		"""配置认证 Token"""
		self._client.switch_identity(token=token, identity=identity)

	def restore_admin_account(self) -> None:
		"""恢复管理员账号"""
		self._client.switch_identity(
			token=self._client.token.judgement,
			identity="judgement",
		)

	def terminate_session(self, role: Literal["user", "admin"] = "user") -> None:
		"""终止当前会话并恢复管理员账号"""
		if role == "admin":
			self.admin_logout()
		else:
			self.execute_logout("web")
		self.restore_admin_account()
		print("已终止会话并恢复管理员账号")

	def get_current_client(self) -> acquire.CodeMaoClient:
		"""获取当前客户端"""
		return self._client


# ==================== 云服务认证器 ====================
class CloudAuthenticator:
	"""云服务认证管理器"""

	CLIENT_SECRET = "pBlYqXbJDu"

	def __init__(self, authorization_token: str | None = None) -> None:
		self.authorization_token = authorization_token
		self.client_id = self._generate_client_id()
		self.time_difference = 0
		self._client = acquire.CodeMaoClient()

	@staticmethod
	def _generate_client_id(length: int = 8) -> str:
		"""生成客户端 ID"""
		chars = "abcdefghijklmnopqrstuvwxyz0123456789"
		return "".join(chars[randint(0, 35)] for _ in range(length))

	def get_calibrated_timestamp(self) -> int:
		"""获取校准后的时间戳"""
		if self.time_difference == 0:
			server_time = fetch_current_timestamp(self._client)
			local_time = int(time.time())
			self.time_difference = local_time - server_time
		return int(time.time()) - self.time_difference

	def generate_x_device_auth(self) -> dict[str, str | int]:
		"""生成设备认证信息"""
		timestamp = self.get_calibrated_timestamp()
		sign_str = f"{self.CLIENT_SECRET}{timestamp}{self.client_id}"
		sign = hashlib.sha256(sign_str.encode()).hexdigest().upper()
		return {"sign": sign, "timestamp": timestamp, "client_id": self.client_id}
