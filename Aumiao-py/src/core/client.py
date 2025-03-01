from collections import defaultdict
from collections.abc import Generator
from enum import Enum
from json import loads
from random import choice
from time import sleep
from typing import Any, Literal, TypedDict, cast, overload

from src.api import community, edu, forum, shop, user, whale, work
from src.utils import acquire, data, decorator, file, tool


class FormattedAnswer(TypedDict):
	question: str
	responses: list[str] | str


class ReplyType(Enum):
	WORK_COMMENT = "WORK_COMMENT"
	WORK_REPLY = "WORK_REPLY"
	# 其他类型同理


VALID_REPLY_TYPES = {"WORK_COMMENT", "WORK_REPLY", "WORK_REPLY_REPLY", "POST_COMMENT", "POST_REPLY", "POST_REPLY_REPLY"}
OK_CODE = 200


@decorator.singleton
class Union:
	# 初始化Union类
	def __init__(self) -> None:
		self.acquire = acquire.CodeMaoClient()
		self.cache = data.CacheManager().data
		self.community_obtain = community.Obtain()
		self.community_login = community.Login()
		self.community_motion = community.Motion()
		self.data = data.DataManager().data
		self.edu_obtain = edu.Obtain()
		self.edu_motion = edu.Motion()
		self.file = file.CodeMaoFile()
		self.forum_motion = forum.Motion()
		self.forum_obtain = forum.Obtain()
		self.setting = data.SettingManager().data
		self.shop_motion = shop.Motion()
		self.shop_obtain = shop.Obtain()
		self.tool_process = tool.CodeMaoProcess()
		self.tool_routine = tool.CodeMaoRoutine()
		self.user_motion = user.Motion()
		self.user_obtain = user.Obtain()
		self.whale_obtain = whale.Obtain()
		self.whale_motion = whale.Motion()
		self.whale_routine = whale.Routine()
		self.work_motion = work.Motion()
		self.work_obtain = work.Obtain()


ClassUnion = Union().__class__


@decorator.singleton
class Tool(ClassUnion):
	def __init__(self) -> None:
		super().__init__()
		self.cache_manager = data.CacheManager()  # 添加这行

	def message_report(self, user_id: str) -> None:
		# 获取用户荣誉信息

		response = self.user_obtain.get_user_honor(user_id=user_id)
		# 获取当前时间戳
		timestamp = self.community_obtain.get_timestamp()["data"]
		# 构造用户数据字典
		user_data = {
			"user_id": response["user_id"],
			"nickname": response["nickname"],
			"level": response["author_level"],
			"fans": response["fans_total"],
			"collected": response["collected_total"],
			"liked": response["liked_total"],
			"view": response["view_times"],
			"timestamp": timestamp,
		}
		# 获取缓存数据
		before_data = self.cache_manager.data
		# 如果缓存数据不为空,则显示数据变化
		if before_data != {}:
			self.tool_routine.display_data_changes(
				before_data=before_data,
				after_data=user_data,
				metrics={
					"fans": "粉丝",
					"collected": "被收藏",
					"liked": "被赞",
					"view": "被预览",
				},
				date_field="timestamp",
			)
		# 更新缓存数据
		self.cache_manager.update(user_data)  # 使用管理器的 update 方法

	# 猜测手机号码(暴力枚举)
	def guess_phonenum(self, phonenum: str) -> int | None:
		# 枚举10000个四位数
		for i in range(10000):
			guess = f"{i:04d}"  # 格式化为四位数,前面补零
			test_string = int(phonenum.replace("****", guess))
			print(test_string)
			if self.user_motion.verify_phone(test_string):
				return test_string
		return None


@decorator.singleton
class Index(ClassUnion):
	def __init__(self) -> None:
		super().__init__()

	# 打印slogan
	def index(self) -> None:
		# 打印slogan
		print(self.setting.PROGRAM.SLOGAN)
		# 打印版本号
		print(f"版本号: {self.setting.PROGRAM.VERSION}")
		# 打印公告标题
		print("*" * 22 + " 公告 " + "*" * 22)
		# 打印编程猫社区行为守则链接
		print("编程猫社区行为守则 https://shequ.codemao.cn/community/1619098")
		# 打印2025编程猫拜年祭活动链接
		print("2025编程猫拜年祭活动 https://shequ.codemao.cn/community/1619855")
		# 打印数据标题
		print("*" * 22 + " 数据 " + "*" * 22)
		# 调用Tool类的message_report方法,传入用户id
		Tool().message_report(user_id=self.data.ACCOUNT_DATA.id)
		# 打印分隔线
		print("*" * 50)


@decorator.singleton
class Obtain(ClassUnion):
	def __init__(self) -> None:
		super().__init__()

	# 获取新回复(传入参数就获取前*个回复,若没传入就获取新回复数量, 再获取新回复数量个回复)
	def get_new_replies(
		self,
		limit: int = 0,
		type_item: Literal["LIKE_FORK", "COMMENT_REPLY", "SYSTEM"] = "COMMENT_REPLY",
	) -> list[dict[str, str | int | dict]]:
		_list = []
		# 获取新回复数量
		reply_num = self.community_obtain.get_message_count(method="web")[0]["count"]
		# 如果新回复数量为0且limit也为0,则返回空列表
		if reply_num == limit == 0:
			return [{}]
		# 如果limit为0,则获取新回复数量个回复,否则获取limit个回复
		result_num = reply_num if limit == 0 else limit
		offset = 0
		# 循环获取新回复
		while result_num >= 0:
			# 每次获取5个或剩余回复数量或200个回复
			limit = sorted([5, result_num, 200])[1]
			# 获取回复
			response = self.community_obtain.get_replies(types=type_item, limit=limit, offset=offset)
			# 将回复添加到列表中
			_list.extend(response["items"][:result_num])
			# 更新剩余回复数量
			result_num -= limit
			# 更新偏移量
			offset += limit
		return _list

	@overload
	def get_comments_detail_new(
		self,
		com_id: int,
		source: Literal["work", "post", "shop"],
		method: Literal["user_id", "comment_id"],
		max_limit: int | None = 200,
	) -> list[str]: ...

	@overload
	def get_comments_detail_new(
		self,
		com_id: int,
		source: Literal["work", "post", "shop"],
		method: Literal["comments"],
		max_limit: int | None = 200,
	) -> list[dict]: ...

	# 获取评论区信息
	def get_comments_detail_new(
		self,
		com_id: int,
		source: Literal["work", "post", "shop"],
		method: Literal["user_id", "comments", "comment_id"] = "user_id",
		max_limit: int | None = 200,
	) -> list[dict] | list[str]:
		def _get_replies(source: str, comment: dict) -> Generator[dict]:
			"""统一获取评论的回复"""
			if source == "post":
				return self.forum_obtain.get_reply_post_comments(post_id=comment["id"], limit=None)
			return comment.get("replies", {}).get("items", [])

		def _extract_reply_user_id(reply: dict, source: str) -> int:
			"""统一提取回复用户ID"""
			return reply["user"]["id"] if source == "post" else reply["reply_user"]["id"]

		def _handle_user_id(comments: list[dict], source: str) -> list[int]:
			"""优化后的用户ID处理"""
			user_ids = []
			for comment in comments:
				user_ids.append(comment["user"]["id"])
				replies = _get_replies(source, comment)
				user_ids.extend(_extract_reply_user_id(reply, source) for reply in replies)
			return user_ids

		def _handle_comment_id(comments: list[dict], source: str) -> list[str]:
			"""优化后的评论ID处理"""
			comment_ids = []
			for comment in comments:
				comment_ids.append(str(comment["id"]))
				replies = _get_replies(source, comment)
				comment_ids.extend(f"{comment['id']}.{reply['id']}" for reply in replies)
			return comment_ids

		def _handle_detailed_comments(comments: list[dict], source: str) -> list[dict]:
			"""处理完整评论信息"""
			detailed_comments = []
			for comment in comments:
				comment_data = {
					"user_id": comment["user"]["id"],
					"nickname": comment["user"]["nickname"],
					"id": comment["id"],
					"content": comment["content"],
					"created_at": comment["created_at"],
					"is_top": comment.get("is_top", False),
					"replies": [],
				}
				for reply in _get_replies(source, comment):
					reply_data = {
						"id": reply["id"],
						"content": reply["content"],
						"created_at": reply["created_at"],
						"user_id": _extract_reply_user_id(reply, source),
						"nickname": reply["user" if source == "post" else "reply_user"]["nickname"],
					}
					comment_data["replies"].append(reply_data)
				detailed_comments.append(comment_data)
			return detailed_comments

		# 通过映射表处理不同来源的评论获取逻辑
		source_methods = {
			"work": (self.work_obtain.get_work_comments, "work_id"),
			"post": (self.forum_obtain.get_post_replies_posts, "ids"),
			"shop": (self.shop_obtain.get_shop_discussion, "shop_id"),
		}
		if source not in source_methods:
			msg = "不支持的来源类型"
			raise ValueError(msg)
		method_func, arg_key = source_methods[source]
		comments = method_func(**{arg_key: com_id, "limit": max_limit})

		# 处理方法映射表
		method_handlers = {
			"user_id": _handle_user_id,
			"comment_id": _handle_comment_id,
			"comments": _handle_detailed_comments,
		}
		if method not in method_handlers:
			msg = "不支持的请求方法"
			raise ValueError(msg)

		# 获取处理结果并去重
		result = method_handlers[method](comments, source)
		return self.tool_process.deduplicate(result) if method in ("user_id", "comment_id") else result


@decorator.singleton
class Motion(ClassUnion):
	def __init__(self) -> None:
		super().__init__()

	# 由于编程猫社区命名极不规范,在本函数变量中,reply指work中comment的回复或者post中reply(回帖)中的回复
	# comment指work中的comment或者post中的reply
	# 但是delete_comment_post_reply函数reply指回帖,comment指回帖的回复
	# 将列表切片翻转是为了先删评论中的回复再删评论,防止在存在评论和回复都是待删项时,删除回复报错
	def clear_comments(
		self,
		source: Literal["work", "post"],
		action_type: Literal["ads", "duplicates", "blacklist"],
	) -> bool:
		"""清理指定来源的评论(广告/黑名单/刷屏)"""

		# 获取数据源和对应方法
		def get_source_data() -> ...:
			if source == "work":
				return (
					self.user_obtain.get_user_works_web(self.data.ACCOUNT_DATA.id, limit=None),
					lambda _id: Obtain().get_comments_detail_new(_id, "work", "comments"),
					self.work_motion.del_comment_work,
				)
			if source == "post":
				return (
					self.forum_obtain.get_post_mine_all("created", limit=None),
					lambda _id: Obtain().get_comments_detail_new(_id, "post", "comments"),
					lambda _id, comment_id, **_: self.forum_motion.delete_comment_post_reply(
						comment_id,
						"comments" if _.get("is_reply") else "replies",
					),
				)
			msg = "不支持的来源类型"
			raise ValueError(msg)

		items, get_comments, delete_handler = get_source_data()
		lists = {"ads": [], "blacklist": [], "duplicates": []}
		params = {
			"ads": self.data.USER_DATA.ads,
			"blacklist": self.data.USER_DATA.black_room,
			"spam_max": self.setting.PARAMETER.spam_max,
		}

		# 主处理逻辑
		for item in items:
			item_id = int(item["id"])
			title = item["title" if source == "post" else "work_name"]
			comments = get_comments(item_id)

			# 处理广告/黑名单
			if action_type in ("ads", "blacklist"):
				for comment in comments:
					if comment.get("is_top"):
						continue
					self._process_comment(
						comment,
						item_id,
						title,
						action_type,
						params,
						lists,
						delete_handler,
					)
					for reply in comment["replies"]:
						self._process_reply(
							reply,
							comment["content"],
							item_id,
							title,
							action_type,
							params,
							lists,
							delete_handler,
						)

			# 处理刷屏评论
			elif action_type == "duplicates":
				content_map = defaultdict(list)
				for comment in comments:
					self._track_duplicates(comment, item_id, content_map)
					for reply in comment["replies"]:
						self._track_duplicates(reply, item_id, content_map, is_reply=True)

				for (_uid, content), ids in content_map.items():
					if len(ids) >= params["spam_max"]:
						print(f"发现刷屏评论:{content}")
						lists["duplicates"].extend(ids)

		# 执行删除操作
		@decorator.skip_on_error
		def execute_deletion(target_list: list, label: str) -> bool:
			if not target_list:
				print(f"未发现{label}")
				return True

			print(f"发现以下{label}:")
			for item in reversed(target_list):
				print(f" - {item.split(':')[0]}")

			if input(f"删除所有{label}?(y/n)  ").lower() != "y":
				print("取消删除操作")
				return True

			for entry in reversed(target_list):
				item_id, comment_id = entry.split(":")[0].split(".")
				is_reply = ":reply" in entry
				if not delete_handler(int(item_id), int(comment_id), is_reply=is_reply):
					print(f"删除失败:{entry}")
					return False
				print(f"已删除:{entry}")
			return True

		return execute_deletion(
			lists[action_type],
			{
				"ads": "广告评论",
				"blacklist": "黑名单评论",
				"duplicates": "刷屏评论",
			}[action_type],
		)

	# 辅助方法(类内部其他位置定义)
	def _process_comment(self, data: dict, item_id: int, title: str, action_type: Literal["ads", "blacklist"], params: dict, lists: dict, _: object) -> None:
		content = data["content"].lower()
		identifier = f"{item_id}.{data['id']}:comment"

		if action_type == "ads" and any(ad in content for ad in params["ads"]):
			print(f"广告评论 [{title}]: {content}")
			lists["ads"].append(identifier)

		elif action_type == "blacklist" and str(data["user_id"]) in params["blacklist"]:
			print(f"黑名单用户 [{title}]: {data['nickname']}")
			lists["blacklist"].append(identifier)

	def _process_reply(self, data: dict, parent_content: str, item_id: int, title: str, action_type: Literal["ads", "blacklist"], params: dict, lists: dict, _: object) -> None:
		content = data["content"].lower()
		identifier = f"{item_id}.{data['id']}:reply"

		if action_type == "ads" and any(ad in content for ad in params["ads"]):
			print(f"广告回复 [{title}] ({parent_content}): {content}")
			lists["ads"].append(identifier)

		elif action_type == "blacklist" and str(data["user_id"]) in params["blacklist"]:
			print(f"黑名单回复 [{title}] ({parent_content}): {data['nickname']}")
			lists["blacklist"].append(identifier)

	def _track_duplicates(self, data: dict, item_id: int, content_map: dict, *, is_reply: bool = False) -> None:
		key = (data["user_id"], data["content"].lower())
		content_map[key].append(
			f"{item_id}.{data['id']}:{'reply' if is_reply else 'comment'}",
		)
		# (user_id,content):[item_id.comment_id:reply/comment]

	def clear_red_point(self, method: Literal["nemo", "web"] = "web") -> bool:
		def get_message_counts(method: Literal["web", "nemo"]) -> dict:
			"""获取各类型消息未读数"""
			return self.community_obtain.get_message_count(method)

		def send_clear_request(url: str, params: dict) -> int:
			"""发送标记已读请求"""
			response = self.acquire.send_request(endpoint=url, method="GET", params=params)
			return response.status_code

		offset = 0  # 分页偏移量
		page_size = 200
		params: dict[str, int | str] = {"limit": page_size, "offset": offset}

		if method == "web":
			query_types = self.setting.PARAMETER.all_read_type
			while True:
				# 检查所有指定类型消息是否均已读
				counts = get_message_counts("web")
				if all(count["count"] == 0 for count in counts[:3]):
					return True

				# 更新当前分页偏移量
				params["offset"] = offset

				# 批量发送标记已读请求
				responses = {}
				for q_type in query_types:
					params["query_type"] = q_type
					responses[q_type] = send_clear_request(
						url="/web/message-record",
						params=params,
					)

				# 校验请求结果
				if any(status != OK_CODE for status in responses.values()):
					return False

				offset += page_size

		elif method == "nemo":
			message_types = [1, 3]  # 1:点赞收藏 3:fork
			while True:
				# 检查所有类型消息总数
				counts = get_message_counts("nemo")
				total_unread = sum(
					counts[key]
					for key in [
						"like_collection_count",
						"comment_count",
						"re_create_count",
						"system_count",
					]
				)
				if total_unread == 0:
					return True

				# 更新当前分页偏移量
				params["offset"] = offset

				# 批量发送标记已读请求
				responses = {}
				for m_type in message_types:
					responses[m_type] = send_clear_request(
						url=f"/nemo/v2/user/message/{m_type}",
						params=params,
					)

				# 校验请求结果
				if any(status != OK_CODE for status in responses.values()):
					return False

				offset += page_size

		return False

	# 给某人作品全点赞
	def like_all_work(self, user_id: str) -> bool:
		works_list = self.user_obtain.get_user_works_web(user_id, limit=None)
		for item in works_list:
			item["id"] = cast(int, item["id"])
			if not self.work_motion.like_work(work_id=item["id"]):
				return False
		return True

	def reply_work(self) -> bool:
		"""自动回复工作流"""
		new_replies: list[dict] = Obtain().get_new_replies()

		@overload
		def _preprocess_data(data_type: Literal["answers"]) -> dict[str, list[str] | str]: ...

		@overload
		def _preprocess_data(data_type: Literal["replies"]) -> list[str]: ...
		# 合并预处理逻辑
		def _preprocess_data(data_type: Literal["answers", "replies"]) -> dict[str, list[str] | str] | list[str]:
			"""统一预处理数据"""
			if data_type == "answers":
				result: dict[str, list[str] | str] = {}
				for answer_dict in self.data.USER_DATA.answers:
					for keyword, response in answer_dict.items():
						# 内联格式化逻辑
						formatted = [resp.format(**self.data.INFO) for resp in response] if isinstance(response, list) else response.format(**self.data.INFO)
						result[keyword] = formatted
				return result
			return [reply.format(**self.data.INFO) for reply in self.data.USER_DATA.replies]

		formatted_answers = _preprocess_data("answers")
		formatted_replies = _preprocess_data("replies")

		# 合并过滤逻辑到主流程
		filtered_replies = self.tool_process.filter_items_by_values(
			data=new_replies,
			id_path="type",
			values=list(VALID_REPLY_TYPES),
		)
		if not filtered_replies:
			return True

		# 合并单条回复处理逻辑
		for reply in filtered_replies:
			try:
				content = loads(reply["content"])
				message = content["message"]
				reply_type = reply["type"]

				# 合并文本提取和响应匹配逻辑
				comment_text = message["comment"] if reply_type in {"WORK_COMMENT", "POST_COMMENT"} else message["reply"]

				# 优化匹配逻辑
				chosen_comment = None
				for keyword, resp in formatted_answers.items():  # 明确 formatted_answers 是 dict
					if keyword in comment_text:
						chosen_comment = choice(resp) if isinstance(resp, list) else resp  # noqa: S311
						break
				if chosen_comment is None:  # 如果没有匹配的答案,则随机选择一个回复
					chosen_comment = choice(formatted_replies)  # noqa: S311

				# 统一处理回复操作
				self._execute_reply(
					reply_type=reply_type,
					message=message,
					raw_reply=reply,
					comment=chosen_comment,
				)
			except Exception as e:
				print(f"处理回复时发生错误: {e}")
				continue

		return True

	@decorator.skip_on_error
	def _execute_reply(
		self,
		reply_type: str,
		message: dict,
		raw_reply: dict,
		comment: str,
	) -> None:
		"""统一执行回复操作(合并work/post处理逻辑)"""
		business_id = message["business_id"]
		source_type = "work" if reply_type.startswith("WORK") else "post"

		# 合并标识获取逻辑
		if reply_type.endswith("_COMMENT"):
			comment_id = raw_reply.get("reference_id", message["comment_id"])
			parent_id = 0
		else:
			parent_id = raw_reply.get("reference_id", message.get("replied_id", 0))
			comment_ids = [
				str(item)
				for item in Obtain().get_comments_detail_new(
					com_id=business_id,
					source=source_type,
					method="comment_id",
				)
				if isinstance(item, int | str)
			]
			target_id = message.get("reply_id", "")
			# search_pattern = f".{target_id}" if source_type == "work" else target_id
			if (found_id := self.tool_routine.find_prefix_suffix(target_id, comment_ids)[0]) is None:
				msg = "未找到匹配的评论ID"
				raise ValueError(msg)
			comment_id = int(found_id)

		# 合并API调用逻辑
		params = (
			{
				"work_id": business_id,
				"comment_id": comment_id,
				"comment": comment,
				"parent_id": parent_id,
				"return_data": True,
			}
			if source_type == "work"
			else {
				"reply_id": comment_id,
				"parent_id": parent_id,
				"content": comment,
			}
		)

		(self.work_motion.reply_work if source_type == "work" else self.forum_motion.reply_comment)(**params)

	# 工作室常驻置顶
	def top_work(self) -> None:
		detail = self.shop_obtain.get_shops_details()
		description = self.shop_obtain.get_shop_details(detail["work_subject_id"])["description"]
		self.shop_motion.update_shop_details(
			description=description,
			shop_id=detail["id"],
			name=detail["name"],
			preview_url=detail["preview_url"],
		)

	# 查看账户所有信息综合
	def get_account_all_data(self) -> dict[Any, Any]:
		# 创建一个空列表来存储所有字典
		all_data: list[dict] = []
		# 调用每个函数并将结果添加到列表中
		all_data.append(self.user_obtain.get_data_details())
		all_data.append(self.user_obtain.get_data_level())
		all_data.append(self.user_obtain.get_data_name())
		all_data.append(self.user_obtain.get_data_privacy())
		all_data.append(self.user_obtain.get_data_score())
		all_data.append(self.user_obtain.get_data_profile("web"))
		all_data.append(self.user_obtain.get_data_tiger())
		all_data.append(self.edu_obtain.get_data_details())
		return self.tool_routine.merge_user_data(data_list=all_data)

	# 查看账户状态
	def get_account_status(self) -> str:
		status = self.user_obtain.get_data_details()
		return f"禁言状态{status['voice_forbidden']},签订友好条约{status['has_signed']}"

	# 处理举报
	# 需要风纪权限
	def handle_report(self, admin_id: int) -> None:
		def process_item(item: dict, report_type: Literal["comment", "post", "discussion"]) -> None:
			# 类型字段映射表
			type_config = {
				"comment": {
					"content_field": "comment_content",
					"user_field": "comment_user",
					"handle_method": "handle_comment_report",
					"source_id_field": "comment_source_object_id",
					"source_name_field": "comment_source_object_name",
					"special_check": lambda: item.get("comment_source") == "WORK_SHOP",
					"com_id": "comment_id",
				},
				"post": {
					"content_field": "post_title",
					"user_field": "post_user",
					"handle_method": "handle_post_report",
					"source_id_field": "post_id",
					"special_check": lambda: True,
					"com_id": "post_id",
				},
				"discussion": {
					"content_field": "discussion_content",
					"user_field": "discussion_user",
					"handle_method": "handle_discussion_report",
					"source_id_field": "post_id",
					"special_check": lambda: True,
					"com_id": "discussion_id",
				},
			}

			cfg = type_config[report_type]
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
			print(f"举报时间: {self.tool_process.format_timestamp(item['created_at'])}")
			if report_type == "post":
				print(f"举报线索: {item['description']}")

			while True:
				print("-" * 50)
				choice = input("选择操作: D:删除, S:禁言7天, P:通过, C:查看, F:检查违规, J:跳过").upper()
				handler = getattr(self.whale_motion, cfg["handle_method"])
				if choice == "J":
					break
				if choice in ("D", "S", "P"):
					status_map = {"D": "DELETE", "S": "MUTE_SEVEN_DAYS", "P": "PASS"}
					handler(report_id=item["id"], status=status_map[choice], admin_id=admin_id)
					break
				if choice == "C":
					self._show_details(item, report_type, cfg)
				elif choice == "F" and cfg["special_check"]():
					self._check_violations(item, report_type, cfg)
				else:
					print("无效输入")

		# 获取所有待处理举报
		lists: list[tuple[Generator[dict], Literal["comment", "post", "discussion"]]] = [
			(self.whale_obtain.get_comment_report(types="ALL", status="TOBEDONE", limit=None), "comment"),
			(self.whale_obtain.get_post_report(status="TOBEDONE", limit=None), "post"),
			(self.whale_obtain.get_discussion_report(status="TOBEDONE", limit=None), "discussion"),
		]

		for report_list, report_type in lists:
			for item in report_list:
				process_item(item=item, report_type=report_type)
		self.acquire.switch_account(token=self.acquire.token.average, identity="average")

	def _show_details(self, item: dict, report_type: Literal["comment", "post", "discussion"], cfg: dict) -> None:
		"""显示详细信息"""
		if report_type == "comment":
			print(f"违规板块ID: https://shequ.codemao.cn/work_shop/{item[cfg['source_id_field']]}")
		elif report_type == "post":
			print(f"违规帖子ID: https://shequ.codemao.cn/community/{item[cfg['source_id_field']]}")
		elif report_type == "discussion":
			print(f"所属帖子标题: {item['post_title']}")
			print(f"所属帖子帖主ID: https://shequ.codemao.cn/user/{item['post_user_id']}")
			print(f"所属帖子ID: https://shequ.codemao.cn/community/{item[cfg['source_id_field']]}")

		cfg_user_field = cfg["user_field"]
		print(f"违规用户ID: https://shequ.codemao.cn/user/{item[f'{cfg_user_field}_id']}")
		if report_type in ("comment", "discussion"):
			source = "shop" if report_type == "comment" else "post"
			comments = Obtain().get_comments_detail_new(com_id=item[cfg["source_id_field"]], source=source, method="comments", max_limit=200)
			if report_type == "comment" and item["comment_parent_id"] != "0":
				for comment in comments:
					if comment["id"] == item["comment_parent_id"]:
						for reply in comment["replies"]:
							if reply["id"] == item["comment_id"]:
								print(f"发送时间: {self.tool_process.format_timestamp(reply['created_at'])}")
								break
						break
			else:
				for comment in comments:
					if comment["id"] == item["comment_id"]:
						print(f"发送时间: {self.tool_process.format_timestamp(comment['created_at'])}")
						break
		else:
			details = self.forum_obtain.get_single_post_details(ids=item[cfg["source_id_field"]])
			print(f"发送时间: {self.tool_process.format_timestamp(details['created_at'])}")  # 有的帖子可能有更新,但是大部分是created_at,为了迎合网页显示的发布时间

	def _check_violations(self, item: dict, report_type: Literal["comment", "post", "discussion"], cfg: dict) -> None:
		"""统一违规检查逻辑"""
		source_map: dict[str, tuple[Literal["shop", "post", "forum"], Literal["comments", "posts"], str]] = {
			"comment": ("shop", "comments", item[cfg["source_id_field"]]),
			"discussion": ("post", "comments", item[cfg["source_id_field"]]),
			"post": ("forum", "posts", item[cfg["content_field"]]),
		}
		source_type, method, source_id = source_map[report_type]

		if report_type in ("comment", "discussion"):
			comments = Obtain().get_comments_detail_new(
				com_id=int(source_id),
				source=cast(Literal["shop", "post"], source_type),
				method=cast(Literal["comments"], method),
			)
			user_comments = self.tool_process.filter_items_by_values(
				data=comments,
				id_path="user_id",
				values=item[f"{cfg['user_field']}_id"],
			)
			# 调用新的自动举报方法
			self._auto_report_comments(
				user_comments=user_comments,
				# source_type=source_type,
				source_id=int(source_id),
				report_source="shop" if report_type == "comment" else "forum",
			)

	def _auto_report_comments(self, user_comments: list, source_id: int, report_source: str) -> None:
		"""自动举报违规评论的优化方法"""
		analyze_comments = self._analyze_comments(user_comments, source_id)
		choice = input("是否自动举报违规评论? (Y/N) ").upper()
		if not analyze_comments or choice != "Y":
			return

		# 账号管理优化
		# original_token = self.acquire.headers["Authorization"].split(" ")[1]
		# del self.acquire.headers["Authorization"]

		# 预先获取所有可用教育账号并缓存
		try:
			self.acquire.switch_account(token=self.acquire.token.average, identity="average")
			all_accounts = self._switch_edu_account(limit=20)
			if not all_accounts:
				print("没有可用的教育账号")
				return
		except Exception as e:
			print(f"获取教育账号失败: {e}")
			return

		current_account_idx = 0
		report_count = 0
		max_retries = 3  # 最大重试次数
		success_count = 0  # 成功举报计数器

		# 优化后的举报处理流程
		for comment in analyze_comments:
			for entry in comment.values():
				for single_item in entry:
					retries = 0
					success = False

					while not success and retries < max_retries:
						try:
							# 当达到最大举报次数或需要切换账号时
							if report_count >= self.setting.PARAMETER.report_max or success_count == 0:
								try:
									current_account = next(all_accounts)
								except StopIteration:
									print("所有账号均已尝试")
									return
								# if current_account_idx >= len(all_accounts):
								# 	print("所有账号均已尝试")
								# 	return

								# 获取新账号并登录
								# current_account = all_accounts[current_account_idx]
								print(f"切换到账号 {current_account[0]}")
								sleep(5)
								# self.acquire.switch_account("", identity="edu")
								self.community_login.login_token(identity=current_account[0], password=current_account[1], status="edu")
								# self.acquire.switch_account(token=self.acquire.token.edu, identity="edu")
								# print("*" * 85)
								# print(f"token={self.acquire.token.edu}")
								# self._switch_account(current_account)
								# current_account_idx += 1
								report_count = 0
								success_count = 0

							# 执行举报逻辑
							item_id, comment_id = single_item.split(":")[0].split(".")
							# comments = Obtain().get_comments_detail_new(
							# 	com_id=source_id,
							# 	source=cast(Literal["shop", "post"], source_type),
							# 	method="comment_id",
							# )
							parent_id, reply_id = self.tool_routine.find_prefix_suffix(
								text=comment_id,
								candidates=user_comments,
							)

							if self.report_work(
								source=cast(Literal["forum", "work", "shop"], report_source),
								target_id=int(comment_id),
								source_id=source_id,
								reason_id=7,
								parent_id=cast(int, parent_id),
								is_reply=bool(":reply" in single_item),
							):
								report_count += 1
								success_count += 1
								success = True
								print(f"举报成功: {single_item} (当前账号成功次数: {success_count})")
							else:
								print("举报失败,尝试切换账号")
								retries = max_retries  # 强制切换账号

						except Exception as e:
							print(f"举报出错: {e}")
							retries += 1
							if retries >= max_retries:
								print("达到最大重试次数,切换账号")
								current_account_idx += 1
								report_count = 0
								success_count = 0

					if not success:
						print(f"无法处理举报项: {single_item}")

		# 恢复原始账号
		self.whale_routine.set_token(self.acquire.token.judgement)

	def _switch_edu_account(self, limit: int | None) -> Generator:
		"""返回所有学生账密列表(优化版本)"""
		students = self.edu_obtain.get_students(limit=limit)
		for student in students:
			self.acquire.switch_account(token=self.acquire.token.average, identity="average")
			yield student["username"], self.edu_motion.reset_password(student["id"])["password"]
		# return [(student["username"], self.edu_motion.reset_password(student["id"])["password"]) for student in students]

	# def _switch_account(self, account: tuple[str, str]) -> None:
	# 	"""优化后的账号切换方法"""
	# 	try:
	# 		# 仅在需要时注销(比如Cookie存在时)
	# 		if "Cookie" in self.acquire.headers:
	# 			self.community_login.logout("web")
	# 			del self.acquire.headers["Cookie"]
	# 		self.community_login.login_password(account[0], account[1])
	# 		# 适当减少等待时间
	# 		sleep(1)
	# 	except Exception as e:
	# 		print(f"账号切换失败: {account[0]},错误信息: {e}")

	def _analyze_comments(self, comments: list, source_id: int) -> None | Generator[dict[tuple[int, str], list[str]]]:
		"""分析评论违规"""
		content_map = defaultdict(list)
		for comment in comments:
			content = comment["content"].lower()
			if any(ad in content for ad in self.data.USER_DATA.ads):
				print(f"广告回复: {content}")

			self._track_duplicates(comment, source_id, content_map)
			for reply in comment.get("replies", []):
				self._track_duplicates(reply, source_id, content_map, is_reply=True)
				if any(ad in reply["content"].lower() for ad in self.data.USER_DATA.ads):
					print(f"广告回复: {reply['content']}")
		# (user_id,content):[item_id.comment_id1:reply/comment,item_id.comment_id2:reply/comment]
		for (user_id, content), entry in content_map.items():
			if len(entry) >= self.setting.PARAMETER.spam_max:
				print(f"发现刷屏评论: {content}")
				print(f"此用户已经刷屏,共发布{len(entry)}次")
				yield {(user_id, content): entry}
		return None

	def report_work(
		self,
		source: Literal["forum", "work", "shop"],
		target_id: int,
		source_id: int,
		reason_id: Literal[0, 1, 2, 3, 4, 5, 6, 7, 8],
		parent_id: int | None = None,
		*,
		is_reply: bool = False,
	) -> bool:
		"""
		举报
		1: 违法违规; 2: 色情暴力
		3: 侵犯隐私; 4: 人身攻击
		5: 引战; 6: 垃圾广告
		7: 无意义刷屏; 8: 不良信息
		0: 自定义
		"""
		reason_content = self.community_obtain.get_report_reason()["items"][reason_id]["content"]
		match source:
			case "work":
				return self.work_motion.report_comment_work(work_id=target_id, comment_id=source_id, reason=reason_content)
			case "forum":
				_source = "COMMENT" if is_reply else "REPLY"
				return self.forum_motion.report_reply_or_comment(comment_id=target_id, reason_id=reason_id, description=reason_content, source=_source, return_data=False)
			case "shop":
				if is_reply:
					parent_id = cast(int, parent_id)
					return self.shop_motion.report_comment(
						comment_id=target_id,
						reason_content=reason_content,
						reason_id=reason_id,
						reporter_id=int(self.data.ACCOUNT_DATA.id),
						comment_parent_id=parent_id,
					)
				return self.shop_motion.report_comment(
					comment_id=target_id,
					reason_content=reason_content,
					reason_id=reason_id,
					reporter_id=int(self.data.ACCOUNT_DATA.id),
				)


# "POST_COMMENT",
# "POST_COMMENT_DELETE_FEEDBACK",
# "POST_DELETE_FEEDBACK",
# "POST_DISCUSSION_LIKED",
# "POST_REPLY",
# "POST_REPLY_AUTHOR",
# "POST_REPLY_REPLY",
# "POST_REPLY_REPLY_AUTHOR",
# "POST_REPLY_REPLY_FEEDBACK",
# "WORK_COMMENT",路人a评论{user}的作品
# "WORK_DISCUSSION_LIKED",
# "WORK_LIKE",
# "WORK_REPLY",路人a评论{user}在某个作品的评论
# "WORK_REPLY_AUTHOR",路人a回复{user}作品下路人b的某条评论
# "WORK_REPLY_REPLY",路人a回复{user}作品下路人b/a的评论下{user}的回复
# "WORK_REPLY_REPLY_AUTHOR",路人a回复{user}作品下路人b/a对某条评论的回复
# "WORK_REPLY_REPLY_FEEDBACK",路人a回复{user}在某个作品下发布的评论的路人b/a的回复
# "WORK_SHOP_REPL"
# "WORK_SHOP_USER_LEAVE",
