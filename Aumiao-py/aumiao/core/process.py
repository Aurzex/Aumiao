from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable, Generator
from json import JSONDecodeError, loads
from pathlib import Path
from random import choice, randint
from time import sleep
from typing import Any, ClassVar, Literal, Protocol, cast
from urllib.parse import urlparse

from aumiao.core.base import NestedDefaultDict, coordinator
from aumiao.core.models import (
	MAX_SIZE_BYTES,
	ActionConfig,
	BatchGroup,
	ProcessingContext,
	ProcessingError,
	ReportRecord,
	SourceConfig,
	SourceType,
)
from aumiao.core.retrieve import Obtain
from aumiao.utils.acquire import FileUploader, HTTPStatus
from aumiao.utils.data import UploadHistory
from aumiao.utils.decorator import singleton


# ========================== 抽象基类或协议 ==========================
class ProcessStrategy[T: Literal["duplicates", "ads", "blacklist"]](ABC):
	"""处理策略抽象基类"""

	@abstractmethod
	def process(
		self,
		comments: list[dict[str, Any]],
		item_id: int,
		title: str,
		params: dict[T, Any],
		target_lists: defaultdict[str, list[str]],
		source_type: SourceType = "shop",
	) -> None:
		"""处理评论的核心方法"""


class ProcessorProtocol(Protocol):
	"""处理器协议接口"""

	def process(self, context: ProcessingContext) -> None: ...


class BaseProcessor(ABC):
	"""处理器基类"""

	def __init__(self, next_processor: ProcessorProtocol | None = None) -> None:
		self.next_processor = next_processor

	def process(self, context: ProcessingContext) -> None:
		"""执行处理并传递给下一个处理器"""
		try:
			self._process(context)
		except ProcessingError as e:
			context.errors.append(f"{self.__class__.__name__}: {e!s}")
			raise
		except Exception as e:
			context.errors.append(f"{self.__class__.__name__}: 未预期错误: {e!s}")
			msg = f"处理器 {self.__class__.__name__} 执行失败"
			raise ProcessingError(msg) from e
		if self.next_processor and not context.processed:
			self.next_processor.process(context)

	@abstractmethod
	def _process(self, context: ProcessingContext) -> None:
		"""子类实现的处理逻辑"""


class FileUploaderProtocol(Protocol):
	"""定义上传器的协议接口"""

	@staticmethod
	def upload(file_path: Path, method: Literal["pgaot", "codemao", "codegame"], save_path: str) -> str: ...


# ========================== 策略模式实现 ==========================
class AbnormalProcessStrategy(ProcessStrategy, ABC):
	"""异常处理策略基类 (模板方法模式)"""

	@abstractmethod
	def _check_condition(self, data: dict[str, Any], params: dict[str, Any]) -> bool:
		"""抽象方法: 检查内容是否符合处理条件"""

	@abstractmethod
	def _format_log_message(self, data: dict[str, Any], log_type: str, source_type: str, title: str, parent_info: str) -> str:
		"""抽象方法: 格式化日志消息"""

	def process(
		self,
		comments: list[dict[str, Any]],
		item_id: int,
		title: str,
		params: dict[str, Any],
		target_lists: defaultdict[str, list[str]],
		source_type: SourceType = "shop",
	) -> None:
		"""处理异常评论的通用流程 (模板方法)"""
		action_type = self._get_action_type()
		for comment in comments:
			# 跳过置顶评论
			if comment.get("is_top"):
				continue
			# 检查主评论
			if self._check_condition(comment, params):
				identifier = f"{source_type}:{item_id}:comment:0:{comment['id']}"
				self._log_and_add(
					target_lists=target_lists,
					data=comment,
					identifier=identifier,
					title=title,
					action_type=action_type,
					source_type=source_type,
				)
			# 检查回复
			for reply in comment.get("replies", []):
				if self._check_condition(reply, params):
					identifier = f"{source_type}:{item_id}:reply:{comment['id']}:{reply['id']}"
					self._log_and_add(
						target_lists=target_lists,
						data=reply,
						identifier=identifier,
						title=title,
						action_type=action_type,
						source_type=source_type,
						parent_content=comment.get("content", ""),
					)

	@abstractmethod
	def _get_action_type(self) -> str:
		"""获取动作类型"""

	def _log_and_add(
		self,
		target_lists: defaultdict[str, list[str]],
		data: dict[str, Any],
		identifier: str,
		title: str,
		action_type: str,
		source_type: SourceType,
		parent_content: str = "",
	) -> None:
		"""记录日志并添加标识到目标列表 (模板方法的钩子)"""
		# 区分评论 / 回复类型
		log_type = "回复" if ":reply:" in identifier else "评论"
		parent_info = f"(父内容: {parent_content[:20]}...)" if parent_content else ""
		# 生成日志信息
		log_message = self._format_log_message(data=data, log_type=log_type, source_type=source_type.upper(), title=title[:10] if title else "", parent_info=parent_info)
		print(log_message)
		# 添加到目标列表
		target_lists[action_type].append(identifier)


@singleton
class AdsProcessStrategy(AbnormalProcessStrategy):
	"""广告处理策略"""

	def _get_action_type(self) -> str:  # noqa: PLR6301
		return "ads"

	def _check_condition(self, data: dict[str, Any], params: dict[str, Any]) -> bool:  # noqa: PLR6301
		"""检查内容是否符合广告条件"""
		content = data.get("content", "").lower()
		ad_keywords = params.get("ads", [])
		return any(ad in content for ad in ad_keywords)

	def _format_log_message(self, data: dict[str, Any], log_type: str, source_type: str, title: str, parent_info: str) -> str:  # noqa: PLR6301
		"""格式化广告日志消息"""
		title_part = f"[{title}]" if title else ""
		return f"广告 {log_type} [{source_type}]{title_part}{parent_info} : {data.get('content', '')[:50]}"


@singleton
class BlacklistProcessStrategy(AbnormalProcessStrategy):
	"""黑名单处理策略"""

	def _get_action_type(self) -> str:  # noqa: PLR6301
		return "blacklist"

	def _check_condition(self, data: dict[str, Any], params: dict[str, Any]) -> bool:  # noqa: PLR6301
		"""检查用户是否在黑名单中"""
		user_id = str(data.get("user_id", ""))
		blacklist_set = params.get("blacklist", set())
		if isinstance(blacklist_set, list):
			blacklist_set = set(blacklist_set)
		return user_id in blacklist_set

	def _format_log_message(self, data: dict[str, Any], log_type: str, source_type: str, title: str, parent_info: str) -> str:  # noqa: PLR6301
		"""格式化黑名单日志消息"""
		title_part = f"[{title}]" if title else ""
		return f"黑名单 {log_type} [{source_type}]{title_part}{parent_info} : {data.get('nickname', ' 未知用户 ')}"


@singleton
class DuplicatesProcessStrategy(ProcessStrategy):
	"""重复评论处理策略"""

	def process(
		self,
		comments: list[dict[str, Any]],
		item_id: int,
		title: str,  # noqa: ARG002
		params: dict[Literal["duplicates"], Any],
		target_lists: defaultdict[str, list[str]],
		source_type: SourceType = "shop",
	) -> None:
		"""处理重复刷屏评论"""
		content_map: defaultdict[tuple, list[str]] = defaultdict(list)
		# 追踪所有评论和回复
		for comment in comments:
			self._track_comment(comment, item_id, content_map, source_type, is_reply=False)
			for reply in comment.get("replies", []):
				self._track_comment(reply, item_id, content_map, source_type, is_reply=True)
		# 筛选出超过阈值的重复内容
		for (user_id, content), identifiers in content_map.items():
			if len(identifiers) >= params["duplicates"]:
				print(f"用户 {user_id} 刷屏评论: {content[:50]}... - 出现 {len(identifiers)} 次")
				target_lists["duplicates"].extend(identifiers)

	@staticmethod
	def _track_comment(data: dict[str, Any], item_id: int, content_map: defaultdict[tuple, list[str]], source_type: SourceType, *, is_reply: bool = False) -> None:
		"""追踪评论内容用于重复检测"""
		content_key = (data.get("user_id"), data.get("content", "").lower())
		if is_reply:
			parent_id = data.get("parent_id", 0) or 0
			identifier = f"{source_type}:{item_id}:reply:{parent_id}:{data.get('id')}"
		else:
			identifier = f"{source_type}:{item_id}:comment:0:{data.get('id')}"
		content_map[content_key].append(identifier)


@singleton
class ProcessStrategyFactory:
	"""处理策略工厂"""

	def __init__(self) -> None:
		self._strategies: dict[str, ProcessStrategy] = {}
		self._register_default_strategies()

	def _register_default_strategies(self) -> None:
		"""注册默认策略"""
		self.register_strategy("ads", AdsProcessStrategy())
		self.register_strategy("blacklist", BlacklistProcessStrategy())
		self.register_strategy("duplicates", DuplicatesProcessStrategy())

	def register_strategy(self, action_type: str, strategy: ProcessStrategy) -> None:
		"""注册处理策略"""
		self._strategies[action_type] = strategy

	def get_strategy(self, action_type: Literal["ads", "blacklist", "duplicates"]) -> ProcessStrategy:
		"""获取处理策略"""
		strategy = self._strategies.get(action_type)
		if not strategy:
			msg = f"未支持的处理类型: {action_type}"
			raise NotImplementedError(msg)
		return strategy

	def get_all_strategy_types(self) -> list[str]:
		"""获取所有支持的处理类型"""
		return list(self._strategies.keys())


# ========================== 管道模式实现 ==========================
@singleton
class OfficialCheckProcessor(BaseProcessor):
	"""官方账号检查处理器"""

	OFFICIAL_IDS: ClassVar = {128963, 629055, 203577, 859722, 148883, 2191000, 7492052, 387963, 3649031}

	def _process(self, context: ProcessingContext) -> None:
		"""检查是否为官方账号"""
		config = context.config
		item_ndd = context.record["item"]
		user_id_str = item_ndd[f"{config.user_id_field}"]
		# 尝试获取用户 ID
		if user_id_str != "UNKNOWN" and user_id_str.isdigit():
			user_id = int(user_id_str)
			context.user_id = user_id
			# 检查是否为官方账号
			if user_id in self.OFFICIAL_IDS:
				context.messages.append("这是一条官方发布的内容, 自动通过")
				context.action = "P"
				context.processed = True
				# 应用动作到记录
				record = context.record
				record["processed"] = True
				record["action"] = "P"
				# 获取状态映射
				status_map = {
					"D": "DELETE",
					"S": "MUTE_SEVEN_DAYS",
					"T": "MUTE_THREE_MONTHS",
					"U": "UNLOAD",
					"P": "PASS",
				}
				# 这里需要实际执行动作
				try:
					handle_method = getattr(coordinator.whale_motion, config.handle_method)
					handle_method(report_id=record["item"]["id"], resolution=status_map["P"], admin_id=context.admin_id)
					context.messages.append("已自动通过官方内容")
				except AttributeError:
					# 如果找不到 _whale_motion, 记录警告
					context.messages.append("警告: 无法执行官方内容自动通过操作")


@singleton
class DetailDisplayProcessor(BaseProcessor):
	"""完整详情显示处理器 - 根据举报类型显示特定信息"""

	def __init__(self, next_processor: ProcessorProtocol | None = None) -> None:
		super().__init__(next_processor)

	def _process(self, context: ProcessingContext) -> None:
		"""根据举报类型显示特定信息"""
		item_ndd = context.record["item"]
		report_type = context.report_type
		config = context.config
		# 显示处理头信息
		if context.is_batch_mode:
			coordinator.printer.print_header(f"=== 批量处理 {config.name} ===")
		elif context.is_reprocess_mode:
			coordinator.printer.print_header(f"=== 重新处理 {config.name} ===")
		else:
			coordinator.printer.print_header(f"=== 处理 {config.name} ===")
		# 根据举报类型调用不同的显示方法
		display_methods = {
			"work_work": self._display_work_report,
			"shop_comment": self._display_comment_report,
			"forum_post": self._display_forum_report,
			"forum_discussion": self._display_discussion_report,
		}
		display_method = display_methods.get(report_type, self._display_generic_report)
		display_method(item_ndd, config)

	@staticmethod
	def _display_work_report(item_ndd: "NestedDefaultDict", config: SourceConfig) -> None:
		"""显示作品举报详情"""
		coordinator.printer.print_header("=== 作品举报详情 ===")
		base_url = "https://shequ.codemao.cn"
		# 1. 作者信息
		author_nickname = item_ndd[config.user_nickname_field]
		author_id = item_ndd[config.user_id_field]
		coordinator.printer.print_message(f"作者昵称: {author_nickname}", "INFO")
		author_url = f"{base_url}/user/{author_id}"
		coordinator.printer.print_message(f"作者链接: {author_url}", "INFO")
		# 2. 作品信息
		work_id = item_ndd[config.source_id_field]
		work_url = f"{base_url}/work/{work_id}"
		coordinator.printer.print_message(f"作品链接: {work_url}", "INFO")
		if config.work_type_field and config.work_type_field in item_ndd:
			work_type = item_ndd[config.work_type_field]
			coordinator.printer.print_message(f"作品类型: {work_type}", "INFO")
		# 3. 举报信息
		reason_content = item_ndd[config.reason_field]
		coordinator.printer.print_message(f"举报原因: {reason_content}", "INFO")
		description = item_ndd[config.description_field]
		coordinator.printer.print_message(f"举报线索: {description}", "INFO")
		# 4. 时间信息
		created_at = item_ndd[config.created_at_field]
		created_at_str = coordinator.toolkit.create_time_utils().format_timestamp(created_at)
		coordinator.printer.print_message(f"举报时间: {created_at_str}", "INFO")

	@staticmethod
	def _display_comment_report(item_ndd: "NestedDefaultDict", config: SourceConfig) -> None:
		"""显示评论举报详情"""
		coordinator.printer.print_header("=== 评论举报详情 ===")
		base_url = "https://shequ.codemao.cn"
		# 1. 被举报内容
		content = item_ndd[config.content_field]
		content_text = coordinator.toolkit.create_data_converter().html_to_text(content)
		coordinator.printer.print_message(f"举报内容: {content_text}", "SUCCESS")
		# 2. 被举报人信息
		user_nickname = item_ndd[config.user_nickname_field]
		user_id = item_ndd[config.user_id_field]
		coordinator.printer.print_message(f"被举报人昵称: {user_nickname}", "INFO")
		user_url = f"{base_url}/user/{user_id}"
		coordinator.printer.print_message(f"被举报人链接: {user_url}", "INFO")
		# 3. 来源信息(工作室)
		studio_name = item_ndd[config.source_name_field]
		studio_id = item_ndd[config.source_id_field]
		coordinator.printer.print_message(f"工作室名称: {studio_name}", "INFO")
		studio_url = f"{base_url}/work_shop/{studio_id}"
		coordinator.printer.print_message(f"工作室链接: {studio_url}", "INFO")
		# 4. 举报信息
		reason_content = item_ndd[config.reason_field]
		coordinator.printer.print_message(f"举报原因: {reason_content}", "INFO")
		# 5. 时间信息
		created_at = item_ndd[config.created_at_field]
		created_at_str = coordinator.toolkit.create_time_utils().format_timestamp(created_at)
		coordinator.printer.print_message(f"举报时间: {created_at_str}", "INFO")

	@staticmethod
	def _display_forum_report(item_ndd: "NestedDefaultDict", config: SourceConfig) -> None:
		"""显示论坛帖子举报详情"""
		coordinator.printer.print_header("=== 论坛帖子举报详情 ===")
		base_url = "https://shequ.codemao.cn"
		# 1. 作者信息
		author_nickname = item_ndd[config.user_nickname_field]
		author_id = item_ndd[config.user_id_field]
		coordinator.printer.print_message(f"帖子作者: {author_nickname}", "INFO")
		author_url = f"{base_url}/user/{author_id}"
		coordinator.printer.print_message(f"作者链接: {author_url}", "INFO")
		# 2. 帖子信息
		post_id_value = item_ndd[config.source_id_field]
		post_id = None
		try:
			post_id = int(post_id_value)
		except (ValueError, TypeError):
			post_id = None
		if post_id:
			post_url = f"{base_url}/community/{post_id}"
			coordinator.printer.print_message(f"帖子链接: {post_url}", "INFO")
			# 获取并显示帖子详情
			try:
				details = coordinator.forum_obtain.fetch_single_post_details(post_id=post_id)
				details_ndd = coordinator.nested_defaultdict.__class__(details)
				if config.title_field and config.title_field in item_ndd:
					title = item_ndd[config.title_field]
					coordinator.printer.print_message(f"标题: {title}", "SUCCESS")
				if "content" in details_ndd:
					content_text = coordinator.toolkit.create_data_converter().html_to_text(details_ndd["content"])
					if len(content_text) > 200:
						content_text = content_text[:200] + "..."
					coordinator.printer.print_message(f"内容: {content_text}", "SUCCESS")
				else:
					coordinator.printer.print_message("内容: 无法获取帖子内容", "WARNING")
			except Exception as e:
				coordinator.printer.print_message(f"获取帖子详情失败: {e!s}", "ERROR")
		else:
			coordinator.printer.print_message("帖子 ID: 未知", "WARNING")
		# 3. 举报信息
		reason_content = item_ndd[config.reason_field]
		coordinator.printer.print_message(f"举报原因: {reason_content}", "INFO")
		description = item_ndd[config.description_field]
		coordinator.printer.print_message(f"举报线索: {description}", "INFO")
		# 4. 时间信息
		created_at = item_ndd[config.created_at_field]
		created_at_str = coordinator.toolkit.create_time_utils().format_timestamp(created_at)
		coordinator.printer.print_message(f"举报时间: {created_at_str}", "INFO")

	@staticmethod
	def _display_discussion_report(item_ndd: "NestedDefaultDict", config: SourceConfig) -> None:
		"""显示讨论举报详情"""
		coordinator.printer.print_header("=== 讨论举报详情 ===")
		base_url = "https://shequ.codemao.cn"
		# 1. 被举报内容
		content = item_ndd[config.content_field]
		content_text = coordinator.toolkit.create_data_converter().html_to_text(content)
		coordinator.printer.print_message(f"被举报内容: {content_text}", "SUCCESS")
		# 2. 被举报人信息
		user_nickname = item_ndd[config.user_nickname_field]
		user_id = item_ndd[config.user_id_field]
		coordinator.printer.print_message(f"被举报人昵称: {user_nickname}", "INFO")
		user_url = f"{base_url}/user/{user_id}"
		coordinator.printer.print_message(f"被举报人链接: {user_url}", "INFO")
		# 3. 帖子信息
		post_id = item_ndd["post_id"]
		if post_id == "UNKNOWN":
			post_id = item_ndd[config.source_id_field]
		post_url = f"{base_url}/community/{post_id}"
		coordinator.printer.print_message(f"帖子链接: {post_url}", "INFO")
		if config.title_field and config.title_field in item_ndd:
			title = item_ndd[config.title_field]
			coordinator.printer.print_message(f"帖子标题: {title}", "INFO")
		# 4. 分区信息
		if config.board_name_field and config.board_name_field in item_ndd:
			board_name = item_ndd[config.board_name_field]
			coordinator.printer.print_message(f"分区: {board_name}", "INFO")
		# 5. 举报信息
		reason_content = item_ndd[config.reason_field]
		coordinator.printer.print_message(f"举报原因: {reason_content}", "INFO")
		# 6. 时间信息
		created_at = item_ndd[config.created_at_field]
		created_at_str = coordinator.toolkit.create_time_utils().format_timestamp(created_at)
		coordinator.printer.print_message(f"举报时间: {created_at_str}", "INFO")

	@staticmethod
	def _display_generic_report(item_ndd: "NestedDefaultDict", config: SourceConfig) -> None:
		"""显示通用举报详情"""
		coordinator.printer.print_header(f"=== {config.name} 详情 ===")
		# 重新组织字段显示顺序,按逻辑分组
		# 1. 内容相关字段
		content_fields = [(config.content_field, "内容"), (config.description_field, "举报描述")]
		# 2. 用户相关字段
		user_fields = [(config.user_nickname_field, "用户昵称"), (config.user_id_field, "用户 ID")]
		# 3. 举报信息
		report_fields = [(config.reason_field, "举报原因")]
		# 4. 时间信息
		time_fields = [(config.created_at_field, "举报时间")]
		# 分组显示
		for label, fields in [("内容信息", content_fields), ("用户信息", user_fields), ("举报信息", report_fields), ("时间信息", time_fields)]:
			has_data = False
			for field_key, field_label in fields:
				if field_key and field_key in item_ndd:
					value = item_ndd[field_key]
					if not has_data:
						coordinator.printer.print_message(f"【{label}】", "INFO")
						has_data = True
					# 特殊处理时间字段
					if field_key == config.created_at_field:
						value = coordinator.toolkit.create_time_utils().format_timestamp(value)
					coordinator.printer.print_message(f"{field_label}: {value}", "INFO")


@singleton
class ActionSelectionProcessor(BaseProcessor):
	"""动作选择处理器"""

	SOURCE_TYPE_MAP: dict[Literal["shop_comment", "forum_post", "forum_discussion"], Literal["shop", "forum"]] = {  # noqa: RUF012
		"shop_comment": "shop",
		"forum_post": "forum",
		"forum_discussion": "forum",
	}

	def __init__(self, fetcher: Any, next_processor: ProcessorProtocol | None = None) -> None:
		super().__init__(next_processor)
		self.fetcher = fetcher

	def _process(self, context: ProcessingContext) -> None:
		"""处理动作选择和执行"""
		_record = context.record
		_admin_id = context.admin_id
		report_type = context.report_type
		# 获取可用操作 (去掉 C 选项)
		available_actions = self.fetcher.registry.get_available_actions(report_type)
		action_keys = [action.key for action in available_actions if action.key != "C"]
		# 操作选择循环
		while not context.processed:
			prompt = self.fetcher.registry.get_action_prompt(report_type)
			choice = coordinator.printer.get_valid_input(
				prompt=prompt,
				valid_options=set(action_keys),
			).upper()
			# 处理状态变更操作
			if choice in {"D", "S", "T", "P"}:
				context.action = choice
				self._apply_action(context)
				context.processed = True
				break
			# 处理辅助操作 (去掉 C 选项)
			if choice == "F":
				config = context.config
				item_ndd = context.record["item"]
				if config.special_check:
					try:
						result = config.special_check(item_ndd)
						if result:
							self._check_violation(context)
							# 检查完成后, 显示完成信息并继续等待用户选择
							coordinator.printer.print_message("违规检查完成, 请选择处理动作", "INFO")
							continue
						coordinator.printer.print_message("该类型不支持检查违规操作", "ERROR")
						continue
					except Exception as e:
						coordinator.printer.print_message(f"违规检查出错: {e}", "ERROR")
						continue
				else:
					print("配置中没有 special_check 或不可调用")
					coordinator.printer.print_message("该类型不支持检查违规操作", "ERROR")
					continue
			if choice == "J":
				context.skip_reason = "用户选择跳过"
				coordinator.printer.print_message("已跳过该举报", "INFO")
				# 对于跳过, 我们设置 processed 为 True, 但记录跳过原因
				context.processed = True
				break

	def _check_violation(self, context: ProcessingContext) -> None:
		"""检查举报内容违规"""
		item_ndd = context.record["item"]
		config = context.config
		source_id = item_ndd[config.source_id_field]
		board_name = item_ndd["board_name"]
		user_id = item_ndd[f"{config.user_id_field}"]
		coordinator.printer.print_header("=== 开始检查违规 ===")
		# 调整来源类型
		adjusted_source_type: Literal["shop", "forum"] = self.SOURCE_TYPE_MAP.get(context.report_type, context.report_type)  # type: ignore  # noqa: PGH003
		processor = ReportProcessor()
		try:
			processor.check_violation(
				source_id=source_id,
				source_type=adjusted_source_type,
				board_name=board_name,
				user_id=user_id if user_id != "UNKNOWN" else None,
			)
			coordinator.printer.print_message("违规检查完成", "SUCCESS")
		except Exception as e:
			coordinator.printer.print_message(f"违规检查失败: {e!s}", "ERROR")
		coordinator.printer.print_header("=== 检查结束 ===")

	def _apply_action(self, context: ProcessingContext) -> None:
		"""应用处理动作"""
		record = context.record
		action = context.action
		if not action:
			return
		config = self.fetcher.registry.get_config(record["report_type"])
		# 检查动作是否可用
		if not self.fetcher.registry.is_action_available(record["report_type"], action):
			coordinator.printer.print_message(f"动作 {action} 对类型 {record['report_type']} 不可用", "ERROR")
			return
		# 获取状态映射
		status_map = self.fetcher.registry.get_status_mapping()
		# 执行处理动作
		try:
			handle_method = getattr(coordinator.whale_motion, config.handle_method)
			handle_method(report_id=record["item"]["id"], resolution=status_map[action], admin_id=context.admin_id)
			# 更新记录状态
			record["processed"] = True
			record["action"] = action
			# 获取动作名称显示
			action_config = next(
				(ac for ac in config.available_actions if ac.key == action),
				None,
			)
			action_name = action_config.name if action_config else action
			coordinator.printer.print_message(f"已应用操作: {action_name}", "SUCCESS")
		except AttributeError:
			coordinator.printer.print_message("警告: 无法执行处理动作", "ERROR")


class ProcessingPipeline:
	"""处理管道 - 组织和执行处理器链"""

	def __init__(self, *processors: ProcessorProtocol) -> None:
		self.processors = list(processors)

	def add_processor(self, processor: ProcessorProtocol) -> None:
		"""添加处理器到管道"""
		self.processors.append(processor)

	def execute(self, context: ProcessingContext) -> ProcessingContext:
		"""执行整个处理管道"""
		try:
			for processor in self.processors:
				if context.processed or context.skip_reason:
					break
				processor.process(context)
		except ProcessingError as e:
			if not context.errors:
				context.errors.append(str(e))
		return context

	@classmethod
	def create_default_pipeline(cls, fetcher: Any) -> "ProcessingPipeline":
		"""创建默认处理管道"""
		# 创建处理器链: official -> detail -> action
		action_processor = ActionSelectionProcessor(fetcher)  # 注意: 这里不需要传入 printer
		detail_processor = DetailDisplayProcessor(action_processor)
		official_processor = OfficialCheckProcessor(detail_processor)
		# 创建管道并添加所有处理器
		return cls(official_processor, detail_processor, action_processor)


class ProcessorFactory:
	"""处理器工厂 - 统一管理处理器的创建"""

	@staticmethod
	def create_processing_pipeline(fetcher: Any) -> ProcessingPipeline:
		"""创建处理管道"""
		return ProcessingPipeline.create_default_pipeline(fetcher)


# ========================== 核心功能类 ==========================
@singleton
class CommentProcessor:
	"""评论处理器 - 使用策略模式优化"""

	def __init__(self) -> None:
		self._strategy_factory = ProcessStrategyFactory()

	def process_item(
		self,
		item: dict[str, Any],
		config: ...,
		action_type: Literal["duplicates", "ads", "blacklist"],
		params: dict[Literal["ads", "blacklist", "duplicates"], Any],
		target_lists: defaultdict[str, list[str]],
		source_type: SourceType = "shop",
	) -> None:
		"""处理项目主入口, 根据 action_type 分发到对应处理策略"""
		item_id = int(item["id"])
		comments = config.get_comments(self, item_id)
		title = item.get(config.title_key, "")
		# 获取处理策略并执行
		strategy = self._strategy_factory.get_strategy(action_type)
		strategy.process(
			comments=comments,
			item_id=item_id,
			title=title,
			params=params,
			target_lists=target_lists,
			source_type=source_type,  # 直接传递源类型
		)

	def register_strategy(self, action_type: str, strategy: ProcessStrategy) -> None:
		"""注册自定义处理策略"""
		self._strategy_factory.register_strategy(action_type, strategy)

	def get_all_strategy_types(self) -> list[str]:
		"""获取所有支持的处理类型"""
		return self._strategy_factory.get_all_strategy_types()


@singleton
class ViolationChecker:
	"""违规检查器"""

	def __init__(self) -> None:
		self.comment_processor = CommentProcessor()

	def check_violation(self, source_id: Any, source_type: Literal["shop", "forum", "work"], board_name: str, user_id: int | None) -> None:
		"""检查举报内容违规"""
		coordinator.printer.print_message(f"检查违规: source_id={source_id}, type={source_type}, board={board_name}, user={user_id}", "INFO")
		source_id = int(source_id) if source_id != "UNKNOWN" and str(source_id).isdigit() else 0
		if not source_id:
			coordinator.printer.print_message("无效的来源 ID, 无法检查违规", "ERROR")
			return
		# 直接使用传入的 source_type
		violations = self._analyze_comment_violations(
			source_id=source_id,
			source_type=source_type,  # 使用统一的源类型
			board_name=board_name,
		)
		spam_posts = []
		if source_type == "forum" and user_id:
			spam_posts = self._check_spam_posts(user_id, board_name)
			violations.extend(spam_posts)
		if not violations and not spam_posts:
			coordinator.printer.print_message("未检测到违规评论或刷屏帖子", "INFO")
			return
		# 执行自动举报
		self._process_auto_report(violations=violations, source_type=source_type)

	def _analyze_comment_violations(
		self,
		source_id: int,
		source_type: Literal["forum", "work", "shop"],  # 使用统一的源类型
		board_name: str,
	) -> list[str]:
		"""分析评论违规内容: 广告、黑名单、重复评论"""
		try:
			total = Obtain().get_comment_total(source_id=source_id, source_type=source_type)
			print(f"当前处理项共有 {total} 个评论")
			limit = int(input("输入要获取的评论数: "))
			comments = Obtain().get_comments(
				source_id=source_id,
				source=source_type,
				method="comments",
				limit=limit,
			)
			# 2. 违规检查参数
			check_params: dict[Literal["ads", "blacklist", "duplicates"], list[str] | int] = {
				"ads": coordinator.data_manager.data.USER_DATA.ads,
				"blacklist": coordinator.data_manager.data.USER_DATA.black_room,
				"duplicates": coordinator.setting_manager.data.PARAMETER.spam_del_max,
			}

			class CommentCheckConfig:
				# 3. 调用评论处理器分析违规
				title_key = "title"

				@staticmethod
				def get_comments(_processor: Callable, _item_id: int) -> list[dict]:
					return comments

			config = CommentCheckConfig()
			violation_targets: defaultdict[str, list[str]] = defaultdict(list)
			# 检查广告、黑名单、重复评论
			for check_type in ["ads", "blacklist", "duplicates"]:
				check_type = cast("Literal ['ads', 'blacklist', 'duplicates']", check_type)
				self.comment_processor.process_item(
					item={"id": source_id, "title": board_name},
					config=config,
					action_type=check_type,
					params=check_params,
					target_lists=violation_targets,
					source_type=source_type,  # 传递统一的源类型
				)
			# 合并所有违规内容
			return list(set(violation_targets["ads"] + violation_targets["blacklist"] + violation_targets["duplicates"]))
		except Exception as e:
			coordinator.printer.print_message(f"分析评论违规失败: {e!s}", "ERROR")
			return []

	@staticmethod
	def _check_spam_posts(user_id: int, title: str) -> list[str]:
		"""检查用户是否刷屏发布相同标题的帖子"""
		try:
			# 搜索同标题的帖子
			post_results = list(coordinator.forum_obtain.search_posts_gen(title=title, limit=None))
			# 筛选当前用户发布的帖子
			user_posts = coordinator.toolkit.create_data_processor().filter_by_nested_values(
				data=post_results,
				id_path="user.id",
				target_values=[user_id],
			)
			# 超过阈值判定为刷屏
			if len(user_posts) >= coordinator.setting_manager.data.PARAMETER.spam_del_max:
				coordinator.printer.print_message(f"警告: 用户 {user_id} 已连续发布标题为【{title}】的帖子 {len(user_posts)} 次 (疑似刷屏)", "WARNING")
				# 生成违规标识符
				violations = []
				for post in user_posts:
					post_id = post.get("id", 0)
					if post_id:
						violations.append(f"forum:{post_id}:post:0:{post_id}")
				return violations
		except Exception as e:
			coordinator.printer.print_message(f"检查刷屏帖子失败: {e!s}", "ERROR")
		return []

	def _process_auto_report(self, violations: list[str], source_type: Literal["forum", "work", "shop"]) -> None:
		"""处理自动举报: 用学生账号批量举报违规评论"""
		# 1. 检查是否有学生账号
		auth_manager = MultiAccount()
		auth_manager.load_from_file(coordinator.path_config.PASSWORD_FILE_PATH)
		# 如果没有账号, 先加载
		# if not auth_manager.accounts:
		# 	coordinator.printer.print_message("未加载学生账号, 无法进行自动举报", "ERROR")
		# 	coordinator.printer.print_message("请在主菜单中选择 ' 加载学生账号 ' 功能", "INFO")
		# 	return
		# 2. 询问是否执行自动举报
		if coordinator.printer.get_valid_input(prompt="是否自动举报违规评论? (Y/N)", valid_options={"Y", "N"}).upper() != "Y":
			coordinator.printer.print_message("自动举报操作已取消", "INFO")
			return
		# 3. 获取举报原因
		try:
			report_reasons = coordinator.community_obtain.fetch_report_reasons()
			report_reasons_ndd = coordinator.nested_defaultdict.__class__(report_reasons)
			reason_content = report_reasons_ndd["items"][7]["content"]
		except (KeyError, IndexError) as e:
			coordinator.printer.print_message(f"获取举报原因失败: {e!s}", "ERROR")
			return
		# 4. 来源类型映射
		source_key_map: dict[Literal["work", "forum", "shop"], Literal["work", "forum", "shop"]] = {
			"work": "work",
			"forum": "forum",
			"shop": "shop",
		}
		_source_key = source_key_map[source_type]
		coordinator.printer.print_message(f"开始自动举报 (共 {len(violations)} 条违规内容)", "INFO")
		success_count = 0
		# 5. 账号管理初始化
		# 重要: 创建账号副本, 避免修改原始列表
		available_accounts = auth_manager.accounts.copy()
		if not available_accounts:
			coordinator.printer.print_message("没有可用的学生账号", "ERROR")
			return
		account_index = 0
		account_usage = {}
		account_success_map = {}  # 记录每个账号的成功状态
		# 6. 处理每条违规内容
		for idx, violation in enumerate(violations, 1):
			try:
				# 检查是否需要切换账号
				usage_count = account_usage.get(account_index, 0)
				if usage_count >= 25:
					# 切换到下一个账号
					old_index = account_index
					account_index = (account_index + 1) % len(available_accounts)
					# 记录账号切换
					if account_usage.get(old_index, 0) > 0:
						coordinator.printer.print_message(f"账号 {old_index + 1} 已使用 {account_usage.get(old_index, 0)} 次, 切换到账号 {account_index + 1}", "INFO")
				# 获取当前要使用的账号
				if account_index >= len(available_accounts):
					coordinator.printer.print_message("账号索引超出范围, 重新开始", "WARNING")
					account_index = 0
				# 使用账号
				current_usage = account_usage.get(account_index, 0)
				if current_usage == 0:
					# 首次使用该账号, 需要切换
					coordinator.printer.print_message(f"使用账号 {account_index + 1} 进行举报...", "INFO")
					# 重要修改: 直接使用账号进行登录, 而不是调用 switch_to_student_account
					# 因为 switch_to_student_account 会从列表中 pop 账号
					username, password = available_accounts[account_index]
					try:
						coordinator.auth_manager.login(
							identity=username,
							password=password,
							status="edu",
							prefer_method="password_v1",
						)
						account_success_map[account_index] = True
						coordinator.printer.print_message(f"账号 {account_index + 1} 登录成功", "SUCCESS")
					except Exception as e:
						coordinator.printer.print_message(f"账号 {account_index + 1} 登录失败: {e!s}", "ERROR")
						account_success_map[account_index] = False
						# 移除失败的账号
						available_accounts.pop(account_index)
						if not available_accounts:
							coordinator.printer.print_message("所有账号均已失效, 停止处理", "ERROR")
							break
						# 重置索引
						if account_index >= len(available_accounts):
							account_index = 0
						continue
				# 执行举报
				result = self._execute_single_report(violation=violation, reason_content=reason_content)
				if result:
					success_count += 1
					# 更新账号使用计数
					account_usage[account_index] = account_usage.get(account_index, 0) + 1
					coordinator.printer.print_message(
						f"[{idx}/{len(violations)}] 举报成功 (账号 {account_index + 1} 使用 {account_usage[account_index]} 次): {violation}",
						"SUCCESS",
					)
				else:
					coordinator.printer.print_message(f"[{idx}/{len(violations)}] 举报失败: {violation}", "ERROR")
			except Exception as e:
				coordinator.printer.print_message(f"[{idx}/{len(violations)}] 举报异常: {e!s}", "ERROR")
		# 完成后恢复管理员账号
		try:
			coordinator.auth_manager.restore_admin_account()
			coordinator.printer.print_message("已恢复管理员账号", "INFO")
		except Exception as e:
			coordinator.printer.print_message(f"恢复管理员账号失败: {e!s}", "WARNING")
		coordinator.printer.print_message(f"自动举报完成, 成功举报 {success_count}/{len(violations)} 条内容", "SUCCESS")

	@staticmethod
	def _parse_violation(violation: str) -> tuple[str, int, str, int, int] | None:
		"""解析违规标识符, 返回 (信息源, 信息源 id, 类型, 父 ID, 内容 ID)"""
		try:
			# 新格式: "信息源: 信息源 id: 类型: 父 id: 类型 id"
			parts = violation.split(":")
			if len(parts) != 5:
				return None
			source = parts[0]  # shop, forum, work
			source_id = int(parts[1])  # 信息源 ID
			violation_type = parts[2]  # post, comment, reply, work
			parent_id = int(parts[3])  # 父 ID (评论的父 ID, 帖子为 0)
			content_id = int(parts[4])  # 内容 ID
		except (ValueError, IndexError):
			return None
		else:
			return (source, source_id, violation_type, parent_id, content_id)

	def _execute_single_report(self, violation: str, reason_content: str) -> bool:
		"""执行单条举报"""
		# 1. 解析违规标识符
		parsed = self._parse_violation(violation)
		if not parsed:
			coordinator.printer.print_message(f"无法解析违规标识符: {violation}", "ERROR")
			return False
		source, source_id, violation_type, parent_id, content_id = parsed
		try:
			# 帖子举报
			if violation_type == "post":
				if source != "forum":
					coordinator.printer.print_message(f"不能在 {source} 平台举报帖子", "ERROR")
					return False
				description = f"违规: {reason_content}"
				return coordinator.forum_motion.report_post(
					post_id=content_id,
					reason_id=7,
					description=description,
				)
			# 作品举报
			if violation_type == "work":
				return coordinator.work_motion.execute_report_work(
					work_id=content_id,
					reason=reason_content,
					describe=reason_content,
				)
			# 评论/回复举报
			if violation_type in {"comment", "reply"}:
				is_reply = violation_type == "reply"
				# 作品评论/回复
				if source == "work":
					return coordinator.work_motion.execute_report_comment(
						work_id=source_id,
						comment_id=content_id,
						reason=reason_content,
					)
				# 论坛评论/回复
				if source == "forum":
					item_type = "REPLY" if is_reply else "COMMENT"
					return coordinator.forum_motion.report_item(
						item_id=content_id,
						reason_id=7,
						description="",
						item_type=item_type,
						return_data=False,
					)
				# 商店评论/回复
				if source == "shop":
					# 回复的举报需要传递父评论ID
					if is_reply:
						reporter_id = randint(10000, 199999999)
						return coordinator.shop_motion.execute_report_comment(
							comment_id=content_id,
							reason_content=reason_content,
							reason_id=7,
							reporter_id=reporter_id,
							comment_parent_id=parent_id,
							description="",
						)
					# 普通评论举报
					reporter_id = randint(10000, 199999999)
					return coordinator.shop_motion.execute_report_comment(
						comment_id=content_id,
						reason_content=reason_content,
						reason_id=7,
						reporter_id=reporter_id,
						description="",
					)
			coordinator.printer.print_message(f"未知的违规类型: {violation_type}", "ERROR")
		except Exception as e:
			coordinator.printer.print_message(f"举报操作失败: {violation} - {e!s}", "ERROR")
			return False
		else:
			return False


@singleton
class ReplyProcessor:
	@staticmethod
	def _protect_cdn_link(link: str) -> str:
		"""
		使用空白字符保护 CDN 链接
		"""
		protected = ""
		for char in link:
			protected += char + "\u200b\u200d"
		return protected.rstrip("\u200b\u200d")

	# 辅助方法
	@staticmethod
	def parse_content_field(reply: dict) -> dict | None:
		"""解析 content 字段"""
		content_data = {}
		try:
			if isinstance(reply.get("content"), str):
				content_data = loads(reply["content"])
			elif isinstance(reply.get("content"), dict):
				content_data = reply["content"]
		except (JSONDecodeError, TypeError) as e:
			print(f"解析 content 失败: {e}")
			return None
		else:
			return content_data

	@staticmethod
	def extract_comment_text(reply_type: str, message_info: dict) -> str:
		"""提取评论文本"""
		if reply_type in {"WORK_COMMENT", "POST_COMMENT"}:
			return message_info.get("comment", "")
		return message_info.get("reply", "")

	@staticmethod
	def extract_target_and_parent_ids(reply_type: str, reply: dict, message_info: dict, business_id: int, source_type: Literal["work", "forum", "shop"]) -> tuple[int, int]:
		"""提取目标 ID 和父 ID"""
		target_id = 0
		parent_id = 0
		if reply_type.endswith("_COMMENT"):
			target_id = int(reply.get("reference_id", 0))
			if not target_id:
				target_id = int(message_info.get("comment_id", 0))
			parent_id = 0
		else:
			parent_id = int(reply.get("reference_id", 0))
			if not parent_id:
				parent_id = int(message_info.get("replied_id", 0))
			comment_ids = [
				str(item)
				for item in Obtain().get_comments(
					source_id=business_id,
					source=source_type,
					method="comment_id",
				)
				if isinstance(item, (int, str))
			]
			target_id_str = str(message_info.get("reply_id", ""))
			found = coordinator.toolkit.create_string_processor().find_substrings(
				text=target_id_str,
				candidates=comment_ids,
			)[0]
			target_id = int(found) if found else 0
		return target_id, parent_id

	@staticmethod
	def match_keyword(comment_text: str, formatted_answers: dict, formatted_replies: list) -> tuple:
		"""匹配关键词"""
		chosen = ""
		matched_keyword = None
		for keyword, resp in formatted_answers.items():
			if keyword in comment_text:
				matched_keyword = keyword
				chosen = choice(resp) if isinstance(resp, list) else resp
				break
		if not chosen:
			chosen = choice(formatted_replies)
		return chosen, matched_keyword

	@staticmethod
	def log_reply_info(
		reply_id: int,
		reply_type: str,
		source_type: str,
		sender_nickname: str,
		sender_id: int,
		business_name: str,
		comment_text: str,
		matched_keyword: str,
		chosen: str,
	) -> None:
		"""记录回复信息"""
		print(f"\n {'=' * 40}")
		print(f"处理新通知 [ID: {reply_id}]")
		print(f"类型: {reply_type} ({' 作品 ' if source_type == 'work' else ' 帖子 '})")
		print(f"发送者: {sender_nickname} (ID: {sender_id})")
		print(f"来源: {business_name}")
		print(f"内容: {comment_text}")
		if matched_keyword:
			print(f"匹配到关键词: 「{matched_keyword}」")
		else:
			print("未匹配关键词, 使用随机回复")
		print(f"选择回复: 【{chosen}】")


@singleton
class ReportTypeRegistry:
	"""举报类型注册表 - 集中管理所有举报类型的配置"""

	def __init__(self) -> None:
		self._registry: dict[str, SourceConfig] = {}
		self._setup_default_actions()

	def _setup_default_actions(self) -> None:
		"""设置默认操作配置"""
		self.default_actions = {
			"D": ActionConfig("D", "删除", "删除内容", "DELETE"),
			"S": ActionConfig("S", "禁言 7 天", "禁言用户 7 天", "MUTE_SEVEN_DAYS"),
			"T": ActionConfig("T", "禁言 3 月", "禁言用户 3 个月", "MUTE_THREE_MONTHS"),
			"U": ActionConfig("U", "取消发布", "取消作品发布", "UNLOAD"),
			"P": ActionConfig("P", "通过", "通过举报, 不做处理", "PASS"),
			"F": ActionConfig("F", "检查违规", "检查其他违规内容", "CHECK_VIOLATION"),
			"J": ActionConfig("J", "跳过", "跳过当前举报", "SKIP"),
		}

	def register(self, report_type: str, config: SourceConfig) -> None:
		"""注册举报类型配置"""
		# 如果未指定可用操作, 使用默认操作
		if config.available_actions is None or len(config.available_actions) == 0:
			config.available_actions = list(self.default_actions.values())
		self._registry[report_type] = config

	def get_config(self, report_type: str) -> SourceConfig:
		"""获取举报类型配置"""
		if report_type not in self._registry:
			msg = f"未知的举报类型: {report_type}"
			raise ValueError(msg)
		return self._registry[report_type]

	def get_all_types(self) -> list[str]:
		"""获取所有注册的举报类型"""
		return list(self._registry.keys())

	def get_available_actions(self, report_type: str) -> list[ActionConfig]:
		"""获取指定举报类型的可用操作"""
		config = self.get_config(report_type)
		return [action for action in config.available_actions if action.enabled]  # pyright: ignore [reportOptionalIterable]  # ty:ignore [not-iterable]

	def get_action_prompt(self, report_type: str) -> str:
		"""生成操作提示字符串"""
		actions = self.get_available_actions(report_type)
		# 过滤掉 C 选项
		actions = [action for action in actions if action.key != "C"]
		prompt_parts = [f"{action.key}({action.name})" for action in actions]
		return "选择操作:" + ",".join(prompt_parts)

	def is_action_available(self, report_type: str, action_key: str) -> bool:
		"""检查指定操作是否可用于该举报类型"""
		actions = self.get_available_actions(report_type)
		return any(action.key == action_key for action in actions)

	def get_status_mapping(self) -> dict[str, str]:
		"""获取状态映射"""
		return {action.key: action.status for action in self.default_actions.values() if action.key in {"D", "S", "T", "P"}}


@singleton
class ReportFetcher:
	"""举报信息获取器 - 支持分块获取和类型扩展"""

	def __init__(self) -> None:
		self.registry = ReportTypeRegistry()
		self._setup_registry()
		super().__init__()

	def _setup_registry(self) -> None:
		"""初始化举报类型注册表"""
		# 商店评论类型配置
		self.registry.register(
			"shop_comment",
			SourceConfig(
				name="工作室评论举报",
				fetch_total=lambda status: coordinator.whale_obtain.fetch_comment_reports_total(source_type="ALL", status=status),
				fetch_generator=lambda status: coordinator.whale_obtain.fetch_comment_reports_gen(source_type="ALL", status=status, limit=100),
				handle_method="execute_process_comment_report",
				# 基础字段
				report_id_field="id",
				reason_id_field="reason_id",
				description_field="description",
				status_field="status",
				admin_id_field="admin_id",
				admin_username_field="admin_user_name",
				# 内容相关
				content_field="comment_content",
				content_type_field="comment_source",
				content_id_field="comment_id",
				# 用户相关
				user_id_field="comment_user_id",
				user_nickname_field="comment_user_nickname",
				user_parent_id_field="comment_parent_user_id",
				user_parent_nickname_field="comment_parent_user_nickname",
				# 来源相关
				source_id_field="comment_source_object_id",
				source_name_field="comment_source_object_name",
				source_type_field="comment_source",
				source_object_id_field="comment_source_object_id",
				source_object_name_field="comment_source_object_name",
				# 附加信息
				parent_id_field="comment_parent_id",
				special_check=lambda item: item["comment_source"] == "WORK_SHOP",
				chunk_size=100,
				available_actions=[
					self.registry.default_actions["D"],  # 删除
					self.registry.default_actions["S"],  # 禁言 7 天
					self.registry.default_actions["T"],  # 禁言 3 月
					self.registry.default_actions["P"],  # 通过
					self.registry.default_actions["F"],  # 检查违规
					self.registry.default_actions["J"],  # 跳过
				],
			),
		)
		# 作品类型配置
		self.registry.register(
			"work_work",
			SourceConfig(
				name="作品举报",
				fetch_total=lambda status: coordinator.whale_obtain.fetch_work_reports_total_extra(source_type="ALL", status=status),
				fetch_generator=lambda status: coordinator.whale_obtain.fetch_work_reports_gen(source_type="ALL", status=status, limit=100),
				handle_method="execute_process_work_report",
				# 基础字段
				report_id_field="id",
				reason_id_field="reason_id",
				description_field="description",
				status_field="status",
				admin_id_field="admin_id",
				admin_username_field="admin_username",
				# 内容相关
				content_field="work_name",
				content_type_field="work_type",
				content_id_field="work_id",
				# 用户相关
				user_id_field="work_user_id",
				user_nickname_field="work_user_nickname",
				# 来源相关
				source_id_field="work_id",
				source_name_field="work_name",
				source_type_field="work_type",
				# 附加信息
				work_type_field="work_type",
				title_field="work_name",
				chunk_size=100,
				available_actions=[
					self.registry.default_actions["D"],  # 删除
					self.registry.default_actions["P"],  # 通过
					self.registry.default_actions["U"],  # 取消发布
					self.registry.default_actions["J"],  # 跳过
				],
			),
		)
		# 论坛帖子类型配置
		self.registry.register(
			"forum_post",
			SourceConfig(
				name="帖子举报",
				fetch_total=lambda status: coordinator.whale_obtain.fetch_post_reports_total(status=status),
				fetch_generator=lambda status: coordinator.whale_obtain.fetch_post_reports_gen(status=status, limit=100),
				handle_method="execute_process_post_report",
				# 基础字段
				report_id_field="id",
				reason_id_field="reason_id",
				description_field="description",
				status_field="status",
				admin_id_field="admin_id",
				admin_username_field="admin_username",
				# 内容相关
				content_field="post_title",
				content_type_field="board_name",
				content_id_field="post_id",
				# 用户相关
				user_id_field="post_user_id",
				user_nickname_field="post_user_nick_name",
				# 来源相关
				source_id_field="post_id",
				source_name_field="board_name",
				source_type_field="board_name",
				# 附加信息
				board_id_field="board_id",
				board_name_field="board_name",
				title_field="post_title",
				chunk_size=100,
				available_actions=[
					self.registry.default_actions["D"],  # 删除
					self.registry.default_actions["S"],  # 禁言 7 天
					self.registry.default_actions["T"],  # 禁言 3 月
					self.registry.default_actions["P"],  # 通过
					self.registry.default_actions["F"],  # 检查违规
					self.registry.default_actions["J"],  # 跳过
				],
			),
		)
		# 论坛讨论类型配置
		self.registry.register(
			"forum_discussion",
			SourceConfig(
				name="讨论举报",
				fetch_total=lambda status: coordinator.whale_obtain.fetch_discussion_reports_total(status=status),
				fetch_generator=lambda status: coordinator.whale_obtain.fetch_discussion_reports_gen(status=status, limit=100),
				handle_method="execute_process_discussion_report",
				# 基础字段
				report_id_field="id",
				reason_id_field="reason_id",
				description_field="description",
				status_field="status",
				admin_id_field="admin_id",
				admin_username_field="admin_username",
				# 内容相关
				content_field="discussion_content",
				content_type_field="discussion_source",
				content_id_field="discussion_id",
				# 用户相关
				user_id_field="discussion_user_id",
				user_nickname_field="discussion_user_nickname",
				# 来源相关
				source_id_field="post_id",
				source_name_field="post_title",
				source_type_field="discussion_source",
				# 附加信息
				board_id_field="board_id",
				board_name_field="board_name",
				title_field="post_title",
				chunk_size=100,
				available_actions=[
					self.registry.default_actions["D"],  # 删除
					self.registry.default_actions["S"],  # 禁言 7 天
					self.registry.default_actions["T"],  # 禁言 3 月
					self.registry.default_actions["P"],  # 通过
					self.registry.default_actions["F"],  # 检查违规
					self.registry.default_actions["J"],  # 跳过
				],
			),
		)

	def fetch_reports_chunked(self, status: Literal["TOBEDONE", "DONE", "ALL"] = "TOBEDONE") -> Generator[list[ReportRecord]]:
		chunk: list[ReportRecord] = []
		current_type_index = 0
		report_types = self.registry.get_all_types()
		print(f"开始分块获取举报, 总类型数: {len(report_types)}")
		while current_type_index < len(report_types):
			report_type = report_types[current_type_index]
			config = self.registry.get_config(report_type=report_type)
			print(f"处理类型: {report_type}, chunk 大小配置: {config.chunk_size}")
			# 临时收集当前类型的记录
			type_chunk: list[ReportRecord] = []
			items_processed = 0
			for item in config.fetch_generator(status):
				# 如果状态是 TOBEDONE, 确保只获取未处理的
				if status == "TOBEDONE":
					item_status = item.get("status", "")
					if item_status and item_status != "TOBEDONE":
						continue
				item_ndd = coordinator.nested_defaultdict.__class__(item)
				# 创建举报记录
				record = ReportRecord(
					item=item_ndd,
					report_type=report_type,  # pyright: ignore [reportArgumentType]  # ty:ignore[invalid-argument-type]
					item_id=str(item_ndd[config.item_id_field]),
					content=item_ndd[config.content_field],
					processed=False,
					action=None,
				)
				type_chunk.append(record)
				items_processed += 1
				# 如果当前类型的 chunk 达到配置大小, 添加到总 chunk
				if len(type_chunk) >= config.chunk_size:
					print(f"类型 {report_type} 达到 chunk 大小, 准备合并")
					break
			print(f"类型 {report_type} 获取了 {len(type_chunk)} 条记录")
			# 将当前类型的记录添加到总 chunk
			chunk.extend(type_chunk)
			# 检查是否需要切换到下一个类型
			if len(type_chunk) < config.chunk_size:
				# 当前类型已无更多数据, 切换到下一个类型
				current_type_index += 1
				print(f"类型 {report_type} 数据不足, 切换到下一个类型")
			else:
				# 当前类型还有数据, 下次继续获取
				print(f"类型 {report_type} 还有数据, 继续获取")
			# 如果总 chunk 达到 100 或处理完所有类型, 则返回
			if (len(chunk) >= 100 or current_type_index >= len(report_types)) and chunk:
				print(f"返回 chunk, 大小: {len(chunk)}")
				yield chunk
				chunk = []  # 重置 chunk
		# 返回最后剩余的记录
		if chunk:
			print(f"返回最后剩余的 chunk, 大小: {len(chunk)}")
			yield chunk

	@staticmethod
	def get_total_reports(status: Literal["TOBEDONE", "DONE", "ALL"] = "TOBEDONE") -> int:
		"""获取所有举报类型的总数"""
		report_configs = [
			("shop_comment", lambda: coordinator.whale_obtain.fetch_comment_reports_total(source_type="ALL", status=status)),
			("forum_post", lambda: coordinator.whale_obtain.fetch_post_reports_total(status=status)),
			("forum_discussion", lambda: coordinator.whale_obtain.fetch_discussion_reports_total(status=status)),
			("work_work", lambda: coordinator.whale_obtain.fetch_work_reports_total_extra(status=status, source_type="ALL")),
		]
		total_reports = 0
		for _report_type, total_func in report_configs:
			total_info = total_func()
			total_reports += total_info.get("total", 0)
		return total_reports


@singleton
class BatchActionManager:
	"""批量动作管理器 - 负责管理批量处理动作和状态"""

	def __init__(self) -> None:
		self.batch_actions: dict[tuple[str, str], str] = {}
		self.processed_records: set[str] = set()
		super().__init__()

	def save_batch_action(self, group_type: str, group_key: str, action: str) -> None:
		"""保存批量处理动作"""
		self.batch_actions[group_type, group_key] = action

	def get_batch_action(self, group_type: str, group_key: str) -> str | None:
		"""获取批量处理动作"""
		return self.batch_actions.get((group_type, group_key))

	def mark_record_processed(self, record_id: str) -> None:
		"""标记记录为已处理"""
		self.processed_records.add(record_id)

	def is_record_processed(self, record_id: str) -> bool:
		"""检查记录是否已处理"""
		return record_id in self.processed_records

	def clear_processed_records(self) -> None:
		"""清空已处理记录"""
		self.processed_records.clear()


@singleton
class ReportProcessor:
	"""举报处理器 - 使用管道模式重构"""

	OFFICIAL_IDS: ClassVar = {128963, 629055, 203577, 859722, 148883, 2191000, 7492052, 387963, 3649031}
	DEFAULT_BATCH_CONFIG: ClassVar = {
		"total_threshold": 15,
		"duplicate_threshold": 5,
		"content_threshold": 3,
	}
	SOURCE_TYPE_MAP: ClassVar = {
		"shop_comment": "shop",
		"forum_post": "forum",
		"forum_discussion": "forum",
	}

	def __init__(self) -> None:
		self.batch_config = self.DEFAULT_BATCH_CONFIG.copy()
		self.processed_count = 0
		self.total_report = 0
		self.fetcher = ReportFetcher()
		self.batch_manager = BatchActionManager()
		self._violation_checker = None
		self._pipeline = None
		self.comment_processor = CommentProcessor()
		super().__init__()

	@property
	def violation_checker(self) -> ...:
		"""获取违规检查器 (懒加载)"""
		if self._violation_checker is None:
			self._violation_checker = ViolationChecker()
		return self._violation_checker

	@violation_checker.setter
	def violation_checker(self, value: ...) -> None:
		self._violation_checker = value

	@property
	def pipeline(self) -> ProcessingPipeline:
		"""获取处理管道 (懒加载)"""
		if self._pipeline is None:
			self._pipeline = ProcessorFactory.create_processing_pipeline(
				self.fetcher,
			)
		return self._pipeline

	def process_all_reports(self, admin_id: int) -> int:
		"""处理所有举报 - 使用管道模式"""
		coordinator.printer.print_header("=== 开始处理所有举报 ===")
		self.batch_manager.clear_processed_records()
		total_processed = 0
		# 询问是否一键全部通过
		auto_pass_choice = coordinator.printer.get_valid_input(
			prompt="是否一键全部通过所有待处理举报? (Y/N)",
			valid_options={"Y", "N"},
		).upper()
		if auto_pass_choice == "Y":
			return self._pass_all_pending_reports(admin_id)
		for chunk_count, chunk in enumerate(self.fetcher.fetch_reports_chunked(status="TOBEDONE")):
			coordinator.printer.print_message(
				f"处理第 {chunk_count + 1} 块数据, 共 {len(chunk)} 条举报",
				"INFO",
			)
			# 处理当前块
			chunk_processed = self._process_chunk_with_pipeline(chunk, admin_id)
			total_processed += chunk_processed
			coordinator.printer.print_message(
				f"第 {chunk_count + 1} 块处理完成, 处理了 {chunk_processed} 条举报",
				"SUCCESS",
			)
		coordinator.printer.print_message(
			f"所有举报处理完成, 共处理 {total_processed} 条举报",
			"SUCCESS",
		)
		return total_processed

	def _process_chunk_with_pipeline(self, chunk: list[ReportRecord], admin_id: int) -> int:
		"""使用管道模式处理单个数据块"""
		processed_count = 0
		# 识别批量处理组
		batch_groups = self._identify_batch_groups(chunk)
		# 处理批量组
		for group in batch_groups:
			self._handle_batch_group_with_pipeline(group, chunk, admin_id)
			processed_count += len(group.record_ids)
		# 处理剩余单个项目
		for record in chunk:
			record_id = record["item"]["id"]
			if not record["processed"] and not self.batch_manager.is_record_processed(record_id):
				# 使用管道处理单个项目
				context = self._create_context(record, admin_id)
				result = self.pipeline.execute(context)
				if result.action or result.skip_reason:
					processed_count += 1
					self.batch_manager.mark_record_processed(record_id)
				# 更新记录状态
				record["processed"] = result.processed
				record["action"] = result.action
		return processed_count

	def _handle_batch_group_with_pipeline(
		self,
		group: BatchGroup,
		chunk: list[ReportRecord],
		admin_id: int,
	) -> None:
		"""使用管道处理批量组"""
		coordinator.printer.print_message(
			f"处理批量组 [{group.group_type}] {group.group_key} (共 {len(group.record_ids)} 条举报)",
			"INFO",
		)
		# 检查是否有保存的批量动作
		saved_action = self.batch_manager.get_batch_action(
			group.group_type,
			group.group_key,
		)
		if saved_action:
			# 应用保存的批量动作
			status_map = self.fetcher.registry.get_status_mapping()
			action_name = status_map.get(saved_action, saved_action)
			coordinator.printer.print_message(
				f"应用保存的批量动作: {action_name}",
				"INFO",
			)
			for record_id in group.record_ids:
				record = self._find_record_by_id(chunk, record_id)
				if record and not record["processed"]:
					self._apply_simple_action(record, saved_action, admin_id)
					self.batch_manager.mark_record_processed(record_id)
		else:
			# 处理第一个记录并保存动作
			records = [self._find_record_by_id(chunk, rid) for rid in group.record_ids]
			records = [r for r in records if r and not r["processed"]]
			if records:
				first_record = records[0]
				# 使用管道处理第一个记录 (批量模式)
				context = self._create_context(
					first_record,
					admin_id,
					is_batch_mode=True,
				)
				result = self.pipeline.execute(context)
				if result.action:
					# 保存批量动作供后续块使用
					self.batch_manager.save_batch_action(
						group.group_type,
						group.group_key,
						result.action,
					)
					# 应用动作到组内其他记录
					for record in records[1:]:
						if group.group_type == "item_id":
							self._apply_simple_action(record, "P", admin_id)
						elif self.fetcher.registry.is_action_available(
							record["report_type"],
							result.action,
						):
							self._apply_simple_action(record, result.action, admin_id)
						else:
							coordinator.printer.print_message(
								f"动作 {result.action} 对类型 {record['report_type']} 不可用, 跳过记录 {record['item']['id']}",
								"WARNING",
							)
						self.batch_manager.mark_record_processed(record["item"]["id"])

	def _create_context(
		self,
		record: ReportRecord,
		admin_id: int,
		**kwargs: Any,
	) -> ProcessingContext:
		"""创建处理上下文"""
		config = self.fetcher.registry.get_config(record["report_type"])
		return ProcessingContext(
			record=record,
			admin_id=admin_id,
			report_type=record["report_type"],
			config=config,
			**kwargs,
		)

	def _apply_simple_action(
		self,
		record: ReportRecord,
		action: str,
		admin_id: int,
	) -> None:
		"""应用简单动作 (不经过完整管道)"""
		config = self.fetcher.registry.get_config(record["report_type"])
		# 检查动作是否可用
		if not self.fetcher.registry.is_action_available(record["report_type"], action):
			return
		# 执行处理动作
		status_map = self.fetcher.registry.get_status_mapping()
		handle_method = getattr(coordinator.whale_motion, config.handle_method)
		handle_method(report_id=record["item"]["id"], resolution=status_map[action], admin_id=admin_id)
		record["processed"] = True
		record["action"] = action

	def _pass_all_pending_reports(self, admin_id: int) -> int:
		"""一键通过所有待处理举报"""
		coordinator.printer.print_header("=== 开始一键通过所有待处理举报 ===")
		total_processed = 0
		for chunk_count, chunk in enumerate(self.fetcher.fetch_reports_chunked(status="TOBEDONE")):
			coordinator.printer.print_message(f"处理第 {chunk_count} 块数据, 共 {len(chunk)} 条举报", "INFO")
			# 批量通过当前块中的所有举报
			chunk_processed = self._pass_chunk_reports(chunk, admin_id)
			total_processed += chunk_processed
			coordinator.printer.print_message(f"第 {chunk_count} 块处理完成, 通过了 {chunk_processed} 条举报", "SUCCESS")
		coordinator.printer.print_message(f"一键通过完成, 共通过 {total_processed} 条待处理举报", "SUCCESS")
		return total_processed

	def _pass_chunk_reports(self, chunk: list[ReportRecord], admin_id: int) -> int:
		"""通过单个数据块中的所有举报"""
		processed_count = 0
		for record in chunk:
			if not record["processed"]:
				try:
					self._apply_simple_action(record, "P", admin_id)
					record["processed"] = True
					record["action"] = "P"
					processed_count += 1
					self.batch_manager.mark_record_processed(record["item"]["id"])
				except Exception as e:
					coordinator.printer.print_message(f"通过举报 {record['item']['id']} 失败: {e!s}", "ERROR")
		return processed_count

	def _identify_batch_groups(self, chunk: list[ReportRecord]) -> list[BatchGroup]:
		"""识别当前块中的批量处理组"""
		item_id_groups = defaultdict(list)
		content_groups = defaultdict(list)
		for record in chunk:
			record_id = record["item"]["id"]
			item_id = record["item_id"]
			content_key = self._get_content_key(record)
			item_id_groups[item_id].append(record_id)
			content_groups[content_key].append(record_id)
		# 构建批量组
		batch_groups = []
		processed_record_ids = set()
		# 同 ID 分组
		for item_id, record_ids in item_id_groups.items():
			if len(record_ids) >= self.batch_config["duplicate_threshold"]:
				batch_groups.append(BatchGroup("item_id", item_id, tuple(record_ids)))
				processed_record_ids.update(record_ids)
		# 同内容分组
		for content_key, record_ids in content_groups.items():
			if len(record_ids) >= self.batch_config["content_threshold"]:
				filtered_record_ids = [rid for rid in record_ids if rid not in processed_record_ids]
				if len(filtered_record_ids) >= self.batch_config["content_threshold"]:
					content_summary = f"{content_key[1]}:{content_key[0][:20]}..."
					batch_groups.append(BatchGroup("content", content_summary, tuple(filtered_record_ids)))
					processed_record_ids.update(filtered_record_ids)
		return batch_groups

	def _get_content_key(self, record: ReportRecord) -> tuple:
		"""生成内容唯一标识"""
		config = self.fetcher.registry.get_config(record["report_type"])
		item_ndd = record["item"]
		return (
			item_ndd[config.content_field],
			record["report_type"],
			item_ndd[config.source_id_field],
		)

	@staticmethod
	def _find_record_by_id(chunk: list[ReportRecord], record_id: str) -> ReportRecord | None:
		"""根据记录 ID 在块中查找记录"""
		for record in chunk:
			if record["item"]["id"] == record_id:
				return record
		return None

	def check_violation(self, source_id: Any, source_type: Literal["shop", "forum", "work"], board_name: str, user_id: int | None) -> None:
		"""检查举报内容违规 - 委托给 ViolationChecker"""
		self.violation_checker.check_violation(source_id=source_id, source_type=source_type, board_name=board_name, user_id=user_id)


@singleton
class MultiAccount:
	"""账号管理器"""

	def __init__(self, identity_type: Literal["judgement", "average", "edu"] = "edu") -> None:
		self.accounts = []
		self.identity_type: Literal["judgement", "average", "edu"] = identity_type

	def load_from_file(self, file_path: Path) -> None:
		"""从文件加载账号"""
		path = Path(file_path)
		if not path.exists():
			msg = f"文件不存在: {file_path}"
			raise FileNotFoundError(msg)

		accounts = []
		with path.open("r", encoding="utf-8") as f:
			for num, line in enumerate(f, 1):
				line = line.strip()  # noqa: PLW2901
				if not line or line.startswith("#"):
					continue

				if ":" not in line:
					print(f"第{num}行格式错误: {line}")
					continue

				username, password = line.split(":", 1)
				username, password = username.strip(), password.strip()

				if username and password:
					accounts.append((username, password))

		if not accounts:
			msg = "文件中没有有效账号"
			raise ValueError(msg)

		self.accounts = accounts
		print(f"加载 {len(accounts)} 个账号")
		self._restore_default()

	def load_from_api(self, count: int) -> None:
		"""从API加载账号"""
		if count <= 0:
			print("数量必须大于0")
			return

		self.accounts = list(
			Obtain().switch_edu_account(limit=count, return_method="list"),
		)
		print(f"从API获取 {len(self.accounts)} 个账号")
		self._restore_default()

	def execute_with_accounts(self, func: Callable[[], Any], limit: int | None = None, delay: int = 1) -> dict:
		"""用多个账号执行函数"""
		if not self.accounts:
			print("没有可用账号")
			return {"success": 0, "failed": 0, "details": []}
		accounts = self.accounts[:limit] if limit else self.accounts
		results = {"success": 0, "failed": 0, "details": []}
		for i, (username, password) in enumerate(accounts, 1):
			print(f"[{i}/{len(accounts)}] 处理: {username}")
			try:
				self._switch_and_run(username, password, func)
				results["success"] += 1
				results["details"].append({"username": username, "status": "success"})
			except Exception as e:
				results["failed"] += 1
				results["details"].append({"username": username, "status": "failed", "error": str(e)})
				print(f"失败: {e}")

			if delay > 0 and i < len(accounts):
				sleep(delay)

		print(f"完成: 成功 {results['success']}, 失败 {results['failed']}")
		self._restore_default()
		return results

	def _switch_and_run(self, username: str, password: str, func: Callable[[], Any]) -> None:
		"""切换账号并执行"""
		self._to_default()
		self._login(username, password)
		func()

	@staticmethod
	def _to_default() -> None:
		"""切到默认身份"""
		coordinator.client.switch_identity(
			token=coordinator.client.token.average,
			identity="average",
		)
		sleep(2)

	def _login(self, username: str, password: str) -> None:
		"""登录账号"""
		print(f"登录: {username}")
		coordinator.auth_manager.login(
			identity=username,
			password=password,
			status=self.identity_type,
			prefer_method="password_v1",
		)

	@staticmethod
	def _restore_default() -> None:
		"""恢复默认身份"""
		try:
			coordinator.client.switch_identity(
				token=coordinator.client.token.average,
				identity="average",
			)
		except Exception as e:
			print(f"恢复失败: {e}")

	def clear(self) -> None:
		"""清空账号"""
		self.accounts.clear()
		print("已清空")


@singleton
class FileProcessor:
	def __init__(self) -> None:
		super().__init__()

	@staticmethod
	def handle_file_upload(
		file_path: Path,
		save_path: str,
		method: Literal["pgaot", "codemao", "codegame"],
		uploader: type[FileUploaderProtocol] = FileUploader,
	) -> str | None:
		"""处理单个文件的上传流程"""
		file_size = file_path.stat().st_size
		if file_size > MAX_SIZE_BYTES:
			size_mb = file_size / 1024 / 1024
			print(f"警告: 文件 {file_path.name} 大小 {size_mb:.2f} MB 超过 15MB 限制, 跳过上传")
			return None
		# 使用重构后的统一上传接口
		url = uploader().upload(file_path=file_path, method=method, save_path=save_path)
		file_size_human = coordinator.toolkit.create_data_converter().bytes_to_human(file_size)
		history = UploadHistory(
			file_name=file_path.name,
			file_size=file_size_human,
			method=method,
			save_url=url,
			upload_time=coordinator.toolkit.create_time_utils().current_timestamp(),
		)
		coordinator.history_manager.data.history.append(history)
		coordinator.history_manager.save()
		return url

	@staticmethod
	def handle_directory_upload(
		dir_path: Path,
		save_path: str,
		method: Literal["pgaot", "codemao", "codegame"],
		uploader: type[FileUploaderProtocol] = FileUploader,
		*,
		recursive: bool,
	) -> dict[str, str | None]:
		"""处理整个文件夹的上传流程"""
		results = {}
		pattern = "**/*" if recursive else "*"
		for child_file in dir_path.rglob(pattern):
			if child_file.is_file():
				try:
					# 检查文件大小
					file_size = child_file.stat().st_size
					if file_size > MAX_SIZE_BYTES:
						size_mb = file_size / 1024 / 1024
						print(f"警告: 文件 {child_file.name} 大小 {size_mb:.2f} MB 超过 15MB 限制, 跳过上传")
						results[str(child_file)] = None
						continue
					# 计算保存路径
					relative_path = child_file.relative_to(dir_path)
					child_save_path = str(Path(save_path) / relative_path.parent)
					# 使用重构后的统一上传接口
					url = uploader().upload(file_path=child_file, method=method, save_path=child_save_path)
					# 记录上传历史
					file_size_human = coordinator.toolkit.create_data_converter().bytes_to_human(file_size)
					history = UploadHistory(
						file_name=str(relative_path),
						file_size=file_size_human,
						method=method,
						save_url=url,
						upload_time=coordinator.toolkit.create_time_utils().current_timestamp(),
					)
					coordinator.history_manager.data.history.append(history)
					results[str(child_file)] = url
				except Exception as e:
					results[str(child_file)] = None
					print(f"上传 {child_file} 失败: {e}")
		# 保存历史记录
		coordinator.history_manager.save()
		return results

	def print_upload_history(self, limit: int = 10, *, reverse: bool = True) -> None:
		"""
		打印上传历史记录 (使用通用数据查看器)
		Args:
			limit: 每页显示记录数 (默认 10 条)
			reverse: 是否按时间倒序显示 (最新的在前)
		"""
		history_list = coordinator.history_manager.data.history
		if not history_list:
			coordinator.printer.print_message("暂无上传历史记录", "INFO")
			return
		# 排序历史记录
		sorted_history = sorted(
			history_list,
			key=lambda x: x.upload_time,
			reverse=reverse,
		)
		# 定义字段格式化函数

		def format_upload_time(upload_time: float) -> str:
			"""格式化上传时间"""
			if isinstance(upload_time, (int, float)):
				return coordinator.toolkit.create_time_utils().format_timestamp(upload_time)
			return str(upload_time)[:19]

		def format_file_name(file_name: str) -> str:
			"""格式化文件名"""
			return file_name.replace("\\", "/")

		def format_url_display(save_url: str) -> str:
			"""格式化 URL 显示"""
			url = save_url.replace("\\", "/")
			parsed_url = urlparse(url)
			host = parsed_url.hostname
			if host == "static.codemao.cn":
				cn_index = url.find(".cn")
				simplified_url = url[cn_index + 3 :].split("?")[0] if cn_index != -1 else url.split("/")[-1].split("?")[0]
				return f"[static]{simplified_url}"
			if host and (host == "cdn-community.bcmcdn.com" or host.endswith(".cdn-community.bcmcdn.com")):
				com_index = url.find(".com")
				simplified_url = url[com_index + 4 :].split("?")[0] if com_index != -1 else url.split("/")[-1].split("?")[0]
				return f"[cdn]{simplified_url}"
			simplified_url = url[:30] + "..." if len(url) > 30 else url
			return f"[other]{simplified_url}"

		# 批量验证链接函数

		def batch_validate_urls(history_items: list) -> dict[int, str]:
			"""批量验证链接状态"""
			results = {}
			for idx, record in enumerate(history_items):
				is_valid = self._validate_url(record.save_url)
				status = "有效" if is_valid else "✗无效"
				results[idx] = status
			return results

		# 定义自定义操作

		def show_record_detail(record: UploadHistory) -> None:
			"""显示单条记录的详细信息并验证链接"""
			# 格式化上传时间
			upload_time = record.upload_time
			if isinstance(upload_time, (int, float)):
				upload_time = coordinator.toolkit.create_time_utils().format_timestamp(upload_time)
			coordinator.printer.print_header("=== 文件上传详情 ===")
			coordinator.printer.print_message("-" * 60, "INFO")
			coordinator.printer.print_message(f"文件名: {record.file_name}", "INFO")
			coordinator.printer.print_message(f"文件大小: {record.file_size}", "INFO")
			coordinator.printer.print_message(f"上传方式: {record.method}", "INFO")
			coordinator.printer.print_message(f"上传时间: {upload_time}", "INFO")
			coordinator.printer.print_message(f"完整 URL: {record.save_url}", "INFO")
			# 验证链接有效性
			is_valid = self._validate_url(record.save_url)
			status = "有效" if is_valid else "无效"
			coordinator.printer.print_message(f"链接状态: {status}", "INFO")
			if record.save_url.startswith("http"):
				coordinator.printer.print_message("提示: 复制上方 URL 到浏览器可直接访问或下载", "INFO")
			coordinator.printer.print_message("-" * 60, "INFO")
			input("按 Enter 键返回...")

		def validate_url_only(record: UploadHistory) -> None:
			"""仅验证链接"""
			is_valid = self._validate_url(record.save_url)
			status = "有效" if is_valid else "无效"
			coordinator.printer.print_message(f"链接 '{record.save_url}' 状态: {status}", "INFO")
			input("按 Enter 键返回...")

		custom_operations = {
			"查看详情": show_record_detail,
			"验证链接": validate_url_only,
		}
		# 使用通用数据查看器
		viewer = coordinator.toolkit.create_data_viewer(coordinator.printer)
		viewer.display_data(
			data_class=type(sorted_history[0]),
			data_list=sorted_history,
			page_size=limit,
			display_fields=["file_name", "upload_time", "save_url"],
			custom_operations=custom_operations,
			title="上传历史记录",
			id_field="file_name",
			field_formatters={
				"upload_time": format_upload_time,
				"file_name": format_file_name,
				"save_url": format_url_display,
			},
			batch_processor=batch_validate_urls,
		)

	@staticmethod
	def _validate_url(url: str) -> bool:
		"""
		验证 URL 链接是否有效
		先使用 HEAD 请求检查, 若返回无效状态则尝试 GET 请求验证内容
		"""
		try:
			# 首先尝试 HEAD 请求
			response = coordinator.client.send_request(endpoint=url, method="HEAD", timeout=5, log=False)
			if response.status_code == HTTPStatus.OK.value:  # 直接使用 200 状态码
				content_length = response.headers.get("Content-Length")
				# 如果有 Content-Length 且大于 0, 或者没有 Content-Length 都认为是有效的
				if not content_length or int(content_length) > 0:
					return True
			# HEAD 请求失败或内容长度为 0, 尝试 GET 请求
			response = coordinator.client.send_request(endpoint=url, method="GET", timeout=5, log=False)
			if response.status_code != HTTPStatus.OK.value:
				return False
			# 检查响应内容是否非空
			content = response.content
			return len(content) > 0 if content else False
		except Exception:
			return False
