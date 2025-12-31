import hashlib
import time
from http import HTTPStatus
from random import randint
from typing import Any, Literal, cast

from src.utils import acquire, data, file, tool
from src.utils.decorator import singleton


def fetch_current_timestamp(client: acquire.CodeMaoClient) -> dict:
	"""获取当前服务器时间戳"""
	response = client.send_request(endpoint="/coconut/clouddb/currentTime", method="GET")
	return response.json()


@singleton
class AuthManager:
	"""
	统一认证管理器
	支持普通用户和管理员两种角色的登录
	"""

	CLIENT_SECRET = "pBlYqXbJDu"  # noqa: S105

	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()
		self.tool = tool
		self.setting = data.SettingManager().data
		self._captcha_img_path = data.PathConfig().CAPTCHA_FILE_PATH

	def login(
		self,
		identity: str | None = None,
		password: str | None = None,
		token: str | None = None,
		cookies: str | None = None,
		pid: str = "65edCTyg",
		status: Literal["judgement", "average", "edu"] = "average",
		role: Literal["user", "admin"] = "user",
		prefer_method: Literal["auto", "simple_password", "secure_password", "token", "cookies", "password"] = "auto",
	) -> dict[str, Any]:
		"""
		整合登录方法
		参数:
			identity: 用户身份标识(手机号/邮箱/用户名)
			password: 用户密码
			token: 用户token
			cookies: 用户cookies字符串
			pid: 请求的PID,默认为"65edCTyg"
			status: 账号状态类型
			role: 用户角色(user-普通用户, admin-管理员)
			prefer_method: 优先使用的登录方式,auto为自动选择
			注意:当role为admin时,prefer_method只能为"auto"、"token"或"password"
		返回:
			登录结果信息
		"""
		if role == "admin":
			# 转换prefer_method类型为admin可接受的类型
			admin_prefer_method: Literal["auto", "token", "password"]
			admin_prefer_method = cast("Literal['auto', 'token', 'password']", prefer_method) if prefer_method in {"auto", "token", "password"} else "auto"
			return self._admin_login(identity, password, token, admin_prefer_method)
		# 为用户登录转换prefer_method类型
		user_prefer_method: Literal["auto", "simple_password", "secure_password", "token", "cookies"]
		if prefer_method in {"auto", "simple_password", "secure_password", "token", "cookies"}:
			user_prefer_method = cast("Literal['auto', 'simple_password', 'secure_password', 'token', 'cookies']", prefer_method)
		else:
			# 如果传入的是"password",转换为默认的"secure_password"
			user_prefer_method = "secure_password"
		return self._user_login(identity, password, token, cookies, pid, status, user_prefer_method)

	def _user_login(
		self,
		identity: str | None,
		password: str | None,
		token: str | None,
		cookies: str | None,
		pid: str,
		status: Literal["judgement", "average", "edu"],
		prefer_method: Literal["auto", "simple_password", "secure_password", "token", "cookies"],
	) -> dict[str, Any]:
		"""普通用户登录"""
		# 自动选择登录方式
		if prefer_method == "auto":
			prefer_method = self._determine_login_method(token, cookies, identity, password)
		try:
			return self._execute_user_login(prefer_method, identity, password, token, cookies, pid, status)
		except Exception as e:
			print(f"用户登录失败: {e}")
			# 如果首选方式失败,尝试备用方式
			if prefer_method != "simple_password" and identity and password:
				print("尝试使用简单密码登录作为备用方案...")
				return self._authenticate_with_simple_password(identity, password, pid, status)
			raise

	def _admin_login(
		self,
		username: str | None,
		password: str | None,
		token: str | None,
		prefer_method: Literal["auto", "token", "password"],
	) -> dict[str, Any]:
		"""管理员登录"""
		if prefer_method == "auto":
			prefer_method = "token" if token else "password"
		if prefer_method == "token":
			return self._handle_admin_token_login(token)
		return self._handle_admin_password_login(username, password)

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
			return "secure_password"
		msg = "缺少必要的登录凭据"
		raise ValueError(msg)

	def _execute_user_login(
		self,
		method: Literal["simple_password", "secure_password", "token", "cookies"],
		identity: str | None,
		password: str | None,
		token: str | None,
		cookies: str | None,
		pid: str,
		status: Literal["judgement", "average", "edu"],
	) -> dict[str, Any]:
		"""执行用户登录操作"""
		login_methods = {
			"simple_password": lambda: self._authenticate_with_simple_password(
				cast("str", identity),
				cast("str", password),
				pid,
				status,
			),
			"secure_password": lambda: self._authenticate_with_secure_password(
				cast("str", identity),
				cast("str", password),
				pid,
				status,
			),
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
		return {
			"success": True,
			"method": "token",
			"token": token,
			"auth_details": auth_details,
			"message": "Token登录成功",
		}

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
		return {
			"success": True,
			"method": "simple_password",
			"data": response_data,
			"message": "简单密码登录成功",
		}

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
		return {
			"success": True,
			"method": "secure_password",
			"data": resp,
			"message": "安全密码登录成功",
		}

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

	def _handle_admin_token_login(self, token: str | None) -> dict[str, Any]:
		"""处理管理员Token登录"""
		if not token:
			token = input("请输入 Authorization Token: ")
		self._client.switch_identity(token=token, identity="judgement")
		return {
			"success": True,
			"method": "admin_token",
			"token": token,
			"message": "管理员Token登录成功",
		}

	def _handle_admin_password_login(
		self,
		username: str | None,
		password: str | None,
		max_retries: int = 3,
	) -> dict[str, Any]:
		"""
		处理管理员账密登录
		验证码原理:
			1. 验证码根据"时间戳"和"序列位置"确定性算法生成
			2. 每个时间戳对应一个虚拟的验证码序列
			3. 每个验证码成功验证后立即失效
			4. 对同一时间戳的连续请求按顺序生成不同验证码
			5. 不同时间戳的验证码序列完全独立
		"""

		def input_account() -> tuple[str, str]:
			"""获取用户名和密码"""
			username_input = username or input("请输入用户名: ")
			password_input = password or input("请输入密码: ")
			return username_input, password_input

		def input_captcha(timestamp: int) -> tuple[str, Any]:
			"""获取验证码和Cookie"""
			print("正在获取验证码...")
			cookies = self.fetch_admin_captcha(timestamp=timestamp)
			captcha = input("请输入验证码: ")
			return captcha, cookies

		# 登录循环
		timestamp = self.tool.TimeUtils().current_timestamp(13)  # 13位时间戳
		username_input, password_input = input_account()
		while True:
			captcha, _ = input_captcha(timestamp=timestamp)
			# 调用鲸平台认证接口
			response = self.authenticate_admin_user(
				username=username_input,
				password=password_input,
				key=timestamp,
				code=captcha,
			)
			# 登录成功
			if "token" in response:
				self._client.switch_identity(token=response["token"], identity="judgement")
				return {
					"success": True,
					"method": "admin_password",
					"token": response["token"],
					"message": "管理员账密登录成功",
				}
			# 登录失败处理
			if "error_code" in response:
				print(f"登录失败: {response.get('error_msg', '未知错误')}")
				# 密码错误/参数无效:重新输入账号
				if response["error_code"] in {"Admin-Password-Error@Community-Admin", "Param - Invalid @ Common"}:
					username_input, password_input = input_account()
				# 重新获取验证码和时间戳
				timestamp = self.tool.TimeUtils().current_timestamp(13)

	def authenticate_admin_user(self, username: str, password: str, key: int, code: str) -> dict:
		"""管理员用户认证"""
		payload = {"username": username, "password": password, "key": key, "code": code}
		response = self._client.send_request(
			endpoint="https://api-whale.codemao.cn/admins/login",
			method="POST",
			payload=payload,
		)
		return response.json()

	def fetch_admin_captcha(self, timestamp: int) -> Any:
		"""获取管理员验证码"""
		response = self._client.send_request(
			endpoint=f"https://api-whale.codemao.cn/admins/captcha/{timestamp}",
			method="GET",
			log=False,
		)
		if response.status_code == HTTPStatus.OK.value:
			# 保存验证码图片
			file.CodeMaoFile().file_write(
				path=self._captcha_img_path,
				content=response.content,
				method="wb",
			)
			print(f"验证码已保存至: {self._captcha_img_path}")
		else:
			print(f"获取验证码失败,错误代码: {response.status_code}")
		return response.cookies

	def fetch_auth_details(self, token: str) -> dict[str, Any]:
		"""获取认证详情"""
		token_ca = {"authorization": token}
		cookie_str = self.tool.DataConverter().convert_cookie(token_ca)
		headers = {**self._client.headers, "cookie": cookie_str}
		response = self._client.send_request(
			method="GET",
			endpoint="/web/users/details",
			headers=headers,
		)
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

	def admin_logout(self) -> bool:
		"""管理员登出"""
		response = self._client.send_request(
			endpoint="https://api-whale.codemao.cn/admins/logout",
			method="DELETE",
		)
		return response.status_code == HTTPStatus.NO_CONTENT.value

	def fetch_admin_dashboard_data(self) -> dict:
		"""获取用户仪表板数据"""
		response = self._client.send_request(
			endpoint="https://api-whale.codemao.cn/admins/info",
			method="GET",
		)
		return response.json()

	def configure_authentication_token(self, token: str, identity: str = "judgement") -> None:
		"""配置认证Token"""
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


class Authenticator:
	"""云服务认证管理器"""

	CLIENT_SECRET = "pBlYqXbJDu"  # noqa: S105

	def __init__(self, authorization_token: str | None = None) -> None:
		self.authorization_token = authorization_token
		self.client_id = self._generate_client_id()
		self.time_difference = 0
		self._client = acquire.CodeMaoClient()  # 直接实例化客户端

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
