from collections import defaultdict
from collections.abc import Callable, Generator
from pathlib import Path
from time import sleep
from typing import Any, Literal, cast

from aumiao.core.base import coordinator
from aumiao.core.cloudcfg import CloudAPI
from aumiao.core.models import VALID_REPLY_TYPES, SourceConfigSimple
from aumiao.core.process import CommentProcessor, FileProcessor, MultiAccount, ReplyProcessor, ReportFetcher, ReportProcessor
from aumiao.core.retrieve import Obtain
from aumiao.utils.acquire import CodeMaoClient, HTTPStatus
from aumiao.utils.decorator import singleton, skip_on_error


# ==============================
# 文件上传服务
# ==============================
@singleton
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
# 自动回复服务
# ==============================
@singleton
class ReplyService:
	"""自动回复服务服务"""

	def __init__(self) -> None:
		self.processor = ReplyProcessor()
		self.file_upload = FileUploadService()

	def process_replies(self, valid_reply_types: set[str] | None = None) -> bool:
		"""
		处理自动回复
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

	@staticmethod
	def _get_formatted_replies() -> dict:
		"""获取格式化的回复内容"""
		coordinator_data = coordinator.data_manager
		formatted_answers = {}
		# 格式化答案
		for answer in coordinator_data.data.USER_DATA.answers:
			for keyword, resp in answer.items():
				if isinstance(resp, str):
					try:
						formatted_answers[keyword] = resp.format(**coordinator_data.data.INFO)
					except (KeyError, ValueError):
						formatted_answers[keyword] = resp
				elif isinstance(resp, list):
					# 处理列表中的每个字符串
					formatted_resp = []
					for item in resp:
						if isinstance(item, str):
							try:
								formatted_resp.append(item.format(**coordinator_data.data.INFO))
							except (KeyError, ValueError):
								formatted_resp.append(item)
						else:
							formatted_resp.append(item)
					formatted_answers[keyword] = formatted_resp
		# 格式化回复
		formatted_replies = []
		for reply in coordinator_data.data.USER_DATA.replies:
			if isinstance(reply, str):
				try:
					formatted_replies.append(reply.format(**coordinator_data.data.INFO))
				except (KeyError, ValueError):
					formatted_replies.append(reply)
			else:
				formatted_replies.append(reply)
		return {"answers": formatted_answers, "replies": formatted_replies}

	@staticmethod
	def _get_new_replies(valid_reply_types: set[str]) -> list:
		"""获取新的回复通知"""
		new_replies = coordinator.toolkit.create_data_processor().filter_by_nested_values(
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
		source_type = "work" if reply_type.startswith("WORK") else "forum"
		# 提取文本内容
		comment_text = self.processor.extract_comment_text(reply_type, message_info)
		# 提取目标 ID
		target_id, parent_id = self.processor.extract_target_and_parent_ids(reply_type, reply, message_info, business_id, source_type)
		# 回复处理
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

	@staticmethod
	def _send_reply(source_type: str, business_id: int, target_id: int, parent_id: int, content: str) -> bool | dict:
		"""发送回复"""
		if source_type == "work":
			return coordinator.work_motion.create_comment_reply(work_id=business_id, comment_id=target_id, parent_id=parent_id, comment=content)
		# 修复类型错误: 确保参数是整数类型
		return coordinator.forum_motion.create_comment_reply(
			reply_id=int(target_id),  # 转换为整数
			parent_id=int(parent_id),  # 转换为整数
			content=content,
		)


# ==============================
# 社区动作服务
# ==============================
@singleton
class CommunityService:
	"""社区动作服务"""

	def __init__(self) -> None:
		self.comment_processor = CommentProcessor()
		self.reply_service = ReplyService()
		self.source_config: dict = {
			"work": SourceConfigSimple(
				get_items=lambda: coordinator.user_obtain.fetch_user_works_web_gen(coordinator.data_manager.data.ACCOUNT_DATA.id, limit=None),
				get_comments=lambda _self, _id: Obtain().get_comments(source_id=_id, source="work", method="comments"),
				delete=lambda self, _item_id, comment_id, is_reply: self._work_motion.delete_comment(comment_id, "comments" if is_reply else "replies"),
				title_key="work_name",
			),
			"forum": SourceConfigSimple(
				get_items=lambda: coordinator.forum_obtain.fetch_my_posts_gen("created", limit=None),
				get_comments=lambda _self, _id: Obtain().get_comments(source_id=_id, source="forum", method="comments"),
				delete=lambda self, _item_id, comment_id, is_reply: self._forum_motion.delete_item(comment_id, "comments" if is_reply else "replies"),
				title_key="title",
			),
		}

	def clean_comments(self, source: Literal["work", "forum"], action_type: Literal["ads", "duplicates", "blacklist"]) -> dict:
		"""
		清理评论
		Args:
			source: 数据来源 work = 作品评论 post = 帖子回复
			action_type: 处理类型 ads = 广告评论 duplicates = 重复刷屏 blacklist = 黑名单用户
		Returns:
			清理结果数据
		"""
		config: SourceConfigSimple = cast("SourceConfigSimple", self.source_config[source])
		params: dict[Literal["ads", "blacklist", "duplicates"], Any] = {
			"ads": coordinator.data_manager.data.USER_DATA.ads,
			"blacklist": coordinator.data_manager.data.USER_DATA.black_room,
			"duplicates": coordinator.setting_manager.data.PARAMETER.spam_del_max,
		}
		target_lists = defaultdict(list)
		for item in config.get_items():
			self.comment_processor.process_item(item, config, action_type, params, target_lists, source)
		label_map = {"ads": "广告评论", "blacklist": "黑名单评论", "duplicates": "刷屏评论"}
		result = self._execute_comment_deletion(target_list=target_lists[action_type], delete_handler=config.delete, label=label_map[action_type])
		return {
			"success": result["success"],
			"action_type": action_type,
			"label": label_map[action_type],
			"found_count": len(target_lists[action_type]),
			"deleted_count": result["deleted_count"],
			"details": result["details"],
		}

	@staticmethod
	@skip_on_error
	def _execute_comment_deletion(target_list: list, delete_handler: Callable[[int, int, bool], bool], label: str) -> dict:
		"""执行删除操作"""
		if not target_list:
			print(f"未发现 {label}")
			return {"success": True, "deleted_count": 0, "details": []}
		print(f"\n 发现以下 {label}(共 {len(target_list)} 条):")
		for item in reversed(target_list):
			print(f"- {item}")
		if input(f"\n 确认删除所有 {label}? (Y/N)").lower() != "y":
			print("操作已取消")
			return {"success": False, "deleted_count": 0, "details": []}
		deleted_count = 0
		details = []
		for entry in reversed(target_list):
			parts = entry.split(":")[0].split(".")
			item_id, comment_id = map(int, parts)
			is_reply = ":reply" in entry
			if not delete_handler(item_id, comment_id, is_reply):
				print(f"删除失败: {entry}")
				details.append({"entry": entry, "status": "failed"})
			else:
				print(f"已删除: {entry}")
				deleted_count += 1
				details.append({"entry": entry, "status": "success"})
		return {"success": True, "deleted_count": deleted_count, "details": details}

	@staticmethod
	def mark_notifications_as_read(method: Literal["nemo", "web"] = "web") -> dict:
		"""
		清除未读消息红点提示
		Args:
			method: 处理模式 web = 网页端消息类型 nemo = 客户端消息类型
		Returns:
			清除结果数据
		"""
		method_config: dict = {
			"web": {
				"endpoint": "/web/message-record",
				"message_types": coordinator.setting_manager.data.PARAMETER.all_read_type,
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
				response = coordinator.client.send_request(endpoint=endpoint, method="GET", params=request_params)
				responses[msg_type] = response.status_code
			return all(code == HTTPStatus.OK.value for code in responses.values())

		try:
			cleared_batches = 0
			while True:
				current_counts = coordinator.community_obtain.fetch_message_count(method)
				if is_all_cleared(current_counts):
					print(f"所有 {method} 消息已标记为已读")
					return {"success": True, "method": method, "cleared_batches": cleared_batches, "message": "所有消息已标记为已读"}
				if not send_batch_requests():
					print(f"清除 {method} 消息请求失败")
					return {"success": False, "method": method, "cleared_batches": cleared_batches, "error": "请求失败"}
				cleared_batches += 1
				params["offset"] += page_size
				print(f"已处理第 {cleared_batches} 批消息")
		except Exception as e:
			print(f"清除红点过程中发生异常: {e}")
			return {"success": False, "method": method, "error": str(e)}

	@staticmethod
	def like_collect_follow_user(user_id: int, works_list: list[dict] | Generator[dict]) -> dict:
		"""点赞和收藏用户作品"""
		print(f"开始处理用户 {user_id} 的作品")
		follow_result = coordinator.work_motion.execute_toggle_follow(user_id=int(user_id))
		print(f"关注用户: {' 成功 ' if follow_result else ' 失败 '}")
		like_count = 0
		collect_count = 0
		processed_count = 0
		for item in works_list:
			work_id = item.get("id")
			if isinstance(work_id, int):
				processed_count += 1
				like_result = coordinator.work_motion.execute_toggle_like(work_id=work_id)
				collect_result = coordinator.work_motion.execute_toggle_collection(work_id=work_id)
				if like_result:
					like_count += 1
					print(f"作品 {work_id} 点赞成功")
				if collect_result:
					collect_count += 1
					print(f"作品 {work_id} 收藏成功")
		print(f"处理完成: 点赞 {like_count}/{processed_count}, 收藏 {collect_count}/{processed_count}")
		return {
			"success": True,
			"user_id": user_id,
			"followed": follow_result,
			"liked_count": like_count,
			"collected_count": collect_count,
			"processed_count": processed_count,
		}

	@staticmethod
	def collect_novels(novel_list: list[dict]) -> dict:
		"""收藏小说"""
		print(f"开始处理 {len(novel_list)} 部小说")
		toggled_count = 0
		failed_ids = []
		for item in novel_list:
			novel_id = item.get("id")
			if isinstance(novel_id, int):
				result = coordinator.novel_motion.execute_toggle_novel_favorite(novel_id)
				if result:
					toggled_count += 1
					print(f"小说 {novel_id} 收藏成功")
				else:
					failed_ids.append(novel_id)
					print(f"小说 {novel_id} 收藏失败")
		print(f"处理完成: 成功 {toggled_count}/{len(novel_list)}")
		return {
			"success": toggled_count > 0,
			"toggled_count": toggled_count,
			"total_novels": len(novel_list),
			"failed_ids": failed_ids,
		}

	@staticmethod
	def create_comment(target_id: int, content: str, source_type: Literal["work", "shop", "post"]) -> bool:
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
				result = coordinator.forum_motion.create_post_reply(post_id=target_id, content=content)
			elif source_type == "shop":
				result = coordinator.shop_motion.create_comment(workshop_id=target_id, content=content, rich_content=content)
			elif source_type == "work":
				result = coordinator.work_motion.create_work_comment(work_id=target_id, comment=content)
			else:
				msg = f"不支持的来源类型: {source_type}"
				raise ValueError(msg)  # noqa: TRY301
			return bool(result)
		except Exception as e:
			print(f"创建评论失败: {e!s}")
			return False

	@staticmethod
	def update_workshop_details(workshop_id: int | None = None) -> dict:
		"""更新工作室详情"""
		if workshop_id is None:
			detail = coordinator.shop_obtain.fetch_workshop_details_list()
			workshop_id = detail.get("id")
			print(f"自动获取工作室 ID: {workshop_id}")
		if workshop_id is None:
			print("未找到工作室 ID")
			return {"success": False, "error": "未找到工作室 ID"}
		workshop_id_str = str(workshop_id)
		workshop_detail = coordinator.shop_obtain.fetch_workshop_details(workshop_id_str)
		if not workshop_detail:
			print("获取工作室详情失败")
			return {"success": False, "error": "获取工作室详情失败", "workshop_id": workshop_id}
		print(f"正在更新工作室: {workshop_detail['name']}")
		result = coordinator.shop_motion.update_workshop_details(
			description=workshop_detail["description"],
			workshop_id=workshop_id_str,
			name=workshop_detail["name"],
			preview_url=workshop_detail["preview_url"],
		)
		if result:
			print(f"工作室更新成功: {workshop_detail['name']}")
		else:
			print(f"工作室更新失败: {workshop_detail['name']}")
		return {
			"success": bool(result),
			"workshop_id": workshop_id,
			"workshop_name": workshop_detail["name"],
			"updated_fields": ["description", "name", "preview_url"] if result else [],
		}

	@staticmethod
	def publish_novel_chapter(novel_id: int, chapter_index: int = 0) -> dict:
		"""发布小说章节"""
		print(f"开始发布小说 {novel_id} 的第 {chapter_index} 章")
		novel_detail = coordinator.novel_obtain.fetch_novel_details(novel_id=novel_id)
		if not novel_detail:
			print("获取小说详情失败")
			return {"success": False, "error": "获取小说详情失败", "novel_id": novel_id}
		chapters = novel_detail["data"]["sectionList"]
		if not chapters:
			print("该小说没有章节")
			return {"success": False, "error": "该小说没有章节", "novel_id": novel_id}
		if chapter_index >= len(chapters):
			print(f"章节索引超出范围, 最大索引: {len(chapters) - 1}")
			return {"success": False, "error": "章节索引超出范围", "novel_id": novel_id, "max_index": len(chapters) - 1, "requested_index": chapter_index}
		chapter_id = chapters[chapter_index]["id"]
		chapter_title = chapters[chapter_index]["title"]
		print(f"准备发布章节: {chapter_title} (ID: {chapter_id})")
		result = coordinator.novel_motion.publish_chapter(chapter_id)
		if result:
			print(f"章节发布成功: {chapter_title}")
		else:
			print(f"章节发布失败: {chapter_title}")
		return {
			"success": bool(result),
			"novel_id": novel_id,
			"chapter_id": chapter_id,
			"chapter_index": chapter_index,
			"chapter_title": chapter_title,
			"total_chapters": len(chapters),
		}

	@staticmethod
	def get_account_status() -> dict:
		"""获取账户状态"""
		status = coordinator.user_obtain.fetch_account_details()
		return {"muted": status["voice_forbidden"], "agreement_signed": status["has_signed"]}

	@staticmethod
	def download_novel(novel_id: int, output_dir: Path | None = None) -> dict:
		"""
		下载小说内容
		Args:
			novel_id: 小说 ID
			output_dir: 输出目录
		Returns:
			下载结果数据
		"""
		details = coordinator.novel_obtain.fetch_novel_details(novel_id)
		if not details:
			msg = "获取小说详情失败"
			raise ValueError(msg)
		info = details["data"]["fanficInfo"]
		print(f"正在下载: {info['title']}-{info['nickname']}")
		print(f"简介: {info['introduction']}")
		print(f"类别: {info['fanfic_type_name']}")
		print(f"词数: {info['total_words']} 收藏数: {info['collect_times']}")
		print(f"更新时间: {coordinator.toolkit.create_time_utils().format_timestamp(info['update_time'])}")
		# 创建输出目录
		if output_dir is None:
			output_dir = coordinator.path_config.FICTION_FILE_PATH
		novel_dir = output_dir / f"{info['title']}-{info['nickname']}"
		info_file = novel_dir / "info.json"
		coordinator.file_manager.file_write(path=info_file, content=info)
		# 下载章节
		chapters = details["data"]["sectionList"]
		downloaded_chapters = []
		for i, section in enumerate(chapters, 1):
			section_id = section["id"]
			section_title = section["title"]
			section_path = novel_dir / f"{i:03d}_{section_title}.txt"
			content_data = coordinator.novel_obtain.fetch_chapter_details(chapter_id=section_id)
			content = content_data["data"]["section"]["content"]
			formatted_content = coordinator.toolkit.create_data_converter().html_to_text(content, merge_empty_lines=True)
			coordinator.file_manager.file_write(path=section_path, content=formatted_content)
			downloaded_chapters.append({"index": i, "title": section_title, "id": section_id, "path": str(section_path)})
			print(f"已下载章节: {section_title}")
		print(f"小说已保存到: {novel_dir}")
		return {
			"success": True,
			"novel_id": novel_id,
			"novel_title": info["title"],
			"author": info["nickname"],
			"introduction": info["introduction"],
			"total_words": info["total_words"],
			"collect_times": info["collect_times"],
			"fanfic_type": info["fanfic_type_name"],
			"output_dir": str(novel_dir),
			"info_file": str(info_file),
			"total_chapters": len(chapters),
			"downloaded_chapters": downloaded_chapters,
		}

	@staticmethod
	def generate_miao_code(work_id: int) -> dict:
		"""
		生成喵口令
		Args:
			work_id: 作品 ID
		Returns:
			喵口令生成结果
		"""
		info = coordinator.client.send_request(endpoint=f"/creation-tools/v1/works/{work_id}", method="GET").json()
		work_name = info.get("work_name", info.get("name", "未知作品"))
		print(f"作品名称: {work_name}")
		if info.get("type") != "NEMO":
			print(f"该作品类型为 {info.get('type')}, 不能生成喵口令")
			return {"success": False, "work_id": work_id, "work_name": work_name, "error": f"该作品类型为 {info.get('type')}, 不能生成喵口令"}
		work_info_url = f"/creation-tools/v1/works/{work_id}/source/public"
		work_info = coordinator.client.send_request(endpoint=work_info_url, method="GET").json()
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
		response = coordinator.client.send_request(endpoint="/nemo/v2/miao-codes/bcm", method="POST", payload=payload)
		if response.status_code == HTTPStatus.OK.value:
			result = response.json()
			miao_code = f"【喵口令】$&{result['token']}&$"
			print(f"生成的喵口令: {miao_code}")
			return {
				"success": True,
				"work_id": work_id,
				"work_name": work_name,
				"miao_code": miao_code,
				"token": result["token"],
				"bcm_url": bcm_url,
			}
		print(f"生成喵口令失败, 状态码: {response.status_code}")
		return {
			"success": False,
			"work_id": work_id,
			"work_name": work_name,
			"error": f"生成喵口令失败, 状态码: {response.status_code}",
		}

	@staticmethod
	def analyze_comments_statistics(comments_data: list[dict], min_comments: int = 1) -> dict:
		"""
		分析用户评论统计
		Args:
			comments_data: 用户评论数据列表
			min_comments: 最小评论数目阈值
		Returns:
			分析结果数据
		"""
		filtered_users = [user for user in comments_data if user["comment_count"] >= min_comments]
		if not filtered_users:
			print(f"没有用户评论数达到或超过 {min_comments} 条")
			return {"min_comments_threshold": min_comments, "total_users": len(comments_data), "filtered_users_count": 0, "filtered_users": []}
		print(f"评论数达到 {min_comments}+ 的用户统计:")
		print("=" * 60)
		result_data = []
		for user_data in filtered_users:
			nickname = user_data["nickname"]
			user_id = user_data["user_id"]
			comment_count = user_data["comment_count"]
			print(f"用户 {nickname} (ID: {user_id}) 发送了 {comment_count} 条评论")
			print("评论内容:")
			for i, comment in enumerate(user_data["comments"], 1):
				print(f"{i}. {comment}")
			print("*" * 50)
			result_data.append({"user_id": user_id, "nickname": nickname, "comment_count": comment_count, "comments": user_data["comments"]})
		return {
			"min_comments_threshold": min_comments,
			"total_users": len(comments_data),
			"filtered_users_count": len(filtered_users),
			"filtered_users": result_data,
		}

	@staticmethod
	def fetch_and_aggregate_works() -> list[dict]:
		"""获取最热作品"""
		filtered_works = []
		seen_ids = set()
		# 处理第一个数据源
		works1 = coordinator.work_obtain.fetch_themed_works_web(limit=50)
		if works1 and "items" in works1:
			for item in works1["items"]:
				work_id = item.get("work_id")
				if work_id and work_id not in seen_ids:
					seen_ids.add(work_id)
					filtered_works.append(
						{
							"likes_count": item.get("likes_count", 0),
							"collect_count": 0,  # 该数据源无收藏数
							"author_id": item.get("user_id", ""),
							"author_nickname": item.get("nickname", ""),
							"work_name": item.get("work_name", ""),
							"work_id": work_id,
						},
					)
		# 处理第二个数据源
		works2 = coordinator.work_obtain.fetch_all_subject_works(limit=50)
		if works2 and "items" in works2:
			for subject in works2["items"]:
				if "subject_works" in subject:
					for work in subject["subject_works"]:
						work_id = work.get("id")
						if work_id and work_id not in seen_ids:
							seen_ids.add(work_id)
							filtered_works.append(
								{
									"likes_count": work.get("n_likes", 0),
									"collect_count": 0,  # 该数据源无收藏数
									"author_id": work.get("user_id", ""),
									"author_nickname": work.get("nickname", ""),
									"work_name": work.get("work_name", ""),
									"work_id": work_id,
								},
							)
		# 处理第三个数据源
		works3 = coordinator.work_obtain.fetch_nemo_discover()
		if works3:
			# 处理主推荐列表
			if "recommend_work_list" in works3:
				for work in works3["recommend_work_list"]:
					work_base = work.get("work_base", {})
					work_id = work_base.get("id")
					if work_id and work_id not in seen_ids:
						seen_ids.add(work_id)
						work_mix = work.get("work_mix", {})
						filtered_works.append(
							{
								"likes_count": work_mix.get("like_times", 0),
								"collect_count": work_mix.get("collect_times", 0),
								"author_id": work.get("author_info", {}).get("user_id", ""),
								"author_nickname": work.get("author_info", {}).get("nickname", ""),
								"work_name": work_base.get("name", ""),
								"work_id": work_id,
							},
						)
			# 处理工作集推荐列表
			if "work_set" in works3 and "recommend_work_list" in works3["work_set"]:
				for work in works3["work_set"]["recommend_work_list"]:
					work_base = work.get("work_base", {})
					work_id = work_base.get("id")
					if work_id and work_id not in seen_ids:
						seen_ids.add(work_id)
						work_mix = work.get("work_mix", {})
						filtered_works.append(
							{
								"likes_count": work_mix.get("like_times", 0),
								"collect_count": work_mix.get("collect_times", 0),
								"author_id": work.get("author_info", {}).get("user_id", ""),
								"author_nickname": work.get("author_info", {}).get("nickname", ""),
								"work_name": work_base.get("name", ""),
								"work_id": work_id,
							},
						)
		return filtered_works

	def generate_online_leaderboard(self, works: list | None) -> dict:
		"""作品在线人数排行榜"""
		# works 数据类型和 fetch_and_aggregate_works 返回的一样

		def _get_online_users(work_id: int, token: str) -> int:
			"""获取作品的在线用户数"""
			client = CloudAPI(work_id=work_id, authorization_token=token)
			if not client.connect(wait_for_data=True):
				return 0
			try:
				return client.get_online_users()
			finally:
				client.disconnect()

		works = works or self.fetch_and_aggregate_works()
		token = CodeMaoClient().token.average
		results: list[tuple[str, int]] = []
		for work in works:
			response = coordinator.work_obtain.fetch_work_details(work["work_id"])
			work_name = response.get("work_name", response.get("name", "未知作品"))
			if response.get("type") == "WOOD":
				continue
			online_count = _get_online_users(work["work_id"], token)
			results.append((work_name, online_count))
		print("\n=== 作品在线人数排行榜 ===")
		sorted_results = []
		for name, count in sorted(results, key=lambda x: x[1], reverse=True):
			print(f"{name}: {count} 人在线")
			sorted_results.append({"work_name": name, "online_count": count})
		return {
			"total_works": len(sorted_results),
			"leaderboard": sorted_results,
			"top_online": sorted_results[0] if sorted_results else None,
			"average_online": sum(item["online_count"] for item in sorted_results) / len(sorted_results) if sorted_results else 0,
		}


# ==============================
# 批量操作服务
# ==============================
@singleton
class BatchOperationService:
	"""批量操作服务"""

	def __init__(self) -> None:
		self.community_service = CommunityService()
		self.account_manger = MultiAccount()

	def manage_edu_accounts(self, action: Literal["create", "delete", "token", "password"], limit: int | None = None) -> bool:
		"""
		管理教育账号
		Args:
			action: 操作类型 create = 创建 delete = 删除 token = 生成 token password = 生成密码
			limit: 限制数量
		Returns:
			是否成功
		"""
		total = coordinator.edu_obtain.fetch_class_students_total()
		print(f"可支配学生账号数: {total['total']}")
		if action == "delete":
			return self._delete_edu_accounts(limit)
		if action == "create":
			return self._create_edu_accounts(limit or 100)
		if action in {"token", "password"}:
			return self._generate_account_credentials(action, limit)
		print(f"不支持的操作类型: {action}")
		return False

	@staticmethod
	def _delete_edu_accounts(limit: int | None) -> bool:
		"""删除教育账号"""
		try:
			students = coordinator.edu_obtain.fetch_class_students_gen(limit=limit)
			deleted_count = 0
			for student in students:
				coordinator.edu_motion.delete_student_from_class(stu_id=student["id"])
				deleted_count += 1
				print(f"已删除学生: {student.get('name', 'Unknown')}")
			print(f"共删除 {deleted_count} 个学生账号")
		except Exception as e:
			print(f"删除学生账号失败: {e!s}")
			return False
		else:
			return True

	@staticmethod
	def _create_edu_accounts(student_limit: int) -> bool:
		"""创建教育账号"""
		try:
			class_capacity = 95
			class_count = (student_limit + class_capacity - 1) // class_capacity
			generator = coordinator.toolkit.create_edu_data_generator()
			# 生成班级和学生名称
			class_names = generator.generate_class_names(num_classes=class_count, add_specialty=True)
			student_names = generator.generate_student_names(num_students=student_limit)
			created_count = 0
			for class_idx in range(class_count):
				# 创建班级
				class_result = coordinator.edu_motion.create_class(name=class_names[class_idx])
				class_id = class_result["id"]
				print(f"创建班级: {class_names[class_idx]} (ID: {class_id})")
				# 添加学生
				start = class_idx * class_capacity
				end = min(start + class_capacity, student_limit)
				batch_names = student_names[start:end]
				coordinator.edu_motion.add_students_to_class(name=batch_names, class_id=class_id)
				created_count += len(batch_names)
				print(f"添加了 {len(batch_names)} 名学生到班级")
			print(f"共创建 {created_count} 个学生账号")
		except Exception as e:
			print(f"创建学生账号失败: {e!s}")
			return False
		else:
			return True

	@staticmethod
	def _generate_account_credentials(cred_type: Literal["token", "password"], limit: int | None) -> bool:
		"""生成账号凭证
		Args:
			cred_type: 凭证类型, token 或 password
			limit: 生成凭证的数量限制, None 表示无限制
		"""
		try:
			accounts = Obtain().switch_edu_account(limit=limit, return_method="list")
			credentials = []
			for identity, password in accounts:
				if cred_type == "token":
					# 登录获取 token
					response = coordinator.auth_manager.login(identity=identity, password=password, status="edu", prefer_method="password_v1")
					credential = response.data["auth"]["token"]
					# 只写入 token, 不包含账号信息
					content = f"{credential}\n"
					file_path = coordinator.path_config.TOKEN_FILE_PATH
				else:  # password
					credential = password
					# 写入账号和密码, 格式: 账号: 密码
					content = f"{identity}:{password}\n"
					file_path = coordinator.path_config.PASSWORD_FILE_PATH
				credentials.append(credential)
				# 写入文件
				coordinator.file_manager.file_write(
					path=file_path,
					content=content,
					method="a",  # 追加模式
				)
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
		Returns:
			举报数量
		"""
		hidden_border = 10
		self.account_manger.load_from_file(coordinator.path_config.PASSWORD_FILE_PATH)
		self.account_manger.execute_with_accounts(
			limit=hidden_border,
			func=lambda: coordinator.work_motion.execute_report_work(describe="", reason=reason, work_id=work_id),
		)

	def batch_like(
		self,
		user_id: int | None = None,
		content_type: Literal["work", "novel"] = "work",
		content_list: list | None = None,
		edu_limit: int | None = None,
	) -> None:
		"""
		批量点赞内容
		Args:
			user_id: 用户 ID (仅当 content_type="work" 且 content_list 为 None 时有效)
			content_type: 内容类型 work = 作品 novel = 小说
			content_list: 内容列表, 如果为 None 则自动获取
			edu_limit: 执行次数, 如果为 None 则使用全部 edu 账户
		"""
		# 获取内容列表
		if content_list:
			target_list = content_list
		elif content_type == "work" and user_id:
			target_list = list(coordinator.user_obtain.fetch_user_works_web_gen(user_id, limit=None))
		elif content_type == "novel":
			target_list = coordinator.novel_obtain.fetch_my_novels()
		else:
			msg = "必须提供 content_list 或 user_id"
			raise ValueError(msg)

		def action() -> None:
			count = 0
			if content_type == "work" and user_id:
				self.community_service.like_collect_follow_user(user_id, target_list)
				count = len(target_list)
			elif content_type == "novel":
				self.community_service.collect_novels(target_list)
				count = len(target_list)
			print(f"已处理 {count} 个 {content_type}")

		self.account_manger.load_from_file(coordinator.path_config.PASSWORD_FILE_PATH)
		self.account_manger.execute_with_accounts(limit=edu_limit, func=action)

	def batch_comment(self, target_id: int, source_type: Literal["work", "shop", "post"], content: str, times: int = 1, edu_limit: int | None = None) -> None:
		"""
		批量评论内容
		Args:
			target_id: 目标 ID
			source_type: 来源类型
			content: 评论内容
		"""

		def action() -> None:
			for _ in range(times):
				success = CommunityService.create_comment(target_id=target_id, content=content, source_type=source_type)
				if success:
					print(f"评论成功 on {source_type} ID {target_id}")
				else:
					print(f"评论失败 on {source_type} ID {target_id}")

		self.account_manger.load_from_file(coordinator.path_config.PASSWORD_FILE_PATH)
		self.account_manger.execute_with_accounts(func=action, limit=edu_limit)

	def batch_signature(self) -> None:
		"""
		批量签订社区友好条约
		"""

		def action() -> None:
			result = coordinator.community_motion.execute_sign_agreement()
			if result:
				print("成功签订社区友好条约")
			else:
				print("签订社区友好条约失败")

		self.account_manger.load_from_file(coordinator.path_config.PASSWORD_FILE_PATH)
		self.account_manger.execute_with_accounts(func=action)


# ==============================
# 举报处理服务
# ==============================
@singleton
class ReportService:
	"""举报处理服务"""

	def __init__(self) -> None:
		self.report_processor = ReportProcessor()
		self.report_fetcher = ReportFetcher()
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
		coordinator.printer.print_header("=== 举报处理系统 ===")
		print(Obtain().get_admin_statistics())
		# 主处理循环
		while True:
			self.total_reports = self.report_fetcher.get_total_reports(status="TOBEDONE")
			if self.total_reports == 0:
				coordinator.printer.print_message("当前没有待处理的举报", "INFO")
				break
			coordinator.printer.print_message(f"发现 {self.total_reports} 条待处理举报", "INFO")
			# 处理举报
			batch_processed = self.report_processor.process_all_reports(admin_id)
			self.processed_count += batch_processed
			coordinator.printer.print_message(f"本次处理完成: {batch_processed} 条举报", "SUCCESS")
			# 询问是否继续
			continue_choice = coordinator.printer.get_valid_input(prompt="是否继续检查新举报? (Y/N)", valid_options={"Y", "N"}).upper()
			if continue_choice != "Y":
				break
			coordinator.printer.print_message("重新获取新举报...", "INFO")
		# 显示统计结果
		coordinator.printer.print_header("=== 处理结果统计 ===")
		coordinator.printer.print_message(f"本次会话共处理 {self.processed_count} 条举报", "SUCCESS")
		# 终止会话
		coordinator.auth_manager.admin_logout()
		coordinator.auth_manager.restore_admin_account()
		return True

	@staticmethod
	def get_report_statistics(
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
		comment_stats = coordinator.whale_obtain.fetch_comment_reports_total(source_type=source_type, status=status)
		work_stats = coordinator.whale_obtain.fetch_work_reports_total(source_type=source_type, status=status)
		return {"comment_reports": comment_stats, "work_reports": work_stats, "total": comment_stats.get("total", 0) + work_stats.get("total", 0)}


# ==============================
# 服务管理器 (统一入口)
# ==============================
@singleton
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
		"""自动回复服务"""
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

	def clear_cache(self) -> None:
		"""清除所有服务缓存"""
		self._services.clear()


# 全局服务管理器实例
services = ServiceManager()
