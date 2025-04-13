from collections.abc import Generator
from typing import Literal

from src.utils import acquire
from src.utils.acquire import HTTPSTATUS
from src.utils.decorator import singleton


@singleton
class Obtain:
	def __init__(self) -> None:
		self.acquire = acquire.CodeMaoClient()

	# 获取工作室简介(简易, 需登录工作室成员账号)

	def get_shops_info(self) -> dict:
		response = self.acquire.send_request(endpoint="/web/work_shops/simple", method="GET")
		# return response.json()["work_shop"]
		return response.json()

	# 获取工作室简介
	# 返回的值中id为常用的id,在函数中未特别注明均用该值,shop_id在引用中改为relation_id,label_id不变
	def get_shop_details(self, shop_id: str) -> dict:
		response = self.acquire.send_request(endpoint=f"/web/shops/{shop_id}", method="GET")
		return response.json()

	# 获取工作室列表的函数
	def get_shops(
		self,
		level: int = 4,
		limit: int = 14,
		works_limit: int = 4,
		offset: int = 0,
		sort: list[Literal["-latest_joined_at", "-created_at"]] = [
			"-created_at",
			"-latest_joined_at",
		],
	) -> dict:  # 不要问我limit默认值为啥是14,因为api默认获取14个
		if isinstance(sort, list):
			_sort = ",".join(sort)
		params = {
			"level": level,
			"works_limit": works_limit,
			"limit": limit,
			"offset": offset,
			"sort": _sort,
		}
		response = self.acquire.send_request(
			endpoint="/web/work-shops/search",
			params=params,
			method="GET",
		)
		return response.json()

	# 获取工作室成员
	def get_shops_members(self, shop_id: int, limit: int | None = 40) -> Generator[dict]:
		params = {"limit": 40, "offset": 0}
		return self.acquire.fetch_data(
			endpoint=f"/web/shops/{shop_id}/users",
			params=params,
			total_key="total",
			limit=limit,
		)

	# 获取工作室列表,包括工作室成员,工作室作品
	def get_shops_details(
		self,
		levels: list[int] | int = [1, 2, 3, 4],
		max_number: int = 4,
		works_limit: int = 4,
		sort: list[str] | str = ["-ordinal,-updated_at"],
	) -> dict:
		_levels: str = ""
		_sort: str = ""
		if isinstance(levels, list):
			_levels = ",".join(map(str, levels))
		if isinstance(sort, list):
			_sort = ",".join(sort)
		params = {
			"levels": _levels,
			"max_number": max_number,
			"works_limit": works_limit,
			"sort": _sort,
		}
		response = self.acquire.send_request(endpoint="/web/shops", method="GET", params=params)
		return response.json()

	# 获取工作室讨论
	def get_shop_discussion(
		self,
		shop_id: int,
		source: Literal["WORK_SHOP"] = "WORK_SHOP",
		sort: Literal["-created_at"] = "-created_at",
		limit: int | None = 15,
	) -> Generator[dict]:
		params = {"source": source, "sort": sort, "limit": 20, "offset": 0}
		return self.acquire.fetch_data(endpoint=f"/web/discussions/{shop_id}/comments", params=params, limit=limit)

	# 获取工作室投稿作品
	def get_shop_works(self, shop_id: int, user_id: int, sort: str = "-created_at,-id", limit: int | None = 20) -> Generator[dict]:
		params = {"limit": 20, "offset": 0, "sort": sort, "user_id": user_id, "work_subject_id": shop_id}
		return self.acquire.fetch_data(endpoint=f"/web/works/subjects/{shop_id}/works", params=params, limit=limit)

	# 获取与工作室关系
	def get_shop_relation(self, relation_id: int) -> dict:
		params = {"id": relation_id}
		response = self.acquire.send_request(endpoint="/web/work_shops/users/relation", method="GET", params=params)
		return response.json()

	# 获取工作室讨论区的帖子
	def get_shop_posts(self, label_id: int, limit: int | None = 20) -> Generator[dict]:
		params = {"limit": 20, "offset": 0}
		return self.acquire.fetch_data(endpoint=f"/web/works/subjects/labels/{label_id}/posts", params=params, limit=limit)


@singleton
class Motion:
	def __init__(self) -> None:
		# 初始化 acquire 对象
		self.acquire = acquire.CodeMaoClient()

	# 更新工作室简介
	def update_shop_details(self, description: str, shop_id: str, name: str, preview_url: str) -> bool:
		# 发送请求,更新工作室简介
		response = self.acquire.send_request(
			endpoint="/web/work_shops/update",
			method="POST",
			payload={
				"description": description,
				"id": shop_id,
				"name": name,
				"preview_url": preview_url,
			},
		)
		# 返回请求状态码是否为 HTTPSTATUS.OK
		return response.status_code == HTTPSTATUS.OK

	# 创建工作室
	def create_shop(self, name: str, description: str, preview_url: str) -> dict:
		# 发送请求,创建工作室
		response = self.acquire.send_request(
			endpoint="/web/work_shops/create",
			method="POST",
			payload={
				"name": name,
				"description": description,
				"preview_url": preview_url,
			},
		)
		# 返回请求的 json 数据
		return response.json()

	# 解散工作室
	def dissolve_shop(self, shop_id: int) -> bool:
		# 发送请求,解散工作室
		response = self.acquire.send_request(
			endpoint="/web/work_shops/dissolve",
			method="POST",
			payload={"id": shop_id},
		)
		# 返回请求状态码是否为 HTTPSTATUS.OK
		return response.status_code == HTTPSTATUS.OK

	# 在指定工作室投稿作品
	def contribute_work(self, shop_id: int, work_id: int) -> bool:
		# 发送请求,在指定工作室投稿作品
		response = self.acquire.send_request(
			endpoint="/web/work_shops/works/contribute",
			method="POST",
			payload={"id": shop_id, "work_id": work_id},
		)
		# 返回请求状态码是否为 HTTPSTATUS.OK
		return response.status_code == HTTPSTATUS.OK

	# 在指定工作室删除作品
	def remove_work(self, shop_id: int, work_id: int) -> bool:
		# 发送请求,在指定工作室删除作品
		response = self.acquire.send_request(
			endpoint="/web/work_shops/works/remove",
			method="POST",
			payload={"id": shop_id, "work_id": work_id},
		)
		# 返回请求状态码是否为 HTTPSTATUS.OK
		return response.status_code == HTTPSTATUS.OK

	# 申请加入工作室
	def apply_join(self, shop_id: int, qq: str | None = None) -> bool:
		# 发送请求申请加入工作室
		response = self.acquire.send_request(
			endpoint="/web/work_shops/users/apply/join",
			method="POST",
			payload={"id": shop_id, "qq": qq},
		)
		# 返回请求状态码是否为 HTTPSTATUS.OK
		return response.status_code == HTTPSTATUS.OK

	# 审核已经申请加入工作室的用户
	def audit_join(self, shop_id: int, status: Literal["UNACCEPTED", "ACCEPTED"], user_id: int) -> bool:
		# 发送请求,审核已经申请加入工作室的用户
		response = self.acquire.send_request(
			endpoint="/web/work_shops/users/audit",
			method="POST",
			payload={"id": shop_id, "status": status, "user_id": user_id},
		)
		# 返回请求状态码是否为 HTTPSTATUS.OK
		return response.status_code == HTTPSTATUS.OK

	# 举报讨论区下的评论
	def report_comment(
		self,
		comment_id: int,
		reason_content: str,
		reason_id: Literal[0, 1, 2, 3, 4, 5, 6, 7, 8],
		reporter_id: int,
		comment_source: Literal["WORK_SHOP"] = "WORK_SHOP",
		comment_parent_id: int = 0,
		description: str = "",
	) -> bool:
		response = self.acquire.send_request(
			endpoint="/web/reports/comments",
			method="POST",
			payload={
				"comment_id": comment_id,
				"comment_parent_id": comment_parent_id,
				"description": description,
				"reason_content": reason_content,
				"reason_id": reason_id,
				"reporter_id": reporter_id,
				"comment_source": comment_source,
			},
		)
		return response.status_code == HTTPSTATUS.CREATED

	# 回复评论
	# parent_id貌似只能为0
	def reply_work(self, shop_id: int, comment_id: int, content: str, source: Literal["WORK_SHOP"] = "WORK_SHOP", parent_id: int = 0, *, return_data: bool = False) -> bool:
		response = self.acquire.send_request(
			endpoint=f"/web/discussions/{shop_id}/comments/{comment_id}/reply",
			method="POST",
			payload={
				"parent_id": parent_id,
				"content": content,
				"source": source,
			},
		)
		return response.json() if return_data else response.status_code == HTTPSTATUS.CREATED

	# 删除回复
	def delete_reply(self, comment_id: int, source: Literal["WORK_SHOP"] = "WORK_SHOP") -> bool:
		response = self.acquire.send_request(
			endpoint=f"/web/discussions/replies/{comment_id}",
			method="DELETE",
			params={"source": source},
		)
		return response.status_code == HTTPSTATUS.NO_CONTENT

	# 评论
	def comment_work(self, shop_id: int, content: str, rich_content: str, source: Literal["WORK_SHOP"] = "WORK_SHOP", *, return_code: bool = False) -> bool:
		response = self.acquire.send_request(
			endpoint=f"/web/discussions/{shop_id}/comment",
			method="POST",
			payload={
				"content": content,
				"rich_content": rich_content,
				"source": source,
			},
		)
		return response.json() if return_code else response.status_code == HTTPSTATUS.CREATED

	# 删除评论
	def delete_comment(self, comment_id: int, source: Literal["WORK_SHOP"] = "WORK_SHOP") -> bool:
		response = self.acquire.send_request(
			endpoint=f"/web/discussions/comments/{comment_id}",
			method="DELETE",
			params={"source": source},
		)
		return response.status_code == HTTPSTATUS.NO_CONTENT
