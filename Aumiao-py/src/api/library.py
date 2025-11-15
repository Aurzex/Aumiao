from typing import Literal

from src.utils import acquire
from src.utils.acquire import HTTPStatus
from src.utils.decorator import singleton


@singleton
class CartoonDataFetcher:
	def __init__(self) -> None:
		# 初始化获取漫画的客户端
		self._client = acquire.CodeMaoClient()

	# 获取全部漫画
	def fetch_all_cartoons(self) -> dict:
		# 发送GET请求获取全部漫画
		response = self._client.send_request(endpoint="/api/comic/list/all", method="GET")
		return response.json()

	# 获取漫画信息
	def fetch_cartoon_info(self, comic_id: int) -> dict:
		# 发送GET请求获取漫画信息
		response = self._client.send_request(endpoint=f"/api/comic/{comic_id}", method="GET")
		return response.json()

	# 获取漫画某个章节信息(每个章节会分配一个唯一id)
	def fetch_cartoon_chapter(self, chapter_id: int) -> dict:
		# 发送GET请求获取漫画某个章节信息
		response = self._client.send_request(endpoint=f"/api/comic/page/list/{chapter_id}", method="GET")
		return response.json()


@singleton
class NovelDataFetcher:
	# ["未知", "连载中", "已完结", "已删除"]
	def __init__(self) -> None:
		# 初始化获取小说的客户端
		self._client = acquire.CodeMaoClient()

	# 获取小说分类列表
	def fetch_novel_categories(self) -> dict:
		# 发送GET请求获取小说分类列表
		response = self._client.send_request(endpoint="/api/fanfic/type", method="GET")
		return response.json()

	# 获取小说列表
	def fetch_novel_list(
		self,
		list_type: Literal["all", "recommend"],
		sort_id: Literal[0, 1, 2, 3],
		category_id: Literal[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
		status: Literal[0, 1, 2],
		page: int = 1,
		limit: int = 20,
	) -> dict:
		# sort_id: 0:默认排序 1:最多点击 2:最多收藏 3:最近更新
		# category_id: 0:不限 1:魔法 2:科幻 3:游戏 4:推理 5:治愈 6:冒险 7:日常 8:校园 9:格斗 10:古风 11:恐怖
		# status: 0:全部 1:连载中 2:已完结
		# list_type: all:全部 recommend:推荐
		# 经测试recommend返回数据不受params影响 recommend
		params = {
			"sort_id": sort_id,
			"type_id": category_id,
			"status": status,
			"page": page,
			"limit": limit,
		}
		# params中的type_id与fanfic_type_id可互换
		response = self._client.send_request(endpoint=f"/api/fanfic/list/{list_type}", method="GET", params=params)
		return response.json()

	# 获取收藏的小说列表
	def fetch_favorite_novels(self, page: int = 1, limit: int = 10) -> dict:
		params = {"page": page, "limit": limit}
		response = self._client.send_request(
			endpoint="/web/fanfic/collection",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取小说详情
	def fetch_novel_details(self, novel_id: int) -> dict:
		response = self._client.send_request(endpoint=f"/api/fanfic/{novel_id}", method="GET")
		return response.json()

	# 获取小说章节信息
	def fetch_chapter_details(self, chapter_id: int) -> dict:
		response = self._client.send_request(
			endpoint=f"/web/fanfic/section/{chapter_id}",
			method="GET",
		)
		return response.json()

	# 获取小说评论
	def fetch_novel_comments(self, novel_id: int, page: int = 0, limit: int = 10) -> dict:
		# page从0开始
		params = {"page": page, "limit": limit}
		response = self._client.send_request(
			endpoint=f"/api/fanfic/comments/list/{novel_id}",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取搜索小说结果
	def search_novels(self, keyword: str, page: int = 0, limit: int = 10) -> dict:
		# page从0开始
		params = {"searchContent": keyword, "page": page, "limit": limit}
		response = self._client.send_request(
			endpoint="/api/fanfic/list/search",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取小说的所有章节
	def fetch_all_chapters(self, novel_id: int, limit: int = 200, page: int = 1) -> dict:
		params = {"amount_items": limit, "page_number": page}
		response = self._client.send_request(endpoint=f"/web/fanfic/{novel_id}/sections", method="GET", params=params)
		return response.json()

	# 获取我的小说
	def fetch_my_novels(self, limit: int = 200, page: int = 1) -> list:
		params = {"amount_items": limit, "page_number": page}
		response = self._client.send_request(endpoint="/web/fanfic/my", method="GET", params=params)
		return response.json()

	# 获取已删除的章节
	def fetch_deleted_chapters(self, limit: int = 200, page: int = 1) -> dict:
		params = {"amount_items": limit, "page_number": page}
		response = self._client.send_request(endpoint="/web/fanfic/section/deleted", method="GET", params=params)
		return response.json()


@singleton
class NovelActionHandler:
	def __init__(self) -> None:
		# 初始化CodeMaoClient对象
		self._client = acquire.CodeMaoClient()

	# 收藏/取消收藏小说
	def execute_toggle_novel_favorite(self, novel_id: int, *, favorite: bool = True) -> dict:
		method = "POST" if favorite else "DELETE"
		response = self._client.send_request(
			endpoint=f"/web/fanfic/collect/{novel_id}",
			method=method,
		)
		return response.json()

	# 发布小说评论
	def create_novel_comment(self, content: str, novel_id: int, *, return_data: bool = False) -> bool | dict:
		response = self._client.send_request(
			endpoint=f"/api/fanfic/comments/{novel_id}",
			method="POST",
			payload={
				"content": content,
			},
		)
		# 如果return_data为True,则返回response的json数据,否则返回response的状态码
		return response.json() if return_data else response.status_code == HTTPStatus.OK.value

	# 点赞/取消点赞小说评论
	def execute_toggle_comment_like(self, comment_id: int, *, like: bool = True, return_data: bool = False) -> bool | dict:
		# 发送请求,点赞赞或取消点赞小说评论
		method = "POST" if like else "DELETE"
		response = self._client.send_request(
			endpoint=f"/api/fanfic/comments/praise/{comment_id}",
			method=method,
		)
		# 如果return_data为True,则返回response的json数据,否则返回response的状态码
		return response.json() if return_data else response.status_code == HTTPStatus.OK.value

	# 删除小说评论
	def delete_novel_comment(self, comment_id: int, *, return_data: bool = False) -> bool | dict:
		response = self._client.send_request(
			endpoint=f"/api/fanfic/comments/{comment_id}",
			method="DELETE",
		)
		# 如果return_data为True,则返回response的json数据,否则返回返回response的状态码
		return response.json() if return_data else response.status_code == HTTPStatus.OK.value

	# 更新章节
	def update_chapter(self, chapter_id: int, title: str, content: str, words_num: int) -> bool:
		payload = {
			"title": title,
			"content": content,
			"draft_words_num": words_num,
		}
		response = self._client.send_request(
			endpoint=f"/web/fanfic/section/{chapter_id}",
			method="PUT",
			payload=payload,
		)
		return response.status_code == HTTPStatus.NO_CONTENT.value

	# 发布章节
	def publish_chapter(self, chapter_id: int) -> bool:
		response = self._client.send_request(endpoint=f"/web/fanfic/section/{chapter_id}/publish", method="PUT", payload={})
		return response.status_code == HTTPStatus.NO_CONTENT.value

	# 更新小说
	def update_novel(self, novel_id: int, title: str, introduction: str, category_id: int, status: int, *, return_data: bool = True) -> bool | dict:
		payload = {
			"title": title,
			"introduction": introduction,
			"fanfic_type_id": category_id,
			"status": status,
		}
		response = self._client.send_request(
			endpoint=f"/web/fanfic/{novel_id}",
			method="PUT",
			payload=payload,
		)
		return response.json() if return_data else response.status_code == HTTPStatus.OK.value

	# 创建小说
	def create_novel(self, title: str, section_title: str, draft: str, cover_pic: str, words_num: int, *, return_data: bool = True) -> bool | dict:
		payload = {
			"title": title,
			"section_title": section_title,
			"draft": draft,
			"cover_pic": cover_pic,
			"draft_words_num": words_num,
		}
		response = self._client.send_request(
			endpoint="/web/fanfic",
			method="POST",
			payload=payload,
		)
		return response.json() if return_data else response.status_code == HTTPStatus.OK.value

	# 删除小说
	def delete_novel(self, novel_id: int) -> bool:
		response = self._client.send_request(
			endpoint=f"/web/fanfic/{novel_id}",
			method="DELETE",
		)
		return response.status_code == HTTPStatus.NO_CONTENT.value


@singleton
class BookDataFetcher:
	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()

	# 获取全部图鉴
	def fetch_all_books(self) -> dict:
		response = self._client.send_request(endpoint="/api/sprite/list/all", method="GET")
		return response.json()

	# 获取所有属性
	def fetch_all_attributes(self) -> dict:
		response = self._client.send_request(endpoint="/api/sprite/factio", method="GET")
		return response.json()

	# 按星级获取图鉴
	def fetch_books_by_star(self, star: Literal[1, 2, 3, 4, 5, 6]) -> dict:
		# 1:一星 2:二星 3:三星 4:四星 5:五星 6:六星
		return self._get_books_by_params({"star": star})

	# 按属性获取图鉴
	def fetch_books_by_attribute(self, attribute_id: Literal[2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]) -> dict:
		# 2:普通 3:草 4:地 5:电 6:虫 7:水 8:火 9:机械 10:飞行 11:超能 12:神圣
		return self._get_books_by_params({"faction_id": attribute_id})

	# 通用获取图鉴方法
	def _get_books_by_params(self, params: dict) -> dict:
		response = self._client.send_request(
			endpoint="/api/sprite/list/all",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取指定图鉴详情
	def fetch_book_details(self, book_id: int) -> dict:
		response = self._client.send_request(
			endpoint=f"/api/sprite/{book_id}",
			method="GET",
		)
		return response.json()


@singleton
class BookActionHandler:
	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()

	# 点赞/取消点赞图鉴
	def execute_toggle_book_like(self, book_id: int, *, like: bool, return_data: bool = False) -> bool | dict:
		method = "POST" if like else "DELETE"
		response = self._client.send_request(
			endpoint=f"/api/sprite/praise/{book_id}",
			method=method,
		)
		return response.json() if return_data else response.status_code == HTTPStatus.OK.value
