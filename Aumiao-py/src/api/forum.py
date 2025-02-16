from collections.abc import Generator
from typing import Literal, overload

from src.utils import acquire
from src.utils.acquire import HTTPSTATUS
from src.utils.decorator import singleton


@singleton
class Obtain:
	def __init__(self) -> None:
		# 初始化获取帖子信息的客户端
		self.acquire = acquire.CodeMaoClient()

	# 获取多个帖子信息
	def get_posts_details(self, ids: int | list[int]) -> dict:
		# 判断传入的ids类型
		if isinstance(ids, int):
			# 如果是单个id,则直接传入
			params = {"ids": ids}
		elif isinstance(ids, list):
			# 如果是多个id,则将id列表转换为字符串
			params = {"ids": ",".join(map(str, ids))}
		# 发送请求获取帖子信息
		response = self.acquire.send_request(endpoint="/web/forums/posts/all", method="GET", params=params)
		return response.json()

	# 获取单个帖子信息
	def get_single_post_details(self, ids: int) -> dict:
		# 发送请求获取单个帖子信息
		response = self.acquire.send_request(endpoint=f"/web/forums/posts/{ids}/details", method="GET")
		return response.json()

	# 回帖会单独分配一个独立于被回复帖子的id
	# 获取帖子回帖
	def get_post_replies_posts(self, ids: int, sort: str = "-created_at", limit: int | None = 15) -> Generator:
		# 设置请求参数
		params = {"page": 1, "limit": 10, "sort": sort}
		# 发送请求获取帖子回帖
		return self.acquire.fetch_data(
			endpoint=f"/web/forums/posts/{ids}/replies",
			params=params,
			total_key="total",
			pagination_method="page",
			args={"amount": "limit", "remove": "page"},
			limit=limit,
		)

	# 获取回帖评论
	def get_reply_post_comments(
		self,
		post_id: int,
		limit: int | None = 10,
	) -> Generator[dict]:
		# 设置请求参数
		params = {"page": 1, "limit": 10}
		return self.acquire.fetch_data(
			endpoint=f"/web/forums/replies/{post_id}/comments",
			params=params,
			limit=limit,
			pagination_method="page",
			args={"amount": "limit", "remove": "page"},
		)

	# 获取我的帖子或回复的帖子
	def get_post_mine_all(self, method: Literal["created", "replied"], limit: int | None = 10) -> Generator[dict]:
		params = {"page": 1, "limit": 10}
		return self.acquire.fetch_data(
			endpoint=f"/web/forums/posts/mine/{method}",
			params=params,
			pagination_method="page",
			args={"amount": "limit", "remove": "page"},
			limit=limit,
		)

	# 获取论坛帖子各个栏目
	def get_post_boards(self) -> dict:
		response = self.acquire.send_request(endpoint="/web/forums/boards/simples/all", method="GET")
		return response.json()

	# 获取论坛单个版块详细信息T
	def get_board_details(self, board_id: int) -> dict:
		response = self.acquire.send_request(endpoint=f"/web/forums/boards/{board_id}", method="GET")
		return response.json()

	# 获取社区所有热门帖子
	def get_hot_posts(self) -> dict:
		response = self.acquire.send_request(endpoint="/web/forums/posts/hots/all", method="GET")
		return response.json()

	# 获取论坛顶部公告
	def get_top_notice(self, limit: int = 4) -> dict:
		params = {"limit": limit}
		response = self.acquire.send_request(endpoint="/web/forums/notice-boards", method="GET", params=params)
		return response.json()

	# 获取论坛本周精选帖子
	# TODO@Aurzex: 待完善
	def get_key_content(self, content_key: Literal["forum.index.top.recommend"], limit: int = 4) -> dict:
		params = {"content_key": content_key, "limit": limit}
		response = self.acquire.send_request(endpoint="/web/contents/get-key", method="GET", params=params)
		return response.json()

	# 获取社区精品合集帖子
	def get_selection_posts(self, limit: int = 20, offset: int = 0) -> dict:
		params = {"limit": limit, "offset": offset}
		response = self.acquire.send_request(
			endpoint="/web/forums/posts/selections",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取社区求帮助帖子
	def get_help_posts(self, limit: int = 20, page: int = 1) -> dict:
		params = {"limit": limit, "page": page}
		response = self.acquire.send_request(
			endpoint="/web/forums/boards/posts/ask-help",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取论坛举报原因
	def get_report_reasons(self) -> dict:
		response = self.acquire.send_request(endpoint="/web/reports/posts/reasons/all", method="GET")
		return response.json()

	# 通过标题搜索帖子
	def search_posts(self, title: str, limit: int | None = 20) -> Generator[dict]:
		params = {"title": title, "limit": 20, "page": 1}
		return self.acquire.fetch_data(
			endpoint="/web/forums/posts/search",
			pagination_method="page",
			params=params,
			limit=limit,
			args={"amount": "limit", "remove": "page"},
		)


@singleton
class Motion:
	def __init__(self) -> None:
		# 初始化acquire对象,用于发送请求
		self.acquire = acquire.CodeMaoClient()

	# 对某个帖子回帖
	def reply_post(
		self,
		post_id: int,
		content: str,
		*,
		return_data: bool = False,
	) -> dict | bool:
		# 构造请求数据
		data = {"content": content}

		response = self.acquire.send_request(
			endpoint=f"/web/forums/posts/{post_id}/replies",
			method="POST",
			payload=data,
		)
		# 返回响应数据或状态码
		return response.json() if return_data else response.status_code == HTTPSTATUS.CREATED

	# 对某个回帖评论进行回复
	def reply_comment(self, reply_id: int, parent_id: int, content: str, *, return_data: bool = False) -> dict | bool:
		# 构造请求数据
		data = {"content": content, "parent_id": parent_id}

		response = self.acquire.send_request(endpoint=f"/web/forums/replies/{reply_id}/comments", method="POST", payload=data)
		# 返回响应数据或状态码
		return response.json() if return_data else response.status_code == HTTPSTATUS.CREATED

	# 点赞某个回帖或评论
	def like_comment_or_reply(
		self,
		method: Literal["PUT", "DELETE"],
		ids: int,
		source: Literal["REPLY", "COMMENT"],
	) -> bool:
		# 每个回帖都有唯一id
		params = {"source": source}

		response = self.acquire.send_request(
			endpoint=f"/web/forums/comments/{ids}/liked",
			method=method,
			params=params,
		)
		# 返回状态码
		return response.status_code == HTTPSTATUS.NO_CONTENT

	@overload
	def report_reply_or_comment(
		self,
		comment_id: int,
		reason_id: Literal[0, 1, 2, 3, 4, 5, 6, 7, 8],
		description: str,
		source: Literal["REPLY", "COMMENT"],
		*,
		return_data: Literal[False],
	) -> bool: ...

	@overload
	def report_reply_or_comment(
		self,
		comment_id: int,
		reason_id: Literal[0, 1, 2, 3, 4, 5, 6, 7, 8],
		description: str,
		source: Literal["REPLY", "COMMENT"],
		*,
		return_data: Literal[True],
	) -> dict: ...

	# 举报某个回帖
	def report_reply_or_comment(
		self,
		comment_id: int,
		reason_id: Literal[0, 1, 2, 3, 4, 5, 6, 7, 8],
		description: str,
		source: Literal["REPLY", "COMMENT"],
		*,
		return_data: bool = False,
	) -> dict | bool:
		# get_report_reasons()仅返回1-8的reason_id,其中description与reason_id一一对应 0为自定义举报理由
		data = {
			"reason_id": reason_id,
			"description": description,
			"discussion_id": comment_id,
			"source": source,
		}

		response = self.acquire.send_request(
			endpoint="/web/reports/posts/discussions",
			method="POST",
			payload=data,
		)
		# 返回响应数据或状态码
		return response.json() if return_data else response.status_code == HTTPSTATUS.CREATED

	# 举报某个帖子
	def report_post(
		self,
		post_id: int,
		reason_id: Literal[1, 2, 3, 4, 5, 6, 7, 8],
		description: str,
		*,
		return_data: bool = False,
	) -> dict | bool:
		# description与reason_id并不对应,可以自定义描述
		data = {
			"reason_id": reason_id,
			"description": description,
			"post_id": post_id,
		}

		response = self.acquire.send_request(
			endpoint="/web/reports/posts",
			method="POST",
			payload=data,
		)
		# 返回响应数据或状态码
		return response.json() if return_data else response.status_code == HTTPSTATUS.CREATED

	# 删除某个回帖或评论或帖子
	def delete_comment_post_reply(self, ids: int, types: Literal["replies", "comments", "posts"]) -> bool:
		response = self.acquire.send_request(
			endpoint=f"/web/forums/{types}/{ids}",
			method="DELETE",
		)
		# 返回状态码
		return response.status_code == HTTPSTATUS.NO_CONTENT

	# 置顶某个回帖
	def top_comment(self, comment_id: int, method: Literal["PUT", "DELETE"]) -> bool:
		response = self.acquire.send_request(
			endpoint=f"/web/forums/replies/{comment_id}/top",
			method=method,
		)
		# 返回状态码
		return response.status_code == HTTPSTATUS.NO_CONTENT

	# 发布帖子
	def create_post(
		self,
		method: Literal["board", "work_shop"],
		title: str,
		content: str,
		board_id: None | Literal[17, 2, 10, 5, 3, 6, 27, 11, 26, 13, 7, 4, 28] = None,
		work_shop_id: None | int = None,
		*,
		return_data: bool = False,
	) -> dict | bool:
		# board_id类型可从get_post_categories()获取
		data = {"title": title, "content": content}
		if method == "board":
			url = f"/web/forums/boards/{board_id}/posts"
		elif method == "work_shop":
			url = f"/web/works/subjects/{work_shop_id}/post"

		response = self.acquire.send_request(
			endpoint=url,
			method="POST",
			payload=data,
		)
		# 返回响应数据或状态码
		return response.json() if return_data else response.status_code == HTTPSTATUS.CREATED
