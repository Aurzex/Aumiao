from collections.abc import Callable, Generator
from functools import lru_cache
from typing import Any, Literal

from src.utils import decorator

from .union import ClassUnion


@decorator.singleton
class Obtain(ClassUnion):
	def __init__(self) -> None:
		super().__init__()
		self.source_map: dict[str, tuple[Callable[..., Any], str, str]] = {
			"work": (self.work_obtain.fetch_work_comments_generator, "work_id", "reply_user"),
			"post": (self.forum_obtain.fetch_post_replies_generator, "post_id", "user"),
			"shop": (self.shop_obtain.fetch_workshop_discussions, "shop_id", "reply_user"),
		}

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
			current_limit = self.tool.MathUtils().clamp(remaining, 5, 200)
			try:
				response = self.community_obtain.fetch_replies(
					types=type_item,
					limit=current_limit,
					offset=offset,
				)
				batch = response.get("items", [])
				replies.extend(batch[:remaining])
				actual_count = len(batch[:remaining])
				remaining -= actual_count
				offset += current_limit

				if actual_count < current_limit:
					break
			except Exception as e:
				print(f"获取回复失败: {e}")
				break

		return replies

	@lru_cache  # noqa: B019
	def get_comments_detail_new(
		self,
		com_id: int,
		source: str,
		method: str = "user_id",
		max_limit: int | None = 200,
	) -> list[dict] | list[str]:
		"""获取结构化评论数据"""
		if source not in self.source_map:
			msg = f"无效来源: {source}"
			raise ValueError(msg)

		method_func, id_key, user_field = self.source_map[source]
		comments = method_func(**{id_key: com_id, "limit": max_limit})

		def extract_reply_user(reply: dict) -> int:
			return reply[user_field]["id"]

		def generate_replies(comment: dict) -> Generator[dict[Any, Any] | Any, Any]:
			if source == "post":
				yield from self.forum_obtain.fetch_reply_comments_generator(reply_id=comment["id"], limit=None)
			else:
				yield from comment.get("replies", {}).get("items", [])

		def process_user_id() -> list:
			user_ids = []
			for comment in comments:
				user_ids.append(comment["user"]["id"])
				user_ids.extend(extract_reply_user(reply) for reply in generate_replies(comment))
			return self.tool.DataProcessor().deduplicate(user_ids)

		def process_comment_id() -> list:
			comment_ids = []
			for comment in comments:
				comment_ids.append(str(comment["id"]))
				comment_ids.extend(f"{comment['id']}.{reply['id']}" for reply in generate_replies(comment))
			return self.tool.DataProcessor().deduplicate(comment_ids)

		def process_detailed() -> list[dict]:
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
