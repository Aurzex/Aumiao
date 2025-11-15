"""基础定义和核心Union类"""

from collections import namedtuple
from collections.abc import Callable, Generator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, TypedDict, cast

from src.api import community, edu, forum, library, shop, user, whale, work
from src.utils import acquire, data, decorator, file, tool

# 常量定义
MAX_SIZE_BYTES: int = 15 * 1024 * 1024
REPORT_BATCH_THRESHOLD: int = 15
VALID_REPLY_TYPES: set[str] = {"WORK_COMMENT", "WORK_REPLY", "WORK_REPLY_REPLY", "POST_COMMENT", "POST_REPLY", "POST_REPLY_REPLY"}


# 类型定义
class FormattedAnswer(TypedDict):
	question: str
	responses: list[str] | str


class ReplyType(Enum):
	WORK_COMMENT = "WORK_COMMENT"
	WORK_REPLY = "WORK_REPLY"
	WORK_REPLY_REPLY = "WORK_REPLY_REPLY"
	POST_COMMENT = "POST_COMMENT"
	POST_REPLY = "POST_REPLY"
	POST_REPLY_REPLY = "POST_REPLY_REPLY"


class ReportRecord(TypedDict):
	item: "data.NestedDefaultDict"
	report_type: Literal["comment", "post", "discussion"]
	item_id: str
	content: str
	processed: bool
	action: str | None


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
		if self.available_actions is None:
			self.available_actions = []
		self.available_actions = cast("list[ActionConfig]", self.available_actions)


# 核心Union类
@decorator.singleton
class Union:
	def __init__(self) -> None:
		self._client = acquire.ClientFactory().create_codemao_client()
		self._community_login = community.AuthManager()
		self._community_motion = community.UserAction()
		self._community_obtain = community.DataFetcher()
		self._data = data.DataManager().data
		self._edu_motion = edu.UserAction()
		self._edu_obtain = edu.DataFetcher()
		self._file = file.CodeMaoFile()
		self._forum_motion = forum.ForumActionHandler()
		self._forum_obtain = forum.ForumDataFetcher()
		self._novel_motion = library.NovelActionHandler()
		self._novel_obtain = library.NovelDataFetcher()
		self._printer = tool.Printer()
		self._setting = data.SettingManager().data
		self._shop_motion = shop.WorkshopActionHandler()
		self._shop_obtain = shop.WorkshopDataFetcher()
		self._tool = tool
		self._upload_history = data.HistoryManger()
		self._user_motion = user.UserManager()
		self._user_obtain = user.UserDataFetcher()
		self._whale_motion = whale.ReportHandler()
		self._whale_obtain = whale.ReportFetcher()
		self._whale_routine = whale.AuthManager()
		self._work_motion = work.WorkManager()
		self._work_obtain = work.WorkDataFetcher()
		self.cache = data.CacheManager().data


ClassUnion = Union().__class__


@decorator.singleton
class Index(ClassUnion):
	COLOR_DATA = "\033[38;5;228m"
	COLOR_LINK = "\033[4;38;5;183m"
	COLOR_RESET = "\033[0m"
	COLOR_SLOGAN = "\033[38;5;80m"
	COLOR_TITLE = "\033[38;5;75m"
	COLOR_VERSION = "\033[38;5;114m"

	def _print_title(self, title: str) -> None:
		print(f"\n{self.COLOR_TITLE}{'*' * 22} {title} {'*' * 22}{self.COLOR_RESET}")

	def _print_slogan(self) -> None:
		print(f"\n{self.COLOR_SLOGAN}{self._setting.PROGRAM.SLOGAN}{self.COLOR_RESET}")
		print(f"{self.COLOR_VERSION}版本号: {self._setting.PROGRAM.VERSION}{self.COLOR_RESET}")

	def _print_lyric(self) -> None:
		self._print_title("一言")
		lyric: str = self._client.send_request(endpoint="https://lty.vc/lyric", method="GET").text
		print(f"{self.COLOR_SLOGAN}{lyric}{self.COLOR_RESET}")

	def _print_announcements(self) -> None:
		self._print_title("公告")
		print(f"{self.COLOR_LINK}编程猫社区行为守则 https://shequ.codemao.cn/community/1619098{self.COLOR_RESET}")
		print(f"{self.COLOR_LINK}2025编程猫拜年祭活动 https://shequ.codemao.cn/community/1619855{self.COLOR_RESET}")

	def _print_user_data(self) -> None:
		self._print_title("数据")
		Tool().message_report(user_id=self._data.ACCOUNT_DATA.id)
		print(f"{self.COLOR_TITLE}{'*' * 50}{self.COLOR_RESET}\n")

	def index(self) -> None:
		self._print_slogan()
		# self._print_lyric()
		self._print_announcements()
		self._print_user_data()


@decorator.singleton
class Tool(ClassUnion):
	def __init__(self) -> None:
		super().__init__()
		self._cache_manager = data.CacheManager()

	def message_report(self, user_id: str) -> None:
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
		self._cache_manager.update(user_data)
