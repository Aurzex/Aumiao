from collections.abc import Generator
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from time import sleep
from typing import Literal, TypedDict, cast

from requests import Response
from requests import post as re_post
from requests.cookies import RequestsCookieJar
from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import HTTPError, RequestException, Timeout
from requests.sessions import Session

from . import data, file, tool
from .decorator import singleton

LOG_DIR: Path = data.CURRENT_DIR / ".log"
LOG_FILE_PATH: Path = LOG_DIR / f"{tool.TimeUtils().current_timestamp()}.txt"
DICT_ITEM = 2

MAX_CHARACTER = 100


@dataclass
class Token:
	average: str = ""
	edu: str = ""
	judgement: str = ""
	blank: str = ""


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


HttpMethod = Literal["GET", "POST", "DELETE", "PATCH", "PUT"]
FetchMethod = Literal["GET", "POST"]


@singleton
class CodeMaoClient:
	def __init__(self) -> None:
		"""初始化客户端实例,增强配置管理"""
		LOG_DIR.mkdir(parents=True, exist_ok=True)
		self._config = data.SettingManager().data
		self._default_session = Session()  # 默认会话用于非教育账号
		self._file = file.CodeMaoFile()
		self._identity: str | None = None
		self._session = self._default_session  # 当前活跃会话
		self.base_url = "https://api.codemao.cn"
		self.headers: dict[str, str] = self._config.PROGRAM.HEADERS.copy()
		self.token = Token()
		self.tool = tool
		self._sessions = {
			"judgement": Session(),
			"average": Session(),
			"blank": Session(),
			"edu_pool": [],
		}
		self._original_session: Session | None = None
		self.log_request: bool = data.SettingManager().data.PARAMETER.log

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
		log: bool = True,
	) -> Response:
		url = endpoint if endpoint.startswith("http") else f"{self.base_url}{endpoint}"
		merged_headers = {**self.headers, **(headers or {})}
		# self._session.headers.clear()
		log = bool(self.log_request and log)
		for attempt in range(retries):
			try:
				response = self._session.request(method=method, url=url, headers=merged_headers, params=params, json=payload, files=files, timeout=timeout)
				# if "Authorization" in response.request.headers:
				# 	print(response.request.headers["Authorization"])
				if log:
					print("=" * 82)
					print(f"Request {method} {url} {response.status_code}")
					# with contextlib.suppress(Exception):
					# 	print(response.json() if len(response.text) <= MAX_CHARACTER else response.text[:MAX_CHARACTER] + "...")
				response.raise_for_status()

			except HTTPError as err:
				print(f"HTTP Error {type(err).__name__} - {err}")
				sleep(2**attempt * backoff_factor)
				if attempt == retries - 1:
					return err.response  # type: ignore  # noqa: PGH003
				continue
				break
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
				# self.update_cookies(response.cookies)
				return response

		return cast("Response", None)

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
		"""
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
		initial_response = self.send_request(endpoint, fetch_method, base_params, payload)
		if not initial_response:
			return

		initial_data = initial_response.json()
		first_page = cast("list[dict]", self.tool.DataProcessor().get_nested_value(initial_data, data_key))
		total_items = int(cast("int", self.tool.DataProcessor().get_nested_value(initial_data, total_key)))

		# 安全获取分页参数配置
		amount_key = config_.get("amount_key", "limit")
		page_size_key = config_.get("response_amount_key", "limit")
		offset_param_key = config_.get("offset_key", "offset")

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
		"""改进后的会话管理"""
		# 保存原始会话状态(仅当从非edu切换到edu时)
		if identity == "edu" and self._identity in {"judgement", "average"}:
			self._original_session = self._session
			self._original_session.close()  # 关闭原始会话连接

		# 教育账号特殊处理
		if identity == "edu":
			# 关闭前一个教育会话
			if self._identity == "edu" and self._session in self._sessions["edu_pool"]:
				self._session.close()
				self._sessions["edu_pool"].remove(self._session)

			# 创建全新隔离会话
			new_session = Session()
			new_session.headers.update(self.headers.copy())
			new_session.headers["Authorization"] = f"Bearer {token}"
			new_session.cookies.clear()
			self._sessions["edu_pool"].append(new_session)
			self._session = new_session
		else:
			# 使用预定义的独立会话
			self._session = self._sessions[identity]
			self._session.headers["Authorization"] = f"Bearer {token}"

		# 保持原有token存储逻辑
		self._identity = identity
		print(f"切换到 {identity} | 会话ID: {id(self._session)}")
		match identity:
			case "average":
				self.token.average = token
			case "edu":
				self.token.edu = token
			case "judgement":
				self.token.judgement = token
			case "blank":
				pass

	def __del__(self) -> None:
		"""对象销毁时清理所有会话"""
		for session in self._sessions["edu_pool"]:
			session.close()
		self._sessions["judgement"].close()
		self._sessions["average"].close()
		self._default_session.close()

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

	def update_cookies(self, cookies: RequestsCookieJar | dict | str) -> None:
		# 清除旧Cookie
		if "Cookie" in self.headers:
			del self.headers["Cookie"]

		# 转换所有类型为Cookie字符串
		def _to_cookie_str(cookie: RequestsCookieJar | dict | str) -> str:
			if isinstance(cookie, RequestsCookieJar):
				return "; ".join(f"{cookie.name}={cookie.value}" for cookie in cookie)
			if isinstance(cookie, dict):
				return "; ".join(f"{k}={v}" for k, v in cookie.items())
			if isinstance(cookie, str):
				# 过滤非法字符
				return ";".join(part.strip() for part in cookie.split(";") if "=" in part and len(part.split("=")) == DICT_ITEM)
			msg = f"不支持的Cookie类型: {type(cookie).__name__}"
			raise TypeError(msg)

		try:
			cookie_str = _to_cookie_str(cookies)
			if cookie_str:
				self.headers["Cookie"] = cookie_str
		except Exception as e:
			print(f"Cookie更新失败: {e!s}")
			msg = "无效的Cookie格式"
			raise ValueError(msg) from e


class FileUploader:
	def __init__(self, codemao_cookie: str | None = None) -> None:
		self.codemao_cookie = codemao_cookie

	@staticmethod
	def upload_via_pgaot(file_path: Path, save_path: str = "aumiao") -> str:
		"""直接上传到Pgaot服务器(使用默认文件类型)"""
		file_obj = file_path.open("rb")
		files = {"file": (file_path.name, file_obj, "application/octet-stream")}
		data = {"path": save_path}
		response = re_post(
			url="https://api.pgaot.com/user/up_cat_file",
			files=files,
			data=data,
			timeout=120,
		)
		file_obj.close()  # Ensure the file is closed
		return response.json()

	def upload_via_codemao(self, file_path: Path) -> str:
		"""通过编程猫接口上传到七牛云CDN(使用默认文件类型)"""
		# Generate unique filename with timestamp
		timestamp = tool.TimeUtils().current_timestamp()
		unique_name = f"aumiao/{timestamp}{file_path.name}"

		# 1. 获取上传Token (with unique filename)
		token_info = self.get_codemao_token(
			file_path=unique_name,  # Pass the unique path
		)

		# 2. 上传文件
		with file_path.open("rb") as file_obj:
			files = {"file": (file_path.name, file_obj, "application/octet-stream")}
			data = {
				"token": token_info["token"],
				"key": token_info["file_path"],
				"fname": file_path.name,  # Add original filename
			}
			_response = re_post(
				token_info["upload_url"],
				files=files,
				data=data,
				timeout=120,
			)

		return token_info["pic_host"] + token_info["file_path"]

	@staticmethod
	def get_codemao_token(
		file_path: str = "aumiao",  # Now accepts custom path
		project_name: str = "community_frontend",
		cdn_name: str = "qiniu",
	) -> dict:
		"""获取七牛云上传凭证(封装原GET请求)"""
		params = {
			"projectName": project_name,
			"filePaths": file_path,
			"filePath": file_path,
			"tokensCount": 1,
			"fileSign": "p1",
			"cdnName": cdn_name,
		}

		response = CodeMaoClient().send_request(endpoint="https://open-service.codemao.cn/cdn/qi-niu/tokens/uploading", method="GET", params=params)

		data = response.json()
		return {"token": data["tokens"][0]["token"], "file_path": data["tokens"][0]["file_path"], "upload_url": data["upload_url"], "pic_host": data["bucket_url"]}
