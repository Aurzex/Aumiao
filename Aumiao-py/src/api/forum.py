from collections.abc import Generator
from typing import Literal, overload

from src.utils import acquire
from src.utils.acquire import HTTPSTATUS
from src.utils.decorator import singleton


@singleton
class ForumDataFetcher:
	def __init__(self) -> None:
		# 初始化获取帖子信息的客户端
		self._client = acquire.CodeMaoClient()

	# 获取多个帖子信息
	# 相较于fetch_single_post_details,这个api在帖子删除后依然可以获取到帖子信息
	def fetch_posts_details(self, post_ids: int | list[int]) -> dict:
		# 判断传入的ids类型
		if isinstance(post_ids, int):
			# 如果是单个id,则直接传入
			params = {"ids": post_ids}
		elif isinstance(post_ids, list):
			if len(post_ids) >= 20:  # noqa: PLR2004
				msg = "数据长度需小于20"
				raise TypeError(msg)
			# 如果是多个id,则将id列表转换为字符串
			params = {"ids": ",".join(map(str, post_ids))}
		# 发送请求获取帖子信息
		response = self._client.send_request(endpoint="/web/forums/posts/all", method="GET", params=params)
		return response.json()

	# 获取单个帖子信息
	def fetch_single_post_details(self, post_id: int) -> dict:
		# 发送请求获取单个帖子信息
		response = self._client.send_request(endpoint=f"/web/forums/posts/{post_id}/details", method="GET")
		return response.json()

	# 回帖会单独分配一个独立于被回复帖子的id
	# 获取帖子回帖
	def fetch_post_replies_gen(self, post_id: int, sort: str = "-created_at", limit: int | None = 15) -> Generator[dict]:
		# 设置请求参数
		params = {"page": 1, "limit": 10, "sort": sort}
		# 发送请求获取帖子回帖
		return self._client.fetch_data(
			endpoint=f"/web/forums/posts/{post_id}/replies",
			params=params,
			total_key="total",
			pagination_method="page",
			config={"amount_key": "limit", "offset_key": "page"},
			limit=limit,
		)

	# 获取回帖评论
	def fetch_reply_comments_gen(
		self,
		reply_id: int,
		limit: int | None = 10,
	) -> Generator[dict]:
		# 设置请求参数
		params = {"page": 1, "limit": 10}
		return self._client.fetch_data(
			endpoint=f"/web/forums/replies/{reply_id}/comments",
			params=params,
			limit=limit,
			pagination_method="page",
			config={"amount_key": "limit", "offset_key": "page"},
		)

	# 获取我的帖子或回复的帖子
	def fetch_my_posts_gen(self, post_type: Literal["created", "replied"], limit: int | None = 10) -> Generator[dict]:
		params = {"page": 1, "limit": 10}
		return self._client.fetch_data(
			endpoint=f"/web/forums/posts/mine/{post_type}",
			params=params,
			pagination_method="page",
			config={"amount_key": "limit", "offset_key": "page"},
			limit=limit,
		)

	# 获取我的帖子或回复的帖子数目
	def fetch_my_post_num(self) -> dict:
		response = self._client.send_request(endpoint="/web/forums/posts/mine/count", method="GET")
		return response.json()

	# 获取论坛帖子各个栏目
	def fetch_post_boards(self) -> dict:
		response = self._client.send_request(endpoint="/web/forums/boards/simples/all", method="GET")
		return response.json()

	# 获取论坛单个版块详细信息
	def fetch_board_details(self, board_id: int) -> dict:
		response = self._client.send_request(endpoint=f"/web/forums/boards/{board_id}", method="GET")
		return response.json()

	# 获取社区所有热门帖子ID
	def fetch_hot_posts_ids(self) -> dict:
		response = self._client.send_request(endpoint="/web/forums/posts/hots/all", method="GET")
		return response.json()

	# 获取论坛顶部公告
	def fetch_top_notices(self, limit: int = 4) -> dict:
		params = {"limit": limit}
		response = self._client.send_request(endpoint="/web/forums/notice-boards", method="GET", params=params)
		return response.json()

	# 获取论坛本周精选帖子
	def fetch_key_content(self, content_key: Literal["forum.index.top.recommend"], limit: int = 4) -> dict:
		params = {"content_key": content_key, "limit": limit}
		response = self._client.send_request(endpoint="/web/contents/get-key", method="GET", params=params)
		return response.json()

	# 获取社区精品合集帖子
	def fetch_selection_posts(self, limit: int = 20, offset: int = 0) -> dict:
		params = {"limit": limit, "offset": offset}
		response = self._client.send_request(
			endpoint="/web/forums/posts/selections",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取论坛举报原因
	def fetch_report_reasons(self) -> dict:
		response = self._client.send_request(endpoint="/web/reports/posts/reasons/all", method="GET")
		return response.json()

	# 通过标题搜索帖子
	def search_posts_gen(self, title: str, limit: int | None = 20) -> Generator[dict]:
		params = {"title": title, "limit": 20, "page": 1}
		return self._client.fetch_data(
			endpoint="/web/forums/posts/search",
			pagination_method="page",
			params=params,
			limit=limit,
			config={"amount_key": "limit", "offset_key": "page"},
		)

	# 获取热门帖子(7天内)
	def fetch_7day_hot_posts_gen(self, board_id: int = -1, limit: int | None = 15) -> Generator[dict]:
		# 设置请求参数
		params = {"page": 1, "limit": 10}
		# 构建endpoint
		endpoint = "/web/forums/boards/posts/7dayHot" if board_id == -1 else f"/web/forums/boards/posts/7dayHot?board_id={board_id}"
		return self._client.fetch_data(
			endpoint=endpoint,
			params=params,
			total_key="total",
			pagination_method="page",
			config={"amount_key": "limit", "offset_key": "page"},
			limit=limit,
		)

	# 获取求助帖子
	def fetch_ask_help_posts_gen(self, limit: int | None = 10) -> Generator[dict]:
		# 设置请求参数
		params = {"page": 1, "limit": 10}
		return self._client.fetch_data(
			endpoint="/web/forums/boards/posts/ask-help",
			params=params,
			pagination_method="page",
			config={"amount_key": "limit", "offset_key": "page"},
			limit=limit,
		)


@singleton
class ForumActionHandler:
	def __init__(self) -> None:
		# 初始化acquire对象,用于发送请求
		self._client = acquire.CodeMaoClient()

	# 对某个帖子回帖
	def create_post_reply(
		self,
		post_id: int,
		content: str,
		*,
		return_data: bool = False,
	) -> dict | bool:
		# 构造请求数据
		data = {"content": content}
		response = self._client.send_request(
			endpoint=f"/web/forums/posts/{post_id}/replies",
			method="POST",
			payload=data,
		)
		# 返回响应数据或状态码
		return response.json() if return_data else response.status_code == HTTPSTATUS.CREATED.value

	# 对某个回帖评论进行回复
	def create_comment_reply(self, reply_id: int, parent_id: int, content: str, *, return_data: bool = False) -> dict | bool:
		# 构造请求数据
		data = {"content": content, "parent_id": parent_id}
		response = self._client.send_request(endpoint=f"/web/forums/replies/{reply_id}/comments", method="POST", payload=data)
		# 返回响应数据或状态码
		return response.json() if return_data else response.status_code == HTTPSTATUS.CREATED.value

	# 点赞某个回帖或评论
	def execute_toggle_like(
		self,
		action: Literal["like", "unlike"],
		item_id: int,
		item_type: Literal["REPLY", "COMMENT"],
	) -> bool:
		# 每个回帖都有唯一id
		method = "PUT" if action == "like" else "DELETE"
		params = {"source": item_type.upper()}
		response = self._client.send_request(
			endpoint=f"/web/forums/comments/{item_id}/liked",
			method=method,
			params=params,
		)
		# 返回状态码
		return response.status_code == HTTPSTATUS.NO_CONTENT.value

	@overload
	def report_item(
		self,
		item_id: int,
		reason_id: Literal[0, 1, 2, 3, 4, 5, 6, 7, 8],
		description: str,
		item_type: Literal["REPLY", "COMMENT"],
		*,
		return_data: Literal[False],
	) -> bool: ...
	@overload
	def report_item(
		self,
		item_id: int,
		reason_id: Literal[0, 1, 2, 3, 4, 5, 6, 7, 8],
		description: str,
		item_type: Literal["REPLY", "COMMENT"],
		*,
		return_data: Literal[True],
	) -> dict: ...
	# 举报某个回帖或评论
	def report_item(
		self,
		item_id: int,
		reason_id: Literal[0, 1, 2, 3, 4, 5, 6, 7, 8],
		description: str,
		item_type: Literal["REPLY", "COMMENT"],
		*,
		return_data: bool = False,
	) -> dict | bool:
		# get_report_reasons()仅返回1-8的reason_id,其中description与reason_id一一对应 0为自定义举报理由
		data = {
			"reason_id": reason_id,
			"description": description,
			"discussion_id": item_id,
			"source": item_type.upper(),
		}
		response = self._client.send_request(
			endpoint="/web/reports/posts/discussions",
			method="POST",
			payload=data,
		)
		# 返回响应数据或状态码
		return response.json() if return_data else response.status_code == HTTPSTATUS.CREATED.value

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
		response = self._client.send_request(
			endpoint="/web/reports/posts",
			method="POST",
			payload=data,
		)
		# 返回响应数据或状态码
		return response.json() if return_data else response.status_code == HTTPSTATUS.CREATED.value

	# 删除某个回帖或评论或帖子
	def delete_item(self, item_id: int, item_type: Literal["reply", "comment", "post"]) -> bool:
		endpoint_map = {"reply": f"/web/forums/replies/{item_id}", "comment": f"/web/forums/comments/{item_id}", "post": f"/web/forums/posts/{item_id}"}
		response = self._client.send_request(
			endpoint=endpoint_map[item_type],
			method="DELETE",
		)
		# 返回状态码
		return response.status_code == HTTPSTATUS.NO_CONTENT.value

	# 置顶某个回帖
	def execute_toggle_comment_top_status(self, comment_id: int, *, should_top: bool) -> bool:
		method = "PUT" if should_top else "DELETE"
		response = self._client.send_request(
			endpoint=f"/web/forums/replies/{comment_id}/top",
			method=method,
		)
		# 返回状态码
		return response.status_code == HTTPSTATUS.NO_CONTENT.value

	# 发布帖子
	def create_post(
		self,
		target_type: Literal["board", "workshop"],
		title: str,
		content: str,
		board_id: Literal[17, 2, 10, 5, 3, 6, 27, 11, 26, 13, 7, 4, 28] | None = None,
		workshop_id: int | None = None,
		*,
		return_data: bool = False,
	) -> dict | bool:
		# board_id类型可从get_post_categories()获取
		data = {"title": title, "content": content}
		if target_type == "board":
			if board_id is None:
				msg = "board_id is required when target_type is 'board'"
				raise ValueError(msg)
			endpoint = f"/web/forums/boards/{board_id}/posts"
		elif target_type == "workshop":
			if workshop_id is None:
				msg = "workshop_id is required when target_type is 'workshop'"
				raise ValueError(msg)
			endpoint = f"/web/works/subjects/{workshop_id}/post"
		else:
			msg = f"Invalid target_type: {target_type}"
			raise ValueError(msg)
		response = self._client.send_request(
			endpoint=endpoint,
			method="POST",
			payload=data,
		)
		# 返回响应数据或状态码
		return response.json() if return_data else response.status_code == HTTPSTATUS.CREATED.value
