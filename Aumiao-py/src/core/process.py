"""处理器类:评论处理和举报处理"""

from collections import defaultdict
from collections.abc import Callable, Generator
from pathlib import Path
from random import randint
from time import sleep
from typing import Any, ClassVar, Literal, cast
from urllib.parse import urlparse

from src.core.base import MAX_SIZE_BYTES, BatchGroup, ClassUnion, ReportRecord, data, decorator, tool
from src.core.retrieve import Obtain
from src.utils import acquire
from src.utils.acquire import HTTPSTATUS


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


@decorator.singleton
class ReportProcessor(ClassUnion):
	OFFICIAL_IDS: ClassVar = {128963, 629055, 203577, 859722, 148883, 2191000, 7492052, 387963, 3649031}
	DEFAULT_BATCH_CONFIG: ClassVar = {
		"total_threshold": 15,
		"duplicate_threshold": 5,
		"content_threshold": 3,
	}
	STATUS_MAP: ClassVar = {
		"D": "DELETE",
		"S": "MUTE_SEVEN_DAYS",
		"T": "MUTE_THREE_MONTHS",
		"P": "PASS",
	}
	SOURCE_TYPE_MAP: ClassVar[dict[Literal["comment", "post", "discussion"], Literal["shop", "post", "discussion"]]] = {
		"comment": "shop",
		"post": "post",
		"discussion": "discussion",
	}

	def __init__(self) -> None:
		self.batch_config = self.DEFAULT_BATCH_CONFIG.copy()
		self.processed_count = 0
		self.total_report = 0
		self.printer = tool.Printer()
		self.auth_manager = ReportAuthManager()
		super().__init__()

	def get_total_reports(self, status: Literal["TOBEDONE", "DONE", "ALL"] = "TOBEDONE") -> int:
		"""获取所有举报类型的总数"""
		report_configs = [
			("comment", lambda: self._whale_obtain.fetch_comment_reports_total(source_type="ALL", status=status)),
			("post", lambda: self._whale_obtain.fetch_post_reports_total(status=status)),
			("discussion", lambda: self._whale_obtain.fetch_discussion_reports_total(status=status)),
		]
		total_reports = 0
		for _report_type, total_func in report_configs:
			total_info = total_func()
			total_reports += total_info.get("total", 0)
		return total_reports

	def fetch_all_reports(self, status: Literal["TOBEDONE", "DONE", "ALL"] = "TOBEDONE") -> Generator[ReportRecord]:
		report_configs: list[tuple[Literal["comment", "post", "discussion"], Callable[[], Generator[dict]]]] = [
			(
				"comment",
				lambda: self._whale_obtain.fetch_comment_reports_gen(source_type="ALL", status=status, limit=2000),
			),
			(
				"post",
				lambda: self._whale_obtain.fetch_post_reports_gen(status=status, limit=2000),
			),
			(
				"discussion",
				lambda: self._whale_obtain.fetch_discussion_reports_gen(status=status, limit=2000),
			),
		]
		# 处理数据生成器
		for report_type, gen_func in report_configs:
			report_generator = gen_func()
			for item in report_generator:
				item_ndd = data.NestedDefaultDict(item)
				type_config = self._get_type_config(report_type, item_ndd)
				yield ReportRecord(
					item=item_ndd,
					report_type=report_type,
					item_id=str(item_ndd[type_config["item_id_field"]]),
					content=item_ndd[type_config["content_field"]],
					processed=False,
					action=None,
				)

	@staticmethod
	def _get_type_config(report_type: str, item_ndd: data.NestedDefaultDict) -> dict:
		"""动态生成举报类型配置:根据类型返回字段映射、处理方法等"""
		configs = {
			"comment": {
				"content_field": "comment_content",  # 内容字段
				"user_field": "comment_user",  # 用户字段前缀
				"handle_method": "execute_process_comment_report",  # 处理方法
				"source_id_field": "comment_source_object_id",  # 来源ID字段
				"source_name_field": "comment_source_object_name",  # 来源名称字段
				"item_id_field": "comment_id",  # 唯一ID字段(评论ID)
				"special_check": lambda: item_ndd["comment_source"] == "WORK_SHOP",  # 特殊检查(是否为店铺评论)
			},
			"post": {
				"content_field": "post_title",  # 内容字段(帖子标题)
				"user_field": "post_user",  # 用户字段前缀
				"handle_method": "execute_process_post_report",  # 处理方法
				"source_id_field": "post_id",  # 来源ID字段(帖子ID)
				"item_id_field": "post_id",  # 唯一ID字段(帖子ID)
				"special_check": lambda: True,  # 帖子无需特殊检查
			},
			"discussion": {
				"content_field": "discussion_content",  # 内容字段(讨论内容)
				"user_field": "discussion_user",  # 用户字段前缀
				"handle_method": "execute_process_discussion_report",  # 处理方法
				"source_id_field": "post_id",  # 来源ID字段(所属帖子ID)
				"item_id_field": "discussion_id",  # 唯一ID字段(讨论ID)
				"special_check": lambda: True,  # 讨论无需特殊检查
			},
		}
		return configs[report_type]

	def _get_content_key(self, record: ReportRecord) -> tuple:
		"""生成内容唯一标识:用于分组同内容举报"""
		type_config = self._get_type_config(record["report_type"], record["item"])
		item_ndd = record["item"]
		# 键组成:(内容,举报类型,来源ID)→ 确保同内容不同来源不被误判
		return (
			item_ndd[type_config["content_field"]],
			record["report_type"],
			item_ndd[type_config["source_id_field"]],
		)

	def process_report_batch(self, report_gen_func: Callable[[], Generator[ReportRecord]], admin_id: int) -> int:
		"""批量处理举报:两次遍历生成器,第一次收集分组信息,第二次处理记录"""
		processed_count = 0
		# 第一次遍历: 收集分组信息(只记录ID和分组键)
		item_id_groups = defaultdict(list)  # item_id -> list[record_id]
		content_groups = defaultdict(list)  # content_key -> list[record_id]
		for record in report_gen_func():
			record_id = record["item"]["id"]
			item_id = record["item_id"]
			content_key = self._get_content_key(record)
			item_id_groups[item_id].append(record_id)
			content_groups[content_key].append(record_id)
		# 确定批量组,避免重复记录
		batch_groups = []
		processed_record_ids = set()
		# 同ID分组
		for item_id, record_ids in item_id_groups.items():
			if len(record_ids) >= self.batch_config["duplicate_threshold"]:
				# 将 record_ids 转换为元组,使其可哈希
				batch_groups.append(BatchGroup("item_id", item_id, tuple(record_ids)))
				processed_record_ids.update(record_ids)
		# 同内容分组
		for content_key, record_ids in content_groups.items():
			if len(record_ids) >= self.batch_config["content_threshold"]:
				filtered_record_ids = [rid for rid in record_ids if rid not in processed_record_ids]
				if len(filtered_record_ids) >= self.batch_config["content_threshold"]:
					# 生成内容摘要
					content_summary = f"{content_key[1]}:{content_key[0][:20]}..."  # content_key: (content, report_type, source_id)
					# 将 filtered_record_ids 转换为元组
					batch_groups.append(BatchGroup("content", content_summary, tuple(filtered_record_ids)))
					processed_record_ids.update(filtered_record_ids)
		# 如果没有批量组,则直接第二次遍历处理所有记录
		if not batch_groups:
			for record in report_gen_func():
				self.process_single_item(record, admin_id)
				processed_count += 1
			return processed_count
		# 构建记录ID到组的映射
		record_id_to_group = {}
		for group in batch_groups:
			for rid in group.record_ids:
				record_id_to_group[rid] = group
		# 第二次遍历: 处理记录
		# 使用字典来存储每个组的记录,键为组的唯一标识
		groups_records = {}
		for group in batch_groups:
			# 使用 (group_type, group_key) 作为唯一标识
			groups_records[group.group_type, group.group_key] = []
		for record in report_gen_func():
			record_id = record["item"]["id"]
			if record_id in record_id_to_group:
				group = record_id_to_group[record_id]
				# 使用 (group_type, group_key) 作为键
				groups_records[group.group_type, group.group_key].append(record)
			else:
				self.process_single_item(record, admin_id)
				processed_count += 1
		# 处理批量组
		for group in batch_groups:
			group_key = (group.group_type, group.group_key)
			records = groups_records.get(group_key, [])
			self._handle_batch_group(group, records, admin_id)
			processed_count += len(records)
		return processed_count

	def _handle_batch_group(self, group: BatchGroup, records: list[ReportRecord], admin_id: int) -> None:
		"""处理一个批量组:首先处理第一个记录,然后应用动作到组内其他记录"""
		self.printer.print_message(f"处理批量组 [{group.group_type}] {group.group_key} (共{len(records)}条举报)", "INFO")
		if not records:
			return
		# 处理第一个记录
		first_action = self.process_single_item(records[0], admin_id, batch_mode=True)
		if first_action is not None:
			for record in records[1:]:
				if group.group_type == "item_id":
					self._apply_action(record, "P", admin_id)  # 同ID分组自动通过
				else:
					self._apply_action(record, first_action, admin_id)
		else:
			# 如果第一个记录跳过,则处理其余记录为单条
			for record in records[1:]:
				self.process_single_item(record, admin_id)

	def _create_batch_groups(
		self,
		item_id_map: defaultdict[str, list[ReportRecord]],
		content_map: defaultdict[tuple, list[ReportRecord]],
	) -> list[tuple[str, str, list[ReportRecord]]]:
		"""创建批量处理组:避免重复分组,优先处理ID分组"""
		batch_groups = []
		processed_records = set()  # 记录已分组的举报记录ID
		# 1. 优先处理同ID分组:重复举报同一对象
		for item_id, records in item_id_map.items():
			if len(records) >= self.batch_config["duplicate_threshold"]:
				# 标记这些记录为已处理
				for record in records:
					record_id = record["item"]["id"]
					if record_id != "UNKNOWN":
						processed_records.add(record_id)
				batch_groups.append(("item_id", item_id, records))
		# 2. 处理同内容分组:排除已分组的记录
		for (content, report_type, _), records in content_map.items():
			if len(records) >= self.batch_config["content_threshold"]:
				# 过滤掉已经在ID分组中的记录
				filtered_records = []
				for record in records:
					record_id = record["item"]["id"]
					if record_id != "UNKNOWN" and record_id not in processed_records:
						filtered_records.append(record)
				# 如果过滤后仍然满足阈值,则添加到批量组
				if len(filtered_records) >= self.batch_config["content_threshold"]:
					content_summary = f"{report_type}:{content[:20]}..."  # 内容摘要
					batch_groups.append(("content", content_summary, filtered_records))
					# 更新已处理的记录
					for record in filtered_records:
						record_id = record["item"]["id"]
						if record_id != "UNKNOWN":
							processed_records.add(record_id)
		return batch_groups

	def _handle_batch_groups(self, batch_groups: list, admin_id: int) -> None:
		"""处理批量分组:展示分组 → 查看详情 → 确认处理 → 自动应用动作"""
		# 1. 展示批量分组信息
		self.printer.print_message("发现以下批量处理项:", "INFO")
		for idx, (group_type, group_key, records) in enumerate(batch_groups, 1):
			self.printer.print_message(f"{idx}. [{group_type}] {group_key} ({len(records)}次举报)", "INFO")
		# 2. 查看分组详情(可选)
		if self.printer.get_valid_input(prompt="是否查看详情?(Y/N)", valid_options={"Y", "N"}).upper() == "Y":
			for group_type, group_key, records in batch_groups:
				self.printer.print_header(f"=== {group_type}组: {group_key} ===")
				# 仅展示前3条详情
				for record in records[:3]:
					create_time = record["item"]["created_at"]
					create_time_str = self._tool.TimeUtils().format_timestamp(create_time) if create_time != "UNKNOWN" else "未知"
					self.printer.print_message(f"举报ID: {record['item']['id']} | 时间: {create_time_str}", "INFO")
				# 多于3条时提示省略
				if len(records) > 3:  # noqa: PLR2004
					self.printer.print_message(f"...及其他{len(records) - 3}条举报", "INFO")
		# 3. 确认是否批量处理
		if self.printer.get_valid_input(prompt="确认批量处理这些项目?(Y/N)", valid_options={"Y", "N"}).upper() != "Y":
			return
		# 4. 执行批量处理
		for group_type, group_key, records in batch_groups:
			self.printer.print_message(f"正在处理 [{group_type}] {group_key}...", "INFO")
			first_action = None
			# 处理首个项目(作为同组的模板动作)
			if records and not records[0]["processed"]:
				first_action = self.process_single_item(records[0], admin_id, batch_mode=True)
			# 自动应用动作到同组其他项目
			if first_action:
				for record in records[1:]:
					if not record["processed"]:
						# 同ID分组:自动通过(同一对象多次举报可能为误报)
						if group_type == "item_id":
							self._apply_action(record, "P", admin_id)
							self.printer.print_message(f"已自动通过举报ID: {record['item']['id']}", "SUCCESS")
						# 同内容分组:复用首个动作
						else:
							self._apply_action(record, first_action, admin_id)
							self.printer.print_message(f"已自动处理举报ID: {record['item']['id']}", "SUCCESS")

	def process_single_item(self, record: ReportRecord, admin_id: int, *, batch_mode: bool = False, reprocess_mode: bool = False) -> str | None:  # noqa: PLR0912, PLR0915
		"""处理单个举报项目:展示详情 → 官方账号判断 → 操作选择 → 执行动作"""
		item_ndd = record["item"]  # NestedDefaultDict 实例
		report_type = record["report_type"]
		type_config = self._get_type_config(report_type, item_ndd)
		# 头部信息:区分批量模式/重新处理模式
		if batch_mode:
			self.printer.print_header("=== 批量处理首个项目 ===")
		elif reprocess_mode:
			self.printer.print_header("=== 重新处理项目 ===")
		# 1. 展示举报详情
		self.printer.print_header("=== 举报详情 ===")
		self.printer.print_message(f"举报ID: {item_ndd['id']}", "INFO")  # 直接访问,缺失返回"UNKNOWN"
		self.printer.print_message(f"举报类型: {report_type}", "INFO")
		# 2. 展示举报内容(HTML转文本,避免标签干扰)
		content = item_ndd[type_config["content_field"]]
		if content != "UNKNOWN":
			content_text = self._tool.DataConverter().html_to_text(content)
			self.printer.print_message(f"举报内容: {content_text}", "INFO")
		else:
			self.printer.print_message("举报内容: 无内容", "INFO")
		# 3. 展示所属板块(优先取board_name,其次取来源名称)
		board_name = item_ndd["board_name"]
		if board_name == "UNKNOWN":
			board_name = item_ndd[type_config["source_name_field"]] if "source_name_field" in type_config else "UNKNOWN"
		self.printer.print_message(f"所属板块: {board_name}", "INFO")
		# 4. 展示被举报人信息(昵称 + 是否官方账号)
		user_field = type_config["user_field"]
		# 昵称:优先取nick_name,其次取nickname(兼容不同字段名)
		user_nickname = item_ndd[f"{user_field}_nick_name"]
		if user_nickname == "UNKNOWN":
			user_nickname = item_ndd[f"{user_field}_nickname"]
		self.printer.print_message(f"被举报人: {user_nickname}", "INFO")
		# 官方账号判断:如果是官方账号,自动通过(无需处罚)
		user_id_str = item_ndd[f"{user_field}_id"]
		user_id = int(user_id_str) if user_id_str != "UNKNOWN" and user_id_str.isdigit() else None
		if user_id and user_id in self.OFFICIAL_IDS:
			self.printer.print_message("这是一条官方发布的内容,自动通过", "WARNING")
			# 执行通过动作
			handle_method = getattr(self._whale_motion, type_config["handle_method"])
			handle_method(report_id=item_ndd["id"], resolution="PASS", admin_id=admin_id)
			record["processed"] = True
			record["action"] = "P"
			self.printer.print_message("已通过", "SUCCESS")
			return "P"
		# 5. 展示其他详情(举报原因、举报时间、帖子线索)
		self.printer.print_message(f"举报原因: {item_ndd['reason_content']}", "INFO")
		# 举报时间:格式化工单时间戳
		create_time = item_ndd["created_at"]
		if create_time != "UNKNOWN":
			create_time_str = self._tool.TimeUtils().format_timestamp(create_time)
			self.printer.print_message(f"举报时间: {create_time_str}", "INFO")
		else:
			self.printer.print_message("举报时间: 未知", "INFO")
		# 帖子类型额外展示线索(其他类型无此字段)
		if report_type == "post":
			self.printer.print_message(f"举报线索: {item_ndd['description']}", "INFO")
		# 6. 操作选择循环:直到选择有效动作
		while True:
			choice = self.printer.get_valid_input(
				prompt="选择操作: D(删除), S(禁言7天), T(禁言3月), P(通过), C(查看详情), F(检查违规), J(跳过)", valid_options={"D", "S", "T", "P", "C", "F", "J"}
			).upper()
			# 执行处理动作(删除/禁言/通过)
			if choice in self.STATUS_MAP:
				handle_method = getattr(self._whale_motion, type_config["handle_method"])
				handle_method(report_id=item_ndd["id"], resolution=self.STATUS_MAP[choice], admin_id=admin_id)
				record["processed"] = True
				record["action"] = choice
				self.printer.print_message(f"已执行操作: {self.STATUS_MAP[choice]}", "SUCCESS")
				return choice
			# 查看详情:展示更多信息(链接、完整内容等)
			if choice == "C":
				self._show_item_details(item_ndd, report_type, type_config)
			# 检查违规:仅满足special_check才执行(如店铺评论需额外检查)
			elif choice == "F" and type_config["special_check"]():
				adjusted_source_type: Literal["shop", "discussion", "post"] = self.SOURCE_TYPE_MAP[report_type]
				self._check_violation(source_id=item_ndd[type_config["source_id_field"]], source_type=adjusted_source_type, board_name=board_name, user_id=user_id_str)
			# 跳过:不处理当前举报
			elif choice == "J":
				self.printer.print_message("已跳过该举报", "INFO")
				return None
			# 无效输入:提示重新选择
			else:
				self.printer.print_message("无效操作,请重新选择", "ERROR")

	def _apply_action(self, record: ReportRecord, action: str, admin_id: int) -> None:
		"""应用处理动作到举报记录"""
		type_config = self._get_type_config(record["report_type"], record["item"])
		handle_method = getattr(self._whale_motion, type_config["handle_method"])
		handle_method(report_id=record["item"]["id"], resolution=self.STATUS_MAP[action], admin_id=admin_id)
		record["processed"] = True
		record["action"] = action
		self.printer.print_message(f"已应用操作: {self.STATUS_MAP[action]}", "SUCCESS")

	def _show_item_details(self, item_ndd: data.NestedDefaultDict, report_type: Literal["comment", "post", "discussion"], type_config: dict) -> None:
		"""展示举报项目详细信息:链接、完整内容、用户链接等"""
		self.printer.print_header("=== 详细信息 ===")
		# 1. 不同类型举报的详情链接
		if report_type == "comment":
			# 评论:违规板块链接
			source_id = item_ndd[type_config["source_id_field"]]
			if source_id != "UNKNOWN":
				self.printer.print_message(f"违规板块链接: https://shequ.codemao.cn/work_shop/{source_id}", "INFO")
		elif report_type == "post":
			# 帖子:违规帖子链接 + 完整内容
			post_id = item_ndd[type_config["source_id_field"]]
			if post_id != "UNKNOWN":
				self.printer.print_message(f"违规帖子链接: https://shequ.codemao.cn/community/{post_id}", "INFO")
				# 获取并展示帖子完整内容
				self.printer.print_header("=== 帖子完整内容 ===")
				try:
					post_details = self._forum_obtain.fetch_posts_details(post_ids=int(post_id))
					post_details_ndd = data.NestedDefaultDict(post_details)
					post_content = post_details_ndd["items"][0]["content"]
					content_text = self._tool.DataConverter().html_to_text(post_content)
					self.printer.print_message(content_text, "INFO")
				except (KeyError, IndexError, ValueError, TypeError) as e:
					self.printer.print_message(f"获取帖子内容失败: {e!s}", "ERROR")
		elif report_type == "discussion":
			# 讨论:所属帖子标题 + 帖主链接 + 所属帖子链接
			post_title = item_ndd["post_title"]
			self.printer.print_message(f"所属帖子标题: {post_title}", "INFO")
			post_user_id = item_ndd["post_user_id"]
			if post_user_id != "UNKNOWN":
				self.printer.print_message(f"所属帖子帖主链接: https://shequ.codemao.cn/user/{post_user_id}", "INFO")
			source_id = item_ndd[type_config["source_id_field"]]
			if source_id != "UNKNOWN":
				self.printer.print_message(f"所属帖子链接: https://shequ.codemao.cn/community/{source_id}", "INFO")
		# 2. 违规用户链接
		user_field = type_config["user_field"]
		user_id = item_ndd[f"{user_field}_id"]
		if user_id != "UNKNOWN":
			self.printer.print_message(f"违规用户链接: https://shequ.codemao.cn/user/{user_id}", "INFO")
		# 3. 展示发送时间(评论/讨论/帖子的时间获取逻辑不同)
		self._show_item_create_time(item_ndd, report_type, type_config)

	def _show_item_create_time(self, item_ndd: data.NestedDefaultDict, report_type: Literal["comment", "post", "discussion"], type_config: dict) -> None:
		"""展示举报对象的发送时间:区分评论/讨论/帖子"""
		try:
			if report_type in {"comment", "discussion"}:
				# 评论/讨论:从评论列表中获取发送时间
				source_type = "shop" if report_type == "comment" and item_ndd["comment_source"] == "WORK_SHOP" else "work"
				source_id = item_ndd[type_config["source_id_field"]]
				if source_id == "UNKNOWN":
					self.printer.print_message("无效的来源ID,无法获取发送时间", "WARNING")
					return
				# 获取评论详情列表
				comments = Obtain().get_comments_detail(com_id=source_id, source=source_type, method="comments", max_limit=200)
				comments_dict = {comment["id"]: comment for comment in comments}
				comments_ndd = data.NestedDefaultDict(comments_dict)
				item_id = item_ndd[type_config["item_id_field"]]
				parent_id = item_ndd["comment_parent_id"]  # 评论的父ID(回复时非0)
				# 回复类型:父ID非0,需从父评论的回复列表中找
				if report_type == "comment" and parent_id not in {"0", "UNKNOWN"}:
					for comment in comments_ndd:
						if comment["id"] == parent_id:
							for reply in comment["replies"]:
								if reply["id"] == item_id:
									create_time = reply["created_at"]
									create_time_str = self._tool.TimeUtils().format_timestamp(create_time)
									self.printer.print_message(f"发送时间: {create_time_str}", "INFO")
									return
				# 普通评论/讨论:直接从评论列表中找
				else:
					for comment in comments_ndd:
						if comment["id"] == item_id:
							create_time = comment["created_at"]
							create_time_str = self._tool.TimeUtils().format_timestamp(create_time)
							self.printer.print_message(f"发送时间: {create_time_str}", "INFO")
							return
				# 未找到对应评论
				self.printer.print_message("未找到对应评论/讨论的发送时间", "WARNING")
			else:  # post 类型:从帖子详情中获取发送时间
				post_id = item_ndd[type_config["source_id_field"]]
				if post_id != "UNKNOWN":
					post_details = self._forum_obtain.fetch_single_post_details(post_id=post_id)
					post_details_ndd = data.NestedDefaultDict(post_details)
					create_time = post_details_ndd["created_at"]
					create_time_str = self._tool.TimeUtils().format_timestamp(create_time)
					self.printer.print_message(f"发送时间: {create_time_str}", "INFO")
		except Exception as e:
			self.printer.print_message(f"获取发送时间失败: {e!s}", "ERROR")

	def _check_violation(self, source_id: ..., source_type: Literal["shop", "work", "discussion", "post"], board_name: str, user_id: str | None) -> None:
		"""检查举报内容违规:评论违规分析 + 帖子重复检查"""
		# 转换source_id为int(避免字符串类型)
		source_id = int(source_id) if source_id != "UNKNOWN" and str(source_id).isdigit() else 0
		if not source_id:
			self.printer.print_message("无效的来源ID,无法检查违规", "ERROR")
			return
		adjusted_type = "post" if source_type == "discussion" else source_type  # 讨论归为帖子类型
		# 分析违规评论
		violations = self._analyze_comment_violations(source_id=source_id, source_type=adjusted_type, board_name=board_name)
		if not violations:
			self.printer.print_message("未检测到违规评论", "INFO")
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
					self.printer.print_message(f"警告:用户{user_id} 已连续发布标题为【{board_name}】的帖子 {len(user_posts)} 次(疑似垃圾帖)", "WARNING")
			except Exception as e:
				self.printer.print_message(f"搜索帖子失败: {e!s}", "ERROR")

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
			self.printer.print_message(f"分析评论违规失败: {e!s}", "ERROR")
			return []

	def _process_auto_report(self, violations: list[str], source_id: int, source_type: Literal["post", "work", "shop"]) -> None:  # noqa: PLR0912, PLR0914, PLR0915
		"""处理自动举报:用学生账号批量举报违规评论"""
		# 1. 检查学生账号是否可用
		if not (self.auth_manager.student_accounts or self.auth_manager.student_tokens):
			self.printer.print_message("未加载学生账号,无法执行自动举报", "WARNING")
			return
		# 2. 询问是否执行自动举报
		if self.printer.get_valid_input(prompt="是否自动举报违规评论? (Y/N)", valid_options={"Y", "N"}).upper() != "Y":
			self.printer.print_message("自动举报操作已取消", "INFO")
			return
		# 3. 获取举报原因(固定取第7个原因,需确保社区接口返回正常)
		try:
			report_reasons = self._community_obtain.fetch_report_reasons()
			report_reasons_ndd = data.NestedDefaultDict(report_reasons)
			reason_content = report_reasons_ndd["items"][7]["content"]
		except (KeyError, IndexError) as e:
			self.printer.print_message(f"获取举报原因失败: {e!s}", "ERROR")
			return
		# 4. 来源类型映射(适配不同模块的举报接口)
		source_key_map: dict[Literal["work", "post", "shop"], Literal["work", "forum", "shop"]] = {
			"work": "work",  # 作品 → 作品模块
			"post": "forum",  # 帖子 → 论坛模块
			"shop": "shop",  # 店铺 → 店铺模块
		}
		source_key = source_key_map[source_type]
		# 5. 自动举报循环:切换账号 → 执行举报 → 计数
		report_counter = -1  # 账号切换计数器(-1表示首次切换)
		# 复制可用账号列表(避免修改原列表)
		# 修复1:根据 auth_method 复制对应账号列表(而非判断是否为空)
		available_accounts = self.auth_manager.student_accounts.copy() if self.auth_manager.auth_method == "grab" else self.auth_manager.student_tokens.copy()
		self.printer.print_message(f"开始自动举报(共 {len(violations)} 条违规内容)", "INFO")
		for idx, violation in enumerate(violations, 1):
			# 切换学生账号:达到阈值或首次执行时切换(避免单账号限流)
			if report_counter >= self._setting.PARAMETER.report_work_max or report_counter == -1:
				if not available_accounts:
					self.printer.print_message("所有学生账号已耗尽,自动举报终止", "WARNING")
					break
				# 更新账号管理类的可用账号(避免重复使用)
				if self.auth_manager.auth_method == "grab":
					self.auth_manager.student_accounts = available_accounts
				else:
					self.auth_manager.student_tokens = available_accounts  # pyright: ignore[reportAttributeAccessIssue]
				# 切换账号:失败则跳过当前违规
				if not self.auth_manager.switch_to_student_account():
					continue
				report_counter = 0  # 重置计数器
			# 获取当前学生账号ID(用于举报接口)
			try:
				user_details = self._user_obtain.fetch_account_details()
				user_details_ndd = data.NestedDefaultDict(user_details)
				reporter_id = user_details_ndd["id"]
				if reporter_id == "UNKNOWN":
					msg = "获取学生账号ID失败"
					raise ValueError(msg)  # noqa: TRY301
			except Exception as e:
				self.printer.print_message(f"获取学生账号信息失败: {e!s}", "ERROR")
				report_counter += 1
				continue
			# 解析违规内容格式:item_id.comment_id:内容(如 123.456:广告内容)
			violation_parts = violation.split(":")
			if len(violation_parts) < 2:  # noqa: PLR2004
				self.printer.print_message(f"违规内容格式错误: {violation}", "ERROR")
				report_counter += 1
				continue
			item_id_part = violation_parts[0].split(".")
			if len(item_id_part) < 2:  # noqa: PLR2004
				self.printer.print_message(f"违规ID格式错误: {violation_parts[0]}", "ERROR")
				report_counter += 1
				continue
			_, comment_id = item_id_part
			is_reply = "reply" in violation  # 是否为回复(非普通评论)
			# 查找父评论ID(回复时需传入父ID)
			parent_id, _ = self._tool.StringProcessor().find_substrings(text=comment_id, candidates=violations)
			parent_id = int(parent_id) if parent_id and parent_id != "UNKNOWN" else None
			# 执行举报操作
			try:
				if self._execute_report_action(
					source_key=source_key,
					target_id=int(comment_id),
					source_id=source_id,
					reason_id=7,  # 固定举报原因ID(与之前获取的原因对应)
					reporter_id=int(reporter_id),
					reason_content=reason_content,
					parent_id=parent_id,
					is_reply=is_reply,
				):
					self.printer.print_message(f"[{idx}/{len(violations)}] 举报成功: {violation}", "SUCCESS")
				else:
					self.printer.print_message(f"[{idx}/{len(violations)}] 举报失败: {violation}", "ERROR")
				report_counter += 1
			except Exception as e:
				self.printer.print_message(f"执行举报异常: {e!s}", "ERROR")
				report_counter += 1
		# 6. 举报完成:恢复管理员账号
		self.auth_manager._restore_admin_account()  # noqa: SLF001
		self.printer.print_message("自动举报完成,已恢复管理员账号", "SUCCESS")

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
			self.printer.print_message(f"举报操作失败: {e!s}", "ERROR")
			return False
		else:
			return False


@decorator.singleton
class ReportAuthManager(ClassUnion):
	def __init__(self) -> None:
		self.student_accounts = []
		self.student_tokens = []
		self.auth_method = "grab"
		self.processor = ReportProcessor()
		self.printer = tool.Printer()
		super().__init__()

	def execute_admin_login(self) -> None:
		"""执行管理员登录(支持Token/账密两种方式)"""
		self.printer.print_header("=== 登录管理后台 ===")
		choice = self.printer.get_valid_input(prompt="请选择登录方式: 1.Token登录 2.账密登录", valid_options={"1", "2"})
		if choice == "1":
			self._handle_token_login()
		else:
			self._handle_password_login()

	def _handle_token_login(self) -> None:
		"""处理Token登录:直接配置认证Token"""
		token = self.printer.prompt_input("请输入 Authorization Token")
		self._whale_routine.configure_authentication_token(token)
		self.printer.print_message("Token登录成功", "SUCCESS")

	def _handle_password_login(self) -> None:
		"""处理账密登录:支持验证码重试,优化错误处理"""

		def input_account() -> tuple[str, str]:
			"""内部函数:获取用户名和密码(统一命名为account)"""
			username = self.printer.prompt_input("请输入用户名")
			password = self.printer.prompt_input("请输入密码")
			return username, password

		def input_captcha(timestamp: int) -> tuple[str, Any]:
			"""内部函数:获取验证码和Cookie"""
			self.printer.print_message("正在获取验证码...", "INFO")
			cookies = self._whale_routine.fetch_verification_captcha(timestamp=timestamp)
			captcha = self.printer.prompt_input("请输入验证码")
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
				self.printer.print_message("账密登录成功", "SUCCESS")
				break
			# 登录失败:根据错误码处理
			if "error_code" in response:
				self.printer.print_message(response["error_msg"], "ERROR")
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
		if self.printer.get_valid_input(prompt="是否加载学生账号用于自动举报? (Y/N)", valid_options={"Y", "N"}).upper() != "Y":
			self.printer.print_message("未加载学生账号,自动举报功能不可用", "WARNING")
			self._restore_admin_account()
			return
		# 选择账号获取方式(实时获取/文件加载)
		method = self.printer.get_valid_input(prompt="选择模式(load.加载文件 grab.实时获取)", valid_options={"load", "grab"}, cast_type=str)
		self.auth_method = cast("Literal['load', 'grab']", method)
		try:
			if method == "grab":
				# 实时获取学生账号(调用Obtain工具)
				account_count = self.printer.get_valid_input(
					prompt="输入获取账号数",
					cast_type=int,
					validator=lambda x: x >= 0,  # 确保数量非负
				)
				self.student_accounts = list(Obtain().switch_edu_account(limit=account_count, return_method="list"))
				self.printer.print_message(f"已实时加载 {len(self.student_accounts)} 个学生账号", "SUCCESS")
			elif method == "load":
				# 从文件加载学生账号Token(文件路径在data模块定义)
				token_list = self._file.read_line(data.TOKEN_DIR)
				self.student_tokens = [token.strip() for token in token_list if token.strip()]  # 过滤空行
				self.printer.print_message(f"已从文件加载 {len(self.student_tokens)} 个学生账号Token", "SUCCESS")
		except Exception as e:
			# 捕获所有异常(文件不存在、接口错误等)
			self.printer.print_message(f"加载学生账号失败: {e!s}", "ERROR")
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
				self.printer.print_message(f"切换学生账号: {id(username)}", "INFO")
				sleep(2)  # 避免接口限流
				self._community_login.authenticate_with_token(
					identity=username,
					password=password,
					status="edu",  # 教育账号标识
				)
			else:
				# 文件加载的账号:用Token切换
				token = cast("str", selected_account)
				self.printer.print_message(f"切换学生账号: {id(token)}", "INFO")
				self._client.switch_account(token=token, identity="edu")
		except Exception as e:
			self.printer.print_message(f"学生账号切换失败: {e!s}", "ERROR")
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
		self.printer.print_message("已终止会话并恢复管理员账号", "INFO")


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
		打印上传历史记录(支持分页、详细查看和链接验证)
		Args:
			limit: 每页显示记录数(默认10条)
			reverse: 是否按时间倒序显示(最新的在前)
		"""
		history_list = self._upload_history.data.history
		if not history_list:
			print("暂无上传历史记录")
			return
		# 排序历史记录
		sorted_history = sorted(
			history_list,
			key=lambda x: x.upload_time,
			reverse=reverse,
		)
		total_records = len(sorted_history)
		max_page = (total_records + limit - 1) // limit
		page = 1
		while True:
			# 获取当前页数据
			start = (page - 1) * limit
			end = min(start + limit, total_records)
			page_data = sorted_history[start:end]
			# 打印当前页
			self._print_current_page(page, max_page, total_records, start, end, page_data)
			# 处理用户操作
			action = input("请输入操作: ").strip().lower()
			if action == "q":
				break
			if action == "n" and page < max_page:
				page += 1
			elif action == "p" and page > 1:
				page -= 1
			elif action.startswith("d"):
				try:
					record_id = int(action[1:])
					if 1 <= record_id <= total_records:
						self._show_record_detail(sorted_history[record_id - 1])
					else:
						print(f"错误:ID超出范围(1-{total_records})")
				except ValueError:
					print("错误:无效的ID格式(正确格式:d1,d2等)")
			else:
				print("错误:无效操作或超出页码范围")

	def _print_current_page(self, page: int, max_page: int, total_records: int, start: int, end: int, page_data: list) -> None:
		"""打印当前分页的所有内容"""
		print(f"\n上传历史记录(第{page}/{max_page}页):")
		print(f"{'ID':<3} | {'文件名':<25} | {'时间':<19} | {'URL(类型)'}")
		print("-" * 85)
		for i, record in enumerate(page_data, start + 1):
			upload_time = record.upload_time
			if isinstance(upload_time, (int, float)):
				upload_time = self._tool.TimeUtils().format_timestamp(upload_time)
			formatted_time = str(upload_time)[:19]
			file_name = record.file_name.replace("\\", "/")[:25]
			url = record.save_url.replace("\\", "/")
			url_type = "[other]"
			simplified_url = url[:30] + "..." if len(url) > 30 else url  # noqa: PLR2004
			parsed_url = urlparse(url)
			host = parsed_url.hostname
			if host == "static.codemao.cn":
				cn_index = url.find(".cn")
				simplified_url = url[cn_index + 3 :].split("?")[0] if cn_index != -1 else url.split("/")[-1].split("?")[0]
				url_type = "[static]"
			elif host and (host == "cdn-community.bcmcdn.com" or host.endswith(".cdn-community.bcmcdn.com")):  # cSpell: ignore bcmcdn
				com_index = url.find(".com")
				simplified_url = url[com_index + 4 :].split("?")[0] if com_index != -1 else url.split("/")[-1].split("?")[0]
				url_type = "[cdn]"
			print(f"{i:<3} | {file_name:<25} | {formatted_time:<19} | {url_type}{simplified_url}")
		print(f"共 {total_records} 条记录 | 当前显示: {start + 1}-{end}")
		print("\n操作选项:")
		print("n:下一页 p:上一页 d[ID]:查看详情(含链接验证) q:退出")

	def _show_record_detail(self, record: data.UploadHistory) -> None:
		"""显示单条记录的详细信息并验证链接"""
		# 格式化上传时间
		upload_time = record.upload_time
		if isinstance(upload_time, (int, float)):
			upload_time = self._tool.TimeUtils().format_timestamp(upload_time)
		print("\n文件上传详情:")
		print("-" * 60)
		print(f"文件名: {record.file_name}")
		print(f"文件大小: {record.file_size}")
		print(f"上传方式: {record.method}")
		print(f"上传时间: {upload_time}")
		print(f"完整URL: {record.save_url}")
		# 验证链接有效性
		is_valid = self._validate_url(record.save_url)
		status = "有效" if is_valid else "无效"
		print(f"链接状态: {status}")
		if record.save_url.startswith("http"):
			print("\n提示:复制上方URL到浏览器可直接访问或下载")
		print("-" * 60)
		input("按Enter键返回...")

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
