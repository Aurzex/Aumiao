from collections.abc import Generator
from pathlib import Path
from re import findall
from typing import ClassVar, Literal

from src.utils import acquire, data, file
from src.utils.acquire import HTTPStatus
from src.utils.decorator import singleton

CAPTCHA_DIR: Path = data.PathConfig.CURRENT_DIR / "captcha.jpg"
JS_DIR: Path = data.PathConfig.CURRENT_DIR / "js_module"


@singleton
class AuthManager:
	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()
		self._captcha_img_path = CAPTCHA_DIR

	def authenticate_user(self, username: str, password: str, key: int, code: str) -> dict:
		payload = {"username": username, "password": password, "key": key, "code": code}
		response = self._client.send_request(endpoint="https://api-whale.codemao.cn/admins/login", method="POST", payload=payload)
		return response.json()

	def terminate_session(self) -> bool:
		response = self._client.send_request(endpoint="https://api-whale.codemao.cn/admins/logout", method="DELETE")
		return response.status_code == HTTPStatus.NO_CONTENT.value

	def fetch_verification_captcha(self, timestamp: int) -> ...:
		response = self._client.send_request(endpoint=f"https://api-whale.codemao.cn/admins/captcha/{timestamp}", method="GET", log=False)
		if response.status_code == HTTPStatus.OK.value:
			file.CodeMaoFile().file_write(path=self._captcha_img_path, content=response.content, method="wb")
			print(f"请到 {CAPTCHA_DIR} 查看验证码")
		else:
			print(f"获取验证码失败, 错误代码{response.status_code}")
		return response.cookies

	def fetch_user_dashboard_data(self) -> dict:
		response = self._client.send_request(endpoint="https://api-whale.codemao.cn/admins/info", method="GET")
		return response.json()

	def configure_authentication_token(self, token: str) -> None:
		self._client.switch_identity(token=token, identity="judgement")


@singleton
class ReportFetcher:
	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()

	def fetch_work_reports_gen(
		self,
		source_type: Literal["KITTEN", "BOX2", "ALL"],
		status: Literal["TOBEDONE", "DONE", "ALL"],
		filter_type: Literal["admin_id", "work_user_id", "work_id"] | None = None,
		target_id: int | None = None,
		limit: int | None = 15,
	) -> Generator[dict]:
		params = {"type": source_type, "status": status, "offset": 0, "limit": 15}
		if filter_type is not None and target_id is not None:
			params[filter_type] = target_id
		return self._client.fetch_paginated_data(endpoint="https://api-whale.codemao.cn/reports/works", params=params, limit=limit)

	def fetch_work_reports_total(
		self,
		source_type: Literal["KITTEN", "BOX2", "ALL"],
		status: Literal["TOBEDONE", "DONE", "ALL"],
		filter_type: Literal["admin_id", "work_user_id", "work_id"] | None = None,
		target_id: int | None = None,
	) -> dict[Literal["total", "total_pages"], int]:
		params = {"type": source_type, "status": status, "offset": 0, "limit": 15}
		if filter_type is not None and target_id is not None:
			params[filter_type] = target_id
		return self._client.get_pagination_total(endpoint="https://api-whale.codemao.cn/reports/works", params=params)

	def fetch_comment_reports_gen(
		self,
		source_type: Literal["ALL", "KITTEN", "BOX2", "FICTION", "COMIC", "WORK_SUBJECT"],
		status: Literal["TOBEDONE", "DONE", "ALL"],
		filter_type: Literal["admin_id", "comment_user_id", "comment_id"] | None = None,
		target_id: int | None = None,
		limit: int | None = 15,
	) -> Generator[dict]:
		params = {"source": source_type, "status": status, "offset": 0, "limit": 15}
		if filter_type is not None and target_id is not None:
			params[filter_type] = target_id
		return self._client.fetch_paginated_data(endpoint="https://api-whale.codemao.cn/reports/comments/search", params=params, limit=limit)

	def fetch_comment_reports_total(
		self,
		source_type: Literal["ALL", "KITTEN", "BOX2", "FICTION", "COMIC", "WORK_SUBJECT"],
		status: Literal["TOBEDONE", "DONE", "ALL"],
		filter_type: Literal["admin_id", "comment_user_id", "comment_id"] | None = None,
		target_id: int | None = None,
	) -> dict[Literal["total", "total_pages"], int]:
		params = {"source": source_type, "status": status, "offset": 0, "limit": 15}
		if filter_type is not None and target_id is not None:
			params[filter_type] = target_id
		return self._client.get_pagination_total(endpoint="https://api-whale.codemao.cn/reports/comments/search", params=params)

	def fetch_post_reports_gen(
		self,
		status: Literal["TOBEDONE", "DONE", "ALL"],
		board_id: int | None = None,  # 新增分区ID参数
		filter_type: Literal["post_id"] | None = None,
		target_id: int | None = None,
		limit: int | None = 15,
	) -> Generator[dict]:
		params = {"status": status, "offset": 0, "limit": 15}
		if board_id is not None:
			params["board_id"] = board_id
		if filter_type is not None and target_id is not None:
			params[filter_type] = target_id
		return self._client.fetch_paginated_data(endpoint="https://api-whale.codemao.cn/reports/posts", params=params, limit=limit)

	def fetch_post_reports_total(
		self,
		status: Literal["TOBEDONE", "DONE", "ALL"],
		board_id: int | None = None,  # 新增分区ID参数
		filter_type: Literal["post_id"] | None = None,
		target_id: int | None = None,
	) -> dict[Literal["total", "total_pages"], int]:
		params = {"status": status, "offset": 0, "limit": 15}
		if board_id is not None:
			params["board_id"] = board_id
		if filter_type is not None and target_id is not None:
			params[filter_type] = target_id
		return self._client.get_pagination_total(endpoint="https://api-whale.codemao.cn/reports/posts", params=params)

	def fetch_discussion_reports_gen(
		self,
		status: Literal["TOBEDONE", "DONE", "ALL"],
		board_id: int | None = None,  # 新增分区ID参数
		filter_type: Literal["post_id"] | None = None,
		target_id: int | None = None,
		limit: int | None = 15,
	) -> Generator[dict]:
		params = {"status": status, "offset": 0, "limit": 15}
		if board_id is not None:
			params["board_id"] = board_id
		if filter_type is not None and target_id is not None:
			params[filter_type] = target_id
		return self._client.fetch_paginated_data(endpoint="https://api-whale.codemao.cn/reports/posts/discussions", params=params, limit=limit)

	def fetch_discussion_reports_total(
		self,
		status: Literal["TOBEDONE", "DONE", "ALL"],
		board_id: int | None = None,  # 新增分区ID参数
		filter_type: Literal["post_id"] | None = None,
		target_id: int | None = None,
	) -> dict[Literal["total", "total_pages"], int]:
		params = {"status": status, "offset": 0, "limit": 15}
		if board_id is not None:
			params["board_id"] = board_id
		if filter_type is not None and target_id is not None:
			params[filter_type] = target_id
		return self._client.get_pagination_total(endpoint="https://api-whale.codemao.cn/reports/posts/discussions", params=params)


@singleton
class ReportHandler:
	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()

	def execute_process_post_report(self, report_id: int, admin_id: int, resolution: Literal["PASS", "DELETE", "MUTE_SEVEN_DAYS", "MUTE_THREE_MONTHS", "TOBEDONE"]) -> bool:
		response = self._client.send_request(
			endpoint=f"https://api-whale.codemao.cn/reports/posts/{report_id}",
			method="PATCH",
			payload={"admin_id": admin_id, "status": resolution},
		)
		return response.status_code == HTTPStatus.NO_CONTENT.value

	def execute_process_discussion_report(self, report_id: int, admin_id: int, resolution: Literal["PASS", "DELETE", "MUTE_SEVEN_DAYS", "MUTE_THREE_MONTHS", "TOBEDONE"]) -> bool:
		response = self._client.send_request(
			endpoint=f"https://api-whale.codemao.cn/reports/posts/discussions/{report_id}",
			method="PATCH",
			payload={"admin_id": admin_id, "status": resolution},
		)
		return response.status_code == HTTPStatus.NO_CONTENT.value

	def execute_process_comment_report(self, report_id: int, admin_id: int, resolution: Literal["PASS", "DELETE", "MUTE_SEVEN_DAYS", "MUTE_THREE_MONTHS", "TOBEDONE"]) -> bool:
		response = self._client.send_request(
			endpoint=f"https://api-whale.codemao.cn/reports/comments/{report_id}",
			method="PATCH",
			payload={"admin_id": admin_id, "status": resolution},
		)
		return response.status_code == HTTPStatus.NO_CONTENT.value

	def execute_process_work_report(self, report_id: int, admin_id: int, resolution: Literal["PASS", "DELETE", "UNLOAD", "TOBEDONE"]) -> bool:
		response = self._client.send_request(
			endpoint=f"https://api-whale.codemao.cn/reports/works/{report_id}",
			method="PATCH",
			payload={"admin_id": admin_id, "status": resolution},
		)
		return response.status_code == HTTPStatus.NO_CONTENT.value


@singleton
class RequestExtractor:
	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()

	js_module: ClassVar[list[dict[Literal["url", "num", "hash", "func"], str | int]]] = [
		{"url": "/login", "num": 55, "hash": "2d5bfbef0848d39805b1", "func": "登录页面"},
		{"url": "/admin", "num": 44, "hash": "2c387cc9ca5f95ff129d", "func": "管理员管理"},
		{"url": "/role", "num": 50, "hash": "3da39291217c79ee434c", "func": "角色管理"},
		{"url": "/comic", "num": 30, "hash": "6aa80d5ac00f83203342", "func": "全部漫画管理"},
		{"url": "/comic/:id", "num": 29, "hash": "983e1d87516549bc92c5", "func": "漫画章节/详情管理"},
		{"url": "/comic/:pid/section/:id", "num": 38, "hash": "949f453d43f8432981ab", "func": "漫画章节详情管理"},
		{"url": "/comic/:id/tucao", "num": 65, "hash": "31bfcc8f656291aff0ff", "func": "漫画吐槽管理"},
		{"url": "/comic/:id/comment", "num": 66, "hash": "0f51ecde0fec206a5156", "func": "漫画评论管理"},
		{"url": "/banner", "num": 25, "hash": "f585680c3de0462e106f", "func": "Banner管理"},
		{"url": "/forum", "num": 1, "hash": "c61dd12616a335c846b0", "func": "帖子管理"},
		{"url": "/forum/:id/reply", "num": 59, "hash": "f1cedc5c1df410cfe593", "func": "论坛回帖管理"},
		{"url": "/forum/:pid/reply/:id/comment", "num": 60, "hash": "bd30f11a34cb8dc418dd", "func": "论坛回帖评论管理"},
		{"url": "/forum-discussion", "num": 61, "hash": "2167f3beaa646556ac24", "func": "回帖与评论管理"},
		{"url": "/forum-area", "num": 11, "hash": "e9281d882c2d6bb6b1f8", "func": "分区管理"},
		{"url": "/forum-topic", "num": 28, "hash": "c1ab3aeb578a23798ee3", "func": "话题管理"},
		{"url": "/fiction", "num": 18, "hash": "440835071ce984bb0732", "func": "全部小说管理"},
		{"url": "/fiction/:id", "num": 8, "hash": "8ddbfa0574924100268b", "func": "小说详情管理"},
		{"url": "/fiction/:id/comment", "num": 62, "hash": "9c06626812252519ba39", "func": "小说评论管理"},  # spellchecker:disable-line
		{"url": "/fiction-recommend", "num": 43, "hash": "0b0361683adddcb85ae2", "func": "推荐小说管理"},
		{"url": "/fiction-tab", "num": 63, "hash": "078eaf7b8b54ef652a4a", "func": "小说标签管理"},
		{"url": "/work-published", "num": 4, "hash": "bf3bdf089e5927af2910", "func": "已发布作品管理"},
		{"url": "/work-channel", "num": 12, "hash": "828847127c53d34ec754", "func": "作品栏目管理"},
		{"url": "/work-recommend", "num": 33, "hash": "c172ee932dcd42fda38b", "func": "作品详情页推荐管理"},
		{"url": "/work-comment", "num": 47, "hash": "7f9f5187564066172558", "func": "作品评论管理"},
		{"url": "/work-cover", "num": 37, "hash": "571c2fbf6de340c4555c", "func": "作品封面管理"},
		{"url": "/work-appraise", "num": 10, "hash": "f0187aec14fb5efc219a", "func": "作品评价/审核管理"},
		{"url": "/work-subject", "num": 6, "hash": "5145a03681c4d43b5717", "func": "作品专题管理"},
		{"url": "/work-subject/:id/recommended", "num": 40, "hash": "15ac7e017b776c5a93ce", "func": "作品专题推荐管理"},
		{"url": "/work-subject/:id", "num": 39, "hash": "064998417a946d483fdc", "func": "作品专题记录管理"},
		{"url": "/message", "num": 2, "hash": "4982bc692fbad2cc60db", "func": "消息管理"},
		{"url": "/message-type", "num": 54, "hash": "711989a96365733fa054", "func": "消息类型管理"},
		{"url": "/report-work", "num": 51, "hash": "f7319a079500751083ee", "func": "作品举报管理"},
		{"url": "/report-comment", "num": 53, "hash": "7ce5e88c86b95532c804", "func": "评论举报管理"},
		{"url": "/report-forum", "num": 52, "hash": "40930262732e75b95fee", "func": "论坛举报管理"},
		{"url": "/user-recommended", "num": 17, "hash": "9ab7fd25d19fb89bcc95", "func": "用户推荐管理"},
		{"url": "/user-ban", "num": 48, "hash": "a6623212ec50c9508a47", "func": "用户封禁管理"},
		{"url": "/material", "num": 3, "hash": "bbb494001b9e5a4316a3", "func": "素材管理"},
		{"url": "/material-theme", "num": 13, "hash": "5026dc0091b3d918ead6", "func": "主题管理"},
		{"url": "/material-theme-recommend", "num": 32, "hash": "8da36236cb18b00dbeaf", "func": "主题推荐管理"},
		{"url": "/material-copyright", "num": 36, "hash": "d6361d144ce0007cd9f3", "func": "版权管理"},
		{"url": "/activity-all", "num": 23, "hash": "2f8c17e2085beaa22d8f", "func": "全部活动管理"},
		{"url": "/column-manage", "num": 15, "hash": "05f3afc2099af53f9204", "func": "活动栏目配置管理"},
		{"url": "/column/:columnId/activity", "num": 16, "hash": "cbdf69cbcc663b18e0d8", "func": "栏目活动管理"},
		{"url": "/work-studio", "num": 24, "hash": "ec087c323541f2a1a13d", "func": "活动工作台"},
		{"url": "/add-studio", "num": 26, "hash": "395d789772a79ba1bb64", "func": "添加工作室"},  # spellchecker:disable-line
		{"url": "/studio-work-manager/:studio_id", "num": 41, "hash": "02e8aaeadc9a5f034a71", "func": "工作室作品管理"},
		{"url": "/studio-work-list/:studio_id", "num": 42, "hash": "badde5c591a120f319c7", "func": "工作室作品列表"},
		{"url": "/common-label", "num": 0, "hash": "849eeb4c4a71c441f0e4", "func": "通用标签管理"},
		{"url": "/label-type/:type", "num": 0, "hash": "849eeb4c4a71c441f0e4", "func": "标签类型管理"},
		{"url": "/label-list/:label_type_id", "num": 57, "hash": "a3cbbb135753607a0d80", "func": "标签列表管理"},
		{"url": "/sensitive-word", "num": 49, "hash": "924bb824d6ee13caf6c2", "func": "敏感词管理"},  # spellchecker:disable-line
		{"url": "/interview-record", "num": 58, "hash": "39c1c7e1701acad98431", "func": "访问日志管理"},
		{"url": "/audit-record", "num": 67, "hash": "e6f83c795dc895563d75", "func": "审计日志管理"},
		{"url": "/sample-all", "num": 5, "hash": "3b037867f0570dd19c83", "func": "全部样本管理"},
		{"url": "/shop-list", "num": 7, "hash": "a7b42d82d69747b0585a", "func": "工作室管理"},
		{"url": "/shop-score", "num": 22, "hash": "ffb5039608394f2ea422", "func": "积分管理"},
		{"url": "/workshop/work-subject/:id", "num": 45, "hash": "ed8895569e6d903de86b", "func": "工作坊作品专题记录"},
		{"url": "/workshop/work-subject/:id/recommended", "num": 46, "hash": "b999be61f5e7b02f3206", "func": "工作坊作品专题推荐"},
		{"url": "/workshop/:id/users", "num": 27, "hash": "c5636030b16976426b4a", "func": "工作坊用户管理"},
		{"url": "/all-lessons", "num": 14, "hash": "4625a69bd3d942c1e270", "func": "全部课程管理"},
		{"url": "/lessons-column", "num": 20, "hash": "57509ab9ea861457bf26", "func": "课程栏目设置"},
		{"url": "/lessons-column/1/:parentId/:parentName", "num": 21, "hash": "34f4625896773fba81e0", "func": "一级课程栏目管理"},
		{"url": "/lessons-column/1/:mainId/:mainName/2/:parentId/:parentName", "num": 19, "hash": "ec6c8e7140836754fc43", "func": "二级课程栏目管理"},
		{"url": "/lessons-column/manage/:id/:name", "num": 56, "hash": "f851bab4151b51059db7", "func": "课程栏目管理"},
		{"url": "/config-manager", "num": 64, "hash": "c47c4f8409eb83865255", "func": "配置管理"},
		{"url": "/content-type", "num": 35, "hash": "db5a3c4d1c3afec33bc3", "func": "内容类型管理"},
		{"url": "/content", "num": 34, "hash": "a5f9932f54aeb45c383f", "func": "内容管理"},
		{"url": "/es", "num": 31, "hash": "a2f5e738c9b01352d9a3", "func": "搜索引擎管理"},
	]

	def fetch_js_module(self) -> None:
		for item in self.js_module:
			js_path = JS_DIR / f"{item['num']}.{item['hash']}.js"
			response = self._client.send_request(endpoint=f"https://whale.codemao.cn/static/js/{item['num']}.{item['hash']}.js", method="GET", log=False)
			if response.status_code == HTTPStatus.OK.value:
				file.CodeMaoFile().file_write(path=js_path, content=response.content, method="wb")
			else:
				print(f"获取js-{item['func']}失败! ")

	@staticmethod
	def extract_requests(
		code: str,
		methods: str | list[str] = ["get"],
	) -> list[str]:
		"""
		从代码中提取指定请求方式的链接
		参数:
			code: 待解析的JS代码字符串
			methods: 期望提取的请求方式(单个字符串或列表), 如"get"、["get", "post"]
		返回:
			提取到的请求链接列表,格式为 "方法: 链接"
		"""
		methods = [methods.lower()] if isinstance(methods, str) else [m.lower() for m in methods]
		methods_pattern = "|".join(methods)
		pattern = rf'(API\.|window\.API\.|this\.API\.)({methods_pattern})\(\s*["\']([^"\']+)["\'](?:\s*,\s*[^)]*)?\s*\)'
		matches = findall(pattern, code)
		seen = set()
		requests = []
		for match in matches:
			method = match[1].upper()
			url = match[2]
			if url not in seen:
				seen.add(url)
				requests.append(f"{method}: {url}")
		return requests
