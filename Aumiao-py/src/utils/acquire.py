import contextlib
import ssl
from abc import ABC, abstractmethod
from collections.abc import Generator
from dataclasses import dataclass, field
from enum import Enum
from json import dumps
from pathlib import Path
from time import sleep
from types import TracebackType
from typing import TYPE_CHECKING, Any, Literal, TypedDict

import httpx
import websocket
from httpx import Response

from src.utils import data as setting
from src.utils import file, tool
from src.utils.decorator import singleton

# 导入必要的模块
if TYPE_CHECKING:
	from src.utils.data import SettingManager


# ==================== 配置类 ====================
@dataclass
class ClientConfig:
	"""客户端配置"""

	base_url: str = "https://api.codemao.cn"
	timeout: float = 30.0
	max_retries: int = 3
	retry_delay: float = 1.0
	log_requests: bool = True


class HTTPStatus(Enum):
	"""HTTP状态码枚举"""

	CREATED = 201
	FORBIDDEN = 403
	NOT_FOUND = 404
	NOT_MODIFIED = 304
	NO_CONTENT = 204
	OK = 200


class PaginationConfig(TypedDict, total=False):
	"""分页配置"""

	amount_key: str
	offset_key: str
	response_amount_key: str
	response_offset_key: str


# ==================== 类型定义 ====================
HttpMethod = Literal["GET", "POST", "DELETE", "PATCH", "PUT", "HEAD"]
FetchMethod = Literal["GET", "POST"]


# ==================== 接口定义 ====================
class IHTTPClient(ABC):
	"""HTTP客户端接口"""

	@abstractmethod
	def send_request(self, method: str, endpoint: str) -> Response:
		"""发送HTTP请求"""

	@abstractmethod
	def update_headers(self, headers: dict[str, str]) -> None:
		"""更新请求头"""

	@abstractmethod
	def fetch_paginated_data(
		self,
		endpoint: str,
		params: dict[str, Any],
		payload: dict[str, Any] | None = None,
		method: FetchMethod = "GET",
		limit: int | None = None,
		total_key: str = "total",
		data_key: str = "items",
		pagination_method: Literal["offset", "page"] = "offset",
		config: PaginationConfig | None = None,
	) -> Generator[dict[str, Any]]:
		"""获取分页数据"""

	@abstractmethod
	def get_pagination_total(
		self,
		endpoint: str,
		params: dict[str, Any],
		payload: dict[str, Any] | None = None,
		fetch_method: FetchMethod = "GET",
		total_key: str = "total",
		data_key: str = "items",
		config: PaginationConfig | None = None,
	) -> dict[Literal["total", "total_pages"], int]:
		"""获取分页总数"""


class IWebSocketClient(ABC):
	"""WebSocket客户端接口"""

	@abstractmethod
	def connect(self, url: str) -> bool:
		"""连接WebSocket"""

	@abstractmethod
	def disconnect(self) -> None:
		"""断开连接"""

	@abstractmethod
	def send(self, message: str | dict[str, Any]) -> bool:
		"""发送消息"""

	@abstractmethod
	def receive(self, timeout: float = 30.0) -> str | bytes | None:
		"""接收消息"""

	@abstractmethod
	def listen(self) -> Generator[str | bytes]:
		"""监听消息"""


class IFileUploader(ABC):
	"""文件上传器接口"""

	@abstractmethod
	def upload(self, file_path: Path, method: str, save_path: str = "aumiao") -> str:
		"""上传文件"""


# ==================== 身份管理器 ====================
@dataclass
class Token:
	"""Token管理"""

	average: str = field(default="", metadata={"track": False})
	edu: str = field(default="", metadata={"track": False})
	judgement: str = field(default="", metadata={"track": False})
	blank: str = field(default="", metadata={"track": False})

	def __setattr__(self, name: str, value: str) -> None:
		"""属性设置监听"""
		if hasattr(self, name) and hasattr(self.__class__, name):
			field_meta = self.__dataclass_fields__[name].metadata
			if field_meta.get("track", False):
				old_value = getattr(self, name)
				if old_value != value:
					print(f"属性 '{name}' 已修改: {old_value[:10]!r}... → {value[:10]!r}...")
		super().__setattr__(name, value)


class IdentityManager:
	"""身份管理器"""

	def __init__(self) -> None:
		self.tokens = Token()
		self._current_identity = "blank"
		self._token_map = {"average": "average", "edu": "edu", "judgement": "judgement", "blank": "blank"}

	def switch_identity(self, identity: str, token: str) -> None:
		"""切换身份"""
		if identity not in self._token_map:
			error_msg = f"无效的身份: {identity}"
			raise ValueError(error_msg)
		# 更新token存储
		setattr(self.tokens, self._token_map[identity], token)
		self._current_identity = identity

	def get_current_token(self) -> str:
		"""获取当前token"""
		return getattr(self.tokens, self._token_map[self._current_identity])

	def get_identity_headers(self) -> dict[str, str]:
		"""获取身份认证头"""
		return {"Authorization": f"Bearer {self.get_current_token()}"}

	@property
	def current_identity(self) -> str:
		"""获取当前身份"""
		return self._current_identity


# ==================== 基础实现 ====================
class BaseHTTPClient(IHTTPClient):
	"""基础HTTP客户端 - 整合原版分页逻辑"""

	def __init__(self, config: ClientConfig) -> None:
		self.config = config
		self.headers = setting.SettingManager().data.PROGRAM.HEADERS.copy()
		self._http_client = httpx.Client(headers=self.headers, timeout=config.timeout)
		self._file_handler = file.CodeMaoFile()
		self._data_processor = tool.DataProcessor()
		self.log_file = Path.cwd() / "logs" / f"requests_{tool.TimeUtils().current_timestamp()}.txt"

	def send_request(
		self,
		method: str,
		endpoint: str,
		params: dict[str, Any] | None = None,
		data: dict[str, Any] | None = None,
		payload: dict[str, Any] | None = None,
		files: dict[str, Any] | None = None,
		headers: dict[str, str] | None = None,
		retries: int | None = None,
		backoff_factor: float = 0.3,
		timeout: float | None = None,
		*,
		log: bool = True,
	) -> Response:
		"""统一的HTTP请求方法"""
		url = endpoint if endpoint.startswith("http") else f"{self.config.base_url}{endpoint}"
		retries = retries or self.config.max_retries
		timeout = timeout or self.config.timeout
		log_enabled = bool(self.config.log_requests and log)
		for attempt in range(retries):
			try:
				request_headers = self._prepare_headers(headers, files)
				response = self._execute_request(method=method, url=url, params=params, data=data, payload=payload, files=files, headers=request_headers, timeout=timeout)
				if log_enabled:
					self._log_request(response)
				response.raise_for_status()
			except httpx.HTTPStatusError as e:
				if attempt == retries - 1:
					return e.response
				self._handle_retry(e, attempt)
			except (httpx.ConnectError, httpx.TimeoutException) as e:
				if attempt == retries - 1:
					raise
				self._handle_retry(e, attempt)
			except Exception as e:
				print(f"请求失败: {e}")
				break
			else:
				return response
			sleep(self.config.retry_delay * (2**attempt * backoff_factor))
		return Response(500)

	def _prepare_headers(self, headers: dict[str, str] | None, files: dict[str, Any] | None) -> dict[str, str]:
		"""准备请求头"""
		request_headers = {**self._http_client.headers, **(headers or {})}
		if files:
			request_headers.pop("Content-Type", None)
			request_headers.pop("Content-Length", None)
		return request_headers

	def _execute_request(
		self,
		method: str,
		url: str,
		params: dict[str, Any] | None,
		data: dict[str, Any] | None,
		payload: dict[str, Any] | None,
		files: dict[str, Any] | None,
		headers: dict[str, str],
		timeout: float,
	) -> Response:
		"""执行HTTP请求"""
		request_args: dict[str, Any] = {"method": method.upper(), "url": url, "params": params, "headers": headers, "timeout": timeout}
		if files:
			request_args.update({"data": data, "files": files})
		else:
			request_args["json"] = payload
		return self._http_client.request(**request_args)

	@staticmethod
	def _handle_retry(error: Exception, attempt: int) -> None:
		"""处理重试逻辑"""
		print(f"请求失败,第 {attempt + 1} 次重试: {error}")

	def update_headers(self, headers: dict[str, str]) -> None:
		"""更新请求头"""
		self._http_client.headers.update(headers)

	def _get_pagination_info(
		self,
		endpoint: str,
		params: dict[str, Any],
		payload: dict[str, Any] | None = None,
		fetch_method: FetchMethod = "GET",
		total_key: str = "total",
		data_key: str = "items",
		config: PaginationConfig | None = None,
		*,
		include_first_page: bool = False,
	) -> tuple[int, int, list[dict[str, Any]], dict[str, Any]]:
		"""获取分页信息 - 原版逻辑"""
		config_ = {"amount_key": "limit", "offset_key": "offset", "response_amount_key": "limit", "response_offset_key": "offset", **(config or {})}
		amount_key = str(config_.get("amount_key", "limit"))  # 确保是字符串
		page_size_key = str(config_.get("response_amount_key", "limit"))  # 确保是字符串
		base_params = params.copy()
		original_limit = 0
		# 调整参数获取第一页
		if not include_first_page and amount_key in base_params:
			original_limit = base_params[amount_key]
			base_params[amount_key] = 15
		# 发送初始请求
		initial_response = self.send_request(fetch_method, endpoint, params=base_params, payload=payload)
		if initial_response.status_code != HTTPStatus.OK.value:
			return 0, 0, [], {}
		initial_data = initial_response.json()
		# 提取总数
		total_items_raw = self._get_nested_value(initial_data, total_key)
		try:
			total_items = int(total_items_raw) if total_items_raw is not None else 0
		except (ValueError, TypeError):
			total_items = 0
		# 确定每页数量
		items_per_page_param = base_params.get(amount_key)
		items_per_page_response = initial_data.get(page_size_key)
		if items_per_page_param and items_per_page_param > 0:
			items_per_page = items_per_page_param
		elif items_per_page_response and items_per_page_response > 0:
			items_per_page = items_per_page_response
		else:
			items_per_page = 15
		if items_per_page <= 0:
			items_per_page = 1
		# 提取第一页数据
		first_page: list[dict[str, Any]] = []
		if include_first_page:
			first_page_raw = self._get_nested_value(initial_data, data_key)
			first_page = first_page_raw if isinstance(first_page_raw, list) else []
		elif not include_first_page and amount_key in base_params:
			base_params[amount_key] = original_limit
		return total_items, items_per_page, first_page, initial_data

	@staticmethod
	def _get_nested_value(data: dict[str, Any], key: str) -> Any:  # noqa: ANN401
		"""获取嵌套值 - 替代原版的DataProcessor"""
		if not key or not isinstance(data, dict):
			return None
		keys = key.split(".")
		current = data
		for k in keys:
			if isinstance(current, dict) and k in current:
				current = current[k]
			else:
				return None
		return current

	def fetch_paginated_data(
		self,
		endpoint: str,
		params: dict[str, Any],
		payload: dict[str, Any] | None = None,
		method: FetchMethod = "GET",
		limit: int | None = None,
		total_key: str = "total",
		data_key: str = "items",
		pagination_method: Literal["offset", "page"] = "offset",
		config: PaginationConfig | None = None,
	) -> Generator[dict[str, Any]]:
		# 获取分页信息
		total_items, items_per_page, first_page, _ = self._get_pagination_info(
			endpoint=endpoint, params=params, payload=payload, fetch_method=method, total_key=total_key, data_key=data_key, config=config, include_first_page=True
		)
		config_ = {"offset_key": "offset", **(config or {})}
		offset_param_key = str(config_.get("offset_key", "offset"))  # 确保是字符串
		base_params = params.copy()
		yielded_count = 0
		# 处理第一页数据
		for item in first_page:
			yield item
			yielded_count += 1
			if limit and yielded_count >= limit:
				return
		# 如果没有更多数据,直接返回
		if total_items <= len(first_page):
			return
		# 计算剩余数据量
		remaining_items = total_items - len(first_page)
		if limit:
			remaining_items = min(remaining_items, limit - yielded_count)
		if remaining_items <= 0:
			return
		# 计算总页数
		total_pages = (remaining_items + items_per_page - 1) // items_per_page
		# 获取后续页面数据
		for page_idx in range(1, total_pages + 1):
			page_params = base_params.copy()
			if pagination_method == "offset":
				page_params[offset_param_key] = page_idx * items_per_page
			elif pagination_method == "page":
				page_params[offset_param_key] = page_idx + 1
			else:
				error_msg = f"不支持的分页方式: {pagination_method}"
				raise ValueError(error_msg)
			page_response = self.send_request(method, endpoint, params=page_params, payload=payload)
			if page_response.status_code != HTTPStatus.OK.value:
				continue
			page_data_raw = self._get_nested_value(page_response.json(), data_key)
			page_data = page_data_raw if isinstance(page_data_raw, list) else []
			for item in page_data:
				yield item
				yielded_count += 1
				if limit and yielded_count >= limit:
					return

	def get_pagination_total(
		self,
		endpoint: str,
		params: dict[str, Any],
		payload: dict[str, Any] | None = None,
		fetch_method: FetchMethod = "GET",
		total_key: str = "total",
		data_key: str = "items",
		config: PaginationConfig | None = None,
	) -> dict[Literal["total", "total_pages"], int]:
		"""获取分页总数 - 原版逻辑"""
		total_items, items_per_page, _, _ = self._get_pagination_info(endpoint, params, payload, fetch_method, total_key, data_key, config, include_first_page=False)
		total_pages = 0 if total_items == 0 else (total_items + items_per_page - 1) // items_per_page
		return {"total": total_items, "total_pages": total_pages}

	def _log_request(self, response: Response) -> None:
		"""记录请求日志"""
		log_entry = (
			f"[{tool.TimeUtils().format_timestamp()}]\n"
			f"Method: {response.request.method}\n"
			f"URL: {response.url}\n"
			f"Status: {response.status_code}\n"
			f"Response: {response.text}\n"
			f"{'=' * 50}\n\n"
		)

		self._file_handler.file_write(path=self.log_file, content=log_entry, method="a")

	def close(self) -> None:
		"""关闭HTTP客户端"""
		self._http_client.close()

	def __enter__(self) -> "BaseHTTPClient":
		return self

	def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None) -> None:
		self.close()


# ==================== 具体实现 ====================
@singleton
class CodeMaoClient(BaseHTTPClient):
	"""编程猫HTTP客户端"""

	def __init__(self) -> None:
		# 修复未定义的data变量
		setting_manager: SettingManager = setting.SettingManager()
		config = ClientConfig(log_requests=setting_manager.data.PARAMETER.log)
		super().__init__(config)
		self.identity_manager = IdentityManager()
		self.token = IdentityManager().tokens

	def switch_identity(self, identity: str, token: str) -> None:
		"""切换身份并更新请求头"""
		self.identity_manager.switch_identity(identity, token)
		self.update_headers(self.identity_manager.get_identity_headers())


class CodeMaoWebSocketClient(IWebSocketClient):
	"""编程猫WebSocket客户端 - 修复版本"""

	def __init__(self) -> None:
		self._ws_app = None
		self._connected = False
		self._message_queue = []

	def connect(self, url: str) -> bool:
		"""连接WebSocket"""
		try:
			self._ws_app = websocket.create_connection(
				url,
				header={
					"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0",
					"Origin": "https://kn.codemao.cn",
					"Accept-Encoding": "gzip, deflate, br, zstd",
					"Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
					"Cache-Control": "no-cache",
					"Pragma": "no-cache",
				},
				sslopt={"cert_reqs": ssl.CERT_NONE},
			)
			self._connected = True
			print(f"WebSocket连接已建立: {url}")

		except Exception as e:
			print(f"WebSocket连接失败: {e}")
			self._connected = False
			return False
		else:
			return True

	def disconnect(self) -> None:
		"""断开WebSocket连接"""
		if self._ws_app:
			with contextlib.suppress(Exception):
				self._ws_app.close()
			self._ws_app = None
		self._connected = False
		print("WebSocket连接已断开")

	def send(self, message: str | dict[str, Any]) -> bool:
		"""发送WebSocket消息"""
		if not self._ws_app or not self._connected:
			print("WebSocket未连接")
			return False
		try:
			if isinstance(message, dict):
				message = dumps(message, ensure_ascii=False)
			self._ws_app.send(message)

		except Exception as e:
			print(f"发送WebSocket消息失败: {e}")
			return False
		else:
			return True

	def receive(self, timeout: float = 30.0) -> str | bytes | None:
		"""接收WebSocket消息"""
		if not self._ws_app or not self._connected:
			return None
		try:
			self._ws_app.settimeout(timeout)
			message = self._ws_app.recv()

		except websocket.WebSocketTimeoutException:
			print("接收WebSocket消息超时")
			return None
		except Exception as e:
			print(f"接收WebSocket消息失败: {e}")
			return None
		else:
			return message

	def listen(self) -> Generator[str | bytes]:
		while self._connected and self._ws_app:
			try:
				message = self.receive(timeout=1.0)
				if message is not None:
					yield message
			except Exception:
				break

	@property
	def connected(self) -> bool:
		return self._connected

	def close(self) -> None:
		self.disconnect()

	def __enter__(self) -> "CodeMaoWebSocketClient":
		return self

	def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None) -> None:
		self.close()


class FileUploader(IFileUploader):
	"""文件上传器 - 整合原版上传逻辑"""

	def __init__(self) -> None:
		self.client = CodeMaoClient()
		self._upload_strategies = {
			"pgaot": self._upload_pgaot,
			"codegame": self._upload_codegame,
			"codemao": self._upload_codemao,
		}
		# 为文件上传创建独立session避免影响主会话
		self._upload_session = httpx.Client()

	def upload(self, file_path: Path, method: str, save_path: str = "aumiao") -> str:
		"""上传文件"""
		if method not in self._upload_strategies:
			error_msg = f"不支持的上传方式: {method}"
			raise ValueError(error_msg)
		return self._upload_strategies[method](file_path, save_path)

	def _upload_pgaot(self, file_path: Path, save_path: str) -> str:
		"""Pgaot上传"""
		with file_path.open("rb") as f:
			files = {"file": (file_path.name, f)}
			data = {"path": save_path}
			response = self._upload_request("POST", "https://api.pgaot.com/user/up_cat_file", files=files, data=data)
		return response.json()["url"]

	def _upload_codegame(self, file_path: Path, save_path: str) -> str:
		"""CodeGame上传"""
		token_info = self._get_codegame_token(save_path, file_path)
		with file_path.open("rb") as f:
			files = {"file": (file_path.name, f)}
			data = {
				"token": token_info["token"],
				"key": token_info["file_path"],
				"fname": "avatar",
			}
			response = self._upload_request("POST", token_info["upload_url"], files=files, data=data)
		result = response.json()
		return f"{token_info['pic_host']}/{result['key']}"

	def _upload_codemao(self, file_path: Path, save_path: str) -> str:
		"""CodeMao上传"""
		unique_name = f"{save_path}/{file_path.name}"
		token_info = self._get_codemao_token(unique_name)
		with file_path.open("rb") as f:
			files = {"file": (file_path.name, f)}
			data = {
				"token": token_info["token"],
				"key": token_info["file_path"],
				"fname": file_path.name,
			}
			self._upload_request("POST", token_info["upload_url"], files=files, data=data)
		return token_info["pic_host"] + token_info["file_path"]

	def _upload_request(self, method: str, endpoint: str, files: dict[str, Any] | None = None, data: dict[str, Any] | None = None, timeout: float = 120.0) -> Response:
		"""专门用于文件上传的请求方法"""
		headers = setting.SettingManager().data.PROGRAM.HEADERS.copy()
		if files:
			headers.pop("Content-Type", None)
			headers.pop("Content-Length", None)
		request_args: dict[str, Any] = {
			"method": method,
			"url": endpoint,
			"headers": headers,
			"timeout": timeout,
		}
		if files:
			request_args.update({"data": data, "files": files})
		else:
			request_args["json"] = data
		response = self._upload_session.request(**request_args)
		response.raise_for_status()
		return response

	def _get_codemao_token(self, file_path: str) -> dict[str, Any]:
		"""获取CodeMao上传token"""
		params = {
			"projectName": "community_frontend",
			"filePaths": file_path,
			"filePath": file_path,
			"tokensCount": 1,
			"fileSign": "p1",
			"cdnName": "qiniu",
		}
		response = self.client.send_request("GET", "https://open-service.codemao.cn/cdn/qi-niu/tokens/uploading", params=params)
		data = response.json()
		return {
			"token": data["tokens"][0]["token"],
			"file_path": data["tokens"][0]["file_path"],
			"upload_url": data["upload_url"],
			"pic_host": data["bucket_url"],
		}

	def _get_codegame_token(self, prefix: str, file_path: Path) -> dict[str, Any]:
		"""获取CodeGame上传token"""
		params = {"prefix": prefix, "bucket": "static", "type": file_path.suffix}
		response = self.client.send_request("GET", "https://oversea-api.code.game/tiger/kitten/cdn/token/1", params=params)
		data = response.json()
		return {
			"token": data["data"][0]["token"],
			"file_path": data["data"][0]["filename"],
			"pic_host": data["bucket_url"],
			"upload_url": "https://upload.qiniup.com",
		}

	def close(self) -> None:
		"""关闭上传会话"""
		self._upload_session.close()


# ==================== 工厂类 ====================
class ClientFactory:
	"""客户端工厂"""

	@staticmethod
	def create_http_client(config: ClientConfig | None = None) -> BaseHTTPClient:
		"""创建HTTP客户端"""
		config = config or ClientConfig()
		return BaseHTTPClient(config)

	@staticmethod
	def create_codemao_client() -> CodeMaoClient:
		"""创建编程猫HTTP客户端"""
		return CodeMaoClient()

	@staticmethod
	def create_websocket_client() -> CodeMaoWebSocketClient:
		"""创建WebSocket客户端"""
		return CodeMaoWebSocketClient()

	@staticmethod
	def create_codemao_websocket_client() -> CodeMaoWebSocketClient:
		"""创建编程猫WebSocket客户端"""
		return CodeMaoWebSocketClient()

	@staticmethod
	def create_file_uploader() -> FileUploader:
		"""创建文件上传器"""
		return FileUploader()
