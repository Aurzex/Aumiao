import operator
from collections.abc import Callable, Generator, Iterator
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from random import randint
from time import sleep
from typing import Any, Literal, cast, overload

from aumiao.core.base import ClassUnion
from aumiao.utils import decorator


class QuerySource(Enum):
	"""查询来源枚举"""

	WORK = "work"
	POST = "post"
	SHOP = "shop"


class QueryMethod(Enum):
	"""查询方法枚举"""

	USER_ID = "user_id"
	COMMENT_ID = "comment_id"
	COMMENTS = "comments"


@dataclass
class QueryParams:
	"""查询参数封装类"""

	source: QuerySource
	id: int
	method: QueryMethod = QueryMethod.USER_ID
	limit: int | None = 500
	type_item: str = "COMMENT_REPLY"


class QueryBuilder:
	"""查询构建器"""

	def __init__(self, obtain_instance: "Obtain") -> None:
		self.obtain = obtain_instance
		self.params = QueryParams(source=QuerySource.WORK, id=0, method=QueryMethod.USER_ID, limit=500)

	def from_source(self, source: Literal["work", "post", "shop"]) -> "QueryBuilder":
		"""设置查询来源"""
		self.params.source = QuerySource(source)
		return self

	def with_id(self, com_id: int) -> "QueryBuilder":
		"""设置查询 ID"""
		self.params.id = com_id
		return self

	def using_method(self, method: str) -> "QueryBuilder":
		"""设置查询方法"""
		self.params.method = QueryMethod(method)
		return self

	def with_limit(self, limit: int | None) -> "QueryBuilder":
		"""设置查询限制"""
		self.params.limit = limit
		return self

	def execute(self) -> Any:
		"""执行查询"""
		return self.obtain.execute_query(self.params)


class QueryManager:
	"""查询管理器"""

	def __init__(self, obtain_instance: "Obtain") -> None:
		self.obtain = obtain_instance

	def create_builder(self) -> QueryBuilder:
		"""创建查询构建器"""
		return QueryBuilder(self.obtain)


def query_method(method_name: str) -> ...:
	"""查询方法装饰器, 用于简化 API 调用"""

	def decorator_func(func: ...) -> ...:
		@wraps(func)
		def wrapper(self: ..., *args: ..., **kwargs: ...) -> ...:
			if kwargs:
				return func(self, *args, **kwargs)
			if method_name == "comments_detail":
				builder = self.query_manager.create_builder()
				arg_names = ["com_id", "source", "method", "max_limit"]
				args_dict = {}
				for i, arg in enumerate(args):
					if i < len(arg_names):
						args_dict[arg_names[i]] = arg
				if "max_limit" not in args_dict:
					args_dict["max_limit"] = 500
				# 调用查询构建器
				return builder.from_source(args_dict["source"]).with_id(args_dict["com_id"]).using_method(args_dict["method"]).with_limit(args_dict["max_limit"]).execute()
			return func(self, *args, **kwargs)

		return wrapper

	return decorator_func


@decorator.singleton
class Obtain(ClassUnion):  # ty:ignore [unsupported-base]
	def __init__(self) -> None:
		super().__init__()
		self._source_map = {
			"work": (self.work_obtain.fetch_work_comments_gen, "work_id", "reply_user"),
			"post": (self.forum_obtain.fetch_post_replies_gen, "post_id", "user"),
			"shop": (self.shop_obtain.fetch_workshop_discussions_gen, "shop_id", "reply_user"),
		}
		self._data_processor = self.toolkit.create_data_processor()
		self.query_manager = QueryManager(self)

	def get_new_replies(
		self,
		limit: int = 0,
		type_item: Literal["LIKE_FORK", "COMMENT_REPLY", "SYSTEM"] = "COMMENT_REPLY",
	) -> list[dict]:
		"""获取社区新回复"""
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
			current_limit = max(5, min(remaining, 200))
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

	# 保持原有重载接口
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
	@query_method("comments_detail")
	def get_comments_detail(
		self,
		com_id: int,
		source: Literal["work", "post", "shop"],
		method: str = "user_id",
		max_limit: int | None = 500,
	) -> list[dict] | list[str]:
		"""获取结构化评论数据 (兼容原有接口)"""
		return self.execute_query(QueryParams(source=QuerySource(source), id=com_id, method=QueryMethod(method), limit=max_limit))

	def execute_query(self, params: QueryParams) -> Any:
		"""执行查询的核心逻辑"""
		source_value = params.source.value
		if source_value not in self._source_map:
			msg = f"无效来源: {source_value}"
			raise ValueError(msg)
		method_func, id_key, user_field = self._source_map[source_value]
		comments = method_func(**{id_key: cast("int", params.id), "limit": cast("int", params.limit)})  # pyright: ignore [reportArgumentType] # ty:ignore [redundant-cast]
		reply_cache = {}

		def extract_reply_user(reply: dict) -> int:
			return reply[user_field]["id"]

		def generate_replies(comment: dict) -> Generator:
			if source_value == "post":
				if comment["id"] not in reply_cache:
					reply_cache[comment["id"]] = list(self.forum_obtain.fetch_reply_comments_gen(reply_id=comment["id"], limit=None))
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
			QueryMethod.USER_ID: process_user_id,
			QueryMethod.COMMENT_ID: process_comment_id,
			QueryMethod.COMMENTS: process_detailed,
		}
		if params.method not in method_handlers:
			msg = f"无效方法: {params.method}"
			raise ValueError(msg)
		return method_handlers[params.method]()

	# 新增: 使用查询构建器的 API
	def query(self) -> QueryBuilder:
		"""创建查询构建器"""
		return QueryBuilder(self)

	# 保持其他方法不变
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

	def collect_work_comments(self, limit: int) -> list[dict]:
		# 使用查询构建器重写
		works = self.integrate_work_data(limit=limit)
		comments = []
		for single_work in works:
			work_comments = self.query().from_source("work").with_id(single_work["work_id"]).using_method("comments").with_limit(20).execute()
			comments.extend(work_comments)
		filtered_comments = self._data_processor.filter_fields(data=comments, include=["user_id", "content", "nickname"])
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
		result = list(user_comments_map.values())
		result.sort(key=operator.itemgetter("comment_count"), reverse=True)
		return result

	@overload
	def switch_edu_account(self, limit: int | None, return_method: Literal["generator"]) -> Iterator[tuple]: ...
	@overload
	def switch_edu_account(self, limit: int | None, return_method: Literal["list"]) -> list[tuple]: ...
	def switch_edu_account(self, limit: int | None, return_method: Literal["generator", "list"]) -> Iterator[tuple] | list[tuple]:
		"""获取教育账号信息"""
		try:
			students = list(self.edu_obtain.fetch_class_students_gen(limit=limit))
			if not students:
				print("没有可用的教育账号")
				return iter([]) if return_method == "generator" else []
			self.client.switch_identity(token=self.client.token.average, identity="average")

			def process_student(student: dict) -> tuple[Any, Any]:
				return (student["username"], self.edu_motion.reset_student_password(student["id"])["password"])

			if return_method == "generator":

				def account_generator() -> Generator[tuple[Any, Any], Any]:
					students_copy = students.copy()
					while students_copy:
						student = students_copy.pop(randint(0, len(students_copy) - 1))
						yield process_student(student)

				return account_generator()
			if return_method == "list":
				result = []
				students_copy = students.copy()
				while students_copy:
					student = students_copy.pop(randint(0, len(students_copy) - 1))
					result.append(process_student(student))
				return result
		except Exception as e:
			print(f"获取教育账号失败: {e}")
			return iter([]) if return_method == "generator" else []

	def process_edu_accounts(self, limit: int | None = None, action: Callable[[], Any] | None = None) -> None:
		"""处理教育账号的切换、登录和执行操作"""
		try:
			self.client.switch_identity(token=self.client.token.average, identity="average")
			accounts = self.switch_edu_account(limit=limit, return_method="list")
			for identity, password in accounts:
				print("切换教育账号")
				sleep(3)
				self.auth.login(identity=identity, password=password, status="edu", prefer_method="simple_password")
				if action:
					action()
		except Exception as e:
			print(f"教育账号处理失败: {e}")
		finally:
			self.client.switch_identity(token=self.client.token.average, identity="average")
