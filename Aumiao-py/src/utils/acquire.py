from collections.abc import Generator
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from time import sleep
from typing import Literal, TypedDict, cast

from requests import Response
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
	average: str = field(default="", metadata={"track": False})
	edu: str = field(default="", metadata={"track": False})
	judgement: str = field(default="", metadata={"track": False})
	blank: str = field(default="", metadata={"track": False})

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


@singleton
class CodeMaoClient:
	def __init__(self) -> None:
		"""初始化客户端实例,增强配置管理"""
		LOG_DIR.mkdir(parents=True, exist_ok=True)
		self._config = data.SettingManager().data
		self._file = file.CodeMaoFile()
		self.base_url = "https://api.codemao.cn"
		self.headers: dict[str, str] = self._config.PROGRAM.HEADERS.copy()
		self.token = Token()
		self.tool = tool
		# 初始化所有会话
		self._sessions = {
			"judgement": Session(),
			"average": Session(),
			"blank": Session(),
			"edu": Session(),  # 为edu也预创建会话
		}
		# 设置当前会话和身份
		self._session = self._sessions["blank"]
		self._identity = "blank"
		self.log_request: bool = data.SettingManager().data.PARAMETER.log
		# 初始化所有会话的headers
		for session in self._sessions.values():
			session.headers.update(self.headers.copy())

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
		"""发送HTTP请求"""
		url = endpoint if endpoint.startswith("http") else f"{self.base_url}{endpoint}"
		# 合并headers,优先级: 临时headers > 会话headers > 全局headers
		merged_headers = {
			**self.headers,
			**dict(self._session.headers),
			**(headers or {}),
		}
		# 移除冲突的headers
		merged_headers.pop("Cookie", None)
		if files:
			merged_headers.pop("Content-Type", None)
			merged_headers.pop("Content-Length", None)
		# 清除会话cookies防止自动添加
		self._session.cookies.clear()
		log_enabled = bool(self.log_request and log)
		for attempt in range(retries):
			try:
				request_args = {
					"method": method,
					"url": url,
					"headers": merged_headers,
					"params": params,
					"timeout": timeout,
					"stream": stream,
				}
				if files:
					request_args.update({"data": payload, "files": files})
				else:
					request_args["json"] = payload
				response = self._session.request(**request_args)  # pyright: ignore[reportArgumentType]
				if log_enabled:
					print("=" * 82)
					print(f"Request {method} {url} {response.status_code}")
				response.raise_for_status()
			except HTTPError as err:
				print(f"HTTP Error {type(err).__name__} - {err}")
				if attempt == retries - 1:
					return err.response
				sleep(2**attempt * backoff_factor)
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
				print(f"Unknown error: {type(err).__name__} - {err}")
				break
			else:
				if log_enabled:
					self._log_request(response)
				return response
		return cast("Response", None)

	def switch_account(self, token: str, identity: Literal["judgement", "average", "edu", "blank"]) -> None:
		"""切换账号 - 优化版本,仅更换session和token"""
		if identity not in self._sessions:
			msg = f"不支持的账号类型: {identity}"
			raise ValueError(msg)
		# 直接切换到对应的session
		self._session = self._sessions[identity]
		self._identity = identity
		# 更新当前session的Authorization头
		self._session.headers["Authorization"] = f"Bearer {token}"
		# 清除可能存在的旧cookies
		self._session.cookies.clear()
		# 更新token存储
		self._update_token_storage(token, identity)
		print(f"切换到 {identity} | 会话ID: {id(self._session)}")

	def _update_token_storage(self, token: str, identity: str) -> None:
		"""更新token存储"""
		token_map = {
			"average": "average",
			"edu": "edu",
			"judgement": "judgement",
		}
		if identity in token_map:
			setattr(self.token, token_map[identity], token)

	# 其他方法保持不变...
	@staticmethod
	def _get_default_pagination_config(method: str) -> PaginationConfig:
		return {
			"amount_key": "limit" if method == "GET" else "page_size",
			"offset_key": "offset" if method == "GET" else "current_page",
			"response_amount_key": "limit",
			"response_offset_key": "offset",
		}

	def _get_pagination_info(
		self,
		endpoint: str,
		params: dict,
		payload: dict | None = None,
		fetch_method: Literal["GET", "POST"] = "GET",
		total_key: str = "total",
		data_key: str = "items",
		config: PaginationConfig | None = None,
		*,
		include_first_page: bool = False,
	) -> tuple[int, int, list, dict]:
		"""获取分页信息"""
		config_ = {
			"amount_key": "limit",
			"offset_key": "offset",
			"response_amount_key": "limit",
			"response_offset_key": "offset",
			**(config or {}),
		}
		amount_key = config_.get("amount_key", "limit")
		page_size_key = config_.get("response_amount_key", "limit")
		base_params = params.copy()
		original_limit = 0
		if not include_first_page and amount_key in base_params:
			original_limit = base_params[amount_key]
			base_params[amount_key] = 15
		initial_response = self.send_request(endpoint, fetch_method, base_params, payload)
		if not initial_response:
			return 0, 0, [], {}
		initial_data = initial_response.json()
		data_processor = self.tool.DataProcessor()
		total_items_raw = data_processor.get_nested_value(initial_data, total_key)
		try:
			total_items = int(total_items_raw) if total_items_raw is not None else 0
		except (ValueError, TypeError):
			total_items = 0
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
		first_page = []
		if include_first_page:
			first_page_raw = data_processor.get_nested_value(initial_data, data_key)
			first_page = first_page_raw if isinstance(first_page_raw, list) else []
		elif not include_first_page and amount_key in base_params:
			base_params[amount_key] = original_limit
		return total_items, items_per_page, first_page, initial_data

	def get_pagination_total(
		self,
		endpoint: str,
		params: dict,
		payload: dict | None = None,
		fetch_method: Literal["GET", "POST"] = "GET",
		total_key: str = "total",
		data_key: str = "items",
		config: PaginationConfig | None = None,
	) -> dict[Literal["total", "total_pages"], int]:
		"""获取分页总数"""
		total_items, items_per_page, _, _ = self._get_pagination_info(endpoint, params, payload, fetch_method, total_key, data_key, config, include_first_page=False)
		total_pages = 0 if total_items == 0 else (total_items + items_per_page - 1) // items_per_page
		return {"total": total_items, "total_pages": total_pages}

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
		total_items, items_per_page, first_page, _ = self._get_pagination_info(
			endpoint=endpoint, params=params, payload=payload, fetch_method=fetch_method, total_key=total_key, data_key=data_key, config=config, include_first_page=True
		)
		config_ = {"offset_key": "offset", **(config or {})}
		offset_param_key = config_.get("offset_key", "offset")
		base_params = params.copy()
		yielded_count = 0
		data_processor = self.tool.DataProcessor()
		# 处理第一页数据
		for item in first_page:
			yield item
			yielded_count += 1
			if limit and yielded_count >= limit:
				return
		if total_items <= len(first_page):
			return
		remaining_items = total_items - len(first_page)
		if limit:
			remaining_items = min(remaining_items, limit - yielded_count)
		if remaining_items <= 0:
			return
		total_pages = (remaining_items + items_per_page - 1) // items_per_page
		for page_idx in range(1, total_pages + 1):
			page_params = base_params.copy()
			if pagination_method == "offset":
				page_params[offset_param_key] = page_idx * items_per_page
			elif pagination_method == "page":
				page_params[offset_param_key] = page_idx + 1
			else:
				msg = f"不支持的分页方式: {pagination_method}"
				raise ValueError(msg)
			page_response = self.send_request(endpoint, fetch_method, page_params, payload)
			if not page_response:
				continue
			page_data_raw = data_processor.get_nested_value(page_response.json(), data_key)
			page_data = page_data_raw if isinstance(page_data_raw, list) else []
			for item in page_data:
				yield item
				yielded_count += 1
				if limit and yielded_count >= limit:
					return

	def _log_request(self, response: Response) -> None:
		"""记录请求日志"""
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


@singleton
class FileUploader:
	def __init__(self) -> None:
		self.client = CodeMaoClient()
		# 为文件上传创建独立的session,避免影响主会话状态
		self._upload_session = Session()
		self._config = data.SettingManager().data
		self.headers: dict[str, str] = self._config.PROGRAM.HEADERS.copy()

	def _upload_request(
		self,
		endpoint: str,
		method: HttpMethod = "POST",
		params: dict | None = None,
		payload: dict | None = None,
		files: dict | None = None,
		timeout: float = 120.0,
	) -> Response:
		"""
		专门用于文件上传的请求方法
		使用独立的会话,避免影响主客户端的会话状态
		"""
		# 文件上传时让requests自动设置Content-Type
		headers = self.headers
		if files:
			headers.pop("Content-Type", None)
			headers.pop("Content-Length", None)
		# 清除可能存在的cookies
		self._upload_session.cookies.clear()
		request_args = {
			"method": method,
			"url": endpoint,
			"headers": headers,
			"params": params,
			"timeout": timeout,
		}
		if files:
			request_args.update({"data": payload, "files": files})
		else:
			request_args["json"] = payload
		response = self._upload_session.request(**request_args)  # type: ignore  # noqa: PGH003
		response.raise_for_status()
		return response

	def upload(self, file_path: Path, method: Literal["pgaot", "codemao", "codegame"], save_path: str = "aumiao") -> str:
		"""统一文件上传接口"""
		upload_methods = {
			"pgaot": self._upload_via_pgaot,
			"codegame": self._upload_via_codegame,
			"codemao": self._upload_via_codemao,
		}
		if method not in upload_methods:
			msg = f"不支持的上传方式: {method}"
			raise ValueError(msg)
		return upload_methods[method](file_path, save_path)

	def _upload_via_pgaot(self, file_path: Path, save_path: str) -> str:
		"""Pgaot服务器上传"""
		with file_path.open("rb") as file_obj:
			files = {"file": (file_path.name, file_obj)}
			data = {"path": save_path}
			response = self._upload_request(
				endpoint="https://api.pgaot.com/user/up_cat_file",
				files=files,
				payload=data,
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
			response = self._upload_request(
				endpoint=token_info["upload_url"],
				files=files,
				payload=data,
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
			self._upload_request(
				endpoint=token_info["upload_url"],
				files=files,
				payload=data,
			)
		return token_info["pic_host"] + token_info["file_path"]

	def _get_codemao_token(self, file_path: str, **kwargs: ...) -> dict:
		"""获取codemao上传凭证 - 使用主客户端"""
		params = {
			"projectName": kwargs.get("project_name", "community_frontend"),
			# 有community_fronted和neko两种
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
		"""获取code.game上传凭证 - 使用主客户端"""
		params = {"prefix": prefix, "bucket": "static", "type": file_path.suffix}
		response = self.client.send_request(endpoint="https://oversea-api.code.game/tiger/kitten/cdn/token/1", method="GET", params=params)
		data = response.json()
		return {
			"token": data["data"][0]["token"],
			"file_path": data["data"][0]["filename"],
			"pic_host": data["bucket_url"],
			"upload_url": "https://upload.qiniup.com",
		}
