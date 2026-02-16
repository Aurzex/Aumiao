from collections.abc import Generator
from typing import Literal

from aumiao.utils import acquire
from aumiao.utils.acquire import HTTPStatus
from aumiao.utils.decorator import singleton

# 定义 HTTP 方法选择类型
SelectMethod = Literal["POST", "DELETE"]


# ==================== 基础操作类====================
@singleton
class BaseWorkOperations:
	"""基础作品操作类 - 包含关注、收藏、点赞等通用操作"""

	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()

	def execute_toggle_follow(self, user_id: int, method: SelectMethod = "POST") -> bool:
		"""关注或取消关注用户"""
		response = self._client.send_request(
			endpoint=f"/nemo/v2/user/{user_id}/follow",
			method=method,
			payload={},
			base_url_key="default",
		)
		return response.status_code == HTTPStatus.NO_CONTENT.value

	def execute_toggle_collection(self, work_id: int, method: SelectMethod = "POST") -> bool:
		"""收藏或取消收藏作品"""
		response = self._client.send_request(
			endpoint=f"/nemo/v2/works/{work_id}/collection",
			method=method,
			payload={},
			base_url_key="default",
		)
		return response.status_code == HTTPStatus.OK.value

	def execute_toggle_like(self, work_id: int, method: SelectMethod = "POST") -> bool:
		"""点赞或取消点赞作品"""
		response = self._client.send_request(
			endpoint=f"/nemo/v2/works/{work_id}/like",
			method=method,
			payload={},
		)
		return response.status_code == HTTPStatus.OK.value

	def execute_fork_work(self, work_id: int) -> bool:
		"""再创作作品"""
		response = self._client.send_request(
			endpoint=f"/nemo/v2/works/{work_id}/fork",
			method="POST",
			payload={},
		)
		return response.status_code == HTTPStatus.OK.value

	def execute_share_work(self, work_id: int) -> bool:
		"""分享作品"""
		response = self._client.send_request(
			endpoint=f"/nemo/v2/works/{work_id}/share",
			method="POST",
			payload={},
		)
		return response.status_code == HTTPStatus.OK.value

	def execute_report_work(self, describe: str, reason: str, work_id: int) -> bool:
		"""举报作品"""
		data = {
			"work_id": work_id,
			"report_reason": reason,
			"report_describe": describe,
		}
		response = self._client.send_request(endpoint="/nemo/v2/report/work", method="POST", payload=data)
		return response.status_code == HTTPStatus.OK.value

	def update_work_name(
		self,
		work_id: int,
		name: str,
		work_type: int | None = None,
		*,
		is_check_name: bool = False,
	) -> bool:
		"""重命名作品"""
		response = self._client.send_request(
			endpoint=f"/work/works/{work_id}/rename",
			method="PATCH",
			params={"is_check_name": is_check_name, "name": name, "work_type": work_type},
			base_url_key="creation",
		)
		return response.status_code == HTTPStatus.OK.value


# ==================== 评论操作类 ====================
@singleton
class CommentOperations:
	"""评论操作类 - 包含评论的增删改查"""

	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()

	def create_work_comment(self, work_id: int, comment: str, emoji: str = "", *, return_data: bool = False) -> bool | dict:
		"""添加作品评论"""
		response = self._client.send_request(
			endpoint=f"/creation-tools/v1/works/{work_id}/comment",
			method="POST",
			payload={
				"content": comment,
				"emoji_content": emoji,
			},
		)
		return response.json() if return_data else response.status_code == HTTPStatus.CREATED.value

	def create_comment_reply(
		self,
		comment: str,
		work_id: int,
		comment_id: int,
		parent_id: int = 0,
		*,
		return_data: bool = False,
	) -> bool | dict:
		"""回复作品评论"""
		data = {"parent_id": parent_id, "content": comment}
		response = self._client.send_request(
			endpoint=f"/creation-tools/v1/works/{work_id}/comment/{comment_id}/reply",
			method="POST",
			payload=data,
		)
		return response.json() if return_data else response.status_code == HTTPStatus.CREATED.value

	def delete_comment(self, work_id: int, comment_id: int, **_: object) -> bool:
		"""删除作品评论"""
		response = self._client.send_request(
			endpoint=f"/creation-tools/v1/works/{work_id}/comment/{comment_id}",
			method="DELETE",
		)
		return response.status_code == HTTPStatus.NO_CONTENT.value

	def execute_toggle_comment_pin(
		self,
		method: Literal["PUT", "DELETE"],
		work_id: int,
		comment_id: int,
	) -> bool:
		"""置顶或取消置顶评论"""
		response = self._client.send_request(
			endpoint=f"/creation-tools/v1/works/{work_id}/comment/{comment_id}/top",
			method=method,
			payload={},
		)
		return response.status_code == HTTPStatus.NO_CONTENT.value

	def execute_toggle_comment_like(self, work_id: int, comment_id: int, method: SelectMethod = "POST") -> bool:
		"""点赞或取消点赞评论"""
		response = self._client.send_request(
			endpoint=f"/creation-tools/v1/works/{work_id}/comment/{comment_id}/liked",
			method=method,
			payload={},
		)
		return response.status_code == HTTPStatus.CREATED.value

	def execute_report_comment(self, work_id: int, comment_id: int, reason: str) -> bool:
		"""举报作品评论"""
		data = {
			"comment_id": comment_id,
			"report_reason": reason,
		}
		response = self._client.send_request(
			endpoint=f"/creation-tools/v1/works/{work_id}/comment/report",
			method="POST",
			payload=data,
		)
		return response.status_code == HTTPStatus.OK.value


# ==================== KITTEN 作品管理类 ====================
@singleton
class KittenWorkManager:
	"""KITTEN 作品管理类 - 包含创建、发布、删除等操作"""

	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()
		self.operations = BaseWorkOperations()
		self.comments = CommentOperations()

	# ---------- 创建与发布 ----------
	def create_kitten_work(
		self,
		name: str,
		work_url: str,
		preview: str,
		version: str,
		orientation: int = 1,
		sample_id: str = "",
		work_source_label: int = 1,
		save_type: int = 2,
	) -> dict:
		"""创建 Kitten 作品"""
		data = {
			"name": name,
			"work_url": work_url,
			"preview": preview,
			"orientation": orientation,
			"sample_id": sample_id,
			"version": version,
			"work_source_label": work_source_label,
			"save_type": save_type,
		}
		response = self._client.send_request(
			endpoint="/kitten/r2/work",
			method="POST",
			payload=data,
			base_url_key="creation",
		)
		return response.json()

	def execute_publish_kitten_work(
		self,
		work_id: int,
		name: str,
		description: str,
		operation: str,
		labels: list,
		cover_url: str,
		bcmc_url: str,
		work_url: str,
		fork_enable: Literal[0, 1],
		if_default_cover: Literal[1, 2],
		version: str,
		cover_type: int = 1,
		user_labels: list = [],
	) -> bool:
		"""发布 Kitten 作品"""
		data = {
			"name": name,
			"description": description,
			"operation": operation,
			"labels": labels,
			"cover_url": cover_url,
			"bcmc_url": bcmc_url,
			"work_url": work_url,
			"fork_enable": fork_enable,
			"if_default_cover": if_default_cover,
			"version": version,
			"cover_type": cover_type,
			"user_labels": user_labels,
		}
		response = self._client.send_request(
			endpoint=f"/kitten/r2/work/{work_id}/publish",
			method="PUT",
			payload=data,
			base_url_key="creation",
		)
		return response.status_code == HTTPStatus.OK.value

	def delete_kitten_draft(self, work_id: int) -> bool:
		"""删除未发布的 Kitten 作品草稿"""
		response = self._client.send_request(
			endpoint=f"/kitten/common/work/{work_id}/temporarily",
			method="DELETE",
			base_url_key="creation",
		)
		return response.status_code == HTTPStatus.OK.value

	def execute_unpublish_work(self, work_id: int) -> bool:
		"""取消发布作品"""
		response = self._client.send_request(
			endpoint=f"/tiger/work/{work_id}/unpublish",
			method="PATCH",
			payload={},
		)
		return response.status_code == HTTPStatus.NO_CONTENT.value

	def execute_unpublish_work_web(self, work_id: int) -> bool:
		"""通过 Web 端取消发布作品"""
		response = self._client.send_request(
			endpoint=f"/web/works/r2/unpublish/{work_id}",
			method="PUT",
			payload={},
		)
		return response.status_code == HTTPStatus.OK.value

	def execute_empty_kitten_trash(self) -> bool:
		"""清空 Kitten 作品回收站"""
		response = self._client.send_request(
			endpoint="/work/user/works/permanently",
			method="DELETE",
			base_url_key="creation",
		)
		return response.status_code == HTTPStatus.NO_CONTENT.value

	# ---------- 翻译 ----------
	def translate_kitten_work(self, data: dict) -> dict:
		"""翻译 Kitten 作品"""
		response = self._client.send_request(
			endpoint="/kitten/work/translate",
			method="POST",
			payload=data,
			base_url_key="creation",
		)
		return response.json()


# ==================== NEKO (Kitten N) 作品管理类 ====================
@singleton
class NekoWorkManager:
	"""NEKO (Kitten N) 作品管理类 - 包含创建、发布、删除等操作"""

	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()
		self.operations = BaseWorkOperations()
		self.comments = CommentOperations()

	# ---------- 创建与发布 ----------
	def create_kn_work(
		self,
		name: str,
		work_url: str,
		preview_url: str,
		bcm_version: str,
		save_type: int = 2,
		stage_type: int = 2,
		n_blocks: int = 0,
		n_roles: int = 2,
		n_scenes: int = 1,
		pic_need_check_file_url: str = "",
	) -> dict:
		"""创建 KN 作品"""
		data = {
			"bcm_version": bcm_version,
			"save_type": save_type,
			"name": name,
			"work_url": work_url,
			"preview_url": preview_url,
			"stage_type": stage_type,
			"n_blocks": n_blocks,
			"n_roles": n_roles,
			"n_scenes": n_scenes,
			"pic_need_check_file_url": pic_need_check_file_url,
		}
		response = self._client.send_request(
			endpoint="/neko/works",
			method="POST",
			payload=data,
			base_url_key="creation",
		)
		return response.json()

	def execute_publish_kn_work(
		self,
		work_id: int,
		name: str,
		preview_url: str,
		description: str,
		operation: str,
		fork_enable: Literal[0, 1, 2],
		if_default_cover: Literal[1, 2],
		bcmc_url: str,
		work_url: str,
		bcm_version: str,
		cover_url: str = "",
	) -> bool:
		"""发布 KN 作品"""
		data = {
			"name": name,
			"preview_url": preview_url,
			"description": description,
			"operation": operation,
			"fork_enable": fork_enable,
			"if_default_cover": if_default_cover,
			"bcmc_url": bcmc_url,
			"work_url": work_url,
			"bcm_version": bcm_version,
			"cover_url": cover_url,
		}
		response = self._client.send_request(
			endpoint=f"/neko/community/work/publish/{work_id}",
			method="POST",
			payload=data,
			base_url_key="creation",
		)
		return response.status_code == HTTPStatus.OK.value

	def delete_kn_draft(self, work_id: int, force: Literal[1, 2]) -> bool:
		"""删除未发布的 KN 作品草稿"""
		params = {"force": force}
		response = self._client.send_request(
			endpoint=f"/neko/works/{work_id}",
			method="DELETE",
			params=params,
			base_url_key="creation",
		)
		return response.status_code == HTTPStatus.OK.value

	def execute_unpublish_kn_work(self, work_id: int) -> bool:
		"""取消发布 KN 作品"""
		response = self._client.send_request(
			endpoint=f"/neko/community/work/unpublish/{work_id}",
			method="PUT",
			base_url_key="creation",
		)
		return response.status_code == HTTPStatus.OK.value

	def execute_empty_kn_trash(self) -> bool:
		"""清空 KN 作品回收站"""
		response = self._client.send_request(
			endpoint="/neko/works/permanently",
			method="DELETE",
			base_url_key="creation",
		)
		return response.status_code == HTTPStatus.OK.value

	def execute_recover_kn_trash(self, work_id: int) -> bool:
		"""恢复 KN 作品回收站作品"""
		response = self._client.send_request(
			endpoint=f"/neko/works/{work_id}/recover",
			method="PATCH",
			base_url_key="creation",
		)
		return response.status_code == HTTPStatus.OK.value

	# ---------- 其他操作 ----------
	def save_teacher_work(self, data: dict) -> dict:
		"""保存教师作品"""
		response = self._client.send_request(endpoint="/neko/works/teacher", method="POST", payload=data, base_url_key="creation")
		return response.json()

	def copy_work(self, work_id: int) -> dict:
		"""复制作品"""
		data = {"work_id": work_id}
		response = self._client.send_request(endpoint="/neko/works/copy", method="POST", payload=data, base_url_key="creation")
		return response.json()

	def troubleshoot_work_pics(self, work_id: int) -> dict:
		"""作品图片故障排查"""
		response = self._client.send_request(
			endpoint=f"/neko/works/pic-troubleshoot/{work_id}",
			method="PUT",
			base_url_key="creation",
		)
		return response.json()


# ==================== WOOD (海龟编辑器) 作品管理类 ====================
@singleton
class WoodWorkManager:
	"""WOOD (海龟编辑器) 作品管理类"""

	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()

	def fetch_wood_project(self, work_id: int) -> dict:
		"""获取海龟编辑器项目信息"""
		response = self._client.send_request(
			endpoint="/wood/project",
			method="GET",
			params={"work_id": work_id},
			base_url_key="creation",
		)
		return response.json()

	def create_wood_project(
		self,
		work_name: str = "新的作品",
		language_type: int = 3,
		run_mode: int = 0,
		files: list | None = None,
		preview_code: str = "",
		preview_url: str = "",
		*,
		is_turn_on_debug: bool = True,
		editor_mode: str = "code",
		update_time: int = 0,
	) -> dict:
		"""创建海龟编辑器作品"""
		if files is None:
			files = []

		payload = {
			"work_name": work_name,
			"language_type": language_type,
			"run_mode": run_mode,
			"update_time": update_time,
			"addition": {
				"readonly_paths": [],
				"locking_file_lines": {},
				"isTurnOnDebug": is_turn_on_debug,
				"editorMode": editor_mode,
			},
			"files": files,
			"preview_url": preview_url,
			"preview_code": preview_code,
		}

		response = self._client.send_request(
			endpoint="/wood/project",
			method="POST",
			payload=payload,
			base_url_key="creation",
		)
		return response.json()

	def delete_wood_draft(self, work_id: int) -> bool:
		"""删除海龟编辑器草稿"""
		response = self._client.send_request(
			endpoint=f"/wood/project/{work_id}/temporarily",
			method="DELETE",
			base_url_key="creation",
		)
		return response.status_code == HTTPStatus.OK.value

	def search_user_wood_projects(self, query: str = "", page: int = 1, limit: int = 15, language_type: int = 0) -> dict:
		"""搜索用户的Wood作品"""
		params = {"query": query, "page": page, "limit": limit, "language_type": language_type}
		response = self._client.send_request(
			endpoint="/wood/user/project/search",
			method="GET",
			params=params,
			base_url_key="creation",
		)
		return response.json()

	def create_wood_file(
		self,
		work_id: int,
		file_name: str = "main.py",
		source_code: str = "",
		file_type: int = 2,
		*,
		is_open: bool = False,
	) -> dict:
		"""在海龟编辑器作品中创建文件"""
		file_data = {
			"work_id": work_id,
			"file_id": -1,
			"file_name": file_name,
			"source": source_code,
			"open": is_open,
			"pid": 0,
			"file_type": file_type,
		}
		project = self.fetch_wood_project(work_id)
		if "files" not in project:
			project["files"] = []
		project["files"].append(file_data)
		return self.create_wood_project(
			work_name=project.get("work_name", "新的作品"),
			language_type=project.get("language_type", 3),
			run_mode=project.get("run_mode", 0),
			files=project["files"],
			preview_code=project.get("preview_code", ""),
			preview_url=project.get("preview_url", ""),
			is_turn_on_debug=project.get("addition", {}).get("isTurnOnDebug", True),
			editor_mode=project.get("addition", {}).get("editorMode", "code"),
			update_time=project.get("update_time", 0),
		)


# ==================== COCO (Coconut) 平台管理类 ====================
@singleton
class CocoWorkManager:
	"""COCO (Coconut) 平台管理类"""

	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()

	def fetch_coco_primary_courses(self) -> dict:
		"""获取 Coco 平台的主要课程列表"""
		response = self._client.send_request(endpoint="/coconut/primary-course/list", method="GET", base_url_key="creation")
		return response.json()

	def fetch_custom_widgets(self, limit: int | None = 100) -> Generator[dict]:
		"""获取 Coco 的自定义控件列表"""
		params = {"current_page": 1, "page_size": 100}
		return self._client.fetch_paginated_data(
			endpoint="/coconut/web/widget/list",
			params=params,
			total_key="data.total",
			data_key="data.items",
			pagination_method="page",
			limit=limit,
			config={"amount_key": "page_size", "offset_key": "current_page"},
			base_url_key="creation",
		)

	def fetch_demo_courses(self) -> dict:
		"""获取 Coco 的示范教程列表"""
		response = self._client.send_request(
			endpoint="/coconut/sample/list",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	def fetch_whitelisted_works(self) -> dict:
		"""获取 Coco 的白名单作品链接"""
		# response = self._client.send_request(endpoint="https://static.codemao.cn/coco/whitelist.json", method="GET")
		response = self._client.send_request(endpoint="static.bcmcdn.com/coco/whitelist.json", method="GET")
		return response.json()

	def fetch_web_wight(self, page: int = 1, page_size: int = 100) -> dict:
		"""获取 Coco 的 web 控件"""
		params = {"current_page": page, "page_size": page_size}
		response = self._client.send_request(
			endpoint="/coconut/web/user/widget/list",
			method="GET",
			params=params,
			base_url_key="creation",
		)
		return response.json()

	def execute_update_coco_work(
		self,
		work_id: int,
		work_name: str,
		bcm_url: str,
		preview_url: str,
		archive_version: str = "0.1.0",
		save_type: int = 1,
	) -> dict:
		"""更新 Coco 作品"""
		data = {
			"id": work_id,
			"name": work_name,
			"preview_url": preview_url,
			"bcm_url": bcm_url,
			"archive_version": archive_version,
			"save_type": save_type,
		}
		response = self._client.send_request(endpoint="/coconut/web/work", method="PUT", data=data, base_url_key="creation")
		return response.json()

	def execute_publish_coco_work(
		self,
		work_id: int,
		work_name: str,
		bcmc_url: str,
		cover_url: str,
		description: str,
		operation: str,
	) -> dict:
		"""发布 Coco 作品"""
		data = {
			"name": work_name,
			"description": description,
			"operation": operation,
			"cover_url": cover_url,
			"bcmc_url": bcmc_url,
			"player_url": f"https://coco.codemao.cn/editor/player/{work_id}?channel=community",
		}
		response = self._client.send_request(endpoint=f"/coconut/web/work/{work_id}/publish", method="PUT", data=data, base_url_key="creation")
		return response.json()


# ==================== 协作功能管理类 ====================
@singleton
class CollaborationManager:
	"""协作功能管理类"""

	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()

	def fetch_kitten_collaboration_code(self, work_id: int, method: Literal["GET", "DELETE"] = "GET") -> dict:
		"""获取或删除 Kitten 协作邀请码"""
		response = self._client.send_request(
			endpoint=f"https://socketcoll.codemao.cn/coll/kitten/collaborator/code/{work_id}",
			method=method,
		)
		return response.json()

	def fetch_coco_collaboration_code(self, work_id: int, permission: Literal["edit", "view"]) -> dict:
		"""获取 Coco 协作邀请码"""
		permission_code = 1 if permission == "edit" else 2
		params = {"edit_permission": permission_code}
		response = self._client.send_request(
			endpoint=f"https://socketcoll.codemao.cn/coll/coco/collaborator/code/{work_id}",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_collaborators_gen(self, work_type: Literal["coco", "kitten"], work_id: int, limit: int | None = 100) -> Generator[dict]:
		"""获取协作者列表生成器"""
		params = {"current_page": 1, "page_size": 100}
		# coco 抓包的时候发现 work_id 也在 params 中出现,但是不影响数据获取, 故省略
		return self._client.fetch_paginated_data(
			endpoint=f"https://socketcoll.codemao.cn/coll/{work_type}/collaborator/{work_id}",
			params=params,
			total_key="data.total",
			data_key="data.items",
			pagination_method="page",
			config={"amount_key": "page_size", "offset_key": "current_page"},
			limit=limit,
		)

	def fetch_collaboration_status(self, work_id: int) -> dict:
		"""获取协作状态"""
		response = self._client.send_request(
			endpoint=f"/collaboration/user/{work_id}",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	def fetch_collaboration_user(self, work_id: int) -> dict:
		"""获取协作用户"""
		response = self._client.send_request(
			endpoint=f"/collaboration/user/edited/{work_id}",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	def execute_enable_kitten_collaboration(self, work_id: int, work_type: Literal["kitten", "coco"]) -> bool:
		"""启用 Kitten/Coco 作品协作功能"""
		response = self._client.send_request(
			endpoint=f"https://socketcoll.codemao.cn/coll/{work_type}/{work_id}",
			method="POST",
			payload={},
		)
		return response.status_code == HTTPStatus.OK.value

	def fetch_collaboration_coco_works_gen(self, limit: int = 40) -> Generator:
		"""获取协作的 Coco 作品"""
		params = {"current_page": 1, "page_size": 40}
		return self._client.fetch_paginated_data(
			endpoint="https://socketcoll.codemao.cn/coll/coco/coll_works",
			params=params,
			total_key="data.total",
			data_key="data.items",
			pagination_method="page",
			config={"amount_key": "page_size", "offset_key": "current_page"},
			limit=limit,
		)


# ==================== AI 服务类 ====================
@singleton
class AIServices:
	"""AI 服务类 - 包含 AI 相关功能"""

	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()

	def fetch_text2img_prompt(self) -> dict:
		"""获取文生图提示词"""
		response = self._client.send_request(
			endpoint="/neko/text2img/prompt",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	def fetch_ai_painting_templates(self, template_type: str) -> dict:
		"""获取 AI 绘画模板"""
		params = {"type": template_type}
		response = self._client.send_request(
			endpoint="/neko/ai-painting/templates",
			method="GET",
			params=params,
			base_url_key="creation",
		)
		return response.json()

	def match_ai_painting(self, data: dict) -> dict:
		"""AI 绘画匹配"""
		response = self._client.send_request(endpoint="/neko/ai-painting/match", method="POST", payload=data, base_url_key="creation")
		return response.json()

	def add_to_inspiration_pool(self, img_url: str, prompt: str, style: str, img_type: str, generation_type: str) -> dict:
		"""添加到灵感池"""
		data = {"img_url": img_url, "prompt": prompt, "style": style, "img_type": img_type, "generation_type": generation_type}
		response = self._client.send_request(endpoint="/neko/inspiration-pool", method="POST", payload=data, base_url_key="creation")
		return response.json()


# ==================== 教学计划管理类 ====================
@singleton
class TeachingPlanManager:
	"""教学计划管理类"""

	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()

	def save_team_work(self, data: dict) -> dict:
		"""保存团队作品 (教学计划)"""
		response = self._client.send_request(
			endpoint="/neko/teaching-plan/save/team/work",
			method="POST",
			payload=data,
			base_url_key="creation",
		)
		return response.json()

	def fetch_teaching_plan_logs(self, work_id: int, offset: int = 0, limit: int = 20) -> dict:
		"""获取教学计划操作日志"""
		params = {"work_id": work_id, "offset": offset, "limit": limit}
		response = self._client.send_request(
			endpoint="/neko/teaching-plan/list/opr/log",
			method="GET",
			params=params,
			base_url_key="creation",
		)
		return response.json()

	def add_teaching_plan_log(self, data: dict) -> dict:
		"""添加教学计划操作日志"""
		response = self._client.send_request(
			endpoint="/neko/teaching-plan/add/opr/log",
			method="POST",
			payload=data,
			base_url_key="creation",
		)
		return response.json()

	def fetch_work_editing_status(self, work_id: int) -> dict:
		"""获取作品编辑状态"""
		response = self._client.send_request(
			endpoint=f"/neko/teaching-plan/work/editing-status/{work_id}",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	def set_work_editing_status(self, data: dict) -> dict:
		"""设置作品编辑状态"""
		response = self._client.send_request(
			endpoint="/neko/teaching-plan/set/work/editing-status",
			method="POST",
			payload=data,
			base_url_key="creation",
		)
		return response.json()

	def update_course_progress(self, data: dict) -> dict:
		"""更新课程进度"""
		response = self._client.send_request(
			endpoint="/neko/course/user/progress",
			method="POST",
			payload=data,
			base_url_key="creation",
		)
		return response.json()

	def submit_course_work(self, data: dict) -> dict:
		"""提交课程作品"""
		response = self._client.send_request(
			endpoint="/neko/course/user/course-work",
			method="POST",
			payload=data,
			base_url_key="creation",
		)
		return response.json()

	def save_teacher_course_invite_url(self, data: dict) -> dict:
		"""保存教师课程邀请链接"""
		response = self._client.send_request(
			endpoint="/neko/works/save-teacher-course-invite-url",
			method="POST",
			payload=data,
			base_url_key="creation",
		)
		return response.json()


# ==================== 图像分类管理类 ====================
@singleton
class ImageClassifyManager:
	"""图像分类管理类"""

	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()

	def fetch_image_classify_list(self, limit: int = 20, offset: int = 0) -> dict:
		"""获取图像分类列表"""
		params = {"limit": limit, "offset": offset}
		response = self._client.send_request(
			endpoint="/neko/image-classify/list",
			method="GET",
			params=params,
			base_url_key="creation",
		)
		return response.json()

	def submit_image_classify(self, data: dict) -> dict:
		"""提交图像分类"""
		response = self._client.send_request(
			endpoint="/neko/image-classify",
			method="POST",
			payload=data,
			base_url_key="creation",
		)
		return response.json()

	def update_image_classify(self, classify_id: str, data: dict) -> dict:
		"""更新图像分类"""
		response = self._client.send_request(
			endpoint=f"/neko/image-classify/{classify_id}",
			method="PUT",
			payload=data,
			base_url_key="creation",
		)
		return response.json()

	def delete_image_classify(self, classify_id: str) -> dict:
		"""删除图像分类"""
		response = self._client.send_request(
			endpoint=f"/neko/image-classify/{classify_id}",
			method="DELETE",
			base_url_key="creation",
		)
		return response.json()


# ==================== 包管理类 ====================
@singleton
class PackageManager:
	"""包管理类"""

	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()

	def fetch_package_list(self, package_type: str, limit: int = 20, offset: int = 0) -> dict:
		"""获取包列表"""
		params = {"type": package_type, "limit": limit, "offset": offset}
		response = self._client.send_request(endpoint="/neko/package/list", method="GET", params=params, base_url_key="creation")
		return response.json()

	def create_package(self, data: dict) -> dict:
		"""创建包"""
		response = self._client.send_request(endpoint="/neko/package", method="POST", payload=data, base_url_key="creation")
		return response.json()

	def update_package(self, package_id: str, name: str, description: str) -> dict:
		"""更新包信息"""
		data = {"name": name, "description": description}
		response = self._client.send_request(endpoint=f"/neko/package/{package_id}", method="PUT", payload=data, base_url_key="creation")
		return response.json()

	def delete_package(self, package_id: str) -> dict:
		"""删除包"""
		response = self._client.send_request(
			endpoint=f"/neko/package/{package_id}",
			method="DELETE",
			base_url_key="creation",
		)
		return response.json()


# ==================== 示例管理类 ====================
@singleton
class SampleManager:
	"""示例管理类"""

	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()

	def fetch_sample_detail(self, params: dict) -> dict:
		"""获取 Kitten N 示例详情"""
		response = self._client.send_request(
			endpoint="/neko/sample/detail",
			method="GET",
			params=params,
			base_url_key="creation",
		)
		return response.json()

	def fetch_sample_list(self, subject_id: str) -> dict:
		"""获取示例列表"""
		params = {"subject_id": subject_id}
		response = self._client.send_request(
			endpoint="/neko/sample/list",
			method="GET",
			params=params,
			base_url_key="creation",
		)
		return response.json()


# ==================== 作品数据获取类====================
@singleton
class WorkDataFetcher:
	"""作品数据获取类 - 包含所有GET请求的数据获取方法"""

	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()

	# ---------- 作品详情 ----------
	def fetch_work_details(self, work_id: int) -> dict:
		"""获取作品详细信息"""
		response = self._client.send_request(
			endpoint=f"/creation-tools/v1/works/{work_id}",
			method="GET",
		)
		return response.json()

	def fetch_kitten_work_details(self, work_id: int) -> dict:
		"""获取 Kitten 作品详细信息"""
		response = self._client.send_request(
			endpoint=f"/kitten/work/detail/{work_id}",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	def fetch_kn_work_details(self, work_id: int) -> dict:
		"""获取 KN 作品详细信息"""
		response = self._client.send_request(
			endpoint=f"/neko/works/{work_id}",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	def fetch_coco_work_info(self, work_id: int) -> dict:
		"""获取 Coco 作品信息"""
		response = self._client.send_request(
			endpoint=f"/coconut/web/work/{work_id}/info",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	def fetch_kn_publish_status(self, work_id: int) -> dict:
		"""获取 KN 作品发布状态"""
		response = self._client.send_request(
			endpoint=f"/neko/community/work/detail/{work_id}",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	def fetch_kn_work_state(self, work_id: int) -> dict:
		"""获取 KN 作品状态"""
		response = self._client.send_request(
			endpoint=f"/neko/works/status/{work_id}",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	def fetch_kn_work_detail(self, work_id: int) -> dict:
		"""获取 KN 作品详情"""
		response = self._client.send_request(
			endpoint=f"/neko/community/player/published-work-detail/{work_id}",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	def fetch_player_work_detail(self, work_id: int) -> dict:
		"""获取玩家作品详情"""
		response = self._client.send_request(
			endpoint=f"/neko/works/player/work-detail/{work_id}",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	def fetch_work_by_course_code(self, course_code: str) -> dict:
		"""通过课程代码获取作品"""
		params = {"course_code": course_code}
		response = self._client.send_request(
			endpoint="/neko/works/get-player-by-course-code",
			method="GET",
			params=params,
			base_url_key="creation",
		)
		return response.json()

	def fetch_work_status(self, work_id: int) -> dict:
		"""获取作品状态"""
		response = self._client.send_request(endpoint=f"/neko/works/status/{work_id}", method="GET", base_url_key="creation")
		return response.json()

	def fetch_work_activity(self, work_id: int) -> dict:
		"""获取作品参加的活动信息"""
		response = self._client.send_request(endpoint=f"/web/works/activity/info/{work_id}", method="GET")
		return response.json()

	def check_user_operation_status(self, work_id: int) -> dict:
		"""检查用户操作状态"""
		response = self._client.send_request(
			endpoint=f"/neko/community/check-user-opr-work-status/{work_id}",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	# ---------- 评论相关 ----------
	def fetch_work_comments_gen(self, work_id: int, limit: int = 15) -> Generator:
		"""获取作品评论生成器"""
		params = {"limit": 15, "offset": 0}
		return self._client.fetch_paginated_data(
			endpoint=f"/creation-tools/v1/works/{work_id}/comments",
			params=params,
			total_key="page_total",
			limit=limit,
		)

	# ---------- 源代码 ----------
	def fetch_work_source_code(self, work_id: int) -> dict:
		"""获取作品源代码"""
		response = self._client.send_request(
			endpoint=f"/creation-tools/v1/works/{work_id}/source/public",
			method="GET",
		)
		return response.json()

	def fetch_kitten_source_code(self, work_id: int) -> dict:
		"""获取 kitten 作品源代码"""
		response = self._client.send_request(endpoint=f"/kitten/work/ide/load/{work_id}", method="GET", base_url_key="creation")
		return response.json()

	def fetch_kitten_player_code(self, work_id: int) -> dict:
		"""获取 游玩端 kitten 作品代码"""
		response = self._client.send_request(endpoint=f"/kitten/r2/work/player/load/{work_id}", method="GET", base_url_key="creation")
		return response.json()

	def fetch_coco_source_code(self, work_id: int) -> dict:
		"""获取 coco 作品源代码"""
		response = self._client.send_request(endpoint=f"/coconut/web/work/{work_id}/content", method="GET", base_url_key="creation")
		return response.json()

	def fetch_coco_player_code(self, work_id: int) -> dict:
		"""获取 游玩端 coco 作品代码"""
		response = self._client.send_request(endpoint=f"/coconut/web/work/{work_id}/load", method="GET", base_url_key="creation")
		return response.json()

	def fetch_kn_work_versions(self, work_id: int) -> dict:
		"""获取 KN 作品历史版本"""
		response = self._client.send_request(
			endpoint=f"/neko/works/archive/{work_id}",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	# ---------- 作品列表和推荐 ----------
	def fetch_web_recommendations(self, work_id: int) -> dict:
		"""获取 Web 端相关作品推荐"""
		response = self._client.send_request(
			endpoint=f"/nemo/v2/works/web/{work_id}/recommended",
			method="GET",
		)
		return response.json()

	def fetch_nemo_recommendations(self, work_id: int) -> dict:
		"""获取 Nemo 端相关作品推荐"""
		params = {"work_id": work_id}
		response = self._client.send_request(
			endpoint="/nemo/v3/work-details/recommended/list",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_new_works_web(self, limit: int = 15, offset: int = 0, *, origin: bool = False) -> dict:
		"""获取 Web 端最新作品"""
		extra_params = {"work_origin_type": "ORIGINAL_WORK"} if origin else {}
		params = {**extra_params, "limit": limit, "offset": offset}
		response = self._client.send_request(
			endpoint="/creation-tools/v1/pc/discover/newest-work",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_themed_works_web(self, limit: int, offset: int = 0, subject_id: int = 0) -> dict:
		"""获取 Web 端主题作品"""
		extra_params = {"subject_id": subject_id} if subject_id else {}
		params = {**extra_params, "limit": limit, "offset": offset}
		response = self._client.send_request(
			endpoint="/creation-tools/v1/pc/discover/subject-work",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_nemo_discover(self) -> dict:
		"""获取 Nemo 端发现页作品"""
		response = self._client.send_request(
			endpoint="/creation-tools/v1/home/discover",
			method="GET",
		)
		return response.json()

	def fetch_new_works_nemo(
		self,
		types: Literal["course-work", "template", "original", "fork"],
		limit: int = 15,
		offset: int = 0,
	) -> dict:
		"""获取 Nemo 端最新作品"""
		params = {"limit": limit, "offset": offset}
		response = self._client.send_request(endpoint=f"/nemo/v3/newest/work/{types}/list", method="GET", params=params)
		return response.json()

	def fetch_activity_feed(self, limit: int = 15, offset: int = 0) -> dict:
		"""获取动态作品"""
		params = {"limit": limit, "offset": offset}
		response = self._client.send_request(
			endpoint="/nemo/v3/work/dynamic",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_recommended_users(self) -> dict:
		"""获取动态推荐用户"""
		response = self._client.send_request(
			endpoint="/nemo/v3/dynamic/focus/user/recommend",
			method="GET",
		)
		return response.json()

	# ---------- 主题相关 ----------
	def fetch_random_subjects(self) -> list[int]:
		"""获取随机作品主题 ID 列表"""
		response = self._client.send_request(
			endpoint="/nemo/v3/work-subject/random",
			method="GET",
		)
		return response.json()

	def fetch_subject_details(self, ids: int) -> dict:
		"""获取主题详细信息"""
		response = self._client.send_request(
			endpoint=f"/nemo/v3/work-subject/{ids}/info",
			method="GET",
		)
		return response.json()

	def fetch_subject_works(self, ids: int, limit: int = 15, offset: int = 0) -> dict:
		"""获取主题下作品"""
		params = {"limit": limit, "offset": offset}
		response = self._client.send_request(
			endpoint=f"/nemo/v3/work-subject/{ids}/works",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_all_subject_works(self, limit: int = 15, offset: int = 0) -> dict:
		"""获取所有主题作品"""
		params = {"limit": limit, "offset": offset}
		response = self._client.send_request(
			endpoint="/nemo/v3/work-subject/home",
			method="GET",
			params=params,
		)
		return response.json()

	# ---------- 作品谱系 ----------
	def fetch_work_lineage_web(self, work_id: int) -> dict:
		"""获取 Web 端作品谱系"""
		response = self._client.send_request(endpoint=f"/tiger/work/tree/{work_id}", method="GET")
		return response.json()

	def fetch_work_lineage_nemo(self, work_id: int) -> dict:
		"""获取 Nemo 端作品谱系"""
		response = self._client.send_request(
			endpoint=f"/nemo/v2/works/root/{work_id}",
			method="GET",
		)
		return response.json()

	# ---------- 回收站 ----------
	def fetch_kitten_trash_gen(self, version_no: Literal["KITTEN_V3", "KITTEN_V4"], work_status: str = "CYCLED", limit: int | None = 30) -> Generator[dict]:
		"""获取 Kitten 回收站作品生成器"""
		params = {
			"limit": 30,
			"offset": 0,
			"version_no": version_no,
			"work_status": work_status,
		}
		return self._client.fetch_paginated_data(
			endpoint="/tiger/work/recycle/list",
			params=params,
			limit=limit,
			base_url_key="creation",
		)

	def fetch_wood_trash_gen(self, language_type: int = 0, work_status: str = "CYCLED", published_status: str = "undefined", limit: int | None = 30) -> Generator[dict]:
		"""获取海龟编辑器回收站作品生成器"""
		params = {
			"limit": 30,
			"offset": 0,
			"language_type": language_type,
			"work_status": work_status,
			"published_status": published_status,
		}
		return self._client.fetch_paginated_data(
			endpoint="/wood/comm/work/list",
			params=params,
			limit=limit,
			base_url_key="creation",
		)

	def fetch_box_trash_gen(self, work_status: str = "CYCLED", limit: int | None = 30) -> Generator[dict]:
		"""获取代码岛回收站作品生成器"""
		params = {
			"limit": 30,
			"offset": 0,
			"work_status": work_status,
		}
		return self._client.fetch_paginated_data(
			endpoint="/box/v2/work/list",
			params=params,
			limit=limit,
			base_url_key="creation",
		)

	def fetch_fiction_trash_gen(self, fiction_status: str = "CYCLED", limit: int | None = 30) -> Generator[dict]:
		"""获取小说回收站生成器"""
		params = {
			"limit": 30,
			"offset": 0,
			"fiction_status": fiction_status,
		}
		return self._client.fetch_paginated_data(
			endpoint="/web/fanfic/my/new",
			params=params,
			limit=limit,
		)

	def fetch_kn_trash_gen(self, name: str = "", work_business_classify: int = 1, limit: int | None = 24) -> Generator[dict]:
		"""获取 KN 回收站作品生成器"""
		params = {
			"name": name,
			"limit": 24,
			"offset": 0,
			"status": -99,
			"work_business_classify": work_business_classify,
		}
		return self._client.fetch_paginated_data(
			endpoint="/neko/works/v2/list/user",
			params=params,
			limit=limit,
			base_url_key="creation",
		)

	# ---------- 搜索 ----------
	def search_kn_works_gen(self, name: str, status: int = 1, work_business_classify: int = 1, limit: int | None = 24) -> Generator[dict]:
		"""搜索 KN 作品生成器"""
		params = {
			"name": name,
			"limit": 24,
			"offset": 0,
			"status": status,
			"work_business_classify": work_business_classify,
		}
		return self._client.fetch_paginated_data(
			endpoint="/neko/works/v2/list/user",
			params=params,
			limit=limit,
			base_url_key="creation",
		)

	def search_published_kn_works_gen(self, name: str, work_business_classify: int = 1, limit: int | None = 24) -> Generator[dict]:
		"""搜索已发布 KN 作品生成器"""
		params = {
			"name": name,
			"limit": 24,
			"offset": 0,
			"work_business_classify": work_business_classify,
		}
		return self._client.fetch_paginated_data(
			endpoint="/neko/works/list/user/published",
			params=params,
			limit=limit,
			base_url_key="creation",
		)

	def search_works_by_name_web(self, name: str, limit: int = 20, offset: int = 0) -> dict:
		"""通过名称搜索作品"""
		params = {"query": name, "offset": offset, "limit": limit}
		response = self._client.send_request(
			endpoint="/nemo/community/work/name/search",
			method="GET",
			params=params,
		)
		return response.json()

	def search_works_by_name_nemo(self, name: str, limit: int = 20, offset: int = 0) -> dict:
		"""通过名称搜索作品 (版本 2)"""
		params = {"key": name, "offset": offset, "limit": limit}
		response = self._client.send_request(
			endpoint="/nemo/v2/work/name/search",
			method="GET",
			params=params,
		)
		return response.json()

	# ---------- 标签和元数据 ----------
	def fetch_work_metadata(self, work_id: int) -> dict:
		"""获取作品元数据"""
		response = self._client.send_request(endpoint=f"/api/work/info/{work_id}", method="GET")
		return response.json()

	def fetch_work_tags(self, work_id: int) -> dict:
		"""获取作品标签"""
		params = {"work_id": work_id}
		response = self._client.send_request(
			endpoint="/creation-tools/v1/work-details/work-labels",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_kitten_tags(self) -> dict:
		"""获取所有 Kitten 作品标签"""
		response = self._client.send_request(
			endpoint="/kitten/work/labels",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	def fetch_kitten_default_covers(self) -> dict:
		"""获取 Kitten 默认封面"""
		response = self._client.send_request(
			endpoint="/kitten/work/cover/defaultCovers",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	def fetch_recent_covers(self, work_id: int) -> dict:
		"""获取作品最近使用的封面"""
		response = self._client.send_request(
			endpoint=f"/kitten/work/cover/{work_id}/recentCovers",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	def validate_work_name(self, name: str, work_id: int) -> dict:
		"""验证作品名称是否可用"""
		params = {"name": name, "work_id": work_id}
		response = self._client.send_request(
			endpoint="/tiger/work/checkname",
			method="GET",
			params=params,
		)
		return response.json()

	# ---------- 作者相关 ----------
	def fetch_author_portfolio(self, user_id: int) -> dict:
		"""获取作者作品集"""
		response = self._client.send_request(
			endpoint=f"/web/works/users/{user_id}",
			method="GET",
		)
		return response.json()

	# ---------- 其他 ----------
	def fetch_work_by_miao_code(self, token: str) -> dict:
		"""根据喵口令获取作品数据"""
		params = {"token": token}
		response = self._client.send_request(
			endpoint="/tiger/nemo/miao-codes",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_kn_variables(self, work_id: int) -> dict:
		"""获取 KN 作品变量列表"""
		response = self._client.send_request(
			endpoint=f"https://socketcv.codemao.cn/neko/cv/list/variables/{work_id}",
			method="GET",
		)
		return response.json()

	def fetch_resource_pack(self, types: Literal["block", "character"], limit: int = 16, offset: int = 0) -> dict:
		"""获取积木或角色资源包"""
		type_ = 1 if types == "block" else 0
		params = {"type": type_, "limit": limit, "offset": offset}
		response = self._client.send_request(
			endpoint="/neko/package/list",
			method="GET",
			params=params,
			base_url_key="creation",
		)
		return response.json()

	def fetch_material_categories(self, material_type: str) -> dict:
		"""获取素材分类"""
		params = {"type": material_type}
		response = self._client.send_request(endpoint="/neko/material/categories", method="GET", params=params, base_url_key="creation")
		return response.json()

	def fetch_material_list(self, second_id: str, limit: int = 20, offset: int = 0) -> dict:
		"""获取素材列表"""
		params = {"second_id": second_id, "limit": limit, "offset": offset}
		response = self._client.send_request(
			endpoint="/neko/material/list",
			method="GET",
			params=params,
			base_url_key="creation",
		)
		return response.json()
