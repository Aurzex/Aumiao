"""基础定义和核心Union类"""

from collections import namedtuple
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal, TypedDict

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
	item: data.NestedDefaultDict
	report_type: Literal["comment", "post", "discussion"]
	item_id: str
	content: str
	processed: bool
	action: str | None


BatchGroup = namedtuple("BatchGroup", ["group_type", "group_key", "record_ids"])  # noqa: PYI024


@dataclass
class SourceConfig:
	get_items: Callable[..., Any]
	get_comments: Callable[..., Any]
	delete: Callable[..., Any]
	title_key: str


# 核心Union类
@decorator.singleton
class Union:
	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()
		self.cache = data.CacheManager().data
		self._community_login = community.AuthManager()
		self._community_motion = community.UserAction()
		self._community_obtain = community.DataFetcher()
		self._data = data.DataManager().data
		self._edu_motion = edu.UserAction()
		self._edu_obtain = edu.DataFetcher()
		self._file = file.CodeMaoFile()
		self._forum_motion = forum.ForumActionHandler()
		self._forum_obtain = forum.ForumDataFetcher()
		self._novel_obtain = library.NovelDataFetcher()
		self._novel_motion = library.NovelActionHandler()
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


ClassUnion = Union().__class__
