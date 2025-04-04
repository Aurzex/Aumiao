import time
from collections.abc import Generator
from dataclasses import dataclass
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Literal, TypedDict, cast

import requests
from requests.cookies import RequestsCookieJar
from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import HTTPError, RequestException, Timeout

from . import data, file, tool
from .decorator import singleton

LOG_DIR: Path = Path.cwd() / ".log"
LOG_FILE_PATH: Path = LOG_DIR / f"{int(time.time())}.txt"
DICT_ITEM = 2


@dataclass
class Token:
	average: str = ""
	edu: str = ""
	judgement: str = ""


class HTTPSTATUS(Enum):
	OK = 200
	CREATED = 201
	NO_CONTENT = 204


class PaginationConfig(TypedDict, total=False):
	"""分页配置参数类型定义"""

	amount_key: Literal["limit", "page_size", "current_page"]
	offset_key: Literal["offset", "page", "current_page"]
	response_amount_key: Literal["limit", "page_size"]
	response_offset_key: Literal["offset", "page"]


# class Loggable(Protocol):
# 	def file_write(self, path: Path, content: str, method: str) -> None: ...


HttpMethod = Literal["GET", "POST", "DELETE", "PATCH", "PUT"]
FetchMethod = Literal["GET", "POST"]


@singleton
class CodeMaoClient:
	def __init__(self) -> None:
		"""初始化客户端实例,增强配置管理"""
		self._session = requests.Session()
		self._config = data.SettingManager().data
		self._processor = tool.CodeMaoProcess()
		self._file = file.CodeMaoFile()
		self.token = Token()
		self.base_url = "https://api.codemao.cn"
		self.headers: dict[str, str] = self._config.PROGRAM.HEADERS.copy()
		self.tool_process = tool.CodeMaoProcess()
		LOG_DIR.mkdir(parents=True, exist_ok=True)

	def send_request(
		self,
		endpoint: str,
		method: HttpMethod,
		params: dict | None = None,
		payload: dict | None = None,
		headers: dict | None = None,
		retries: int = 1,
		backoff_factor: float = 0.3,
		timeout: float = 10.0,
		*,
		log: bool = True,
	) -> requests.Response:
		url = endpoint if endpoint.startswith("http") else f"{self.base_url}{endpoint}"
		merged_headers = {**self.headers, **(headers or {})}
		# self._session.headers.clear()
		for attempt in range(retries):
			try:
				response = self._session.request(method=method, url=url, headers=merged_headers, params=params, json=payload, timeout=timeout)
				# print("=" * 82)
				# print(f"Request {method} {url} {response.status_code}")
				# # if "Authorization" in response.request.headers:
				# # 	print(response.request.headers["Authorization"])
				# with contextlib.suppress(Exception):
				# 	print(response.json() if len(response.text) <= 100 else response.text[:100] + "...")
				response.raise_for_status()

			except HTTPError as err:
				print(f"HTTP Error {type(err).__name__} - {err}")
				if err.response.status_code in {429, 503}:
					time.sleep(2**attempt * backoff_factor)
					continue
				break
			except (ReqConnectionError, Timeout) as err:
				print(f"Network error ({type(err).__name__}): {err}")
				if attempt == retries - 1:
					raise
				time.sleep(2**attempt * backoff_factor)
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

		return cast("requests.Response", None)

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
		first_page = cast("list[dict]", self.tool_process.get_nested_value(initial_data, data_key))
		total_items = int(cast("int", self.tool_process.get_nested_value(initial_data, total_key)))

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
			page_data = cast("list[dict]", self.tool_process.get_nested_value(page_response.json(), data_key))
			for item in page_data:
				yield item
				yielded_count += 1
				if limit and yielded_count >= limit:
					return

	def switch_account(self, token: str, identity: Literal["judgement", "average", "edu"]) -> None:
		self.headers["Cookie"] = f"authorization={token}"
		self.headers["Authorization"] = token
		# print(f"\n切换到账户{identity}")
		match identity:
			case "average":
				self.token.average = token
			case "edu":
				self.token.edu = token
			case "judgement":
				self.token.judgement = token

	# def update_cookies(self, cookies: RequestsCookieJar | dict | str) -> None:
	# 	"""仅操作headers中的Cookie,不涉及session cookies"""
	# 	# 清除旧Cookie
	# 	if "Cookie" in self.headers:
	# 		del self.headers["Cookie"]

	# 	# 转换所有类型为Cookie字符串
	# 	def _to_cookie_str(cookie: RequestsCookieJar | dict | str) -> str:
	# 		if isinstance(cookie, RequestsCookieJar):
	# 			return "; ".join(f"{cookie.name}={cookie.value}" for cookie in cookie)
	# 		if isinstance(cookie, dict):
	# 			return "; ".join(f"{k}={v}" for k, v in cookie.items())
	# 		if isinstance(cookie, str):
	# 			# 过滤非法字符
	# 			return ";".join(part.strip() for part in cookie.split(";") if "=" in part and len(part.split("=")) == DICT_ITEM)
	# 		msg = f"不支持的Cookie类型: {type(cookie).__name__}"
	# 		raise TypeError(msg)

	# 	try:
	# 		cookie_str = _to_cookie_str(cookies)
	# 		if cookie_str:
	# 			self.headers["Cookie"] = cookie_str
	# 	except Exception as e:
	# 		print(f"Cookie更新失败: {e!s}")
	# 		msg = "无效的Cookie格式"
	# 		raise ValueError(msg) from e

	def _log_request(self, response: requests.Response) -> None:
		"""简化的日志记录,使用文本格式而不是字典"""
		log_entry = (
			f"[{time.strftime('%Y-%m-%d %H:%M:%S')}]\n"
			f"Method: {response.request.method}\n"
			f"URL: {response.url}\n"
			f"Status: {response.status_code}\n"
			f"Request Headers: {response.request.headers}\n"
			f"Response Headers: {response.headers}\n"
			f"Response: {response.text}\n"
			f"{'=' * 50}\n"
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

	@staticmethod
	def stream_upload(file_path: Path, upload_path: str = "aumiao", chunk_size: int = 8192) -> str:
		try:
			# 打开文件并定义生成器
			with file_path.open("rb") as f:

				def file_generator() -> Generator[bytes]:
					while True:
						chunk = f.read(chunk_size)
						if not chunk:
							break
						yield chunk

				# 将生成器内容包装为 BytesIO 对象,模拟文件对象
				file_content = BytesIO()
				for chunk in file_generator():
					file_content.write(chunk)
				file_content.seek(0)  # 重置文件指针

				files = {
					"file": (file_path.name, file_content, "application/octet-stream"),
				}
				data = {"path": upload_path}

				response = requests.post(
					url="https://api.pgaot.com/user/up_cat_file",
					files=files,
					data=data,
					timeout=120,
				)
				# 处理响应
				response.raise_for_status()  # 如果响应状态码不是 200,会抛出异常
				result = response.json()
				return result.get("url", None)
		except requests.exceptions.RequestException as e:
			return f"请求错误: {e}"
		except Exception as e:
			return f"上传出错: {e!s}"

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
