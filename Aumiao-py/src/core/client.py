from collections import defaultdict
from collections.abc import Callable, Generator
from enum import Enum
from json import loads
from random import choice, randint
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
		self.community_login = community.Login()
		self.community_motion = community.Motion()
		self.community_obtain = community.Obtain()
		self.data = data.DataManager().data
		self.edu_motion = edu.Motion()
		self.edu_obtain = edu.Obtain()
		self.file = file.CodeMaoFile()
		self.forum_motion = forum.Motion()
		self.forum_obtain = forum.Obtain()
		self.setting = data.SettingManager().data
		self.shop_motion = shop.Motion()
		self.shop_obtain = shop.Obtain()
		self.tool = tool
		self.user_motion = user.Motion()
		self.user_obtain = user.Obtain()
		self.whale_motion = whale.Motion()
		self.whale_obtain = whale.Obtain()
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
			self.tool.DataAnalyzer().compare_datasets(
				before=before_data,
				after=user_data,
				metrics={
					"fans": "粉丝",
					"collected": "被收藏",
					"liked": "被赞",
					"view": "被预览",
				},
				timestamp_field="timestamp",
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
		self.COLOR_DATA = "\033[38;5;228m"  # 月光黄-数据
		self.COLOR_LINK = "\033[4;38;5;183m"  # 薰衣草紫带下划线-链接
		self.COLOR_RESET = "\033[0m"  # 样式重置
		self.COLOR_SLOGAN = "\033[38;5;80m"  # 湖水青-标语
		self.COLOR_TITLE = "\033[38;5;75m"  # 晴空蓝-标题
		self.COLOR_VERSION = "\033[38;5;114m"  # 新芽绿-版本号

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
		"""获取社区新回复
		Args:
			limit: 获取数量限制 (0表示获取全部新回复)
			type_item: 消息类型
		Returns:
			结构化回复数据列表
		"""
		replies: list[dict] = []

		# 获取初始消息计数
		try:
			message_data = self.community_obtain.get_message_count(method="web")
			total_replies = message_data[0].get("count", 0) if message_data else 0
		except Exception as e:
			print(f"获取消息计数失败: {e}")
			return replies

		# 处理无新回复的情况
		if total_replies == 0 and limit == 0:
			return replies

		# 计算实际需要获取的数量
		remaining = total_replies if limit == 0 else min(limit, total_replies)
		offset = 0

		while remaining > 0:
			# 动态计算每次请求量(5-200之间)
			current_limit = self.tool.MathUtils().clamp(remaining, 5, 200)

			try:
				response = self.community_obtain.get_replies(
					types=type_item,
					limit=current_limit,
					offset=offset,
				)
				batch = response.get("items", [])
			except Exception as e:
				print(f"获取回复失败: {e}")
				break

			# 计算实际有效数据量(考虑剩余需求)
			valid_batch = batch[:remaining]
			replies.extend(valid_batch)

			# 更新迭代参数
			actual_count = len(valid_batch)
			remaining -= actual_count
			offset += current_limit

			# 提前退出条件(无更多数据时)
			if actual_count < current_limit:
				break

		return replies

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
		source_config = {
			"work": (self.work_obtain.get_work_comments, "work_id", "reply_user"),
			"post": (self.forum_obtain.get_post_replies_posts, "ids", "user"),
			"shop": (self.shop_obtain.get_shop_discussion, "shop_id", "reply_user"),
		}

		# 验证来源有效性
		if source not in source_config:
			msg = f"不支持的来源类型: {source},可用选项: {list(source_config.keys())}"
			raise ValueError(msg)

		# 获取基础数据
		method_func, id_key, user_field = source_config[source]
		comments = method_func(**{id_key: com_id, "limit": max_limit})

		# 定义处理函数
		def _extract_reply_user(reply: dict) -> int:
			"""提取回复用户ID"""
			return reply[user_field]["id"]

		def _generate_replies(comment: dict) -> Generator[dict]:
			if source == "post":
				yield from self.forum_obtain.get_reply_post_comments(post_id=comment["id"], limit=None)
			else:
				yield from comment.get("replies", {}).get("items", [])

		def _process_user_id() -> list[object]:
			"""提取用户ID列表"""
			user_ids = []
			for comment in comments:
				user_ids.append(comment["user"]["id"])
				user_ids.extend(_extract_reply_user(reply) for reply in _generate_replies(comment))
			return self.tool.DataProcessor().deduplicate(user_ids)

		def _process_comment_id() -> list[object]:
			"""生成评论ID链"""
			comment_ids = []
			for comment in comments:
				comment_ids.append(str(comment["id"]))
				comment_ids.extend(f"{comment['id']}.{reply['id']}" for reply in _generate_replies(comment))
			return self.tool.DataProcessor().deduplicate(comment_ids)

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
			msg = f"不支持的请求方法: {method},可用选项: {list(method_router.keys())}"
			raise ValueError(msg)

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
				"title_key": "work_name",
			},
			"post": {
				"items": lambda: self.forum_obtain.get_post_mine_all("created", limit=None),
				"get_comments": lambda _id: Obtain().get_comments_detail_new(_id, "post", "comments"),
				"delete": lambda _id, comment_id, **_: self.forum_motion.delete_comment_post_reply(comment_id, "comments" if _.get("is_reply") else "replies"),
				"title_key": "title",
			},
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
			label={"ads": "广告评论", "blacklist": "黑名单评论", "duplicates": "刷屏评论"}[action_type],
		)

	def _get_source_config(self, source: str) -> dict:
		"""获取来源配置"""
		if source not in self.SOURCE_CONFIG:
			msg = f"不支持的来源类型: {source}"
			raise ValueError(msg)
		return self.SOURCE_CONFIG[source]

	def _process_item(self, item: dict, config: dict, action_type: Literal["ads", "duplicates", "blacklist"], params: dict, target_lists: defaultdict) -> None:
		"""处理单个作品/帖子"""
		item_id = int(item["id"])
		title = item[config["title_key"]]
		comments = config["get_comments"](item_id)

		# 分类型处理逻辑
		if action_type in {"ads", "blacklist"}:
			action_type = cast("Literal['ads', 'blacklist']", action_type)
			self._find_abnormal_comments(comments, item_id, title, action_type, params, target_lists)
		elif action_type == "duplicates":
			self._find_duplicate_comments(comments, item_id, params, target_lists)

	def _find_abnormal_comments(self, comments: list, item_id: int, title: str, action_type: Literal["ads", "blacklist"], params: dict, target_lists: defaultdict) -> None:
		"""发现异常评论 (广告/黑名单 )"""
		for comment in comments:
			if comment.get("is_top"):
				continue  # 跳过置顶内容

			# 处理主评论
			if self._check_condition(comment, action_type, params):
				identifier = f"{item_id}.{comment['id']}:comment"
				# 修正参数顺序 :添加action_type参数
				self._log_and_add(
					target_lists=target_lists,
					data=comment,
					identifier=identifier,
					title=title,
					action_type=action_type,  # 正确传递action_type
				)

			# 处理回复
			for reply in comment.get("replies", []):
				if self._check_condition(reply, action_type, params):
					identifier = f"{item_id}.{reply['id']}:reply"
					# 修正参数顺序 :添加action_type参数和parent_content
					self._log_and_add(
						target_lists=target_lists,
						data=reply,
						identifier=identifier,
						title=title,
						action_type=action_type,
						parent_content=comment["content"],  # 作为最后一个参数
					)

	@staticmethod
	def _check_condition(data: dict, action_type: Literal["ads", "blacklist"], params: dict) -> bool:
		"""检查评论是否符合处理条件"""
		content = data["content"].lower()
		user_id = str(data["user_id"])

		if action_type == "ads":
			return any(ad in content for ad in params["ads"])
		if action_type == "blacklist":
			return user_id in params["blacklist"]
		return False

	@staticmethod
	def _log_and_add(target_lists: defaultdict, data: dict, identifier: str, title: str, action_type: str, parent_content: str = "") -> None:
		"""记录日志并添加到处理列表"""
		log_template = {"ads": "广告{type} [{title}]{parent} :{content}", "blacklist": "黑名单{type} [{title}]{parent} :{nickname}"}[action_type]

		log_message = log_template.format(
			type="回复" if ":reply" in identifier else "评论",
			title=title,
			parent=f" ({parent_content})" if parent_content else "",
			content=data["content"],
			nickname=data["nickname"],
		)
		print(log_message)
		target_lists[action_type].append(identifier)

	def _find_duplicate_comments(self, comments: list, item_id: int, params: dict, target_lists: defaultdict) -> None:
		"""发现重复刷屏评论"""
		content_map = defaultdict(list)
		for comment in comments:
			self._track_comment(comment, item_id, content_map)
			for reply in comment.get("replies", []):
				self._track_comment(reply, item_id, content_map, is_reply=True)

		# 筛选达到阈值的评论
		for (uid, content), ids in content_map.items():
			if len(ids) >= params["spam_max"]:
				print(f"发现刷屏评论 :用户{uid} 重复发送 :{content} {len(ids)}次")
				target_lists["duplicates"].extend(ids)

	@staticmethod
	def _track_comment(data: dict, item_id: int, content_map: defaultdict, *, is_reply: bool = False) -> None:
		"""跟踪评论数据"""
		if not isinstance(data, dict):
			msg = f"Invalid comment data type: {type(data)}, expected dict"
			raise TypeError(msg)

		key = (data["user_id"], data["content"].lower())
		identifier = f"{item_id}.{data['id']}:{'reply' if is_reply else 'comment'}"
		content_map[key].append(identifier)

	@staticmethod
	@decorator.skip_on_error
	def _execute_deletion(target_list: list, delete_handler: Callable[[int, int, bool], bool], label: str) -> bool:
		"""执行删除操作 (保留原有注释 )

		注意 :由于编程猫社区接口限制,需要先删除回复再删除主评论,
		通过反转列表实现从后往前删除,避免出现删除父级评论后无法删除子回复的情况
		"""
		if not target_list:
			print(f"未发现{label}")
			return True

		print(f"\n发现以下{label} (共{len(target_list)}条 ) :")
		for item in reversed(target_list):
			print(f" - {item.split(':')[0]}")

		if input(f"\n确认删除所有{label}? (Y/N )").lower() != "y":
			print("操作已取消")
			return True

		# 从最后一条开始删除 (先删回复后删评论 )
		for entry in reversed(target_list):
			parts = entry.split(":")[0].split(".")
			item_id, comment_id = map(int, parts)
			is_reply = ":reply" in entry

			if not delete_handler(item_id, comment_id, is_reply):
				print(f"删除失败 :{entry}")
				return False
			print(f"已删除 :{entry}")

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
		# 配置参数映射表
		method_config = {
			"web": {
				"endpoint": "/web/message-record",
				"message_types": self.setting.PARAMETER.all_read_type,
				"check_keys": ["count"],  # 对应get_message_counts返回值的结构
			},
			"nemo": {
				"endpoint": "/nemo/v2/user/message/{type}",
				"message_types": [1, 3],  # 1:点赞收藏 3:fork
				"check_keys": ["like_collection_count", "comment_count", "re_create_count", "system_count"],
			},
		}

		# 验证方法有效性
		if method not in method_config:
			msg = f"不支持的方法类型: {method}"
			raise ValueError(msg)

		config = method_config[method]
		page_size = 200
		params = {"limit": page_size, "offset": 0}

		def is_all_cleared(counts: dict) -> bool:
			"""检查是否全部消息已读"""
			if method == "web":
				return all(count["count"] == 0 for count in counts[:3])
			return sum(counts[key] for key in config["check_keys"]) == 0

		def send_batch_requests() -> bool:
			"""批量发送标记已读请求"""
			responses = {}
			for msg_type in config["message_types"]:
				# 构造请求端点
				endpoint = config["endpoint"].format(type=msg_type) if "{" in config["endpoint"] else config["endpoint"]

				# 添加类型参数
				request_params = params.copy()
				if method == "web":
					request_params["query_type"] = msg_type

				# 发送请求
				response = self.acquire.send_request(endpoint=endpoint, method="GET", params=request_params)
				responses[msg_type] = response.status_code

			return all(code == OK_CODE for code in responses.values())

		try:
			while True:
				# 获取当前未读状态
				current_counts = self.community_obtain.get_message_count(method)
				if is_all_cleared(current_counts):
					return True

				# 批量处理当前页
				if not send_batch_requests():
					return False

				# 更新分页参数
				params["offset"] += page_size

		except Exception as e:
			print(f"清除红点过程中发生异常: {e}")
			return False

	def like_all_work(self, user_id: str, works_list: list[dict] | Generator[dict]) -> None:
		self.work_motion.follow_work(user_id=int(user_id))
		for item in works_list:
			item["id"] = cast("int", item["id"])
			self.work_motion.like_work(work_id=item["id"])
			self.work_motion.collection_work(work_id=item["id"])

	def reply_work(self) -> bool:  # noqa: PLR0914
		"""自动回复作品/帖子评论"""
		# 合并预处理和数据获取逻辑
		formatted_answers = {
			k: v.format(**self.data.INFO) if isinstance(v, str) else [i.format(**self.data.INFO) for i in v] for answer in self.data.USER_DATA.answers for k, v in answer.items()
		}
		formatted_replies = [r.format(**self.data.INFO) for r in self.data.USER_DATA.replies]

		# 获取并过滤有效回复 (解决set类型问题 )
		valid_types = list(VALID_REPLY_TYPES)  # 将set转为list
		new_replies = self.tool.DataProcessor().filter_by_nested_values(
			data=Obtain().get_new_replies(),
			id_path="type",
			target_values=valid_types,
		)

		for reply in new_replies:
			try:
				# 合并处理逻辑
				content = loads(reply["content"])
				msg = content["message"]
				reply_type = reply["type"]
				# 提取评论内容
				comment_text = msg["comment"] if reply_type in {"WORK_COMMENT", "POST_COMMENT"} else msg["reply"]
				# 匹配回复内容
				chosen = next((choice(resp) for keyword, resp in formatted_answers.items() if keyword in comment_text), choice(formatted_replies))  # noqa: S311
				# 执行回复 (解决source类型问题 )
				source_type = cast("Literal['work', 'post']", "work" if reply_type.startswith("WORK") else "post")
				# 获取评论ID (解决find_prefix_suffix参数问题 )
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
						text=target_id,  # 添加text参数
						candidates=comment_ids,
					)[0]
					comment_id = int(found) if found else 0
				print(f"\n{'=' * 30} 新回复 {'=' * 30}")
				print(f"类型: {reply_type}")
				# 提取评论内容
				comment_text = msg["comment"] if reply_type in {"WORK_COMMENT", "POST_COMMENT"} else msg["reply"]
				print(f"提取关键文本: {comment_text}")
				# 匹配回复内容 (添加匹配提示 )
				matched_keyword = None
				for keyword, resp in formatted_answers.items():
					if keyword in comment_text:
						matched_keyword = keyword
						chosen = choice(resp) if isinstance(resp, list) else resp  # noqa: S311
						print(f"匹配到关键字「{keyword}」")
						break
				if not matched_keyword:
					chosen = choice(formatted_replies)  # noqa: S311
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

				(self.work_motion.reply_work if source_type == "work" else self.forum_motion.reply_comment)(**params)
				print(f"已发送回复到{source_type},评论ID: {comment_id}")

			except Exception as e:
				print(f"回复处理失败: {e}")
				continue

		return True

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
		return self.tool.DataMerger().merge(datasets=all_data)

	# 查看账户状态
	def get_account_status(self) -> str:
		status = self.user_obtain.get_data_details()
		return f"禁言状态{status['voice_forbidden']}, 签订友好条约{status['has_signed']}"

	# 处理举报
	# 需要风纪权限
	def handle_report(self, admin_id: int) -> None:  # noqa: PLR0915
		class ReportRecord(TypedDict):
			item: dict
			report_type: Literal["comment", "post", "discussion"]
			com_id: str
			content: str  # 新增内容字段
			processed: bool
			action: str | None

		batch_config = {
			"total_threshold": 15,
			"duplicate_threshold": 5,
			"content_threshold": 3,  # 新增内容相同阈值
		}

		def get_content_key(record: ReportRecord) -> tuple:
			"""生成内容唯一标识"""
			cfg = get_type_config(record["report_type"], record["item"])
			return (
				record["item"][cfg["content_field"]],
				record["report_type"],
				record["item"][cfg["source_id_field"]],
			)

		def get_type_config(report_type: str, current_item: dict) -> dict:
			"""动态生成类型配置(修复闭包问题)"""
			return {
				"comment": {
					"content_field": "comment_content",
					"user_field": "comment_user",
					"handle_method": "handle_comment_report",
					"source_id_field": "comment_source_object_id",
					"source_name_field": "comment_source_object_name",
					"special_check": lambda i=current_item: i.get("comment_source") == "WORK_SHOP",
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
			}[report_type]

		def process_report_batch(records: list[ReportRecord]) -> None:  # noqa: PLR0912
			"""智能批量处理核心逻辑(增强版)"""
			# 分组策略:按ID和内容双重分组
			id_map = defaultdict(list)
			content_map = defaultdict(list)

			for record in records:
				# ID分组
				id_map[record["com_id"]].append(record)
				# 内容分组
				content_key = get_content_key(record)
				content_map[content_key].append(record)

			# 合并需要批量处理的项目

			# 1. 按ID分组
			batch_groups = [("ID", items[0]["com_id"], items) for items in id_map.values() if len(items) >= batch_config["duplicate_threshold"]]

			# 2. 按内容分组
			for (content, report_type, _), items in content_map.items():
				if len(items) >= batch_config["content_threshold"]:
					batch_groups.append(("内容", f"{report_type}:{content[:20]}...", items))

			# 批量处理提示
			if batch_groups and len(records) >= batch_config["total_threshold"]:
				print("\n发现以下批量处理项:")
				for i, (g_type, g_key, items) in enumerate(batch_groups, 1):
					print(f"{i}. [{g_type}] {g_key} ({len(items)}次举报)")

				if input("\n是否查看详情?(Y/N) ").upper() == "Y":
					for g_type, g_key, items in batch_groups:
						print(f"\n=== {g_type}组: {g_key} ===")
						for item in items[:3]:  # 展示前3条
							print(f"举报ID: {item['item']['id']} | 时间: {self.tool.TimeUtils().format_timestamp(item['item']['created_at'])}")
						if len(items) > batch_config["content_threshold"]:
							print(f"...及其他{len(items) - 3}条举报")

				if input("\n确认批量处理这些项目?(Y/N) ").upper() == "Y":
					# 处理批量组
					for g_type, g_key, items in batch_groups:
						print(f"\n正在处理 [{g_type}] {g_key}...")
						first_action = None

						# 处理首个项目
						if not items[0]["processed"]:
							first_action = process_single_item(items[0], batch_mode=True)

						# 自动应用操作到同组项目
						if first_action:
							for item in items[1:]:
								if not item["processed"]:
									apply_action(item, first_action)
									print(f"已自动处理举报ID: {item['item']['id']}")

			# 处理剩余项目
			for record in records:
				if not record["processed"]:
					process_single_item(record)

		def process_single_item(record: ReportRecord, *, batch_mode: bool = False) -> str:
			item = record["item"]
			report_type = record["report_type"]
			cfg = get_type_config(report_type, item)
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
			print(f"举报时间: {self.tool.TimeUtils().format_timestamp(item['created_at'])}")
			if report_type == "post":
				print(f"举报线索: {item['description']}")

			while True:
				choice = input("选择操作: D:删除, S:禁言7天, T:禁言3月 P:通过, C:查看, F:检查违规, J:跳过  ").upper()
				if choice in {"D", "S", "T", "P"}:
					status_map = {"D": "DELETE", "S": "MUTE_SEVEN_DAYS", "P": "PASS", "T": "MUTE_THREE_MONTHS"}
					handler = getattr(self.whale_motion, cfg["handle_method"])
					handler(report_id=item["id"], status=status_map[choice], admin_id=admin_id)
					record["processed"] = True
					return choice
				if choice == "C":
					self._show_details(item, report_type, cfg)
				elif choice == "F" and cfg["special_check"]():
					# self._check_violations(item, report_type, cfg)
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
				if choice == "J" and batch_mode:
					print("批量处理已取消")

				print("无效输入")

		def apply_action(record: ReportRecord, action: str) -> None:
			cfg = get_type_config(record["report_type"], record["item"])
			handler = getattr(self.whale_motion, cfg["handle_method"])
			handler(
				report_id=record["item"]["id"],
				status={"D": "DELETE", "S": "MUTE_SEVEN_DAYS", "P": "PASS"}[action],
				admin_id=admin_id,
			)
			record["processed"] = True

		# 数据收集
		all_records: list[ReportRecord] = []
		for report_list, report_type in [
			(self.whale_obtain.get_comment_report(types="ALL", status="TOBEDONE", limit=None), "comment"),
			(self.whale_obtain.get_post_report(status="TOBEDONE", limit=None), "post"),
			(self.whale_obtain.get_discussion_report(status="TOBEDONE", limit=None), "discussion"),
		]:
			for item in report_list:
				cfg = get_type_config(report_type, item)
				all_records.append(
					{
						"item": item,
						"report_type": cast("Literal['comment', 'post', 'discussion']", report_type),
						"com_id": str(item[cfg["com_id"]]),
						"content": item[cfg["content_field"]],  # 记录内容
						"processed": False,
						"action": None,
					},
				)
		process_report_batch(all_records)
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
								print(f"发送时间: {self.tool.TimeUtils().format_timestamp(reply['created_at'])}")
								break
						break
			else:
				for comment in comments:
					if comment["id"] == item["comment_id"]:
						print(f"发送时间: {self.tool.TimeUtils().format_timestamp(comment['created_at'])}")
						break
		else:
			details = self.forum_obtain.get_single_post_details(ids=item[cfg["source_id_field"]])
			print(f"发送时间: {self.tool.TimeUtils().format_timestamp(details['created_at'])}")  # 有的帖子可能有更新,但是大部分是created_at,为了迎合网页显示的发布时间

	def _switch_edu_account(self, limit: int | None) -> Generator[tuple[str, str]]:
		students = list(self.edu_obtain.get_students(limit=limit))

		while students:
			# 随机选择一个索引并pop
			student = students.pop(randint(0, len(students) - 1))  # noqa: S311
			self.acquire.switch_account(token=self.acquire.token.average, identity="average")
			yield student["username"], self.edu_motion.reset_password(student["id"])["password"]

	def _check_report(self, source_id: int, source_type: Literal["shop", "work", "discussion", "post"], title: str, user_id: int) -> None:
		if source_type in {"work", "discussion", "shop"}:
			source_type = cast("Literal['post', 'work', 'shop']", source_type)
			# 分析违规评论
			violations = self._analyze_comments_violations(
				source_id=source_id,
				source_type=source_type,
				title=title,
			)

			if not violations:
				print("没有违规评论")
				return

			# 处理举报请求
			self._process_report_requests(
				violations=violations,
				source_id=source_id,
				source_type=source_type,
			)
		if source_type == "post":
			source_type = cast("Literal['post']", source_type)
			search_result = list(self.forum_obtain.search_posts(title=title, limit=None))
			user_posts = self.tool.DataProcessor().filter_by_nested_values(data=search_result, id_path="user.id", target_values=[user_id])
			if len(user_posts) >= self.setting.PARAMETER.spam_del_max:
				print(f"用户{user_id} 已连续发布帖子{title} {len(user_posts)}次")

	def _analyze_comments_violations(
		self,
		source_id: int,
		source_type: Literal["post", "work", "shop"],
		title: str,
	) -> list[str]:
		"""分析评论违规内容"""
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

		# 收集异常评论
		abnormal_targets = defaultdict(list)
		self._find_abnormal_comments(
			comments=comments,
			item_id=source_id,
			title=title,
			action_type="ads",
			params=params,
			target_lists=abnormal_targets,
		)

		# 收集重复评论
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
		"""处理举报请求核心逻辑"""
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
		report_counter = 0
		max_retries = 3
		reason_content = self.community_obtain.get_report_reason()["items"][7]["content"]
		source_map = {"work": "work", "post": "forum", "shop": "shop"}

		for violation in violations:
			retries = 0
			while retries < max_retries:
				try:
					# 账号切换逻辑
					if report_counter >= self.setting.PARAMETER.report_work_max:
						current_account = next(account_pool, None)
						if not current_account:
							print("所有账号均已尝试")
							return
						print("切换教育账号")
						sleep(5)
						self.community_login.login_password(
							identity=current_account[0],
							password=current_account[1],
							status="edu",
						)
						report_counter = 0

					# 解析评论信息
					parts = violation.split(":")
					_item_id, comment_id = parts[0].split(".")
					is_reply = "reply" in violation

					# 获取父评论ID
					parent_id, _ = self.tool.StringProcessor().find_substrings(
						text=comment_id,
						candidates=violations,
					)

					# 执行举报
					if self.report_work(
						source=cast("Literal['forum', 'work', 'shop']", source_map[source_type]),
						target_id=int(comment_id),
						source_id=source_id,
						reason_id=7,
						reason_content=reason_content,
						parent_id=cast("int", parent_id),
						is_reply=is_reply,
					):
						report_counter += 1
						print(f"举报成功: {violation}")
						break
					print(f"举报失败: {violation}")
					retries += 1

				except Exception as e:
					print(f"处理异常: {e}")
					retries += 1
					if retries >= max_retries:
						print(f"达到最大重试次数: {violation}")

		# 恢复原始账号
		self.whale_routine.set_token(self.acquire.token.judgement)

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
