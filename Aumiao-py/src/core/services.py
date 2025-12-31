"""服务类:认证管理、文件上传、高级服务"""

import contextlib
from collections import defaultdict
from collections.abc import Callable, Generator
from pathlib import Path
from time import sleep
from typing import ClassVar, Literal, cast

from src.api import auth
from src.core.base import VALID_REPLY_TYPES, ClassUnion, SourceConfigSimple, data, decorator, tool
from src.core.compile import decompile_work
from src.core.editorkn import KNEditor, KNProject
from src.core.process import CommentProcessor, FileProcessor, ReplyProcessor, ReportAuthManager, ReportFetcher, ReportProcessor
from src.core.retrieve import Obtain
from src.utils.acquire import HTTPStatus


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
		if method in {"pgaot", "codegame"}:
			print("编程猫于2025年10月22日对对象存储进行限制")
			print("关闭了文件上传接口, 并更换域名*.codemao.cn -> *.bcmcdn.com")  # cSpell:ignore bcmcdn
			print(f"该上传方法 {method} 已经弃用, 可能导致上传失败问题")
		if file_path.is_file():
			return self.uploader.handle_file_upload(file_path=file_path, save_path=save_path, method=method)
		if file_path.is_dir():
			return self.uploader.handle_directory_upload(dir_path=file_path, save_path=save_path, method=method, recursive=recursive)
		return None


class WorkParser(ClassUnion):
	"""作品解析处理器"""

	def __init__(self) -> None:
		super().__init__()
		self.process = ReplyProcessor()

	def execute_auto_reply_work(self, data: data.CodeMaoData, valid_reply_types: set[str]) -> bool:
		"""
		自动回复作品/帖子评论和回复,包含作品解析功能
		Args:
			data: 用户数据
			valid_reply_types: 有效的回复类型列表
		Returns:
			是否成功执行
		"""
		# 格式化回复内容
		formatted_answers = {}
		for answer in data.USER_DATA.answers:
			for keyword, resp in answer.items():
				if isinstance(resp, str):
					formatted_answers[keyword] = resp.format(**data.INFO)
				elif isinstance(resp, list):
					formatted_answers[keyword] = [item.format(**data.INFO) for item in resp]
		formatted_replies = [reply.format(**data.INFO) for reply in data.USER_DATA.replies]
		# 获取新的回复通知
		new_replies = self._tool.DataProcessor().filter_by_nested_values(
			data=Obtain().get_new_replies(),
			id_path="type",
			target_values=list(valid_reply_types),
		)
		if not new_replies:
			print("没有需要回复的新通知")
			return False
		# 已处理的通知ID集合
		processed_ids = set()
		for reply in new_replies:
			try:
				# 1. 基础信息提取
				reply_id = reply.get("id", "")
				reply_type = reply.get("type", "")
				# 去重检查
				if reply_id in processed_ids:
					print(f"跳过重复通知: {reply_id}")
					continue
				processed_ids.add(reply_id)
				# 2. 解析content字段
				content_data = self.process.parse_content_field(reply)
				if content_data is None:
					continue
				# 3. 提取必要信息
				sender_info = content_data.get("sender", {})
				message_info = content_data.get("message", {})
				sender_id = sender_info.get("id", "")
				sender_nickname = sender_info.get("nickname", "未知用户")
				business_id = message_info.get("business_id")
				business_name = message_info.get("business_name", "未知")
				# 4. 确定通知类型
				if not reply_type:
					continue
				source_type = "work" if reply_type.startswith("WORK") else "post"
				# 5. 提取文本内容
				comment_text = self.process.extract_comment_text(reply_type, message_info)
				# 6. 解析目标ID和父ID
				target_id, parent_id = self.process.extract_target_and_parent_ids(reply_type, reply, message_info, business_id, source_type)
				# 7. 检查是否包含作品解析关键词
				if "@作品解析:" in comment_text:
					# 处理作品解析请求
					self._handle_work_parsing(
						comment_text=comment_text,
						sender_id=sender_id,
						sender_nickname=sender_nickname,
						business_id=business_id,
						source_type=source_type,
						target_id=target_id,
						parent_id=parent_id,
						reply_id=reply_id,
					)
					continue  # 跳过普通回复流程
				# 8. 原有关键词匹配逻辑
				chosen, matched_keyword = self.process.match_keyword(comment_text, formatted_answers, formatted_replies)
				# 9. 打印日志
				self.process.log_reply_info(reply_id, reply_type, source_type, sender_nickname, sender_id, business_name, comment_text, matched_keyword, chosen)
				# 10. 发送回复
				result = self._send_reply(source_type=source_type, business_id=business_id, target_id=target_id, parent_id=parent_id, content=chosen)
				if result:
					print(f"✓ 回复成功发送到{source_type}")
				else:
					print("✗ 回复失败")
				sleep(5)
			except Exception as e:
				print(f"处理通知时发生错误: {e!s}")
				continue
		print(f"\n处理完成,共处理 {len(processed_ids)} 条通知")
		return True

	def _handle_work_parsing(  # noqa: PLR0915
		self,
		comment_text: str,
		sender_id: int,
		sender_nickname: str,
		business_id: int,  # noqa: ARG002
		source_type: str,
		target_id: int,
		parent_id: int,
		reply_id: str,
	) -> None:
		"""
		处理作品解析请求
		"""
		print(f"\n{'=' * 40}")
		print(f"检测到作品解析请求 [通知ID: {reply_id}]")
		print(f"发送者: {sender_nickname} (ID: {sender_id})")
		print(f"原始内容: {comment_text}")
		try:
			# 1. 提取作品链接或ID
			work_info = self.process.extract_work_info(comment_text)
			if not work_info:
				print("未找到有效的作品链接或ID")
				return
			work_id = work_info["work_id"]
			print(f"提取到作品ID: {work_id}")
			# 2. 获取作品详细信息
			work_details = self._work_obtain.fetch_work_details(work_id)
			if not work_details:
				print("获取作品信息失败")
				return
			# 3. 检查是否为作品作者
			work_author_id = work_details.get("user_info", {}).get("id", 0)
			is_author = str(sender_id) == str(work_author_id)
			work_name = work_details.get("work_name", "未知作品")
			author_nickname = work_details.get("user_info", {}).get("nickname", "未知作者")
			print(f"作品名称: {work_name}")
			print(f"作者: {author_nickname} (ID: {work_author_id})")
			print(f"发送者是否为作者: {'是' if is_author else '否'}")
			# 4. 解析命令
			commands = self.process.parse_commands(comment_text)
			print(f"解析到命令: {commands or '无'}")
			# 5. 生成基础解析报告
			report = self.process.generate_work_report(work_details=work_details, is_author=is_author, commands=commands)
			# 6. 如果是作者且有编译命令,执行编译并生成CDN链接
			cdn_links = []
			if is_author and commands and "compile" in commands:
				print("检测到编译命令,开始编译作品...")
				cdn_link = self._handle_work_compilation(work_id, work_details)
				if cdn_link:
					print("作品编译完成,CDN链接已生成")
					cdn_links = self.process.split_long_cdn_link(cdn_link)
				else:
					print("作品编译失败")
					cdn_links = ["编译失败,请检查作品类型"]
			# 7. 准备所有要发送的消息
			messages_to_send = []
			# 添加报告消息
			report_parts = self.process.split_long_message(report)
			messages_to_send.extend(report_parts)
			# 添加CDN链接消息
			if cdn_links:
				messages_to_send.extend(cdn_links)
			print(f"总共需要发送 {len(messages_to_send)} 条消息")
			# 8. 根据作者身份和来源类型决定评论位置
			if is_author:
				print("作者身份确认,准备多位置处理")
				# 发送作品评论
				print(f"发送作品评论到作品 {work_id}:")
				self.process.send_messages_with_delay(
					messages=messages_to_send,
					send_func=lambda msg: self._work_motion.create_work_comment(work_id=work_id, comment=msg, return_data=True),
					comment_type="作品评论",
				)
				# 如果在帖子中,也发送到帖子
				if source_type == "post" and target_id > 0:
					print(f"发送回复到帖子评论 {target_id}:")
					self.process.send_messages_with_delay(
						messages=messages_to_send,
						send_func=lambda msg: self._forum_motion.create_comment_reply(reply_id=target_id, parent_id=parent_id, content=msg, return_data=True),
						comment_type="帖子回复",
					)
			else:
				print("非作者身份,仅在帖子下回复")
				# 非作者:只在帖子下回复评论
				if source_type == "post" and target_id > 0:
					print(f"发送回复到帖子评论 {target_id}:")
					self.process.send_messages_with_delay(
						messages=messages_to_send,
						send_func=lambda msg: self._forum_motion.create_comment_reply(reply_id=target_id, parent_id=parent_id, content=msg, return_data=True),
						comment_type="帖子回复",
					)
				elif source_type == "work":
					print("当前通知来自作品,非作者无法回复,跳过")
		except Exception as e:
			print(f"处理作品解析时发生错误: {e!s}")

	@staticmethod
	def _handle_work_compilation(work_id: int, work_details: dict) -> str | None:
		"""
		处理作品编译流程并返回CDN链接
		"""
		try:
			print(f"编译作品 {work_id}...")
			print(f"作品名称: {work_details.get('work_name')}")
			print(f"积木块数: {work_details.get('n_brick')}")
			print(f"角色数量: {work_details.get('n_roles')}")
			if work_details.get("type", "NEMO") == "NEMO":
				print("不支持NEMO作品上传到编程猫CDN")
				return None
			# 解压作品文件
			file_path = Path(decompile_work(work_id=work_id))
			# 上传文件到CDN
			return FileProcessor().handle_file_upload(
				file_path=file_path,
				save_path="aumiao",
				method="codemao",
			)
		except Exception as e:
			print(f"编译作品时发生错误: {e!s}")
			return None

	def _send_reply(self, source_type: str, business_id: int, target_id: int, parent_id: int, content: str) -> bool | dict:
		"""发送回复"""
		if source_type == "work":
			params = {
				"work_id": business_id,
				"comment_id": target_id,
				"parent_id": parent_id,
				"comment": content,
			}
			result = self._work_motion.create_comment_reply(**params)  # pyright: ignore[reportArgumentType]
		else:
			params = {
				"reply_id": str(target_id),
				"parent_id": str(parent_id),
				"content": content,
			}
			result = self._forum_motion.create_comment_reply(**params)  # pyright: ignore[reportArgumentType]
		return result


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
			return all(code == HTTPStatus.OK.value for code in responses.values())

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

	def execute_auto_reply(self) -> bool:
		"""执行自动回复"""
		data = self._data
		valid_reply_types = VALID_REPLY_TYPES
		# 使用作品解析器执行自动回复
		return WorkParser().execute_auto_reply_work(data, valid_reply_types)

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
		print(f"词数: {info['total_words']} 收藏数: {info['collect_times']}")
		print(f"更新时间: {self._tool.TimeUtils().format_timestamp(info['update_time'])}")
		fiction_dir = data.PathConfig.FICTION_FILE_PATH / f"{info['title']}-{info['nickname']}"
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
			if response:
				result = response.json()
				miao_code = f"【喵口令】$&{result['token']}&$"
				print("\nGenerated Miao Code:")
				print(miao_code)
			else:
				print(f"Error: {response.status_code} - {response.text}")
		except Exception as e:
			print(f"An error occurred: {e!s}")

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
		token_list = self._file.read_line(data.PathConfig.TOKEN_FILE_PATH)
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
				response = self._auth.login(identity=identity, password=pass_key, status="edu", prefer_method="simple_password")
				token = response["auth"]["token"]
				token_list.append(token)
				self._file.file_write(path=data.PathConfig.TOKEN_FILE_PATH, content=f"{token}\n", method="a")
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
							comment_id=target_id,
							reason_content=reason_content,
							reason_id=reason_id,
							reporter_id=reporter_id,
							comment_parent_id=parent_id,
							description=description,
						)
					# 普通评论:无需父ID
					return self._shop_motion.execute_report_comment(
						comment_id=target_id,
						reason_content=reason_content,
						reason_id=reason_id,
						reporter_id=reporter_id,
						description=description,
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
		auth.AuthManager().terminate_session()


class KnEditor:
	def __init__(self) -> None:
		self.editor = KNEditor()

	def handle_menu_choice(self, choice: str) -> bool:  # noqa: PLR0915
		"""处理菜单选择"""
		if choice == "1":
			project_name = input("请输入项目名称: ").strip()
			self.editor.project = KNProject(project_name)
			print(f"已创建新项目: {project_name}")
		elif choice == "2":
			filepath = input("请输入项目文件路径 (.bcmkn): ").strip()
			try:
				self.editor.load_project(filepath)
			except Exception as e:
				print(f"加载失败: {e}")
		elif choice == "3":
			if self.editor.project.filepath:
				save_path = input(f"保存路径 [{self.editor.project.filepath}]: ").strip()
				if not save_path:
					save_path = self.editor.project.filepath
			else:
				save_path = input("请输入保存路径: ").strip()
			try:
				self.editor.save_project(save_path)
			except Exception as e:
				print(f"保存失败: {e}")
		elif choice == "4":
			if self.editor.project:
				self.editor.print_project_info()
			else:
				print("请先加载或创建项目")
		elif choice == "5":
			if self.editor.project:
				analysis = self.editor.project.analyze_project()
				print("\n" + "=" * 60)
				print("项目详细分析:")
				print("=" * 60)
				for key, value in analysis.items():
					if key in {"block_type_counts", "category_counts"}:
						print(f"\n{key}:")
						for sub_key, sub_value in value.items():
							print(f"  {sub_key}: {sub_value}")
					else:
						print(f"{key}: {value}")
			else:
				print("请先加载或创建项目")
		elif choice == "6":
			self.handle_scene_management()
		elif choice == "7":
			self.handle_actor_management()
		elif choice == "8":
			self.handle_block_management()
		elif choice == "9":
			self.handle_resource_management()
		elif choice == "10":
			self.handle_export_xml()
		elif choice == "11":
			self.handle_search()
		elif choice == "12":
			print("感谢使用,再见!")
			return False
		else:
			print("无效选项,请重新选择")
		return True

	def handle_scene_management(self) -> None:
		"""处理场景管理"""
		if not self.editor.project:
			print("请先加载或创建项目")
			return
		print("\n场景管理:")
		print(" 1. 添加场景")
		print(" 2. 查看所有场景")
		print(" 3. 选择当前场景")
		print(" 4. 添加积木到场景")
		sub_choice = input("请选择: ").strip()
		if sub_choice == "1":
			name = input("场景名称: ").strip()
			screen_name = input("屏幕名称 [默认: 屏幕]: ").strip()
			if not screen_name:
				screen_name = "屏幕"
			scene_id = self.editor.project.add_scene(name, screen_name)
			print(f"已添加场景: {name} (ID: {scene_id})")
		elif sub_choice == "2":
			print("\n所有场景:")
			for scene_id, scene in self.editor.project.scenes.items():
				print(f"  ID: {scene_id}, 名称: {scene.name}, 角色数: {len(scene.actor_ids)}")
		elif sub_choice == "3":
			scene_name = input("请输入场景名称: ").strip()
			if self.editor.select_scene_by_name(scene_name):
				print(f"已选择场景: {scene_name}")
			else:
				print("场景未找到")
		elif sub_choice == "4":
			if not self.editor.current_entity_id:
				print("请先选择场景")
				return
			block_type = input("积木类型: ").strip()
			try:
				block = self.editor.add_block(block_type)
				if block:
					print(f"已添加积木: {block_type} (ID: {block.id})")
			except Exception as e:
				print(f"添加失败: {e}")

	def handle_actor_management(self) -> None:
		"""处理角色管理"""
		if not self.editor.project:
			print("请先加载或创建项目")
			return
		print("\n角色管理:")
		print(" 1. 添加角色")
		print(" 2. 查看所有角色")
		print(" 3. 选择当前角色")
		print(" 4. 添加积木到角色")
		sub_choice = input("请选择: ").strip()
		if sub_choice == "1":
			name = input("角色名称: ").strip()
			x = input("X坐标 [默认: 0]: ").strip()
			y = input("Y坐标 [默认: 0]: ").strip()
			position = {"x": 0.0, "y": 0.0}
			if x:
				with contextlib.suppress(ValueError):
					position["x"] = float(x)
			if y:
				with contextlib.suppress(ValueError):
					position["y"] = float(y)
			actor_id = self.editor.project.add_actor(name, position)
			print(f"已添加角色: {name} (ID: {actor_id})")
		elif sub_choice == "2":
			print("\n所有角色:")
			for actor_id, actor in self.editor.project.actors.items():
				print(f"  ID: {actor_id}, 名称: {actor.name}, 位置: ({actor.position['x']}, {actor.position['y']})")
		elif sub_choice == "3":
			actor_name = input("请输入角色名称: ").strip()
			if self.editor.select_actor_by_name(actor_name):
				print(f"已选择角色: {actor_name}")
			else:
				print("角色未找到")
		elif sub_choice == "4":
			if not self.editor.current_entity_id:
				print("请先选择角色")
				return
			block_type = input("积木类型: ").strip()
			try:
				block = self.editor.add_block(block_type)
				if block:
					print(f"已添加积木: {block_type} (ID: {block.id})")
			except Exception as e:
				print(f"添加失败: {e}")

	def handle_block_management(self) -> None:
		"""处理积木管理"""
		if not self.editor.project:
			print("请先加载或创建项目")
			return
		print("\n积木管理:")
		print(" 1. 查看所有积木")
		print(" 2. 查找积木")
		print(" 3. 查看积木统计")
		sub_choice = input("请选择: ").strip()
		if sub_choice == "1":
			all_blocks = self.editor.project.get_all_blocks()
			print(f"\n总积木数: {len(all_blocks)}")
			print("前10个积木:")
			for i, block in enumerate(all_blocks[:10]):
				print(f"  {i + 1}. ID: {block.id}, 类型: {block.type}")
		elif sub_choice == "2":
			block_id = input("请输入积木ID: ").strip()
			block = self.editor.project.find_block(block_id)
			if block:
				print(f"找到积木: ID={block.id}, 类型={block.type}")
				print(f"字段: {block.fields}")
			else:
				print("积木未找到")
		elif sub_choice == "3":
			stats = self.editor.project.workspace.get_statistics()
			print("\n积木统计信息:")
			for key, value in stats.items():
				if isinstance(value, dict):
					print(f"\n{key}:")
					for sub_key, sub_value in value.items():
						print(f"  {sub_key}: {sub_value}")
				else:
					print(f"{key}: {value}")

	def handle_resource_management(self) -> None:
		"""处理资源管理"""
		if not self.editor.project:
			print("请先加载或创建项目")
			return
		print("\n资源管理:")
		print(" 1. 添加变量")
		print(" 2. 添加音频")
		print(" 3. 查看所有资源")
		sub_choice = input("请选择: ").strip()
		if sub_choice == "1":
			name = input("变量名称: ").strip()
			value = input("初始值 [默认: 0]: ").strip()
			if not value:
				value = 0
			var_id = self.editor.project.add_variable(name, value)
			print(f"已添加变量: {name} (ID: {var_id})")
		elif sub_choice == "2":
			name = input("音频名称: ").strip()
			url = input("音频URL [可选]: ").strip()
			audio_id = self.editor.project.add_audio(name, url)
			print(f"已添加音频: {name} (ID: {audio_id})")
		elif sub_choice == "3":
			print("\n变量:")
			for var in self.editor.project.variables.values():
				print(f"  {var.get('name', 'Unknown')}: {var.get('value', 'N/A')}")

	def handle_export_xml(self) -> None:
		"""处理XML导出"""
		if not self.editor.project:
			print("请先加载或创建项目")
			return
		filepath = input("请输入XML导出路径: ").strip()
		try:
			self.editor.export_to_xml_file(filepath)
		except Exception as e:
			print(f"导出失败: {e}")

	def handle_search(self) -> None:
		"""处理查找功能"""
		if not self.editor.project:
			print("请先加载或创建项目")
			return
		search_type = input("查找类型 (block/actor/scene): ").strip().lower()
		if search_type == "block":
			search_term = input("请输入积木ID或类型关键词: ").strip()
			all_blocks = self.editor.project.get_all_blocks()
			found = [b for b in all_blocks if search_term in b.id or search_term in b.type]
			print(f"找到 {len(found)} 个积木")
			for block in found[:5]:
				print(f"  ID: {block.id}, 类型: {block.type}")
		elif search_type == "actor":
			search_term = input("请输入角色名称: ").strip()
			actor = self.editor.project.find_actor_by_name(search_term)
			if actor:
				print(f"找到角色: {actor.name} (ID: {actor.id})")
			else:
				print("角色未找到")
		elif search_type == "scene":
			search_term = input("请输入场景名称: ").strip()
			scene = self.editor.project.find_scene_by_name(search_term)
			if scene:
				print(f"找到场景: {scene.name} (ID: {scene.id})")
			else:
				print("场景未找到")

	def init_loop(self) -> None:
		# 主循环
		while True:
			print("\n请选择操作:")
			print(" 1. 创建新项目")
			print(" 2. 加载项目文件")
			print(" 3. 保存项目")
			print(" 4. 显示项目摘要")
			print(" 5. 分析项目结构")
			print(" 6. 管理场景")
			print(" 7. 管理角色")
			print(" 8. 管理积木")
			print(" 9. 管理变量/函数/音频")
			print("10. 导出为XML格式")
			print("11. 查找积木/角色/场景")
			print("12. 退出")
			choice = input("请输入选项 (1-12): ").strip()
			if not self.handle_menu_choice(choice):
				break
