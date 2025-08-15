from collections import defaultdict
from collections.abc import Callable, Generator, Iterator
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from json import loads
from pathlib import Path
from random import choice, randint
from time import sleep
from typing import Any, ClassVar, Literal, TypedDict, cast, overload
from urllib.parse import urlparse

from src.api import community, edu, forum, library, shop, user, whale, work
from src.utils import acquire, data, decorator, file, tool
from src.utils.acquire import HTTPSTATUS

# 常量定义
DOWNLOAD_DIR: Path = data.CURRENT_DIR / "download"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_SIZE_BYTES = 15 * 1024 * 1024  # 转换为字节
REPORT_BATCH_THRESHOLD = 15
VALID_REPLY_TYPES = {"WORK_COMMENT", "WORK_REPLY", "WORK_REPLY_REPLY", "POST_COMMENT", "POST_REPLY", "POST_REPLY_REPLY"}


class FormattedAnswer(TypedDict):
	question: str
	responses: list[str] | str


class ReplyType(Enum):
	WORK_COMMENT = "WORK_COMMENT"
	WORK_REPLY = "WORK_REPLY"
	WORK_REPLY_REPLY = "WORK_REPLY_REPLY"
	POST_COMMENT = "POST_COMMENT"
	POST_REPLY = "POST_REPLY"
	POST_REPLY_REPLY = "POST_REPLY_REPLY"


class ReportRecord(TypedDict):
	item: dict
	report_type: Literal["comment", "post", "discussion"]
	com_id: str
	content: str
	processed: bool
	action: str | None


@dataclass
class SourceConfig:
	get_items: Callable[..., Any]
	get_comments: Callable[..., Any]
	delete: Callable[..., Any]
	title_key: str


@decorator.singleton
class Union:
	# 初始化Union类
	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()  # 统一客户端属性命名
		self.cache = data.CacheManager().data
		self.community_login = community.AuthManager()
		self.community_motion = community.UserAction()
		self.community_obtain = community.DataFetcher()
		self.data = data.DataManager().data
		self.edu_motion = edu.UserAction()
		self.edu_obtain = edu.DataFetcher()
		self.file = file.CodeMaoFile()
		self.forum_motion = forum.ForumActionHandler()
		self.forum_obtain = forum.ForumDataFetcher()
		self.novel_obtain = library.NovelDataFetcher()
		self.novel_motion = library.NovelActionHandler()
		self.setting = data.SettingManager().data
		self.shop_motion = shop.WorkshopActionHandler()
		self.shop_obtain = shop.WorkshopDataFetcher()
		self.tool = tool
		self.upload_history = data.HistoryManger()
		self.user_motion = user.UserManager()
		self.user_obtain = user.UserDataFetcher()
		self.whale_motion = whale.ReportHandler()
		self.whale_obtain = whale.ReportFetcher()
		self.whale_routine = whale.AuthManager()
		self.work_motion = work.WorkManager()
		self.work_obtain = work.WorkDataFetcher()


ClassUnion = Union().__class__


@decorator.singleton
class Tool(ClassUnion):
	def __init__(self) -> None:
		super().__init__()
		self.cache_manager = data.CacheManager()

	def message_report(self, user_id: str) -> None:
		response = self.user_obtain.fetch_user_honors(user_id=user_id)
		timestamp = self.community_obtain.fetch_current_timestamp()["data"]
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
		if self.cache_manager.data:
			self.tool.DataAnalyzer().compare_datasets(
				before=self.cache_manager.data,
				after=user_data,
				metrics={
					"fans": "粉丝",
					"collected": "被收藏",
					"liked": "被赞",
					"view": "被预览",
				},
				timestamp_field="timestamp",
			)
		self.cache_manager.update(user_data)

	def guess_phone_num(self, phone_num: str) -> int | None:
		for i in range(10000):
			guess = f"{i:04d}"
			test_string = int(phone_num.replace("****", guess))
			if self.user_motion.validate_phone_number(test_string):  # 优化方法名:verify→validate
				return test_string
		return None


@decorator.singleton
class CommentProcessor:
	"""评论处理核心类,支持内置处理逻辑和自定义扩展"""

	def __init__(self) -> None:
		# 注册处理策略:action_type -> 处理函数
		self._process_strategies: dict[str, Callable] = {"ads": self._process_ads, "blacklist": self._process_blacklist, "duplicates": self._process_duplicates}

	def process_item(
		self,
		item: dict[str, Any],
		config: ...,  # 实际使用时应替换为SourceConfig类型
		action_type: str,
		params: dict[str, Any],
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

	# ========================== 辅助方法 ==========================
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
class Index(ClassUnion):
	COLOR_DATA = "\033[38;5;228m"
	COLOR_LINK = "\033[4;38;5;183m"
	COLOR_RESET = "\033[0m"
	COLOR_SLOGAN = "\033[38;5;80m"
	COLOR_TITLE = "\033[38;5;75m"
	COLOR_VERSION = "\033[38;5;114m"

	def _print_title(self, title: str) -> None:
		print(f"\n{self.COLOR_TITLE}{'*' * 22} {title} {'*' * 22}{self.COLOR_RESET}")

	def _print_slogan(self) -> None:
		print(f"\n{self.COLOR_SLOGAN}{self.setting.PROGRAM.SLOGAN}{self.COLOR_RESET}")
		print(f"{self.COLOR_VERSION}版本号: {self.setting.PROGRAM.VERSION}{self.COLOR_RESET}")

	def _print_lyric(self) -> None:
		self._print_title("一言")
		lyric: str = self._client.send_request(endpoint="https://lty.vc/lyric", method="GET").text  # 统一客户端调用
		print(f"{self.COLOR_SLOGAN}{lyric}{self.COLOR_RESET}")

	def _print_announcements(self) -> None:
		self._print_title("公告")
		print(f"{self.COLOR_LINK}编程猫社区行为守则 https://shequ.codemao.cn/community/1619098{self.COLOR_RESET}")
		print(f"{self.COLOR_LINK}2025编程猫拜年祭活动 https://shequ.codemao.cn/community/1619855{self.COLOR_RESET}")

	def _print_user_data(self) -> None:
		self._print_title("数据")
		Tool().message_report(user_id=self.data.ACCOUNT_DATA.id)
		print(f"{self.COLOR_TITLE}{'*' * 50}{self.COLOR_RESET}\n")

	def index(self) -> None:
		self._print_slogan()
		# self._print_lyric()
		self._print_announcements()
		self._print_user_data()


@decorator.singleton
class Obtain(ClassUnion):
	def __init__(self) -> None:
		super().__init__()
		self.source_map: dict[str, tuple[Callable[..., Any], str, str]] = {
			"work": (self.work_obtain.fetch_work_comments_gen, "work_id", "reply_user"),  # 生成器后缀优化
			"post": (self.forum_obtain.fetch_post_replies_gen, "post_id", "user"),  # 生成器后缀优化
			"shop": (self.shop_obtain.fetch_workshop_discussions_gen, "shop_id", "reply_user"),  # 生成器后缀优化
		}
		self.math_utils = self.tool.MathUtils()
		self.data_processor = self.tool.DataProcessor()

	def get_new_replies(
		self,
		limit: int = 0,
		type_item: Literal["LIKE_FORK", "COMMENT_REPLY", "SYSTEM"] = "COMMENT_REPLY",
	) -> list[dict]:
		"""获取社区新回复
		Args:
			limit: 获取数量限制 (0表示获取全部新回复)
			type_item: 消息类型
		Returns:
			结构化回复数据列表
		"""
		try:
			message_data = self.community_obtain.fetch_message_count(method="web")
			total_replies = message_data[0].get("count", 0) if message_data else 0
		except Exception as e:
			print(f"获取消息计数失败: {e}")
			return []
		if total_replies == 0 and limit == 0:
			return []
		remaining = total_replies if limit == 0 else min(limit, total_replies)
		offset = 0
		replies = []
		while remaining > 0:
			current_limit = self.math_utils.clamp(remaining, 5, 200)
			try:
				response = self.community_obtain.fetch_replies(
					types=type_item,
					limit=current_limit,
					offset=offset,
				)
				batch = response.get("items", [])
				actual_count = min(len(batch), remaining)
				replies.extend(batch[:actual_count])
				remaining -= actual_count
				offset += current_limit
				if actual_count < current_limit:
					break
			except Exception as e:
				print(f"获取回复失败: {e}")
				break
		return replies

	@overload
	def get_comments_detail(
		self,
		com_id: int,
		source: Literal["work", "post", "shop"],
		method: Literal["user_id", "comment_id"],
		max_limit: int | None = 200,
	) -> list[str]: ...
	@overload
	def get_comments_detail(
		self,
		com_id: int,
		source: Literal["work", "post", "shop"],
		method: Literal["comments"],
		max_limit: int | None = 200,
	) -> list[dict]: ...
	@lru_cache  # noqa: B019
	def get_comments_detail(
		self,
		com_id: int,
		source: Literal["work", "post", "shop"],
		method: str = "user_id",
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
		if source not in self.source_map:
			msg = f"无效来源: {source}"
			raise ValueError(msg)
		method_func, id_key, user_field = self.source_map[source]
		comments = method_func(**{id_key: com_id, "limit": max_limit})
		reply_cache = {}

		def extract_reply_user(reply: dict) -> int:
			return reply[user_field]["id"]

		def generate_replies(comment: dict) -> Generator:
			if source == "post":
				# 缓存未命中时请求数据
				if comment["id"] not in reply_cache:
					reply_cache[comment["id"]] = list(self.forum_obtain.fetch_reply_comments_gen(reply_id=comment["id"], limit=None))  # 生成器后缀优化
				yield from reply_cache[comment["id"]]
			else:
				yield from comment.get("replies", {}).get("items", [])

		def process_user_id() -> list:
			user_ids = []
			for comment in comments:
				user_ids.append(comment["user"]["id"])
				user_ids.extend(extract_reply_user(reply) for reply in generate_replies(comment))
			return self.data_processor.deduplicate(user_ids)

		def process_comment_id() -> list:
			comment_ids = []
			for comment in comments:
				comment_ids.append(str(comment["id"]))
				comment_ids.extend(f"{comment['id']}.{reply['id']}" for reply in generate_replies(comment))
			return self.data_processor.deduplicate(comment_ids)

		def process_detailed() -> list[dict]:
			return [
				{
					"user_id": item["user"]["id"],
					"nickname": item["user"]["nickname"],
					**{k: item[k] for k in ("id", "content", "created_at")},
					"is_top": item.get("is_top", False),
					"replies": [
						{
							"id": reply["id"],
							"content": reply["content"],
							"created_at": reply["created_at"],
							"user_id": extract_reply_user(reply),
							"nickname": reply[user_field]["nickname"],
						}
						for reply in generate_replies(item)
					],
				}
				for item in comments
			]

		method_handlers = {
			"user_id": process_user_id,
			"comment_id": process_comment_id,
			"comments": process_detailed,
		}
		if method not in method_handlers:
			msg = f"无效方法: {method}"
			raise ValueError(msg)
		return method_handlers[method]()

	def integrate_work_data(self, limit: int) -> Generator[dict[str, Any]]:
		per_source_limit = limit // 2
		data_sources = [
			(self.work_obtain.fetch_new_works_nemo(types="original", limit=per_source_limit), "nemo"),
			(self.work_obtain.fetch_new_works_web(limit=per_source_limit), "web"),
		]
		field_mapping = {
			"nemo": {"work_id": "work_id", "work_name": "work_name", "user_name": "user_name", "user_id": "user_id", "like_count": "like_count", "updated_at": "updated_at"},
			"web": {"work_id": "work_id", "work_name": "work_name", "user_name": "nickname", "user_id": "user_id", "like_count": "likes_count", "updated_at": "updated_at"},
		}
		for source_data, source in data_sources:
			if not isinstance(source_data, dict) or "items" not in source_data:
				continue
			mapping = field_mapping[source]
			for item in source_data["items"]:
				yield {target: item.get(source_field) for target, source_field in mapping.items()}

	def switch_edu_account(self, limit: int | None, return_method: Literal["generator", "list"] = "generator") -> Iterator[Any] | list[Any]:
		"""
		获取教育账号信息,可选择返回生成器或列表

		:param limit: 要获取的账号数量限制s
		:param return_method: 返回方式,"generator"返回生成器,"list"返回列表
		:return: 账号生成器或列表,每个元素为(username, password)元组
		"""
		try:
			# 获取学生列表
			students = list(self.edu_obtain.fetch_class_students_gen(limit=limit))

			if not students:
				print("没有可用的教育账号")
				return iter([]) if return_method == "generator" else []

			# 定义处理函数
			def process_student(student: dict) -> tuple[Any, Any]:
				self._client.switch_account(token=self._client.token.average, identity="average")
				return (student["username"], self.edu_motion.reset_student_password(student["id"])["password"])

			# 根据返回方式处理
			if return_method == "generator":

				def account_generator() -> Generator[tuple[Any, Any], Any]:
					students_copy = students.copy()  # 避免修改原列表
					while students_copy:
						student = students_copy.pop(randint(0, len(students_copy) - 1))
						yield process_student(student)

				return account_generator()

			if return_method == "list":
				result = []
				students_copy = students.copy()  # 避免修改原列表
				while students_copy:
					student = students_copy.pop(randint(0, len(students_copy) - 1))
					result.append(process_student(student))
				return result

			msg = f"不支持的返回方式: {return_method}"
			raise ValueError(msg)  # noqa: TRY301

		except Exception as e:
			print(f"获取教育账号失败: {e}")
			return iter([]) if return_method == "generator" else []

	def process_edu_accounts(self, limit: int | None = None, action: Callable[[], Any] | None = None) -> None:
		"""
		处理教育账号的切换、登录和执行操作

		:param limit: 要处理的账号数量限制
		:param action: 登录成功后执行的回调函数
		"""
		try:
			self._client.switch_account(token=self._client.token.average, identity="average")
			accounts = self.switch_edu_account(limit=limit, return_method="list")
			for identity, password in accounts:
				print("切换教育账号")
				sleep(3)
				self.community_login.authenticate_with_password(identity=identity, password=password, status="edu")
				if action:
					action()
		except Exception as e:
			print(f"教育账号处理失败: {e}")
		finally:
			self._client.switch_account(token=self._client.token.average, identity="average")


@decorator.singleton
class Motion(ClassUnion):
	SOURCE_CONFIG: ClassVar[dict[str, SourceConfig]] = {
		"work": SourceConfig(
			get_items=lambda self=None: self.user_obtain.fetch_user_works_web_gen(self.data.ACCOUNT_DATA.id, limit=None),  # 生成器后缀优化
			get_comments=lambda _self, _id: Obtain().get_comments_detail(_id, "work", "comments"),
			delete=lambda self, _item_id, comment_id, is_reply: self.work_motion.delete_comment(
				comment_id,
				"comments" if is_reply else "replies",
			),
			title_key="work_name",
		),
		"post": SourceConfig(
			get_items=lambda self=None: self.forum_obtain.fetch_my_posts_gen("created", limit=None),  # 生成器后缀优化
			get_comments=lambda _self, _id: Obtain().get_comments_detail(_id, "post", "comments"),
			delete=lambda self, _item_id, comment_id, is_reply: self.forum_motion.delete_item(
				comment_id,
				"comments" if is_reply else "replies",
			),
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
		params = {
			"ads": self.data.USER_DATA.ads,
			"blacklist": self.data.USER_DATA.black_room,
			"spam_max": self.setting.PARAMETER.spam_del_max,
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
				current_counts = self.community_obtain.fetch_message_count(method)
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
		self.work_motion.execute_toggle_follow(user_id=int(user_id))  # 优化方法名:manage→execute_toggle
		for item in works_list:
			item["id"] = cast("int", item["id"])
			self.work_motion.execute_toggle_like(work_id=item["id"])  # 优化方法名:manage→execute_toggle
			self.work_motion.execute_toggle_collection(work_id=item["id"])  # 优化方法名:manage→execute_toggle

	def like_my_novel(self, novel_list: list[dict]) -> None:
		for item in novel_list:
			item["id"] = cast("int", item["id"])
			self.novel_motion.execute_toggle_novel_favorite(item["id"])

	def execute_auto_reply_work(self) -> bool:  # 优化方法名:添加execute_前缀  # noqa: PLR0914
		"""自动回复作品/帖子评论"""
		formatted_answers = {
			k: v.format(**self.data.INFO) if isinstance(v, str) else [i.format(**self.data.INFO) for i in v] for answer in self.data.USER_DATA.answers for k, v in answer.items()
		}
		formatted_replies = [r.format(**self.data.INFO) for r in self.data.USER_DATA.replies]
		valid_types = list(VALID_REPLY_TYPES)  # 将set转为list
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
					found = self.tool.StringProcessor().find_substrings(
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
				(self.work_motion.create_comment_reply if source_type == "work" else self.forum_motion.create_comment_reply)(
					**params  # pyright: ignore[reportArgumentType]
				)  # 优化方法名:reply_to_comment→create_comment_reply
				print(f"已发送回复到{source_type},评论ID: {comment_id}")
			except Exception as e:
				print(f"回复处理失败: {e}")
				continue
		return True

	# 工作室常驻置顶
	def execute_maintain_top(self, method: Literal["shop", "novel"]) -> None:  # 优化方法名:添加execute_前缀
		if method == "shop":
			detail = self.shop_obtain.fetch_workshop_details_list()
			description = self.shop_obtain.fetch_workshop_details(detail["work_subject_id"])["description"]
			self.shop_motion.update_workshop_details(
				description=description,
				workshop_id=detail["id"],
				name=detail["name"],
				preview_url=detail["preview_url"],
			)
		elif method == "novel":
			novel_list = self.novel_obtain.fetch_my_novels()
			for item in novel_list:
				novel_id = item["id"]
				novel_detail = self.novel_obtain.fetch_novel_details(novel_id=novel_id)
				single_chapter_id = novel_detail["data"]["sectionList"][0]["id"]
				self.novel_motion.publish_chapter(single_chapter_id)

	# 查看账户状态
	def get_account_status(self) -> str:
		status = self.user_obtain.fetch_account_details()
		return f"禁言状态{status['voice_forbidden']}, 签订友好条约{status['has_signed']}"

	def execute_chiaroscuro_chronicles(self, user_id: int | None, method: Literal["work", "novel"], custom_list: list | None = None) -> None:  # 优化方法名:添加execute_前缀
		if custom_list:
			target_list = custom_list
		elif method == "work":
			target_list = list(self.user_obtain.fetch_user_works_web_gen(str(user_id), limit=None))  # 生成器后缀优化
		elif method == "novel":
			target_list = self.novel_obtain.fetch_my_novels()
		else:
			msg = f"不支持的{method}"
			raise TypeError(msg)

		def action() -> None:
			if method == "work":
				self.like_all_work(user_id=str(user_id), works_list=target_list)
			else:
				self.like_my_novel(novel_list=target_list)

		Obtain().process_edu_accounts(limit=None, action=action())

	def execute_celestial_maiden_chronicles(self, real_name: str) -> None:  # 优化方法名:添加execute_前缀
		# grade:1 幼儿园 2 小学 3 初中 4 高中 5 中职 6 高职 7 高校 99 其他
		generator = tool.EduDataGenerator()
		self.edu_motion.execute_upgrade_to_teacher(
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

	def execute_batch_handle_account(self, method: Literal["create", "delete"], limit: int | None = 100) -> None:  # 优化方法名:添加execute_前缀
		"""批量处理教育账号"""

		def _create_students(student_limit: int) -> None:
			"""创建学生账号内部逻辑"""
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
				edu.UserAction().add_students_to_class(name=batch_names, class_id=class_id)
				print("添加学生ing")

		def _delete_students(delete_limit: int | None) -> None:
			"""删除学生账号内部逻辑"""
			students = self.edu_obtain.fetch_class_students_gen(limit=delete_limit)  # 生成器后缀优化
			for student in students:
				self.edu_motion.delete_student_from_class(stu_id=student["id"])

		if method == "delete":
			_delete_students(limit)
		elif method == "create":
			actual_limit = limit or 100
			_create_students(actual_limit)

	def execute_chalky_brook(self, work_id: int) -> None:
		hidden_border = 10
		Obtain().process_edu_accounts(limit=hidden_border, action=lambda: self.work_motion.execute_report_work(describe="", reason="违法违规", work_id=work_id))

	def execute_nanmuona(self, target_id: int, content: str, source: Literal["work", "shop", "post"]) -> None:  # cSpell: ignore nanmuona
		if source == "post":
			self.forum_motion.create_post_reply(post_id=target_id, content=content)
		elif source == "shop":
			self.shop_motion.create_comment(workshop_id=target_id, content=content, rich_content=content)
		elif source == "work":
			self.work_motion.create_work_comment(work_id=target_id, comment=content)
		else:
			msg = f"不支持的源 {source}"
			raise TypeError(msg)

	def execute_download_fiction(self, fiction_id: int) -> None:  # 优化方法名:添加execute_前缀
		details = self.novel_obtain.fetch_novel_details(fiction_id)
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
			content = self.novel_obtain.fetch_chapter_details(chapter_id=section_id)["data"]["section"]["content"]
			formatted_content = self.tool.DataConverter().html_to_text(content, merge_empty_lines=True)
			self.file.file_write(path=section_path, content=formatted_content)

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
			return self._handle_file_upload(file_path=file_path, save_path=save_path, method=method, uploader=uploader)
		if file_path.is_dir():
			return self._handle_directory_upload(dir_path=file_path, save_path=save_path, method=method, uploader=uploader, recursive=recursive)
		return None

	def _handle_file_upload(self, file_path: Path, save_path: str, method: Literal["pgaot", "codemao", "codegame"], uploader: acquire.FileUploader) -> str | None:
		"""处理单个文件的上传流程"""
		file_size = file_path.stat().st_size
		if file_size > MAX_SIZE_BYTES:
			size_mb = file_size / 1024 / 1024
			print(f"警告: 文件 {file_path.name} 大小 {size_mb:.2f}MB 超过 15MB 限制,跳过上传")
			return None
		# 使用重构后的统一上传接口
		url = uploader.upload(file_path=file_path, method=method, save_path=save_path)
		file_size_human = self.tool.DataConverter().bytes_to_human(file_size)
		history = data.UploadHistory(file_name=file_path.name, file_size=file_size_human, method=method, save_url=url, upload_time=self.tool.TimeUtils().current_timestamp())
		self.upload_history.data.history.append(history)
		self.upload_history.save()
		return url

	def _handle_directory_upload(
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
					file_size_human = self.tool.DataConverter().bytes_to_human(file_size)
					history = data.UploadHistory(
						file_name=str(relative_path), file_size=file_size_human, method=method, save_url=url, upload_time=self.tool.TimeUtils().current_timestamp()
					)
					self.upload_history.data.history.append(history)
					results[str(child_file)] = url
				except Exception as e:
					results[str(child_file)] = None
					print(f"上传 {child_file} 失败: {e}")
		# 保存历史记录
		self.upload_history.save()
		return results

	def print_upload_history(self, limit: int = 10, *, reverse: bool = True) -> None:
		"""
		打印上传历史记录(支持分页、详细查看和链接验证)
		Args:
			limit: 每页显示记录数(默认10条)
			reverse: 是否按时间倒序显示(最新的在前)
		"""
		history_list = self.upload_history.data.history
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
				upload_time = self.tool.TimeUtils().format_timestamp(upload_time)
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
			upload_time = self.tool.TimeUtils().format_timestamp(upload_time)
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

	def collect_work_comments(self, limit: int) -> dict[str, list[str]]:
		works = Obtain().integrate_work_data(limit=limit)
		comments = []
		for single_work in works:
			work_comments = Obtain().get_comments_detail(com_id=single_work["work_id"], source="work", method="comments", max_limit=20)
			comments.extend(work_comments)
		filtered_comments = self.tool.DataProcessor().filter_data(data=comments, include=["user_id", "content"])
		filtered_comments = cast("list[dict]", filtered_comments)
		user_comments = {}
		for comment in filtered_comments:
			user_id = comment.get("user_id")
			content = comment.get("content")
			if user_id is None or content is None:
				continue
			user_id_str = str(user_id)
			user_comments.setdefault(user_id_str, []).append(content)
		return user_comments


class ReportHandler(ClassUnion):
	"""举报处理核心类,封装举报处理全流程"""

	def __init__(self) -> None:
		super().__init__()
		# 状态变量
		self.student_accounts: list[tuple[str, str]] = []
		self.processed_count = 0
		# 批量处理配置
		self.batch_config = {
			"total_threshold": 15,
			"duplicate_threshold": 5,
			"content_threshold": 3,
		}

	def execute_judgement_login(self) -> None:  # 优化方法名:添加execute_前缀
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
			captcha, _cookies = input_captcha(timestamp=timestamp)
			while True:
				# self._client.update_cookies(cookies)  # 统一客户端调用
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
					captcha, _cookies = input_captcha(timestamp=timestamp)

	def execute_handle_report(self, admin_id: int) -> None:
		"""执行举报处理主流程"""
		# 加载学生账号(用于自动举报)
		self._load_student_accounts()
		# 主处理循环
		while True:
			# 获取所有待处理举报
			all_records = self._fetch_all_reports()
			if not all_records:
				print("\n当前没有待处理的举报")
				break
			print(f"\n===== 发现 {len(all_records)} 条待处理举报 =====")
			batch_processed = self.process_report_batch(all_records, admin_id)
			self.processed_count += batch_processed
			print(f"\n本次处理完成: {batch_processed} 条举报")
			if input("\n是否继续检查新举报? (Y/N) ").upper() != "Y":
				break
			print("\n重新获取新举报...")
		print(f"\n{'=' * 50}")
		print(f"本次会话共处理 {self.processed_count} 条举报")
		print(f"{'=' * 50}")
		self._client.switch_account(token=self._client.token.judgement, identity="judgement")
		print("已恢复原始账号状态")

	def _load_student_accounts(self) -> None:
		"""加载学生账号用于自动举报"""
		self._client.switch_account(token=self._client.token.average, identity="average")
		if input("是否加载学生账号用于自动举报? (Y/N) ").upper() == "Y":
			try:
				self.student_accounts = list(Obtain().switch_edu_account(limit=50))
				print(f"已加载 {len(self.student_accounts)} 个学生账号")
			except Exception as e:
				print(f"加载学生账号失败: {e}")
				self.student_accounts = []
		else:
			print("未加载学生账号,自动举报功能不可用")
		self._client.switch_account(token=self._client.token.judgement, identity="judgement")

	def _fetch_all_reports(self) -> list[ReportRecord]:
		"""获取所有类型的待处理举报"""
		all_records: list[ReportRecord] = []
		sources: list[tuple[Literal["comment", "post", "discussion"], Generator]] = [
			("comment", self.whale_obtain.fetch_comment_reports_gen(source_type="ALL", status="TOBEDONE", limit=2000)),
			("post", self.whale_obtain.fetch_post_reports_gen(status="TOBEDONE", limit=2000)),
			("discussion", self.whale_obtain.fetch_discussion_reports_gen(status="TOBEDONE", limit=2000)),
		]
		for report_type, report_gen in sources:
			for item in report_gen:
				cfg = self.get_type_config(report_type, item)
				all_records.append(
					{
						"item": item,
						"report_type": report_type,
						"com_id": str(item[cfg["com_id"]]),
						"content": item[cfg["content_field"]],
						"processed": False,
						"action": None,
					}
				)
		return all_records

	@staticmethod
	def get_type_config(report_type: str, current_item: dict) -> dict:
		"""动态生成不同举报类型的配置"""
		return {
			"comment": {
				"content_field": "comment_content",
				"user_field": "comment_user",
				"handle_method": "execute_process_comment_report",
				"source_id_field": "comment_source_object_id",
				"source_name_field": "comment_source_object_name",
				"special_check": lambda: current_item.get("comment_source") == "WORK_SHOP",
				"com_id": "comment_id",
			},
			"post": {
				"content_field": "post_title",
				"user_field": "post_user",
				"handle_method": "execute_process_post_report",
				"source_id_field": "post_id",
				"special_check": lambda: True,
				"com_id": "post_id",
			},
			"discussion": {
				"content_field": "discussion_content",
				"user_field": "discussion_user",
				"handle_method": "execute_process_discussion_report",
				"source_id_field": "post_id",
				"special_check": lambda: True,
				"com_id": "discussion_id",
			},
		}[report_type]

	def get_content_key(self, record: ReportRecord) -> tuple:
		"""获取内容唯一标识键"""
		cfg = self.get_type_config(record["report_type"], record["item"])
		return (
			record["item"][cfg["content_field"]],
			record["report_type"],
			record["item"][cfg["source_id_field"]],
		)

	def process_report_batch(self, records: list[ReportRecord], admin_id: int) -> int:  # noqa: PLR0912
		"""智能批量处理核心逻辑"""
		processed = 0
		id_map = defaultdict(list)
		content_map = defaultdict(list)
		# 构建ID分组和内容分组
		for record in records:
			id_map[record["com_id"]].append(record)
			content_key = self.get_content_key(record)
			content_map[content_key].append(record)
		# 合并批量处理组
		batch_groups = [("ID", items[0]["com_id"], items) for items in id_map.values() if len(items) >= self.batch_config["duplicate_threshold"]]
		for (content, report_type, _), items in content_map.items():
			if len(items) >= self.batch_config["content_threshold"]:
				batch_groups.append(("内容", f"{report_type}:{content[:20]}...", items))
		# 批量处理逻辑
		if batch_groups and len(records) >= self.batch_config["total_threshold"]:
			print("\n发现以下批量处理项:")
			for i, (g_type, g_key, items) in enumerate(batch_groups, 1):
				print(f"{i}. [{g_type}] {g_key} ({len(items)}次举报)")
			if input("\n是否查看详情?(Y/N) ").upper() == "Y":
				for g_type, g_key, items in batch_groups:
					print(f"\n=== {g_type}组: {g_key} ===")
					for item in items[:3]:  # 展示前3条
						print(f"举报ID: {item['item']['id']} | 时间: {self.tool.TimeUtils().format_timestamp(item['item']['created_at'])}")
					if len(items) > self.batch_config["content_threshold"]:
						print(f"...及其他{len(items) - 3}条举报")
			if input("\n确认批量处理这些项目?(Y/N) ").upper() == "Y":
				for g_type, g_key, items in batch_groups:
					print(f"\n正在处理 [{g_type}] {g_key}...")
					first_action = None
					# 处理首个项目
					if not items[0]["processed"]:
						first_action = self.process_single_item(items[0], admin_id, batch_mode=True)
					# 自动应用操作到同组项目
					if first_action:
						for item in items[1:]:
							if not item["processed"]:
								self.apply_action(item, first_action, admin_id)
								print(f"已自动处理举报ID: {item['item']['id']}")
		# 处理剩余未处理项目
		for record in records:
			if not record["processed"]:
				self.process_single_item(record, admin_id)
				processed += 1
		return processed

	def process_single_item(self, record: ReportRecord, admin_id: int, *, batch_mode: bool = False) -> str | None:
		"""处理单个举报项目"""
		item = data.NestedDefaultDict(record["item"])
		report_type = record["report_type"]
		cfg = self.get_type_config(report_type, item.to_dict())
		if batch_mode:
			print(f"\n{'=' * 30} 批量处理首个项目 {'=' * 30}")
		print(f"\n{'=' * 50}")
		print(f"举报ID: {item['id']}")
		print(f"举报类型 {report_type}")
		print(f"举报内容: {self.tool.DataConverter().html_to_text(item[cfg['content_field']])}")
		print(f"所属板块: {item.get('board_name', item.get(cfg.get('source_name_field', ''), ''))}")
		# 显示被举报人信息
		cfg_user_field = cfg["user_field"]
		if report_type == "post":
			print(f"被举报人: {item[f'{cfg_user_field}_nick_name']}")
		else:
			print(f"被举报人: {item[f'{cfg_user_field}_nickname']}")
		print(f"举报原因: {item['reason_content']}")
		print(f"举报时间: {self.tool.TimeUtils().format_timestamp(item['created_at'])}")
		if report_type == "post":
			print(f"举报线索: {item['description']}")
		# 操作选择循环
		while True:
			choice = input("选择操作: D:删除, S:禁言7天, T:禁言3月 P:通过, C:查看, F:检查违规, J:跳过  ").upper()
			if choice in {"D", "S", "T", "P"}:
				status_map = {"D": "DELETE", "S": "MUTE_SEVEN_DAYS", "P": "PASS", "T": "MUTE_THREE_MONTHS"}
				handler = getattr(self.whale_motion, cfg["handle_method"])
				handler(report_id=item["id"], resolution=status_map[choice], admin_id=admin_id)
				record["processed"] = True
				return choice
			if choice == "C":
				self._show_details(item.to_dict(), report_type, cfg)
			elif choice == "F" and cfg["special_check"]():
				source_map: dict[Literal["comment", "post", "discussion"], Literal["work", "shop", "post", "discussion"]] = {
					"comment": "shop" if item.get("comment_source") == "WORK_SHOP" else "work",
					"post": "post",
					"discussion": "discussion",
				}
				self._check_report(
					source_id=item[cfg["source_id_field"]],
					source_type=source_map[report_type],
					title=item.get("board_name", item.get(cfg.get("source_name_field", ""), "")),
					user_id=item[f"{cfg['user_field']}_id"],
				)
			elif choice == "J":
				print("已跳过")
				return None
			else:
				print("无效输入")

	def apply_action(self, record: ReportRecord, action: str, admin_id: int) -> None:
		"""应用处理操作到举报项目"""
		cfg = self.get_type_config(record["report_type"], record["item"])
		handler = getattr(self.whale_motion, cfg["handle_method"])
		status_map = {"D": "DELETE", "S": "MUTE_SEVEN_DAYS", "P": "PASS", "T": "MUTE_THREE_MONTHS"}
		handler(
			report_id=record["item"]["id"],
			resolution=status_map[action],
			admin_id=admin_id,
		)
		record["processed"] = True

	def _show_details(self, item: dict, report_type: Literal["comment", "post", "discussion"], cfg: dict) -> None:
		"""显示举报项目详细信息"""
		if report_type == "comment":
			print(f"违规板块ID: https://shequ.codemao.cn/work_shop/{item[cfg['source_id_field']]}")
		elif report_type == "post":
			print(f"违规帖子ID: https://shequ.codemao.cn/community/{item[cfg['source_id_field']]}")
			print(f"\n{'=' * 30} 帖子内容 {'=' * 30}")
			post_id = item[cfg["source_id_field"]]
			content = self.forum_obtain.fetch_posts_details(post_ids=int(post_id))["items"][0]["content"]
			print(self.tool.DataConverter().html_to_text(content))
		elif report_type == "discussion":
			print(f"所属帖子标题: {item['post_title']}")
			print(f"所属帖子帖主ID: https://shequ.codemao.cn/user/{item['post_user_id']}")
			print(f"所属帖子ID: https://shequ.codemao.cn/community/{item[cfg['source_id_field']]}")
		# 显示违规用户信息
		cfg_user_field = cfg["user_field"]
		print(f"违规用户ID: https://shequ.codemao.cn/user/{item[f'{cfg_user_field}_id']}")
		# 显示发送时间
		if report_type in {"comment", "discussion"}:
			source = "shop" if report_type == "comment" else "post"
			comments = Obtain().get_comments_detail(com_id=item[cfg["source_id_field"]], source=source, method="comments", max_limit=200)
			if report_type == "comment" and item["comment_parent_id"] != "0":
				for comment in comments:
					if comment["id"] == item["comment_parent_id"]:
						for reply in comment["replies"]:
							if reply["id"] == item["comment_id"]:
								print(f"发送时间: {self.tool.TimeUtils().format_timestamp(reply['created_at'])}")
								break
						break
			else:
				found = False
				for comment in comments:
					if comment["id"] == item.get("comment_id"):
						print(f"发送时间: {self.tool.TimeUtils().format_timestamp(comment['created_at'])}")
						found = True
						break
				if not found:
					print("未找到 comment_id")
		else:
			details = self.forum_obtain.fetch_single_post_details(post_id=item[cfg["source_id_field"]])
			print(f"发送时间: {self.tool.TimeUtils().format_timestamp(details['created_at'])}")

	def _check_report(self, source_id: int, source_type: Literal["shop", "work", "discussion", "post"], title: str, user_id: int) -> None:
		"""检查举报内容"""
		if source_type in {"work", "discussion", "shop"}:
			adjusted_type = "post" if source_type == "discussion" else source_type
			# 分析违规评论
			violations = self._analyze_comments_violations(
				source_id=source_id,
				source_type=adjusted_type,
				title=title,
			)
			if not violations:
				print("没有违规评论")
				return
			# 处理举报请求
			self._process_report_requests(
				violations=violations,
				source_id=source_id,
				source_type=adjusted_type,
			)
		if source_type == "post":
			search_result = list(self.forum_obtain.search_posts_gen(title=title, limit=None))
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
		# 直接获取评论(保留原有逻辑:
		comments = Obtain().get_comments_detail(
			com_id=source_id,
			source=source_type,
			method="comments",
		)
		params = {
			"ads": self.data.USER_DATA.ads,
			"blacklist": self.data.USER_DATA.black_room,
			"spam_max": self.setting.PARAMETER.spam_del_max,
		}
		processor = CommentProcessor()

		class CommentConfig:
			title_key = "title"

			@staticmethod
			def get_comments(_processor_instance: ..., _item_id: int) -> list[dict]:
				return comments

		# 使用简单配置
		config = CommentConfig()
		# 收集异常评论(广告和黑名单:
		abnormal_targets = defaultdict(list)
		# 处理广告
		processor.process_item(
			item={"id": source_id, "title": title},  # 临时item对象
			config=config,
			action_type="ads",
			params=params,
			target_lists=abnormal_targets,
		)
		# 处理黑名单
		processor.process_item(item={"id": source_id, "title": title}, config=config, action_type="blacklist", params=params, target_lists=abnormal_targets)
		# 收集重复评论
		duplicate_targets = defaultdict(list)
		processor.process_item(item={"id": source_id, "title": title}, config=config, action_type="duplicates", params=params, target_lists=duplicate_targets)
		return abnormal_targets["ads"] + abnormal_targets["blacklist"] + duplicate_targets["duplicates"]

	def _process_report_requests(
		self,
		violations: list[str],
		source_id: int,
		source_type: Literal["post", "work", "shop"],
	) -> None:
		"""处理举报请求核心逻辑"""
		if not self.student_accounts:
			print("未加载学生账号,无法执行自动举报")
			return
		if input("是否自动举报违规评论? (Y/N) ").upper() != "Y":
			print("操作已取消")
			return
		# 账号处理逻辑
		available_accounts = self.student_accounts.copy()
		current_account = None
		report_counter = -1
		reason_content = self.community_obtain.fetch_report_reasons()["items"][7]["content"]
		source_map: dict[Literal["work", "post", "shop"], Literal["work", "forum", "shop"]] = {"work": "work", "post": "forum", "shop": "shop"}
		print(f"\n开始自动举报 ({len(violations)} 条违规内容)")
		for i, violation in enumerate(violations, 1):
			# 账号切换逻辑
			if report_counter >= self.setting.PARAMETER.report_work_max or report_counter == -1:
				if not available_accounts:
					print("所有可用学生账号均已尝试")
					break
				# 随机选择账号
				current_account = available_accounts.pop(randint(0, len(available_accounts) - 1))
				print(f"\n切换教育账号: {current_account[0]}")
				sleep(2)
				try:
					self.community_login.authenticate_with_token(
						identity=current_account[0],
						password=current_account[1],
						status="edu",
					)
					report_counter = 0
				except Exception as e:
					print(f"账号登录失败: {e}")
					continue
			# 解析违规内容并执行举报
			parts = violation.split(":")
			_item_id, comment_id = parts[0].split(".")
			is_reply = "reply" in violation
			parent_id, _ = self.tool.StringProcessor().find_substrings(
				text=comment_id,
				candidates=violations,
			)
			try:
				source_key = source_map[source_type]
				if self.execute_report_work(
					source=source_key,
					target_id=int(comment_id),
					source_id=source_id,
					reason_id=7,
					reason_content=reason_content,
					parent_id=parent_id,
					is_reply=is_reply,
				):
					report_counter += 1
					print(f"[{i}/{len(violations)}] 举报成功: {violation}")
				else:
					print(f"[{i}/{len(violations)}] 举报失败: {violation}")
					report_counter += 1
			except Exception as e:
				print(f"处理异常: {e}")
		self._client.switch_account(token=self._client.token.judgement, identity="judgement")
		print("\n自动举报完成,已恢复原始账号状态")

	def execute_report_work(
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
		"""执行举报操作"""
		match source:
			case "work":
				return self.work_motion.execute_report_comment(work_id=target_id, comment_id=source_id, reason=reason_content)
			case "forum":
				source_ = "COMMENT" if is_reply else "REPLY"
				return self.forum_motion.report_item(item_id=target_id, reason_id=reason_id, description=description, item_type=source_, return_data=False)
			case "shop":
				if is_reply and parent_id is not None:
					return self.shop_motion.execute_report_comment(
						comment_id=target_id,
						reason_content=reason_content,
						reason_id=reason_id,
						reporter_id=int(self.data.ACCOUNT_DATA.id),
						comment_parent_id=parent_id,
						description=description,
					)
				return self.shop_motion.execute_report_comment(
					comment_id=target_id,
					reason_content=reason_content,
					reason_id=reason_id,
					reporter_id=int(self.data.ACCOUNT_DATA.id),
					description=description,
				)
