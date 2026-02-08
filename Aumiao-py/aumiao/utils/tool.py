from __future__ import annotations

from abc import ABC, abstractmethod
from base64 import b64decode
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass, fields, is_dataclass
from functools import lru_cache
from hashlib import sha256
from html import unescape
from json import loads
from random import choice, randint, random
from re import DOTALL, IGNORECASE, Match, findall, sub
from time import localtime, strftime, time
from types import GeneratorType
from typing import Any, ClassVar, Final, Literal, TypeVar, cast

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from aumiao.utils.decorator import singleton

# ========== 类型定义 ==========
T = TypeVar("T")
DataDict = dict[str, Any]
DataObject = DataDict | list[DataDict] | Iterable[DataDict]
# ========== 常量定义 ==========
FILE_SIZE: Final[int] = 1024
CLASS_NUM_LIMIT: Final[int] = 12
LETTER_PROBABILITY: Final[float] = 0.3
SPECIALTY_PROBABILITY: Final[float] = 0.4
NAME_SUFFIX_PROBABILITY: Final[float] = 0.2
MIN_DATA_LENGTH: Final[int] = 13
MIN_CHOICE_LENGTH: Final[int] = 2
AES_IV_LENGTH: Final[int] = 12


# ========== 颜色配置管理器 ==========
@singleton
class ColorManager:
	"""颜色管理单例类"""

	_instance: ClassVar[ColorManager | None] = None
	_COLOR_MAP: ClassVar[dict[str, str]] = {
		"COMMENT": "\033[38;5;245m",
		"ERROR": "\033[38;5;203m",
		"MENU_ITEM": "\033[38;5;183m",
		"MENU_TITLE": "\033[38;5;80m",
		"PROMPT": "\033[38;5;75m",
		"RESET": "\033[0m",
		"STATUS": "\033[38;5;228m",
		"SUCCESS": "\033[38;5;114m",
		"INFO": "\033[38;5;39m",
		"WARNING": "\033[38;5;214m",
	}

	@classmethod
	@lru_cache(maxsize=64)
	def get(cls, color_name: str) -> str:
		"""获取颜色代码, 使用缓存提高性能"""
		return cls._COLOR_MAP.get(color_name, cls._COLOR_MAP["RESET"])

	@property
	def separator(self) -> str:
		"""获取分隔符"""
		return f"{self.get('PROMPT')}══════════════════════════════════════════════════════════{self.get('RESET')}"


# ========== 数据处理器接口 ==========
class DataProcessorStrategy(ABC):
	"""数据处理策略接口"""

	@abstractmethod
	def process(self, data: Any) -> Any:
		"""处理数据"""


# ========== 具体数据处理策略 ==========
@singleton
class PathCache:
	"""路径缓存管理器"""

	def __init__(self) -> None:
		self._cache: dict[str, tuple[str, ...]] = {}

	def get(self, path: str) -> tuple[str, ...]:
		"""获取解析后的路径"""
		if path not in self._cache:
			self._cache[path] = tuple(path.split("."))
		return self._cache[path]

	def clear(self) -> None:
		"""清空缓存"""
		self._cache.clear()


@singleton
class NestedFilterStrategy(DataProcessorStrategy):
	"""嵌套字段过滤策略"""

	def __init__(self, path_cache: PathCache | None = None) -> None:
		self._path_cache = path_cache or PathCache()

	def process(self, data: tuple[DataObject, str, Iterable[object], bool]) -> list[DataDict]:
		"""过滤数据"""
		data_object, id_path, target_values, strict_mode = data
		if not id_path or not isinstance(id_path, str):
			msg = "id_path 必须是非空字符串"
			raise ValueError(msg)
		if not hasattr(target_values, "__iter__"):
			msg = "target_values 必须是可迭代对象"
			raise TypeError(msg)
		target_set = set(target_values)
		path_keys = self._path_cache.get(id_path)
		items = self._normalize_input(data_object)
		if strict_mode:
			return [item for item in items if self._get_nested_strict(item, path_keys) in target_set]
		return [item for item in items if self._get_nested_safe(item, path_keys) in target_set]

	@staticmethod
	def _normalize_input(data: DataObject) -> ...:
		"""优化输入标准化逻辑"""
		key: str = "items"
		if isinstance(data, dict):
			data = cast("dict", data)
			if key in data and hasattr(data[key], "__iter__"):
				return list(data[key])
			return [data]
		if isinstance(data, (list, GeneratorType)) or hasattr(data, "__iter__"):
			return data
		msg = f"输入数据必须是字典或可迭代的字典集合, 实际类型: {type(data).__name__}"
		raise TypeError(msg)

	@staticmethod
	def _get_nested_strict(data: Mapping[str, Any], path_keys: tuple[str, ...]) -> object:
		"""严格模式下的嵌套值获取"""
		current = data
		for key in path_keys:
			if not isinstance(current, Mapping):
				msg = f"路径 {key} 处遇到非字典类型: {type(current)}"
				raise TypeError(msg)
			current = current[key]
		return current

	@staticmethod
	def _get_nested_safe(data: Mapping[str, Any], path_keys: tuple[str, ...]) -> object | None:
		"""安全模式下的嵌套值获取"""
		current = data
		for key in path_keys:
			if not isinstance(current, Mapping):
				return None
			current = current.get(key)
			if current is None:
				break
		return current


@singleton
class FieldFilterStrategy(DataProcessorStrategy):
	"""字段过滤策略"""

	def process(self, data: tuple[DataObject, set[str] | None, set[str] | None]) -> DataObject:
		"""过滤字段"""
		data_object, include_set, exclude_set = data
		if isinstance(data_object, dict):
			data_object = cast("dict", data_object)
			return self._filter_dict(data_object, include_set, exclude_set)
		if isinstance(data_object, list):
			data_object = cast("list", data_object)
			return self._filter_list(data_object, include_set, exclude_set)
		if hasattr(data_object, "__iter__"):
			return self._filter_iterable(data_object, include_set, exclude_set)
		msg = f"不支持的数据类型: {type(data_object).__name__}"
		raise TypeError(msg)

	@staticmethod
	def _filter_dict(data: DataDict, include: set[str] | None, exclude: set[str] | None) -> DataDict:
		"""字典类型过滤"""
		if include is not None:
			return {k: v for k, v in data.items() if k in include}
		if exclude is not None:
			return {k: v for k, v in data.items() if k not in exclude}
		return data

	@staticmethod
	def _filter_list(data: list[DataDict], include: set[str] | None, exclude: set[str] | None) -> list[DataDict]:
		"""列表类型过滤"""
		return [FieldFilterStrategy._filter_dict(item, include, exclude) for item in data]

	@staticmethod
	def _filter_iterable(data: Iterable[DataDict], include: set[str] | None, exclude: set[str] | None) -> Iterable[DataDict]:
		"""通用可迭代类型过滤"""
		return (FieldFilterStrategy._filter_dict(item, include, exclude) for item in data)


# ========== 数据处理器工厂 ==========
@singleton
class DataProcessor:
	"""数据处理器工厂"""

	@staticmethod
	def create_filter_processor() -> NestedFilterStrategy:
		"""创建过滤器处理器"""
		return NestedFilterStrategy()

	@staticmethod
	def create_field_filter_processor() -> FieldFilterStrategy:
		"""创建字段过滤器处理器"""
		return FieldFilterStrategy()

	@staticmethod
	def filter_by_nested_values(
		data: DataObject,
		id_path: str,
		target_values: Iterable[object],
		*,
		strict_mode: bool = False,
	) -> list[DataDict]:
		"""过滤数据"""
		processor = DataProcessor.create_filter_processor()
		return processor.process((data, id_path, target_values, strict_mode))

	@staticmethod
	def filter_fields(
		data: DataObject,
		*,
		include: list[str] | None = None,
		exclude: list[str] | None = None,
	) -> DataObject:
		"""过滤字段"""
		if include is not None and exclude is not None:
			msg = "不能同时指定包含和排除字段"
			raise ValueError(msg)
		include_set = set(include) if include else None
		exclude_set = set(exclude) if exclude else None
		processor = DataProcessor.create_field_filter_processor()
		return processor.process((data, include_set, exclude_set))

	@staticmethod
	def get_nested_value(data: Mapping[str, Any], path: str, *, strict: bool = False) -> object | None:
		"""获取嵌套值"""
		path_cache = PathCache()
		path_keys = path_cache.get(path)
		if strict:
			return NestedFilterStrategy._get_nested_strict(data, path_keys)  # noqa: SLF001
		return NestedFilterStrategy._get_nested_safe(data, path_keys)  # noqa: SLF001

	@staticmethod
	def deduplicate(sequence: Iterable[str | int]) -> list[str]:
		"""保持顺序去重"""
		seen = set()
		result = []
		for item in sequence:
			if item not in seen:
				seen.add(item)
				result.append(item)
		return result


# ========== 数据转换器 ==========
@singleton
class DataConverter:
	"""数据转换工具类"""

	@staticmethod
	def convert_cookie(cookie: dict[str, str]) -> str:
		"""将字典格式 cookie 转换为字符串"""
		return ";".join(f"{k}={v}" for k, v in cookie.items())

	@staticmethod
	def to_serializable(data: object) -> dict[str, object]:
		"""转换为可序列化字典"""
		if isinstance(data, dict):
			return cast("dict", data.copy())

		def is_dataclass_instance(obj: object) -> bool:
			"""检查对象是否是数据类实例"""
			return isinstance(obj, object) and not isinstance(obj, type) and is_dataclass(obj)

		if is_dataclass_instance(data):
			return asdict(data)  # pyright: ignore [reportArgumentType] # ty:ignore [invalid-argument-type]
		if hasattr(data, "__dict__"):
			return vars(data)
		msg = f"不支持的类型: {type(data).__name__}。支持类型: dict, 数据类实例, 或包含__dict__属性的对象"
		raise TypeError(msg)

	@staticmethod
	def bbcode_to_html(bbcode: str) -> str:
		"""将 BBCode 转换为 HTML"""
		if not bbcode or not bbcode.strip():
			return ""
		result = bbcode.strip()
		# 基础标签替换
		replacements = {
			r"\[b\](.*?)\[/b\]": r"<strong>\1</strong>",
			r"\[i\](.*?)\[/i\]": r"<em>\1</em>",
			r"\[u\](.*?)\[/u\]": r"<u>\1</u>",
			r"\[s\](.*?)\[/s\]": r"<strike>\1</strike>",
			r"\[br\]": "<br>",
			r"\[hr\]": "<hr>",
			r"\[code\](.*?)\[/code\]": r"<code>\1</code>",
			r"\[left\](.*?)\[/left\]": r'<div style="text-align:left;">\1</div>',
			r"\[center\](.*?)\[/center\]": r'<div style="text-align:center;">\1</div>',
			r"\[right\](.*?)\[/right\]": r'<div style="text-align:right;">\1</div>',
		}
		for pattern, replacement in replacements.items():
			result = sub(pattern, replacement, result, flags=DOTALL)
		# 带参数的标签
		# 字体大小
		result = sub(
			r"\[font_size=(\d+)\](.*?)\[/font_size\]",
			r'<span style="font-size:\1px;">\2</span>',
			result,
			flags=DOTALL,
		)
		# 颜色

		def _expand_color(match: Match) -> str:
			color = match.group(1)
			content = match.group(2)
			if len(color) == 3:
				color = color[0] * 2 + color[1] * 2 + color[2] * 2
			return f'<span style="color:#{color};">{content}</span>'

		result = sub(
			r"\[color=#?([0-9a-fA-F]{3,6})\](.*?)\[/color\]",
			_expand_color,
			result,
			flags=DOTALL,
		)
		# 链接
		result = sub(
			r"\[url=(.+?)\](.+?)\[/url\]",
			r'<a href="\1" target="_blank">\2</a>',
			result,
			flags=DOTALL,
		)
		# 图片
		result = sub(
			r"\[image=(.+?)\]",
			r'<img src="\1" alt="image" style="max-width:100%;height:auto;">',
			result,
		)
		# 还原 HTML 标签
		tag_replacements = {
			"&lt;strong&gt;": "<strong>",
			"&lt;/strong&gt;": "</strong>",
			"&lt;em&gt;": "<em>",
			"&lt;/em&gt;": "</em>",
			"&lt;u&gt;": "<u>",
			"&lt;/u&gt;": "</u>",
			"&lt;strike&gt;": "<strike>",
			"&lt;/strike&gt;": "</strike>",
			"&lt;br&gt;": "<br>",
			"&lt;hr&gt;": "<hr>",
			"&lt;code&gt;": "<code>",
			"&lt;/code&gt;": "</code>",
			"&lt;div style=&quot;text-align:left;&quot;&gt;": '<div style="text-align:left;">',
			"&lt;/div&gt;": "</div>",
			"&lt;div style=&quot;text-align:center;&quot;&gt;": '<div style="text-align:center;">',
			"&lt;div style=&quot;text-align:right;&quot;&gt;": '<div style="text-align:right;">',
			"&lt;span style=&quot;font-size:": '<span style="font-size:',
			"&lt;/span&gt;": "</span>",
			"&lt;span style=&quot;color:#": '<span style="color:#',
			"&lt;a href=&quot;": '<a href="',
			"&lt;/a&gt;": "</a>",
			"&lt;img src=&quot;": '<img src="',
			"&quot; alt=&quot;image&quot; style=&quot;max-width:100%;height:auto;&quot;&gt;": '"alt="image"style="max-width:100%;height:auto;">',
		}
		for old, new in tag_replacements.items():
			result = result.replace(old, new)
		# 添加段落
		lines = result.split("\n")
		lines = [line.strip() for line in lines if line.strip()]
		if lines:
			has_block_elements = any(any(tag in line for tag in ["<div", "<img", "<a href", "<code>", "<pre>"]) for line in lines)
			result = "\n".join(lines) if has_block_elements else "\n".join(f"<p>{line}</p>" for line in lines)
		return result

	@staticmethod
	def html_to_text(
		html_content: str,
		*,
		replace_images: bool = True,
		img_format: str = "[图片链接: {src}]",
		merge_empty_lines: bool = True,
		unescape_entities: bool = True,
		keep_line_breaks: bool = True,
	) -> str:
		"""将 HTML 转换为可配置的纯文本"""

		def replace_img(match: Match) -> str:
			src = next((g for g in match.groups()[1:] if g), "")
			return img_format.format(src=unescape(src)) if src else img_format.format(src="")

		# 处理段落和 div 块
		blocks = findall(r"<(?:div|p)\b [^>]*>(.*?)</(?:div|p)>", html_content, flags=DOTALL | IGNORECASE)
		if not blocks:
			blocks = [html_content]
		processed = []
		for block in blocks:
			# 图片处理
			if replace_images:
				block = sub(  # noqa: PLW2901
					r'<img\b [^>]*?src\s*=\s*("([^"]+)"|\'([^\']+)\'|([^\s>]+))[^>]*>',
					replace_img,
					block,
					flags=IGNORECASE,
				)
			# 移除 span 标签但保留内容
			block = sub(r"<span [^>]*>|</span>", "", block)  # noqa: PLW2901
			# 转换 HTML 实体
			if unescape_entities:
				block = unescape(block)  # noqa: PLW2901
				block = block.replace("&nbsp;", " ")  # noqa: PLW2901
			# 移除其他 HTML 标签但保留内容
			text = sub(r"<[^>]+>", "", block)
			# 处理换行
			if not keep_line_breaks:
				text = text.replace("\n", " ")
			processed.append(text)
		# 构建结果
		result = "\n\n".join(processed)
		if merge_empty_lines:
			result = sub(r"\n {3,}", "\n\n", result)
		return result.strip()

	@staticmethod
	def bytes_to_human(size: int) -> str:
		"""将字节数转换为易读格式"""
		size_float = float(size)
		for unit in ["B", "KB", "MB", "GB"]:
			if size_float < FILE_SIZE or unit == "GB":
				return f"{size_float:.2f} {unit}"
			size_float /= FILE_SIZE
		return f"{size_float:.2f} GB"


# ========== 字符串处理器 ==========
@singleton
class StringProcessor:
	"""字符串处理工具类"""

	@staticmethod
	def insert_zero_width(text: str) -> str:
		"""插入零宽空格防爬"""
		return "\u200b".join(text)

	@staticmethod
	def find_substrings(text: str, candidates: Iterable[str]) -> tuple[int | None, int | None]:
		"""在候选中查找子字符串位置"""
		text_str = str(text)
		for candidate in candidates:
			if text_str in candidate:
				parts = candidate.split(".", 1)
				try:
					main_id = int(parts[0])
					sub_id = int(parts[1]) if len(parts) > 1 else None
				except ValueError:
					continue
				else:
					return main_id, sub_id
		return None, None


# ========== 时间工具 ==========
@singleton
class TimeUtils:
	"""时间工具类"""

	@staticmethod
	def current_timestamp(length: Literal[10, 13] = 10) -> int:
		"""获取指定精度的时间戳"""
		if length not in {10, 13}:
			msg = f"Invalid timestamp length: {length}. Valid options are 10 or 13"
			raise ValueError(msg)
		ts = time()
		return int(ts * 1000) if length == 13 else int(ts)

	@staticmethod
	def format_timestamp(ts: float | None = None) -> str:
		"""格式化时间戳为字符串"""
		return strftime("%Y-%m-%d %H:%M:%S", localtime(ts))


# ========== 数据分析器 ==========
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
		"""对比数据集差异"""
		before_dict = self._to_dict(before)
		after_dict = self._to_dict(after)
		if timestamp_field:
			fmt = TimeUtils.format_timestamp
			print(f"时间段: {fmt(before_dict[timestamp_field])} → {fmt(after_dict[timestamp_field])}")
		for field, label in metrics.items():
			before_val = before_dict.get(field, 0)
			after_val = after_dict.get(field, 0)
			diff = after_val - before_val
			print(f"{label}: {diff:+} (当前: {after_val}, 初始: {before_val})")

	@staticmethod
	def _to_dict(data: dict | object) -> dict:
		"""转换为字典"""
		try:
			return DataConverter.to_serializable(data)
		except TypeError as e:
			msg = "数据格式转换失败"
			raise ValueError(msg) from e


# ========== 教育数据生成器 ==========
@singleton
class EduDataGenerator:
	"""教育数据生成器"""

	_CHINESE_NUMBERS: Final[list[str]] = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二"]
	_SPECIALTIES: Final[list[str]] = ["实验", "国际", "理科", "文科"]
	_SURNAMES: Final[list[str]] = ["李", "王", "张", "刘", "陈", "杨", "黄", "赵", "周", "吴"]
	_MALE_NAMES: Final[list[str]] = ["浩", "宇", "轩", "杰", "博", "晨", "俊", "鑫", "昊", "睿", "子轩", "浩然", "俊杰", "宇航", "皓轩", "子豪", "宇轩", "致远", "天佑", "明轩"]
	_FEMALE_NAMES: Final[list[str]] = ["欣", "怡", "婷", "雨", "梓", "涵", "诗", "静", "雅", "娜", "雨萱", "梓涵", "诗琪", "欣怡", "紫萱", "思雨", "梦瑶", "梓晴", "语嫣", "可馨"]

	@classmethod
	def generate_class_names(
		cls,
		num_classes: int,
		grade_range: tuple[int, int] = (1, 6),
		*,
		use_letters: bool = False,
		add_specialty: bool = False,
	) -> list[str]:
		"""生成随机班级名称"""

		def number_to_chinese(n: int) -> str:
			return cls._CHINESE_NUMBERS[n - 1] if 1 <= n <= CLASS_NUM_LIMIT else str(n)

		class_names = []
		for _ in range(num_classes):
			grade = randint(grade_range[0], grade_range[1])
			grade_str = f"{number_to_chinese(grade)} 年级"
			class_num = choice(["A", "B", "C", "D"]) if use_letters and random() < LETTER_PROBABILITY else str(randint(1, 20))
			specialty = ""
			if add_specialty and random() < SPECIALTY_PROBABILITY:
				specialty = choice(cls._SPECIALTIES)
			class_name = f"{grade_str}{class_num}{specialty} 班"
			class_names.append(class_name)
		return class_names

	@classmethod
	def generate_student_names(
		cls,
		num_students: int,
		gender: Literal["male", "female"] | None = None,
	) -> list[str]:
		"""生成随机学生姓名"""
		names = []
		for _ in range(num_students):
			surname = choice(cls._SURNAMES)
			current_gender = gender or choice(["male", "female"])
			first_name = choice(cls._MALE_NAMES) if current_gender == "male" else choice(cls._FEMALE_NAMES)
			# 添加后缀
			if random() < NAME_SUFFIX_PROBABILITY:
				suffix = choice(["儿", "然", "轩", "瑶", "豪", "菲"])
				if current_gender == "male" and suffix in {"儿", "瑶", "菲"}:
					suffix = choice(["然", "轩", "豪"])
				first_name += suffix
			names.append(f"{surname}{first_name}")
		return names


# ========== 加密工具 ==========
@singleton
class Crypto:
	"""加密工具类"""

	def __init__(self, salt: bytes) -> None:
		self.default_salt = salt

	@staticmethod
	def sha256(data: str | bytes) -> str:
		"""计算 SHA256 哈希"""
		if isinstance(data, str):
			data = data.encode()
		return sha256(data).hexdigest()

	@staticmethod
	def reverse_string(s: str) -> str:
		"""字符串反转"""
		return s[::-1]

	@staticmethod
	def base64_to_bytes(base64_str: str) -> bytes:
		"""Base64 解码"""
		try:
			return b64decode(base64_str)
		except Exception as e:
			msg = f"Base64 解码错误: {e}"
			raise ValueError(msg) from e

	def generate_aes_key(self) -> bytes:
		"""生成 AES 密钥"""
		digest = hashes.Hash(hashes.SHA256())
		digest.update(self.default_salt)
		return digest.finalize()

	@staticmethod
	def decrypt_aes_gcm(encrypted_data: bytes, key: bytes, iv: bytes) -> bytes:
		"""AES-GCM 解密"""
		try:
			aesgcm = AESGCM(key)
			return aesgcm.decrypt(iv, encrypted_data, None)
		except Exception as e:
			msg = f"AES 解密错误: {e}"
			raise ValueError(msg) from e

	def decrypt_bcmkn_data(self, encrypted_content: str) -> dict[str, Any]:
		"""解密 BCMKN 数据"""
		# 字符串反转
		reversed_data = self.reverse_string(encrypted_content)
		# Base64 解码
		decoded_data = self.base64_to_bytes(reversed_data)
		# 分离 IV 和密文
		if len(decoded_data) < MIN_DATA_LENGTH:
			msg = "数据太短, 无法分离 IV 和密文"
			raise ValueError(msg)
		iv = decoded_data[:AES_IV_LENGTH]
		cipher_text = decoded_data[AES_IV_LENGTH:]
		# 生成密钥并解密
		key = self.generate_aes_key()
		raw_bytes = self.decrypt_aes_gcm(cipher_text, key, iv)
		text_content = raw_bytes.decode("utf-8", errors="ignore")
		return loads(text_content)


# ========== 输出处理器 ==========
@singleton
class OutputHandler:
	"""输出处理器"""

	def __init__(self) -> None:
		self.color_mgr = ColorManager()
		self._input_prefix = "↳"
		self._input_suffix = ":"
		self._header_width = 60

	def color_text(self, text: str, color_name: str) -> str:
		"""为文本添加颜色"""
		return f"{self.color_mgr.get(color_name)}{text}{self.color_mgr.get('RESET')}"

	def prompt_input(self, text: str, color: str = "PROMPT") -> str:
		"""统一的输入提示函数"""
		prompt_text = f"{self._input_prefix}{text}{self._input_suffix}"
		colored_prompt = self.color_text(prompt_text, color)
		return input(colored_prompt)

	def print_message(self, text: str, color_name: str) -> None:
		"""打印消息"""
		print(self.color_text(text, color_name))

	def print_header(self, text: str) -> None:
		"""打印装饰头部"""
		separator = self.color_mgr.separator
		formatted_text = text.center(self._header_width)
		print(f"\n {separator}")
		print(self.color_text(formatted_text, "MENU_TITLE"))
		print(f"{separator}\n")

	@staticmethod
	def _normalize_string_input(value_str: str, valid_options: set[str]) -> str:
		"""标准化字符串输入"""
		if not valid_options:
			return value_str
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
		cast_type: Callable[[str], T] = str,  # ty:ignore [invalid-parameter-default]
		validator: Callable[[T], bool] | None = None,
		max_attempts: int = 10,
	) -> T:
		"""获取有效输入并进行类型转换验证"""
		attempts = 0
		while attempts < max_attempts:
			try:
				value_str = self.prompt_input(prompt).strip()
				if not value_str:
					self.print_message("输入不能为空, 请重新输入", "WARNING")
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
				type_name = cast_type.__name__  # ty:ignore [unresolved-attribute]
				self.print_message(f"格式错误: 请输入 {type_name} 类型的值 ({e})", "ERROR")
				attempts += 1
			except KeyboardInterrupt:
				self.print_message("\n 操作已取消", "INFO")
				raise
			except Exception as e:
				self.print_message(f"发生意外错误: {e!s}", "ERROR")
				attempts += 1
			else:
				return value
		msg = "输入尝试次数过多, 程序退出"
		raise ValueError(msg)


# ========== 配置类 ==========
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


# ========== 显示渲染器 ==========
@singleton
class DisplayRenderer:
	"""负责数据渲染显示"""

	def __init__(self, output_handler: OutputHandler) -> None:
		self.output = output_handler

	def render_page(
		self,
		data: list[Any],
		field_info: dict[str, Any],
		page_info: dict[str, Any],
		batch_results: dict[int, str] | None = None,
		operations: dict[str, str] | None = None,
	) -> None:
		"""渲染单页数据"""
		self._render_header(page_info)
		self._render_table_header(field_info, batch_results)
		self._render_data_rows(data, field_info, batch_results, operations, page_info)
		self._render_footer()

	def _render_header(self, page_info: dict[str, Any]) -> None:
		"""渲染页眉"""
		self.output.print_header(f"=== {page_info['title']} ===")
		self.output.print_message(f"第 {page_info['current_page']}/{page_info['total_pages']} 页 (共 {page_info['total_items']} 条记录)", "INFO")

	def _render_table_header(self, field_info: dict[str, Any], batch_results: dict[int, str] | None) -> None:
		"""渲染表头"""
		header_parts = ["操作".ljust(10), "序号".ljust(6)]
		header_parts.extend(f"{field}".ljust(20) for field in field_info["fields"])
		if batch_results:
			header_parts.append("状态".ljust(15))
		header = "".join(header_parts)
		separator = "-" * len(header)
		self.output.print_message(separator, "INFO")
		self.output.print_message(header, "INFO")
		self.output.print_message(separator, "INFO")

	def _render_data_rows(
		self,
		data: list[Any],
		field_info: dict[str, Any],
		batch_results: dict[int, str] | None,
		operations: dict[str, str] | None,
		page_info: dict[str, Any],
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
			self.output.print_message(row, "INFO")

	def _render_footer(self) -> None:
		"""渲染页脚"""
		self.output.print_message("-" * 100, "INFO")

	@staticmethod
	def _format_operations(operations: dict[str, str] | None, local_index: int) -> str:
		"""格式化操作显示"""
		if not operations:
			return ""
		operation_display = ""
		for shortcut in operations:
			operation_display += f"{shortcut}{local_index}"
		return operation_display.strip()

	def _batch_format_values(self, item: Any, field_info: dict[str, Any]) -> dict[str, str]:
		"""批量格式化字段值"""
		formatted = {}
		for field in field_info["fields"]:
			value = self._safe_get_attribute(item, field)
			if field in field_info["formatters"]:
				formatted[field] = field_info["formatters"][field](value)
			else:
				formatted[field] = str(value)
		return formatted

	def _safe_get_attribute(self, item: Any, field: str) -> Any:
		"""安全获取属性"""
		try:
			return getattr(item, field, "N/A")
		except Exception as e:
			self.output.print_message(f"获取字段 {field} 时出错: {e}", "ERROR")
			return "ERROR"

	@staticmethod
	def _format_display_value(value: str, max_length: int = 18) -> str:
		"""格式化显示值, 处理长文本"""
		if len(value) > max_length:
			return value[: max_length - 3] + "..."
		return value


# ========== 输入处理器 ==========
@singleton
class InputProcessor:
	"""负责处理用户输入"""

	def __init__(self, output_handler: OutputHandler) -> None:
		self.output = output_handler

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
		self.output.print_message("|".join(options), "INFO")
		try:
			return self.output.get_valid_input(prompt="请选择", valid_options=valid_choices, cast_type=str)
		except (EOFError, KeyboardInterrupt):
			self.output.print_message("\n 操作已取消", "INFO")
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
			options.append(f"{nav_config['next_page']}: 下一页")
		if current_page > 1:
			options.append(f"{nav_config['previous_page']}: 上一页")
		options.append(f"{nav_config['quit']}: 退出")
		# 操作选项
		if custom_operations and operation_shortcuts:
			op_descriptions = [f"{shortcut} 数字:{op_name}" for shortcut, op_name in operation_shortcuts.items()]
			options.extend(op_descriptions)
		return options


# ========== 通用数据查看器 ==========
@singleton
class GenericDataViewer:
	"""通用的数据查看器"""

	def __init__(self, output_handler: OutputHandler | None = None) -> None:
		self.output = output_handler or OutputHandler()
		self.renderer = DisplayRenderer(self.output)
		self.input_processor = InputProcessor(self.output)
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
		"""通用数据显示功能"""
		# 合并导航配置
		nav_config = {**self.default_navigation, **(navigation_config or {})}
		# 参数验证
		self._validate_parameters(data_class, data_list, page_size, display_fields, id_field, nav_config)
		if not data_list:
			self.output.print_message("没有数据可显示", "WARNING")
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
		return {
			"title": title,
			"current_page": current_page,
			"total_pages": total_pages,
			"total_items": total_items,
			"page_size": page_size,
		}

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
		self.output.print_message("无效的输入", "ERROR")
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
		item_num = int(choice[1:]) - 1  # 转换为 0-based 索引
		if 0 <= item_num < len(current_page_items):
			selected_item = current_page_items[item_num]
			op_name = operation_shortcuts[shortcut]
			if custom_operations and op_name in custom_operations:
				try:
					custom_operations[op_name](selected_item)
					self.output.print_message(f"操作 '{op_name}' 执行成功", "SUCCESS")
				except Exception as e:
					self.output.print_message(f"操作 '{op_name}' 执行失败: {e}", "ERROR")
			else:
				self.output.print_message("没有可用的操作", "ERROR")
		else:
			self.output.print_message("无效的选择", "ERROR")

	@staticmethod
	def _is_operation_choice(choice: str, operation_shortcuts: dict[str, str], current_item_count: int) -> bool:
		"""检查是否为操作选择"""
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
		if not is_dataclass(data_class):
			msg = "data_class 必须是一个 dataclass"
			raise TypeError(msg)
		if not isinstance(data_list, list):
			msg = "data_list 必须是一个列表"
			raise TypeError(msg)
		if page_size <= 0:
			msg = "page_size 必须大于 0"
			raise ValueError(msg)
		if display_fields is not None and not isinstance(display_fields, list):
			msg = "display_fields 必须是一个列表或 None"
			raise ValueError(msg)
		self._validate_navigation_config(nav_config)
		self._validate_id_field(data_class, id_field)

	@staticmethod
	def _validate_navigation_config(nav_config: dict[str, str]) -> None:
		"""验证导航配置"""
		required_keys = ["next_page", "previous_page", "quit", "back"]
		missing_keys = [key for key in required_keys if key not in nav_config]
		if missing_keys:
			msg = f"导航配置缺少必需的键: {', '.join(missing_keys)}"
			raise ValueError(msg)
		# 检查字符唯一性
		nav_chars = [nav_config[key] for key in required_keys]
		if len(nav_chars) != len(set(nav_chars)):
			msg = "导航键配置中存在重复的字符"
			raise ValueError(msg)

	def _validate_id_field(self, data_class: type[T], id_field: str) -> None:
		"""验证 ID 字段"""
		try:
			if is_dataclass(data_class):
				field_names = [field.name for field in fields(data_class)]
				if id_field not in field_names:
					self.output.print_message(f"警告: dataclass 中没有找到字段 '{id_field}'", "WARNING")
			else:
				self.output.print_message("警告: 提供的类不是 dataclass", "WARNING")
		except (TypeError, AttributeError):
			self.output.print_message(f"警告: 无法验证字段 '{id_field}', 请确保是有效的 dataclass", "WARNING")

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
			self.output.print_message(f"警告: 以下字段不存在: {', '.join(missing_fields)}", "WARNING")
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
		# 使用可用的字母作为操作快捷键 (避免与导航键冲突)
		available_letters = [chr(i) for i in range(ord("a"), ord("z") + 1) if chr(i) not in existing_shortcuts]
		for i, op_name in enumerate(operations):
			shortcut = available_letters[i] if i < len(available_letters) else str(i - len(available_letters))
			shortcuts[shortcut] = op_name
		return shortcuts


# ========== 工具集工厂 ==========
@singleton
class ToolKitFactory:
	"""工具集工厂, 提供统一的工具访问接口"""

	@staticmethod
	def create_data_processor() -> DataProcessor:
		"""创建数据处理器"""
		return DataProcessor()

	@staticmethod
	def create_data_converter() -> DataConverter:
		"""创建数据转换器"""
		return DataConverter()

	@staticmethod
	def create_string_processor() -> StringProcessor:
		"""创建字符串处理器"""
		return StringProcessor()

	@staticmethod
	def create_time_utils() -> TimeUtils:
		"""创建时间工具"""
		return TimeUtils()

	@staticmethod
	def create_data_analyzer() -> DataAnalyzer:
		"""创建数据分析器"""
		return DataAnalyzer()

	@staticmethod
	def create_edu_data_generator() -> EduDataGenerator:
		"""创建教育数据生成器"""
		return EduDataGenerator()

	@staticmethod
	def create_crypto(salt: bytes) -> Crypto:
		"""创建加密工具"""
		return Crypto(salt)

	@staticmethod
	def create_output_handler() -> OutputHandler:
		"""创建输出处理器"""
		return OutputHandler()

	@staticmethod
	def create_data_viewer(output_handler: OutputHandler | None = None) -> GenericDataViewer:
		"""创建数据查看器"""
		return GenericDataViewer(output_handler)
