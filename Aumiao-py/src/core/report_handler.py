import time
from collections import defaultdict
from collections.abc import Generator
from random import randint
from typing import Literal, cast

from src.core.obtain import Obtain

from .base import ReportRecord
from .union import ClassUnion


class ReportHandler(ClassUnion):
	def handle_report(self, admin_id: int) -> None:
		"""处理举报核心逻辑"""
		batch_config = {
			"total_threshold": 15,
			"duplicate_threshold": 5,
			"content_threshold": 3,
		}

		def get_content_key(record: ReportRecord) -> tuple:
			cfg = self._get_type_config(record["report_type"], record["item"])
			return (
				record["item"][cfg["content_field"]],
				record["report_type"],
				record["item"][cfg["source_id_field"]],
			)

		def process_report_batch(records: list[ReportRecord]) -> None:  # noqa: PLR0912
			id_map = defaultdict(list)
			content_map = defaultdict(list)

			for record in records:
				id_map[record["com_id"]].append(record)
				content_key = get_content_key(record)
				content_map[content_key].append(record)

			batch_groups = [("ID", items[0]["com_id"], items) for items in id_map.values() if len(items) >= batch_config["duplicate_threshold"]]

			for (content, report_type, _), items in content_map.items():
				if len(items) >= batch_config["content_threshold"]:
					batch_groups.append(("内容", f"{report_type}:{content[:20]}...", items))

			if batch_groups and len(records) >= batch_config["total_threshold"]:
				print("\n发现以下批量处理项:")
				for i, (g_type, g_key, items) in enumerate(batch_groups, 1):
					print(f"{i}. [{g_type}] {g_key} ({len(items)}次举报)")

				if input("\n是否查看详情?(Y/N) ").upper() == "Y":
					for g_type, g_key, items in batch_groups:
						print(f"\n=== {g_type}组: {g_key} ===")
						for item in items[:3]:
							print(f"举报ID: {item['item']['id']} | 时间: {self.tool.TimeUtils().format_timestamp(float(item['item']['created_at']))}")
						if len(items) > batch_config["content_threshold"]:
							print(f"...及其他{len(items) - 3}条举报")

				if input("\n确认批量处理这些项目?(Y/N) ").upper() == "Y":
					for g_type, g_key, items in batch_groups:
						print(f"\n正在处理 [{g_type}] {g_key}...")
						first_action = None

						if not items[0]["processed"]:
							first_action = self._process_single_item(items[0], admin_id, batch_mode=True)

						if first_action:
							for item in items[1:]:
								if not item["processed"]:
									self._apply_action(item, first_action, admin_id)
									print(f"已自动处理举报ID: {item['item']['id']}")

			for record in records:
				if not record["processed"]:
					self._process_single_item(record, admin_id)

		all_records: list[ReportRecord] = []
		for report_list, report_type in [
			(self.whale_obtain.fetch_comment_reports_generator(source_type="ALL", status="TOBEDONE", limit=None), "comment"),
			(self.whale_obtain.fetch_post_reports_generator(status="TOBEDONE", limit=None), "post"),
			(self.whale_obtain.fetch_discussion_reports_generator(status="TOBEDONE", limit=None), "discussion"),
		]:
			for item in report_list:
				cfg = self._get_type_config(report_type, item)
				all_records.append(
					{
						"item": item,
						"report_type": cast("Literal['comment', 'post', 'discussion']", report_type),
						"com_id": str(item[cfg["com_id"]]),
						"content": item[cfg["content_field"]],
						"processed": False,
						"action": None,
					},
				)
		process_report_batch(all_records)
		self.acquire.switch_account(token=self.acquire.token.average, identity="average")

	@staticmethod
	def _get_type_config(report_type: str, current_item: dict) -> dict:
		return {
			"comment": {
				"content_field": "comment_content",
				"user_field": "comment_user",
				"handle_method": "process_comment_report",
				"source_id_field": "comment_source_object_id",
				"source_name_field": "comment_source_object_name",
				"special_check": lambda i=current_item: i.get("comment_source") == "WORK_SHOP",
				"com_id": "comment_id",
			},
			"post": {
				"content_field": "post_title",
				"user_field": "post_user",
				"handle_method": "process_post_report",
				"source_id_field": "post_id",
				"special_check": lambda: True,
				"com_id": "post_id",
			},
			"discussion": {
				"content_field": "discussion_content",
				"user_field": "discussion_user",
				"handle_method": "process_discussion_report",
				"source_id_field": "post_id",
				"special_check": lambda: True,
				"com_id": "discussion_id",
			},
		}[report_type]

	def _process_single_item(self, record: ReportRecord, admin_id: int, *, batch_mode: bool = False) -> str | None:
		item = record["item"]
		report_type = record["report_type"]
		cfg = self._get_type_config(report_type, item)
		if batch_mode:
			print(f"\n{'=' * 30} 批量处理首个项目 {'=' * 30}")
		print(f"\n{'=' * 50}")
		print(f"举报ID: {item['id']}")
		print(f"举报内容: {item[cfg['content_field']]}")
		print(f"所属板块: {item.get('board_name', item.get(cfg.get('source_name_field', ''), ''))}")
		cfg_user_field = cfg["user_field"]
		if report_type == "post":
			print(f"被举报人: {item[f'{cfg_user_field}_nick_name']}")
		else:
			print(f"被举报人: {item[f'{cfg_user_field}_nickname']}")
		print(f"举报原因: {item['reason_content']}")
		print(f"举报时间: {self.tool.TimeUtils().format_timestamp(float(item['created_at']))}")
		if report_type == "post":
			print(f"举报线索: {item['description']}")

		while True:
			choice = input("选择操作: D:删除, S:禁言7天, T:禁言3月 P:通过, C:查看, F:检查违规, J:跳过  ").upper()
			if choice in {"D", "S", "T", "P"}:
				status_map = {"D": "DELETE", "S": "MUTE_SEVEN_DAYS", "P": "PASS", "T": "MUTE_THREE_MONTHS"}
				handler = getattr(self.whale_motion, cfg["handle_method"])
				handler(report_id=item["id"], resolution=status_map[choice], admin_id=admin_id)
				record["processed"] = True
				return choice
			if choice == "C":
				self._show_details(item, report_type, cfg)
			elif choice == "F" and cfg["special_check"]():
				source_map = {
					"comment": "shop" if item.get("comment_source") == "WORK_SHOP" else "work",
					"post": "post",
					"discussion": "discussion",
				}
				self._check_report(
					source_id=item[cfg["source_id_field"]],
					source_type=cast("Literal['shop', 'work', 'discussion', 'post']", source_map[report_type]),
					title=item.get("board_name", item.get(cfg.get("source_name_field", ""), "")),
					user_id=item[f"{cfg['user_field']}_id"],
				)
			elif choice == "J":
				print("已跳过")
				return None
			else:
				print("无效输入")

	def _apply_action(self, record: ReportRecord, action: str, admin_id: int) -> None:
		cfg = self._get_type_config(record["report_type"], record["item"])
		handler = getattr(self.whale_motion, cfg["handle_method"])
		handler(
			report_id=record["item"]["id"],
			resolution={"D": "DELETE", "S": "MUTE_SEVEN_DAYS", "P": "PASS"}[action],
			admin_id=admin_id,
		)
		record["processed"] = True

	def _show_details(self, item: dict, report_type: Literal["comment", "post", "discussion"], cfg: dict) -> None:
		"""显示详细信息"""
		if report_type == "comment":
			print(f"违规板块ID: https://shequ.codemao.cn/work_shop/{item[cfg['source_id_field']]}")
		elif report_type == "post":
			print(f"违规帖子ID: https://shequ.codemao.cn/community/{item[cfg['source_id_field']]}")
			print(f"\n{'=' * 30} 帖子内容 {'=' * 30}")
			post_id = item[cfg["source_id_field"]]  # 获取实际的帖子ID数值
			content = self.forum_obtain.fetch_posts_details(post_ids=int(post_id))["items"][0]["content"]
			print(content)
			print(self.tool.DataConverter().html_to_text(content))
		elif report_type == "discussion":
			print(f"所属帖子标题: {item['post_title']}")
			print(f"所属帖子帖主ID: https://shequ.codemao.cn/user/{item['post_user_id']}")
			print(f"所属帖子ID: https://shequ.codemao.cn/community/{item[cfg['source_id_field']]}")

		cfg_user_field = cfg["user_field"]
		print(f"违规用户ID: https://shequ.codemao.cn/user/{item[f'{cfg_user_field}_id']}")
		if report_type in {"comment", "discussion"}:
			source = "shop" if report_type == "comment" else "post"
			comments = Obtain().get_comments_detail_new(com_id=item[cfg["source_id_field"]], source=source, method="comments", max_limit=200)
			if report_type == "comment" and item["comment_parent_id"] != "0":
				for comment in comments:
					if comment["id"] == item["comment_parent_id"]:
						for reply in comment["replies"]:
							if reply["id"] == item["comment_id"]:
								print(f"发送时间: {self.tool.TimeUtils().format_timestamp(reply['created_at'])}")
								break
						break
			else:
				for comment in comments:
					if comment["id"] == item["comment_id"]:
						print(f"发送时间: {self.tool.TimeUtils().format_timestamp(comment['created_at'])}")
						break
		else:
			details = self.forum_obtain.fetch_single_post_details(post_id=item[cfg["source_id_field"]])
			print(f"发送时间: {self.tool.TimeUtils().format_timestamp(details['created_at'])}")  # 有的帖子可能有更新,但是大部分是created_at,为了迎合网页显示的发布时间

	def _check_report(self, source_id: int, source_type: Literal["shop", "work", "discussion", "post"], title: str, user_id: int) -> None:
		if source_type in {"work", "discussion", "shop"}:
			if source_type == "discussion":
				source_type = "post"
			violations = self._analyze_comments_violations(
				source_id=source_id,
				source_type=source_type,
				title=title,
			)

			if not violations:
				print("没有违规评论")
				return

			self._process_report_requests(
				violations=violations,
				source_id=source_id,
				source_type=source_type,
			)
		if source_type == "post":
			search_result = list(self.forum_obtain.search_posts_generator(title=title, limit=None))
			user_posts = self.tool.DataProcessor().filter_by_nested_values(data=search_result, id_path="user.id", target_values=[user_id])
			if len(user_posts) >= self.setting.PARAMETER.spam_del_max:
				print(f"用户{user_id} 已连续发布帖子{title} {len(user_posts)}次")

	def _analyze_comments_violations(
		self,
		source_id: int,
		source_type: Literal["post", "work", "shop"],
		title: str,
	) -> list[str]:
		comments = Obtain().get_comments_detail_new(
			com_id=source_id,
			source=source_type,
			method="comments",
		)

		params = {
			"ads": self.data.USER_DATA.ads,
			"blacklist": self.data.USER_DATA.black_room,
			"spam_max": self.setting.PARAMETER.spam_del_max,
		}

		abnormal_targets = defaultdict(list)
		self._find_abnormal_comments(
			comments=comments,
			item_id=source_id,
			title=title,
			action_type="ads",
			params=params,
			target_lists=abnormal_targets,
		)

		duplicate_targets = defaultdict(list)
		self._find_duplicate_comments(
			comments=comments,
			item_id=source_id,
			params=params,
			target_lists=duplicate_targets,
		)

		return abnormal_targets["ads"] + abnormal_targets["blacklist"] + duplicate_targets["duplicates"]

	def _process_report_requests(
		self,
		violations: list[str],
		source_id: int,
		source_type: Literal["post", "work", "shop"],
	) -> None:
		if input("是否自动举报违规评论? (Y/N) ").upper() != "Y":
			print("操作已取消")
			return

		try:
			self.acquire.switch_account(token=self.acquire.token.average, identity="average")
			account_pool = self._switch_edu_account(limit=20)
			if not account_pool:
				print("没有可用的教育账号")
				return
		except Exception as e:
			print(f"账号切换失败: {e}")
			return

		current_account = None
		report_counter = -1
		reason_content = self.community_obtain.fetch_report_reasons()["items"][7]["content"]
		source_map = {"work": "work", "post": "forum", "shop": "shop"}
		for violation in violations:
			try:
				if report_counter >= self.setting.PARAMETER.report_work_max or report_counter == -1:
					current_account = next(account_pool, None)
					if not current_account:
						print("所有账号均已尝试")
						return
					print("切换教育账号")
					time.sleep(5)
					self.community_login.authenticate_with_password(
						identity=current_account[0],
						password=current_account[1],
						status="edu",
					)
					time.sleep(5)
					report_counter = 0

				parts = violation.split(":")
				_item_id, comment_id = parts[0].split(".")
				is_reply = "reply" in violation

				parent_id, _ = self.tool.StringProcessor().find_substrings(
					text=comment_id,
					candidates=violations,
				)
				self.community_obtain.fetch_replies(types="COMMENT_REPLY")
				self.community_obtain.fetch_message_count(method="web")
				self.community_obtain.fetch_community_status(types="WEB_FORUM_STATUS")

				if self.report_work(
					source=cast("Literal['forum', 'work', 'shop']", source_map[source_type]),
					target_id=int(comment_id),
					source_id=source_id,
					reason_id=7,
					reason_content=reason_content,
					parent_id=cast("int", int(parent_id)) if parent_id else None,
					is_reply=is_reply,
				):
					report_counter += 1
					print(f"举报成功: {violation}")
					continue
				print(f"举报失败: {violation}")
				report_counter += 1

			except Exception as e:
				print(f"处理异常: {e}")

		self.whale_routine.configure_authentication_token(self.acquire.token.judgement)

	def report_work(
		self,
		source: Literal["forum", "work", "shop"],
		target_id: int,
		source_id: int,
		reason_id: Literal[0, 1, 2, 3, 4, 5, 6, 7, 8],
		reason_content: str,
		parent_id: int | None = None,
		description: str = "",
		*,
		is_reply: bool = False,
	) -> bool:
		"""举报作品/评论"""
		reason_content = self.community_obtain.fetch_report_reasons()["items"][reason_id]["content"]
		match source:
			case "work":
				return self.work_motion.report_comment(work_id=target_id, comment_id=source_id, reason=reason_content)
			case "forum":
				source_ = "COMMENT" if is_reply else "REPLY"
				return self.forum_motion.report_item(item_id=target_id, reason_id=reason_id, description=description, item_type=source_, return_data=False)
			case "shop":
				if is_reply:
					return self.shop_motion.report_comment(
						comment_id=target_id,
						reason_content=reason_content,
						reason_id=reason_id,
						reporter_id=int(self.data.ACCOUNT_DATA.id),
						comment_parent_id=parent_id or 0,
						description=description,
					)
				return self.shop_motion.report_comment(
					comment_id=target_id,
					reason_content=reason_content,
					reason_id=reason_id,
					reporter_id=int(self.data.ACCOUNT_DATA.id),
					description=description,
				)

	# 以下是从 Motion 类复制过来的辅助方法
	def _find_abnormal_comments(self, comments: list, item_id: int, title: str, action_type: str, params: dict, target_lists: defaultdict) -> None:
		for comment in comments:
			if comment.get("is_top"):
				continue

			if self._check_condition(comment, action_type, params):
				identifier = f"{item_id}.{comment['id']}:comment"
				self._log_and_add(
					target_lists=target_lists,
					data=comment,
					identifier=identifier,
					title=title,
					action_type=action_type,
				)

			for reply in comment.get("replies", []):
				if self._check_condition(reply, action_type, params):
					identifier = f"{item_id}.{reply['id']}:reply"
					self._log_and_add(
						target_lists=target_lists,
						data=reply,
						identifier=identifier,
						title=title,
						action_type=action_type,
						parent_content=comment["content"],
					)

	@staticmethod
	def _check_condition(data: dict, action_type: str, params: dict) -> bool:
		content = data["content"].lower()
		user_id = str(data["user_id"])

		if action_type == "ads":
			return any(ad in content for ad in params["ads"])
		if action_type == "blacklist":
			return user_id in params["blacklist"]
		return False

	@staticmethod
	def _log_and_add(target_lists: defaultdict, data: dict, identifier: str, title: str, action_type: str, parent_content: str = "") -> None:
		log_templates = {
			"ads": "广告{type} [{title}]{parent} :{content}",
			"blacklist": "黑名单{type} [{title}]{parent} :{nickname}",
		}

		log_type = "回复" if ":reply" in identifier else "评论"
		parent_info = f" ({parent_content})" if parent_content else ""

		if action_type == "ads":
			log_message = log_templates[action_type].format(
				type=log_type,
				title=title,
				parent=parent_info,
				content=data["content"],
			)
		else:
			log_message = log_templates[action_type].format(
				type=log_type,
				title=title,
				parent=parent_info,
				nickname=data["nickname"],
			)

		print(log_message)
		target_lists[action_type].append(identifier)

	def _find_duplicate_comments(self, comments: list, item_id: int, params: dict, target_lists: defaultdict) -> None:
		"""查找重复评论"""
		content_map = defaultdict(list)

		for comment in comments:
			self._track_comment(comment, item_id, content_map)
			for reply in comment.get("replies", []):
				self._track_comment(reply, item_id, content_map, is_reply=True)

		for (user_id, content), ids in content_map.items():
			if len(ids) >= params["spam_max"]:
				print(f"用户 {user_id} 刷屏评论: {content} - 出现 {len(ids)} 次")
				target_lists["duplicates"].extend(ids)

	@staticmethod
	def _track_comment(data: dict, item_id: int, content_map: defaultdict, *, is_reply: bool = False) -> None:
		"""追踪评论到内容映射"""
		key = (data["user_id"], data["content"].lower())
		identifier = f"{item_id}.{data['id']}:{'reply' if is_reply else 'comment'}"
		content_map[key].append(identifier)

	def _switch_edu_account(self, limit: int | None) -> Generator[tuple[str, str]]:
		students = list(self.edu_obtain.fetch_class_students_generator(limit=limit))
		while students:
			student = students.pop(randint(0, len(students) - 1))
			self.acquire.switch_account(token=self.acquire.token.average, identity="average")
			yield student["username"], self.edu_motion.reset_student_password(student["id"])["password"]
