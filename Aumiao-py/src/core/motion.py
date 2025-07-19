import time
from collections import defaultdict
from collections.abc import Callable, Generator
from json import loads
from pathlib import Path
from random import choice, randint
from typing import ClassVar, Literal, cast

from src.api import edu, whale
from src.core.obtain import Obtain
from src.utils import acquire, decorator, tool

from .base import DOWNLOAD_DIR, VALID_REPLY_TYPES, SourceConfig
from .report_handler import ReportHandler
from .union import ClassUnion


@decorator.singleton
class Motion(ClassUnion, ReportHandler):
	SOURCE_CONFIG: ClassVar[dict[str, SourceConfig]] = {
		"work": SourceConfig(
			get_items=lambda self=None: self.user_obtain.fetch_user_works_web_generator(self.data.ACCOUNT_DATA.id, limit=None),
			get_comments=lambda _self, _id: Obtain().get_comments_detail_new(_id, "work", "comments"),
			delete=lambda self, _item_id, comment_id, is_reply: self.work_motion.delete_comment(
				comment_id,
				"comments" if is_reply else "replies",
			),
			title_key="work_name",
		),
		"post": SourceConfig(
			get_items=lambda self=None: self.forum_obtain.fetch_my_posts_generator("created", limit=None),
			get_comments=lambda _self, _id: Obtain().get_comments_detail_new(_id, "post", "comments"),
			delete=lambda self, _item_id, comment_id, is_reply: self.forum_motion.delete_item(
				comment_id,
				"comments" if is_reply else "replies",
			),
			title_key="title",
		),
	}

	def clear_comments(
		self,
		source: str,
		action_type: str,
	) -> bool:
		"""清理评论核心方法"""
		config = self.SOURCE_CONFIG[source]
		params = {
			"ads": self.data.USER_DATA.ads,
			"blacklist": self.data.USER_DATA.black_room,
			"spam_max": self.setting.PARAMETER.spam_del_max,
		}

		target_lists = defaultdict(list)
		for item in config.get_items(self):
			self._process_item(item, config, action_type, params, target_lists)

		return self._execute_deletion(
			target_list=target_lists[action_type],
			delete_handler=config.delete,
			label={"ads": "广告评论", "blacklist": "黑名单评论", "duplicates": "刷屏评论"}[action_type],
		)

	def _process_item(self, item: dict, config: SourceConfig, action_type: str, params: dict, target_lists: defaultdict) -> None:
		item_id = int(item["id"])
		comments = config.get_comments(self, item_id)

		if action_type in {"ads", "blacklist"}:
			self._find_abnormal_comments(comments, item_id, item[config.title_key], action_type, params, target_lists)
		elif action_type == "duplicates":
			self._find_duplicate_comments(comments, item_id, params, target_lists)

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

	@staticmethod
	@decorator.skip_on_error
	def _execute_deletion(target_list: list, delete_handler: Callable[[int, int, bool], bool], label: str) -> bool:
		"""执行删除操作"""
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
		"""清除未读消息红点提示"""
		method_config = {
			"web": {
				"endpoint": "/web/message-record",
				"message_types": self.setting.PARAMETER.all_read_type,
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
		params = {"limit": page_size, "offset": 0}

		def is_all_cleared(counts: dict) -> bool:
			if method == "web":
				return all(count["count"] == 0 for count in counts[:3])
			return sum(counts[key] for key in config["check_keys"]) == 0

		def send_batch_requests() -> bool:
			responses = {}
			for msg_type in config["message_types"]:
				endpoint = config["endpoint"].format(type=msg_type) if "{" in config["endpoint"] else config["endpoint"]

				request_params = params.copy()
				if method == "web":
					request_params["query_type"] = msg_type

				response = self.acquire.send_request(endpoint=endpoint, method="GET", params=request_params)
				responses[msg_type] = response.status_code

			return all(code == acquire.HTTPSTATUS.OK.value for code in responses.values())

		try:
			while True:
				current_counts = self.community_obtain.fetch_message_count(method)
				if is_all_cleared(current_counts):
					return True

				if not send_batch_requests():
					return False

				params["offset"] += page_size

		except Exception as e:
			print(f"清除红点过程中发生异常: {e}")
			return False

	def like_all_work(self, user_id: str, works_list: list[dict] | Generator[dict]) -> None:
		self.work_motion.manage_follow(user_id=int(user_id))
		for item in works_list:
			item["id"] = cast("int", item["id"])
			self.work_motion.manage_like(work_id=item["id"])
			self.work_motion.manage_collection(work_id=item["id"])

	def reply_work(self) -> bool:  # noqa: PLR0914
		"""自动回复作品/帖子评论"""
		formatted_answers = {
			k: v.format(**self.data.INFO) if isinstance(v, str) else [i.format(**self.data.INFO) for i in v] for answer in self.data.USER_DATA.answers for k, v in answer.items()
		}
		formatted_replies = [r.format(**self.data.INFO) for r in self.data.USER_DATA.replies]

		valid_types = list(VALID_REPLY_TYPES)
		new_replies = self.tool.DataProcessor().filter_by_nested_values(
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
					for item in Obtain().get_comments_detail_new(
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
					found = self.tool.StringProcessor().find_substrings(
						text=target_id,
						candidates=comment_ids,
					)[0]
					comment_id = int(found) if found else 0
				print(f"\n{'=' * 30} 新回复 {'=' * 30}")
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

				(self.work_motion.reply_to_comment if source_type == "work" else self.forum_motion.create_comment_reply)(**params)
				print(f"已发送回复到{source_type},评论ID: {comment_id}")

			except Exception as e:
				print(f"回复处理失败: {e}")
				continue

		return True

	def top_work(self) -> None:
		"""工作室常驻置顶"""
		detail = self.shop_obtain.fetch_workshop_details_list()
		description = self.shop_obtain.fetch_workshop_details(detail["work_subject_id"])["description"]
		self.shop_motion.update_workshop_details(
			description=description,
			workshop_id=detail["id"],
			name=detail["name"],
			preview_url=detail["preview_url"],
		)

	def get_account_status(self) -> str:
		"""查看账户状态"""
		status = self.user_obtain.fetch_account_details()
		return f"禁言状态{status['voice_forbidden']}, 签订友好条约{status['has_signed']}"

	def judgement_login(self) -> None:
		"""风纪委登录"""
		choice = input("请选择登录方式: 1.Token登录 2.账密登录 ")
		if choice == "1":
			token = input("请输入 Authorization: ")
			self.whale_routine.configure_authentication_token(token)
		if choice == "2":

			def input_password() -> tuple[str, str]:
				identity = input("请输入用户名: ")
				password = input("请输入密码: ")
				return (identity, password)

			def input_captcha(timestamp: int) -> tuple[str, whale.RequestsCookieJar]:
				print("正在获取验证码...")
				cookies: whale.RequestsCookieJar = self.whale_routine.fetch_verification_captcha(timestamp=timestamp)
				return input("请输入验证码: "), cookies

			timestamp = self.tool.TimeUtils().current_timestamp(13)
			identity, password = input_password()
			captcha, cookies = input_captcha(timestamp=timestamp)
			while True:
				self.acquire.update_cookies(cookies)
				response = self.whale_routine.authenticate_user(username=identity, password=password, key=timestamp, code=captcha)
				if "token" in response:
					self.whale_routine.configure_authentication_token(response["token"])
					break
				if "error_code" in response:
					print(response["error_msg"])
					if response["error_code"] in {"Admin-Password-Error@Community-Admin", "Param - Invalid @ Common"}:
						identity, password = input_password()
					elif response["error_code"] == "Captcha-Error@Community-Admin":
						pass
					timestamp = self.tool.TimeUtils().current_timestamp(13)
					captcha, cookies = input_captcha(timestamp=timestamp)

	def _switch_edu_account(self, limit: int | None) -> Generator[tuple[str, str]]:
		"""切换教育账号"""
		students = list(self.edu_obtain.fetch_class_students_generator(limit=limit))
		while students:
			student = students.pop(randint(0, len(students) - 1))
			self.acquire.switch_account(token=self.acquire.token.average, identity="average")
			yield student["username"], self.edu_motion.reset_student_password(student["id"])["password"]

	def chiaroscuro_chronicles(self, user_id: int) -> None:
		"""批量点赞作品"""
		try:
			self.acquire.switch_account(token=self.acquire.token.average, identity="average")
			account_pool = self._switch_edu_account(limit=None)
			if not account_pool:
				print("没有可用的教育账号")
				return
		except Exception as e:
			print(f"账号切换失败: {e}")
			return
		works_list = list(self.user_obtain.fetch_user_works_web_generator(str(user_id), limit=None))
		accounts = self._switch_edu_account(limit=None)
		for current_account in accounts:
			print("切换教育账号")
			time.sleep(5)
			self.community_login.authenticate_with_password(identity=current_account[0], password=current_account[1], status="edu")
			self.like_all_work(user_id=str(user_id), works_list=works_list)
		self.acquire.switch_account(token=self.acquire.token.average, identity="average")

	def celestial_maiden_chronicles(self, real_name: str) -> None:
		"""升级为教师账号"""
		generator = tool.EduDataGenerator()
		self.edu_motion.upgrade_to_teacher(
			user_id=int(self.data.ACCOUNT_DATA.id),
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

	@staticmethod
	def batch_handle_account(method: Literal["create", "delete"], limit: int | None = 100) -> None:
		"""批量处理教育账号"""

		def _create_students(student_limit: int) -> None:
			class_capacity = 95
			class_count = (student_limit + class_capacity - 1) // class_capacity

			generator = tool.EduDataGenerator()
			class_names = generator.generate_class_names(num_classes=class_count, add_specialty=True)
			student_names = generator.generate_student_names(num_students=student_limit)

			for class_idx in range(class_count):
				class_id = edu.UserAction().create_class(name=class_names[class_idx])["id"]
				print(f"创建班级 {class_id}")
				start = class_idx * class_capacity
				end = start + class_capacity
				batch_names = student_names[start:end]
				edu.UserAction().add_students(name=batch_names, class_id=class_id)
				print("添加学生ing")

		def _delete_students(delete_limit: int | None) -> None:
			students = edu.DataFetcher().fetch_class_students_generator(limit=delete_limit)
			for student in students:
				edu.UserAction().remove_student_from_class(stu_id=student["id"])

		if method == "delete":
			_delete_students(limit)
		elif method == "create":
			actual_limit = limit or 100
			_create_students(actual_limit)

	def download_fiction(self, fiction_id: int) -> None:
		"""下载小说"""
		details = self.library_obtain.fetch_novel_details(fiction_id)
		info = details["data"]["fanficInfo"]

		print(f"正在下载: {info['title']}-{info['nickname']}")
		print(f"简介: {info['introduction']}")
		print(f"类别: {info['fanfic_type_name']}")
		print(f"词数: {info['total_words']}")
		print(f"更新时间: {self.tool.TimeUtils().format_timestamp(info['update_time'])}")

		fiction_dir = DOWNLOAD_DIR / f"{info['title']}-{info['nickname']}"
		fiction_dir.mkdir(parents=True, exist_ok=True)

		for section in details["data"]["sectionList"]:
			section_id = section["id"]
			section_title = section["title"]
			section_path = fiction_dir / f"{section_title}.txt"
			content = self.library_obtain.fetch_chapter_details(chapter_id=section_id)["data"]["section"]["content"]
			formatted_content = self.tool.DataConverter().html_to_text(content, merge_empty_lines=True)
			self.file.file_write(path=section_path, content=formatted_content)

	def generate_nemo_code(self, work_id: int) -> None:
		"""生成喵口令"""
		try:
			work_info_url = f"https://api.codemao.cn/creation-tools/v1/works/{work_id}/source/public"
			work_info = self.acquire.send_request(endpoint=work_info_url, method="GET").json()
			bcm_url = work_info["work_urls"][0]
			payload = {
				"app_version": "5.6.2",
				"bcm_version": "0.16.2",
				"equipment": "Aumiao",
				"name": work_info["name"],
				"os": "android",
				"preview": work_info["preview"],
				"work_id": work_id,
				"work_url": bcm_url,
			}
			response = self.acquire.send_request(endpoint="https://api.codemao.cn/nemo/v2/miao-codes/bcm", method="POST", payload=payload)
			if response.ok:
				result = response.json()
				miao_code = f"【喵口令】$&{result['token']}&$"
				print("\nGenerated Miao Code:")
				print(miao_code)
			else:
				print(f"Error: {response.status_code} - {response.text}")
		except Exception as e:
			print(f"An error occurred: {e!s}")

	@staticmethod
	def upload_file(method: Literal["pgaot", "codemao"], file_path: Path, save_path: str = "aumiao") -> None:
		"""上传文件"""
		uploader = acquire.FileUploader()
		method_name = f"upload_via_{method}"
		upload_method = getattr(uploader, method_name)
		upload_method(file_path, save_path)
		upload_method(file_path, save_path)
