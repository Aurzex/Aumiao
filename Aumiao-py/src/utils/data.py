import json
import os
from collections.abc import Mapping
from dataclasses import MISSING, asdict, dataclass, field, fields, is_dataclass, replace
from pathlib import Path
from typing import Any, Literal, TypeVar, cast, get_args, get_origin, get_type_hints

from . import decorator

# 改进的类型定义
T = TypeVar("T")
DataclassInstance = Any  # 类型别名

# 路径处理改进
CURRENT_DIR = Path.cwd()
DATA_DIR = Path(os.getenv("APP_DATA_DIR", CURRENT_DIR / "data"))

CACHE_FILE_PATH = DATA_DIR / "cache.json"
DATA_FILE_PATH = DATA_DIR / "data.json"
SETTING_FILE_PATH = DATA_DIR / "setting.json"

# 确保数据目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 定义Literal类型别名
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
	log: bool = True
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
class DashscopePlugin:
	model: str = ""
	more: More = field(default_factory=More)


@dataclass
class Plugin:
	DASHSCOPE: DashscopePlugin = field(default_factory=DashscopePlugin)
	prompt: str = ""


@dataclass
class Program:
	AUTHOR: str = ""
	HEADERS: dict[str, str] = field(default_factory=dict)
	MEMBER: str = ""
	SLOGAN: str = ""
	TEAM: str = ""
	VERSION: str = ""


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
	PLUGIN: Plugin = field(default_factory=Plugin)
	PROGRAM: Program = field(default_factory=Program)


# --------------------------
# 增强型转换工具
# --------------------------
def validate_literal(value: Any, field_type: type) -> Any:  # noqa: ANN401
	"""验证Literal类型字段值"""
	if get_origin(field_type) is Literal:
		valid_values = get_args(field_type)
		if value not in valid_values:
			msg = f"Invalid value. Expected one of {valid_values}, got {value}"
			raise ValueError(msg)
	return value


def dict_to_dataclass[T](cls: type[T], data: Mapping[str, Any]) -> T:  # noqa: PLR0912
	if not (is_dataclass(cls) and isinstance(cls, type)):
		msg = f"{cls.__name__} must be a dataclass type"
		raise ValueError(msg)

	field_types = get_type_hints(cls)
	kwargs = {}

	for field_name, field_type in field_types.items():
		if field_name not in data:
			continue

		value = data[field_name]
		origin_type = get_origin(field_type)
		type_args = get_args(field_type)

		# 特殊处理Literal类型
		if get_origin(field_type) is Literal:
			try:
				value = validate_literal(value, field_type)
			except ValueError as e:
				print(f"Warning: {e}. Using first valid value.")
				value = get_args(field_type)[0] if get_args(field_type) else None
			kwargs[field_name] = value
			continue

		# 处理嵌套数据类 - 添加类型断言
		if isinstance(field_type, type) and is_dataclass(field_type):
			kwargs[field_name] = dict_to_dataclass(field_type, value)
		# 处理泛型列表 - 改进对Literal类型的处理
		elif origin_type is list and type_args:
			item_type = type_args[0]
			if isinstance(item_type, type) and is_dataclass(item_type):
				kwargs[field_name] = [dict_to_dataclass(item_type, item) for item in value]
			elif get_origin(item_type) is Literal:
				# 特殊处理列表中的Literal类型
				valid_values = get_args(item_type)
				processed_items = []
				for item in value:
					if item in valid_values:
						processed_items.append(item)
					else:
						print(f"Warning: Invalid value in list. Expected one of {valid_values}, got {item}")
						if valid_values:
							processed_items.append(valid_values[0])
				kwargs[field_name] = processed_items
			else:
				kwargs[field_name] = [item_type(v) for v in value]
		# 处理泛型字典 - 添加类型断言
		elif origin_type is dict and type_args:
			key_type, val_type = type_args
			if isinstance(val_type, type) and is_dataclass(val_type):
				kwargs[field_name] = {key_type(k): dict_to_dataclass(val_type, v) for k, v in value.items()}
			else:
				kwargs[field_name] = {key_type(k): val_type(v) for k, v in value.items()}
		# 处理其他类型
		elif isinstance(value, field_type):
			kwargs[field_name] = value
		else:
			try:
				kwargs[field_name] = field_type(value)
			except (TypeError, ValueError):
				kwargs[field_name] = value

	return cls(**kwargs)


# --------------------------
# 增强型文件操作
# --------------------------
def load_json_file[T](path: Path, data_class: type[T]) -> T:
	try:
		if not path.exists():
			return data_class()

		with path.open(encoding="utf-8") as f:
			data = json.load(f)

			# 预处理Literal类型字段
			if hasattr(data_class, "__annotations__"):
				for field_name, field_type in get_type_hints(data_class).items():
					if field_name in data and get_origin(field_type) is Literal:
						valid_values = get_args(field_type)
						if data[field_name] not in valid_values:
							data[field_name] = valid_values[0] if valid_values else None

			return dict_to_dataclass(data_class, data)
	except (json.JSONDecodeError, ValueError) as e:
		print(f"Error loading {path.name}: {e!s}")
		return data_class()
	except Exception as e:
		print(f"Unexpected error loading {path.name}: {e!s}")
		return data_class()


def save_json_file(path: Path, data: object) -> None:
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
		msg = f"Failed to save {path.name}: {e!s}"
		raise RuntimeError(msg) from e


# --------------------------
# 统一管理器基类 - 使用 PEP 695 语法解决 UP046 警告
# --------------------------
class BaseManager[T]:
	_data: T | None = None
	_file_path: Path

	def __init__(self, file_path: Path, data_class: type[T]) -> None:
		self._file_path = file_path
		self._data_class = data_class

	@property
	def data(self) -> T:
		if self._data is None:
			self._data = load_json_file(self._file_path, self._data_class)
		return self._data

	def update(self, new_data: dict[str, Any]) -> None:
		for key, value in new_data.items():
			if not hasattr(self.data, key):
				continue
			current = getattr(self.data, key)

			# 确保处理的是数据类实例而不是类型
			if current is not None and is_dataclass(current) and not isinstance(current, type):
				if not isinstance(value, dict):
					msg = f"Expected dict for {key}, got {type(value).__name__}"
					raise TypeError(msg)

				# 创建有效字段的字典
				valid_fields = {f.name for f in fields(current)}
				filtered_value = {k: v for k, v in value.items() if k in valid_fields}

				# 使用 replace 更新实例 - 添加类型断言
				updated_value = replace(cast("DataclassInstance", current), **filtered_value)
				setattr(self.data, key, updated_value)
			else:
				setattr(self.data, key, value)

		self.save()

	def reset(self, *fields_to_reset: str) -> None:
		"""重置指定字段到默认值"""
		# 直接使用实例的字段信息 - 添加类型断言
		for f in fields(cast("DataclassInstance", self.data)):
			if f.name in fields_to_reset:
				if f.default is not MISSING:
					setattr(self.data, f.name, f.default)
				elif f.default_factory is not MISSING:
					setattr(self.data, f.name, f.default_factory())
		self.save()

	def save(self) -> None:
		save_json_file(self._file_path, self.data)


# --------------------------
# 单例管理器
# --------------------------
@decorator.singleton
class DataManager(BaseManager[CodeMaoData]):
	def __init__(self) -> None:
		super().__init__(DATA_FILE_PATH, CodeMaoData)


@decorator.singleton
class CacheManager(BaseManager[CodeMaoCache]):
	def __init__(self) -> None:
		super().__init__(CACHE_FILE_PATH, CodeMaoCache)


@decorator.singleton
class SettingManager(BaseManager[CodeMaoSetting]):
	def __init__(self) -> None:
		super().__init__(SETTING_FILE_PATH, CodeMaoSetting)
