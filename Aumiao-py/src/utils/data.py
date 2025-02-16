import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, fields, is_dataclass, replace
from pathlib import Path
from typing import Any, Generic, TypeVar, cast, get_args, get_origin, get_type_hints

from . import decorator

# 添加 DataclassInstance 定义

T = TypeVar("T")
DataclassInstance = T
# 常量定义
DATA_DIR = Path.cwd() / "data"
DATA_FILE_PATH = DATA_DIR / "data.json"
CACHE_FILE_PATH = DATA_DIR / "cache.json"
SETTING_FILE_PATH = DATA_DIR / "setting.json"

# 确保数据目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)


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
	INFO: dict[str, str] = field(default_factory=dict)
	ACCOUNT_DATA: AccountData = field(default_factory=AccountData)
	USER_DATA: UserData = field(default_factory=UserData)


@dataclass
class DefaultAction:
	action: str = ""
	name: str = ""


@dataclass
class Parameter:
	all_read_type: list[str] = field(default_factory=list)
	clear_ad_exclude_top: bool = False
	cookie_check_url: str = ""
	get_works_method: str = ""
	password_login_method: str = ""
	spam_max: int = 0
	report_max: int = 0


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
	DEFAULT: list[DefaultAction] = field(default_factory=list)
	PARAMETER: Parameter = field(default_factory=Parameter)
	PLUGIN: Plugin = field(default_factory=Plugin)
	PROGRAM: Program = field(default_factory=Program)


# --------------------------
# 增强型转换工具
# --------------------------
def dict_to_dataclass(cls: type[T], data: Mapping[str, Any]) -> T:
	"""安全类型转换字典到数据类,支持嵌套结构和泛型"""
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

		# 处理嵌套数据类(添加类型断言)
		if is_dataclass(field_type):
			kwargs[field_name] = dict_to_dataclass(cast(type, field_type), value)
		# 处理泛型容器(添加类型断言)
		elif origin_type is list and type_args:
			item_type = type_args[0]
			if is_dataclass(item_type):
				kwargs[field_name] = [
					dict_to_dataclass(cast(type, item_type), item)  # 类型断言
					for item in value
				]
			else:
				kwargs[field_name] = value
		elif origin_type is dict and type_args:
			key_type, val_type = type_args
			kwargs[field_name] = {key_type(k): val_type(v) for k, v in value.items()}
		else:
			try:
				kwargs[field_name] = field_type(value)
			except TypeError:
				kwargs[field_name] = value

	return cls(**kwargs)


# --------------------------
# 增强型文件操作
# --------------------------
def load_json_file(path: Path, data_class: type[T]) -> T:
	"""安全加载JSON文件,增强错误处理"""
	try:
		if not path.exists():
			return data_class()

		with path.open(encoding="utf-8") as f:
			data = json.load(f)
			return dict_to_dataclass(data_class, data)
	except (json.JSONDecodeError, KeyError, TypeError) as e:
		print(f"Error loading {path.name}: {e!s}")
		return data_class()
	except Exception as e:
		print(f"Unexpected error loading {path.name}: {e!s}")
		return data_class()


def save_json_file(path: Path, data: object) -> None:
	"""原子化写入JSON文件,防止数据损坏"""
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
# 统一管理器基类
# --------------------------
class BaseManager(Generic[T]):
	_data: T
	_file_path: Path

	def __init__(self, file_path: Path, data_class: type[T]) -> None:
		self._data = load_json_file(file_path, data_class)
		self._file_path = file_path

	@property
	def data(self) -> T:
		"""明确返回类型为泛型 T"""
		return self._data

	def update(self, new_data: dict[str, Any]) -> None:
		"""类型安全的深度更新"""
		for key, value in new_data.items():
			if not hasattr(self._data, key):
				continue
			current = getattr(self._data, key)

			# 确保 current 是实例
			if isinstance(current, type) and is_dataclass(current):
				current = current()

			if is_dataclass(current):
				if not isinstance(value, dict):
					msg = f"Expected dict for {key}, got {type(value).__name__}"
					raise TypeError(msg)

				# 使用 cast 来确保类型检查器知道 current 是一个数据类实例
				current = cast(DataclassInstance, current)

				# 创建一个新的字典,只包含数据类字段中存在的键
				valid_fields = {f.name for f in fields(current)}
				filtered_value = {k: v for k, v in value.items() if k in valid_fields}
				updated_value = replace(current, **filtered_value)
				setattr(self._data, key, updated_value)
			else:
				setattr(self._data, key, value)

		self.save()

	def reset(self, *fields: str) -> None:
		"""重置指定字段到默认值"""
		for field_name in fields:
			if hasattr(self._data, field_name):
				default_value = self._data.__annotations__[field_name]()
				setattr(self._data, field_name, default_value)
		self.save()

	def save(self) -> None:
		save_json_file(self._file_path, self._data)


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
