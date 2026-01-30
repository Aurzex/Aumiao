import operator
from collections.abc import Callable, Generator, Iterator
from dataclasses import dataclass
from enum import Enum
from random import randint
from time import sleep
from typing import Any, Literal, cast, overload

from aumiao.core.base import ClassUnion
from aumiao.utils import decorator


class QuerySource(Enum):
	"""查询来源枚举"""

	WORK = "work"
	FORUM = "forum"
	SHOP = "shop"


class QueryMethod(Enum):
	"""查询方法枚举"""

	USER_ID = "user_id"
	COMMENT_ID = "comment_id"
	COMMENTS = "comments"


@dataclass
class QueryOptions:
	"""查询选项"""

	method: QueryMethod = QueryMethod.USER_ID
	limit: int | None = 500


@decorator.singleton
class Obtain(ClassUnion):  # type: ignore [unsupported-base]
	def __init__(self) -> None:
		super().__init__()
		self._source_map = {
			"work": (self.work_obtain.fetch_work_comments_gen, "work_id", "reply_user"),
			"forum": (self.forum_obtain.fetch_post_replies_gen, "post_id", "user"),
			"shop": (self.shop_obtain.fetch_workshop_discussions_gen, "shop_id", "reply_user"),
		}
		self._data_processor = self.toolkit.create_data_processor()

	# ==================== 核心查询方法 ====================
	@decorator.lru_cache_with_reset(max_calls=3)
	def _execute_query(
		self,
		source: QuerySource,
		source_id: int,
		method: QueryMethod = QueryMethod.USER_ID,
		limit: int | None = 500,
	) -> list[str] | list[dict[str, Any]]:
		"""执行查询的核心逻辑(内部实现)"""
		source_value = source.value
		if source_value not in self._source_map:
			msg = f"无效来源: {source_value}"
			raise ValueError(msg)
		method_func, id_key, user_field = self._source_map[source_value]
		comments = method_func(**{id_key: source_id, "limit": limit})  # pyright: ignore[reportArgumentType]
		reply_cache: dict[int, list[dict[str, Any]]] = {}

		def extract_reply_user(reply: dict[str, Any]) -> int:
			return reply[user_field]["id"]

		def generate_replies(comment: dict[str, Any]) -> Generator[dict[str, Any]]:
			if source_value == "forum":
				if comment["id"] not in reply_cache:
					reply_cache[comment["id"]] = list(self.forum_obtain.fetch_reply_comments_gen(reply_id=comment["id"], limit=None))
				yield from reply_cache[comment["id"]]
			else:
				yield from comment.get("replies", {}).get("items", [])

		def process_user_id() -> list[str]:
			user_ids: list[str] = []
			for comment in comments:
				user_ids.append(str(comment["user"]["id"]))
				user_ids.extend(str(extract_reply_user(reply)) for reply in generate_replies(comment))
			return self._data_processor.deduplicate(user_ids)

		def process_comment_id() -> list[str]:
			comment_ids: list[str] = []
			for comment in comments:
				comment_ids.append(str(comment["id"]))
				comment_ids.extend(f"{comment['id']}.{reply['id']}" for reply in generate_replies(comment))
			return self._data_processor.deduplicate(comment_ids)

		def process_detailed() -> list[dict[str, Any]]:
			detailed_comments: list[dict[str, Any]] = []
			for item in comments:
				comment_data: dict[str, Any] = {
					"user_id": item["user"]["id"],
					"nickname": item["user"]["nickname"],
					"id": item["id"],
					"content": item["content"],
					"created_at": item["created_at"],
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
				detailed_comments.append(comment_data)
			return detailed_comments

		method_handlers = {
			QueryMethod.USER_ID: process_user_id,
			QueryMethod.COMMENT_ID: process_comment_id,
			QueryMethod.COMMENTS: process_detailed,
		}
		if method not in method_handlers:
			msg = f"无效方法: {method}"
			raise ValueError(msg)
		return method_handlers[method]()

	# ==================== 公共 API 接口 ====================
	@overload
	def get_comments(self, source: Literal["work", "forum", "shop"], source_id: int, method: Literal["user_id"] = ..., limit: int | None = ...) -> list[str]: ...
	@overload
	def get_comments(self, source: Literal["work", "forum", "shop"], source_id: int, method: Literal["comment_id"], limit: int | None = ...) -> list[str]: ...
	@overload
	def get_comments(self, source: Literal["work", "forum", "shop"], source_id: int, method: Literal["comments"], limit: int | None = ...) -> list[dict[str, Any]]: ...
	def get_comments(
		self,
		source: Literal["work", "forum", "shop"],
		source_id: int,
		method: str = "user_id",
		limit: int | None = 500,
	) -> list[str] | list[dict[str, Any]]:
		"""
		获取评论数据(主公共接口)
		Args:
			source: 数据来源(work/forum/shop)
			source_id: 资源 ID(作品 ID / 帖子 ID / 商店 ID)
			method: 查询方法(user_id/comment_id/comments)
			limit: 数量限制
		Returns:
			- user_id: 用户 ID 列表
			- comment_id: 评论 ID 列表
			- comments: 详细的评论数据结构
		"""
		# 处理默认参数
		query_method = QueryMethod(method)
		return self._execute_query(source=QuerySource(source), source_id=source_id, method=query_method, limit=limit)

	# ==================== 保持原有方法 ====================
	def get_new_replies(
		self,
		limit: int = 0,
		type_item: Literal["LIKE_FORK", "COMMENT_REPLY", "SYSTEM"] = "COMMENT_REPLY",
	) -> list[dict[str, Any]]:
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
		replies: list[dict[str, Any]] = []
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

	def collect_work_comments(self, limit: int) -> list[dict[str, Any]]:
		"""收集作品评论"""
		works = self.integrate_work_data(limit=limit)
		comments: list[dict[str, Any]] = []
		for single_work in works:
			# 使用新的简洁 API
			work_comments = self.get_comments(source="work", source_id=single_work["work_id"], method="comments", limit=20)
			# 类型断言:我们知道当 method="comments" 时返回的是 list [dict]
			work_comments = cast("list [dict [str, Any]]", work_comments)
			comments.extend(work_comments)
		# 处理评论数据
		filtered_comments = self._data_processor.filter_fields(data=comments, include=["user_id", "content", "nickname"])
		filtered_comments = cast("list [dict [str, Any]]", filtered_comments)
		user_comments_map: dict[str, dict[str, Any]] = {}
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
	def switch_edu_account(self, limit: int | None, return_method: Literal["generator"]) -> Iterator[tuple[str, str]]: ...
	@overload
	def switch_edu_account(self, limit: int | None, return_method: Literal["list"]) -> list[tuple[str, str]]: ...
	def switch_edu_account(self, limit: int | None, return_method: Literal["generator", "list"]) -> Iterator[tuple[str, str]] | list[tuple[str, str]]:
		"""获取教育账号信息"""
		try:
			students = list(self.edu_obtain.fetch_class_students_gen(limit=limit))
			if not students:
				print("没有可用的教育账号")
				return iter([]) if return_method == "generator" else []
			self.client.switch_identity(token=self.client.token.average, identity="average")

			def process_student(student: dict[str, Any]) -> tuple[str, str]:
				return (student["username"], self.edu_motion.reset_student_password(student["id"])["password"])

			if return_method == "generator":

				def account_generator() -> Generator[tuple[str, str]]:
					students_copy = students.copy()
					while students_copy:
						student = students_copy.pop(randint(0, len(students_copy) - 1))
						yield process_student(student)

				return account_generator()
			if return_method == "list":
				result: list[tuple[str, str]] = []
				students_copy = students.copy()
				while students_copy:
					student = students_copy.pop(randint(0, len(students_copy) - 1))
					result.append(process_student(student))
				return result
		except Exception as e:
			print(f"获取教育账号失败: {e}")
			return iter([]) if return_method == "generator" else []
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
