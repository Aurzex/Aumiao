from collections.abc import Generator, Iterator
from dataclasses import dataclass
from enum import Enum
from random import randint
from typing import Any, Literal, cast, overload

from aumiao.core.base import coordinator
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
class Obtain:
	def __init__(self) -> None:
		super().__init__()
		self._source_map = {
			"work": (coordinator.work_obtain.fetch_work_comments_gen, "work_id", "reply_user"),
			"forum": (coordinator.forum_obtain.fetch_post_replies_gen, "post_id", "user"),
			"shop": (coordinator.shop_obtain.fetch_workshop_discussions_gen, "shop_id", "reply_user"),
		}
		self._data_processor = coordinator.toolkit.create_data_processor()

	# ==================== 核心查询方法 ====================
	@decorator.lru_cache_with_reset(max_calls=3)
	def _execute_query(
		self,
		source: QuerySource,
		source_id: int,
		method: QueryMethod = QueryMethod.USER_ID,
		limit: int | None = 500,
	) -> list[str] | list[dict[str, Any]]:
		"""执行查询的核心逻辑 (内部实现)"""
		source_value = source.value
		if source_value not in self._source_map:
			msg = f"无效来源: {source_value}"
			raise ValueError(msg)
		method_func, id_key, user_field = self._source_map[source_value]
		comments = method_func(**{id_key: source_id, "limit": limit})  # pyright: ignore [reportArgumentType]  # ty:ignore[invalid-argument-type]
		reply_cache: dict[int, list[dict[str, Any]]] = {}

		def extract_reply_user(reply: dict[str, Any]) -> int:
			return reply[user_field]["id"]

		def generate_replies(comment: dict[str, Any]) -> Generator[dict[str, Any]]:
			if source_value == "forum":
				if comment["id"] not in reply_cache:
					reply_cache[comment["id"]] = list(coordinator.forum_obtain.fetch_reply_comments_gen(reply_id=comment["id"], limit=None))
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
		获取评论数据 (主公共接口)
		Args:
			source: 数据来源 (work/forum/shop)
			source_id: 资源 ID (作品 ID / 帖子 ID / 商店 ID)
			method: 查询方法 (user_id/comment_id/comments)
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
	@staticmethod
	def get_new_replies(
		limit: int = 0,
		type_item: Literal["LIKE_FORK", "COMMENT_REPLY", "SYSTEM"] = "COMMENT_REPLY",
	) -> list[dict[str, Any]]:
		"""获取社区新回复"""
		try:
			message_data = coordinator.community_obtain.fetch_message_count(method="web")
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
				response = coordinator.community_obtain.fetch_replies(
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

	@staticmethod
	def get_comment_total(source_type: Literal["work", "shop", "forum"], source_id: int) -> int:
		"""
		获取不同来源的评论总数
		Args:
			source_type: 来源类型 ("work", "shop", "forum")
			source_id: 来源 ID
		Returns:
			int: 评论总数
		"""
		if source_type == "work":
			comments_url = f"/creation-tools/v1/works/{source_id}/comments"
			comments_response = coordinator.client.send_request(
				method="GET",
				endpoint=comments_url,
				params={"offset": 0, "limit": 15},
				base_url_key="default",
			).json()

			if "total" in comments_response:
				return comments_response["total"]

			work_response = coordinator.client.send_request(
				method="GET",
				endpoint=f"/creation-tools/v1/works/{source_id}",
				params={},
				base_url_key="default",
			).json()

			return work_response.get("comment_times", 0)
		if source_type == "shop":
			response = coordinator.client.send_request(
				method="GET",
				endpoint=f"/web/discussions/{source_id}/comments",
				params={
					"source": "WORK_SHOP",
					"sort": "-created_at",
					"limit": 15,
					"offset": 0,
				},
				base_url_key="default",
			).json()
			return response.get("total", 0) + response.get("totalReply", 0)
		if source_type == "forum":
			response = coordinator.client.send_request(
				method="GET",
				endpoint=f"/web/forums/posts/{source_id}/details",
				params={},
				base_url_key="default",
			).json()
			return response.get("n_replies", 0) + response.get("n_comments", 0)
		msg = f"不支持的来源类型: {source_type}"
		raise ValueError(msg)

	@staticmethod
	def integrate_work_data(limit: int) -> Generator[dict[str, Any]]:
		per_source_limit = limit // 2
		data_sources = [
			(coordinator.work_obtain.fetch_new_works_nemo(types="original", limit=per_source_limit), "nemo"),
			(coordinator.work_obtain.fetch_new_works_web(limit=per_source_limit), "web"),
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
		result.sort(key=lambda x: x["comment_count"], reverse=True)
		return result

	@staticmethod
	def get_admin_statistics() -> dict:
		"""获取管理员统计信息"""
		# 管理员列表作为常量提取
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
		statistics = []
		total_comment_reports = 0
		total_work_reports = 0
		# 单次循环完成所有统计
		for admin in admins:
			admin_id: int = cast("int", admin["id"])
			# 获取评论举报数
			comment_count = coordinator.whale_obtain.fetch_comment_reports_total(
				source_type="ALL",
				status="ALL",
				filter_type="admin_id",
				target_id=admin_id,
			)["total"]
			# 获取作品举报数
			work_count = coordinator.whale_obtain.fetch_work_reports_total(
				source_type="ALL",
				status="ALL",
				filter_type="admin_id",
				target_id=admin_id,
			)["total"]
			total_count = comment_count + work_count
			# 累加总计
			total_comment_reports += comment_count
			total_work_reports += work_count
			statistics.append(
				{
					"admin_id": admin_id,
					"admin_name": admin["name"],
					"comment_reports": comment_count,
					"work_reports": work_count,
					"total_reports": total_count,
				},
			)
		total_all_reports = total_comment_reports + total_work_reports
		# 计算百分比并添加到统计数据中
		for stat in statistics:
			percentage = (stat["total_reports"] / total_all_reports * 100) if total_all_reports > 0 else 0.0
			stat["percentage"] = round(percentage, 1)
		# 按总举报数降序排序
		statistics.sort(key=lambda x: x["total_reports"], reverse=True)
		return {
			"total_admins": len(statistics),
			"total_comment_reports": total_comment_reports,
			"total_work_reports": total_work_reports,
			"total_all_reports": total_all_reports,
			"statistics": statistics,
		}

	@staticmethod
	def get_fans_statistics(user_id: int, like_num: int = 1000) -> dict:
		"""获取粉丝统计信息"""
		fans = list(coordinator.user_obtain.fetch_followers_gen(limit=None, user_id=user_id))
		qualified_fans = []
		for fan in fans:
			if int(fan.get("total_likes", 0)) >= like_num:
				print("\n 符合条件的粉丝:")
				print(f"昵称: {fan['nickname']}")
				print(f"ID: {fan['id']}")
				print(f"获赞数: {fan['total_likes']}")
				user_data = coordinator.user_obtain.fetch_user_honors(user_id=fan["id"])
				if user_data:
					print(f"粉丝数: {user_data.get('fans_total', 'N/A')}")
					print(f"作品收藏数: {user_data.get('collected_total', 'N/A')}")
					print(f"作者等级: {user_data.get('author_level', 'N/A')}")
				qualified_fans.append(
					{
						"user_id": fan["id"],
						"nickname": fan["nickname"],
						"total_likes": fan.get("total_likes", 0),
						"fans_total": user_data.get("fans_total", "N/A") if user_data else "N/A",
						"collected_total": user_data.get("collected_total", "N/A") if user_data else "N/A",
						"author_level": user_data.get("author_level", "N/A") if user_data else "N/A",
						"n_works": fan.get("n_works", 0),
					},
				)
		return {
			"target_user_id": user_id,
			"like_threshold": like_num,
			"total_fans": len(fans),
			"qualified_fans_count": len(qualified_fans),
			"qualified_fans": qualified_fans,
		}

	@overload
	@staticmethod
	def switch_edu_account(limit: int | None, return_method: Literal["generator"]) -> Iterator[tuple[str, str]]: ...
	@overload
	@staticmethod
	def switch_edu_account(limit: int | None, return_method: Literal["list"]) -> list[tuple[str, str]]: ...
	@staticmethod
	def switch_edu_account(limit: int | None, return_method: Literal["generator", "list"]) -> Iterator[tuple[str, str]] | list[tuple[str, str]]:
		"""获取教育账号信息"""
		try:
			students = list(coordinator.edu_obtain.fetch_class_students_gen(limit=limit))
			if not students:
				print("没有可用的教育账号")
				return iter([]) if return_method == "generator" else []
			coordinator.client.switch_identity(token=coordinator.client.token.average, identity="average")

			def process_student(student: dict[str, Any]) -> tuple[str, str]:
				return (student["username"], coordinator.edu_motion.reset_student_password(student["id"])["password"])

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
