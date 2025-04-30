from collections import defaultdict
from collections.abc import Generator
from enum import Enum
from json import loads
from random import choice, randint
from time import sleep
from typing import Any, Callable, Literal, TypedDict, cast, overload

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
		# 颜色配置
		self.COLOR_SLOGAN = "\033[38;5;80m"  # 湖水青-标语
		self.COLOR_VERSION = "\033[38;5;114m"  # 新芽绿-版本号
		self.COLOR_TITLE = "\033[38;5;75m"  # 晴空蓝-标题
		self.COLOR_LINK = "\033[4;38;5;183m"  # 薰衣草紫带下划线-链接
		self.COLOR_DATA = "\033[38;5;228m"  # 月光黄-数据
		self.COLOR_RESET = "\033[0m"  # 样式重置

	def index(self) -> None:
		"""打印引导界面"""
		# 打印slogan
		print(f"\n{self.COLOR_SLOGAN}{self.setting.PROGRAM.SLOGAN}{self.COLOR_RESET}")
		# 打印版本号
		print(f"{self.COLOR_VERSION}版本号: {self.setting.PROGRAM.VERSION}{self.COLOR_RESET}")

		title = f"{'*' * 22} 一言 {'*' * 22}"
		print(f"\n{self.COLOR_TITLE}{title}{self.COLOR_RESET}")
		lyric: str = self.acquire.send_request(endpoint="https://lty.vc/lyric", method="GET").text
		print(f"{self.COLOR_SLOGAN}{lyric}{self.COLOR_RESET}")
		# 打印公告标题
		title = f"{'*' * 22} 公告 {'*' * 22}"
		print(f"\n{self.COLOR_TITLE}{title}{self.COLOR_RESET}")
		# 打印链接
		print(f"{self.COLOR_LINK}编程猫社区行为守则 https://shequ.codemao.cn/community/1619098{self.COLOR_RESET}")
		print(f"{self.COLOR_LINK}2025编程猫拜年祭活动 https://shequ.codemao.cn/community/1619855{self.COLOR_RESET}")

		# 打印数据标题
		data_title = f"{'*' * 22} 数据 {'*' * 22}"
		print(f"\n{self.COLOR_DATA}{data_title}{self.COLOR_RESET}")
		# 调用数据报告
		Tool().message_report(user_id=self.data.ACCOUNT_DATA.id)
		# 分隔线
		print(f"{self.COLOR_TITLE}{'*' * 50}{self.COLOR_RESET}\n")


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
		list_ = []
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
			list_.extend(response["items"][:result_num])
			# 更新剩余回复数量
			result_num -= limit
			# 更新偏移量
			offset += limit
		return list_

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
		"""获取结构化评论数据
		Args:
			com_id: 目标主体ID (作品/帖子/工作室ID)
			source: 数据来源 work=作品 post=帖子 shop=工作室
			method: 返回格式
				user_id -> 用户ID列表
				comment_id -> 评论ID列表
				comments -> 结构化评论数据
			max_limit: 最大获取数量
		Returns:
			根据method参数返回对应格式的数据
		"""
		# 预定义字段映射表
		SOURCE_CONFIG = {
			"work": (self.work_obtain.get_work_comments, "work_id", "reply_user"),
			"post": (self.forum_obtain.get_post_replies_posts, "ids", "user"),
			"shop": (self.shop_obtain.get_shop_discussion, "shop_id", "reply_user"),
		}

		# 验证来源有效性
		if source not in SOURCE_CONFIG:
			raise ValueError(f"不支持的来源类型: {source}，可用选项: {list(SOURCE_CONFIG.keys())}")

		# 获取基础数据
		method_func, id_key, user_field = SOURCE_CONFIG[source]
		comments = method_func(**{id_key: com_id, "limit": max_limit})

		# 定义处理函数
		def _extract_reply_user(reply: dict) -> int:
			"""提取回复用户ID"""
			return reply[user_field]["id"]

		def _generate_replies(comment: dict) -> Generator[dict]:
			"""生成回复数据"""
			if source == "post":
				yield from self.forum_obtain.get_reply_post_comments(post_id=comment["id"], limit=None)
			else:
				yield from comment.get("replies", {}).get("items", [])

		def _process_user_id() -> list[int]:
			"""提取用户ID列表"""
			user_ids = []
			for comment in comments:
				user_ids.append(comment["user"]["id"])
				user_ids.extend(_extract_reply_user(reply) for reply in _generate_replies(comment))
			return self.tool_process.deduplicate(user_ids)

		def _process_comment_id() -> list[str]:
			"""生成评论ID链"""
			comment_ids = []
			for comment in comments:
				comment_ids.append(str(comment["id"]))
				comment_ids.extend(f"{comment['id']}.{reply['id']}" for reply in _generate_replies(comment))
			return self.tool_process.deduplicate(comment_ids)

		def _process_detailed() -> list[dict]:
			"""构建结构化数据"""
			return [
				{
					"user_id": item["user"]["id"],
					"nickname": item["user"]["nickname"],
					"id": item["id"],
					"content": item["content"],
					"created_at": item["created_at"],
					"is_top": item.get("is_top", False),
					"replies": [
						{
							"id": r_item["id"],
							"content": r_item["content"],
							"created_at": r_item["created_at"],
							"user_id": _extract_reply_user(r_item),
							"nickname": r_item[user_field]["nickname"],
						}
						for r_item in _generate_replies(item)
					],
				}
				
				for item in comments
			]

		# 处理方法路由
		method_router = {
			"user_id": _process_user_id,
			"comment_id": _process_comment_id,
			"comments": _process_detailed,
		}

		if method not in method_router:
			raise ValueError(f"不支持的请求方法: {method}，可用选项: {list(method_router.keys())}")

		return method_router[method]()


@decorator.singleton
class Motion(ClassUnion):
	def __init__(self) -> None:
			super().__init__()
			# 配置不同来源的参数
			self.SOURCE_CONFIG = {
				"work": {
					"items": lambda: self.user_obtain.get_user_works_web(self.data.ACCOUNT_DATA.id, limit=None),
					"get_comments": lambda _id: Obtain().get_comments_detail_new(_id, "work", "comments"),
					"delete": self.work_motion.del_comment_work,
					"title_key": "work_name"
				},
				"post": {
					"items": lambda: self.forum_obtain.get_post_mine_all("created", limit=None),
					"get_comments": lambda _id: Obtain().get_comments_detail_new(_id, "post", "comments"),
					"delete": lambda _id, comment_id, **_: self.forum_motion.delete_comment_post_reply(
						comment_id, "comments" if _.get("is_reply") else "replies"),
					"title_key": "title"
				}
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
			# 初始化配置参数
			config = self._get_source_config(source)
			params = {
				"ads": self.data.USER_DATA.ads,
				"blacklist": self.data.USER_DATA.black_room,
				"spam_max": self.setting.PARAMETER.spam_del_max,
			}

			# 收集待处理项
			target_lists = defaultdict(list)
			for item in config["items"]():
				self._process_item(item, config, action_type, params, target_lists)

			# 执行删除操作
			return self._execute_deletion(
				target_list=target_lists[action_type],
				delete_handler=config["delete"],
				label={
					"ads": "广告评论",
					"blacklist": "黑名单评论", 
					"duplicates": "刷屏评论"
				}[action_type]
			)

	def _get_source_config(self, source: str) -> dict:
			"""获取来源配置"""
			if source not in self.SOURCE_CONFIG:
				raise ValueError(f"不支持的来源类型: {source}")
			return self.SOURCE_CONFIG[source]

	def _process_item(
			self,
			item: dict,
			config: dict,
			action_type: str,
			params: dict,
			target_lists: defaultdict
		) -> None:
			"""处理单个作品/帖子"""
			item_id = int(item["id"])
			title = item[config["title_key"]]
			comments = config["get_comments"](item_id)

			# 分类型处理逻辑
			if action_type in ("ads", "blacklist"):
				self._find_abnormal_comments(comments, item_id, title, action_type, params, target_lists)
			elif action_type == "duplicates":
				self._find_duplicate_comments(comments, item_id, params, target_lists)

	def _find_abnormal_comments(
		self,
		comments: list,
		item_id: int,
		title: str,
		action_type: str,
		params: dict,
		target_lists: defaultdict
	) -> None:
		"""发现异常评论（广告/黑名单）"""
		for comment in comments:
			if comment.get("is_top"):
				continue  # 跳过置顶内容

			# 处理主评论
			if self._check_condition(comment, action_type, params):
				identifier = f"{item_id}.{comment['id']}:comment"
				# 修正参数顺序：添加action_type参数
				self._log_and_add(
					target_lists=target_lists,
					data=comment,
					identifier=identifier,
					title=title,
					action_type=action_type  # 正确传递action_type
				)

			# 处理回复
			for reply in comment.get("replies", []):
				if self._check_condition(reply, action_type, params):
					identifier = f"{item_id}.{reply['id']}:reply"
					# 修正参数顺序：添加action_type参数和parent_content
					self._log_and_add(
						target_lists=target_lists,
						data=reply,
						identifier=identifier,
						title=title,
						action_type=action_type,
						parent_content=comment["content"]  # 作为最后一个参数
					)

	def _check_condition(self, data: dict, action_type: str, params: dict) -> bool:
			"""检查评论是否符合处理条件"""
			content = data["content"].lower()
			user_id = str(data["user_id"])
			
			if action_type == "ads":
				
				return any(ad in content for ad in params["ads"])
			if action_type == "blacklist":
				return user_id in params["blacklist"]
			return False

	def _log_and_add(
		self,
		target_lists: defaultdict,
		data: dict,
		identifier: str,
		title: str,
		action_type: str,  
		parent_content: str = ""
	) -> None:
		"""记录日志并添加到处理列表"""
		log_template = {
			"ads": "广告{type} [{title}]{parent}：{content}",
			"blacklist": "黑名单{type} [{title}]{parent}：{nickname}"
		}[action_type]
		
		log_message = log_template.format(
			type="回复" if ":reply" in identifier else "评论",
			title=title,
			parent=f" ({parent_content})" if parent_content else "",
			content=data["content"],
			nickname=data["nickname"]
		)
		print(log_message)
		target_lists[action_type].append(identifier)

	def _find_duplicate_comments(
			self,
			comments: list,
			item_id: int,
			params: dict,
			target_lists: defaultdict
		) -> None:
			"""发现重复刷屏评论"""
			content_map = defaultdict(list)
			for comment in comments:
				self._track_comment(comment, item_id, content_map)
				for reply in comment.get("replies", []):
					self._track_comment(reply, item_id, content_map, is_reply=True)

			# 筛选达到阈值的评论
			for (uid, content), ids in content_map.items():
				if len(ids) >= params["spam_max"]:
					print(f"发现刷屏评论：用户{uid} 重复发送：{content} {len(ids)}次")
					target_lists["duplicates"].extend(ids)

	def _track_comment(
			self,
			data: dict,
			item_id: int,
			content_map: defaultdict,
			is_reply: bool = False
		) -> None:
			"""跟踪评论数据"""
			key = (data["user_id"], data["content"].lower())
			identifier = f"{item_id}.{data['id']}:{'reply' if is_reply else 'comment'}"
			content_map[key].append(identifier)

	@decorator.skip_on_error
	def _execute_deletion(
			self,
			target_list: list,
			delete_handler: Callable[[int, int, bool], bool],
			label: str
		) -> bool:
			"""执行删除操作（保留原有注释）
			
			注意：由于编程猫社区接口限制，需要先删除回复再删除主评论，
			通过反转列表实现从后往前删除，避免出现删除父级评论后无法删除子回复的情况
			"""
			if not target_list:
				print(f"未发现{label}")
				return True

			print(f"\n发现以下{label}（共{len(target_list)}条）：")
			for item in reversed(target_list):
				print(f" - {item.split(':')[0]}")

			if input(f"\n确认删除所有{label}？（Y/N）").lower() != "y":
				print("操作已取消")
				return True

			# 从最后一条开始删除（先删回复后删评论）
			for entry in reversed(target_list):
				parts = entry.split(':')[0].split('.')
				item_id, comment_id = map(int, parts)
				is_reply = ":reply" in entry
				
				if not delete_handler(item_id, comment_id, is_reply):
					print(f"删除失败：{entry}")
					return False
				print(f"已删除：{entry}")
			
			return True

	def clear_red_point(self, method: Literal["nemo", "web"] = "web") -> bool:
		def get_message_counts(method: Literal["web", "nemo"]) -> dict:
			return self.community_obtain.get_message_count(method)

		def send_clear_request(url: str, params: dict) -> int:
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
			item["id"] = cast("int", item["id"])
			if not self.work_motion.like_work(work_id=item["id"]):
				return False
		return True

	def reply_work(self) -> bool:
		new_replies: list[dict] = Obtain().get_new_replies()

		@overload
		def _preprocess_data(data_type: Literal["answers"]) -> dict[str, list[str] | str]: ...

		@overload
		def _preprocess_data(data_type: Literal["replies"]) -> list[str]: ...
		# 合并预处理逻辑
		def _preprocess_data(data_type: Literal["answers", "replies"]) -> dict[str, list[str] | str] | list[str]:
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
		all_data.extend(
			(
				self.user_obtain.get_data_details(),
				self.user_obtain.get_data_level(),
				self.user_obtain.get_data_name(),
				self.user_obtain.get_data_privacy(),
				self.user_obtain.get_data_score(),
				self.user_obtain.get_data_profile("web"),
				self.user_obtain.get_data_tiger(),
				self.edu_obtain.get_data_details(),
			),
		)
		return self.tool_routine.merge_user_data(data_list=all_data)

	# 查看账户状态
	def get_account_status(self) -> str:
		status = self.user_obtain.get_data_details()
		return f"禁言状态{status['voice_forbidden']}, 签订友好条约{status['has_signed']}"

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
				choice = input("选择操作: D:删除, S:禁言7天, P:通过, C:查看, F:检查违规, J:跳过  ").upper()
				handler = getattr(self.whale_motion, cfg["handle_method"])
				if choice == "J":
					break
				if choice in {"D", "S", "P"}:
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
		if report_type in {"comment", "discussion"}:
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

		if report_type in {"comment", "discussion"}:
			comments = Obtain().get_comments_detail_new(
				com_id=int(source_id),
				source=cast("Literal['shop', 'post']", source_type),
				method=cast("Literal['comments']", method),
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

	def _auto_report_comments(self, user_comments: list, source_id: int, report_source: str) -> None:  # noqa: PLR0915
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
							if report_count >= self.setting.PARAMETER.report_work_max or success_count == 0:
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
								# print(f"切换到账号 {current_account[0]}")
								print("已经切换账号")
								sleep(5)
								# self.acquire.switch_account("", identity="edu")
								self.community_login.login_password(identity=current_account[0], password=current_account[1], status="edu")
								sleep(10)
								# self.acquire.switch_account(token=self.acquire.token.edu, identity="edu")
								# print("*" * 85)
								# print(f"token={self.acquire.token.edu}")
								# self._switch_account(current_account)
								# current_account_idx += 1
								report_count = 0
								success_count = 0

							# 执行举报逻辑
							_item_id, comment_id = single_item.split(":")[0].split(".")
							# comments = Obtain().get_comments_detail_new(
							# 	com_id=source_id,
							# 	source=cast(Literal["shop", "post"], source_type),
							# 	method="comment_id",
							# )
							parent_id, _reply_id = self.tool_routine.find_prefix_suffix(
								text=comment_id,
								candidates=user_comments,
							)
							# self.acquire.switch_account(self.acquire.token.edu, identity="edu")
							# self.community_motion.sign_nature()
							if self.report_work(
								source=cast("Literal['forum', 'work', 'shop']", report_source),
								target_id=int(comment_id),
								source_id=source_id,
								reason_id=7,
								parent_id=cast("int", parent_id),
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
		"""使用pop随机抽取学生账密"""
		students = list(self.edu_obtain.get_students(limit=limit))

		while students:
			# 随机选择一个索引并pop
			student = students.pop(randint(0, len(students) - 1))  # noqa: S311
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

	def _analyze_comments(self, comments: list, source_id: int) -> Generator[dict[tuple[int, str], list[str]]] | None:
		content_map = defaultdict(list)
		for comment in comments:
			content = comment["content"].lower()
			if any(ad in content for ad in self.data.USER_DATA.ads):
				print(f"广告回复: {content}")
			params = {
				"spam_max": self.setting.PARAMETER.spam_del_max,
			}
			self._find_duplicate_comments(comments, source_id, params, content_map)
			for reply in comment.get("replies", []):
				self._find_duplicate_comments(reply, source_id, params, content_map)
				if any(ad in reply["content"].lower() for ad in self.data.USER_DATA.ads):
					print(f"广告回复: {reply['content']}")
		# (user_id,content):[item_id.comment_id1:reply/comment,item_id.comment_id2:reply/comment]
		for (user_id, content), entry in content_map.items():
			if len(entry) >= self.setting.PARAMETER.spam_del_max:
				# print(f"发现刷屏评论: {content}")
				# print(f"此用户已经刷屏,共发布{len(entry)}次")
				yield {(user_id, content): entry}

	def report_work(
		self,
		source: Literal["forum", "work", "shop"],
		target_id: int,
		source_id: int,
		reason_id: Literal[0, 1, 2, 3, 4, 5, 6, 7, 8],
		parent_id: int | None = None,
		description: str = "",
		*,
		is_reply: bool = False,
	) -> bool:
		# 1: 违法违规; 2: 色情暴力
		# 3: 侵犯隐私; 4: 人身攻击
		# 5: 引战; 6: 垃圾广告
		# 7: 无意义刷屏; 8: 不良信息
		# 0: 自定义

		reason_content = self.community_obtain.get_report_reason()["items"][reason_id]["content"]
		match source:
			case "work":
				return self.work_motion.report_comment_work(work_id=target_id, comment_id=source_id, reason=reason_content)
			case "forum":
				source_ = "COMMENT" if is_reply else "REPLY"
				return self.forum_motion.report_reply_or_comment(comment_id=target_id, reason_id=reason_id, description=description, source=source_, return_data=False)
			case "shop":
				if is_reply:
					parent_id = cast("int", parent_id)
					return self.shop_motion.report_comment(
						comment_id=target_id,
						reason_content=reason_content,
						reason_id=reason_id,
						reporter_id=int(self.data.ACCOUNT_DATA.id),
						comment_parent_id=parent_id,
						description=description,
					)
				return self.shop_motion.report_comment(
					comment_id=target_id,
					reason_content=reason_content,
					reason_id=reason_id,
					reporter_id=int(self.data.ACCOUNT_DATA.id),
					description=description,
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
