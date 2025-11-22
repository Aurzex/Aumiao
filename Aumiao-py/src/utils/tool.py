from __future__ import annotations

import random
import re
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass, fields, is_dataclass
from functools import lru_cache
from html import unescape
from types import GeneratorType
from typing import Any, ClassVar, Literal, LiteralString, TypeGuard, TypeVar, final, overload

from src.utils.decorator import singleton

T = TypeVar("T")
# 类型别名定义
type DataDict = dict[str, Any]
type DataObject = DataDict | list[DataDict]
# 常量定义
FILE_SIZE: int = 1024


# 颜色配置类 - 使用更高效的数据结构
@final
class ColorConfig:
	"""颜色配置管理"""

	# 使用元组代替字典,提高访问性能
	_COLOR_MAP: ClassVar = {
		"COMMENT": "\033[38;5;245m",  # 辅助说明
		"ERROR": "\033[38;5;203m",  # 错误提示
		"MENU_ITEM": "\033[38;5;183m",  # 菜单项
		"MENU_TITLE": "\033[38;5;80m",  # 菜单标题
		"PROMPT": "\033[38;5;75m",  # 输入提示
		"RESET": "\033[0m",  # 重置样式
		"STATUS": "\033[38;5;228m",  # 状态信息
		"SUCCESS": "\033[38;5;114m",  # 成功提示
		"INFO": "\033[38;5;39m",  # 信息提示
		"WARNING": "\033[38;5;214m",  # 警告提示
	}
	# 预计算的分隔符,避免重复计算
	_SEPARATOR = f"{_COLOR_MAP['PROMPT']}══════════════════════════════════════════════════════════{_COLOR_MAP['RESET']}"

	@classmethod
	@lru_cache(maxsize=64)
	def get_color(cls, color_name: str) -> str:
		"""获取颜色代码,使用缓存提高性能"""
		return cls._COLOR_MAP.get(color_name, cls._COLOR_MAP["RESET"])

	@classmethod
	def get_separator(cls) -> str:
		"""获取分隔符"""
		return cls._SEPARATOR

	@classmethod
	def is_valid_color(cls, color_name: str) -> bool:
		"""验证颜色名称是否有效"""
		return color_name in cls._COLOR_MAP


# 颜色类型别名,提高类型安全性
ColorType = Literal["COMMENT", "ERROR", "MENU_ITEM", "MENU_TITLE", "PROMPT", "RESET", "STATUS", "SUCCESS", "INFO", "WARNING"]


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
		...	 name: str
		>>> is_dataclass_instance(User("Alice"))  # False(类本身)
		>>> is_dataclass_instance(User("Alice"))  # True(实例)
	"""
	return not isinstance(obj, type) and is_dataclass(obj)


# 类型定义
T = TypeVar("T")
DataDict = dict[str, Any]
DataObject = DataDict | list[DataDict] | Iterable[DataDict]  # pyright: ignore[reportAssignmentType]


class DataProcessor:
	"""核心数据处理工具类(修复版本)"""

	# 使用ClassVar修复可变类属性问题
	_path_cache: ClassVar[dict[str, tuple[str, ...]]] = {}

	@staticmethod
	def is_dataclass_instance(obj: object) -> TypeGuard[Any]:
		"""修复后的数据类实例检查"""
		return isinstance(obj, object) and not isinstance(obj, type) and is_dataclass(obj)

	@classmethod
	def _parse_path(cls, path: str) -> tuple[str, ...]:
		"""解析并缓存路径"""
		if path not in cls._path_cache:
			cls._path_cache[path] = tuple(path.split("."))
		return cls._path_cache[path]

	@classmethod
	def filter_by_nested_values(
		cls,
		data: DataObject,
		id_path: str,
		target_values: Iterable[object],
		*,
		strict_mode: bool = False,
	) -> list[DataDict]:
		"""性能优化的嵌套字段过滤"""
		# 参数验证优化
		if not id_path or not isinstance(id_path, str):
			msg = "id_path 必须是非空字符串"
			raise ValueError(msg)

		if not hasattr(target_values, "__iter__"):
			msg = "target_values 必须是可迭代对象"
			raise TypeError(msg)

		# 预处理目标值为集合(提高查找性能)
		target_set = set(target_values)
		path_keys = cls._parse_path(id_path)
		items = cls._normalize_input(data)

		# 使用列表推导式提高性能
		if strict_mode:
			return [item for item in items if cls._get_nested_strict(item, path_keys) in target_set]
		return [item for item in items if cls._get_nested_safe(item, path_keys) in target_set]

	@classmethod
	def _get_nested_strict(cls, data: Mapping[str, Any], path_keys: tuple[str, ...]) -> object:
		"""严格模式下的嵌套值获取"""
		current = data
		for key in path_keys:
			if not isinstance(current, Mapping):
				error_msg = f"路径 {key} 处遇到非字典类型: {type(current)}"
				raise TypeError(error_msg)
			current = current[key]  # 严格模式下使用直接访问
		return current

	@classmethod
	def _get_nested_safe(cls, data: Mapping[str, Any], path_keys: tuple[str, ...]) -> object | None:
		"""安全模式下的嵌套值获取"""
		current = data
		for key in path_keys:
			if not isinstance(current, Mapping):
				return None
			current = current.get(key)  # 安全模式下使用get
			if current is None:
				break
		return current

	@staticmethod
	def _is_item_container(data: DataDict) -> bool:
		"""简化类型检查逻辑"""
		return isinstance(data, dict) and "items" in data and hasattr(data["items"], "__iter__")

	@overload
	@staticmethod
	def _normalize_input(data: DataDict) -> list[DataDict]: ...

	@overload
	@staticmethod
	def _normalize_input(data: list[DataDict]) -> list[DataDict]: ...

	@overload
	@staticmethod
	def _normalize_input(data: Iterable[DataDict]) -> Iterable[DataDict]: ...

	@staticmethod
	def _normalize_input(data: DataObject) -> Iterable[DataDict]:  # pyright: ignore[reportInconsistentOverload]
		"""优化输入标准化逻辑"""
		if isinstance(data, dict):
			if DataProcessor._is_item_container(data):
				return list(data["items"])  # 确保返回列表
			return [data]

		if isinstance(data, list):
			return data

		if isinstance(data, Iterable):
			return data

		error_msg = f"输入数据必须是字典或可迭代的字典集合, 实际类型: {type(data).__name__}"
		raise TypeError(error_msg)

	@classmethod
	def filter_data(
		cls,
		data: DataObject,
		*,
		include: list[str] | None = None,
		exclude: list[str] | None = None,
	) -> DataObject:
		"""通用字段过滤方法"""
		if include is not None and exclude is not None:
			msg = "不能同时指定包含和排除字段"
			raise ValueError(msg)

		# 预处理过滤字段集合(提高性能)
		include_set = set(include) if include else None
		exclude_set = set(exclude) if exclude else None

		return cls._filter_dispatch(data, include_set, exclude_set)

	@classmethod
	def _filter_dispatch(cls, data: DataObject, include: set[str] | None, exclude: set[str] | None) -> DataObject:
		"""类型分发方法"""
		if isinstance(data, dict):
			return cls._filter_dict(data, include, exclude)
		if isinstance(data, list):
			return cls._filter_list(data, include, exclude)
		if isinstance(data, GeneratorType):
			return cls._filter_generator(data, include, exclude)
		if hasattr(data, "__iter__"):
			return cls._filter_iterable(data, include, exclude)
		error_msg = f"不支持的数据类型: {type(data).__name__}"
		raise TypeError(error_msg)

	@classmethod
	def _filter_dict(cls, data: DataDict, include: set[str] | None, exclude: set[str] | None) -> DataDict:
		"""字典类型过滤"""
		if include is not None:
			return {k: v for k, v in data.items() if k in include}
		if exclude is not None:
			return {k: v for k, v in data.items() if k not in exclude}
		return data

	@classmethod
	def _filter_list(cls, data: list[DataDict], include: set[str] | None, exclude: set[str] | None) -> list[DataDict]:
		"""列表类型过滤"""
		return [cls._filter_dict(item, include, exclude) for item in data]

	@classmethod
	def _filter_generator(cls, data: Iterable[DataDict], include: set[str] | None, exclude: set[str] | None) -> Iterable[DataDict]:
		"""生成器类型过滤(惰性求值)"""
		return (cls._filter_dict(item, include, exclude) for item in data)

	@classmethod
	def _filter_iterable(cls, data: Iterable[DataDict], include: set[str] | None, exclude: set[str] | None) -> Iterable[DataDict]:
		"""通用可迭代类型过滤"""
		return (cls._filter_dict(item, include, exclude) for item in data)

	@classmethod
	def get_nested_value(cls, data: Mapping[str, Any], path: str, *, strict: bool = False) -> object | None:
		"""增强的嵌套值获取方法"""
		path_keys = cls._parse_path(path)
		if strict:
			return cls._get_nested_strict(data, path_keys)
		return cls._get_nested_safe(data, path_keys)

	@staticmethod
	def deduplicate(sequence: Iterable[object]) -> list[object]:
		"""性能优化的保持顺序去重"""
		seen = set()
		# 使用列表预分配(如果可能)
		if hasattr(sequence, "__len__"):
			result = []
			for item in sequence:
				if item not in seen:
					seen.add(item)
					result.append(item)
			return result
		# 对于未知长度的序列使用列表推导
		return [x for x in sequence if not (x in seen or seen.add(x))]


@singleton
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
			...	 name: str
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
		merge_empty_lines: bool = True,  # 是否合并连续空行
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
		# 处理段落和div块
		blocks = re.findall(r"<(?:div|p)\b[^>]*>(.*?)</(?:div|p)>", html_content, flags=re.DOTALL | re.IGNORECASE)
		if not blocks:
			blocks = [html_content]
		processed = []
		for block in blocks:
			# 图片处理
			if replace_images:

				def replace_img(match: re.Match) -> str:
					src = next((g for g in match.groups()[1:] if g), "")
					return img_format.format(src=unescape(src)) if src else img_format.format(src="")

				block = re.sub(  # noqa: PLW2901
					r'<img\b[^>]*?src\s*=\s*("([^"]+)"|\'([^\']+)\'|([^\s>]+))[^>]*>',
					replace_img,
					block,
					flags=re.IGNORECASE,
				)
			# 保留颜色标签内容(特殊处理)
			block = re.sub(r"<span[^>]*>|</span>", "", block)  # noqa: PLW2901
			# 转换HTML实体(保留&nbsp;)
			if unescape_entities:
				block = unescape(block)  # noqa: PLW2901
				block = block.replace("&nbsp;", " ")  # 单独处理空格实体  # noqa: PLW2901
			# 移除其他HTML标签但保留内容
			text = re.sub(r"<[^>]+>", "", block)
			# 保留原始换行结构
			if not keep_line_breaks:
				text = text.replace("\n", " ")
			processed.append(text)
		# 构建结果并处理空行
		result = "\n\n".join(processed)
		if merge_empty_lines:
			result = re.sub(r"\n{3,}", "\n\n", result)
		return result.strip()

	@staticmethod
	def bytes_to_human(size: int) -> str:
		"""将字节数转换为易读格式(如 KB/MB/GB)"""
		size_float = float(size)  # 转为float避免除法问题
		for unit in ["B", "KB", "MB", "GB"]:
			if size_float < FILE_SIZE or unit == "GB":
				return f"{size_float:.2f} {unit}"
			size_float /= FILE_SIZE
		return f"{size_float:.2f} GB"  # 兜底返回


@singleton
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


@singleton
class TimeUtils:
	@staticmethod
	def current_timestamp(length: Literal[10, 13] = 10) -> int:
		"""获取指定精度的时间戳
		Args:
			length: 时间戳长度选项
				10 - 秒级(默认)
				13 - 毫秒级
		Returns:
			int: 对应精度的时间戳整数
		Raises:
			ValueError: 当传入无效长度参数时
		Example:
			>>> # 获取秒级时间戳
			>>> TimeUtils.current_timestamp()
			1717821234
			>>> # 获取毫秒级时间戳
			>>> TimeUtils.current_timestamp(13)
			1717821234123
		"""
		if length not in {10, 13}:
			msg = f"Invalid timestamp length: {length}. Valid options are 10 or 13"
			raise ValueError(msg)
		ts = time.time()
		return int(ts * 1000) if length == 13 else int(ts)  # noqa: PLR2004

	@staticmethod
	def format_timestamp(ts: float | None = None) -> str:
		"""格式化时间戳为字符串
		Example:
			>>> TimeUtils.format_timestamp(1672531200)
			'2023-01-01 00:00:00'
		"""
		return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


@singleton
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


@singleton
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


@singleton
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


@singleton
class EduDataGenerator:
	# 定义常量
	CLASS_NUM_LIMIT = 12
	LETTER_PROBABILITY = 0.3
	SPECIALTY_PROBABILITY = 0.4
	NAME_SUFFIX_PROBABILITY = 0.2

	@staticmethod
	def generate_class_names(
		num_classes: int,
		grade_range: tuple[int, int] = (1, 6),
		*,
		use_letters: bool = False,
		add_specialty: bool = False,
	) -> list[str]:
		"""
		生成随机班级名称
		参数:
			num_classes: 需要生成的班级数量
			grade_range: 年级范围,默认小学1-6年级
			use_letters: 是否使用字母后缀,默认False
			add_specialty: 是否添加特色班级类型,默认False
		返回:
			包含班级名称的列表
		"""

		def number_to_chinese(n: int) -> str:
			chinese_numbers = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二"]
			return chinese_numbers[n - 1] if 1 <= n <= EduDataGenerator.CLASS_NUM_LIMIT else str(n)

		specialties = ["实验", "重点", "国际", "理科", "文科", "艺术", "体育", "国防"]
		class_names: list[str] = []
		for _ in range(num_classes):
			# 生成年级部分
			grade = random.randint(grade_range[0], grade_range[1])
			grade_str = f"{number_to_chinese(grade)}年级"
			# 生成班级序号
			class_num = random.choice(["A", "B", "C", "D"]) if use_letters and random.random() < EduDataGenerator.LETTER_PROBABILITY else str(random.randint(1, 20))
			# 添加特色类型
			specialty = ""
			if add_specialty and random.random() < EduDataGenerator.SPECIALTY_PROBABILITY:
				specialty = random.choice(specialties)
			# 组合班级名称
			class_name = f"{grade_str}{class_num}{specialty}班"
			class_names.append(class_name)
		return class_names

	@staticmethod
	def generate_student_names(
		num_students: int,
		gender: Literal["male", "female"] | None = None,
	) -> list[str]:
		"""
		生成随机学生姓名
		参数:
			num_students: 需要生成的学生数量
			gender: 性别限制,'male'或'female',默认None表示随机
		返回:
			包含学生姓名的列表
		"""
		surnames = [
			"李",
			"王",
			"张",
			"刘",
			"陈",
			"杨",
			"黄",
			"赵",
			"周",
			"吴",
			"徐",
			"孙",
			"马",
			"朱",
			"胡",
			"郭",
			"何",
			"高",
			"林",
			"罗",
			"郑",
			"梁",
			"谢",
			"宋",
			"唐",
			"许",
			"韩",
			"冯",
			"邓",
			"曹",
			"彭",
			"曾",
			"肖",
			"田",
			"董",
			"袁",
			"潘",
			"于",
			"蒋",
			"蔡",
			"余",
			"杜",
			"叶",
			"程",
			"苏",
			"魏",
			"吕",
			"丁",
			"任",
			"沈",
			"姚",
			"卢",
			"姜",
			"崔",
			"钟",
			"谭",
			"陆",
			"汪",
			"范",
			"金",
			"石",
			"廖",
			"贾",
			"夏",
			"韦",
			"付",
			"方",
			"白",
			"邹",
			"孟",
			"熊",
			"秦",
			"邱",
			"江",
			"尹",
			"薛",
			"闫",
			"段",
			"雷",
			"侯",
			"龙",
			"史",
			"陶",
			"黎",
			"贺",
			"顾",
			"毛",
			"郝",
			"龚",
			"邵",
			"万",
			"钱",
			"严",
			"覃",
			"武",
		]
		# 现代常见名字库
		male_names = [
			"浩",
			"宇",
			"轩",
			"杰",
			"博",
			"晨",
			"俊",
			"鑫",
			"昊",
			"睿",
			"涛",
			"鹏",
			"翔",
			"泽",
			"楷",
			"子轩",
			"浩然",
			"俊杰",
			"宇航",
			"皓轩",
			"子豪",
			"宇轩",
			"致远",
			"天佑",
			"明轩",
			"雨泽",
			"思聪",
			"瑞霖",
			"瑾瑜",
			"煜城",
			"逸辰",
			"梓睿",
			"旭尧",
			"晟睿",
			"明哲",
		]
		female_names = [
			"欣",
			"怡",
			"婷",
			"雨",
			"梓",
			"涵",
			"诗",
			"静",
			"雅",
			"娜",
			"雪",
			"雯",
			"璐",
			"颖",
			"琳",
			"雨萱",
			"梓涵",
			"诗琪",
			"欣怡",
			"紫萱",
			"思雨",
			"梦瑶",
			"梓晴",
			"语嫣",
			"可馨",
			"雨彤",
			"若曦",
			"欣妍",
			"雅雯",
			"慧敏",
			"佳琪",
			"美琳",
			"晓菲",
			"思婷",
			"雨欣",
			"静怡",
			"晨曦",
		]
		names: list[str] = []
		for _ in range(num_students):
			surname = random.choice(surnames)
			# 确定性别
			current_gender = gender or random.choice(["male", "female"])
			# 使用三元运算符选择名字
			first_name = (
				random.choice(male_names)
				if current_gender == "male"
				else random.choice(
					female_names,
				)
			)
			# 添加后缀
			if random.random() < EduDataGenerator.NAME_SUFFIX_PROBABILITY:
				suffix = random.choice(["儿", "然", "轩", "瑶", "豪", "菲"])
				if current_gender == "male" and suffix in {"儿", "瑶", "菲"}:
					suffix = random.choice(["然", "轩", "豪"])  # 保持性别特征
				first_name += suffix
			names.append(f"{surname}{first_name}")
		return names

	@staticmethod
	def generate_teacher_certificate_number() -> str:
		year_number = 2009
		# 1. 年度代码(前4位):2000-2025随机年份
		year = random.randint(2000, 2025)
		# 2. 省级行政区代码(5-6位):国家标准行政区代码
		province_codes = [
			"11",
			"12",
			"13",
			"14",
			"15",  # 华北
			"21",
			"22",
			"23",  # 东北
			"31",
			"32",
			"33",
			"34",
			"35",
			"36",
			"37",  # 华东
			"41",
			"42",
			"43",
			"44",
			"45",
			"46",  # 中南
			"50",
			"51",
			"52",
			"53",
			"54",  # 西南
			"61",
			"62",
			"63",
			"64",
			"65",  # 西北
		]
		province = random.choice(province_codes)
		# 3. 认定机构代码(7-9位):随机3位数字
		agency = f"{random.randint(0, 999):03d}"
		# 4. 教师资格类型(第10位):1-7随机
		teacher_type = random.randint(1, 7)
		# 5. 性别代码(第11位):根据年份区分编码规则
		gender = random.choice(["male", "female"])
		gender_code = ("0" if gender == "male" else "1") if year <= year_number else "1" if gender == "male" else "2"
		# 6. 顺序号(12-17位):6位随机序列号
		sequence = f"{random.randint(1, 999999):06d}"
		# 组合所有部分
		return f"{year}{province}{agency}{teacher_type}{gender_code}{sequence}"


@singleton
class Encrypt:
	def __init__(self) -> None:
		self.MAPPING = "jklmnopqrst"  # cSpell:ignore jklmnopqrst
		self.REVERSE_MAPPING = {char: str(i) for i, char in enumerate(self.MAPPING)}
		self.KEY = 0x7F

	def encrypt(self, data: int | str | list[int | str]) -> LiteralString:
		if isinstance(data, int):
			str_data = f"i{data}"
		elif isinstance(data, str):
			str_data = f"s{data}"
		elif isinstance(data, list):
			list_str = ",".join(f"i{item}" if isinstance(item, int) else f"s{item}" for item in data)
			str_data = f"l{list_str}"
		else:
			msg = f"不支持的类型: {type(data)}"
			raise TypeError(msg)
		return self._encrypt_string(str_data)

	def decrypt(self, cipher: str) -> int | LiteralString | list[int | Any]:
		decrypted_str = self._decrypt_string(cipher)
		marker = decrypted_str[0]
		data_str = decrypted_str[1:]
		if marker == "i":
			return int(data_str)
		if marker == "s":
			return data_str
		if marker == "l":
			items = []
			current = ""
			in_escape = False
			for char in data_str:
				if char == "\\" and not in_escape:
					in_escape = True
				elif char == "," and not in_escape:
					items.append(current)
					current = ""
				else:
					current += char
					in_escape = False
			if current:
				items.append(current)
			return [int(item[1:]) if item[0] == "i" else item[1:] for item in items]
		msg = f"未知的类型标记: {marker}"
		raise ValueError(msg)

	def _encrypt_string(self, s: str) -> LiteralString:
		result = []
		for i, char in enumerate(s):
			idx = i % 4
			char_val = ord(char)
			if idx == 0:
				val = char_val ^ self.KEY
			elif idx == 1:
				val = (char_val + self.KEY) % 256
			elif idx == 2:  # noqa: PLR2004
				val = (char_val - self.KEY) % 256
			else:
				val = ~char_val & 0xFF
			val_str = f"{val:03d}"
			result.extend(self.MAPPING[int(d) % 10] for d in val_str)
		return "".join(result)

	def _decrypt_string(self, cipher: str) -> LiteralString:
		digits = "".join(self.REVERSE_MAPPING[char] for char in cipher)
		parts = []
		i = 0
		while i + 3 <= len(digits):
			num_str = digits[i : i + 3]
			if num_str.isdigit():
				val = int(num_str)
				if 0 <= val <= 255:  # noqa: PLR2004
					parts.append(val)
					i += 3
				else:
					i += 1
			else:
				i += 1
		result = []
		for i, val in enumerate(parts):
			idx = i % 4
			if idx == 0:
				result.append(chr(val ^ self.KEY))
			elif idx == 1:
				result.append(chr((val - self.KEY) % 256))
			elif idx == 2:  # noqa: PLR2004
				result.append(chr((val + self.KEY) % 256))
			else:
				result.append(chr(~val & 0xFF))
		return "".join(result)


@singleton
@final
class Printer:
	"""
	优化后的打印器类,提供颜色输出和输入验证功能
	使用单例模式确保全局一致的输出格式
	"""

	def __init__(self) -> None:
		# 预计算常用字符串,减少运行时计算
		self._input_prefix = "↳ "
		self._input_suffix = ": "
		self._header_width = 60

	@staticmethod
	def color_text(text: str, color_name: ColorType) -> str:
		"""为文本添加颜色 - 静态方法优化"""
		return f"{ColorConfig.get_color(color_name)}{text}{ColorConfig.get_color('RESET')}"

	def prompt_input(self, text: str, color: ColorType = "PROMPT") -> str:
		"""统一的输入提示函数 - 优化字符串拼接"""
		prompt_text = f"{self._input_prefix}{text}{self._input_suffix}"
		colored_prompt = self.color_text(prompt_text, color)
		# 确保输出被立即刷新
		return input(colored_prompt)

	def print_message(self, text: str, color_name: ColorType) -> None:
		"""打印消息 - 优化性能"""
		print(self.color_text(text, color_name))

	def print_header(self, text: str) -> None:
		"""打印装饰头部 - 优化字符串格式化"""
		separator = ColorConfig.get_separator()
		formatted_text = text.center(self._header_width)
		print(f"\n{separator}")
		print(self.color_text(formatted_text, "MENU_TITLE"))
		print(f"{separator}\n")

	@staticmethod
	def _normalize_string_input(value_str: str, valid_options: set[str]) -> str:
		"""标准化字符串输入,智能处理大小写"""
		if not valid_options:
			return value_str
		# 分析选项的大小写模式
		all_lower = all(opt.islower() for opt in valid_options)
		all_upper = all(opt.isupper() for opt in valid_options)
		if all_lower:
			return value_str.lower()
		if all_upper:
			return value_str.upper()
		return value_str

	@staticmethod
	def _validate_range(value: float, valid_range: range) -> bool:
		"""验证范围输入"""
		return value in valid_range

	@staticmethod
	def _validate_options(value: T, valid_options: set[T]) -> bool:
		"""验证选项输入"""
		return value in valid_options

	def get_valid_input(
		self,
		prompt: str,
		valid_options: set[T] | range | None = None,
		cast_type: Callable[[str], T] = str,
		validator: Callable[[T], bool] | None = None,
		max_attempts: int = 10,
	) -> T:
		"""
		获取有效输入并进行类型转换验证
		支持范围验证、自定义验证和大小写智能处理
		增加最大尝试次数限制,避免无限循环
		"""
		attempts = 0
		while attempts < max_attempts:
			try:
				value_str = self.prompt_input(prompt).strip()
				if not value_str:
					self.print_message("输入不能为空,请重新输入", "WARNING")
					attempts += 1
					continue
				# 字符串类型的智能处理
				if cast_type is str and valid_options and not isinstance(valid_options, range) and all(isinstance(opt, str) for opt in valid_options):
					value_str = self._normalize_string_input(value_str, valid_options)  # type: ignore  # noqa: PGH003
				# 类型转换
				value = cast_type(value_str)
				# 验证逻辑
				validation_passed = True
				validation_error = ""
				if valid_options is not None:
					if isinstance(valid_options, range):
						if not self._validate_range(value, valid_options):  # type: ignore  # noqa: PGH003
							validation_passed = False
							validation_error = f"输入超出范围。有效范围: [{valid_options.start}-{valid_options.stop - 1}]"
					elif not self._validate_options(value, valid_options):
						validation_passed = False
						validation_error = f"无效输入。有效选项: {valid_options}"
				# 自定义验证
				if validation_passed and validator and not validator(value):
					validation_passed = False
					validation_error = "输入不符合要求"
				if not validation_passed:
					self.print_message(validation_error, "ERROR")
					attempts += 1
					continue
			except ValueError as e:
				type_name = cast_type.__name__
				self.print_message(f"格式错误: 请输入{type_name}类型的值 ({e})", "ERROR")
				attempts += 1
			except KeyboardInterrupt:
				self.print_message("\n操作已取消", "INFO")
				raise
			except Exception as e:
				self.print_message(f"发生意外错误: {e!s}", "ERROR")
				attempts += 1
			else:
				# 如果所有验证都通过,返回结果
				return value
		# 达到最大尝试次数
		error_msg = "输入尝试次数过多,程序退出"
		self.print_message(error_msg, "ERROR")
		raise ValueError(error_msg)


T = TypeVar("T")


@dataclass
class DisplayConfig:
	"""显示配置"""

	page_size: int = 10
	display_fields: list[str] | None = None
	title: str = "数据列表"
	id_field: str = "id"
	navigation_config: dict[str, str] | None = None
	field_formatters: dict[str, Callable[[Any], str]] | None = None


@dataclass
class OperationConfig:
	"""操作配置"""

	custom_operations: dict[str, Callable[[Any], None]] | None = None
	batch_processor: Callable[[list[Any]], dict[int, str]] | None = None


class DisplayRenderer:
	"""负责数据渲染显示"""

	def __init__(self, printer: Any) -> None:  # noqa: ANN401
		self.printer = printer

	def render_page(
		self, data: list[Any], field_info: dict[str, Any], page_info: dict[str, Any], batch_results: dict[int, str] | None = None, operations: dict[str, str] | None = None
	) -> None:
		"""渲染单页数据"""
		self._render_header(page_info)
		self._render_table_header(field_info, batch_results)
		self._render_data_rows(data, field_info, batch_results, operations, page_info)
		self._render_footer(field_info, batch_results)

	def _render_header(self, page_info: dict[str, Any]) -> None:
		"""渲染页眉"""
		self.printer.print_header(f"=== {page_info['title']} ===")
		self.printer.print_message(f"第 {page_info['current_page']}/{page_info['total_pages']} 页 (共 {page_info['total_items']} 条记录)", "INFO")

	def _render_table_header(self, field_info: dict[str, Any], batch_results: dict[int, str] | None) -> None:
		"""渲染表头"""
		header_parts = ["操作".ljust(10), "序号".ljust(6)]
		header_parts.extend(f"{field}".ljust(20) for field in field_info["fields"])
		if batch_results:
			header_parts.append("状态".ljust(15))
		header = "".join(header_parts)
		separator = "-" * len(header)
		self.printer.print_message(separator, "INFO")
		self.printer.print_message(header, "INFO")
		self.printer.print_message(separator, "INFO")

	def _render_data_rows(
		self, data: list[Any], field_info: dict[str, Any], batch_results: dict[int, str] | None, operations: dict[str, str] | None, page_info: dict[str, Any]
	) -> None:
		"""渲染数据行"""
		start_idx = (page_info["current_page"] - 1) * page_info["page_size"]
		for i, item in enumerate(data):
			local_index = i + 1
			global_index = start_idx + i
			# 操作列
			operation_display = self._format_operations(operations, local_index)
			row = operation_display.ljust(10)
			# 序号列
			row += f"{local_index}".ljust(6)
			# 数据字段
			formatted_values = self._batch_format_values(item, field_info)
			for field in field_info["fields"]:
				display_value = self._format_display_value(formatted_values[field], 18)
				row += f"{display_value}".ljust(20)
			# 批量处理状态
			if batch_results and global_index in batch_results:
				row += f"{batch_results[global_index]}".ljust(15)
			self.printer.print_message(row, "INFO")

	def _render_footer(self, field_info: dict[str, Any], batch_results: dict[int, str] | None) -> None:
		"""渲染页脚"""
		footer_parts = [""] * (2 + len(field_info["fields"]) + (1 if batch_results else 0))
		footer = "".join(part.ljust(20) for part in footer_parts)
		separator = "-" * len(footer) if footer else "-" * 100
		self.printer.print_message(separator, "INFO")

	@staticmethod
	def _format_operations(operations: dict[str, str] | None, local_index: int) -> str:
		"""格式化操作显示"""
		if not operations:
			return ""
		operation_display = ""
		for shortcut in operations:
			operation_display += f"{shortcut}{local_index} "
		return operation_display.strip()

	def _batch_format_values(self, item: Any, field_info: dict[str, Any]) -> dict[str, str]:  # noqa: ANN401
		"""批量格式化字段值"""
		formatted = {}
		for field in field_info["fields"]:
			value = self._safe_get_attribute(item, field)
			if field in field_info["formatters"]:
				formatted[field] = field_info["formatters"][field](value)
			else:
				formatted[field] = str(value)
		return formatted

	def _safe_get_attribute(self, item: Any, field: str) -> Any:  # noqa: ANN401
		"""安全获取属性"""
		try:
			return getattr(item, field, "N/A")
		except Exception as e:
			self.printer.print_message(f"获取字段 {field} 时出错: {e}", "DEBUG")
			return "ERROR"

	@staticmethod
	def _format_display_value(value: str, max_length: int = 18) -> str:
		"""格式化显示值,处理长文本"""
		if len(value) > max_length:
			return value[: max_length - 3] + "..."
		return value


class InputProcessor:
	"""负责处理用户输入"""

	def __init__(self, printer: Any) -> None:  # noqa: ANN401
		self.printer = printer

	def get_user_choice(
		self,
		current_page: int,
		total_pages: int,
		custom_operations: dict[str, Callable[[Any], None]] | None,
		nav_config: dict[str, str],
		current_page_item_count: int,
		operation_shortcuts: dict[str, str],
	) -> str:
		"""获取用户选择"""
		valid_choices = self._build_valid_choices(current_page, total_pages, nav_config, current_page_item_count, operation_shortcuts)
		options = self._build_options_display(current_page, total_pages, nav_config, custom_operations, operation_shortcuts)
		self.printer.print_message(" | ".join(options), "INFO")
		try:
			return self.printer.get_valid_input(prompt="请选择", valid_options=valid_choices, cast_type=str)
		except (EOFError, KeyboardInterrupt):
			self.printer.print_message("\n操作已取消", "INFO")
			return nav_config["quit"]

	@staticmethod
	def _build_valid_choices(
		current_page: int,
		total_pages: int,
		nav_config: dict[str, str],
		current_page_item_count: int,
		operation_shortcuts: dict[str, str],
	) -> set[str]:
		"""构建有效选择集合"""
		valid_choices = set()
		# 导航选项
		if current_page < total_pages:
			valid_choices.add(nav_config["next_page"])
		if current_page > 1:
			valid_choices.add(nav_config["previous_page"])
		valid_choices.add(nav_config["quit"])
		# 操作选项
		if operation_shortcuts and current_page_item_count > 0:
			for shortcut in operation_shortcuts:
				valid_choices.update(f"{shortcut}{i}" for i in range(1, current_page_item_count + 1))
		return valid_choices

	@staticmethod
	def _build_options_display(
		current_page: int,
		total_pages: int,
		nav_config: dict[str, str],
		custom_operations: dict[str, Callable[[Any], None]] | None,
		operation_shortcuts: dict[str, str],
	) -> list[str]:
		"""构建选项显示列表"""
		options = []
		# 导航选项
		if current_page < total_pages:
			options.append(f"{nav_config['next_page']}:下一页")
		if current_page > 1:
			options.append(f"{nav_config['previous_page']}:上一页")
		options.append(f"{nav_config['quit']}:退出")
		# 操作选项
		if custom_operations and operation_shortcuts:
			op_descriptions = [f"{shortcut}数字:{op_name}" for shortcut, op_name in operation_shortcuts.items()]
			options.extend(op_descriptions)
		return options


class GenericDataViewer:
	"""通用的数据查看器"""

	def __init__(self, printer: Any) -> None:  # noqa: ANN401
		self.printer = printer
		self.renderer = DisplayRenderer(printer)
		self.input_processor = InputProcessor(printer)
		self.default_navigation = {"next_page": "n", "previous_page": "p", "quit": "q", "back": "b"}

	def display_data(
		self,
		data_class: type[T],
		data_list: list[T],
		page_size: int = 10,
		display_fields: list[str] | None = None,
		custom_operations: dict[str, Callable[[T], None]] | None = None,
		title: str = "数据列表",
		id_field: str = "id",
		navigation_config: dict[str, str] | None = None,
		field_formatters: dict[str, Callable[[Any], str]] | None = None,
		batch_processor: Callable[[list[T]], dict[int, str]] | None = None,
	) -> None:
		"""
		通用数据显示功能
		Args:
			data_class: dataclass类
			data_list: 数据列表
			page_size: 每页显示数量
			display_fields: 要显示的字段列表,如果为None则显示所有字段
			custom_operations: 自定义操作字典 {操作名称: 操作函数}
			title: 显示标题
			id_field: 用于标识数据项的字段名
			navigation_config: 导航键配置,可覆盖默认配置
			field_formatters: 字段格式化函数字典 {字段名: 格式化函数}
			batch_processor: 批量处理函数,返回 {索引: 状态信息}
		"""
		# 合并导航配置
		nav_config = {**self.default_navigation, **(navigation_config or {})}
		# 参数验证
		self._validate_parameters(data_class, data_list, page_size, display_fields, id_field, nav_config)
		if not data_list:
			self.printer.print_message("没有数据可显示", "WARNING")
			return
		# 预计算和初始化
		field_info = self._precompute_field_info(data_class, display_fields, field_formatters)
		operation_shortcuts = self._assign_operation_shortcuts(custom_operations, list(nav_config.values()))
		batch_results = batch_processor(data_list) if batch_processor else {}
		# 主显示循环
		self._display_loop(data_list, field_info, operation_shortcuts, batch_results, page_size, title, nav_config, custom_operations)

	def _display_loop(
		self,
		data_list: list[T],
		field_info: dict[str, Any],
		operation_shortcuts: dict[str, str],
		batch_results: dict[int, str],
		page_size: int,
		title: str,
		nav_config: dict[str, str],
		custom_operations: dict[str, Callable[[T], None]] | None,
	) -> None:
		"""主显示循环"""
		current_page = 1
		total_pages = (len(data_list) + page_size - 1) // page_size
		while True:
			# 获取当前页数据
			current_page_items = self._get_current_page_items(data_list, current_page, page_size)
			page_info = self._build_page_info(title, current_page, total_pages, len(data_list), page_size)
			# 显示当前页
			self.renderer.render_page(current_page_items, field_info, page_info, batch_results, operation_shortcuts)
			# 获取用户输入
			choice = self.input_processor.get_user_choice(current_page, total_pages, custom_operations, nav_config, len(current_page_items), operation_shortcuts)
			# 处理用户选择
			result = self._process_user_choice(choice, current_page, total_pages, nav_config, operation_shortcuts, current_page_items, custom_operations)
			if result == "quit":
				break
			if isinstance(result, int):
				current_page = result

	@staticmethod
	def _get_current_page_items(data_list: list[T], current_page: int, page_size: int) -> list[T]:
		"""获取当前页数据"""
		start_idx = (current_page - 1) * page_size
		end_idx = min(start_idx + page_size, len(data_list))
		return data_list[start_idx:end_idx]

	@staticmethod
	def _build_page_info(title: str, current_page: int, total_pages: int, total_items: int, page_size: int) -> dict[str, Any]:
		"""构建页面信息"""
		return {"title": title, "current_page": current_page, "total_pages": total_pages, "total_items": total_items, "page_size": page_size}

	def _process_user_choice(
		self,
		choice: str,
		current_page: int,
		total_pages: int,
		nav_config: dict[str, str],
		operation_shortcuts: dict[str, str],
		current_page_items: list[T],
		custom_operations: dict[str, Callable[[T], None]] | None,
	) -> int | str:
		"""处理用户选择"""
		# 导航操作
		if choice == nav_config["next_page"] and current_page < total_pages:
			return current_page + 1
		if choice == nav_config["previous_page"] and current_page > 1:
			return current_page - 1
		if choice == nav_config["quit"]:
			return "quit"
		# 自定义操作
		if self._is_operation_choice(choice, operation_shortcuts, len(current_page_items)):
			self._execute_operation(choice, operation_shortcuts, current_page_items, custom_operations)
			return current_page  # 操作后停留在当前页
		self.printer.print_message("无效的输入", "ERROR")
		return current_page

	def _execute_operation(
		self,
		choice: str,
		operation_shortcuts: dict[str, str],
		current_page_items: list[T],
		custom_operations: dict[str, Callable[[T], None]] | None,
	) -> None:
		"""执行操作"""
		shortcut = choice[0]
		item_num = int(choice[1:]) - 1  # 转换为0-based索引
		if 0 <= item_num < len(current_page_items):
			selected_item = current_page_items[item_num]
			op_name = operation_shortcuts[shortcut]
			if custom_operations and op_name in custom_operations:
				try:
					custom_operations[op_name](selected_item)
					self.printer.print_message(f"操作 '{op_name}' 执行成功", "SUCCESS")
				except Exception as e:
					self.printer.print_message(f"操作 '{op_name}' 执行失败: {e}", "ERROR")
			else:
				self.printer.print_message("没有可用的操作", "ERROR")
		else:
			self.printer.print_message("无效的选择", "ERROR")

	@staticmethod
	def _is_operation_choice(choice: str, operation_shortcuts: dict[str, str], current_item_count: int) -> bool:
		"""检查是否为操作选择"""
		MIN_CHOICE_LENGTH = 2  # noqa: N806
		if len(choice) < MIN_CHOICE_LENGTH:
			return False
		shortcut = choice[0]
		number_part = choice[1:]
		if shortcut not in operation_shortcuts:
			return False
		if not number_part.isdigit():
			return False
		item_num = int(number_part)
		return 1 <= item_num <= current_item_count

	def _validate_parameters(
		self,
		data_class: type[T],
		data_list: list[T],
		page_size: int,
		display_fields: list[str] | None,
		id_field: str,
		nav_config: dict[str, str],
	) -> None:
		"""验证输入参数"""
		validation_checks = [
			(not is_dataclass(data_class), "data_class 必须是一个 dataclass"),
			(not isinstance(data_list, list), "data_list 必须是一个列表"),
			(page_size <= 0, "page_size 必须大于 0"),
			(display_fields is not None and not isinstance(display_fields, list), "display_fields 必须是一个列表或 None"),
		]
		for condition, error_msg in validation_checks:
			if condition:
				raise ValueError(error_msg)
		self._validate_navigation_config(nav_config)
		self._validate_id_field(data_class, id_field)

	@staticmethod
	def _validate_navigation_config(nav_config: dict[str, str]) -> None:
		"""验证导航配置"""
		required_keys = ["next_page", "previous_page", "quit", "back"]
		missing_keys = [key for key in required_keys if key not in nav_config]
		if missing_keys:
			error_msg = f"导航配置缺少必需的键: {', '.join(missing_keys)}"
			raise ValueError(error_msg)
		# 检查字符唯一性
		nav_chars = [nav_config[key] for key in required_keys]
		if len(nav_chars) != len(set(nav_chars)):
			error_msg = "导航键配置中存在重复的字符"
			raise ValueError(error_msg)

	def _validate_id_field(self, data_class: type[T], id_field: str) -> None:
		"""验证ID字段"""
		try:
			# 使用 is_dataclass 检查并安全获取字段
			if is_dataclass(data_class):
				field_names = [field.name for field in fields(data_class)]
				if id_field not in field_names:
					self.printer.print_message(f"警告: dataclass 中没有找到字段 '{id_field}'", "WARNING")
			else:
				self.printer.print_message("警告: 提供的类不是 dataclass", "WARNING")
		except (TypeError, AttributeError):
			# 如果 fields() 调用失败,说明不是有效的 dataclass
			self.printer.print_message(f"警告: 无法验证字段 '{id_field}',请确保是有效的 dataclass", "WARNING")

	def _precompute_field_info(
		self,
		data_class: type[T],
		display_fields: list[str] | None,
		field_formatters: dict[str, Callable[[Any], str]] | None,
	) -> dict[str, Any]:
		"""预计算字段信息"""
		available_fields = self._get_available_fields(data_class, display_fields)
		return {
			"fields": available_fields,
			"formatters": field_formatters or {},
		}

	def _get_available_fields(self, data_class: type[T], display_fields: list[str] | None) -> list[str]:
		"""获取可用的字段列表"""
		if not is_dataclass(data_class):
			msg = f"Expected a dataclass, got {type(data_class)}"
			raise TypeError(msg)
		all_fields = [field.name for field in fields(data_class)]
		if display_fields is None:
			return all_fields
		# 过滤掉不存在的字段
		available_fields = [field for field in display_fields if field in all_fields]
		missing_fields = set(display_fields) - set(all_fields)
		if missing_fields:
			self.printer.print_message(f"警告: 以下字段不存在: {', '.join(missing_fields)}", "WARNING")
		return available_fields or all_fields

	@staticmethod
	def _assign_operation_shortcuts(
		custom_operations: dict[str, Callable[[T], None]] | None,
		existing_shortcuts: list[str],
	) -> dict[str, str]:
		"""为操作分配快捷键"""
		if not custom_operations:
			return {}
		shortcuts = {}
		operations = list(custom_operations.keys())
		# 使用可用的字母作为操作快捷键(避免与导航键冲突)
		available_letters = [chr(i) for i in range(ord("a"), ord("z") + 1)]
		available_letters = [letter for letter in available_letters if letter not in existing_shortcuts]
		for i, op_name in enumerate(operations):
			if i < len(available_letters):
				shortcut = available_letters[i]
				shortcuts[shortcut] = op_name
			else:
				# 如果字母不够用,使用数字作为后备
				shortcut = str(i - len(available_letters))
				shortcuts[shortcut] = op_name
		return shortcuts
