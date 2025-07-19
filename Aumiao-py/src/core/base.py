from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Literal, TypedDict

# 常量定义
DOWNLOAD_DIR: Path = Path.cwd() / "download"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
VALID_REPLY_TYPES = {"WORK_COMMENT", "WORK_REPLY", "WORK_REPLY_REPLY", "POST_COMMENT", "POST_REPLY", "POST_REPLY_REPLY"}
REPORT_BATCH_THRESHOLD = 15


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


@dataclass
class SourceConfig:
	get_items: Callable[..., Any]
	get_comments: Callable[..., Any]
	delete: Callable[..., Any]
	title_key: str


class ReportRecord(TypedDict):
	item: dict
	report_type: Literal["comment", "post", "discussion"]
	com_id: str
	content: str
	processed: bool
	action: str | None
