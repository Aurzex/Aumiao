import operator
from collections.abc import Callable, Generator, Iterator
from random import randint
from time import sleep
from typing import Any, Literal, cast, overload

from src.core.base import ClassUnion
from src.utils import decorator


@decorator.singleton
class Obtain(ClassUnion):
	def __init__(self) -> None:
		super().__init__()
		self._source_map = {
			"work": (self._work_obtain.fetch_work_comments_gen, "work_id", "reply_user"),
			"post": (self._forum_obtain.fetch_post_replies_gen, "post_id", "user"),
			"shop": (self._shop_obtain.fetch_workshop_discussions_gen, "shop_id", "reply_user"),
		}
		self._math_utils = self._tool.MathUtils()
		self._data_processor = self._tool.DataProcessor()

	def get_new_replies(
		self,
		limit: int = 0,
		type_item: Literal["LIKE_FORK", "COMMENT_REPLY", "SYSTEM"] = "COMMENT_REPLY",
	) -> list[dict]:
		"""获取社区新回复
		Args:
			limit: 获取数量限制 (0 表示获取全部新回复)
			type_item: 消息类型
		Returns:
			结构化回复数据列表
		"""
		try:
			message_data = self._community_obtain.fetch_message_count(method="web")
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
			current_limit = self._math_utils.clamp(remaining, 5, 200)
			try:
				response = self._community_obtain.fetch_replies(
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
		max_limit: int | None = 500,
	) -> list[str]: ...
	@overload
	def get_comments_detail(
		self,
		com_id: int,
		source: Literal["work", "post", "shop"],
		method: Literal["comments"],
		max_limit: int | None = 500,
	) -> list[dict]: ...
	@decorator.lru_cache_with_reset(max_calls=3)
	def get_comments_detail(
		self,
		com_id: int,
		source: Literal["work", "post", "shop"],
		method: str = "user_id",
		max_limit: int | None = 500,
	) -> list[dict] | list[str]:
		"""获取结构化评论数据
		Args:
			com_id: 目标主体 ID (作品 / 帖子 / 工作室 ID)
			source: 数据来源 work = 作品 post = 帖子 shop = 工作室
			method: 返回格式
				user_id -> 用户 ID 列表
				comment_id -> 评论 ID 列表
				comments -> 结构化评论数据
			max_limit: 最大获取数量
		Returns:
			根据 method 参数返回对应格式的数据
		"""
		if source not in self._source_map:
			msg = f"无效来源: {source}"
			raise ValueError(msg)
		method_func, id_key, user_field = self._source_map[source]
		comments = method_func(**{id_key: com_id, "limit": max_limit})  # pyright: ignore [reportArgumentType]
		reply_cache = {}

		def extract_reply_user(reply: dict) -> int:
			return reply[user_field]["id"]

		def generate_replies(comment: dict) -> Generator:
			if source == "post":
				# 缓存未命中时请求数据
				if comment["id"] not in reply_cache:
					reply_cache[comment["id"]] = list(self._forum_obtain.fetch_reply_comments_gen(reply_id=comment["id"], limit=None))  # 生成器后缀优化
				yield from reply_cache[comment["id"]]
			else:
				yield from comment.get("replies", {}).get("items", [])

		def process_user_id() -> list:
			user_ids = []
			for comment in comments:
				user_ids.append(comment["user"]["id"])
				user_ids.extend(extract_reply_user(reply) for reply in generate_replies(comment))
			return self._data_processor.deduplicate(user_ids)

		def process_comment_id() -> list:
			comment_ids = []
			for comment in comments:
				comment_ids.append(str(comment["id"]))
				comment_ids.extend(f"{comment['id']}.{reply['id']}" for reply in generate_replies(comment))
			return self._data_processor.deduplicate(comment_ids)

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
			(self._work_obtain.fetch_new_works_nemo(types="original", limit=per_source_limit), "nemo"),
			(self._work_obtain.fetch_new_works_web(limit=per_source_limit), "web"),
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

	def collect_work_comments(self, limit: int) -> list[dict]:
		works = Obtain().integrate_work_data(limit=limit)
		comments = []
		for single_work in works:
			work_comments = Obtain().get_comments_detail(com_id=single_work["work_id"], source="work", method="comments", max_limit=20)
			comments.extend(work_comments)
		filtered_comments = self._tool.DataProcessor().filter_data(data=comments, include=["user_id", "content", "nickname"])
		filtered_comments = cast("list [dict]", filtered_comments)
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

	@overload
	def switch_edu_account(self, limit: int | None, return_method: Literal["generator"]) -> Iterator[Any]: ...
	@overload
	def switch_edu_account(self, limit: int | None, return_method: Literal["list"]) -> list[Any]: ...
	def switch_edu_account(self, limit: int | None, return_method: Literal["generator", "list"]) -> Iterator[Any] | list[Any]:
		"""
		获取教育账号信息, 可选择返回生成器或列表
		:param limit: 要获取的账号数量限制
		:param return_method: 返回方式,"generator" 返回生成器,"list" 返回列表
		:return: 账号生成器或列表, 每个元素为 (username, password) 元组
		"""
		try:
			# 获取学生列表
			students = list(self._edu_obtain.fetch_class_students_gen(limit=limit))
			if not students:
				print("没有可用的教育账号")
				return iter([]) if return_method == "generator" else []
			# 定义处理函数
			self._client.switch_identity(token=self._client.token.average, identity="average")

			def process_student(student: dict) -> tuple[Any, Any]:
				return (student["username"], self._edu_motion.reset_student_password(student["id"])["password"])

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
			self._client.switch_identity(token=self._client.token.average, identity="average")
			accounts = self.switch_edu_account(limit=limit, return_method="list")
			for identity, password in accounts:
				print("切换教育账号")
				sleep(3)
				self._auth.login(identity=identity, password=password, status="edu", prefer_method="simple_password")
				if action:
					action()
		except Exception as e:
			print(f"教育账号处理失败: {e}")
		finally:
			self._client.switch_identity(token=self._client.token.average, identity="average")
