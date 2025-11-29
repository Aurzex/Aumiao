from __future__ import annotations

import json
from collections import UserDict
from dataclasses import MISSING, asdict, dataclass, field, fields, is_dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypeVar, cast, get_args, get_origin, get_type_hints

if TYPE_CHECKING:
	from collections.abc import Mapping

from src.utils import decorator

# 改进的类型定义
T = TypeVar("T")
DataclassInstance = Any


# 路径处理改进
class PathConfig:
	"""集中管理所有路径配置"""

	CURRENT_DIR = Path.cwd()
	DATA_DIR = CURRENT_DIR / "data"
	DOWNLOAD_DIR = CURRENT_DIR / "download"
	PLUGIN_PATH = CURRENT_DIR / "plugins"

	# 数据文件路径
	CACHE_FILE_PATH = DATA_DIR / "cache.json"
	DATA_FILE_PATH = DATA_DIR / "data.json"
	HISTORY_FILE_PATH = DATA_DIR / "history.json"
	SETTING_FILE_PATH = DATA_DIR / "setting.json"
	TOKEN_FILE_PATH = DATA_DIR / "token.txt"  # 修正: 改为文件路径

	@classmethod
	def ensure_directories(cls) -> None:
		"""确保所有必要的目录存在"""
		cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
		cls.DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


# 初始化路径配置
PathConfig.ensure_directories()

# 类型别名
ReadType = Literal["COMMENT_REPLY", "LIKE_FORK", "SYSTEM"]


# --------------------------
# 增强型数据类定义
# --------------------------
@dataclass
class AccountData:
	author_level: str = ""
	create_time: str = ""
	description: str = ""
	id: str = ""
	identity: str = ""
	nickname: str = ""
	password: str = ""


@dataclass
class UserData:
	ads: list[str] = field(default_factory=list)
	answers: list[dict[str, str | list[str]]] = field(default_factory=list)
	black_room: list[str] = field(default_factory=list)
	comments: list[str] = field(default_factory=list)
	emojis: list[str] = field(default_factory=list)
	replies: list[str] = field(default_factory=list)


@dataclass
class CodeMaoData:
	ACCOUNT_DATA: AccountData = field(default_factory=AccountData)
	INFO: dict[str, str] = field(default_factory=dict)
	USER_DATA: UserData = field(default_factory=UserData)


@dataclass
class Parameter:
	all_read_type: list[ReadType] = field(default_factory=list)
	cookie_check_url: str = ""
	log: bool = False
	password_login_method: str = ""
	report_work_max: int = 0
	spam_del_max: int = 0


@dataclass
class ExtraBody:
	enable_search: bool = False


@dataclass
class More:
	extra_body: ExtraBody = field(default_factory=ExtraBody)
	stream: bool = False


@dataclass
class Program:
	AUTHOR: str = ""
	HEADERS: dict[str, str] = field(default_factory=dict)
	MEMBER: str = ""
	SLOGAN: str = ""
	TEAM: str = ""
	VERSION: str = ""


@dataclass
class UploadHistory:
	file_name: str = ""
	file_size: str = ""
	method: Literal["codemao", "pgaot", "codegame"] = "pgaot"
	save_url: str = ""
	upload_time: int = 0


@dataclass
class CodeMaoCache:
	collected: int = 0
	fans: int = 0
	level: int = 0
	liked: int = 0
	nickname: str = ""
	timestamp: int = 0
	user_id: int = 0
	view: int = 0


@dataclass
class CodeMaoSetting:
	PARAMETER: Parameter = field(default_factory=Parameter)
	PLUGIN: dict[str, Any] = field(default_factory=dict)
	PROGRAM: Program = field(default_factory=Program)


@dataclass
class CodemaoHistory:
	history: list[UploadHistory] = field(default_factory=list)


# --------------------------
# 增强型转换工具
# --------------------------
class DataClassConverter:
	"""数据类转换工具"""

	@staticmethod
	def validate_literal(value: object, field_type: type) -> object:
		"""验证Literal类型字段值"""
		if get_origin(field_type) is Literal:
			valid_values = get_args(field_type)
			if value not in valid_values:
				print(f"Warning: Invalid value. Expected one of {valid_values}, got {value}")
				return valid_values[0] if valid_values else None
		return value

	@classmethod
	def dict_to_dataclass(cls, data_class: type[T], data: Mapping[str, Any]) -> T:
		"""将字典转换为数据类实例"""
		if not (is_dataclass(data_class) and isinstance(data_class, type)):
			msg = f"{data_class.__name__} must be a dataclass type"
			raise ValueError(msg)

		field_types = get_type_hints(data_class)
		kwargs: dict[str, Any] = {}

		for field_name, field_type in field_types.items():
			if field_name not in data:
				continue

			value = data[field_name]
			origin_type = get_origin(field_type)
			type_args = get_args(field_type)

			# 处理Literal类型
			if get_origin(field_type) is Literal:
				kwargs[field_name] = cls.validate_literal(value, field_type)
				continue

			# 处理嵌套数据类
			if isinstance(field_type, type) and is_dataclass(field_type):
				kwargs[field_name] = cls.dict_to_dataclass(field_type, value)

			# 处理列表类型
			elif origin_type is list and type_args:
				item_type = type_args[0]
				kwargs[field_name] = cls._process_list_value(value, item_type)

			# 处理字典类型
			elif origin_type is dict and type_args:
				key_type, val_type = type_args
				kwargs[field_name] = cls._process_dict_value(value, key_type, val_type)

			# 处理其他类型
			else:
				kwargs[field_name] = cls._process_basic_value(value, field_type)

		return data_class(**kwargs)

	@classmethod
	def _process_list_value(cls, value: object, item_type: type) -> list[Any]:
		"""处理列表类型的值"""
		if not isinstance(value, list):
			return []

		if isinstance(item_type, type) and is_dataclass(item_type):
			return [cls.dict_to_dataclass(item_type, item) for item in value]

		if get_origin(item_type) is Literal:
			# 特殊处理列表中的Literal类型
			valid_values = get_args(item_type)
			return [item if item in valid_values else (valid_values[0] if valid_values else None) for item in value]

		try:
			return [item_type(v) for v in value]
		except (TypeError, ValueError):
			print(f"Warning: Failed to convert list item to {item_type.__name__}")
			return list(value)

	@classmethod
	def _process_dict_value(cls, value: object, key_type: type, val_type: type) -> dict[Any, Any]:
		"""处理字典类型的值"""
		if not isinstance(value, dict):
			return {}

		if isinstance(val_type, type) and is_dataclass(val_type):
			return {key_type(k): cls.dict_to_dataclass(val_type, v) for k, v in value.items()}
		try:
			return {key_type(k): val_type(v) for k, v in value.items()}
		except (TypeError, ValueError):
			print(f"Warning: Failed to convert dict values to {val_type.__name__}")
			return dict(value)

	@classmethod
	def _process_basic_value(cls, value: object, field_type: type) -> Any:  # noqa: ANN401
		"""处理基本类型的值"""
		if isinstance(value, field_type):
			return value
		try:
			return field_type(value)
		except (TypeError, ValueError):
			print(f"Warning: Failed to convert {value} to {field_type.__name__}")
			return value


# --------------------------
# 增强型文件操作
# --------------------------
class JsonFileHandler:
	"""JSON文件处理器"""

	@staticmethod
	def load_json_file(path: Path, data_class: type[T]) -> T:
		"""从JSON文件加载数据到数据类"""
		try:
			if not path.exists():
				return data_class()

			with path.open(encoding="utf-8") as f:
				data = json.load(f)

			# 预处理Literal类型字段
			field_types = get_type_hints(data_class)
			for field_name, field_type in field_types.items():
				if field_name in data and get_origin(field_type) is Literal:
					valid_values = get_args(field_type)
					if data[field_name] not in valid_values:
						data[field_name] = valid_values[0] if valid_values else None

			return DataClassConverter.dict_to_dataclass(data_class, data)

		except (json.JSONDecodeError, ValueError) as e:
			print(f"Error loading {path.name}: {e}")
			return data_class()
		except Exception as e:
			print(f"Unexpected error loading {path.name}: {e}")
			return data_class()

	@staticmethod
	def save_json_file(path: Path, data: object) -> None:
		"""将数据类实例保存到JSON文件"""
		if not is_dataclass(data) or isinstance(data, type):
			msg = "Only dataclass instances can be saved"
			raise ValueError(msg)

		temp_file = path.with_suffix(".tmp")
		try:
			serialized = asdict(data)
			with temp_file.open("w", encoding="utf-8") as f:
				json.dump(serialized, f, ensure_ascii=False, indent=4)
			temp_file.replace(path)
		except Exception as e:
			temp_file.unlink(missing_ok=True)
			error_msg = f"Failed to save {path.name}: {e}"
			raise RuntimeError(error_msg) from e


# --------------------------
# 统一管理器基类
# --------------------------
class BaseManager[T]:
	"""基础数据管理器"""

	_data: T | None = None
	_file_path: Path
	_data_class: type[T]

	def __init__(self, file_path: Path, data_class: type[T]) -> None:
		self._file_path = file_path
		self._data_class = data_class

	@property
	def data(self) -> T:
		"""获取数据实例(懒加载)"""
		if self._data is None:
			self._data = JsonFileHandler.load_json_file(self._file_path, self._data_class)
		return self._data

	def update(self, new_data: dict[str, Any]) -> None:
		"""更新数据"""
		for key, value in new_data.items():
			if not hasattr(self.data, key):
				continue

			current = getattr(self.data, key)

			# 处理嵌套数据类更新
			if current is not None and is_dataclass(current) and not isinstance(current, type):
				if not isinstance(value, dict):
					error_msg = f"Expected dict for {key}, got {type(value).__name__}"
					raise TypeError(error_msg)

				# 创建有效字段的字典
				valid_fields = {f.name for f in fields(current)}
				filtered_value = {k: v for k, v in value.items() if k in valid_fields}

				# 使用 replace 更新实例
				updated_value = replace(current, **filtered_value)
				setattr(self.data, key, updated_value)
			else:
				setattr(self.data, key, value)

		self.save()

	def reset(self, *fields_to_reset: str) -> None:
		"""重置指定字段到默认值"""
		data_instance = cast("DataclassInstance", self.data)
		for f in fields(data_instance):
			if f.name in fields_to_reset:
				if f.default is not MISSING:
					setattr(self.data, f.name, f.default)
				elif f.default_factory is not MISSING:
					setattr(self.data, f.name, f.default_factory())

		self.save()

	def save(self) -> None:
		"""保存数据到文件"""
		JsonFileHandler.save_json_file(self._file_path, self.data)

	def reload(self) -> None:
		"""重新加载数据"""
		self._data = None


# --------------------------
# 单例管理器
# --------------------------
@decorator.singleton
class DataManager(BaseManager[CodeMaoData]):
	def __init__(self) -> None:
		super().__init__(file_path=PathConfig.DATA_FILE_PATH, data_class=CodeMaoData)


@decorator.singleton
class CacheManager(BaseManager[CodeMaoCache]):
	def __init__(self) -> None:
		super().__init__(file_path=PathConfig.CACHE_FILE_PATH, data_class=CodeMaoCache)


@decorator.singleton
class SettingManager(BaseManager[CodeMaoSetting]):
	def __init__(self) -> None:
		super().__init__(file_path=PathConfig.SETTING_FILE_PATH, data_class=CodeMaoSetting)


@decorator.singleton
class HistoryManager(BaseManager[CodemaoHistory]):
	def __init__(self) -> None:
		super().__init__(file_path=PathConfig.HISTORY_FILE_PATH, data_class=CodemaoHistory)


class NestedDefaultDict(UserDict[str, Any]):
	"""嵌套默认字典"""

	def __getitem__(self, key: str) -> Any:  # noqa: ANN401
		if key not in self.data:
			return "UNKNOWN"
		val = self.data[key]
		if isinstance(val, dict):
			return NestedDefaultDict(val)
		return val

	def to_dict(self) -> dict[str, Any]:
		"""转换为普通字典"""
		result = {}
		for key, value in self.data.items():
			if isinstance(value, NestedDefaultDict):
				result[key] = value.to_dict()
			else:
				result[key] = value
		return result


# 导出常用实例
data_manager = DataManager()
cache_manager = CacheManager()
setting_manager = SettingManager()
history_manager = HistoryManager()
