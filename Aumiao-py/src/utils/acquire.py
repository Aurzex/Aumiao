import time
from collections.abc import Generator
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Literal, Protocol, TypedDict, cast

import requests
from requests.cookies import RequestsCookieJar
from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import HTTPError, RequestException, Timeout

from . import data, file, tool
from .decorator import singleton

LOG_DIR: Path = Path.cwd() / "log"
LOG_FILE_PATH: Path = LOG_DIR / f"{int(time.time())}.txt"
DICT_ITEM = 2


class HTTPSTATUS(Enum):
	OK = 200
	CREATED = 201
	NO_CONTENT = 204


# 类型定义增强
class PaginationConfig(TypedDict, total=False):
	amount_key: Literal["limit", "page_size", "current_page"]
	offset_key: Literal["offset", "page", "current_page"]
	response_amount_key: Literal["limit", "page_size"]
	response_offset_key: Literal["offset", "page"]


class Loggable(Protocol):
	def file_write(self, path: Path, content: str, method: str) -> None: ...


HttpMethod = Literal["GET", "POST", "DELETE", "PATCH", "PUT"]
FetchMethod = Literal["GET", "POST"]


@singleton
class CodeMaoClient:
	def __init__(self) -> None:
		"""初始化客户端实例,增强配置管理"""
		self._session = requests.Session()
		self._config = data.SettingManager().data
		self._processor = tool.CodeMaoProcess()
		self._file: Loggable = file.CodeMaoFile()

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
		"""增强型请求方法,支持重试机制和更安全的超时处理"""
		url = endpoint if endpoint.startswith("http") else f"{self.base_url}{endpoint}"
		merged_headers = {**self.headers, **(headers or {})}
		self._session.headers.clear()
		for attempt in range(retries):
			try:
				response = self._session.request(method=method, url=url, headers=merged_headers, params=params, json=payload, timeout=timeout)
				# print(f"Request {method} {url} {response.status_code}")
				# print(response.json() if len(response.text) <= 100 else response.text[:100] + "...")
				response.raise_for_status()

			except HTTPError as err:
				print(f"HTTP Error {type(err).__name__} - {err}")
				if err.response.status_code in (429, 503):
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

		return cast(requests.Response, None)

	def fetch_data(
		self,
		endpoint: str,
		params: dict,
		payload: dict | None = None,
		limit: int | None = None,
		fetch_method: FetchMethod = "GET",
		total_key: str = "total",
		data_key: str = "items",
		pagination_method: Literal["offset", "page"] = "offset",
		args: dict[
			Literal["amount", "remove", "res_amount_key", "res_remove_key"],
			Literal["limit", "offset", "page", "current_page", "page_size"],
		] = {},
	) -> Generator[dict]:
		"""分页获取数据生成器版本"""
		# 设置默认分页参数
		args.setdefault("amount", "limit")
		args.setdefault("remove", "offset")
		args.setdefault("res_amount_key", "limit")
		args.setdefault("res_remove_key", "offset")
		# 初始化计数器
		yielded_count = 0

		# 第一次请求
		initial_response = self.send_request(endpoint, fetch_method, params, payload)
		if not initial_response:
			return

		initial_json = initial_response.json()
		first_page_data: list = self.tool_process.get_nested_value(initial_json, data_key)  # type: ignore  # noqa: PGH003
		total_items = int(cast(str, self.tool_process.get_nested_value(initial_json, total_key)))

		items_per_page = params.get(args["amount"], initial_json.get(args["res_amount_key"], 0))

		# 处理第一页数据
		for item in first_page_data:
			yield item
			yielded_count += 1
			if limit and yielded_count >= limit:
				return

		# 计算总请求次数(从第二页开始)
		total_pages = (total_items + items_per_page - 1) // items_per_page
		for page in range(1, total_pages):
			# 更新分页参数
			if pagination_method == "offset":
				params[args["remove"]] = page * items_per_page
			elif pagination_method == "page":
				params[args["remove"]] = page + 1

			response = self.send_request(endpoint, fetch_method, params, payload=payload)
			if not response:
				continue

			page_data: list = self.tool_process.get_nested_value(response.json(), data_key)  # type: ignore  # noqa: PGH003
			for item in page_data:
				yield item
				yielded_count += 1
				if limit and yielded_count >= limit:  # 达到限制立即停止
					return

	def update_cookies(self, cookies: RequestsCookieJar | dict | str) -> None:
		"""仅操作headers中的Cookie,不涉及session cookies"""
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
		"""获取分页参数默认配置"""
		return {
			"amount_key": "limit" if method == "GET" else "page_size",
			"offset_key": "offset" if method == "GET" else "current_page",
			"response_amount_key": "limit",
			"response_offset_key": "offset",
		}

	def stream_upload(self, file_path: Path, upload_path: str = "aumiao", chunk_size: int = 8192) -> str:
		"""
		简单的流式上传实现
		:param file_path: 文件路径
		:param upload_path: 上传目标路径,默认为 "aumiao"
		:param chunk_size: 每次读取的文件块大小,默认为 8192 字节
		:return: 返回文件的 URL 和消息
		"""
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
