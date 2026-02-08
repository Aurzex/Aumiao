from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
from http import HTTPStatus
from random import randint
from time import time
from typing import Any, Literal, cast

from aumiao.utils import acquire, data, tool
from aumiao.utils.decorator import singleton


# ==================== 基础数据结构和枚举 ====================
class LoginMethod(Enum):
	"""登录方法枚举"""

	PASSWORD_V0 = "password_v0"
	PASSWORD_V1 = "password_v1"
	PASSWORD_V2 = "password_v2"
	TOKEN = "token"
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


# 类型别名定义
StatusType = Literal["judgement", "average", "edu"]
RoleType = Literal["user", "admin"]
UserMethodType = Literal["password_v0", "password_v1", "password_v2", "token"]
AdminMethodType = Literal["admin_token", "admin_password"]
AllMethodType = Literal["password_v0", "password_v1", "password_v2", "token", "admin_token", "admin_password"]


@dataclass
class LoginCredentials:
	"""登录凭证数据类"""

	identity: str = ""
	password: str = ""
	token: str = ""
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


def determine_login_method(token: str | None, identity: str | None, password: str | None) -> UserMethodType:
	"""确定用户登录方法"""
	if token:
		return "token"
	if identity and password:
		return "password_v2"  # 默认使用 v2 登录
	msg = "缺少必要的登录凭据"
	raise ValueError(msg)


def determine_admin_login_method(token: str | None, identity: str | None, password: str | None) -> AdminMethodType:
	"""确定管理员登录方法"""
	if token:
		return "admin_token"
	if identity or password:
		return "admin_password"
	msg = "缺少必要的管理员登录凭据"
	raise ValueError(msg)


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
			data.CodeMaoFile().file_write(
				path=self.captcha_img_path,
				content=response.content,
				method="wb",
			)
			print(f"验证码已保存至: {self.captcha_img_path}")
		else:
			print(f"获取验证码失败, 错误代码: {response.status_code}")
		return response.cookies

	def handle_password_v0(self, identity: str, password: str, pid: str = "OqMVXvXp") -> dict[str, Any]:
		"""处理 v0 版本密码登录 (基础登录)"""
		payload = {"identity": identity, "password": password, "pid": pid}
		response = self.client.send_request(endpoint="/tiger/accounts/login", method="POST", payload=payload)
		return response.json()

	def handle_password_v1(self, identity: str, password: str, pid: str = "65edCTyg") -> dict[str, Any]:
		"""处理 v1 版本密码登录 - 使用 /tiger/v3/web/accounts/login 登录"""
		self.client.switch_identity(token="", identity="blank")
		response = self.client.send_request(
			endpoint="/tiger/v3/web/accounts/login",
			method="POST",
			payload={"identity": identity, "password": password, "pid": pid},
		)
		return response.json()

	def handle_password_v2(self, identity: str, password: str, pid: str = "65edCTyg") -> dict[str, Any]:
		"""处理 v2 版本密码登录 - 使用 /tiger/v3/web/accounts/login/security 安全登录"""
		timestamp = fetch_current_timestamp(self.client)
		ticket_response = self.get_login_ticket(identity, timestamp, pid)
		ticket = ticket_response["ticket"]
		return self.get_login_security_info(identity, password, ticket, pid)


# ==================== 登录处理器 ====================
class LoginHandler:
	"""登录处理器, 负责执行具体的登录操作"""

	def __init__(self, client: acquire.CodeMaoClient, processor: AuthProcessor) -> None:
		self.client = client
		self.processor = processor
		self.tool = tool

	def handle_password_v0(self, identity: str, password: str, pid: str, status: AccountStatus) -> LoginResult:
		"""处理 v0 版本密码登录"""
		self.client.switch_identity(token="", identity="blank")
		response_data = self.processor.handle_password_v0(identity, password, pid)
		if "token" in response_data:
			self.client.switch_identity(token=response_data["token"], identity=status.value)
			return LoginResult(success=True, method=LoginMethod.PASSWORD_V0, message="v0 密码登录成功", data=response_data)
		return LoginResult(success=False, method=LoginMethod.PASSWORD_V0, message="v0 密码登录失败", data=response_data)

	def handle_password_v1(self, identity: str, password: str, pid: str, status: AccountStatus) -> LoginResult:
		"""处理 v1 版本密码登录"""
		self.client.switch_identity(token="", identity="blank")
		response_data = self.processor.handle_password_v1(identity, password, pid)
		if "auth" in response_data and "token" in response_data["auth"]:
			token = response_data["auth"]["token"]
			if token:
				self.client.switch_identity(token=token, identity=status.value)
				return LoginResult(success=True, method=LoginMethod.PASSWORD_V1, message="v1 密码登录成功", data=response_data)
		return LoginResult(success=False, method=LoginMethod.PASSWORD_V1, message="v1 密码登录失败", data=response_data)

	def handle_password_v2(self, identity: str, password: str, pid: str, status: AccountStatus) -> LoginResult:
		"""处理 v2 版本密码登录"""
		self.client.switch_identity(token="", identity="blank")
		response_data = self.processor.handle_password_v2(identity, password, pid)
		if "auth" in response_data and "token" in response_data["auth"]:
			token = response_data["auth"]["token"]
			if token:
				self.client.switch_identity(token=token, identity=status.value)
				return LoginResult(success=True, method=LoginMethod.PASSWORD_V2, message="v2 密码登录成功", data=response_data)
		return LoginResult(success=False, method=LoginMethod.PASSWORD_V2, message="v2 密码登录失败", data=response_data)

	def handle_token(self, token: str, status: AccountStatus) -> LoginResult:
		"""处理 token 登录"""
		auth_details = self.processor.fetch_auth_details(token)
		self.client.switch_identity(token=token, identity=status.value)
		return LoginResult(success=True, method=LoginMethod.TOKEN, message="Token 登录成功", token=token, auth_details=auth_details)

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
		pid: str = "65edCTyg",
		status: StatusType = "average",
		role: RoleType = "user",
		prefer_method: AllMethodType | None = None,
	) -> LoginResult:
		"""
		统一的登录接口

		参数:
			identity: 用户身份标识
			password: 用户密码
			token: 用户 token
			pid: 请求的 PID
			status: 账号状态类型
				- "judgement": 判定状态
				- "average": 普通状态
				- "edu": 教育状态
			role: 用户角色
				- "user": 普通用户
				- "admin": 管理员
			prefer_method: 优先使用的登录方式
				- 普通用户可选: "password_v0", "password_v1", "password_v2", "token"
				- 管理员可选: "admin_token", "admin_password"

		返回:
			登录结果

		示例:
			>>> auth = AuthManager()
			>>> # 普通用户密码登录
			>>> result = auth.login(identity="user@example.com", password="password", prefer_method="password_v2")
			>>> # 普通用户token登录
			>>> result = auth.login(token="your_token_here", prefer_method="token")
			>>> # 管理员token登录
			>>> result = auth.login(role="admin", token="admin_token", prefer_method="admin_token")
			>>> # 管理员密码登录
			>>> result = auth.login(role="admin", identity="admin_user", password="admin_pass", prefer_method="admin_password")
		"""
		# 验证参数组合的有效性
		self._validate_login_parameters(identity, password, token, role, prefer_method)

		credentials = LoginCredentials(
			identity=identity,
			password=password,
			token=token,
			pid=pid,
			status=AccountStatus(status),
			role=UserRole(role),
		)
		self._current_credentials = credentials

		if credentials.role == UserRole.ADMIN:
			return self._admin_login(credentials, prefer_method)
		return self._user_login(credentials, prefer_method)

	@staticmethod
	def _validate_login_parameters(
		identity: str,
		password: str,
		token: str,
		role: RoleType,
		prefer_method: AllMethodType | None,
	) -> None:
		"""验证登录参数的有效性"""
		if prefer_method:
			# 验证 prefer_method 与 role 的匹配性
			user_methods: list[UserMethodType] = ["password_v0", "password_v1", "password_v2", "token"]
			admin_methods: list[AdminMethodType] = ["admin_token", "admin_password"]

			if role == "user" and prefer_method not in user_methods:
				msg = f"用户角色不支持登录方法 '{prefer_method}',可用方法: {user_methods}"
				raise ValueError(
					msg,
				)

			if role == "admin" and prefer_method not in admin_methods:
				msg = f"管理员角色不支持登录方法 '{prefer_method}',可用方法: {admin_methods}"
				raise ValueError(msg)
			if prefer_method in {"password_v0", "password_v1", "password_v2", "admin_password"} and (not identity or not password):
				msg = f"登录方法 '{prefer_method}' 需要提供 identity 和 password 参数"
				raise ValueError(
					msg,
				)

			if prefer_method in {"token", "admin_token"} and not token:
				msg = f"登录方法 '{prefer_method}' 需要提供 token 参数"
				raise ValueError(
					msg,
				)

	def _user_login(self, credentials: LoginCredentials, prefer_method: AllMethodType | None) -> LoginResult:
		"""用户登录"""
		method = self._get_user_login_method(credentials, prefer_method)

		if method == "password_v0":
			return self._handler.handle_password_v0(
				credentials.identity,
				credentials.password,
				credentials.pid,
				credentials.status,
			)

		if method == "password_v1":
			return self._handler.handle_password_v1(
				credentials.identity,
				credentials.password,
				credentials.pid,
				credentials.status,
			)

		if method == "password_v2":
			return self._handler.handle_password_v2(
				credentials.identity,
				credentials.password,
				credentials.pid,
				credentials.status,
			)

		if method == "token":
			return self._handler.handle_token(credentials.token, credentials.status)

		msg = f"不支持的登录方式: {method}"
		raise ValueError(msg)

	def _admin_login(self, credentials: LoginCredentials, prefer_method: AllMethodType | None) -> LoginResult:
		"""管理员登录"""
		method = self._get_admin_login_method(credentials, prefer_method)

		if method == "admin_token":
			return self._handler.handle_admin_token(credentials.token)

		if method == "admin_password":
			return self._handler.handle_admin_password(credentials.identity, credentials.password)

		msg = f"不支持的管理员登录方式: {method}"
		raise ValueError(msg)

	@staticmethod
	def _get_user_login_method(credentials: LoginCredentials, prefer_method: AllMethodType | None) -> UserMethodType:
		"""获取用户登录方法"""
		if prefer_method:
			# 确保返回的是 UserMethodType
			if prefer_method in {"password_v0", "password_v1", "password_v2", "token"}:
				return cast("UserMethodType", prefer_method)
			msg = f"'{prefer_method}' 不是有效的用户登录方法"
			raise ValueError(msg)
		return determine_login_method(credentials.token, credentials.identity, credentials.password)

	@staticmethod
	def _get_admin_login_method(credentials: LoginCredentials, prefer_method: AllMethodType | None) -> AdminMethodType:
		"""获取管理员登录方法"""
		if prefer_method:
			# 确保返回的是 AdminMethodType
			if prefer_method in {"admin_token", "admin_password"}:
				return cast("AdminMethodType", prefer_method)
			msg = f"'{prefer_method}' 不是有效的管理员登录方法"
			raise ValueError(msg)
		return determine_admin_login_method(credentials.token, credentials.identity, credentials.password)

	def execute_logout_v0(self) -> bool:
		"""执行 v0 版本用户登出"""
		response = self._client.send_request(
			endpoint="/tiger/accounts/logout",
			method="POST",
			payload={},
		)
		return response.status_code == acquire.HTTPStatus.NO_CONTENT.value

	def execute_logout_v12(self, method: Literal["web", "app"] = "web") -> bool:
		"""
		执行 v12 版本用户登出

		Args:
			method: 登出方法类型
				"web": web 版登出接口
				"app": app 版登出接口
		"""
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

	def configure_authentication_token(self, token: str, identity: StatusType = "judgement") -> None:
		"""配置认证 Token"""
		self._client.switch_identity(token=token, identity=identity)

	def restore_admin_account(self) -> None:
		"""恢复管理员账号"""
		self._client.switch_identity(
			token=self._client.token.judgement,
			identity="judgement",
		)

	def get_current_client(self) -> acquire.CodeMaoClient:
		"""获取当前客户端"""
		return self._client

	def get_current_credentials(self) -> LoginCredentials | None:
		"""获取当前登录凭证"""
		return self._current_credentials


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
			local_time = int(time())
			self.time_difference = local_time - server_time
		return int(time()) - self.time_difference

	def generate_x_device_auth(self) -> dict[str, str | int]:
		"""生成设备认证信息"""
		timestamp = self.get_calibrated_timestamp()
		sign_str = f"{self.CLIENT_SECRET}{timestamp}{self.client_id}"
		sign = sha256(sign_str.encode()).hexdigest().upper()
		return {"sign": sign, "timestamp": timestamp, "client_id": self.client_id}
