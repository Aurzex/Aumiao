from collections.abc import Generator
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from time import sleep
from typing import Literal, TypedDict, cast

from requests import Response
from requests.adapters import HTTPAdapter
from requests.cookies import RequestsCookieJar
from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import HTTPError, RequestException, Timeout
from requests.sessions import Session

from src.utils import data, file, tool
from src.utils.decorator import singleton

DICT_ITEM = 2
LOG_DIR: Path = data.CURRENT_DIR / "logs"
ERROR_LOG_PATH = LOG_DIR / f"errors_{tool.TimeUtils().current_timestamp()}.txt"
LOG_FILE_PATH: Path = LOG_DIR / f"{tool.TimeUtils().current_timestamp()}.txt"
MAX_CHARACTER = 100


@singleton
@dataclass
class Token:
	average: str = field(default="", metadata={"track": True})
	edu: str = field(default="", metadata={"track": True})
	judgement: str = field(default="", metadata={"track": True})
	blank: str = field(default="", metadata={"track": True})

	def __setattr__(self, name: str, value: ...) -> None:
		if hasattr(self, name) and hasattr(self.__class__, name):
			field_meta = self.__dataclass_fields__[name].metadata
			if field_meta.get("track", False):
				old_value = getattr(self, name)
				if old_value != value:
					print(f"属性 '{name}' 已修改: {old_value[:10]!r}... → {value[:10]!r}... ")
		super().__setattr__(name, value)


class HTTPSTATUS(Enum):
	CREATED = 201
	FORBIDDEN = 403
	NOT_FOUND = 404
	NOT_MODIFIED = 304
	NO_CONTENT = 204
	OK = 200


class PaginationConfig(TypedDict, total=False):
	"""分页配置参数类型定义"""

	amount_key: Literal["limit", "page_size", "current_page"]
	offset_key: Literal["offset", "page", "current_page"]
	response_amount_key: Literal["limit", "page_size"]
	response_offset_key: Literal["offset", "page"]


HttpMethod = Literal["GET", "POST", "DELETE", "PATCH", "PUT", "HEAD"]
FetchMethod = Literal["GET", "POST"]
EXTRA_HEADERS: dict[str, str] = {"Cookie": "access-token=0;"}


@singleton
class CodeMaoClient:
	def __init__(self) -> None:
		"""初始化客户端实例,增强配置管理"""
		LOG_DIR.mkdir(parents=True, exist_ok=True)
		self._config = data.SettingManager().data
		self._default_session = Session()  # 默认会话用于非教育账号
		self._default_session.trust_env = False
		self._file = file.CodeMaoFile()
		self._identity: str | None = None
		self._session: Session = self._default_session  # 当前活跃会话
		self.base_url = "https://api.codemao.cn"
		self.headers: dict[str, str] = self._config.PROGRAM.HEADERS.copy()
		self.token = Token()
		self.tool = tool
		self._sessions = {
			"judgement": Session(),
			"average": Session(),
			"blank": Session(),
			"edu": None,
		}
		# 初始化所有会话为无Cookie状态
		self._init_sessions()
		# 当前状态
		self._session = cast("Session", self._sessions["blank"])
		self._identity = "blank"
		self.log_request: bool = data.SettingManager().data.PARAMETER.log

	def _init_sessions(self) -> None:
		"""初始化所有会话,禁用自动Cookie处理"""
		for session in self._sessions.values():
			if session:
				session.trust_env = False
				# 禁用会话的Cookie自动处理
				session.cookies = RequestsCookieJar()  # 使用空CookieJar
				# 移除可能的Cookie相关适配器
				session.adapters.clear()
				# 添加自定义适配器,确保不保存Cookie
				adapter = HTTPAdapter()
				session.mount("http://", adapter)
				session.mount("https://", adapter)

	def send_request(
		self,
		endpoint: str,
		method: HttpMethod,
		params: dict | None = None,
		payload: dict | None = None,
		files: dict | None = None,
		headers: dict | None = None,
		retries: int = 1,
		backoff_factor: float = 0.3,
		timeout: float = 10.0,
		*,
		stream: bool | None = None,
		log: bool = True,
	) -> Response:
		url = endpoint if endpoint.startswith("http") else f"{self.base_url}{endpoint}"
		base_headers = dict(self._session.headers)  # 包含账户token
		# 优先级:传入headers > 会话headers > 全局headers
		merged_headers: dict[str, str | bytes] = {
			**self.headers,  # 全局默认头
			**EXTRA_HEADERS,  # 额外请求头
			**base_headers,  # 当前会话头.含账户token
			**(headers or {}),  # 本次请求临时头.最高优先级
		}
		# 强制移除Cookie头
		merged_headers.pop("Cookie", None)
		# 当有文件上传时,移除 Content-Type 头
		if files is not None:
			for header_to_remove in ["Content-Type", "Content-Length"]:
				merged_headers.pop(header_to_remove, None)
		log = bool(self.log_request and log)
		# 强制清除会话中的Cookie(关键修复2:防止会话自动添加)
		self._session.cookies.clear()
		for attempt in range(retries):
			try:
				if files is not None:
					response = self._session.request(
						method=method,
						url=url,
						headers=merged_headers,
						params=params,
						data=payload,
						files=files,
						timeout=timeout,
						stream=stream,
					)
				else:
					response = self._session.request(
						method=method,
						url=url,
						headers=merged_headers,
						params=params,
						json=payload,
						timeout=timeout,
					)
				if log:
					print("=" * 82)
					print(f"Request {method} {url} {response.status_code}")
				response.raise_for_status()
			except HTTPError as err:
				self._log_http_error(err.response, attempt, retries)
				print(f"HTTP Error {type(err).__name__} - {err}")
				sleep(2**attempt * backoff_factor)
				if attempt == retries - 1:
					return err.response
				continue
			except (ReqConnectionError, Timeout) as err:
				print(f"Network error ({type(err).__name__}): {err}")
				if attempt == retries - 1:
					raise
				sleep(2**attempt * backoff_factor)
			except RequestException as err:
				print(f"Request failed: {type(err).__name__} - {err}")
				break
			except Exception as err:
				print(err)
				print(f"Unknown error: {type(err).__name__} - {err}")
			else:
				if log:
					self._log_request(response)
				return response
		return cast("Response", None)

	def _log_http_error(self, response: Response, attempt: int, max_attempts: int) -> None:
		"""
		记录HTTP错误的详细信息
		"""
		try:
			# 提取请求信息
			request_info = {
				"method": response.request.method,
				"url": response.request.url,
				"headers": dict(response.request.headers),
				"body": response.request.body[:1000] if response.request.body else None,
			}
			# 提取响应信息,安全处理可能不存在的键
			response_info = {
				"status_code": response.status_code,
				"headers": dict(response.headers),
				"text": response.text[:1000] if response.text else None,
			}
			# 尝试解析JSON响应,避免因解析失败导致日志记录中断
			try:
				response_info["json"] = response.json()
			except Exception:
				response_info["json"] = "Failed to parse JSON"
			# 提取额外的上下文信息
			context_info = {
				"attempt": attempt + 1,
				"max_attempts": max_attempts,
				"session_identity": self._identity,
				"timestamp": tool.TimeUtils().format_timestamp(),
			}
			# 构建完整的日志条目
			log_entry = (
				f"{'=' * 80}\n"
				f"HTTP Error {response.status_code}\n"
				f"Timestamp: {context_info['timestamp']}\n"
				f"Attempt {context_info['attempt']}/{context_info['max_attempts']}\n"
				f"Session Identity: {context_info['session_identity']}\n\n"
				f"Request:\n"
				f"  Method: {request_info['method']}\n"
				f"  URL: {request_info['url']}\n"
				f"  Headers: {request_info['headers']}\n"
				f"  Body: {request_info['body']}\n\n"
				f"Response:\n"
				f"  Status: {response_info['status_code']}\n"
				f"  Headers: {response_info['headers']}\n"
				f"  Text: {response_info['text']}\n"
				f"  JSON: {response_info['json']}\n"
				f"{'=' * 80}\n\n"
			)
			# 写入日志文件
			self._file.file_write(path=ERROR_LOG_PATH, content=log_entry, method="a")
			# 同时在控制台输出简要信息
			print(f"[ERROR] HTTP {response.status_code} - Logged to {ERROR_LOG_PATH}")
		except Exception as e:
			# 确保日志记录过程中不会引发新的异常
			print(f"Failed to log HTTP error: {e}")

	def fetch_data(  # noqa: PLR0914
		self,
		endpoint: str,
		params: dict,
		payload: dict | None = None,
		limit: int | None = None,
		fetch_method: Literal["GET", "POST"] = "GET",
		total_key: str = "total",
		data_key: str = "items",
		pagination_method: Literal["offset", "page"] = "offset",
		config: PaginationConfig | None = None,
	) -> Generator[dict]:
		"""获取分页API数据
		Args:
			endpoint: API端点地址
			params: 基础请求参数
			payload: POST请求负载
			limit: 最大返回条目数
			fetch_method: 请求方法 (GET/POST)
			total_key: 总条目数键名
			data_key: 数据列表键名
			pagination_method: 分页方式 (offset/page)
			config: 分页参数配置
		Yields:
			数据条目
		Raises:
			ValueError: 无效分页配置或参数错误
		"""  # noqa: DOC402
		# 合并分页配置参数
		config_: PaginationConfig = {
			"amount_key": "limit",
			"offset_key": "offset",
			"response_amount_key": "limit",
			"response_offset_key": "offset",
			**(config or {}),
		}
		# 参数副本避免污染原始参数
		base_params = params.copy()
		yielded_count = 0
		# 处理初始请求
		initial_response: Response = self.send_request(endpoint, fetch_method, base_params, payload)
		if not initial_response:
			return
		initial_data = initial_response.json()
		first_page = cast("list[dict]", self.tool.DataProcessor().get_nested_value(initial_data, data_key))
		total_items = int(cast("int", self.tool.DataProcessor().get_nested_value(initial_data, total_key)))
		# 安全获取分页参数配置
		amount_key: Literal["limit", "page_size", "current_page"] = config_.get("amount_key", "limit")
		page_size_key: Literal["limit", "page_size"] = config_.get("response_amount_key", "limit")
		offset_param_key: Literal["offset", "page", "current_page"] = config_.get("offset_key", "offset")
		# 计算每页数量
		items_per_page = base_params.get(
			amount_key,
			initial_data.get(page_size_key, 0),
		)
		if items_per_page <= 0:
			msg = f"无效的每页数量: {items_per_page}"
			raise ValueError(msg)
		# 处理首屏数据
		for item in first_page:
			yield item
			yielded_count += 1
			if limit and yielded_count >= limit:
				return
		# 计算总页数
		total_pages = (total_items + items_per_page - 1) // items_per_page
		# 分页请求循环
		for current_page in range(1, total_pages):
			page_params = base_params.copy()
			# 设置分页参数
			if pagination_method == "offset":
				page_params[offset_param_key] = current_page * items_per_page
			elif pagination_method == "page":
				page_params[offset_param_key] = current_page + 1  # 页码通常从1开始
			else:
				msg = f"不支持的分页方式: {pagination_method}"
				raise ValueError(msg)
			# 发送分页请求
			page_response = self.send_request(endpoint, fetch_method, page_params, payload)
			if not page_response:
				continue
			# 处理分页数据
			page_data = cast("list[dict]", self.tool.DataProcessor().get_nested_value(page_response.json(), data_key))
			for item in page_data:
				yield item
				yielded_count += 1
				if limit and yielded_count >= limit:
					return

	def switch_account(self, token: str, identity: Literal["judgement", "average", "edu", "blank"]) -> None:
		"""改进版的会话切换方法,确保完全隔离会话状态"""
		# 清除前一会话状态
		self._clean_session()
		if identity == "edu":
			if self._sessions["edu"]:
				self._sessions["edu"].close()
				del self._sessions["edu"]
			new_session = Session()
			adapter = HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=0)
			new_session.mount("http://", adapter)
			new_session.mount("https://", adapter)
			new_session.headers.update(self._create_headers())
			new_session.headers["Authorization"] = f"Bearer {token}"
			new_session.cookies.clear()  # 确保清除Cookie
			self._sessions["edu"] = new_session
			self._session = new_session
		else:
			self._session = cast("Session", self._sessions[identity])
			self._clean_session()
			self._session.headers["Authorization"] = f"Bearer {token}"
			self._session.cookies.clear()  # 确保清除Cookie
		self._identity = identity
		print(f"切换到 {identity} | 会话ID: {id(self._session)} | Token: {token[:10]}...")
		self._update_token_storage(token, identity)

	def _clean_session(self) -> None:
		"""更彻底的会话清理方法"""
		if not self._session:
			return
		headers_to_keep: set[str] = set(self._config.PROGRAM.HEADERS.keys()) - {"Authorization", "Cookie"}
		new_headers: dict[str, str] = {k: v for k, v in self._config.PROGRAM.HEADERS.items() if k in headers_to_keep}
		self._session.headers.clear()
		self._session.headers.update(new_headers)
		self._session.cookies = RequestsCookieJar()  # 替换为全新的空CookieJar
		# 清除连接池
		if hasattr(self._session, "adapters"):
			for adapter in self._session.adapters.values():
				adapter.close()

	def _create_headers(self) -> dict:
		"""创建完全干净的请求头,排除敏感信息"""
		clean_headers = self._config.PROGRAM.HEADERS.copy()
		for header in ["Authorization", "Cookie", "X-Identity", "X-User-Id"]:
			if header in clean_headers:
				del clean_headers[header]
		return clean_headers

	def cookie_to_str(self, cookies: RequestsCookieJar | dict | str) -> str:
		"""更安全的cookie更新方法"""
		# 仅在明确需要时使用,默认禁用
		self._session.cookies.clear()
		if "Cookie" in self._session.headers:
			del self._session.headers["Cookie"]

		def _to_cookie_str(cookie: RequestsCookieJar | dict | str) -> str:
			if isinstance(cookie, RequestsCookieJar):
				return "; ".join(f"{k}={v}" for k, v in cookie.get_dict().items())
			if isinstance(cookie, dict):
				return "; ".join(f"{k}={v}" for k, v in cookie.items())
			if isinstance(cookie, str):
				return ";".join(part.strip() for part in cookie.split(";") if "=" in part and len(part.split("=")) == 2)  # noqa: PLR2004
			msg = f"不支持的Cookie类型: {type(cookie).__name__}"
			raise TypeError(msg)

		return _to_cookie_str(cookies)

	def _update_token_storage(self, token: str, identity: str) -> None:
		"""更新token存储"""
		match identity:
			case "average":
				self.token.average = token
			case "edu":
				self.token.edu = token
			case "judgement":
				self.token.judgement = token
			case "blank":
				pass

	def _log_request(self, response: Response) -> None:
		"""简化的日志记录,使用文本格式而不是字典"""
		log_entry = (
			f"[{tool.TimeUtils().format_timestamp()}]\n"
			f"Method: {response.request.method}\n"
			f"URL: {response.url}\n"
			f"Status: {response.status_code}\n"
			f"{'*' * 50}\n"
			f"Request Body: {response.request.body}\n"
			f"Request Headers: {response.request.headers}\n"
			f"{'*' * 50}\n"
			f"Response Headers: {response.headers}\n"
			f"Response: {response.text}\n"
			f"{'=' * 50}\n\n"
		)
		self._file.file_write(path=LOG_FILE_PATH, content=log_entry, method="a")

	@staticmethod
	def _get_default_pagination_config(method: str) -> PaginationConfig:
		return {
			"amount_key": "limit" if method == "GET" else "page_size",
			"offset_key": "offset" if method == "GET" else "current_page",
			"response_amount_key": "limit",
			"response_offset_key": "offset",
		}


@singleton
class FileUploader:
	def __init__(self) -> None:
		self.client = CodeMaoClient()

	def upload(self, file_path: Path, method: Literal["pgaot", "codemao", "codegame"], save_path: str = "aumiao") -> str:
		"""
		统一文件上传接口

		参数:
			file_path: 文件路径
			method: 上传方式 (pgaot/codegame/codemao)
			save_path: 存储路径前缀
		返回:
			文件完整URL
		"""
		if method == "pgaot":
			return self._upload_via_pgaot(file_path, save_path)
		if method == "codegame":
			return self._upload_via_codegame(file_path, save_path)
		if method == "codemao":
			return self._upload_via_codemao(file_path, save_path)
		msg = f"Unsupported upload method: {method}"
		raise ValueError(msg)

	def _upload_via_pgaot(self, file_path: Path, save_path: str) -> str:
		"""Pgaot服务器上传"""
		with file_path.open("rb") as file_obj:
			files = {"file": (file_path.name, file_obj)}
			data = {"path": save_path}
			response = self.client.send_request(
				endpoint="https://api.pgaot.com/user/up_cat_file",
				method="POST",
				files=files,
				payload=data,
				timeout=120,
			)
		return response.json()["url"]

	def _upload_via_codegame(self, file_path: Path, save_path: str) -> str:
		"""七牛云上传(code.game)"""
		token_info = self._get_codegame_token(prefix=save_path, file_path=file_path)
		with file_path.open("rb") as file_obj:
			files = {"file": (file_path.name, file_obj)}
			data = {
				"token": token_info["token"],
				"key": token_info["file_path"],
				"fname": "avatar",
			}
			response = self.client.send_request(
				endpoint=token_info["upload_url"],
				method="POST",
				files=files,
				payload=data,
				timeout=120,
			)
		result = response.json()
		return f"{token_info['pic_host']}/{result['key']}"

	def _upload_via_codemao(self, file_path: Path, save_path: str) -> str:
		"""七牛云上传(codemao)"""
		unique_name = f"{save_path}/{file_path.name}"
		token_info = self._get_codemao_token(file_path=unique_name)
		with file_path.open("rb") as file_obj:
			files = {"file": (file_path.name, file_obj)}
			data = {
				"token": token_info["token"],
				"key": token_info["file_path"],
				"fname": file_path.name,
			}
			self.client.send_request(
				endpoint=token_info["upload_url"],
				method="POST",
				files=files,
				payload=data,
				timeout=120,
			)
		return token_info["pic_host"] + token_info["file_path"]

	def _get_codemao_token(self, file_path: str, **kwargs: ...) -> dict:
		"""获取codemao上传凭证(私有)"""
		params = {
			"projectName": kwargs.get("project_name", "community_frontend"),
			"filePaths": file_path,
			"filePath": file_path,
			"tokensCount": 1,
			"fileSign": "p1",
			"cdnName": kwargs.get("cdn_name", "qiniu"),
		}
		response = self.client.send_request(
			endpoint="https://open-service.codemao.cn/cdn/qi-niu/tokens/uploading",
			method="GET",
			params=params,
		)
		data = response.json()
		return {
			"token": data["tokens"][0]["token"],
			"file_path": data["tokens"][0]["file_path"],
			"upload_url": data["upload_url"],
			"pic_host": data["bucket_url"],
		}

	def _get_codegame_token(self, prefix: str, file_path: Path) -> dict:
		"""获取code.game上传凭证(私有)"""
		params = {"prefix": prefix, "bucket": "static", "type": file_path.suffix}
		response = self.client.send_request(endpoint="https://oversea-api.code.game/tiger/kitten/cdn/token/1", method="GET", params=params)
		data = response.json()
		return {
			"token": data["data"][0]["token"],
			"file_path": data["data"][0]["filename"],
			"pic_host": data["bucket_url"],
			"upload_url": "https://upload.qiniup.com",
		}
