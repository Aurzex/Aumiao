from __future__ import annotations

from collections import UserDict
from dataclasses import MISSING, asdict, dataclass, field, fields, is_dataclass, replace
from json import JSONDecodeError, dump, dumps, load
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypeVar, cast, get_args, get_origin, get_type_hints

if TYPE_CHECKING:
	from collections.abc import Mapping
from aumiao.utils import decorator

# 改进的类型定义
T = TypeVar("T")
DataclassInstance = Any


# 路径处理改进
class PathConfig:
	"""集中管理所有路径配置"""

	CURRENT_DIR = Path.cwd()
	CACHE_DIR = CURRENT_DIR / "cache"
	DATA_DIR = CURRENT_DIR / "data"
	DOWNLOAD_DIR = CURRENT_DIR / "download"
	JS_DIR: Path = CURRENT_DIR / "js_module"
	# PLUGIN_DIR = CURRENT_DIR / "plugins"
	# 文件夹嵌套文件夹
	COMPILE_FILE_PATH = DOWNLOAD_DIR / "compile"
	FICTION_FILE_PATH = DOWNLOAD_DIR / "fiction"
	# 数据文件路径
	CACHE_FILE_PATH = CACHE_DIR / "info.json"
	CAPTCHA_FILE_PATH: Path = CACHE_DIR / "captcha.jpg"
	DATA_FILE_PATH = DATA_DIR / "data.json"
	HISTORY_FILE_PATH = CACHE_DIR / "history.json"
	SETTING_FILE_PATH = DATA_DIR / "setting.json"
	TOKEN_FILE_PATH = DATA_DIR / "token.txt"
	PASSWORD_FILE_PATH = DATA_DIR / "password.txt"

	@classmethod
	def ensure_directories(cls) -> None:
		"""确保所有必要的目录存在"""
		cls.CACHE_DIR.mkdir(parents=True, exist_ok=True)
		cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
		cls.DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

	@classmethod
	def get_config_files(cls) -> list[tuple[Path, type]]:
		"""获取所有配置文件路径和对应的数据类型"""
		return [
			(cls.DATA_FILE_PATH, CodeMaoData),
			(cls.CACHE_FILE_PATH, CodeMaoCache),
			(cls.HISTORY_FILE_PATH, CodemaoHistory),
			(cls.SETTING_FILE_PATH, CodeMaoSetting),
		]


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
	id: int = 0
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
	# PLUGIN: dict[str, Any] = field(default_factory=dict)
	PROGRAM: Program = field(default_factory=Program)


@dataclass
class CodemaoHistory:
	history: list[UploadHistory] = field(default_factory=list)


# --------------------------
# 默认配置数据
# --------------------------
# setting.json 的默认配置
DEFAULT_SETTING_DATA = {
	"PARAMETER": {
		"all_read_type": ["COMMENT_REPLY", "LIKE_FORK", "SYSTEM"],
		"log": False,
		"password_login_method": "token",
		"report_work_max": 8,
		"spam_del_max": 3,
	},
	# "PLUGIN": {},
	"PROGRAM": {
		"AUTHOR": "Aurzex",
		"HEADERS": {
			"Accept-Encoding": "gzip, deflate, br, zstd",
			"Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
			"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0",
		},
		"MEMBER": "Aurzex, MoonLeaaaf, Nomen, MiTao, DontLoveBy",
		"SLOGAN": "欢迎使用 Aumiao-PY!"
		"你说的对, 但是《Aumiao》是一款由 Aumiao 开发团队开发的编程猫自动化工具, 于 2023 年 5 月 2 日发布"
		"工具以编程猫宇宙为舞台, 玩家可以扮演扮演毛毡用户, 在这个社区毛线坍缩并邂逅各种不同的乐子人"
		"在领悟了《猫站圣经》后, 打败强敌扫厕所, 在维护编程猫核邪铀删的局面的同时, 逐步揭开编程猫社区的真相",
		"TEAM": "Aumiao Team",
		"VERSION": "2.7.0",
	},
}
# data.json 的默认配置
DEFAULT_DATA_DATA = {
	"ACCOUNT_DATA": {"author_level": 1, "create_time": 1800000000, "description": "", "id": "1742185446", "identity": "********", "nickname": " 猫猫捏 ", "password": "******"},
	"INFO": {"e_mail": "zybqw@qq.com", "nickname": "喵鱼 a", "qq_number": "3611198191"},
	"USER_DATA": {
		"ads": [
			"codemao.cn/work",
			"cpdd",
			"scp",
			"不喜可删",
			"互关",
			"互赞",
			"交友",
			"光头强",
			"关注",
			"再创作",
			"冲传说",
			"冲大佬",
			"冲高手",
			"协作项目",
			"基金会",
			"处cp",
			"家族招人",
			"我的作品",
			"戴雨默",
			"所有作品",
			"扫厕所",
			"找徒弟",
			"找闺",
			"招人",
			"有赞必回",
			"点个",
			"爬虫",
			"看一下我的",
			"看我的",
			"看看我的",
			"粘贴到别人作品",
			"赞我",
			"转发",
		],
		"answers": [
			{"牢大": "孩子们, 我回来了"},
			{"奶龙": "我才是奶龙"},
			{"name": "I'm {nickname}"},
			{"QQ": "It's {qq_number}"},
			{"只因": ["不许你黑我家鸽鸽!😡", "想要绿尸函了食不食?", "香精煎鱼食不食?"]},
		],
		"black_room": ["2233", "114514", "1919810"],
		"comments": ["666", "不错不错", "前排:P", "加油!:O", "沙发 */ω\\*", "针不戳:D"],
		"emojis": [
			"星能猫_好吃",
			"星能猫_耶",
			"编程猫_666",
			"编程猫_加油",
			"编程猫_好厉害",
			"编程猫_我来啦",
			"编程猫_打call",
			"编程猫_抱大腿",
			"编程猫_棒",
			"编程猫_点手机",
			"编程猫_爱心",
			"编程猫_爱心",
			"雷电猴_哇塞",
			"雷电猴_哈哈哈",
			"雷电猴_嘻嘻嘻",
			"雷电猴_围观",
			"魔术喵_开心",
			"魔术喵_收藏",
			"魔术喵_点赞",
			"魔术喵_点赞",
			"魔术喵_魔术",
		],
		"replies": [
			"{nickname} 很忙 oh, 机器人来凑热闹 (*^^*)",
			"{nickname} 的自动回复来喽",
			"嗨嗨嗨! 这事 {nickname} の自动回复鸭!",
			"对不起,{nickname} 它又搞忘了时间, 一定是在忙呢",
			"这是 {nickname} 的自动回复, 不知道你在说啥 (",
		],
	},
}


# --------------------------
# 增强型转换工具
# --------------------------
class DataClassConverter:
	"""数据类转换工具"""

	@staticmethod
	def validate_literal(value: object, field_type: type) -> object:
		"""验证 Literal 类型字段值"""
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
			# 处理 Literal 类型
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
			return [cls.dict_to_dataclass(item_type, item) for item in value]  # ty:ignore[invalid-argument-type]
		if get_origin(item_type) is Literal:
			# 特殊处理列表中的 Literal 类型
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
			return {key_type(k): cls.dict_to_dataclass(val_type, v) for k, v in value.items()}  # ty:ignore[invalid-argument-type]
		try:
			return {key_type(k): val_type(v) for k, v in value.items()}
		except (TypeError, ValueError):
			print(f"Warning: Failed to convert dict values to {val_type.__name__}")
			return dict(value)

	@classmethod
	def _process_basic_value(cls, value: object, field_type: type) -> Any:
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
	"""JSON 文件处理器"""

	@staticmethod
	def load_json_file(path: Path, data_class: type[T], *, create_if_missing: bool = True) -> T:
		"""从 JSON 文件加载数据到数据类, 如果文件不存在则创建"""
		try:
			if not path.exists():
				if create_if_missing:
					print(f"文件 {path.name} 不存在, 使用默认值创建...")
					# 根据路径选择默认数据
					default_data = {}
					if path == PathConfig.SETTING_FILE_PATH:
						default_data = DEFAULT_SETTING_DATA
					elif path == PathConfig.DATA_FILE_PATH:
						default_data = DEFAULT_DATA_DATA
					# 创建默认实例并保存
					instance = DataClassConverter.dict_to_dataclass(data_class, default_data)
					JsonFileHandler.save_json_file(path, instance)
					return instance
				return data_class()
			with path.open(encoding="utf-8") as f:
				data = load(f)
			# 预处理 Literal 类型字段
			field_types = get_type_hints(data_class)
			for field_name, field_type in field_types.items():
				if field_name in data and get_origin(field_type) is Literal:
					valid_values = get_args(field_type)
					if data[field_name] not in valid_values:
						data[field_name] = valid_values[0] if valid_values else None
			return DataClassConverter.dict_to_dataclass(data_class, data)
		except (JSONDecodeError, ValueError) as e:
			print(f"Error loading {path.name}: {e}")
			print("使用默认值...")
			return data_class()
		except Exception as e:
			print(f"Unexpected error loading {path.name}: {e}")
			return data_class()

	@staticmethod
	def save_json_file(path: Path, data: object) -> None:
		"""将数据类实例保存到 JSON 文件"""
		if not is_dataclass(data) or isinstance(data, type):
			msg = "Only dataclass instances can be saved"
			raise ValueError(msg)
		temp_file = path.with_suffix(".tmp")
		try:
			serialized = asdict(data)
			with temp_file.open("w", encoding="utf-8") as f:
				dump(serialized, f, ensure_ascii=False, indent=4, separators=(",", ":"))
			temp_file.replace(path)
			print(f"文件 {path.name} 已保存")
		except Exception as e:
			temp_file.unlink(missing_ok=True)
			error_msg = f"Failed to save {path.name}: {e}"
			raise RuntimeError(error_msg) from e


# --------------------------
# 初始化函数
# --------------------------
def initialize_config_files() -> None:
	"""初始化所有配置文件, 如果不存在则用默认值创建"""
	print("正在初始化配置文件...")
	for file_path, data_class in PathConfig.get_config_files():
		if not file_path.exists():
			print(f"创建配置文件: {file_path.name}")
			JsonFileHandler.load_json_file(file_path, data_class, create_if_missing=True)
		else:
			print(f"配置文件已存在: {file_path.name}")
	print("配置文件初始化完成!")


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
		# 确保文件存在
		if not file_path.exists():
			JsonFileHandler.load_json_file(file_path, data_class, create_if_missing=True)

	@property
	def data(self) -> T:
		"""获取数据实例 (懒加载)"""
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

	def dataclass(self) -> type[T]:
		"""获取dataclass实例"""
		return self._data_class


# --------------------------
# 单例管理器
# --------------------------
@decorator.singleton
class CodeMaoFile:
	@staticmethod
	def file_write(
		path: Path,
		content: str | bytes | dict | list[str],
		method: str = "w",
		encoding: str = "utf-8",
	) -> None:
		# 确保父目录存在
		path.parent.mkdir(parents=True, exist_ok=True)
		# 根据内容类型自动决定模式和编码
		mode = method
		kwargs = {}
		if isinstance(content, (str, dict, list)):
			# 文本模式需指定编码
			kwargs["encoding"] = encoding
			if "b" in mode:
				# 禁止文本内容使用二进制模式
				msg = f"文本内容不能使用二进制模式: {mode}"
				raise ValueError(msg)
		elif isinstance(content, bytes):
			# 字节内容强制使用二进制模式
			if "b" not in mode:
				mode += "b"
		# 打开文件并写入
		with Path.open(path, mode, **kwargs) as f:
			if isinstance(content, (str, bytes)):
				f.write(content)
			elif isinstance(content, dict):
				json_str = dumps(content, ensure_ascii=False, indent=4)
				f.write(json_str)
			elif isinstance(content, list):
				f.writelines(line + "\n" for line in content)


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

	def __getitem__(self, key: str) -> Any:
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
