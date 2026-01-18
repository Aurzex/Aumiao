"""服务类: 认证管理、文件上传、高级服务"""

import json
from collections import defaultdict
from collections.abc import Callable, Generator
from dataclasses import dataclass
from pathlib import Path
from time import sleep
from typing import Any, Literal, cast

from aumiao.core.base import VALID_REPLY_TYPES, ClassUnion, SourceConfigSimple, auth, data, decorator, toolkit
from aumiao.core.compile import CodemaoDecompiler
from aumiao.core.editorkn import KNEditor, KNProject
from aumiao.core.process import CommentProcessor, FileProcessor, ReplyProcessor, ReportAuthManager, ReportFetcher, ReportProcessor
from aumiao.core.retrieve import Obtain
from aumiao.utils.acquire import HTTPStatus


# ==============================
# 数据模型和辅助类
# ==============================
@dataclass
class UploadResult:
	"""文件上传结果"""

	file_path: Path
	url: str | None
	success: bool
	error: str | None = None


@dataclass
class WorkParsingRequest:
	"""作品解析请求"""

	comment_text: str
	sender_id: int
	sender_nickname: str
	business_id: int
	source_type: str
	target_id: int
	parent_id: int
	reply_id: str
	work_id: int
	commands: list[str] | None = None

	def __post_init__(self) -> None:
		if self.commands is None:
			self.commands = []


@dataclass
class AdminStatistics:
	"""管理员统计信息"""

	admin_id: int
	admin_name: str
	comment_reports: int
	work_reports: int


# ==============================
# 文件上传服务
# ==============================
@decorator.singleton
class FileUploadService:
	"""文件上传服务"""

	def __init__(self) -> None:
		self.uploader = FileProcessor()
		self._deprecated_methods = {"pgaot", "codegame"}

	def upload_file(self, file_path: str | Path, save_path: str = "aumiao", method: Literal["pgaot", "codemao", "codegame"] = "codemao") -> str | None:
		"""
		上传单个文件
		Args:
			file_path: 文件路径
			save_path: 保存路径
			method: 上传方法
		Returns:
			上传成功的 URL 或 None
		"""
		self._warn_deprecated_method(method)
		path = Path(file_path)
		if not path.is_file():
			print(f"文件不存在: {file_path}")
			return None
		return self.uploader.handle_file_upload(file_path=path, save_path=save_path, method=method)

	def upload_directory(
		self,
		dir_path: str | Path,
		save_path: str = "aumiao",
		method: Literal["pgaot", "codemao", "codegame"] = "codemao",
		*,
		recursive: bool = True,
	) -> dict[str, str | None]:
		"""
		上传整个目录
		Args:
			dir_path: 目录路径
			save_path: 保存路径
			method: 上传方法
			recursive: 是否递归上传
		Returns:
			文件路径到 URL 的映射字典
		"""
		self._warn_deprecated_method(method)
		path = Path(dir_path)
		if not path.is_dir():
			print(f"目录不存在: {dir_path}")
			return {}
		result = self.uploader.handle_directory_upload(dir_path=path, save_path=save_path, method=method, recursive=recursive)
		if isinstance(result, dict):
			return result
		return {}

	def upload(
		self,
		path: str | Path,
		save_path: str = "aumiao",
		method: Literal["pgaot", "codemao", "codegame"] = "codemao",
		*,
		recursive: bool = True,
	) -> str | dict[str, str | None] | None:
		"""
		通用上传方法, 自动判断是文件还是目录
		Args:
			path: 文件或目录路径
			save_path: 保存路径
			method: 上传方法
			recursive: 是否递归上传 (目录时有效)
		Returns:
			文件: 返回 URL
			目录: 返回字典
		"""
		self._warn_deprecated_method(method)
		path_obj = Path(path)
		if path_obj.is_file():
			return self.upload_file(path_obj, save_path, method)
		if path_obj.is_dir():
			return self.upload_directory(dir_path=path_obj, save_path=save_path, method=method, recursive=recursive)
		print(f"路径不存在: {path}")
		return None

	def _warn_deprecated_method(self, method: str) -> None:
		"""警告已弃用的方法"""
		if method in self._deprecated_methods:
			print("警告: 编程猫于 2025 年 10 月 22 日对对象存储进行限制")
			print("关闭了文件上传接口, 并更换域名 *.codemao.cn -> *.bcmcdn.com")
			print(f"方法 {method} 已弃用, 可能导致上传失败")


# ==============================
# 作品解析和自动回复服务
# ==============================
@decorator.singleton
class ReplyService:
	"""作品解析服务"""

	def __init__(self) -> None:
		self.coordinator = ClassUnion()
		self.processor = ReplyProcessor()
		self.file_upload = FileUploadService()

	def process_replies(self, valid_reply_types: set[str] | None = None) -> bool:
		"""
		处理自动回复, 包含作品解析功能
		Args:
			valid_reply_types: 有效的回复类型集合
		Returns:
			是否成功执行
		"""
		if valid_reply_types is None:
			valid_reply_types = VALID_REPLY_TYPES
		# 获取用户数据和格式化回复
		user_data = self._get_formatted_replies()
		formatted_answers = user_data["answers"]
		formatted_replies = user_data["replies"]
		# 获取新回复
		new_replies = self._get_new_replies(valid_reply_types)
		if not new_replies:
			print("没有需要回复的新通知")
			return False
		# 处理回复
		processed_count = 0
		for reply in new_replies:
			try:
				if self._process_single_reply(reply, formatted_answers, formatted_replies):
					processed_count += 1
					sleep(5)  # 防止请求过快
			except Exception as e:
				print(f"处理通知时发生错误: {e!s}")
		print(f"\n 处理完成, 共处理 {processed_count} 条通知")
		return processed_count > 0

	def parse_work_from_comment(self, work_id: int, *, is_author: bool = False, commands: list[str] | None = None) -> tuple[str, list[str]]:
		"""
		解析作品并生成报告
		Args:
			work_id: 作品 ID
			is_author: 是否为作者
			commands: 附加命令
		Returns:
			(报告内容, CDN 链接列表)
		"""
		try:
			# 获取作品详情
			work_details = self.coordinator.work_obtain.fetch_work_details(work_id)
			if not work_details:
				return "获取作品信息失败", []
			# 生成报告
			report = self.processor.generate_work_report(work_details=work_details, is_author=is_author, commands=commands or [])
			# 如果是作者且有编译命令, 编译作品
			cdn_links = []
			if is_author and commands and "compile" in commands:
				cdn_link = self._compile_work(work_id, work_details)
				if cdn_link:
					cdn_links = self.processor.split_long_cdn_link(cdn_link)
		except Exception as e:
			return f"解析作品时发生错误: {e!s}", []
		else:
			return report, cdn_links

	def _get_formatted_replies(self) -> dict:
		"""获取格式化的回复内容"""
		coordinator_data = self.coordinator.data
		formatted_answers = {}
		# 格式化答案
		for answer in coordinator_data.USER_DATA.answers:
			for keyword, resp in answer.items():
				if isinstance(resp, str):
					try:
						formatted_answers[keyword] = resp.format(**coordinator_data.INFO)
					except (KeyError, ValueError):
						formatted_answers[keyword] = resp
				elif isinstance(resp, list):
					# 处理列表中的每个字符串
					formatted_resp = []
					for item in resp:
						if isinstance(item, str):
							try:
								formatted_resp.append(item.format(**coordinator_data.INFO))
							except (KeyError, ValueError):
								formatted_resp.append(item)
						else:
							formatted_resp.append(item)
					formatted_answers[keyword] = formatted_resp
		# 格式化回复
		formatted_replies = []
		for reply in coordinator_data.USER_DATA.replies:
			if isinstance(reply, str):
				try:
					formatted_replies.append(reply.format(**coordinator_data.INFO))
				except (KeyError, ValueError):
					formatted_replies.append(reply)
			else:
				formatted_replies.append(reply)
		return {"answers": formatted_answers, "replies": formatted_replies}

	def _get_new_replies(self, valid_reply_types: set[str]) -> list:
		"""获取新的回复通知"""
		new_replies = self.coordinator.toolkit.create_data_processor().filter_by_nested_values(
			data=Obtain().get_new_replies(),
			id_path="type",
			target_values=list(valid_reply_types),
		)
		return new_replies or []

	def _process_single_reply(self, reply: dict, formatted_answers: dict, formatted_replies: list) -> bool:
		"""处理单个回复"""
		# 基础信息提取
		reply_id = reply.get("id", "")
		reply_type = reply.get("type", "")
		# 解析内容字段
		content_data = self.processor.parse_content_field(reply)
		if content_data is None:
			return False
		# 提取信息
		sender_info = content_data.get("sender", {})
		message_info = content_data.get("message", {})
		sender_id = sender_info.get("id", "")
		sender_nickname = sender_info.get("nickname", "未知用户")
		business_id = message_info.get("business_id")
		# 确定来源类型
		source_type = "work" if reply_type.startswith("WORK") else "post"
		# 提取文本内容
		comment_text = self.processor.extract_comment_text(reply_type, message_info)
		# 提取目标 ID
		target_id, parent_id = self.processor.extract_target_and_parent_ids(reply_type, reply, message_info, business_id, source_type)
		# 检查是否是作品解析请求
		if "@作品解析:" in comment_text:
			return self._handle_parsing_request(
				comment_text=comment_text,
				sender_id=sender_id,
				sender_nickname=sender_nickname,
				business_id=business_id,
				source_type=source_type,
				target_id=target_id,
				parent_id=parent_id,
				reply_id=reply_id,
			)
		# 普通回复处理
		return self._handle_normal_reply(
			comment_text=comment_text,
			formatted_answers=formatted_answers,
			formatted_replies=formatted_replies,
			source_type=source_type,
			business_id=business_id,
			target_id=target_id,
			parent_id=parent_id,
			reply_id=reply_id,
			reply_type=reply_type,
			sender_nickname=sender_nickname,
			sender_id=sender_id,
		)

	def _handle_parsing_request(self, **kwargs: Any) -> bool:
		"""处理作品解析请求"""
		try:
			request = WorkParsingRequest(
				comment_text=str(kwargs.get("comment_text", "")),
				sender_id=int(kwargs.get("sender_id", 0)),
				sender_nickname=str(kwargs.get("sender_nickname", "")),
				business_id=int(kwargs.get("business_id", 0)),
				source_type=str(kwargs.get("source_type", "")),
				target_id=int(kwargs.get("target_id", 0)),
				parent_id=int(kwargs.get("parent_id", 0)),
				reply_id=str(kwargs.get("reply_id", "")),
				work_id=0,  # 临时值, 将在后面设置
			)
		except (ValueError, TypeError):
			return False
		print(f"\n {'=' * 40}")
		print(f"检测到作品解析请求 [通知 ID: {request.reply_id}]")
		print(f"发送者: {request.sender_nickname} (ID: {request.sender_id})")
		try:
			# 提取作品信息
			work_info = self.processor.extract_work_info(request.comment_text)
			if not work_info:
				print("未找到有效的作品链接或 ID")
				return False
			request.work_id = work_info["work_id"]
			print(f"提取到作品 ID: {request.work_id}")
			# 获取作品详情
			work_details = self.coordinator.work_obtain.fetch_work_details(request.work_id)
			if not work_details:
				print("获取作品信息失败")
				return False
			# 检查作者身份
			work_author_id = work_details.get("user_info", {}).get("id", 0)
			is_author = str(request.sender_id) == str(work_author_id)
			print(f"作品名称: {work_details.get('work_name', ' 未知作品 ')}")
			print(f"作者 ID: {work_author_id}, 发送者是否为作者: {' 是 ' if is_author else ' 否 '}")
			# 解析命令
			request.commands = self.processor.parse_commands(request.comment_text)
			print(f"解析到命令: {request.commands or ' 无 '}")
			# 生成报告和链接
			report, cdn_links = self.parse_work_from_comment(work_id=request.work_id, is_author=is_author, commands=request.commands)
			# 发送消息
			self._send_parsing_result(request=request, _work_details=work_details, report=report, cdn_links=cdn_links, is_author=is_author)
		except Exception as e:
			print(f"处理作品解析时发生错误: {e!s}")
			return False
		else:
			return True

	def _handle_normal_reply(self, **kwargs: Any) -> bool:
		"""处理普通回复"""
		# 匹配关键词
		chosen, matched_keyword = self.processor.match_keyword(
			str(kwargs["comment_text"]),
			kwargs["formatted_answers"],
			kwargs["formatted_replies"],
		)
		# 打印日志
		self.processor.log_reply_info(
			kwargs["reply_id"],
			kwargs["reply_type"],
			kwargs["source_type"],
			kwargs["sender_nickname"],
			kwargs["sender_id"],
			"未知",  # business_name
			kwargs["comment_text"],
			matched_keyword,
			chosen,
		)
		# 发送回复
		result = self._send_reply(
			source_type=kwargs["source_type"],
			business_id=kwargs["business_id"],
			target_id=kwargs["target_id"],
			parent_id=kwargs["parent_id"],
			content=chosen,
		)
		if result:
			print(f"✓ 回复成功发送到 {kwargs['source_type']}")
			return True
		print("✗ 回复失败")
		return False

	def _send_parsing_result(self, request: WorkParsingRequest, _work_details: dict, report: str, cdn_links: list[str], *, is_author: bool) -> None:
		"""发送解析结果"""
		# 准备所有消息
		messages_to_send = []
		report_parts = self.processor.split_long_message(report)
		messages_to_send.extend(report_parts)
		messages_to_send.extend(cdn_links)
		print(f"总共需要发送 {len(messages_to_send)} 条消息")
		# 发送消息
		if is_author:
			print("作者身份确认, 准备多位置处理")
			# 发送作品评论
			print(f"发送作品评论到作品 {request.work_id}:")
			self.processor.send_messages_with_delay(
				messages=messages_to_send,
				send_func=lambda msg: self.coordinator.work_motion.create_work_comment(work_id=request.work_id, comment=msg, return_data=True),
				comment_type="作品评论",
			)
			# 如果在帖子中, 也发送到帖子
			if request.source_type == "post" and request.target_id > 0:
				print(f"发送回复到帖子评论 {request.target_id}:")
				self.processor.send_messages_with_delay(
					messages=messages_to_send,
					send_func=lambda msg: self.coordinator.forum_motion.create_comment_reply(
						reply_id=request.target_id,
						parent_id=request.parent_id,
						content=msg,
						return_data=True,
					),
					comment_type="帖子回复",
				)
		else:
			print("非作者身份, 仅在帖子下回复")
			if request.source_type == "post" and request.target_id > 0:
				print(f"发送回复到帖子评论 {request.target_id}:")
				self.processor.send_messages_with_delay(
					messages=messages_to_send,
					send_func=lambda msg: self.coordinator.forum_motion.create_comment_reply(
						reply_id=request.target_id,
						parent_id=request.parent_id,
						content=msg,
						return_data=True,
					),
					comment_type="帖子回复",
				)

	def _send_reply(self, source_type: str, business_id: int, target_id: int, parent_id: int, content: str) -> bool | dict:
		"""发送回复"""
		if source_type == "work":
			return self.coordinator.work_motion.create_comment_reply(work_id=business_id, comment_id=target_id, parent_id=parent_id, comment=content)
		# 修复类型错误: 确保参数是整数类型
		return self.coordinator.forum_motion.create_comment_reply(
			reply_id=int(target_id),  # 转换为整数
			parent_id=int(parent_id),  # 转换为整数
			content=content,
		)

	def _compile_work(self, work_id: int, work_details: dict) -> str | None:
		"""编译作品到 CDN"""
		try:
			print(f"编译作品 {work_id}...")
			print(f"作品名称: {work_details.get('work_name')}")
			print(f"积木块数: {work_details.get('n_brick')}")
			print(f"角色数量: {work_details.get('n_roles')}")
			if work_details.get("type", "NEMO") == "NEMO":
				print("不支持 NEMO 作品上传到编程猫 CDN")
				return None
			# 解压作品文件
			file_path = Path(CodemaoDecompiler().decompile(work_id=work_id))
			# 上传文件到 CDN
			return self.file_upload.upload_file(file_path=file_path, save_path="aumiao", method="codemao")
		except Exception as e:
			print(f"编译作品时发生错误: {e!s}")
			return None


# ==============================
# 社区动作服务
# ==============================
@decorator.singleton
class CommunityService:
	"""社区动作服务"""

	def __init__(self) -> None:
		self.coordinator = ClassUnion()
		self.comment_processor = CommentProcessor()
		self.printer = toolkit.create_output_handler()
		self.reply_service = ReplyService()
		coordinator = self.coordinator
		self.source_config: dict = {
			"work": SourceConfigSimple(
				get_items=lambda: coordinator.user_obtain.fetch_user_works_web_gen(data.AccountData.id, limit=None),
				get_comments=lambda _self, _id: Obtain().get_comments_detail(_id, "work", "comments"),
				delete=lambda self, _item_id, comment_id, is_reply: self._work_motion.delete_comment(comment_id, "comments" if is_reply else "replies"),
				title_key="work_name",
			),
			"post": SourceConfigSimple(
				get_items=lambda: coordinator.forum_obtain.fetch_my_posts_gen("created", limit=None),
				get_comments=lambda _self, _id: Obtain().get_comments_detail(_id, "post", "comments"),
				delete=lambda self, _item_id, comment_id, is_reply: self._forum_motion.delete_item(comment_id, "comments" if is_reply else "replies"),
				title_key="title",
			),
		}

	def clean_comments(self, source: Literal["work", "post"], action_type: Literal["ads", "duplicates", "blacklist"]) -> bool:
		"""
		清理评论
		Args:
			source: 数据来源 work = 作品评论 post = 帖子回复
			action_type: 处理类型 ads = 广告评论 duplicates = 重复刷屏 blacklist = 黑名单用户
		Returns:
			是否成功
		"""
		config = self.source_config[source]
		# 获取参数, 使用字典字面量类型注解
		params: dict[Literal["ads", "blacklist", "spam_max"], Any] = {
			"ads": self.coordinator.data.USER_DATA.ads,
			"blacklist": self.coordinator.data.USER_DATA.black_room,
			"spam_max": self.coordinator.setting.PARAMETER.spam_del_max,
		}
		# 处理目标列表
		target_lists = defaultdict(list)
		for item in config.get_items():
			self.comment_processor.process_item(item, config, action_type, params, target_lists)
		# 执行删除
		label_map = {"ads": "广告评论", "blacklist": "黑名单评论", "duplicates": "刷屏评论"}
		return self._execute_deletion(target_list=target_lists[action_type], delete_handler=config.delete, label=label_map[action_type])

	@staticmethod
	@decorator.skip_on_error
	def _execute_deletion(target_list: list, delete_handler: Callable[[int, int, bool], bool], label: str) -> bool:
		"""执行删除操作"""
		if not target_list:
			print(f"未发现 {label}")
			return True
		print(f"\n 发现以下 {label}(共 {len(target_list)} 条):")
		for item in reversed(target_list):
			print(f"- {item.split(':')[0]}")
		if input(f"\n 确认删除所有 {label}? (Y/N)").lower() != "y":
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

	def mark_notifications_as_read(self, method: Literal["nemo", "web"] = "web") -> bool:
		"""
		清除未读消息红点提示
		Args:
			method: 处理模式 web = 网页端消息类型 nemo = 客户端消息类型
		Returns:
			是否全部清除成功
		"""
		method_config = {
			"web": {
				"endpoint": "/web/message-record",
				"message_types": self.coordinator.setting.PARAMETER.all_read_type,
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
				endpoint = cast("str", config["endpoint"])
				if "{" in endpoint:
					endpoint = endpoint.format(type=msg_type)
				request_params = params.copy()
				if method == "web":
					request_params["query_type"] = cast("int", msg_type)
				response = self.coordinator.client.send_request(endpoint=endpoint, method="GET", params=request_params)
				responses[msg_type] = response.status_code
			return all(code == HTTPStatus.OK.value for code in responses.values())

		try:
			while True:
				current_counts = self.coordinator.community_obtain.fetch_message_count(method)
				if is_all_cleared(current_counts):
					return True
				if not send_batch_requests():
					return False
				params["offset"] += page_size
		except Exception as e:
			print(f"清除红点过程中发生异常: {e}")
			return False

	def like_and_collect_works(self, user_id: str, works_list: list[dict] | Generator[dict]) -> None:
		"""点赞和收藏用户作品"""
		self.coordinator.work_motion.execute_toggle_follow(user_id=int(user_id))
		for item in works_list:
			work_id = item.get("id")
			if isinstance(work_id, int):
				self.coordinator.work_motion.execute_toggle_like(work_id=work_id)
				self.coordinator.work_motion.execute_toggle_collection(work_id=work_id)

	def toggle_novel_favorites(self, novel_list: list[dict]) -> None:
		"""切换小说收藏状态"""
		for item in novel_list:
			novel_id = item.get("id")
			if isinstance(novel_id, int):
				self.coordinator.novel_motion.execute_toggle_novel_favorite(novel_id)

	def update_workshop_details(self, workshop_id: int | None = None) -> bool:
		"""更新工作室详情"""
		if workshop_id is None:
			detail = self.coordinator.shop_obtain.fetch_workshop_details_list()
			workshop_id = detail.get("id")
		if workshop_id is None:
			print("未找到工作室 ID")
			return False
		# 确保 workshop_id 是字符串类型
		workshop_id_str = str(workshop_id)
		workshop_detail = self.coordinator.shop_obtain.fetch_workshop_details(workshop_id_str)
		if not workshop_detail:
			print("获取工作室详情失败")
			return False
		result = self.coordinator.shop_motion.update_workshop_details(
			description=workshop_detail["description"],
			workshop_id=workshop_id_str,
			name=workshop_detail["name"],
			preview_url=workshop_detail["preview_url"],
		)
		return bool(result)

	def publish_novel_chapter(self, novel_id: int, chapter_index: int = 0) -> bool:
		"""发布小说章节"""
		novel_detail = self.coordinator.novel_obtain.fetch_novel_details(novel_id=novel_id)
		if not novel_detail:
			print("获取小说详情失败")
			return False
		chapters = novel_detail["data"]["sectionList"]
		if not chapters:
			print("该小说没有章节")
			return False
		if chapter_index >= len(chapters):
			print(f"章节索引超出范围, 最大索引: {len(chapters) - 1}")
			return False
		chapter_id = chapters[chapter_index]["id"]
		result = self.coordinator.novel_motion.publish_chapter(chapter_id)
		return bool(result)

	def get_account_status(self) -> dict:
		"""获取账户状态"""
		status = self.coordinator.user_obtain.fetch_account_details()
		return {"muted": status["voice_forbidden"], "agreement_signed": status["has_signed"]}

	def download_novel(self, novel_id: int, output_dir: Path | None = None) -> Path:
		"""
		下载小说内容
		Args:
			novel_id: 小说 ID
			output_dir: 输出目录
		Returns:
			小说目录路径
		"""
		details = self.coordinator.novel_obtain.fetch_novel_details(novel_id)
		if not details:
			msg = "获取小说详情失败"
			raise ValueError(msg)
		info = details["data"]["fanficInfo"]
		print(f"正在下载: {info['title']}-{info['nickname']}")
		print(f"简介: {info['introduction']}")
		print(f"类别: {info['fanfic_type_name']}")
		print(f"词数: {info['total_words']} 收藏数: {info['collect_times']}")
		print(f"更新时间: {self.coordinator.toolkit.create_time_utils().format_timestamp(info['update_time'])}")
		# 创建输出目录
		if output_dir is None:
			output_dir = data.PathConfig.FICTION_FILE_PATH
		novel_dir = output_dir / f"{info['title']}-{info['nickname']}"
		novel_dir.mkdir(parents=True, exist_ok=True)
		# 保存小说信息
		info_file = novel_dir / "info.json"
		with Path(info_file).open("w", encoding="utf-8") as f:
			json.dump(info, f, ensure_ascii=False, indent=2)
		# 下载章节
		chapters = details["data"]["sectionList"]
		for i, section in enumerate(chapters, 1):
			section_id = section["id"]
			section_title = section["title"]
			section_path = novel_dir / f"{i:03d}_{section_title}.txt"
			content_data = self.coordinator.novel_obtain.fetch_chapter_details(chapter_id=section_id)
			content = content_data["data"]["section"]["content"]
			formatted_content = self.coordinator.toolkit.create_data_converter().html_to_text(content, merge_empty_lines=True)
			self.coordinator.file.file_write(path=section_path, content=formatted_content)
			print(f"已下载章节: {section_title}")
		print(f"小说已保存到: {novel_dir}")
		return novel_dir

	def generate_miao_code(self, work_id: int) -> str | None:
		"""
		生成喵口令
		Args:
			work_id: 作品 ID
		Returns:
			喵口令字符串
		"""
		info = self.coordinator.client.send_request(endpoint=f"/creation-tools/v1/works/{work_id}", method="GET").json()
		print(f"作品名称: {info.get('work_name', info.get('name', '未知作品'))}")
		if info.get("type") != "NEMO":
			print(f"该作品类型为{info.get('type')}, 不能生成喵口令")
			return None
		work_info_url = f"/creation-tools/v1/works/{work_id}/source/public"
		work_info = self.coordinator.client.send_request(endpoint=work_info_url, method="GET").json()
		print(work_info)
		bcm_url = work_info["work_urls"][0]
		payload = {
			"app_version": "5.11.0",
			"bcm_version": "0.16.2",
			"equipment": "Aumiao",
			"name": work_info["name"],
			"os": "android",
			"preview": work_info["preview"],
			"work_id": work_id,
			"work_url": bcm_url,
		}
		response = self.coordinator.client.send_request(endpoint="/nemo/v2/miao-codes/bcm", method="POST", payload=payload)
		if response.status_code == HTTPStatus.OK.value:
			result = response.json()
			miao_code = f"【喵口令】$&{result['token']}&$"
			print(f"生成的喵口令: {miao_code}")
			return miao_code
		return None

	@staticmethod
	def analyze_comments_statistics(comments_data: list[dict], min_comments: int = 1) -> list[dict]:
		"""
		分析用户评论统计
		Args:
			comments_data: 用户评论数据列表
			min_comments: 最小评论数目阈值
		Returns:
			过滤后的用户数据
		"""
		filtered_users = [user for user in comments_data if user["comment_count"] >= min_comments]
		if not filtered_users:
			print(f"没有用户评论数达到或超过 {min_comments} 条")
			return []
		print(f"评论数达到 {min_comments}+ 的用户统计:")
		print("=" * 60)
		for user_data in filtered_users:
			nickname = user_data["nickname"]
			user_id = user_data["user_id"]
			comment_count = user_data["comment_count"]
			print(f"用户 {nickname} (ID: {user_id}) 发送了 {comment_count} 条评论")
			print("评论内容:")
			for i, comment in enumerate(user_data["comments"], 1):
				print(f"{i}. {comment}")
			print("*" * 50)
		return filtered_users

	def find_recent_posts(self, timeline: int) -> list[dict]:
		"""
		查找近期帖子
		Args:
			timeline: 时间戳, 查找此时间之后的帖子
		Returns:
			帖子列表
		"""
		print(f"正在查找发布时间在 {self.coordinator.toolkit.create_time_utils().format_timestamp(timeline)} 之后的帖子")
		post_list = self.coordinator.forum_obtain.fetch_hot_posts_ids()["items"][0:19]
		posts_details = self.coordinator.forum_obtain.fetch_posts_details(post_ids=post_list)["items"]
		recent_posts = []
		for post in posts_details:
			create_time = post["created_at"]
			if create_time > timeline:
				recent_posts.append(post)
				print(f"帖子 {post['title']}-ID {post['id']}- 发布于 {self.coordinator.toolkit.create_time_utils().format_timestamp(create_time)}")
		return recent_posts

	def get_admin_statistics(self) -> list[AdminStatistics]:
		"""获取管理员统计信息"""
		admins = [
			{"id": 220, "name": "石榴 Grant"},
			{"id": 222, "name": "shidang88"},
			{"id": 223, "name": "喵鱼 a"},
			{"id": 224, "name": "沙雕的初小白"},
			{"id": 225, "name": "旁观者 JErS"},
			{"id": 226, "name": "宜壳乐 Cat"},
			{"id": 227, "name": "凌风光耀 Aug"},
			{"id": 228, "name": "奇怪的小蜜桃"},
		]
		print("管理员处理统计报表")
		print("-" * 50)
		statistics = []
		for admin in admins:
			admin_id: int = cast("int", admin["id"])
			comment_count = self.coordinator.whale_obtain.fetch_comment_reports_total(
				source_type="ALL",
				status="ALL",
				filter_type="admin_id",
				target_id=admin_id,  # 确保是整数
			)["total"]
			work_count = self.coordinator.whale_obtain.fetch_work_reports_total(
				source_type="ALL",
				status="ALL",
				filter_type="admin_id",
				target_id=admin_id,  # 确保是整数
			)["total"]
			stats = AdminStatistics(
				admin_id=admin_id,  # 确保是整数
				admin_name=str(admin["name"]),  # 确保是字符串
				comment_reports=comment_count,
				work_reports=work_count,
			)
			statistics.append(stats)
			print(f"{admin['name']} (ID: {admin['id']}):")
			print(f"评论举报处理数: {comment_count}")
			print(f"作品举报处理数: {work_count}")
			print()
		return statistics


# ==============================
# 批量操作服务
# ==============================
@decorator.singleton
class BatchOperationService:
	"""批量操作服务"""

	def __init__(self) -> None:
		self.coordinator = ClassUnion()
		self.auth_manager = auth.AuthManager()
		self.community_service = CommunityService()

	def batch_like(
		self,
		user_id: int | None = None,
		content_type: Literal["work", "novel"] = "work",
		content_list: list | None = None,
		limit: int | None = None,
	) -> None:
		"""
		批量点赞内容
		Args:
			user_id: 用户 ID (仅当 content_type="work" 且 content_list 为 None 时有效)
			content_type: 内容类型 work = 作品 novel = 小说
			content_list: 内容列表, 如果为 None 则自动获取
			limit: 执行次数, 如果为 None 则使用全部 edu 账户
		"""
		# 获取内容列表
		if content_list:
			target_list = content_list
		elif content_type == "work" and user_id:
			target_list = list(self.coordinator.user_obtain.fetch_user_works_web_gen(str(user_id), limit=None))
		elif content_type == "novel":
			target_list = self.coordinator.novel_obtain.fetch_my_novels()
		else:
			msg = "必须提供 content_list 或 user_id"
			raise ValueError(msg)

		def action() -> None:
			self._batch_like_directly(target_list, content_type, user_id)

		Obtain().process_edu_accounts(limit=limit, action=action)

	def _batch_like_directly(self, target_list: list, content_type: str, user_id: int | None = None) -> int:
		"""直接批量点赞"""
		count = 0
		if content_type == "work" and user_id:
			self.community_service.like_and_collect_works(str(user_id), target_list)
			count = len(target_list)
		elif content_type == "novel":
			self.community_service.toggle_novel_favorites(target_list)
			count = len(target_list)
		print(f"已处理 {count} 个 {content_type}")
		return count

	def manage_edu_accounts(self, action: Literal["create", "delete", "token", "password"], limit: int | None = None) -> bool:
		"""
		管理教育账号
		Args:
			action: 操作类型 create = 创建 delete = 删除 token = 生成 token password = 生成密码
			limit: 限制数量
		Returns:
			是否成功
		"""
		total = self.coordinator.edu_obtain.fetch_class_students_total()
		print(f"可支配学生账号数: {total['total']}")
		if action == "delete":
			return self._delete_edu_accounts(limit)
		if action == "create":
			return self._create_edu_accounts(limit or 100)
		if action in {"token", "password"}:
			return self._generate_account_credentials(action, limit)
		print(f"不支持的操作类型: {action}")
		return False

	def _delete_edu_accounts(self, limit: int | None) -> bool:
		"""删除教育账号"""
		try:
			students = self.coordinator.edu_obtain.fetch_class_students_gen(limit=limit)
			deleted_count = 0
			for student in students:
				self.coordinator.edu_motion.delete_student_from_class(stu_id=student["id"])
				deleted_count += 1
				print(f"已删除学生: {student.get('name', 'Unknown')}")
			print(f"共删除 {deleted_count} 个学生账号")
		except Exception as e:
			print(f"删除学生账号失败: {e!s}")
			return False
		else:
			return True

	def _create_edu_accounts(self, student_limit: int) -> bool:
		"""创建教育账号"""
		try:
			class_capacity = 95
			class_count = (student_limit + class_capacity - 1) // class_capacity
			generator = toolkit.create_edu_data_generator()
			# 生成班级和学生名称
			class_names = generator.generate_class_names(num_classes=class_count, add_specialty=True)
			student_names = generator.generate_student_names(num_students=student_limit)
			created_count = 0
			for class_idx in range(class_count):
				# 创建班级
				class_result = self.coordinator.edu_motion.create_class(name=class_names[class_idx])
				class_id = class_result["id"]
				print(f"创建班级: {class_names[class_idx]} (ID: {class_id})")
				# 添加学生
				start = class_idx * class_capacity
				end = min(start + class_capacity, student_limit)
				batch_names = student_names[start:end]
				self.coordinator.edu_motion.add_students_to_class(name=batch_names, class_id=class_id)
				created_count += len(batch_names)
				print(f"添加了 {len(batch_names)} 名学生到班级")
			print(f"共创建 {created_count} 个学生账号")
		except Exception as e:
			print(f"创建学生账号失败: {e!s}")
			return False
		else:
			return True

	def _generate_account_credentials(self, cred_type: Literal["token", "password"], limit: int | None) -> bool:
		"""生成账号凭证"""
		try:
			accounts = Obtain().switch_edu_account(limit=limit, return_method="list")
			credentials = []
			for identity, password in accounts:
				if cred_type == "token":
					# 登录获取 token
					response = self.auth_manager.login(identity=identity, password=password, status="edu", prefer_method="simple_password")
					credential = response["data"]["auth"]["token"]
					file_path = data.PathConfig.TOKEN_FILE_PATH
					file_method = "a"  # 追加模式
				else:  # password
					credential = password
					file_path = data.PathConfig.PASSWORD_FILE_PATH
					file_method = "a"
				credentials.append(credential)
				# 写入文件
				content = f"{credential}\n" if cred_type == "token" else f"{identity}:{credential}\n"
				self.coordinator.file.file_write(path=file_path, content=content, method=file_method)
			print(f"已生成 {len(credentials)} 个 {cred_type}")
		except Exception as e:
			print(f"生成 {cred_type} 失败: {e!s}")
			return False
		else:
			return True

	def batch_report_work(self, work_id: int, reason: str = "违法违规") -> None:
		"""
		批量举报作品
		Args:
			work_id: 作品 ID
			reason: 举报原因
			use_edu_accounts: 是否使用教育账号
			account_limit: 账号数量限制
		Returns:
			举报数量
		"""
		hidden_border = 10
		Obtain().process_edu_accounts(limit=hidden_border, action=lambda: self.coordinator.work_motion.execute_report_work(describe="", reason=reason, work_id=work_id))

	def create_comment(self, target_id: int, content: str, source_type: Literal["work", "shop", "post"]) -> bool:
		"""
		创建评论 / 回复
		Args:
			target_id: 目标 ID
			content: 评论内容
			source_type: 来源类型
		Returns:
			是否成功
		"""
		try:
			if source_type == "post":
				result = self.coordinator.forum_motion.create_post_reply(post_id=target_id, content=content)
			elif source_type == "shop":
				result = self.coordinator.shop_motion.create_comment(workshop_id=target_id, content=content, rich_content=content)
			elif source_type == "work":
				result = self.coordinator.work_motion.create_work_comment(work_id=target_id, comment=content)
			else:
				msg = f"不支持的来源类型: {source_type}"
				raise ValueError(msg)  # noqa: TRY301
			return bool(result)
		except Exception as e:
			print(f"创建评论失败: {e!s}")
			return False

	def report_item(
		self,
		source_type: Literal["forum", "work", "shop"],
		target_id: int,
		reason_id: Literal[0, 1, 2, 3, 4, 5, 6, 7, 8],
		reason_content: str,
		description: str = "",
		*,
		is_reply: bool = False,
		parent_id: int | None = None,
	) -> bool:
		"""
		执行举报操作
		Args:
			source_type: 来源类型
			target_id: 目标 ID
			reason_id: 原因 ID
			reason_content: 原因内容
			description: 描述
			is_reply: 是否为回复
			parent_id: 父 ID (仅 shop 类型需要)
		Returns:
			是否成功
		"""
		try:
			if source_type == "work":
				return self.coordinator.work_motion.execute_report_comment(
					work_id=target_id,
					comment_id=target_id,
					reason=reason_content,
				)
			if source_type == "forum":
				item_type = "COMMENT" if is_reply else "REPLY"
				return self.coordinator.forum_motion.report_item(item_id=target_id, reason_id=reason_id, description=description, item_type=item_type, return_data=False)
			if source_type == "shop":
				if is_reply and parent_id is not None:
					return self.coordinator.shop_motion.execute_report_comment(
						comment_id=target_id,
						reason_content=reason_content,
						reason_id=reason_id,
						reporter_id=int(self.coordinator.data.ACCOUNT_DATA.id),
						comment_parent_id=parent_id,
						description=description,
					)
				return self.coordinator.shop_motion.execute_report_comment(
					comment_id=target_id,
					reason_content=reason_content,
					reason_id=reason_id,
					reporter_id=int(self.coordinator.data.ACCOUNT_DATA.id),
					description=description,
				)
			print(f"不支持的来源类型: {source_type}")
		except Exception as e:
			print(f"举报操作失败: {e!s}")
			return False
		else:
			return False


# ==============================
# 举报处理服务
# ==============================
@decorator.singleton
class ReportService:
	"""举报处理服务"""

	def __init__(self) -> None:
		self.coordinator = ClassUnion()
		self.report_manager = ReportAuthManager()
		self.report_processor = ReportProcessor()
		self.report_fetcher = ReportFetcher()
		self.printer = toolkit.create_output_handler()
		self.processed_count = 0
		self.total_reports = 0

	def process_reports(self, admin_id: int) -> bool:
		"""
		处理举报主流程
		Args:
			admin_id: 管理员 ID
		Returns:
			是否成功
		"""
		self.printer.print_header("=== 举报处理系统 ===")
		# 加载学生账号
		self.report_manager.load_student_accounts()
		# 主处理循环
		while True:
			self.total_reports = self.report_fetcher.get_total_reports(status="TOBEDONE")
			if self.total_reports == 0:
				self.printer.print_message("当前没有待处理的举报", "INFO")
				break
			self.printer.print_message(f"发现 {self.total_reports} 条待处理举报", "INFO")
			# 处理举报
			batch_processed = self.report_processor.process_all_reports(admin_id)
			self.processed_count += batch_processed
			self.printer.print_message(f"本次处理完成: {batch_processed} 条举报", "SUCCESS")
			# 询问是否继续
			continue_choice = self.printer.get_valid_input(prompt="是否继续检查新举报? (Y/N)", valid_options={"Y", "N"}).upper()
			if continue_choice != "Y":
				break
			self.printer.print_message("重新获取新举报...", "INFO")
		# 显示统计结果
		self.printer.print_header("=== 处理结果统计 ===")
		self.printer.print_message(f"本次会话共处理 {self.processed_count} 条举报", "SUCCESS")
		# 终止会话
		self._auth_manager().terminate_session()
		return True

	def get_report_statistics(
		self,
		source_type: Literal["KITTEN", "BOX2", "ALL"] = "ALL",
		status: Literal["TOBEDONE", "DONE", "ALL"] = "ALL",
	) -> dict:
		"""
		获取举报统计信息
		Args:
			source_type: 来源类型
			status: 状态
		Returns:
			统计信息
		"""
		comment_stats = self.coordinator.whale_obtain.fetch_comment_reports_total(source_type=source_type, status=status)
		work_stats = self.coordinator.whale_obtain.fetch_work_reports_total(source_type=source_type, status=status)
		return {"comment_reports": comment_stats, "work_reports": work_stats, "total": comment_stats.get("total", 0) + work_stats.get("total", 0)}

	@staticmethod
	def _auth_manager() -> auth.AuthManager:
		"""获取认证管理器 (延迟加载)"""
		return auth.AuthManager()


# ==============================
# KN 编辑器服务
# ==============================
@decorator.singleton
class KNEditorService:
	"""KN 编辑器服务"""

	def __init__(self) -> None:
		self.editor = KNEditor()
		self.current_project: KNProject | None = None
		self.printer = toolkit.create_output_handler()

	def create_project(self, name: str) -> bool:
		"""创建新项目"""
		try:
			self.current_project = KNProject(name)
			self.editor.project = self.current_project
			print(f"已创建新项目: {name}")
		except Exception as e:
			print(f"创建项目失败: {e}")
			return False
		else:
			return True

	def load_project(self, filepath: str) -> bool:
		"""加载项目"""
		try:
			self.editor.load_project(filepath)
			self.current_project = self.editor.project
			print(f"已加载项目: {filepath}")
		except Exception as e:
			print(f"加载项目失败: {e}")
			return False
		else:
			return True

	def save_project(self, filepath: str | Path | None = None) -> bool:
		"""保存项目"""
		if not self.current_project:
			print("没有当前项目")
			return False
		try:
			save_path = filepath or self.current_project.filepath
			if not save_path:
				print("请提供保存路径")
				return False
			self.editor.save_project(save_path)
			print(f"项目已保存到: {save_path}")
		except Exception as e:
			print(f"保存项目失败: {e}")
			return False
		else:
			return True

	def show_project_info(self) -> None:
		"""显示项目信息"""
		if self.current_project:
			self.editor.print_project_info()
		else:
			print("请先加载或创建项目")

	def analyze_project(self) -> dict | None:
		"""分析项目结构"""
		if not self.current_project:
			print("请先加载或创建项目")
			return None
		analysis = self.current_project.analyze_project()
		print("\n" + "=" * 60)
		print("项目详细分析:")
		print("=" * 60)
		for key, value in analysis.items():
			if key in {"block_type_counts", "category_counts"}:
				print(f"\n {key}:")
				for sub_key, sub_value in value.items():
					print(f"{sub_key}: {sub_value}")
			else:
				print(f"{key}: {value}")
		return analysis

	def add_scene(self, name: str, screen_name: str = "屏幕") -> str | None:
		"""添加场景"""
		if not self.current_project:
			print("请先加载或创建项目")
			return None
		try:
			scene_id = self.current_project.add_scene(name, screen_name)
			print(f"已添加场景: {name} (ID: {scene_id})")
		except Exception as e:
			print(f"添加场景失败: {e}")
			return None
		else:
			return scene_id

	def add_actor(self, name: str, x: float = 0.0, y: float = 0.0) -> str | None:
		"""添加角色"""
		if not self.current_project:
			print("请先加载或创建项目")
			return None
		try:
			position = {"x": x, "y": y}
			actor_id = self.current_project.add_actor(name, position)
			print(f"已添加角色: {name} (ID: {actor_id})")
		except Exception as e:
			print(f"添加角色失败: {e}")
			return None
		else:
			return actor_id

	def add_block(self, block_type: str, entity_name: str | None = None) -> Any | None:
		"""添加积木"""
		if not self.current_project:
			print("请先加载或创建项目")
			return None
		# 选择实体 (场景或角色)
		if entity_name:
			if self.editor.select_scene_by_name(entity_name):
				print(f"选择场景: {entity_name}")
			elif self.editor.select_actor_by_name(entity_name):
				print(f"选择角色: {entity_name}")
			else:
				print(f"未找到实体: {entity_name}")
				return None
		if not self.editor.current_entity_id:
			print("请先选择场景或角色")
			return None
		try:
			block = self.editor.add_block(block_type)
			if block:
				print(f"已添加积木: {block_type} (ID: {block.id})")
		except Exception as e:
			print(f"添加积木失败: {e}")
			return None
		else:
			return block

	def list_scenes(self) -> list:
		"""列出所有场景"""
		if not self.current_project:
			return []
		scenes = []
		for scene_id, scene in self.current_project.scenes.items():
			scenes.append({"id": scene_id, "name": scene.name, "actor_count": len(scene.actor_ids)})
		print("\n 所有场景:")
		for scene in scenes:
			print(f"ID: {scene['id']}, 名称: {scene['name']}, 角色数: {scene['actor_count']}")
		return scenes

	def list_actors(self) -> list:
		"""列出所有角色"""
		if not self.current_project:
			return []
		actors = []
		for actor_id, actor in self.current_project.actors.items():
			actors.append({"id": actor_id, "name": actor.name, "x": actor.position.get("x", 0), "y": actor.position.get("y", 0)})
		print("\n 所有角色:")
		for actor in actors:
			print(f"ID: {actor['id']}, 名称: {actor['name']}, 位置: ({actor['x']}, {actor['y']})")
		return actors

	def get_block_statistics(self) -> dict | None:
		"""获取积木统计信息"""
		if not self.current_project:
			return None
		stats = self.current_project.workspace.get_statistics()
		print("\n 积木统计信息:")
		for key, value in stats.items():
			if isinstance(value, dict):
				print(f"\n {key}:")
				for sub_key, sub_value in value.items():
					print(f"{sub_key}: {sub_value}")
			else:
				print(f"{key}: {value}")
		return stats

	def add_variable(self, name: str, value: Any = 0) -> str | None:
		"""添加变量"""
		if not self.current_project:
			print("请先加载或创建项目")
			return None
		try:
			var_id = self.current_project.add_variable(name, value)
			print(f"已添加变量: {name} (ID: {var_id})")
		except Exception as e:
			print(f"添加变量失败: {e}")
			return None
		else:
			return var_id

	def add_audio(self, name: str, url: str) -> str | None:
		"""添加音频"""
		if not self.current_project:
			print("请先加载或创建项目")
			return None
		try:
			audio_id = self.current_project.add_audio(name, url)
			print(f"已添加音频: {name} (ID: {audio_id})")
		except Exception as e:
			print(f"添加音频失败: {e}")
			return None
		else:
			return audio_id

	def export_to_xml(self, filepath: str) -> bool:
		"""导出为 XML 格式"""
		if not self.current_project:
			print("请先加载或创建项目")
			return False
		try:
			self.editor.export_to_xml_file(filepath)
			print(f"项目已导出到: {filepath}")
		except Exception as e:
			print(f"导出失败: {e}")
			return False
		else:
			return True

	def search(self, search_type: Literal["block", "actor", "scene"], search_term: str) -> list:
		"""查找内容"""
		if not self.current_project:
			return []
		results = []
		if search_type == "block":
			all_blocks = self.current_project.get_all_blocks()
			found = [b for b in all_blocks if search_term in b.id or search_term in b.type]
			results = found
			print(f"找到 {len(found)} 个积木")
			for block in found[:5]:
				print(f"ID: {block.id}, 类型: {block.type}")
		elif search_type == "actor":
			actor = self.current_project.find_actor_by_name(search_term)
			if actor:
				results = [actor]
				print(f"找到角色: {actor.name} (ID: {actor.id})")
			else:
				print("角色未找到")
		elif search_type == "scene":
			scene = self.current_project.find_scene_by_name(search_term)
			if scene:
				results = [scene]
				print(f"找到场景: {scene.name} (ID: {scene.id})")
			else:
				print("场景未找到")
		return results

	def run_cli(self) -> None:
		"""运行命令行界面"""
		while True:
			print("\n 请选择操作:")
			print("1. 创建新项目")
			print("2. 加载项目文件")
			print("3. 保存项目")
			print("4. 显示项目摘要")
			print("5. 分析项目结构")
			print("6. 管理场景")
			print("7. 管理角色")
			print("8. 管理积木")
			print("9. 管理变量 / 函数 / 音频")
			print("10. 导出为 XML 格式")
			print("11. 查找积木 / 角色 / 场景")
			print("12. 退出")
			choice = input("请输入选项 (1-12):").strip()
			if choice == "1":
				project_name = input("请输入项目名称:").strip()
				self.create_project(project_name)
			elif choice == "2":
				filepath = input("请输入项目文件路径 (.bcmkn):").strip()
				self.load_project(filepath)
			elif choice == "3":
				if self.current_project and self.current_project.filepath:
					save_path = input(f"保存路径 [{self.current_project.filepath}]:").strip()
					if not save_path:
						save_path = self.current_project.filepath
				else:
					save_path = input("请输入保存路径:").strip()
				self.save_project(save_path)
			elif choice == "4":
				self.show_project_info()
			elif choice == "5":
				self.analyze_project()
			elif choice == "6":
				self._handle_scene_menu()
			elif choice == "7":
				self._handle_actor_menu()
			elif choice == "8":
				self._handle_block_menu()
			elif choice == "9":
				self._handle_resource_menu()
			elif choice == "10":
				filepath = input("请输入 XML 导出路径:").strip()
				self.export_to_xml(filepath)
			elif choice == "11":
				self._handle_search_menu()
			elif choice == "12":
				print("感谢使用, 再见!")
				break
			else:
				print("无效选项, 请重新选择")

	def _handle_scene_menu(self) -> None:
		"""处理场景菜单"""
		print("\n 场景管理:")
		print("1. 添加场景")
		print("2. 查看所有场景")
		print("3. 选择当前场景")
		print("4. 添加积木到场景")
		sub_choice = input("请选择:").strip()
		if sub_choice == "1":
			name = input("场景名称:").strip()
			screen_name = input("屏幕名称 [默认: 屏幕]:").strip() or "屏幕"
			self.add_scene(name, screen_name)
		elif sub_choice == "2":
			self.list_scenes()
		elif sub_choice == "3":
			scene_name = input("请输入场景名称:").strip()
			if self.editor.select_scene_by_name(scene_name):
				print(f"已选择场景: {scene_name}")
			else:
				print("场景未找到")
		elif sub_choice == "4":
			entity_name = input("请输入场景名称:").strip()
			block_type = input("积木类型:").strip()
			self.add_block(block_type, entity_name)

	def _handle_actor_menu(self) -> None:
		"""处理角色菜单"""
		print("\n 角色管理:")
		print("1. 添加角色")
		print("2. 查看所有角色")
		print("3. 选择当前角色")
		print("4. 添加积木到角色")
		sub_choice = input("请选择:").strip()
		if sub_choice == "1":
			name = input("角色名称:").strip()
			x = input("X 坐标 [默认: 0]:").strip()
			y = input("Y 坐标 [默认: 0]:").strip()
			x_pos = float(x) if x else 0.0
			y_pos = float(y) if y else 0.0
			self.add_actor(name, x_pos, y_pos)
		elif sub_choice == "2":
			self.list_actors()
		elif sub_choice == "3":
			actor_name = input("请输入角色名称:").strip()
			if self.editor.select_actor_by_name(actor_name):
				print(f"已选择角色: {actor_name}")
			else:
				print("角色未找到")
		elif sub_choice == "4":
			entity_name = input("请输入角色名称:").strip()
			block_type = input("积木类型:").strip()
			self.add_block(block_type, entity_name)

	def _handle_block_menu(self) -> None:
		"""处理积木菜单"""
		print("\n 积木管理:")
		print("1. 查看所有积木")
		print("2. 查找积木")
		print("3. 查看积木统计")
		sub_choice = input("请选择:").strip()
		if sub_choice == "1":
			if self.current_project:
				all_blocks = self.current_project.get_all_blocks()
				print(f"\n 总积木数: {len(all_blocks)}")
				print("前 10 个积木:")
				for i, block in enumerate(all_blocks[:10]):
					print(f"{i + 1}. ID: {block.id}, 类型: {block.type}")
		elif sub_choice == "2":
			block_id = input("请输入积木 ID:").strip()
			if self.current_project:
				block = self.current_project.find_block(block_id)
				if block:
					print(f"找到积木: ID={block.id}, 类型 ={block.type}")
					print(f"字段: {block.fields}")
				else:
					print("积木未找到")
		elif sub_choice == "3":
			self.get_block_statistics()

	def _handle_resource_menu(self) -> None:
		"""处理资源菜单"""
		print("\n 资源管理:")
		print("1. 添加变量")
		print("2. 添加音频")
		print("3. 查看所有资源")
		sub_choice = input("请选择:").strip()
		if sub_choice == "1":
			name = input("变量名称:").strip()
			value = input("初始值 [默认: 0]:").strip()
			value = value or 0
			self.add_variable(name, value)
		elif sub_choice == "2":
			name = input("音频名称:").strip()
			url = input("音频 URL [可选]:").strip()
			self.add_audio(name, url)
		elif sub_choice == "3":
			if self.current_project:
				print("\n 变量:")
				for var in self.current_project.variables.values():
					print(f"{var.get('name', 'Unknown')}: {var.get('value', 'N/A')}")

	def _handle_search_menu(self) -> None:
		"""处理查找菜单"""
		search_type = cast("Literal ['block', 'actor', 'scene']", input("查找类型 (block/actor/scene):").strip())
		if search_type not in {"block", "actor", "scene"}:
			print("无效的查找类型")
			return
		search_term = input("请输入搜索关键词:").strip()
		self.search(search_type, search_term)  # 类型提示已经在上面的检查中确保正确


# ==============================
# 服务管理器 (统一入口)
# ==============================
@decorator.singleton
class ServiceManager:
	"""服务管理器, 提供统一的服务访问入口"""

	def __init__(self) -> None:
		self._services = {}

	@property
	def file_upload(self) -> FileUploadService:
		"""文件上传服务"""
		if "file_upload" not in self._services:
			self._services["file_upload"] = FileUploadService()
		return self._services["file_upload"]

	@property
	def reply(self) -> ReplyService:
		"""作品解析服务"""
		if "reply_service" not in self._services:
			self._services["reply_service"] = ReplyService()
		return self._services["reply_service"]

	@property
	def community(self) -> CommunityService:
		"""社区动作服务"""
		if "community" not in self._services:
			self._services["community"] = CommunityService()
		return self._services["community"]

	@property
	def batch_operations(self) -> BatchOperationService:
		"""批量操作服务"""
		if "batch_operations" not in self._services:
			self._services["batch_operations"] = BatchOperationService()
		return self._services["batch_operations"]

	@property
	def report(self) -> ReportService:
		"""举报处理服务"""
		if "report" not in self._services:
			self._services["report"] = ReportService()
		return self._services["report"]

	@property
	def kn_editor(self) -> KNEditorService:
		"""KN 编辑器服务"""
		if "kn_editor" not in self._services:
			self._services["kn_editor"] = KNEditorService()
		return self._services["kn_editor"]

	def clear_cache(self) -> None:
		"""清除所有服务缓存"""
		self._services.clear()


# ==============================
# 全局实例和别名
# ==============================
# 全局服务管理器实例
services = ServiceManager()
