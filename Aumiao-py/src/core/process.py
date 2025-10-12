"""处理器类:评论处理和举报处理"""

from collections import defaultdict
from collections.abc import Callable, Generator
from pathlib import Path
from random import randint
from time import sleep
from typing import Any, ClassVar, Literal, cast
from urllib.parse import urlparse

from src.core.base import MAX_SIZE_BYTES, ActionConfig, BatchGroup, ClassUnion, ReportRecord, SourceConfig, data, decorator
from src.core.retrieve import Obtain
from src.utils import acquire
from src.utils.acquire import HTTPSTATUS
from src.utils.tool import GenericDataViewer


@decorator.singleton
class CommentProcessor:
	def __init__(self) -> None:
		self._process_strategies = {"ads": self._process_ads, "blacklist": self._process_blacklist, "duplicates": self._process_duplicates}

	def process_item(
		self,
		item: dict[str, Any],
		config: ...,  # 实际使用时应替换为SourceConfig类型
		action_type: str,
		params: dict[Literal["ads", "blacklist", "spam_max"], Any],
		target_lists: defaultdict[str, list[str]],
	) -> None:
		"""处理项目主入口,根据action_type分发到对应处理策略"""
		item_id = int(item["id"])
		comments = config.get_comments(self, item_id)
		title = item.get(config.title_key, "")
		# 获取处理函数并执行
		strategy = self._get_strategy(action_type)
		strategy(comments=comments, item_id=item_id, title=title, params=params, target_lists=target_lists)

	def register_strategy(self, action_type: str, handler: Callable) -> None:
		"""注册自定义处理策略"""
		if not callable(handler):
			msg = "处理策略必须是可调用对象"
			raise TypeError(msg)
		self._process_strategies[action_type] = handler

	def _get_strategy(self, action_type: str) -> Callable:
		"""获取处理策略,不存在则抛出异常"""
		strategy = self._process_strategies.get(action_type)
		if not strategy:
			msg = f"未支持的处理类型: {action_type}"
			raise NotImplementedError(msg)
		return strategy

	# ========================== 内置处理策略 ==========================
	def _process_ads(self, comments: list[dict[str, Any]], item_id: int, title: str, params: dict[str, Any], target_lists: defaultdict[str, list[str]]) -> None:
		"""处理广告评论"""
		self._process_abnormal_comments(comments=comments, item_id=item_id, title=title, action_type="ads", params=params, target_lists=target_lists)

	def _process_blacklist(self, comments: list[dict[str, Any]], item_id: int, title: str, params: dict[str, Any], target_lists: defaultdict[str, list[str]]) -> None:
		"""处理黑名单用户评论"""
		self._process_abnormal_comments(comments=comments, item_id=item_id, title=title, action_type="blacklist", params=params, target_lists=target_lists)

	def _process_duplicates(
		self,
		comments: list[dict[str, Any]],
		item_id: int,
		title: str,  # 预留参数,保持策略接口一致性  # noqa: ARG002
		params: dict[str, Any],
		target_lists: defaultdict[str, list[str]],
	) -> None:
		"""处理重复刷屏评论"""
		content_map: defaultdict[tuple, list[str]] = defaultdict(list)
		# 追踪所有评论和回复
		for comment in comments:
			self._track_comment(comment, item_id, content_map, is_reply=False)
			for reply in comment.get("replies", []):
				self._track_comment(reply, item_id, content_map, is_reply=True)
		# 筛选出超过阈值的重复内容
		for (user_id, content), identifiers in content_map.items():
			if len(identifiers) >= params["spam_max"]:
				print(f"用户 {user_id} 刷屏评论: {content[:50]}... - 出现 {len(identifiers)} 次")
				target_lists["duplicates"].extend(identifiers)

	def _process_abnormal_comments(
		self, comments: list[dict[str, Any]], item_id: int, title: str, action_type: str, params: dict[str, Any], target_lists: defaultdict[str, list[str]]
	) -> None:
		"""处理异常评论 广告/黑名单:"""
		for comment in comments:
			# 跳过置顶评论
			if comment.get("is_top"):
				continue
			# 检查主评论
			if self._check_condition(comment, action_type, params):
				identifier = f"{item_id}.{comment['id']}:comment"
				self._log_and_add(target_lists=target_lists, data=comment, identifier=identifier, title=title, action_type=action_type)
			# 检查回复
			for reply in comment.get("replies", []):
				if self._check_condition(reply, action_type, params):
					identifier = f"{item_id}.{reply['id']}:reply"
					self._log_and_add(target_lists=target_lists, data=reply, identifier=identifier, title=title, action_type=action_type, parent_content=comment.get("content", ""))

	@staticmethod
	def _check_condition(data: dict[str, Any], action_type: str, params: dict[str, Any]) -> bool:
		"""检查内容是否符合处理条件"""
		content = data.get("content", "").lower()
		user_id = str(data.get("user_id", ""))
		if action_type == "ads":
			return any(ad in content for ad in params.get("ads", []))
		if action_type == "blacklist":
			return user_id in params.get("blacklist", set())
		return False

	@staticmethod
	def _log_and_add(target_lists: defaultdict[str, list[str]], data: dict[str, Any], identifier: str, title: str, action_type: str, parent_content: str = "") -> None:
		"""记录日志并添加标识到目标列表"""
		# 日志模板配置
		log_templates = {"ads": "广告{type} [{title}]{parent} : {content}", "blacklist": "黑名单{type} [{title}]{parent} : {nickname}"}
		# 区分评论/回复类型
		log_type = "回复" if ":reply" in identifier else "评论"
		parent_info = f" (父内容: {parent_content[:20]}...)" if parent_content else ""
		# 生成日志信息
		if action_type in log_templates:
			log_message = log_templates[action_type].format(
				type=log_type, title=title[:10], parent=parent_info, content=data.get("content", "")[:50], nickname=data.get("nickname", "未知用户")
			)
			print(log_message)
		# 添加到目标列表
		target_lists[action_type].append(identifier)

	@staticmethod
	def _track_comment(data: dict[str, Any], item_id: int, content_map: defaultdict[tuple, list[str]], *, is_reply: bool = False) -> None:
		"""追踪评论内容用于重复检测"""
		content_key = (data.get("user_id"), data.get("content", "").lower())
		identifier = f"{item_id}.{data.get('id')}:{'reply' if is_reply else 'comment'}"
		content_map[content_key].append(identifier)


class ReportTypeRegistry:
	"""举报类型注册表 - 集中管理所有举报类型的配置"""

	def __init__(self) -> None:
		self._registry: dict[str, SourceConfig] = {}
		self._setup_default_actions()

	def _setup_default_actions(self) -> None:
		"""设置默认操作配置"""
		self.default_actions = {
			"D": ActionConfig("D", "删除", "删除内容", "DELETE"),
			"S": ActionConfig("S", "禁言7天", "禁言用户7天", "MUTE_SEVEN_DAYS"),
			"T": ActionConfig("T", "禁言3月", "禁言用户3个月", "MUTE_THREE_MONTHS"),
			"U": ActionConfig("U", "取消发布", "取消作品发布", "UNLOAD"),
			"P": ActionConfig("P", "通过", "通过举报,不做处理", "PASS"),
			"C": ActionConfig("C", "查看详情", "查看详细信息", "DETAIL"),
			"F": ActionConfig("F", "检查违规", "检查其他违规内容", "CHECK_VIOLATION"),
			"J": ActionConfig("J", "跳过", "跳过当前举报", "SKIP"),
		}

	def register(self, report_type: str, config: SourceConfig) -> None:
		"""注册举报类型配置"""
		# 如果未指定可用操作,使用默认操作
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
		return [action for action in config.available_actions if action.enabled]  # pyright: ignore[reportOptionalIterable]

	def get_action_prompt(self, report_type: str) -> str:
		"""生成操作提示字符串"""
		actions = self.get_available_actions(report_type)
		prompt_parts = [f"{action.key}({action.name})" for action in actions]
		return "选择操作: " + ", ".join(prompt_parts)

	def is_action_available(self, report_type: str, action_key: str) -> bool:
		"""检查指定操作是否可用于该举报类型"""
		actions = self.get_available_actions(report_type)
		return any(action.key == action_key for action in actions)

	def get_status_mapping(self) -> dict[str, str]:
		"""获取状态映射"""
		return {action.key: action.status for action in self.default_actions.values() if action.key in {"D", "S", "T", "P"}}


@decorator.singleton
class ReportFetcher(ClassUnion):
	"""举报信息获取器 - 支持分块获取和类型扩展"""

	def __init__(self) -> None:
		self.registry = ReportTypeRegistry()
		self._setup_registry()
		super().__init__()

	def _setup_registry(self) -> None:
		"""初始化举报类型注册表"""
		# 评论类型配置
		self.registry.register(
			"comment",
			SourceConfig(
				name="评论举报",
				fetch_total=lambda status: self._whale_obtain.fetch_comment_reports_total(source_type="ALL", status=status),
				fetch_generator=lambda status: self._whale_obtain.fetch_comment_reports_gen(source_type="ALL", status=status, limit=100),
				handle_method="execute_process_comment_report",
				content_field="comment_content",
				user_field="comment_user",
				source_id_field="comment_source_object_id",
				source_name_field="comment_source_object_name",
				item_id_field="comment_id",
				special_check=lambda item: item["comment_source"] == "WORK_SHOP",
				chunk_size=100,
				available_actions=[
					self.registry.default_actions["D"],  # 删除
					self.registry.default_actions["S"],  # 禁言7天
					self.registry.default_actions["T"],  # 禁言3月
					self.registry.default_actions["P"],  # 通过
					self.registry.default_actions["C"],  # 查看详情
					self.registry.default_actions["F"],  # 检查违规
					self.registry.default_actions["J"],  # 跳过
				],
			),
		)
		# 作品类型配置
		self.registry.register(
			"work",
			SourceConfig(
				name="作品举报",
				fetch_total=lambda status: self._whale_obtain.fetch_work_reports_total(source_type="ALL", status=status),
				fetch_generator=lambda status: self._whale_obtain.fetch_work_reports_gen(source_type="ALL", status=status, limit=100),
				handle_method="execute_process_work_report",
				content_field="work_name",
				user_field="work_user_nickname",
				source_id_field="work_id",
				source_name_field=None,
				item_id_field="work_id",
				chunk_size=100,
				available_actions=[
					self.registry.default_actions["D"],  # 删除
					self.registry.default_actions["P"],  # 通过
					self.registry.default_actions["U"],  # 取消发布
					self.registry.default_actions["J"],  # 跳过
				],
			),
		)
		# 帖子类型配置
		self.registry.register(
			"post",
			SourceConfig(
				name="帖子举报",
				fetch_total=lambda status: self._whale_obtain.fetch_post_reports_total(status=status),
				fetch_generator=lambda status: self._whale_obtain.fetch_post_reports_gen(status=status, limit=100),
				handle_method="execute_process_post_report",
				content_field="post_title",
				user_field="post_user",
				source_id_field="post_id",
				source_name_field=None,
				item_id_field="post_id",
				chunk_size=100,
				available_actions=[
					self.registry.default_actions["D"],  # 删除
					self.registry.default_actions["S"],  # 禁言7天
					self.registry.default_actions["T"],  # 禁言3月
					self.registry.default_actions["P"],  # 通过
					self.registry.default_actions["C"],  # 查看详情
					self.registry.default_actions["F"],  # 检查违规
					self.registry.default_actions["J"],  # 跳过
				],
			),
		)
		# 讨论类型配置
		self.registry.register(
			"discussion",
			SourceConfig(
				name="讨论举报",
				fetch_total=lambda status: self._whale_obtain.fetch_discussion_reports_total(status=status),
				fetch_generator=lambda status: self._whale_obtain.fetch_discussion_reports_gen(status=status, limit=100),
				handle_method="execute_process_discussion_report",
				content_field="discussion_content",
				user_field="discussion_user",
				source_id_field="post_id",
				source_name_field=None,
				item_id_field="discussion_id",
				chunk_size=100,
				available_actions=[
					self.registry.default_actions["D"],  # 删除
					self.registry.default_actions["S"],  # 禁言7天
					self.registry.default_actions["T"],  # 禁言3月
					self.registry.default_actions["P"],  # 通过
					self.registry.default_actions["C"],  # 查看详情
					self.registry.default_actions["F"],  # 检查违规
					self.registry.default_actions["J"],  # 跳过
				],
			),
		)

	def fetch_reports_chunked(self, status: Literal["TOBEDONE", "DONE", "ALL"] = "TOBEDONE") -> Generator[list[ReportRecord]]:
		for report_type in self.registry.get_all_types():
			config = self.registry.get_config(report_type=report_type)
			yield from self._fetch_type_chunked(report_type=report_type, config=config, status=status)

	@staticmethod
	def _fetch_type_chunked(report_type: str, config: SourceConfig, status: str) -> Generator[list[ReportRecord]]:
		chunk: list[ReportRecord] = []
		for item in config.fetch_generator(status):
			item_ndd = data.NestedDefaultDict(item)
			# 创建举报记录
			record = ReportRecord(
				item=item_ndd,
				report_type=report_type,  # pyright: ignore[reportArgumentType]
				item_id=str(item_ndd[config.item_id_field]),
				content=item_ndd[config.content_field],
				processed=False,
				action=None,
			)
			chunk.append(record)
			# 达到分块大小时返回
			if len(chunk) >= config.chunk_size:
				yield chunk
				chunk = []
		# 返回剩余记录
		if chunk:
			yield chunk

	def get_total_reports(self, status: Literal["TOBEDONE", "DONE", "ALL"] = "TOBEDONE") -> int:
		"""获取所有举报类型的总数"""
		report_configs = [
			("comment", lambda: self._whale_obtain.fetch_comment_reports_total(source_type="ALL", status=status)),
			("post", lambda: self._whale_obtain.fetch_post_reports_total(status=status)),
			("discussion", lambda: self._whale_obtain.fetch_discussion_reports_total(status=status)),
			("work", lambda: self._whale_obtain.fetch_work_reports_total(status=status, source_type="ALL")),
		]
		total_reports = 0
		for _report_type, total_func in report_configs:
			total_info = total_func()
			total_reports += total_info.get("total", 0)
		return total_reports


# 其余类保持不变...
@decorator.singleton
class BatchActionManager(ClassUnion):
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


@decorator.singleton
class ReportProcessor(ClassUnion):
	"""举报处理器 - 主处理逻辑"""

	OFFICIAL_IDS: ClassVar = {128963, 629055, 203577, 859722, 148883, 2191000, 7492052, 387963, 3649031}
	DEFAULT_BATCH_CONFIG: ClassVar = {
		"total_threshold": 15,
		"duplicate_threshold": 5,
		"content_threshold": 3,
	}
	SOURCE_TYPE_MAP: ClassVar = {
		"comment": "shop",
		"post": "post",
		"discussion": "discussion",
	}

	def __init__(self) -> None:
		self.batch_config = self.DEFAULT_BATCH_CONFIG.copy()
		self.processed_count = 0
		self.total_report = 0

		self.auth_manager = ReportAuthManager()
		self.fetcher = ReportFetcher()
		self.batch_manager = BatchActionManager()
		super().__init__()

	@property
	def STATUS_MAP(self) -> dict[str, str]:  # noqa: N802
		"""动态获取状态映射"""
		return self.fetcher.registry.get_status_mapping()

	def process_all_reports(self, admin_id: int) -> int:
		"""处理所有举报 - 分块处理主入口"""
		self._printer.print_header("=== 开始处理所有举报 ===")
		self.batch_manager.clear_processed_records()
		total_processed = 0
		chunk_count = 0
		# 询问是否一键全部通过
		auto_pass_choice = self._printer.get_valid_input(prompt="是否一键全部通过所有待处理举报? (Y/N)", valid_options={"Y", "N"}).upper()
		if auto_pass_choice == "Y":  # noqa: S105
			return self._pass_all_pending_reports(admin_id)
		# 分块获取和处理举报信息
		for chunk in self.fetcher.fetch_reports_chunked(status="TOBEDONE"):
			chunk_count += 1  # noqa: SIM113
			self._printer.print_message(f"处理第 {chunk_count} 块数据,共 {len(chunk)} 条举报", "INFO")
			# 处理当前块
			chunk_processed = self._process_chunk(chunk, admin_id)
			total_processed += chunk_processed
			self._printer.print_message(f"第 {chunk_count} 块处理完成,处理了 {chunk_processed} 条举报", "SUCCESS")
			# 移除询问是否继续的代码,直接处理下一块
		self._printer.print_message(f"所有举报处理完成,共处理 {total_processed} 条举报", "SUCCESS")
		return total_processed

	def _pass_all_pending_reports(self, admin_id: int) -> int:
		"""一键通过所有待处理举报"""
		self._printer.print_header("=== 开始一键通过所有待处理举报 ===")
		total_processed = 0
		chunk_count = 0
		for chunk in self.fetcher.fetch_reports_chunked(status="TOBEDONE"):
			chunk_count += 1  # noqa: SIM113
			self._printer.print_message(f"处理第 {chunk_count} 块数据,共 {len(chunk)} 条举报", "INFO")
			# 批量通过当前块中的所有举报
			chunk_processed = self._pass_chunk_reports(chunk, admin_id)
			total_processed += chunk_processed
			self._printer.print_message(f"第 {chunk_count} 块处理完成,通过了 {chunk_processed} 条举报", "SUCCESS")
		self._printer.print_message(f"一键通过完成,共通过 {total_processed} 条待处理举报", "SUCCESS")
		return total_processed

	def _pass_chunk_reports(self, chunk: list[ReportRecord], admin_id: int) -> int:
		"""通过单个数据块中的所有举报"""
		processed_count = 0
		for record in chunk:
			if not record["processed"]:
				try:
					self._apply_action(record, "P", admin_id)
					processed_count += 1
					self.batch_manager.mark_record_processed(record["item"]["id"])
				except Exception as e:
					self._printer.print_message(f"通过举报 {record['item']['id']} 失败: {e!s}", "ERROR")
		return processed_count

	def _process_chunk(self, chunk: list[ReportRecord], admin_id: int) -> int:
		"""处理单个数据块"""
		processed_count = 0
		# 识别批量处理组
		batch_groups = self._identify_batch_groups(chunk)
		# 处理批量组
		for group in batch_groups:
			self._handle_batch_group(group, chunk, admin_id)
			processed_count += len(group.record_ids)
		# 处理剩余单个项目
		for record in chunk:
			record_id = record["item"]["id"]
			if not record["processed"] and not self.batch_manager.is_record_processed(record_id):
				self.process_single_item(record, admin_id)
				processed_count += 1
				self.batch_manager.mark_record_processed(record_id)
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
		# 同ID分组
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

	def _handle_batch_group(self, group: BatchGroup, chunk: list[ReportRecord], admin_id: int) -> None:
		"""处理批量组"""
		self._printer.print_message(f"处理批量组 [{group.group_type}] {group.group_key} (共{len(group.record_ids)}条举报)", "INFO")
		# 检查是否有保存的批量动作
		saved_action = self.batch_manager.get_batch_action(group.group_type, group.group_key)
		if saved_action:
			# 应用保存的批量动作
			self._printer.print_message(f"应用保存的批量动作: {self.STATUS_MAP[saved_action]}", "INFO")
			for record_id in group.record_ids:
				record = self._find_record_by_id(chunk, record_id)
				if record and not record["processed"]:
					self._apply_action(record, saved_action, admin_id)
					self.batch_manager.mark_record_processed(record_id)
		else:
			# 处理第一个记录并保存动作
			records = [self._find_record_by_id(chunk, rid) for rid in group.record_ids]
			records = [r for r in records if r and not r["processed"]]
			if records:
				first_record = records[0]
				first_action = self.process_single_item(first_record, admin_id, batch_mode=True)
				if first_action:
					# 保存批量动作供后续块使用
					self.batch_manager.save_batch_action(group.group_type, group.group_key, first_action)
					# 应用动作到组内其他记录
					for record in records[1:]:
						if group.group_type == "item_id":
							self._apply_action(record, "P", admin_id)
						# 确保动作对当前记录类型可用
						elif self.fetcher.registry.is_action_available(record["report_type"], first_action):
							self._apply_action(record, first_action, admin_id)
						else:
							self._printer.print_message(f"动作 {first_action} 对类型 {record['report_type']} 不可用,跳过记录 {record['item']['id']}", "WARNING")
						self.batch_manager.mark_record_processed(record["item"]["id"])

	@staticmethod
	def _find_record_by_id(chunk: list[ReportRecord], record_id: str) -> ReportRecord | None:
		"""根据记录ID在块中查找记录"""
		for record in chunk:
			if record["item"]["id"] == record_id:
				return record
		return None

	def _apply_action(self, record: ReportRecord, action: str, admin_id: int) -> None:
		"""应用处理动作到举报记录"""
		config = self.fetcher.registry.get_config(record["report_type"])
		# 检查动作是否可用
		if not self.fetcher.registry.is_action_available(record["report_type"], action):
			self._printer.print_message(f"动作 {action} 对类型 {record['report_type']} 不可用", "ERROR")
			return
		# 执行处理动作
		handle_method = getattr(self._whale_motion, config.handle_method)
		handle_method(report_id=record["item"]["id"], resolution=self.STATUS_MAP[action], admin_id=admin_id)
		record["processed"] = True
		record["action"] = action
		action_config = next((ac for ac in config.available_actions if ac.key == action), None)  # pyright: ignore[reportOptionalIterable]
		action_name = action_config.name if action_config else action
		self._printer.print_message(f"已应用操作: {action_name}", "SUCCESS")

	def process_single_item(self, record: ReportRecord, admin_id: int, *, batch_mode: bool = False, reprocess_mode: bool = False) -> str | None:
		"""处理单个举报项目"""
		item_ndd = record["item"]
		report_type = record["report_type"]
		config = self.fetcher.registry.get_config(report_type)
		# 显示处理头信息
		if batch_mode:
			self._printer.print_header("=== 批量处理首个项目 ===")
		elif reprocess_mode:
			self._printer.print_header("=== 重新处理项目 ===")
		# 显示举报详情
		self._display_report_details(item_ndd, report_type, config)
		# 官方账号检查
		user_id_str = item_ndd[f"{config.user_field}_id"]
		user_id = int(user_id_str) if user_id_str != "UNKNOWN" and user_id_str.isdigit() else None
		if user_id and user_id in self.OFFICIAL_IDS:
			self._printer.print_message("这是一条官方发布的内容,自动通过", "WARNING")
			self._apply_action(record, "P", admin_id)
			return "P"
		# 获取可用操作
		available_actions = self.fetcher.registry.get_available_actions(report_type)
		action_keys = [action.key for action in available_actions]
		# 操作选择循环
		while True:
			prompt = self.fetcher.registry.get_action_prompt(report_type)
			choice = self._printer.get_valid_input(prompt=prompt, valid_options=set(action_keys)).upper()
			# 处理状态变更操作
			if choice in {"D", "S", "T", "P"}:
				self._apply_action(record, choice, admin_id)
				return choice
			# 处理辅助操作
			if choice == "C":
				self._show_item_details(item_ndd, report_type, config)
				# 查看详情后继续选择操作
				continue
			if choice == "F":
				if config.special_check(item_ndd):
					adjusted_source_type = self.SOURCE_TYPE_MAP[report_type]
					self._check_violation(
						source_id=item_ndd[config.source_id_field],
						source_type=adjusted_source_type,  # pyright: ignore[reportArgumentType]
						board_name=item_ndd.get("board_name", "UNKNOWN"),
						user_id=user_id_str,
					)
					# 检查违规后继续选择操作,不标记为已处理
					continue
				self._printer.print_message("该类型不支持检查违规操作", "ERROR")
				continue
			if choice == "J":
				self._printer.print_message("已跳过该举报", "INFO")
				# 跳过也不标记为已处理,让用户后续可以重新处理
				return None

	def _display_report_details(self, item_ndd: "data.NestedDefaultDict", report_type: str, config: SourceConfig) -> None:
		"""显示举报详情"""
		self._printer.print_header("=== 举报详情 ===")
		self._printer.print_message(f"举报ID: {item_ndd['id']}", "INFO")
		self._printer.print_message(f"举报类型: {report_type}", "INFO")
		# 显示内容
		content = item_ndd[config.content_field]
		if content != "UNKNOWN":
			content_text = self._tool.DataConverter().html_to_text(content)
			self._printer.print_message(f"举报内容: {content_text}", "INFO")
		else:
			self._printer.print_message("举报内容: 无内容", "INFO")
		# 显示板块信息
		board_name = item_ndd.get("board_name", "UNKNOWN")
		if board_name == "UNKNOWN" and config.source_name_field:
			board_name = item_ndd[config.source_name_field]
		self._printer.print_message(f"所属板块: {board_name}", "INFO")
		# 显示被举报人信息
		user_nickname = item_ndd.get(f"{config.user_field}_nick_name", "UNKNOWN")
		if user_nickname == "UNKNOWN":
			user_nickname = item_ndd.get(f"{config.user_field}_nickname", "UNKNOWN")
		self._printer.print_message(f"被举报人: {user_nickname}", "INFO")
		# 显示举报原因和时间
		self._printer.print_message(f"举报原因: {item_ndd.get('reason_content', 'UNKNOWN')}", "INFO")
		create_time = item_ndd.get("created_at", "UNKNOWN")
		if create_time != "UNKNOWN":
			create_time_str = self._tool.TimeUtils().format_timestamp(create_time)
			self._printer.print_message(f"举报时间: {create_time_str}", "INFO")
		else:
			self._printer.print_message("举报时间: 未知", "INFO")
		# 帖子类型额外信息
		if report_type in {"post", "work"}:
			self._printer.print_message(f"举报线索: {item_ndd.get('description', 'UNKNOWN')}", "INFO")

	def _show_item_details(self, item_ndd: "data.NestedDefaultDict", report_type: str, config: SourceConfig) -> None:
		"""展示举报项目详细信息"""
		self._printer.print_header("=== 详细信息 ===")
		post_id = item_ndd[config.source_id_field]
		if post_id != "UNKNOWN":
			self._printer.print_message(f"违规帖子链接: https://shequ.codemao.cn/community/{post_id}", "INFO")
		elif report_type == "discussion":
			post_title = item_ndd.get("post_title", "UNKNOWN")
			self._printer.print_message(f"所属帖子标题: {post_title}", "INFO")
			source_id = item_ndd[config.source_id_field]
			if source_id != "UNKNOWN":
				self._printer.print_message(f"所属帖子链接: https://shequ.codemao.cn/community/{source_id}", "INFO")
		# 违规用户链接
		user_id = item_ndd.get(f"{config.user_field}_id", "UNKNOWN")
		if user_id != "UNKNOWN":
			self._printer.print_message(f"违规用户链接: https://shequ.codemao.cn/user/{user_id}", "INFO")

	def _check_violation(self, source_id: Any, source_type: Literal["shop", "post", "discussion"], board_name: str, user_id: str | None) -> None:  # noqa: ANN401
		"""检查举报内容违规"""
		# 这里实现违规检查逻辑,可以从旧版代码移植
		self._printer.print_message(f"检查违规: source_id={source_id}, type={source_type}, board={board_name}, user={user_id}", "INFO")
		source_id = int(source_id) if source_id != "UNKNOWN" and str(source_id).isdigit() else 0
		if not source_id:
			self._printer.print_message("无效的来源ID,无法检查违规", "ERROR")
			return
		adjusted_type = "post" if source_type == "discussion" else source_type  # 讨论归为帖子类型
		# 分析违规评论
		violations = self._analyze_comment_violations(source_id=source_id, source_type=adjusted_type, board_name=board_name)
		if not violations:
			self._printer.print_message("未检测到违规评论", "INFO")
			return
		# 执行自动举报(用学生账号)
		self._process_auto_report(violations=violations, source_id=source_id, source_type=adjusted_type)
		# 2. 帖子的违规检查:重复发帖(同一用户发布同标题帖子过多)
		if source_type == "post" and user_id and user_id != "UNKNOWN":
			try:
				# 搜索同标题的帖子
				post_results = self._forum_obtain.search_posts_gen(title=board_name, limit=None)
				# 筛选当前用户发布的帖子
				user_posts = self._tool.DataProcessor().filter_by_nested_values(
					data=post_results,
					id_path="user.id",  # 嵌套字段路径:user -> id
					target_values=[user_id],
				)
				# 超过阈值判定为垃圾帖
				if len(user_posts) >= self._setting.PARAMETER.spam_del_max:
					self._printer.print_message(f"警告:用户{user_id} 已连续发布标题为【{board_name}】的帖子 {len(user_posts)} 次(疑似垃圾帖)", "WARNING")
			except Exception as e:
				self._printer.print_message(f"搜索帖子失败: {e!s}", "ERROR")

	def _analyze_comment_violations(self, source_id: int, source_type: Literal["post", "work", "shop"], board_name: str) -> list[str]:
		"""分析评论违规内容:广告、黑名单、重复评论"""
		try:
			# 1. 获取评论详情列表
			comments = Obtain().get_comments_detail(com_id=source_id, source=source_type, method="comments")
			# 2. 违规检查参数(广告关键词、黑名单、垃圾帖阈值)
			check_params: dict[Literal["ads", "blacklist", "spam_max"], list[str] | int] = {
				"ads": self._data.USER_DATA.ads,
				"blacklist": self._data.USER_DATA.black_room,
				"spam_max": self._setting.PARAMETER.spam_del_max,
			}
			# 3. 调用评论处理器分析违规
			comment_processor = CommentProcessor()
			# 临时配置类:适配评论处理器的参数要求

			class CommentCheckConfig:
				title_key = "title"  # 标题字段名

				@staticmethod
				def get_comments(_processor: Callable, _item_id: int) -> list[dict]:
					return comments  # 返回评论列表

			config = CommentCheckConfig()
			violation_targets: defaultdict[str, list[str]] = defaultdict(list)  # 违规内容列表
			# 检查广告、黑名单、重复评论
			for check_type in ["ads", "blacklist", "duplicates"]:
				comment_processor.process_item(
					item={"id": source_id, "title": board_name}, config=config, action_type=check_type, params=check_params, target_lists=violation_targets
				)
			# 合并所有违规内容(去重,避免重复举报)
			return list(set(violation_targets["ads"] + violation_targets["blacklist"] + violation_targets["duplicates"]))
		except Exception as e:
			self._printer.print_message(f"分析评论违规失败: {e!s}", "ERROR")
			return []

	def _process_auto_report(self, violations: list[str], source_id: int, source_type: Literal["post", "work", "shop"]) -> None:  # noqa: PLR0912, PLR0914, PLR0915
		"""处理自动举报:用学生账号批量举报违规评论"""
		# 1. 检查学生账号是否可用
		if not (self.auth_manager.student_accounts or self.auth_manager.student_tokens):
			self._printer.print_message("未加载学生账号,无法执行自动举报", "WARNING")
			return
		# 2. 询问是否执行自动举报
		if self._printer.get_valid_input(prompt="是否自动举报违规评论? (Y/N)", valid_options={"Y", "N"}).upper() != "Y":
			self._printer.print_message("自动举报操作已取消", "INFO")
			return
		# 3. 获取举报原因
		try:
			report_reasons = self._community_obtain.fetch_report_reasons()
			report_reasons_ndd = data.NestedDefaultDict(report_reasons)
			reason_content = report_reasons_ndd["items"][7]["content"]
		except (KeyError, IndexError) as e:
			self._printer.print_message(f"获取举报原因失败: {e!s}", "ERROR")
			return
		# 4. 来源类型映射
		source_key_map: dict[Literal["work", "post", "shop"], Literal["work", "forum", "shop"]] = {
			"work": "work",
			"post": "forum",
			"shop": "shop",
		}
		source_key = source_key_map[source_type]
		# 5. 准备账号管理
		# 复制可用账号列表,避免修改原列表
		available_accounts = self.auth_manager.student_accounts.copy() if self.auth_manager.auth_method == "grab" else self.auth_manager.student_tokens.copy()
		self._printer.print_message(f"开始自动举报(共 {len(violations)} 条违规内容)", "INFO")
		success_count = 0
		# 6. 处理每条违规内容
		for idx, violation in enumerate(violations, 1):
			# 解析违规内容格式
			violation_parts = violation.split(":")
			if len(violation_parts) < 2:  # noqa: PLR2004
				self._printer.print_message(f"违规内容格式错误: {violation}", "ERROR")
				continue
			item_id_part = violation_parts[0].split(".")
			if len(item_id_part) < 2:  # noqa: PLR2004
				self._printer.print_message(f"违规ID格式错误: {violation_parts[0]}", "ERROR")
				continue
			_, comment_id = item_id_part
			is_reply = "reply" in violation
			# 查找父评论ID
			parent_id, _ = self._tool.StringProcessor().find_substrings(text=comment_id, candidates=violations)
			parent_id = int(parent_id) if parent_id and parent_id != "UNKNOWN" else None
			# 为当前违规项尝试举报
			violation_success = False
			retry_count = 0
			max_retries = min(3, len(available_accounts))  # 最多重试3次或可用账号数
			while not violation_success and retry_count < max_retries and available_accounts:
				# 切换学生账号
				if self.auth_manager.auth_method == "grab":
					self.auth_manager.student_accounts = available_accounts.copy()
				else:
					self.auth_manager.student_tokens = available_accounts.copy()
				if not self.auth_manager.switch_to_student_account():
					# 切换失败,移除当前账号并重试
					if available_accounts:
						available_accounts.pop(0)
					retry_count += 1
					continue
				# 获取当前学生账号ID
				try:
					user_details = self._user_obtain.fetch_account_details()
					user_details_ndd = data.NestedDefaultDict(user_details)
					reporter_id = user_details_ndd["id"]
					if reporter_id == "UNKNOWN":
						msg = "获取学生账号ID失败"
						raise ValueError(msg)  # noqa: TRY301
				except Exception as e:
					self._printer.print_message(f"获取学生账号信息失败: {e!s}", "ERROR")
					# 移除当前账号并重试
					if available_accounts:
						available_accounts.pop(0)
					retry_count += 1
					continue
				# 执行举报操作
				try:
					if self._execute_report_action(
						source_key=source_key,
						target_id=int(comment_id),
						source_id=source_id,
						reason_id=7,
						reporter_id=int(reporter_id),
						reason_content=reason_content,
						parent_id=parent_id,
						is_reply=is_reply,
					):
						self._printer.print_message(f"[{idx}/{len(violations)}] 举报成功: {violation}", "SUCCESS")
						success_count += 1
						violation_success = True
					else:
						self._printer.print_message(f"[{idx}/{len(violations)}] 举报失败: {violation}", "ERROR")
						# 移除当前账号并重试
						if available_accounts:
							available_accounts.pop(0)
						retry_count += 1
				except Exception as e:
					self._printer.print_message(f"[{idx}/{len(violations)}] 执行举报异常: {e!s}", "ERROR")
					# 移除当前账号并重试
					if available_accounts:
						available_accounts.pop(0)
					retry_count += 1
			# 如果当前违规项处理失败,记录日志
			if not violation_success:
				self._printer.print_message(f"[{idx}/{len(violations)}] 处理失败,跳过: {violation}", "WARNING")
		# 7. 举报完成:恢复管理员账号
		self.auth_manager._restore_admin_account()  # noqa: SLF001
		self._printer.print_message(f"自动举报完成,成功举报 {success_count}/{len(violations)} 条内容", "SUCCESS")

	def _execute_report_action(
		self,
		source_key: Literal["forum", "work", "shop"],
		target_id: int,
		source_id: int,
		reason_id: Literal[0, 1, 2, 3, 4, 5, 6, 7, 8],
		reporter_id: int,
		reason_content: str,
		parent_id: int | None = None,
		*,
		is_reply: bool = False,
		description: str = "",
	) -> bool:
		"""执行举报操作:根据来源类型调用不同模块的举报接口"""
		try:
			match source_key:
				# 作品模块:举报作品评论
				case "work":
					return self._work_motion.execute_report_comment(work_id=target_id, comment_id=source_id, reason=reason_content)
				# 论坛模块:举报帖子评论/回复
				case "forum":
					item_type = "COMMENT" if is_reply else "REPLY"  # 回复/普通评论区分
					return self._forum_motion.report_item(item_id=target_id, reason_id=reason_id, description=description, item_type=item_type, return_data=False)
				# 店铺模块:举报店铺评论/回复
				case "shop":
					if is_reply and parent_id is not None:
						# 回复类型:需传入父评论ID
						return self._shop_motion.execute_report_comment(
							comment_id=target_id, reason_content=reason_content, reason_id=reason_id, reporter_id=reporter_id, comment_parent_id=parent_id, description=description
						)
					# 普通评论:无需父ID
					return self._shop_motion.execute_report_comment(
						comment_id=target_id, reason_content=reason_content, reason_id=reason_id, reporter_id=reporter_id, description=description
					)
			# 未知来源类型:举报失败
		except Exception as e:
			self._printer.print_message(f"举报操作失败: {e!s}", "ERROR")
			return False
		else:
			return False


@decorator.singleton
class ReportAuthManager(ClassUnion):
	def __init__(self) -> None:
		self.student_accounts = []
		self.student_tokens = []
		self.auth_method = "grab"

		super().__init__()

	def execute_admin_login(self) -> None:
		"""执行管理员登录(支持Token/账密两种方式)"""
		self._printer.print_header("=== 登录管理后台 ===")
		choice = self._printer.get_valid_input(prompt="请选择登录方式: 1.Token登录 2.账密登录", valid_options={"1", "2"})
		if choice == "1":
			self._handle_token_login()
		else:
			self._handle_password_login()

	def _handle_token_login(self) -> None:
		"""处理Token登录:直接配置认证Token"""
		token = self._printer.prompt_input("请输入 Authorization Token")
		self._whale_routine.configure_authentication_token(token)
		self._printer.print_message("Token登录成功", "SUCCESS")

	def _handle_password_login(self) -> None:
		"""处理账密登录:支持验证码重试,优化错误处理"""

		# 根本原理:验证码并非完全随机生成,而是使用确定性算法,根据“时间戳”和“序列位置”计算得出。
		# 验证码池:系统为每个请求的时间戳维护一个虚拟的、按需生成的验证码序列。你每次请求并不是从一个预先生好的池子里取,而是实时计算出该时间戳对应的第N个验证码。
		# 一次性使用:每个验证码在成功验证后立即失效,不能重复使用。
		# 序列连续性:对同一时间戳的连续请求,会按顺序生成该序列中的不同验证码。
		# 时间戳隔离:不同时间戳对应的验证码序列完全独立,无法交叉使用。
		# 长期有效性:系统缺乏对客户端时间戳的时效性校验,导致很久之前的时间戳仍然可以生成有效的验证码序列。
		def input_account() -> tuple[str, str]:
			"""内部函数:获取用户名和密码(统一命名为account)"""
			username = self._printer.prompt_input("请输入用户名")
			password = self._printer.prompt_input("请输入密码")
			return username, password

		def input_captcha(timestamp: int) -> tuple[str, Any]:
			"""内部函数:获取验证码和Cookie"""
			self._printer.print_message("正在获取验证码...", "INFO")
			cookies = self._whale_routine.fetch_verification_captcha(timestamp=timestamp)
			captcha = self._printer.prompt_input("请输入验证码")
			return captcha, cookies

		# 登录循环:直到成功或用户中断(实际可加重试次数限制)
		timestamp = self._tool.TimeUtils().current_timestamp(13)  # 13位时间戳
		username, password = input_account()
		captcha, _ = input_captcha(timestamp=timestamp)
		while True:
			# 调用鲸平台认证接口
			response = self._whale_routine.authenticate_user(username=username, password=password, key=timestamp, code=captcha)
			# 登录成功:配置Token并退出循环
			if "token" in response:
				self._whale_routine.configure_authentication_token(response["token"])
				self._printer.print_message("账密登录成功", "SUCCESS")
				break
			# 登录失败:根据错误码处理
			if "error_code" in response:
				self._printer.print_message(response["error_msg"], "ERROR")
				# 密码错误/参数无效:重新输入账号
				if response["error_code"] in {"Admin-Password-Error@Community-Admin", "Param - Invalid @ Common"}:
					username, password = input_account()
				# 重新获取验证码和时间戳(无论何种错误,验证码均失效)
				timestamp = self._tool.TimeUtils().current_timestamp(13)
				captcha, _ = input_captcha(timestamp=timestamp)

	def load_student_accounts(self) -> None:
		"""加载学生账号:用于自动举报,支持实时获取/文件加载"""
		# 切换到普通账号上下文(加载学生账号需普通权限)
		self._client.switch_account(token=self._client.token.average, identity="average")
		# 询问是否加载学生账号
		if self._printer.get_valid_input(prompt="是否加载学生账号用于自动举报? (Y/N)", valid_options={"Y", "N"}).upper() != "Y":
			self._printer.print_message("未加载学生账号,自动举报功能不可用", "WARNING")
			self._restore_admin_account()
			return
		# 选择账号获取方式(实时获取/文件加载)
		method = self._printer.get_valid_input(prompt="选择模式(load.加载文件 grab.实时获取)", valid_options={"load", "grab"}, cast_type=str)
		self.auth_method = cast("Literal['load', 'grab']", method)
		try:
			if method == "grab":
				# 实时获取学生账号(调用Obtain工具)
				account_count = self._printer.get_valid_input(
					prompt="输入获取账号数",
					cast_type=int,
					validator=lambda x: x >= 0,  # 确保数量非负
				)
				self.student_accounts = list(Obtain().switch_edu_account(limit=account_count, return_method="list"))
				self._printer.print_message(f"已实时加载 {len(self.student_accounts)} 个学生账号", "SUCCESS")
			elif method == "load":
				# 从文件加载学生账号Token(文件路径在data模块定义)
				token_list = self._file.read_line(data.TOKEN_DIR)
				self.student_tokens = [token.strip() for token in token_list if token.strip()]  # 过滤空行
				self._printer.print_message(f"已从文件加载 {len(self.student_tokens)} 个学生账号Token", "SUCCESS")
		except Exception as e:
			# 捕获所有异常(文件不存在、接口错误等)
			self._printer.print_message(f"加载学生账号失败: {e!s}", "ERROR")
			self.student_accounts = []
			self.student_tokens = []
		# 恢复管理员账号上下文(加载完成后切回管理员)
		self._restore_admin_account()

	def switch_to_student_account(self) -> bool:
		"""切换到学生账号:供举报处理类调用,返回切换结果"""
		# 确定可用账号列表(实时获取的账密 / 文件加载的Token)
		available_accounts = self.student_accounts or self.student_tokens
		if not available_accounts:
			return False
		# 随机选择一个账号(避免重复使用)
		selected_account = available_accounts.pop(randint(0, len(available_accounts) - 1))
		try:
			if self.auth_method == "grab":
				# 实时获取的账号:用账密认证
				username, password = selected_account
				self._printer.print_message(f"切换学生账号: {id(username)}", "INFO")
				sleep(2)  # 避免接口限流
				self._community_login.authenticate_with_token(
					identity=username,
					password=password,
					status="edu",  # 教育账号标识
				)
			else:
				# 文件加载的账号:用Token切换
				token = cast("str", selected_account)
				self._printer.print_message(f"切换学生账号: {id(token)}", "INFO")
				self._client.switch_account(token=token, identity="edu")
		except Exception as e:
			self._printer.print_message(f"学生账号切换失败: {e!s}", "ERROR")
			return False  # 切换失败
		else:
			return True

	def _restore_admin_account(self) -> None:
		"""恢复管理员账号:封装重复切换逻辑,避免代码冗余"""
		self._client.switch_account(token=self._client.token.judgement, identity="judgement")

	def terminate_session(self) -> None:
		"""终止当前会话:清理资源并恢复管理员账号"""
		self._whale_routine.terminate_session()
		self._restore_admin_account()
		self._printer.print_message("已终止会话并恢复管理员账号", "INFO")


class FileProcessor(ClassUnion):
	def __init__(self) -> None:
		super().__init__()

	def handle_file_upload(self, file_path: Path, save_path: str, method: Literal["pgaot", "codemao", "codegame"], uploader: acquire.FileUploader) -> str | None:
		"""处理单个文件的上传流程"""
		file_size = file_path.stat().st_size
		if file_size > MAX_SIZE_BYTES:
			size_mb = file_size / 1024 / 1024
			print(f"警告: 文件 {file_path.name} 大小 {size_mb:.2f}MB 超过 15MB 限制,跳过上传")
			return None
		# 使用重构后的统一上传接口
		url = uploader.upload(file_path=file_path, method=method, save_path=save_path)
		file_size_human = self._tool.DataConverter().bytes_to_human(file_size)
		history = data.UploadHistory(file_name=file_path.name, file_size=file_size_human, method=method, save_url=url, upload_time=self._tool.TimeUtils().current_timestamp())
		self._upload_history.data.history.append(history)
		self._upload_history.save()
		return url

	def handle_directory_upload(
		self, dir_path: Path, save_path: str, method: Literal["pgaot", "codemao", "codegame"], uploader: acquire.FileUploader, *, recursive: bool
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
						print(f"警告: 文件 {child_file.name} 大小 {size_mb:.2f}MB 超过 15MB 限制,跳过上传")
						results[str(child_file)] = None
						continue
					# 计算保存路径
					relative_path = child_file.relative_to(dir_path)
					child_save_path = str(Path(save_path) / relative_path.parent)
					# 使用重构后的统一上传接口
					url = uploader.upload(file_path=child_file, method=method, save_path=child_save_path)
					# 记录上传历史
					file_size_human = self._tool.DataConverter().bytes_to_human(file_size)
					history = data.UploadHistory(
						file_name=str(relative_path), file_size=file_size_human, method=method, save_url=url, upload_time=self._tool.TimeUtils().current_timestamp()
					)
					self._upload_history.data.history.append(history)
					results[str(child_file)] = url
				except Exception as e:
					results[str(child_file)] = None
					print(f"上传 {child_file} 失败: {e}")
		# 保存历史记录
		self._upload_history.save()
		return results

	def print_upload_history(self, limit: int = 10, *, reverse: bool = True) -> None:
		"""
		打印上传历史记录(使用通用数据查看器)
		Args:
			limit: 每页显示记录数(默认10条)
			reverse: 是否按时间倒序显示(最新的在前)
		"""
		history_list = self._upload_history.data.history
		if not history_list:
			self._printer.print_message("暂无上传历史记录", "INFO")
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
				return self._tool.TimeUtils().format_timestamp(upload_time)
			return str(upload_time)[:19]

		def format_file_name(file_name: str) -> str:
			"""格式化文件名"""
			return file_name.replace("\\", "/")

		def format_url_display(save_url: str) -> str:
			"""格式化URL显示"""
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
			simplified_url = url[:30] + "..." if len(url) > 30 else url  # noqa: PLR2004
			return f"[other]{simplified_url}"

		# 定义自定义操作
		def show_record_detail(record: data.UploadHistory) -> None:
			"""显示单条记录的详细信息并验证链接"""
			# 格式化上传时间
			upload_time = record.upload_time
			if isinstance(upload_time, (int, float)):
				upload_time = self._tool.TimeUtils().format_timestamp(upload_time)

			self._printer.print_header("=== 文件上传详情 ===")
			self._printer.print_message("-" * 60, "INFO")
			self._printer.print_message(f"文件名: {record.file_name}", "INFO")
			self._printer.print_message(f"文件大小: {record.file_size}", "INFO")
			self._printer.print_message(f"上传方式: {record.method}", "INFO")
			self._printer.print_message(f"上传时间: {upload_time}", "INFO")
			self._printer.print_message(f"完整URL: {record.save_url}", "INFO")

			# 验证链接有效性
			is_valid = self._validate_url(record.save_url)
			status = "有效" if is_valid else "无效"
			self._printer.print_message(f"链接状态: {status}", "INFO")

			if record.save_url.startswith("http"):
				self._printer.print_message("提示: 复制上方URL到浏览器可直接访问或下载", "INFO")

			self._printer.print_message("-" * 60, "INFO")
			input("按Enter键返回...")

		def validate_url_only(record: data.UploadHistory) -> None:
			"""仅验证链接"""
			is_valid = self._validate_url(record.save_url)
			status = "有效" if is_valid else "无效"
			self._printer.print_message(f"链接 '{record.save_url}' 状态: {status}", "INFO")
			input("按Enter键返回...")

		custom_operations = {
			"查看详情": show_record_detail,
			"验证链接": validate_url_only,
		}

		# 使用通用数据查看器
		viewer = GenericDataViewer(self._printer)
		viewer.display_data(
			data_class=type(sorted_history[0]),  # 获取dataclass类型
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
		)

	# 保留原有的验证URL方法
	def _validate_url(self, url: str) -> bool:
		"""
		验证URL链接是否有效
		先使用HEAD请求检查,若返回无效状态则尝试GET请求验证内容
		"""
		response = self._client.send_request(endpoint=url, method="HEAD", timeout=5)
		if response.status_code == HTTPSTATUS.OK.value:
			content_length = response.headers.get("Content-Length")
			if content_length and int(content_length) > 0:
				return True
		response = self._client.send_request(endpoint=url, method="GET", stream=True, timeout=5)
		if response.status_code != HTTPSTATUS.OK.value:
			return False
		return bool(next(response.iter_content(chunk_size=1)))
