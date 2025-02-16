import time
from collections.abc import Generator
from collections.abc import Iterable as IterableABC
from dataclasses import asdict, is_dataclass
from typing import Any, TypeVar, Union, cast, overload

from .decorator import singleton

Data = Union[list[dict], dict]  # noqa: UP007
Nested_dict = dict[str, Any]
T = TypeVar("T")


@singleton
class CodeMaoProcess:
	@overload
	def filter_data(
		self,
		data: dict,
		reserve: list[str] | None = None,
		exclude: list[str] | None = None,
	) -> dict: ...

	@overload
	def filter_data(
		self,
		data: list[dict],
		reserve: list[str] | None = None,
		exclude: list[str] | None = None,
	) -> list[dict]: ...
	@overload
	def filter_data(
		self,
		data: Generator[dict],
		reserve: list[str] | None = None,
		exclude: list[str] | None = None,
	) -> Generator[dict]: ...

	def filter_data(
		self,
		data: dict | list[dict] | Generator[dict],
		reserve: list[str] | None = None,
		exclude: list[str] | None = None,
	) -> dict | list[dict] | Generator[dict]:
		"""
		处理输入数据,根据 `reserve` 或 `exclude` 进行键筛选

		:param data: 输入数据(字典/列表/生成器)
		:param reserve: 保留的键列表
		:param exclude: 排除的键列表
		:return: 筛选后的数据(保持原数据结构或生成器)
		:raises ValueError: 参数冲突或数据类型错误
		"""
		if reserve and exclude:
			msg = "请仅提供 'reserve' 或 'exclude' 中的一个参数"
			raise ValueError(msg)

		def filter_item(item: dict) -> dict:
			"""键过滤核心逻辑"""
			if reserve:
				return {k: v for k, v in item.items() if k in reserve}
			if exclude:
				return {k: v for k, v in item.items() if k not in exclude}
			return dict(item)  # 无过滤条件返回副本

		# 处理字典类型
		if isinstance(data, dict):
			return filter_item(data)

		# 处理列表类型
		if isinstance(data, list):
			return [filter_item(item) for item in data if isinstance(item, dict)]

		# 处理生成器和其他可迭代对象(排除字符串等)
		if isinstance(data, IterableABC) and not isinstance(data, str | bytes):
			return (filter_item(item) for item in data if isinstance(item, dict))

		msg = f"不支持的数据类型: {type(data)}"
		raise ValueError(msg)

	# 以下其他方法保持不变...
	@staticmethod
	def insert_zero_width_chars(content: str) -> str:
		return "\u200b".join(content)

	@staticmethod
	def format_timestamp(timestamp: int) -> str:
		return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))

	def get_nested_value(self, data: Nested_dict, path: str | None) -> object:
		if not path:
			return data
		value = data
		for key in path.split("."):
			if not isinstance(value, dict):
				return None
			value = value.get(key)
		return value

	@staticmethod
	def convert_cookie_to_str(cookie: dict[str, str]) -> str:
		return "; ".join(f"{k}={v}" for k, v in cookie.items())

	def filter_items_by_values(self, data: Data, id_path: str, values: list[Any]) -> list[dict]:
		items = data.get("items", []) if isinstance(data, dict) else data if isinstance(data, list) else []
		return [item for item in items if self.get_nested_value(item, id_path) in values]

	@staticmethod
	def deduplicate(sequence: list[Any]) -> list[Any]:
		seen = set()
		return [x for x in sequence if not (x in seen or seen.add(x))]


class CodeMaoRoutine:
	def __init__(self) -> None:
		# 初始化CodeMaoProcess类
		self.process = CodeMaoProcess()

	@staticmethod
	def get_timestamp() -> float:
		return time.time()

	def display_data_changes(
		self,
		before_data: dict[str, Any] | T,
		after_data: dict[str, Any] | T,
		metrics: dict[str, str],
		date_field: str | None = None,
	) -> None:
		def to_dict(data: dict[str, Any] | T) -> dict[str, Any]:
			# 将数据转换为字典
			if isinstance(data, dict):
				return data
			if hasattr(data, "__dict__"):
				return vars(data)
			if is_dataclass(data):
				return asdict(cast(Any, data))
			msg = f"Unsupported data type: {type(data)}"
			raise TypeError(msg)

		try:
			before_dict = to_dict(before_data)
			after_dict = to_dict(after_data)
		except TypeError as e:
			print(f"Error converting data: {e}")
			return

		if date_field:
			fmt = self.process.format_timestamp
			print(f"时间段: {fmt(before_dict[date_field])} → {fmt(after_dict[date_field])}")

		for field, label in metrics.items():
			before = before_dict.get(field, 0)
			after = after_dict.get(field, 0)
			print(f"{label}: {after - before:+} (当前: {after}, 初始: {before})")

	def find_prefix_suffix(self, text: str | int, candidates: list[str]) -> tuple[int | None, int | None]:
		target = str(text)
		for item in candidates:
			if isinstance(item, str) and target in item:
				parts = item.split(".", 1)
				try:
					return int(parts[0]), int(parts[1]) if len(parts) > 1 else None
				except ValueError:
					continue
		return (None, None)

	def merge_user_data(self, data_list: list[dict]) -> dict:
		merged = {}
		counter = {}
		for item in filter(None, data_list):
			for key, value in item.items():
				counter[key] = counter.get(key, 0) + 1
				if isinstance(value, dict):
					merged.setdefault(key, {}).update(value)
				else:
					merged[key] = value
		return {k: v for k, v in merged.items() if counter[k] > 1}
