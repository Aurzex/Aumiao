"""服务类:认证管理、文件上传、高级服务"""

import operator
from collections import defaultdict
from collections.abc import Callable, Generator
from json import loads
from pathlib import Path
from random import choice
from typing import ClassVar, Literal, cast

from src.core.base import VALID_REPLY_TYPES, ClassUnion, SourceConfigSimple, acquire, data, decorator, tool
from src.core.process import CommentProcessor, FileProcessor, ReportAuthManager, ReportFetcher, ReportProcessor
from src.core.retrieve import Obtain
from src.utils.acquire import HTTPSTATUS


@decorator.singleton
class FileUploader(ClassUnion):
	def __init__(self) -> None:
		super().__init__()
		self.uploader = FileProcessor()

	def upload_file(
		self,
		method: Literal["pgaot", "codemao", "codegame"],
		file_path: Path,
		save_path: str = "aumiao",
		*,
		recursive: bool = True,
	) -> dict[str, str | None] | str | None:
		"""
		上传文件或文件夹
		Args:
			method: 上传方法 ("pgaot", "codemao" 或 "codegame")
			file_path: 要上传的文件或文件夹路径
			save_path: 保存路径 (默认为 "aumiao")
			recursive: 是否递归上传子文件夹中的文件 (默认为 True)
		Returns:
			- 如果是单个文件: 返回上传后的URL或None
			- 如果是文件夹: 返回字典 {文件路径: 上传URL或None}
		"""
		uploader = acquire.FileUploader()
		if file_path.is_file():
			return self.uploader.handle_file_upload(file_path=file_path, save_path=save_path, method=method, uploader=uploader)
		if file_path.is_dir():
			return self.uploader.handle_directory_upload(dir_path=file_path, save_path=save_path, method=method, uploader=uploader, recursive=recursive)
		return None


@decorator.singleton
class Motion(ClassUnion):
	SOURCE_CONFIG: ClassVar = {
		"work": SourceConfigSimple(
			get_items=lambda self=None: self._user_obtain.fetch_user_works_web_gen(self._data.ACCOUNT_DATA.id, limit=None),
			get_comments=lambda _self, _id: Obtain().get_comments_detail(_id, "work", "comments"),
			delete=lambda self, _item_id, comment_id, is_reply: self._work_motion.delete_comment(comment_id, "comments" if is_reply else "replies"),
			title_key="work_name",
		),
		"post": SourceConfigSimple(
			get_items=lambda self=None: self._forum_obtain.fetch_my_posts_gen("created", limit=None),
			get_comments=lambda _self, _id: Obtain().get_comments_detail(_id, "post", "comments"),
			delete=lambda self, _item_id, comment_id, is_reply: self._forum_motion.delete_item(comment_id, "comments" if is_reply else "replies"),
			title_key="title",
		),
	}

	def clear_comments(
		self,
		source: Literal["work", "post"],
		action_type: Literal["ads", "duplicates", "blacklist"],
	) -> bool:
		"""清理评论核心方法
		Args:
		source: 数据来源 work=作品评论 post=帖子回复
		action_type: 处理类型
			ads=广告评论
			duplicates=重复刷屏
			blacklist=黑名单用户
		"""
		config = self.SOURCE_CONFIG[source]
		params: dict[Literal["ads", "blacklist", "spam_max"], list[str] | int] = {
			"ads": self._data.USER_DATA.ads,
			"blacklist": self._data.USER_DATA.black_room,
			"spam_max": self._setting.PARAMETER.spam_del_max,
		}
		target_lists = defaultdict(list)
		for item in config.get_items(self):
			CommentProcessor().process_item(item, config, action_type, params, target_lists)
		return self._execute_deletion(
			target_list=target_lists[action_type],
			delete_handler=config.delete,
			label={"ads": "广告评论", "blacklist": "黑名单评论", "duplicates": "刷屏评论"}[action_type],
		)

	@staticmethod
	@decorator.skip_on_error
	def _execute_deletion(target_list: list, delete_handler: Callable[[int, int, bool], bool], label: str) -> bool:
		"""执行删除操作
		注意 :由于编程猫社区接口限制,需要先删除回复再删除主评论,
		通过反转列表实现从后往前删除,避免出现删除父级评论后无法删除子回复的情况
		"""
		if not target_list:
			print(f"未发现{label}")
			return True
		print(f"\n发现以下{label} (共{len(target_list)}条):")
		for item in reversed(target_list):
			print(f" - {item.split(':')[0]}")
		if input(f"\n确认删除所有{label}? (Y/N)").lower() != "y":
			print("操作已取消")
			return True
		for entry in reversed(target_list):
			parts = entry.split(":")[0].split(".")
			item_id, comment_id = map(int, parts)
			is_reply = ":reply" in entry
			if not delete_handler(item_id, comment_id, is_reply):
				print(f"删除失败: {entry}")
				return False
			print(f"已删除: {entry}")
		return True

	def clear_red_point(self, method: Literal["nemo", "web"] = "web") -> bool:
		"""清除未读消息红点提示
		Args:
			method: 处理模式
			web - 网页端消息类型
			nemo - 客户端消息类型
		Returns:
		bool: 是否全部清除成功
		"""
		method_config = {
			"web": {
				"endpoint": "/web/message-record",
				"message_types": self._setting.PARAMETER.all_read_type,
				"check_keys": ["count"],
			},
			"nemo": {
				"endpoint": "/nemo/v2/user/message/{type}",
				"message_types": [1, 3],
				"check_keys": ["like_collection_count", "comment_count", "re_create_count", "system_count"],
			},
		}
		if method not in method_config:
			msg = f"不支持的方法类型: {method}"
			raise ValueError(msg)
		config = method_config[method]
		page_size = 200
		params: dict[str, int | str] = {"limit": page_size, "offset": 0}

		def is_all_cleared(counts: dict) -> bool:
			if method == "web":
				return all(count["count"] == 0 for count in counts[:3])
			return sum(counts[key] for key in config["check_keys"]) == 0

		def send_batch_requests() -> bool:
			responses = {}
			for msg_type in config["message_types"]:
				config["endpoint"] = cast("str", config["endpoint"])
				endpoint = config["endpoint"].format(type=msg_type) if "{" in config["endpoint"] else config["endpoint"]
				request_params = params.copy()
				if method == "web":
					request_params["query_type"] = msg_type
				response = self._client.send_request(endpoint=endpoint, method="GET", params=request_params)  # 统一客户端调用
				responses[msg_type] = response.status_code
			return all(code == HTTPSTATUS.OK.value for code in responses.values())

		try:
			while True:
				current_counts = self._community_obtain.fetch_message_count(method)
				if is_all_cleared(current_counts):
					return True
				if not send_batch_requests():
					return False
				params["offset"] = cast("int", params["offset"])
				params["offset"] += page_size
		except Exception as e:
			print(f"清除红点过程中发生异常: {e}")
			return False

	def like_all_work(self, user_id: str, works_list: list[dict] | Generator[dict]) -> None:
		self._work_motion.execute_toggle_follow(user_id=int(user_id))  # 优化方法名:manage→execute_toggle
		for item in works_list:
			item["id"] = cast("int", item["id"])
			self._work_motion.execute_toggle_like(work_id=item["id"])  # 优化方法名:manage→execute_toggle
			self._work_motion.execute_toggle_collection(work_id=item["id"])  # 优化方法名:manage→execute_toggle

	def like_my_novel(self, novel_list: list[dict]) -> None:
		for item in novel_list:
			item["id"] = cast("int", item["id"])
			self._novel_motion.execute_toggle_novel_favorite(item["id"])

	def execute_auto_reply_work(self) -> bool:  # 优化方法名:添加execute_前缀  # noqa: PLR0914
		"""自动回复作品/帖子评论"""
		formatted_answers = {
			k: v.format(**self._data.INFO) if isinstance(v, str) else [i.format(**self._data.INFO) for i in v] for answer in self._data.USER_DATA.answers for k, v in answer.items()
		}
		formatted_replies = [r.format(**self._data.INFO) for r in self._data.USER_DATA.replies]
		valid_types = list(VALID_REPLY_TYPES)  # 将set转为list
		new_replies = self._tool.DataProcessor().filter_by_nested_values(
			data=Obtain().get_new_replies(),
			id_path="type",
			target_values=valid_types,
		)
		for reply in new_replies:
			try:
				content = loads(reply["content"])
				msg = content["message"]
				reply_type = reply["type"]
				comment_text = msg["comment"] if reply_type in {"WORK_COMMENT", "POST_COMMENT"} else msg["reply"]
				chosen = next((choice(resp) for keyword, resp in formatted_answers.items() if keyword in comment_text), choice(formatted_replies))
				source_type = cast("Literal['work', 'post']", "work" if reply_type.startswith("WORK") else "post")
				comment_ids = [
					str(item)
					for item in Obtain().get_comments_detail(
						com_id=msg["business_id"],
						source=source_type,
						method="comment_id",
					)
					if isinstance(item, (int, str))
				]
				target_id = str(msg.get("reply_id", ""))
				if reply_type.endswith("_COMMENT"):
					comment_id = int(reply.get("reference_id", msg.get("comment_id", 0)))
					parent_id = 0
				else:
					parent_id = int(reply.get("reference_id", msg.get("replied_id", 0)))
					found = self._tool.StringProcessor().find_substrings(
						text=target_id,
						candidates=comment_ids,
					)[0]
					comment_id = int(found) if found else 0
				print(f"\n{'=' * 30} 新回复 {'=' * 30}")
				print(f"类型: {reply_type}")
				comment_text = msg["comment"] if reply_type in {"WORK_COMMENT", "POST_COMMENT"} else msg["reply"]
				print(f"提取关键文本: {comment_text}")
				matched_keyword = None
				for keyword, resp in formatted_answers.items():
					if keyword in comment_text:
						matched_keyword = keyword
						chosen = choice(resp) if isinstance(resp, list) else resp
						print(f"匹配到关键字「{keyword}」")
						break
				if not matched_keyword:
					chosen = choice(formatted_replies)
					print("未匹配关键词,随机选择回复")
				print(f"最终选择回复: 【{chosen}】")
				params = (
					{
						"work_id": msg["business_id"],
						"comment_id": comment_id,
						"parent_id": parent_id,
						"comment": chosen,
						"return_data": True,
					}
					if source_type == "work"
					else {
						"reply_id": comment_id,
						"parent_id": parent_id,
						"content": chosen,
					}
				)
				(self._work_motion.create_comment_reply if source_type == "work" else self._forum_motion.create_comment_reply)(
					**params  # pyright: ignore[reportArgumentType]
				)  # 优化方法名:reply_to_comment→create_comment_reply
				print(f"已发送回复到{source_type},评论ID: {comment_id}")
			except Exception as e:
				print(f"回复处理失败: {e}")
				continue
		return True

	# 常驻置顶
	def execute_maintain_top(self, method: Literal["shop", "novel"]) -> None:  # 优化方法名:添加execute_前缀
		if method == "shop":
			detail = self._shop_obtain.fetch_workshop_details_list()
			description = self._shop_obtain.fetch_workshop_details(detail["work_subject_id"])["description"]
			self._shop_motion.update_workshop_details(
				description=description,
				workshop_id=detail["id"],
				name=detail["name"],
				preview_url=detail["preview_url"],
			)
		elif method == "novel":
			novel_list = self._novel_obtain.fetch_my_novels()
			for item in novel_list:
				novel_id = item["id"]
				novel_detail = self._novel_obtain.fetch_novel_details(novel_id=novel_id)
				single_chapter_id = novel_detail["data"]["sectionList"][0]["id"]
				self._novel_motion.publish_chapter(single_chapter_id)

	# 查看账户状态
	def get_account_status(self) -> str:
		status = self._user_obtain.fetch_account_details()
		return f"禁言状态{status['voice_forbidden']}, 签订友好条约{status['has_signed']}"

	def execute_download_fiction(self, fiction_id: int) -> None:  # 优化方法名:添加execute_前缀
		details = self._novel_obtain.fetch_novel_details(fiction_id)
		info = details["data"]["fanficInfo"]
		print(f"正在下载: {info['title']}-{info['nickname']}")
		print(f"简介: {info['introduction']}")
		print(f"类别: {info['fanfic_type_name']}")
		print(f"词数: {info['total_words']}")
		print(f"更新时间: {self._tool.TimeUtils().format_timestamp(info['update_time'])}")
		fiction_dir = data.DOWNLOAD_DIR / f"{info['title']}-{info['nickname']}"
		fiction_dir.mkdir(parents=True, exist_ok=True)
		for section in details["data"]["sectionList"]:
			section_id = section["id"]
			section_title = section["title"]
			section_path = fiction_dir / f"{section_title}.txt"
			content = self._novel_obtain.fetch_chapter_details(chapter_id=section_id)["data"]["section"]["content"]
			formatted_content = self._tool.DataConverter().html_to_text(content, merge_empty_lines=True)
			self._file.file_write(path=section_path, content=formatted_content)

	def generate_nemo_code(self, work_id: int) -> None:
		try:
			work_info_url = f"https://api.codemao.cn/creation-tools/v1/works/{work_id}/source/public"
			work_info = self._client.send_request(endpoint=work_info_url, method="GET").json()  # 统一客户端调用
			bcm_url = work_info["work_urls"][0]
			payload = {
				"app_version": "5.9.0",
				"bcm_version": "0.16.2",
				"equipment": "Aumiao",
				"name": work_info["name"],
				"os": "android",
				"preview": work_info["preview"],
				"work_id": work_id,
				"work_url": bcm_url,
			}
			response = self._client.send_request(endpoint="https://api.codemao.cn/nemo/v2/miao-codes/bcm", method="POST", payload=payload)  # 统一客户端调用
			# Process the response
			if response.ok:
				result = response.json()
				miao_code = f"【喵口令】$&{result['token']}&$"
				print("\nGenerated Miao Code:")
				print(miao_code)
			else:
				print(f"Error: {response.status_code} - {response.text}")
		except Exception as e:
			print(f"An error occurred: {e!s}")

	def collect_work_comments(self, limit: int) -> list[dict]:
		works = Obtain().integrate_work_data(limit=limit)
		comments = []
		for single_work in works:
			work_comments = Obtain().get_comments_detail(com_id=single_work["work_id"], source="work", method="comments", max_limit=20)
			comments.extend(work_comments)
		filtered_comments = self._tool.DataProcessor().filter_data(data=comments, include=["user_id", "content", "nickname"])
		filtered_comments = cast("list[dict]", filtered_comments)
		user_comments_map = {}
		for comment in filtered_comments:
			user_id = comment.get("user_id")
			content = comment.get("content")
			nickname = comment.get("nickname")
			if user_id is None or content is None or nickname is None:
				continue
			user_id_str = str(user_id)
			if user_id_str not in user_comments_map:
				user_comments_map[user_id_str] = {"user_id": user_id_str, "nickname": nickname, "comments": [], "comment_count": 0}
			user_comments_map[user_id_str]["comments"].append(content)
			user_comments_map[user_id_str]["comment_count"] += 1
		# 转换为列表并按评论数从大到小排序
		result = list(user_comments_map.values())
		result.sort(key=operator.itemgetter("comment_count"), reverse=True)
		return result

	@staticmethod
	def check_user_comments_stats(comments_data: list[dict], min_comments: int = 1) -> None:
		"""通过统计作品评论信息查看违规情况
		Args:
			comments_data: 用户评论数据列表
			min_comments: 最小评论数目阈值, 只有评论数大于等于此值的用户才会被打印
		"""
		# 过滤出评论数达到阈值的用户
		filtered_users = [user for user in comments_data if user["comment_count"] >= min_comments]
		if not filtered_users:
			print(f"没有用户评论数达到或超过 {min_comments} 条")
			return
		print(f"评论数达到 {min_comments}+ 的用户统计:")
		print("=" * 60)
		for user_data in filtered_users:
			nickname = user_data["nickname"]
			user_id = user_data["user_id"]
			comment_count = user_data["comment_count"]
			print(f"用户 {nickname} (ID: {user_id}) 发送了 {comment_count} 条评论")
			print("评论内容:")
			for i, comment in enumerate(user_data["comments"], 1):
				print(f"  {i}. {comment}")
			print("*" * 50)

	def batch_report_post(self, timeline: int) -> None:
		"""
		实现风纪欲望的小帮手
		"""
		token_list = self._file.read_line(data.TOKEN_DIR)
		_student_tokens = [token.strip() for token in token_list if token.strip()]  # 过滤空行
		print(f"正在查找发布时间在{self._tool.TimeUtils().format_timestamp(timeline)}之后的帖子")
		post_list: list = self._forum_obtain.fetch_hot_posts_ids()["items"][0:19]
		posts_details: list[dict] = self._forum_obtain.fetch_posts_details(post_ids=post_list)["items"]
		for single in posts_details:
			create_time: int = single["created_at"]
			if create_time > timeline:
				print(f"帖子{single['title']}-ID{single['id']}-发布于{self._tool.TimeUtils().format_timestamp(create_time)}")


@decorator.singleton
class MillenniumEntanglement(ClassUnion):
	def __init__(self) -> None:
		super().__init__()

	def batch_like_content(self, user_id: int | None, content_type: Literal["work", "novel"], custom_list: list | None = None) -> None:
		"""批量点赞用户作品或小说"""
		if custom_list:
			target_list = custom_list
		elif content_type == "work":
			target_list = list(self._user_obtain.fetch_user_works_web_gen(str(user_id), limit=None))
		elif content_type == "novel":
			target_list = self._novel_obtain.fetch_my_novels()
		else:
			msg = f"不支持的内容类型 {content_type}"
			raise TypeError(msg)

		def action() -> None:
			if content_type == "work":
				Motion().like_all_work(user_id=str(user_id), works_list=target_list)
			else:
				Motion().like_my_novel(novel_list=target_list)

		Obtain().process_edu_accounts(limit=None, action=action())

	def upgrade_to_teacher(self, real_name: str) -> None:
		"""升级账号为教师身份"""
		generator = tool.EduDataGenerator()
		self._edu_motion.execute_upgrade_to_teacher(
			user_id=int(self._data.ACCOUNT_DATA.id),
			real_name=real_name,
			grade=["2", "3", "4"],
			school_id=11000161,
			school_name="北京景山学校",
			school_type=1,
			country_id="156",
			province_id=1,
			city_id=1,
			district_id=1,
			teacher_card_number=generator.generate_teacher_certificate_number(),
		)

	def manage_edu_accounts(self, action_type: Literal["create", "delete", "token"], limit: int | None = 100) -> None:
		"""批量管理教育账号"""

		def _create_students(student_limit: int) -> None:
			"""创建学生账号"""
			class_capacity = 95
			class_count = (student_limit + class_capacity - 1) // class_capacity
			generator = tool.EduDataGenerator()
			class_names = generator.generate_class_names(num_classes=class_count, add_specialty=True)
			student_names = generator.generate_student_names(num_students=student_limit)
			for class_idx in range(class_count):
				class_id = self._edu_motion.create_class(name=class_names[class_idx])["id"]
				print(f"创建班级 {class_id}")
				start = class_idx * class_capacity
				end = start + class_capacity
				batch_names = student_names[start:end]
				self._edu_motion.add_students_to_class(name=batch_names, class_id=class_id)
				print("添加学生ing")

		def _delete_students(delete_limit: int | None) -> None:
			"""删除学生账号"""
			students = self._edu_obtain.fetch_class_students_gen(limit=delete_limit)
			for student in students:
				self._edu_motion.delete_student_from_class(stu_id=student["id"])

		def _create_token(token_limit: int | None) -> list[str]:
			"""生成账号token"""
			accounts = Obtain().switch_edu_account(limit=token_limit, return_method="list")
			token_list = []
			for identity, pass_key in accounts:
				response = self._community_login.authenticate_with_password(identity=identity, password=pass_key, status="edu")
				token = response["auth"]["token"]
				token_list.append(token)
				self._file.file_write(path=data.TOKEN_DIR, content=f"{token}\n", method="a")
			return token_list

		if action_type == "delete":
			_delete_students(limit)
		elif action_type == "create":
			actual_limit = limit or 100
			_create_students(actual_limit)
		elif action_type == "token":
			_create_token(token_limit=limit)

	def batch_report_work(self, work_id: int) -> None:
		"""批量举报作品"""
		hidden_border = 10
		Obtain().process_edu_accounts(limit=hidden_border, action=lambda: self._work_motion.execute_report_work(describe="", reason="违法违规", work_id=work_id))

	def create_comment(self, target_id: int, content: str, source_type: Literal["work", "shop", "post"]) -> None:
		"""创建评论/回复"""
		if source_type == "post":
			self._forum_motion.create_post_reply(post_id=target_id, content=content)
		elif source_type == "shop":
			self._shop_motion.create_comment(workshop_id=target_id, content=content, rich_content=content)
		elif source_type == "work":
			self._work_motion.create_work_comment(work_id=target_id, comment=content)
		else:
			msg = f"不支持的来源类型 {source_type}"
			raise TypeError(msg)

	def execute_report_action(
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
class Report(ClassUnion):
	def __init__(self) -> None:
		super().__init__()
		self.report = ReportAuthManager()
		self.processor = ReportProcessor()  # 使用新的处理器
		self.fetcher = ReportFetcher()
		self.processed_count = 0
		self.printer = tool.Printer()  # 添加打印机实例

	def execute_report_handle(self, admin_id: int) -> None:
		"""举报处理主流程:加载账号 → 循环处理 → 统计结果"""
		self.printer.print_header("=== 举报处理系统 ===")
		# 1. 加载学生账号(用于自动举报)
		self.report.load_student_accounts()
		# 2. 主处理循环:分块处理 → 询问是否继续
		while True:
			# 获取所有待处理举报总数
			self.total_report = self.fetcher.get_total_reports(status="TOBEDONE")
			if self.total_report == 0:
				self.printer.print_message("当前没有待处理的举报", "INFO")
				break
			# 显示待处理举报数量
			self.printer.print_message(f"发现 {self.total_report} 条待处理举报", "INFO")
			# 使用新的分块处理方法
			batch_processed = self.processor.process_all_reports(admin_id)
			self.processed_count += batch_processed
			# 本次处理结果
			self.printer.print_message(f"本次处理完成: {batch_processed} 条举报", "SUCCESS")
			# 询问是否继续检查新举报
			continue_choice = self.printer.get_valid_input(prompt="是否继续检查新举报? (Y/N)", valid_options={"Y", "N"}).upper()
			if continue_choice != "Y":
				break
			self.printer.print_message("重新获取新举报...", "INFO")
		# 3. 处理结束:统计结果 + 终止会话
		self.printer.print_header("=== 处理结果统计 ===")
		self.printer.print_message(f"本次会话共处理 {self.processed_count} 条举报", "SUCCESS")
		self.report.terminate_session()
