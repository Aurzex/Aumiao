"""基础定义和核心Union类"""

from collections import namedtuple
from collections.abc import Callable, Generator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, TypedDict, cast

from src.api import auth, community, edu, forum, library, shop, user, whale, work
from src.utils import acquire, data, decorator, file, tool

# ==============================
# 常量定义
# ==============================
# 数据大小限制
MAX_SIZE_BYTES: int = 15 * 1024 * 1024  # 15MB
REPORT_BATCH_THRESHOLD: int = 15
# 回复类型验证集
VALID_REPLY_TYPES: set[str] = {"WORK_COMMENT", "WORK_REPLY", "WORK_REPLY_REPLY", "POST_COMMENT", "POST_REPLY", "POST_REPLY_REPLY"}


# ==============================
# 类型定义
# ==============================
class FormattedAnswer(TypedDict):
	"""格式化答案类型"""

	question: str
	responses: list[str] | str


class ReplyType(Enum):
	"""回复类型枚举"""

	WORK_COMMENT = "WORK_COMMENT"
	WORK_REPLY = "WORK_REPLY"
	WORK_REPLY_REPLY = "WORK_REPLY_REPLY"
	POST_COMMENT = "POST_COMMENT"
	POST_REPLY = "POST_REPLY"
	POST_REPLY_REPLY = "POST_REPLY_REPLY"


class ReportRecord(TypedDict):
	"""举报记录类型"""

	item: "data.NestedDefaultDict"
	report_type: Literal["comment", "post", "discussion"]
	item_id: str
	content: str
	processed: bool
	action: str | None


# ==============================
# 配置类定义
# ==============================
@dataclass(frozen=True)
class HTTPConfig:
	"""HTTP相关配置"""

	SUCCESS_CODE: int = 200
	CONNECTION_TIMEOUT: int = 30
	REQUEST_TIMEOUT: int = 10


@dataclass(frozen=True)
class WebSocketConfig:
	"""WebSocket相关配置"""

	PING_MESSAGE: str = "2"
	PONG_MESSAGE: str = "3"
	CONNECT_MESSAGE: str = "40"
	CONNECTED_MESSAGE: str = "40"
	EVENT_MESSAGE_PREFIX: str = "42"
	HANDSHAKE_MESSAGE_PREFIX: str = "0"
	TRANSPORT_TYPE: str = "websocket"
	PING_INTERVAL: int = 20
	PING_TIMEOUT: int = 10
	MESSAGE_TYPE_LENGTH: int = 2


@dataclass(frozen=True)
class DisplayConfig:
	"""显示相关配置"""

	MAX_DISPLAY_LENGTH: int = 50
	TRUNCATED_SUFFIX: str = "..."
	MAX_LIST_DISPLAY_ELEMENTS: int = 6
	PARTIAL_LIST_DISPLAY_COUNT: int = 3


@dataclass(frozen=True)
class DataConfig:
	"""数据相关配置"""

	DATA_TIMEOUT: int = 30
	DEFAULT_RANKING_LIMIT: int = 31
	MAX_INACTIVITY_TIME: int = 30
	MAX_RECONNECT_ATTEMPTS: int = 5
	PING_INTERVAL_MS: int = 25000
	PING_TIMEOUT_MS: int = 5000
	RECONNECT_INTERVAL: int = 8
	WAIT_TIMEOUT: int = 30


@dataclass(frozen=True)
class ValidationConfig:
	"""验证相关配置"""

	MIN_RANKING_LIMIT: int = 1
	MAX_RANKING_LIMIT: int = 31
	ASCENDING_ORDER: int = 1
	DESCENDING_ORDER: int = -1
	LIST_START_INDEX: int = 0
	FIRST_ELEMENT_INDEX: int = 0
	LAST_ELEMENT_INDEX: int = -1
	MIN_LIST_INDEX: int = 0
	MIN_LIST_OPERATION_ARGS: int = 2
	MIN_SET_ARGS: int = 2
	MIN_INSERT_ARGS: int = 2
	MIN_REMOVE_ARGS: int = 1
	MIN_REPLACE_ARGS: int = 2
	MIN_GET_ARGS: int = 1
	MIN_RANKING_ARGS: int = 1


@dataclass(frozen=True)
class ErrorMessages:
	"""错误消息常量"""

	CALLBACK_EXECUTION: str = "回调执行错误"
	CLOUD_VARIABLE_CALLBACK: str = "云变量变更回调执行错误"
	RANKING_CALLBACK: str = "排行榜回调执行错误"
	OPERATION_CALLBACK: str = "操作回调执行错误"
	EVENT_CALLBACK: str = "事件回调执行错误"
	SEND_MESSAGE: str = "发送消息错误"
	CONNECTION: str = "连接错误"
	WEB_SOCKET_RUN: str = "WebSocket运行错误"
	CLOSE_CONNECTION: str = "关闭连接时出错"
	GET_SERVER_TIME: str = "获取服务器时间失败"
	HANDSHAKE_DATA_PARSE: str = "握手数据解析失败"
	HANDSHAKE_PROCESSING: str = "握手处理错误"
	JSON_PARSE: str = "JSON解析错误"
	CLOUD_MESSAGE_PROCESSING: str = "云消息处理错误"
	CREATE_DATA_ITEM: str = "创建数据项时出错"
	INVALID_RANKING_DATA: str = "无效的排行榜数据格式"
	PING_SEND: str = "发送 ping 失败"
	NO_PENDING_REQUESTS: str = "收到排行榜数据但没有待处理的请求"
	INVALID_VARIABLE_TYPE: str = "云变量值必须是整数或字符串"
	INVALID_LIST_ITEM_TYPE: str = "列表元素必须是整数或字符串"
	INVALID_RANKING_ORDER: str = "排序顺序必须是1(正序)或-1(逆序)"
	INVALID_RANKING_LIMIT: str = "限制数量必须是正整数"


# ==============================
# 枚举类型定义
# ==============================
class EditorType(Enum):
	"""编辑器类型枚举"""

	NEMO = "NEMO"
	KITTEN = "KITTEN"
	KITTEN_N = "NEKO"
	COCO = "COCO"


class DataType(Enum):
	"""云数据类型枚举"""

	PRIVATE_VARIABLE = 0
	PUBLIC_VARIABLE = 1
	LIST = 2


class ReceiveMessageType(Enum):
	"""接收消息类型枚举"""

	JOIN = "connect_done"
	RECEIVE_ALL_DATA = "list_variables_done"
	UPDATE_PRIVATE_VARIABLE = "update_private_vars_done"
	RECEIVE_PRIVATE_VARIABLE_RANKING_LIST = "list_ranking_done"
	UPDATE_PUBLIC_VARIABLE = "update_vars_done"
	UPDATE_LIST = "update_lists_done"
	ILLEGAL_EVENT = "illegal_event_done"
	UPDATE_ONLINE_USER_NUMBER = "online_users_change"


class SendMessageType(Enum):
	"""发送消息类型枚举"""

	JOIN = "join"
	GET_ALL_DATA = "list_variables"
	UPDATE_PRIVATE_VARIABLE = "update_private_vars"
	GET_PRIVATE_VARIABLE_RANKING_LIST = "list_ranking"
	UPDATE_PUBLIC_VARIABLE = "update_vars"
	UPDATE_LIST = "update_lists"


# ==============================
# 数据结构定义
# ==============================
BatchGroup = namedtuple("BatchGroup", ["group_type", "group_key", "record_ids"])  # noqa: PYI024


@dataclass
class ActionConfig:
	"""操作配置 - 定义每个操作的行为"""

	key: str
	name: str
	description: str
	status: str  # 对应的状态值
	enabled: bool = True  # 是否启用该操作


@dataclass
class SourceConfigSimple:
	"""简化版数据源配置"""

	get_items: Callable[..., Any]
	get_comments: Callable[..., Any]
	delete: Callable[..., Any]
	title_key: str


@dataclass
class SourceConfig:
	"""举报源配置 - 定义每种举报类型的处理方法"""

	name: str
	# 数据获取方法
	fetch_total: Callable[..., dict]
	fetch_generator: Callable[..., Generator[dict]]
	# 处理动作方法
	handle_method: str
	# 字段映射
	content_field: str
	user_field: str
	source_id_field: str
	item_id_field: str
	source_name_field: str | None = None
	# 特殊检查
	special_check: Callable[..., bool] = field(default_factory=lambda: lambda: True)
	# 分块大小
	chunk_size: int = 100
	available_actions: list["ActionConfig"] | None = None

	def __post_init__(self) -> None:
		"""初始化后处理"""
		if self.available_actions is None:
			self.available_actions = []
		self.available_actions = cast("list[ActionConfig]", self.available_actions)


# ==============================
# 核心Union类
# ==============================
@decorator.singleton
class Union:
	"""核心联合类 - 整合所有功能模块"""

	def __init__(self) -> None:
		# API客户端
		self._client = acquire.ClientFactory().create_codemao_client()
		# 认证模块
		self._auth = auth.AuthManager()
		self._whale_routine = whale.AuthManager()
		# 社区模块
		self._community_motion = community.UserAction()
		self._community_obtain = community.DataFetcher()
		# 教育模块
		self._edu_motion = edu.UserAction()
		self._edu_obtain = edu.DataFetcher()
		# 论坛模块
		self._forum_motion = forum.ForumActionHandler()
		self._forum_obtain = forum.ForumDataFetcher()
		# 图书馆模块
		self._novel_motion = library.NovelActionHandler()
		self._novel_obtain = library.NovelDataFetcher()
		# 商店模块
		self._shop_motion = shop.WorkshopActionHandler()
		self._shop_obtain = shop.WorkshopDataFetcher()
		# 用户模块
		self._user_motion = user.UserManager()
		self._user_obtain = user.UserDataFetcher()
		# 作品模块
		self._work_motion = work.WorkManager()
		self._work_obtain = work.WorkDataFetcher()
		# 举报模块
		self._whale_motion = whale.ReportHandler()
		self._whale_obtain = whale.ReportFetcher()
		# 工具模块
		self._printer = tool.Printer()
		self._tool = tool
		self._file = file.CodeMaoFile()
		# 数据管理
		self._data = data.DataManager().data
		self._setting = data.SettingManager().data
		self._upload_history = data.HistoryManager()
		self.cache = data.CacheManager().data


ClassUnion = Union().__class__


@decorator.singleton
class Index(ClassUnion):
	"""首页展示类"""

	# 颜色配置
	COLOR_DATA = "\033[38;5;228m"
	COLOR_LINK = "\033[4;38;5;183m"
	COLOR_RESET = "\033[0m"
	COLOR_SLOGAN = "\033[38;5;80m"
	COLOR_TITLE = "\033[38;5;75m"
	COLOR_VERSION = "\033[38;5;114m"

	def _print_title(self, title: str) -> None:
		"""打印标题"""
		print(f"\n{self.COLOR_TITLE}{'*' * 22} {title} {'*' * 22}{self.COLOR_RESET}")

	def _print_slogan(self) -> None:
		"""打印标语"""
		print(f"\n{self.COLOR_SLOGAN}{self._setting.PROGRAM.SLOGAN}{self.COLOR_RESET}")
		print(f"{self.COLOR_VERSION}版本号: {self._setting.PROGRAM.VERSION}{self.COLOR_RESET}")

	def _print_lyric(self) -> None:
		"""打印歌词"""
		self._print_title("一言")
		lyric: str = self._client.send_request(endpoint="https://lty.vc/lyric", method="GET").text
		print(f"{self.COLOR_SLOGAN}{lyric}{self.COLOR_RESET}")

	def _print_announcements(self) -> None:
		"""打印公告"""
		self._print_title("公告")
		print(f"{self.COLOR_LINK}编程猫社区行为守则 https://shequ.codemao.cn/community/1619098{self.COLOR_RESET}")
		print(f"{self.COLOR_LINK}2025编程猫拜年祭活动 https://shequ.codemao.cn/community/1619855{self.COLOR_RESET}")

	def _print_user_data(self) -> None:
		"""打印用户数据"""
		self._print_title("数据")
		Tool().message_report(user_id=self._data.ACCOUNT_DATA.id)
		print(f"{self.COLOR_TITLE}{'*' * 50}{self.COLOR_RESET}\n")

	def index(self) -> None:
		"""显示首页"""
		self._print_slogan()
		# self._print_lyric()  # 暂时注释掉歌词显示
		self._print_announcements()
		self._print_user_data()


@decorator.singleton
class Tool(ClassUnion):
	"""工具类"""

	def __init__(self) -> None:
		super().__init__()
		self._cache_manager = data.CacheManager()

	def message_report(self, user_id: str) -> None:
		"""生成用户数据报告"""
		response = self._user_obtain.fetch_user_honors(user_id=user_id)
		timestamp = self._community_obtain.fetch_current_timestamp_10()["data"]
		user_data = {
			"user_id": response["user_id"],
			"nickname": response["nickname"],
			"level": response["author_level"],
			"fans": response["fans_total"],
			"collected": response["collected_total"],
			"liked": response["liked_total"],
			"view": response["view_times"],
			"timestamp": timestamp,
		}
		# 如果有缓存数据,进行对比分析
		if self._cache_manager.data:
			self._tool.DataAnalyzer().compare_datasets(
				before=self._cache_manager.data,
				after=user_data,
				metrics={
					"fans": "粉丝",
					"collected": "被收藏",
					"liked": "被赞",
					"view": "被预览",
				},
				timestamp_field="timestamp",
			)
		# 更新缓存
		self._cache_manager.update(user_data)
