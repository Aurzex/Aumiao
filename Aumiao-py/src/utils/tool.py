from __future__ import annotations

import re
import time
from collections.abc import Generator, Iterable, Mapping
from dataclasses import asdict, is_dataclass
from html import unescape
from typing import TypeGuard, TypeVar, overload

DataObject = dict | list[dict] | Generator[dict, object]
T = TypeVar("T")


@staticmethod
def is_dataclass_instance[T](obj: T) -> TypeGuard[T]:
	"""检查对象是否是数据类实例(类型安全的检查方法)

	Args:
		obj (T): 要检查的对象

	Returns:
		TypeGuard[T]: 如果是数据类实例返回True

	Example:
		>>> @dataclass
		... class User:
		...     name: str
		>>> is_dataclass_instance(User("Alice"))  # False(类本身)
		>>> is_dataclass_instance(User("Alice"))  # True(实例)
	"""
	return not isinstance(obj, type) and is_dataclass(obj)


class DataProcessor:
	"""核心数据处理工具类"""

	@classmethod
	def filter_by_nested_values(
		cls,
		data: dict | Iterable[dict],
		id_path: str,
		target_values: Iterable[object],
		*,
		strict_mode: bool = False,
	) -> list[dict]:
		"""根据嵌套字段值过滤数据集

		Args:
			data: 输入数据,可以是单个字典或字典的可迭代集合
			id_path: 嵌套字段路径(使用点号分隔,如:"user.profile.id")
			target_values: 需要匹配的目标值集合
			strict_mode: 严格模式(路径类型不匹配时抛出异常)

		Returns:
			过滤后的字典列表

		Raises:
			ValueError: 路径格式错误或数据不符合预期结构
			TypeError: 严格模式下的类型不匹配

		Example:
			>>> data = [{"user": {"profile": {"id": 1}}}, {"user": {"profile": {"id": 2}}}]
			>>> DataProcessor.filter_by_nested_values(data, "user.profile.id", [1])
			[{'user': {'profile': {'id': 1}}}]
		"""
		if not isinstance(id_path, str) or not id_path:
			msg = "id_path 必须是非空字符串"
			raise ValueError(msg)

		if not isinstance(target_values, Iterable):
			msg = "target_values 必须是可迭代对象"
			raise TypeError(msg)

		items = cls._normalize_input(data)
		path_keys = id_path.split(".")

		results = []
		for item in items:
			try:
				current_value = item
				for key in path_keys:
					if not isinstance(current_value, Mapping):
						if strict_mode:
							msg = f"路径 {key} 处遇到非字典类型"
							raise ValueError(msg)
						current_value = None
						break
					current_value = current_value.get(key, None)

				if current_value in target_values:
					results.append(item)

			except (TypeError, AttributeError) as e:
				if strict_mode:
					msg = f"处理条目时发生错误: {e!s}"
					raise ValueError(msg) from e

		return results

	@staticmethod
	def _is_item_container(data: dict) -> TypeGuard[dict[str, Iterable[dict]]]:
		"""类型安全的项目容器检查

		Args:
			data: 需要检查的字典对象

		Returns:
			当data是包含items键且值为字典迭代器时返回True
		"""
		return "items" in data and isinstance(data["items"], Iterable)

	@overload
	@staticmethod
	def _normalize_input(data: dict) -> list[dict]: ...

	@overload
	@staticmethod
	def _normalize_input(data: Iterable[dict]) -> Iterable[dict]: ...

	@staticmethod
	def _normalize_input(data: dict | Iterable[dict]) -> Iterable[dict]:
		"""标准化输入数据格式(类型安全版本)

		Args:
			data: 输入数据(支持三种格式):
				1. 普通字典
				2. 包含items键的字典(自动展开items内容)
				3. 字典列表/生成器

		Returns:
			标准化的可迭代字典集合

		Example:
			>>> DataProcessor._normalize_input({"a": 1})
			[{'a': 1}]
			>>> DataProcessor._normalize_input({"items": [{"b": 2}]})
			[{'b': 2}]
			>>> DataProcessor._normalize_input([{"c": 3}, {"d": 4}])
			[{'c': 3}, {'d': 4}]
		"""
		if isinstance(data, dict):  # 改为精确检查dict类型
			if DataProcessor._is_item_container(data):
				return list(data["items"])
			return [data]
		if isinstance(data, Iterable):
			return data
		msg = "输入数据必须是字典或可迭代的字典集合"
		raise ValueError(msg)

	@classmethod
	def filter_data(
		cls,
		data: DataObject,
		*,
		include: list[str] | None = None,
		exclude: list[str] | None = None,
	) -> DataObject:
		"""通用字段过滤方法

		Args:
			data: 输入数据(字典/列表/生成器)
			include: 需要包含的字段列表
			exclude: 需要排除的字段列表

		Returns:
			过滤后的数据(保持原始结构)

		Raises:
			ValueError: 同时指定include和exclude

		Example:
			>>> data = {"name": "Alice", "age": 30, "email": "alice@example.com"}
			>>> DataProcessor.filter_data(data, include=["name", "age"])
			{'name': 'Alice', 'age': 30}
		"""
		if include and exclude:
			msg = "不能同时指定包含和排除字段"
			raise ValueError(msg)

		def _filter(item: dict) -> dict:
			return {k: v for k, v in item.items() if (include and k in include) or (exclude and k not in exclude) or (not include and not exclude)}

		if isinstance(data, dict):
			return _filter(data)
		if isinstance(data, (list, Generator)):
			return type(data)(_filter(item) for item in data)  # type: ignore  # noqa: PGH003
		msg = f"不支持的数据类型: {type(data)}"
		raise TypeError(msg)

	@classmethod
	def get_nested_value(cls, data: Mapping, path: str) -> object:
		"""安全获取嵌套字典值

		Args:
			data: 输入字典
			path: 点号分隔的字段路径

		Returns:
			找到的值或None

		Example:
			>>> data = {"user": {"profile": {"id": 1}}}
			>>> DataProcessor.get_nested_value(data, "user.profile.id")
			1
		"""
		keys = path.split(".")
		current = data
		for key in keys:
			if not isinstance(current, Mapping):
				return None
			current = current.get(key, None)
			if current is None:
				break
		return current

	@classmethod
	def deduplicate(cls, sequence: Iterable[object]) -> list[object]:
		"""保持顺序去重

		Args:
			sequence: 输入序列

		Returns:
			去重后的列表(保持原始顺序)

		Example:
			>>> DataProcessor.deduplicate([3, 2, 1, 2, 3])
			[3, 2, 1]
		"""
		seen = set()
		return [x for x in sequence if not (x in seen or seen.add(x))]


class DataConverter:
	"""数据转换工具类"""

	@staticmethod
	def convert_cookie(cookie: dict[str, str]) -> str:
		"""将字典格式cookie转换为字符串

		Example:
			>>> DataConverter.convert_cookie({"name": "value", "age": "20"})
			'name=value; age=20'
		"""
		return "; ".join(f"{k}={v}" for k, v in cookie.items())

	@staticmethod
	def to_serializable(data: object) -> dict[str, object]:
		"""转换为可序列化字典

		Args:
			data: 输入数据(支持数据类/对象/字典)

		Raises:
			TypeError: 不支持的类型

		Example:
			>>> @dataclass
			... class User:
			...     name: str
			>>> DataConverter.to_serializable(User("Alice"))
			{'name': 'Alice'}
		"""
		if isinstance(data, dict):
			return data.copy()
		if is_dataclass_instance(data):
			return asdict(data)
		if hasattr(data, "__dict__"):
			return vars(data)
		msg = f"不支持的类型: {type(data).__name__}。支持类型: dict, 数据类实例,或包含__dict__属性的对象"
		raise TypeError(msg)

	@staticmethod
	def html_to_text(
		html_content: str,
		*,
		replace_images: bool = True,  # 是否替换图片标签
		img_format: str = "[图片链接: {src}]",  # 图片替换格式
		merge_empty_lines: bool = False,  # 是否合并连续空行
		unescape_entities: bool = True,  # 是否解码HTML实体
		keep_line_breaks: bool = True,  # 是否保留段落换行
	) -> str:
		"""
		将HTML转换为可配置的纯文本

		:param html_content: 输入的HTML内容
		:param replace_images: 是否将图片替换为指定格式 (默认True)
		:param img_format: 图片替换格式,可用{src}占位符 (默认"[图片链接: {src}]")
		:param merge_empty_lines: 是否合并连续空行 (默认True)
		:param unescape_entities: 是否解码HTML实体如&amp; (默认True)
		:param keep_line_breaks: 是否保留原始段落换行 (默认True)
		:return: 格式化后的纯文本
		"""
		# 提取可能存在的嵌套外层<p>
		outer_match = re.match(r"<p\b[^>]*>(.*)</p>", html_content, re.DOTALL)
		inner_content = outer_match.group(1).strip() if outer_match else html_content

		# 修正段落提取逻辑
		paragraphs = re.findall(r"<p\b[^>]*>(.*?)</p>", inner_content, re.DOTALL)

		# 新增：处理无段落情况
		if not paragraphs:
			paragraphs = [inner_content]

		processed = []
		for content in paragraphs:
			# 图片标签处理
			if replace_images:

				def replace_img(match: re.Match) -> str:
					src = next((g for g in match.groups()[1:] if g), "")
					return img_format.format(src=unescape(src)) if src else img_format.format(src="")

				content = re.sub(  # noqa: PLW2901
					r'<img\b[^>]*?src\s*=\s*("([^"]+)"|\'([^\']+)\'|([^\s>]+))[^>]*>',
					replace_img,
					content,
					flags=re.IGNORECASE,
				)

			# 移除所有HTML标签
			text = re.sub(r"<.*?>", "", content, flags=re.DOTALL)

			# HTML实体解码
			if unescape_entities:
				text = unescape(text)

			# 清理空白并保留空行标记
			text = text.strip()
			processed.append(text if keep_line_breaks else text.replace("\n", " "))

		# 构建最终结果
		result = "\n".join(processed)

		# 空行合并处理
		if merge_empty_lines:
			result = re.sub(r"\n{2,}", "\n", result)

		return result.strip()


class StringProcessor:
	"""字符串处理工具类"""

	@staticmethod
	def insert_zero_width(text: str) -> str:
		"""插入零宽空格防爬

		Example:
			>>> StringProcessor.insert_zero_width("hello")
			'h\u200be\u200bl\u200bl\u200bo'
		"""
		return "\u200b".join(text)

	@staticmethod
	def find_substrings(text: str, candidates: Iterable[str]) -> tuple[int | None, int | None]:
		"""在候选中查找子字符串位置

		Args:
			text: 需要查找的文本
			candidates: 候选字符串集合

		Returns:
			(主ID, 子ID) 或 (None, None)

		Example:
			>>> StringProcessor.find_substrings("23", ["12.34", "45.23"])
			(45, 23)
		"""
		text = str(text)
		for candidate in candidates:
			if text in candidate:
				parts = candidate.split(".", 1)
				try:
					return int(parts[0]), int(parts[1]) if len(parts) > 1 else None
				except ValueError:
					continue
		return (None, None)


class TimeUtils:
	"""时间处理工具类"""

	@staticmethod
	def current_timestamp() -> float:
		"""获取当前时间戳

		Example:
			>>> isinstance(TimeUtils.current_timestamp(), float)
			True
		"""
		return time.time()

	@staticmethod
	def format_timestamp(ts: float) -> str:
		"""格式化时间戳为字符串

		Example:
			>>> TimeUtils.format_timestamp(1672531200)
			'2023-01-01 00:00:00'
		"""
		return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


class DataAnalyzer:
	"""数据分析工具类"""

	def compare_datasets(
		self,
		before: dict | object,
		after: dict | object,
		metrics: dict[str, str],
		timestamp_field: str | None = None,
	) -> None:
		"""对比数据集差异

		Args:
			before: 原始数据集(字典或对象)
			after: 新数据集(字典或对象)
			metrics: 需要对比的指标 {字段: 显示名称}
			timestamp_field: 时间戳字段名

		Example:
			>>> analyzer = DataAnalyzer()
			>>> before = {"users": 100}
			>>> after = {"users": 150}
			>>> analyzer.compare_datasets(before, after, {"users": "用户数"})
			用户数: +50 (当前: 150, 初始: 100)
		"""
		before_dict = self._to_dict(before)
		after_dict = self._to_dict(after)

		if timestamp_field:
			fmt = TimeUtils.format_timestamp
			print(f"时间段: {fmt(before_dict[timestamp_field])} → {fmt(after_dict[timestamp_field])}")

		for field, label in metrics.items():
			before_val = before_dict.get(field, 0)
			after_val = after_dict.get(field, 0)
			print(f"{label}: {after_val - before_val:+} (当前: {after_val}, 初始: {before_val})")

	@staticmethod
	def _to_dict(data: dict | object) -> dict:
		try:
			return DataConverter.to_serializable(data)
		except TypeError as e:
			msg = "数据格式转换失败"
			raise ValueError(msg) from e


class DataMerger:
	"""数据合并工具类"""

	@staticmethod
	def merge(datasets: Iterable[dict]) -> dict:
		"""智能合并多个字典(深度合并字典值)

		Args:
			datasets: 需要合并的字典集合

		Returns:
			合并后的字典

		Example:
			>>> DataMerger.merge([{"a": 1}, {"a": 2, "b": {"c": 3}}])
			{'a': 2, 'b': {'c': 3}}
		"""
		merged = {}
		for dataset in filter(None, datasets):
			for key, value in dataset.items():
				if isinstance(value, dict):
					merged.setdefault(key, {}).update(value)
				else:
					merged[key] = value
		return merged


class MathUtils:
	"""数学工具类"""

	@staticmethod
	def clamp(value: int, min_val: int, max_val: int) -> int:
		"""数值范围约束

		Example:
			>>> MathUtils.clamp(15, 0, 10)
			10
			>>> MathUtils.clamp(-5, 0, 10)
			0
		"""
		return max(min_val, min(value, max_val))
