from collections.abc import Generator
from typing import Literal

from aumiao.utils import acquire
from aumiao.utils.acquire import HTTPStatus
from aumiao.utils.decorator import singleton

# 定义 HTTP 方法选择类型
SelectMethod = Literal["POST", "DELETE"]


@singleton
class BaseWorkManager:
	"""基础作品管理类, 包含通用操作方法"""

	def __init__(self) -> None:
		"""初始化作品管理类, 创建 CodeMaoClient 实例"""
		self._client = acquire.CodeMaoClient()

	def execute_toggle_follow(self, user_id: int, method: SelectMethod = "POST") -> bool:
		"""
		关注或取消关注用户
		Args:
			user_id: 用户 ID
			method: HTTP 方法 (POST = 关注, DELETE = 取消关注)
		Returns:
			操作是否成功
		"""
		response = self._client.send_request(
			endpoint=f"/nemo/v2/user/{user_id}/follow",
			method=method,
			payload={},
			base_url_key="default",
		)
		return response.status_code == HTTPStatus.NO_CONTENT.value

	def execute_toggle_collection(self, work_id: int, method: SelectMethod = "POST") -> bool:
		"""
		收藏或取消收藏作品
		Args:
			work_id: 作品 ID
			method: HTTP 方法 (POST = 收藏, DELETE = 取消收藏)
		Returns:
			操作是否成功
		"""
		response = self._client.send_request(
			endpoint=f"/nemo/v2/works/{work_id}/collection",
			method=method,
			payload={},
			base_url_key="default",
		)
		return response.status_code == HTTPStatus.OK.value

	def execute_toggle_like(self, work_id: int, method: SelectMethod = "POST") -> bool:
		"""
		点赞或取消点赞作品
		Args:
			work_id: 作品 ID
			method: HTTP 方法 (POST = 点赞, DELETE = 取消点赞)
		Returns:
			操作是否成功
		"""
		response = self._client.send_request(
			endpoint=f"/nemo/v2/works/{work_id}/like",
			method=method,
			payload={},
		)
		return response.status_code == HTTPStatus.OK.value

	def execute_fork_work(self, work_id: int) -> bool:
		"""
		再创作作品
		Args:
			work_id: 作品 ID
		Returns:
			再创作是否成功
		"""
		response = self._client.send_request(
			endpoint=f"/nemo/v2/works/{work_id}/fork",
			method="POST",
			payload={},
		)
		return response.status_code == HTTPStatus.OK.value

	def execute_share_work(self, work_id: int) -> bool:
		"""
		分享作品
		Args:
			work_id: 作品 ID
		Returns:
			分享是否成功
		"""
		response = self._client.send_request(
			endpoint=f"/nemo/v2/works/{work_id}/share",
			method="POST",
			payload={},
		)
		return response.status_code == HTTPStatus.OK.value

	def create_work_comment(self, work_id: int, comment: str, emoji: str = "", *, return_data: bool = False) -> bool | dict:
		"""
		添加作品评论
		Args:
			work_id: 作品 ID
			comment: 评论内容
			emoji: 表情内容 (可选)
			return_data: 是否返回完整响应数据
		Returns:
			操作结果 (成功状态或完整响应数据)
		"""
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
		"""
		回复作品评论
		Args:
			comment: 回复内容
			work_id: 作品 ID
			comment_id: 评论 ID
			parent_id: 父评论 ID (可选)
			return_data: 是否返回完整响应数据
		Returns:
			操作结果 (成功状态或完整响应数据)
		"""
		data = {"parent_id": parent_id, "content": comment}
		response = self._client.send_request(
			endpoint=f"/creation-tools/v1/works/{work_id}/comment/{comment_id}/reply",
			method="POST",
			payload=data,
		)
		return response.json() if return_data else response.status_code == HTTPStatus.CREATED.value

	def delete_comment(self, work_id: int, comment_id: int, **_: object) -> bool:
		"""
		删除作品评论
		Args:
			work_id: 作品 ID
			comment_id: 评论 ID
		Returns:
			删除是否成功
		"""
		response = self._client.send_request(
			endpoint=f"/creation-tools/v1/works/{work_id}/comment/{comment_id}",
			method="DELETE",
		)
		return response.status_code == HTTPStatus.NO_CONTENT.value

	def execute_report_work(self, describe: str, reason: str, work_id: int) -> bool:
		"""
		举报作品
		Args:
			describe: 举报描述
			reason: 举报原因
			work_id: 作品 ID
		Returns:
			举报是否成功
		"""
		data = {
			"work_id": work_id,
			"report_reason": reason,
			"report_describe": describe,
		}
		response = self._client.send_request(endpoint="/nemo/v2/report/work", method="POST", payload=data)
		return response.status_code == HTTPStatus.OK.value

	def execute_toggle_comment_pin(
		self,
		method: Literal["PUT", "DELETE"],
		work_id: int,
		comment_id: int,
	) -> bool:
		"""
		置顶或取消置顶评论
		Args:
			method: HTTP 方法 (PUT = 置顶, DELETE = 取消置顶)
			work_id: 作品 ID
			comment_id: 评论 ID
			return_data: 是否返回完整响应数据
		Returns:
			操作结果 (成功状态或完整响应数据)
		"""
		response = self._client.send_request(
			endpoint=f"/creation-tools/v1/works/{work_id}/comment/{comment_id}/top",
			method=method,
			payload={},
		)
		return response.status_code == HTTPStatus.NO_CONTENT.value

	def execute_toggle_comment_like(self, work_id: int, comment_id: int, method: SelectMethod = "POST") -> bool:
		"""
		点赞或取消点赞评论
		Args:
			work_id: 作品 ID
			comment_id: 评论 ID
			method: HTTP 方法 (POST = 点赞, DELETE = 取消点赞)
		Returns:
			操作是否成功
		"""
		response = self._client.send_request(
			endpoint=f"/creation-tools/v1/works/{work_id}/comment/{comment_id}/liked",
			method=method,
			payload={},
		)
		return response.status_code == HTTPStatus.CREATED.value

	def execute_report_comment(self, work_id: int, comment_id: int, reason: str) -> bool:
		"""
		举报作品评论
		Args:
			work_id: 作品 ID
			comment_id: 评论 ID
			reason: 举报原因
		Returns:
			举报是否成功
		"""
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

	def execute_enable_collaboration(self, work_id: int) -> bool:
		"""
		启用作品协作功能
		Args:
			work_id: 作品 ID
		Returns:
			操作是否成功
		"""
		response = self._client.send_request(
			endpoint=f"https://socketcoll.codemao.cn/coll/kitten/{work_id}",
			method="POST",
			payload={},
		)
		return response.status_code == HTTPStatus.OK.value

	def execute_unpublish_work(self, work_id: int) -> bool:
		"""
		取消发布作品
		Args:
			work_id: 作品 ID
		Returns:
			操作是否成功
		"""
		response = self._client.send_request(
			endpoint=f"/tiger/work/{work_id}/unpublish",
			method="PATCH",
			payload={},
		)
		return response.status_code == HTTPStatus.NO_CONTENT.value

	def execute_unpublish_work_web(self, work_id: int) -> bool:
		"""
		通过 Web 端取消发布作品
		Args:
			work_id: 作品 ID
		Returns:
			操作是否成功
		"""
		response = self._client.send_request(
			endpoint=f"/web/works/r2/unpublish/{work_id}",
			method="PUT",
			payload={},
		)
		return response.status_code == HTTPStatus.OK.value

	def execute_empty_kitten_trash(self) -> bool:
		"""
		清空 Kitten 作品回收站
		Returns:
			操作是否成功
		"""
		response = self._client.send_request(
			endpoint="/work/user/works/permanently",
			method="DELETE",
			base_url_key="creation",
		)
		return response.status_code == HTTPStatus.NO_CONTENT.value

	def update_work_name(
		self,
		work_id: int,
		name: str,
		work_type: int | None = None,
		*,
		is_check_name: bool = False,
	) -> bool:
		"""
		重命名作品
		Args:
			work_id: 作品 ID
			name: 新名称
			work_type: 作品类型 (可选)
			is_check_name: 是否检查名称有效性 (可选)
		Returns:
			重命名是否成功
		"""
		# 这个api还没有测试是否已经弃用
		# response = self._client.send_request(
		# 	endpoint=f"/tiger/work/works/{work_id}/rename",
		# 	method="PATCH",
		# 	params={"is_check_name": is_check_name, "name": name, "work_type": work_type},
		# )
		# 2026/1/21 新 api
		response = self._client.send_request(
			endpoint=f"/work/works/{work_id}/rename",
			method="PATCH",
			params={"is_check_name": is_check_name, "name": name, "work_type": work_type},
			base_url_key="creation",
		)
		return response.status_code == HTTPStatus.OK.value


@singleton
class KittenWorkManager:
	def __init__(self) -> None:
		"""初始化作品数据获取类"""
		self._client = acquire.CodeMaoClient()

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
		"""
		创建 Kitten 作品
		Args:
			name: 作品名称
			work_url: 作品 URL
			preview: 预览图 URL
			version: 作品版本
			orientation: 作品方向 (1 = 横屏, 2 = 竖屏)
			sample_id: 样本 ID (可选)
			work_source_label: 作品来源标签
			save_type: 保存类型
		Returns:
			创建的作品信息字典
		"""
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
		"""
		发布 Kitten 作品
		Args:
			work_id: 作品 ID
			name: 作品名称
			description: 作品描述
			operation: 操作说明
			labels: 作品标签列表
			cover_url: 封面 URL
			bcmc_url: BCMC URL
			work_url: 作品 URL
			fork_enable: 是否允许分叉 (0 = 不允许, 1 = 允许)
			if_default_cover: 封面类型 (1 = 默认, 2 = 自定义)
			version: 作品版本
			cover_type: 封面类型 (可选)
			user_labels: 用户标签列表 (可选)
		Returns:
			发布是否成功
		"""
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
		"""
		删除未发布的 Kitten 作品草稿
		Args:
			work_id: 作品 ID
		Returns:
			删除是否成功
		"""
		response = self._client.send_request(
			endpoint=f"/kitten/common/work/{work_id}/temporarily",
			method="DELETE",
			base_url_key="creation",
		)
		return response.status_code == HTTPStatus.OK.value


@singleton
class NekoWorkManager:
	def __init__(self) -> None:
		"""初始化作品数据获取类"""
		self._client = acquire.CodeMaoClient()

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
		"""
		创建 KN 作品
		Args:
			name: 作品名称
			work_url: 作品 URL
			preview_url: 预览 URL
			bcm_version: BCM 版本
			save_type: 保存类型
			stage_type: 舞台类型
			n_blocks: 积木数量
			n_roles: 角色数量
			n_scenes: 场景数量
			pic_need_check_file_url: 图片检查文件 URL
		Returns:
			创建的作品信息字典
		"""
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
		"""
		发布 KN 作品
		Args:
			work_id: 作品 ID
			name: 作品名称
			preview_url: 预览 URL
			description: 作品描述
			operation: 操作说明
			fork_enable: 分叉权限 (0 = 不允许, 1 = 允许, 2 = 仅粉丝允许)
			if_default_cover: 封面类型 (1 = 默认, 2 = 自定义)
			bcmc_url: BCMC URL
			work_url: 作品 URL
			bcm_version: BCM 版本
			cover_url: 封面 URL (可选)
		Returns:
			发布是否成功
		"""
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
		"""
		删除未发布的 KN 作品草稿
		Args:
			work_id: 作品 ID
			force: 强制删除模式 (1 = 网页端, 2 = 手机端)
		Returns:
			删除是否成功
		"""
		params = {"force": force}
		response = self._client.send_request(
			endpoint=f"/neko/works/{work_id}",
			method="DELETE",
			params=params,
			base_url_key="creation",
		)
		return response.status_code == HTTPStatus.OK.value

	def execute_unpublish_kn_work(self, work_id: int) -> bool:
		"""
		取消发布 KN 作品
		Args:
			work_id: 作品 ID
		Returns:
			操作是否成功
		"""
		response = self._client.send_request(
			endpoint=f"/neko/community/work/unpublish/{work_id}",
			method="PUT",
			base_url_key="creation",
		)
		return response.status_code == HTTPStatus.OK.value

	def execute_empty_kn_trash(self) -> bool:
		"""
		清空 KN 作品回收站
		Returns:
			操作是否成功
		"""
		response = self._client.send_request(
			endpoint="/neko/works/permanently",
			method="DELETE",
			base_url_key="creation",
		)
		return response.status_code == HTTPStatus.OK.value

	def execute_recover_kn_trash(self, work_id: int) -> bool:
		"""
		恢复 KN 作品回收站作品
		Returns:
			操作是否成功
		"""
		response = self._client.send_request(
			endpoint=f"/neko/works/{work_id}/recover",
			method="PATCH",
			base_url_key="creation",
		)
		return response.status_code == HTTPStatus.OK.value


@singleton
class WorkDataFetcher:
	"""作品数据获取类"""

	def __init__(self) -> None:
		"""初始化作品数据获取类"""
		self._client = acquire.CodeMaoClient()

	def fetch_work_comments_gen(self, work_id: int, limit: int = 15) -> Generator:
		"""
		获取作品评论生成器
		Args:
			work_id: 作品 ID
			limit: 获取评论数量限制
		Returns:
			评论数据生成器
		"""
		params = {"limit": 15, "offset": 0}
		return self._client.fetch_paginated_data(
			endpoint=f"/creation-tools/v1/works/{work_id}/comments",
			params=params,
			total_key="page_total",
			limit=limit,
		)

	def fetch_work_details(self, work_id: int) -> dict:
		"""
		获取作品详细信息
		Args:
			work_id: 作品 ID
		Returns:
			作品详细信息字典
		"""
		response = self._client.send_request(
			endpoint=f"/creation-tools/v1/works/{work_id}",
			method="GET",
		)
		return response.json()

	def fetch_kitten_work_details(self, work_id: int) -> dict:
		"""
		获取 Kitten 作品详细信息
		Args:
			work_id: 作品 ID
		Returns:
			Kitten 作品详细信息字典
		"""
		response = self._client.send_request(
			endpoint=f"/kitten/work/detail/{work_id}",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	def fetch_kn_work_details(self, work_id: int) -> dict:
		"""
		获取 KN 作品详细信息
		Args:
			work_id: 作品 ID
		Returns:
			KN 作品详细信息字典
		"""
		response = self._client.send_request(
			endpoint=f"/neko/works/{work_id}",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	def fetch_kn_publish_status(self, work_id: int) -> dict:
		"""
		获取 KN 作品发布状态
		Args:
			work_id: 作品 ID
		Returns:
			发布状态信息字典
		"""
		response = self._client.send_request(
			endpoint=f"/neko/community/work/detail/{work_id}",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	def fetch_kn_work_state(self, work_id: int) -> dict:
		"""
		获取 KN 作品状态
		Args:
			work_id: 作品 ID
		Returns:
			作品状态信息字典
		"""
		response = self._client.send_request(
			endpoint=f"/neko/works/status/{work_id}",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	def fetch_web_recommendations(self, work_id: int) -> dict:
		"""
		获取 Web 端相关作品推荐
		Args:
			work_id: 作品 ID
		Returns:
			推荐作品信息字典
		"""
		response = self._client.send_request(
			endpoint=f"/nemo/v2/works/web/{work_id}/recommended",
			method="GET",
		)
		return response.json()

	def fetch_nemo_recommendations(self, work_id: int) -> dict:
		"""
		获取 Nemo 端相关作品推荐
		Args:
			work_id: 作品 ID
		Returns:
			推荐作品信息字典
		"""
		params = {"work_id": work_id}
		response = self._client.send_request(
			endpoint="/nemo/v3/work-details/recommended/list",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_work_metadata(self, work_id: int) -> dict:
		"""
		获取作品元数据
		Args:
			work_id: 作品 ID
		Returns:
			作品元数据字典
		"""
		response = self._client.send_request(endpoint=f"/api/work/info/{work_id}", method="GET")
		return response.json()

	def fetch_work_tags(self, work_id: int) -> dict:
		"""
		获取作品标签
		Args:
			work_id: 作品 ID
		Returns:
			作品标签信息字典
		"""
		params = {"work_id": work_id}
		response = self._client.send_request(
			endpoint="/creation-tools/v1/work-details/work-labels",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_kitten_tags(self) -> dict:
		"""
		获取所有 Kitten 作品标签
		Returns:
			Kitten 标签列表字典
		"""
		response = self._client.send_request(
			endpoint="/kitten/work/labels",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	def fetch_kitten_default_covers(self) -> dict:
		"""
		获取 Kitten 默认封面
		Returns:
			默认封面列表字典
		"""
		response = self._client.send_request(
			endpoint="/kitten/work/cover/defaultCovers",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	def fetch_recent_covers(self, work_id: int) -> dict:
		"""
		获取作品最近使用的封面
		Args:
			work_id: 作品 ID
		Returns:
			最近封面列表字典
		"""
		response = self._client.send_request(
			endpoint=f"/kitten/work/cover/{work_id}/recentCovers",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	def validate_work_name(self, name: str, work_id: int) -> dict:
		"""
		验证作品名称是否可用
		Args:
			name: 作品名称
			work_id: 作品 ID (可选)
		Returns:
			验证结果字典
		"""
		params = {"name": name, "work_id": work_id}
		response = self._client.send_request(
			endpoint="/tiger/work/checkname",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_author_portfolio(self, user_id: int) -> dict:
		"""
		获取作者作品集
		Args:
			user_id: 用户 ID
		Returns:
			作者作品集字典
		"""
		response = self._client.send_request(
			endpoint=f"/web/works/users/{user_id}",
			method="GET",
		)
		return response.json()

	def fetch_work_source_code(self, work_id: int) -> dict:
		"""
		获取作品源代码
		Args:
			work_id: 作品 ID
		Returns:
			源代码信息字典
		"""
		response = self._client.send_request(
			endpoint=f"/creation-tools/v1/works/{work_id}/source/public",
			method="GET",
		)
		return response.json()

	def fetch_new_works_web(self, limit: int = 15, offset: int = 0, *, origin: bool = False) -> dict:
		"""
		获取 Web 端最新作品
		Args:
			limit: 获取数量
			offset: 偏移量 (可选)
			origin: 是否只获取原创作品 (可选)
		Returns:
			最新作品列表字典
		"""
		extra_params = {"work_origin_type": "ORIGINAL_WORK"} if origin else {}
		params = {**extra_params, "limit": limit, "offset": offset}
		response = self._client.send_request(
			endpoint="/creation-tools/v1/pc/discover/newest-work",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_themed_works_web(self, limit: int, offset: int = 0, subject_id: int = 0) -> dict:
		"""
		获取 Web 端主题作品
		Args:
			limit: 获取数量
			offset: 偏移量 (可选)
			subject_id: 主题 ID (可选)
		Returns:
			主题作品列表字典
		"""
		extra_params = {"subject_id": subject_id} if subject_id else {}
		params = {**extra_params, "limit": limit, "offset": offset}
		response = self._client.send_request(
			endpoint="/creation-tools/v1/pc/discover/subject-work",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_nemo_discover(self) -> dict:
		"""
		获取 Nemo 端发现页作品
		Returns:
			发现页作品列表字典
		"""
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
		"""
		获取 Nemo 端最新作品
		Args:
			types: 作品类型
			limit: 获取数量 (可选)
			offset: 偏移量 (可选)
		Returns:
			最新作品列表字典
		"""
		params = {"limit": limit, "offset": offset}
		response = self._client.send_request(endpoint=f"/nemo/v3/newest/work/{types}/list", method="GET", params=params)
		return response.json()

	def fetch_random_subjects(self) -> list[int]:
		"""
		获取随机作品主题 ID 列表
		Returns:
			主题 ID 列表
		"""
		response = self._client.send_request(
			endpoint="/nemo/v3/work-subject/random",
			method="GET",
		)
		return response.json()

	def fetch_subject_details(self, ids: int) -> dict:
		"""
		获取主题详细信息
		Args:
			ids: 主题 ID
		Returns:
			主题信息字典
		"""
		response = self._client.send_request(
			endpoint=f"/nemo/v3/work-subject/{ids}/info",
			method="GET",
		)
		return response.json()

	def fetch_subject_works(self, ids: int, limit: int = 15, offset: int = 0) -> dict:
		"""
		获取主题下作品
		Args:
			ids: 主题 ID
			limit: 获取数量 (可选)
			offset: 偏移量 (可选)
		Returns:
			主题作品列表字典
		"""
		params = {"limit": limit, "offset": offset}
		response = self._client.send_request(
			endpoint=f"/nemo/v3/work-subject/{ids}/works",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_all_subject_works(self, limit: int = 15, offset: int = 0) -> dict:
		"""
		获取所有主题作品
		Args:
			limit: 获取数量 (可选)
			offset: 偏移量 (可选)
		Returns:
			主题作品列表字典
		"""
		params = {"limit": limit, "offset": offset}
		response = self._client.send_request(
			endpoint="/nemo/v3/work-subject/home",
			method="GET",
			params=params,
		)
		return response.json()

	def manage_collaboration_code(self, work_id: int, method: Literal["GET", "DELETE"] = "GET") -> dict:
		"""
		获取或删除协作邀请码
		Args:
			work_id: 作品 ID
			method: HTTP 方法 (GET = 获取, DELETE = 删除)
		Returns:
			协作信息字典
		"""
		response = self._client.send_request(
			endpoint=f"https://socketcoll.codemao.cn/coll/kitten/collaborator/code/{work_id}",
			method=method,
		)
		return response.json()

	def fetch_collaborators_gen(self, work_id: int, limit: int | None = 100) -> Generator[dict]:
		"""
		获取协作者列表生成器
		Args:
			work_id: 作品 ID
			limit: 获取数量限制 (可选)
		Returns:
			协作者列表生成器
		"""
		params = {"current_page": 1, "page_size": 100}
		return self._client.fetch_paginated_data(
			endpoint=f"https://socketcoll.codemao.cn/coll/kitten/collaborator/{work_id}",
			params=params,
			total_key="data.total",
			data_key="data.items",
			pagination_method="page",
			config={"amount_key": "page_size", "offset_key": "current_page"},
			limit=limit,
		)

	def fetch_collaboration_status(self, work_id: int) -> dict:
		"""
		获取协作状态
		Args:
			work_id: 作品 ID
		Returns:
			协作状态字典
		"""
		response = self._client.send_request(
			endpoint=f"/collaboration/user/{work_id}",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	def fetch_collaboration_user(self, work_id: int) -> dict:
		"""
		获取协作用户
		Args:
			work_id: 作品 ID
		Returns:
			协作用户字典
		"""
		response = self._client.send_request(
			endpoint=f"/collaboration/user/edited/{work_id}",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	def fetch_work_lineage_web(self, work_id: int) -> dict:
		"""
		获取 Web 端作品谱系
		Args:
			work_id: 作品 ID
		Returns:
			谱系信息字典
		"""
		response = self._client.send_request(endpoint=f"/tiger/work/tree/{work_id}", method="GET")
		return response.json()

	def fetch_work_lineage_nemo(self, work_id: int) -> dict:
		"""
		获取 Nemo 端作品谱系
		Args:
			work_id: 作品 ID
		Returns:
			谱系信息字典
		"""
		response = self._client.send_request(
			endpoint=f"/nemo/v2/works/root/{work_id}",
			method="GET",
		)
		return response.json()

	def fetch_kn_work_versions(self, work_id: int) -> dict:
		"""
		获取 KN 作品历史版本
		Args:
			work_id: 作品 ID
		Returns:
			版本历史字典
		"""
		response = self._client.send_request(
			endpoint=f"/neko/works/archive/{work_id}",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	def fetch_kitten_trash_gen(self, version_no: Literal["KITTEN_V3", "KITTEN_V4"], work_status: str = "CYCLED", limit: int | None = 30) -> Generator[dict]:
		"""
		获取 Kitten 回收站作品生成器
		Args:
			version_no: 版本号
			work_status: 作品状态 (可选)
			limit: 获取数量限制 (可选)
		Returns:
			回收站作品生成器
		"""
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
		"""
		获取海龟编辑器回收站作品生成器
		Args:
			language_type: 语言类型 (可选)
			work_status: 作品状态 (可选)
			published_status: 发布状态 (可选)
			limit: 获取数量限制 (可选)
		Returns:
			回收站作品生成器
		"""
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
		"""
		获取代码岛回收站作品生成器
		Args:
			work_status: 作品状态 (可选)
			limit: 获取数量限制 (可选)
		Returns:
			回收站作品生成器
		"""
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
		"""
		获取小说回收站生成器
		Args:
			fiction_status: 小说状态 (可选)
			limit: 获取数量限制 (可选)
		Returns:
			回收站生成器
		"""
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
		"""
		获取 KN 回收站作品生成器
		Args:
			name: 搜索名称 (可选)
			work_business_classify: 作品业务分类 (可选)
			limit: 获取数量限制 (可选)
		Returns:
			回收站作品生成器
		"""
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

	def search_kn_works_gen(self, name: str, status: int = 1, work_business_classify: int = 1, limit: int | None = 24) -> Generator[dict]:
		"""
		搜索 KN 作品生成器
		Args:
			name: 搜索名称
			status: 作品状态 (可选)
			work_business_classify: 作品业务分类 (可选)
			limit: 获取数量限制 (可选)
		Returns:
			作品生成器
		"""
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
		"""
		搜索已发布 KN 作品生成器
		Args:
			name: 搜索名称
			work_business_classify: 作品业务分类 (可选)
			limit: 获取数量限制 (可选)
		Returns:
			作品生成器
		"""
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

	def fetch_kn_variables(self, work_id: int) -> dict:
		"""
		获取 KN 作品变量列表
		Args:
			work_id: 作品 ID
		Returns:
			变量列表字典
		"""
		response = self._client.send_request(
			endpoint=f"https://socketcv.codemao.cn/neko/cv/list/variables/{work_id}",
			method="GET",
		)
		return response.json()

	def fetch_resource_pack(self, types: Literal["block", "character"], limit: int = 16, offset: int = 0) -> dict:
		"""
		获取积木或角色资源包
		Args:
			types: 资源类型 (block = 积木, character = 角色)
			limit: 获取数量 (可选)
			offset: 偏移量 (可选)
		Returns:
			资源包字典
		"""
		if types == "block":
			type_ = 1
		elif types == "character":
			type_ = 0
		params = {
			"type": type_,
			"limit": limit,
			"offset": offset,
		}
		response = self._client.send_request(
			endpoint="/neko/package/list",
			method="GET",
			params=params,
			base_url_key="creation",
		)
		return response.json()

	def fetch_activity_feed(self, limit: int = 15, offset: int = 0) -> dict:
		"""
		获取动态作品
		Args:
			limit: 获取数量 (可选)
			offset: 偏移量 (可选)
		Returns:
			动态作品字典
		"""
		params = {
			"limit": limit,
			"offset": offset,
		}
		response = self._client.send_request(
			endpoint="/nemo/v3/work/dynamic",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_recommended_users(self) -> dict:
		"""
		获取动态推荐用户
		Returns:
			推荐用户字典
		"""
		response = self._client.send_request(
			endpoint="/nemo/v3/dynamic/focus/user/recommend",
			method="GET",
		)
		return response.json()

	def search_works_by_name_web(self, name: str, limit: int = 20, offset: int = 0) -> dict:
		"""
		通过名称搜索作品
		Args:
			name: 搜索名称
			limit: 获取数量 (可选)
			offset: 偏移量 (可选)
		Returns:
			搜索结果字典
		"""
		params = {
			"query": name,
			"offset": offset,
			"limit": limit,
		}
		response = self._client.send_request(
			endpoint="/nemo/community/work/name/search",
			method="GET",
			params=params,
		)
		return response.json()

	def search_works_by_name_nemo(self, name: str, limit: int = 20, offset: int = 0) -> dict:
		"""
		通过名称搜索作品 (版本 2)
		Args:
			name: 搜索名称
			limit: 获取数量 (可选)
			offset: 偏移量 (可选)
		Returns:
			搜索结果字典
		"""
		params = {
			"key": name,
			"offset": offset,
			"limit": limit,
		}
		response = self._client.send_request(
			endpoint="/nemo/v2/work/name/search",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_work_by_miao_code(self, token: str) -> dict:
		"""
		根据喵口令获取作品数据
		Args:
			token: 喵口令
		Returns:
			作品数据字典
		"""
		params = {"token": token}
		response = self._client.send_request(
			endpoint="/tiger/nemo/miao-codes",
			method="GET",
			params=params,
		)
		return response.json()


@singleton
class NekoAIServices:
	"""Neko AI 服务类, 包含 AI 相关功能"""

	def __init__(self) -> None:
		"""初始化 Neko AI 服务类"""
		self._client = acquire.CodeMaoClient()

	def fetch_text2img_prompt(self) -> dict:
		"""
		获取文生图提示词
		Returns:
			提示词信息
		"""
		response = self._client.send_request(
			endpoint="/neko/text2img/prompt",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	def fetch_ai_painting_templates(self, template_type: str) -> dict:
		"""
		获取 AI 绘画模板
		Args:
			template_type: 模板类型
		Returns:
			模板列表
		"""
		params = {"type": template_type}
		response = self._client.send_request(
			endpoint="/neko/ai-painting/templates",
			method="GET",
			params=params,
			base_url_key="creation",
		)
		return response.json()

	def match_ai_painting(self, data: dict) -> dict:
		"""
		AI 绘画匹配
		Args:
			data: 匹配参数
		Returns:
			匹配结果
		"""
		response = self._client.send_request(endpoint="/neko/ai-painting/match", method="POST", payload=data, base_url_key="creation")
		return response.json()

	def add_to_inspiration_pool(self, img_url: str, prompt: str, style: str, img_type: str, generation_type: str) -> dict:
		"""
		添加到灵感池
		Args:
			img_url: 图片 URL
			prompt: 提示词
			style: 风格
			img_type: 图片类型
			generation_type: 生成类型
		Returns:
			添加结果
		"""
		data = {"img_url": img_url, "prompt": prompt, "style": style, "img_type": img_type, "generation_type": generation_type}
		response = self._client.send_request(endpoint="/neko/inspiration-pool", method="POST", payload=data, base_url_key="creation")
		return response.json()


@singleton
class NekoPlatformServices:
	"""Neko 平台服务类, 包含社区、素材、排行榜、包管理等功能"""

	def __init__(self) -> None:
		"""初始化 Neko 平台服务类"""
		self._client = acquire.CodeMaoClient()

	def save_teacher_work(self, data: dict) -> dict:
		"""
		保存教师作品
		Args:
			data: 作品数据
		Returns:
			保存结果
		"""
		response = self._client.send_request(endpoint="/neko/works/teacher", method="POST", payload=data, base_url_key="creation")
		return response.json()

	def copy_work(self, work_id: int) -> dict:
		"""
		复制作品
		Args:
			work_id: 源作品 ID
		Returns:
			复制结果
		"""
		data = {"work_id": work_id}
		response = self._client.send_request(endpoint="/neko/works/copy", method="POST", payload=data, base_url_key="creation")
		return response.json()

	def fetch_work_status(self, work_id: int) -> dict:
		"""
		获取作品状态
		Args:
			work_id: 作品 ID
		Returns:
			作品状态信息
		"""
		response = self._client.send_request(endpoint=f"/neko/works/status/{work_id}", method="GET", base_url_key="creation")
		return response.json()

	# 社区相关 API
	def fetch_published_work_detail(self, work_id: int) -> dict:
		"""
		获取已发布作品详情
		Args:
			work_id: 作品 ID
		Returns:
			已发布作品详情
		"""
		response = self._client.send_request(
			endpoint=f"/neko/community/player/published-work-detail/{work_id}",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	# 素材相关 API
	def fetch_material_categories(self, material_type: str) -> dict:
		"""
		获取素材分类
		Args:
			material_type: 素材类型
		Returns:
			分类列表
		"""
		params = {"type": material_type}
		response = self._client.send_request(endpoint="/neko/material/categories", method="GET", params=params, base_url_key="creation")
		return response.json()

	def fetch_material_list(self, second_id: str, limit: int = 20, offset: int = 0) -> dict:
		"""
		获取素材列表
		Args:
			second_id: 二级分类 ID
			limit: 每页数量
			offset: 偏移量
		Returns:
			素材列表
		"""
		params = {"second_id": second_id, "limit": limit, "offset": offset}
		response = self._client.send_request(
			endpoint="/neko/material/list",
			method="GET",
			params=params,
			base_url_key="creation",
		)
		return response.json()

	# 包管理相关 API
	def fetch_package_list(self, package_type: str, limit: int = 20, offset: int = 0) -> dict:
		"""
		获取包列表
		Args:
			package_type: 包类型
			limit: 每页数量
			offset: 偏移量
		Returns:
			包列表
		"""
		params = {"type": package_type, "limit": limit, "offset": offset}
		response = self._client.send_request(endpoint="/neko/package/list", method="GET", params=params, base_url_key="creation")
		return response.json()

	def create_package(self, data: dict) -> dict:
		"""
		创建包
		Args:
			data: 包数据
		Returns:
			创建结果
		"""
		response = self._client.send_request(endpoint="/neko/package", method="POST", payload=data, base_url_key="creation")
		return response.json()

	def update_package(self, package_id: str, name: str, description: str) -> dict:
		"""
		更新包信息
		Args:
			package_id: 包 ID
			name: 新名称
			description: 新描述
		Returns:
			更新结果
		"""
		data = {"name": name, "description": description}
		response = self._client.send_request(endpoint=f"/neko/package/{package_id}", method="PUT", payload=data, base_url_key="creation")
		return response.json()

	def delete_package(self, package_id: str) -> dict:
		"""
		删除包
		Args:
			package_id: 包 ID
		Returns:
			删除结果
		"""
		response = self._client.send_request(
			endpoint=f"/neko/package/{package_id}",
			method="DELETE",
			base_url_key="creation",
		)
		return response.json()

	# 课程相关 API
	def update_course_progress(self, data: dict) -> dict:
		"""
		更新课程进度
		Args:
			data: 进度数据
		Returns:
			更新结果
		"""
		response = self._client.send_request(
			endpoint="/neko/course/user/progress",
			method="POST",
			payload=data,
			base_url_key="creation",
		)
		return response.json()

	def submit_course_work(self, data: dict) -> dict:
		"""
		提交课程作品
		Args:
			data: 作品数据
		Returns:
			提交结果
		"""
		response = self._client.send_request(
			endpoint="/neko/course/user/course-work",
			method="POST",
			payload=data,
			base_url_key="creation",
		)
		return response.json()

	def translate_kitten_work(self, data: dict) -> dict:
		"""
		翻译 Kitten 作品
		Args:
			data: 翻译数据
		Returns:
			翻译结果
		"""
		response = self._client.send_request(
			endpoint="/kitten/work/translate",
			method="POST",
			payload=data,
			base_url_key="creation",
		)
		return response.json()

	# 图像分类相关 API
	def fetch_image_classify_list(self, limit: int = 20, offset: int = 0) -> dict:
		"""
		获取图像分类列表
		Args:
			limit: 每页数量
			offset: 偏移量
		Returns:
			分类列表
		"""
		params = {"limit": limit, "offset": offset}
		response = self._client.send_request(
			endpoint="/neko/image-classify/list",
			method="GET",
			params=params,
			base_url_key="creation",
		)
		return response.json()

	def submit_image_classify(self, data: dict) -> dict:
		"""
		提交图像分类
		Args:
			data: 分类数据
		Returns:
			分类结果
		"""
		response = self._client.send_request(
			endpoint="/neko/image-classify",
			method="POST",
			payload=data,
			base_url_key="creation",
		)
		return response.json()

	def update_image_classify(self, classify_id: str, data: dict) -> dict:
		"""
		更新图像分类
		Args:
			classify_id: 分类 ID
			data: 更新数据
		Returns:
			更新结果
		"""
		response = self._client.send_request(
			endpoint=f"/neko/image-classify/{classify_id}",
			method="PUT",
			payload=data,
			base_url_key="creation",
		)
		return response.json()

	def delete_image_classify(self, classify_id: str) -> dict:
		"""
		删除图像分类
		Args:
			classify_id: 分类 ID
		Returns:
			删除结果
		"""
		response = self._client.send_request(
			endpoint=f"/neko/image-classify/{classify_id}",
			method="DELETE",
			base_url_key="creation",
		)
		return response.json()

	# 教学计划相关 API
	def save_team_work(self, data: dict) -> dict:
		"""
		保存团队作品 (教学计划)
		Args:
			data: 作品数据
		Returns:
			保存结果
		"""
		response = self._client.send_request(
			endpoint="/neko/teaching-plan/save/team/work",
			method="POST",
			payload=data,
			base_url_key="creation",
		)
		return response.json()

	def fetch_teaching_plan_logs(self, work_id: int, offset: int = 0, limit: int = 20) -> dict:
		"""
		获取教学计划操作日志
		Args:
			work_id: 作品 ID
			offset: 偏移量
			limit: 每页数量
		Returns:
			操作日志列表
		"""
		params = {"work_id": work_id, "offset": offset, "limit": limit}
		response = self._client.send_request(
			endpoint="/neko/teaching-plan/list/opr/log",
			method="GET",
			params=params,
			base_url_key="creation",
		)
		return response.json()

	def add_teaching_plan_log(self, data: dict) -> dict:
		"""
		添加教学计划操作日志
		Args:
			data: 日志数据
		Returns:
			添加结果
		"""
		response = self._client.send_request(
			endpoint="/neko/teaching-plan/add/opr/log",
			method="POST",
			payload=data,
			base_url_key="creation",
		)
		return response.json()

	def fetch_work_editing_status(self, work_id: int) -> dict:
		"""
		获取作品编辑状态
		Args:
			work_id: 作品 ID
		Returns:
			编辑状态信息
		"""
		response = self._client.send_request(
			endpoint=f"/neko/teaching-plan/work/editing-status/{work_id}",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	def set_work_editing_status(self, data: dict) -> dict:
		"""
		设置作品编辑状态
		Args:
			data: 状态数据
		Returns:
			设置结果
		"""
		response = self._client.send_request(
			endpoint="/neko/teaching-plan/set/work/editing-status",
			method="POST",
			payload=data,
			base_url_key="creation",
		)
		return response.json()

	# 作品相关补充 API
	def save_teacher_course_invite_url(self, data: dict) -> dict:
		"""
		保存教师课程邀请链接
		Args:
			data: 链接数据
		Returns:
			保存结果
		"""
		response = self._client.send_request(
			endpoint="/neko/works/save-teacher-course-invite-url",
			method="POST",
			payload=data,
			base_url_key="creation",
		)
		return response.json()

	def fetch_player_work_detail(self, work_id: int) -> dict:
		"""
		获取玩家作品详情
		Args:
			work_id: 作品 ID
		Returns:
			作品详情
		"""
		response = self._client.send_request(
			endpoint=f"/neko/works/player/work-detail/{work_id}",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	def fetch_work_by_course_code(self, course_code: str) -> dict:
		"""
		通过课程代码获取作品
		Args:
			course_code: 课程代码
		Returns:
			作品信息
		"""
		params = {"course_code": course_code}
		response = self._client.send_request(
			endpoint="/neko/works/get-player-by-course-code",
			method="GET",
			params=params,
			base_url_key="creation",
		)
		return response.json()

	def troubleshoot_work_pics(self, work_id: int) -> dict:
		"""
		作品图片故障排查
		Args:
			work_id: 作品 ID
		Returns:
			排查结果
		"""
		response = self._client.send_request(
			endpoint=f"/neko/works/pic-troubleshoot/{work_id}",
			method="PUT",
			base_url_key="creation",
		)
		return response.json()

	# 社区相关补充 API
	def check_user_operation_status(self, work_id: int) -> dict:
		"""
		检查用户操作状态
		Args:
			work_id: 作品 ID
		Returns:
			操作状态
		"""
		response = self._client.send_request(
			endpoint=f"/neko/community/check-user-opr-work-status/{work_id}",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	# 示例相关 API
	def fetch_sample_detail(self, params: dict) -> dict:
		"""
		获取示例详情
		Args:
			params: 查询参数
		Returns:
			示例详情
		"""
		response = self._client.send_request(
			endpoint="/neko/sample/detail",
			method="GET",
			params=params,
			base_url_key="creation",
		)
		return response.json()

	def fetch_sample_list(self, subject_id: str) -> dict:
		"""
		获取示例列表
		Args:
			subject_id: 学科 ID
		Returns:
			示例列表
		"""
		params = {"subject_id": subject_id}
		response = self._client.send_request(
			endpoint="/neko/sample/list",
			method="GET",
			params=params,
			base_url_key="creation",
		)
		return response.json()


@singleton
class WoodWorkManager:
	"""海龟编辑器 (Wood) 作品管理类"""

	def __init__(self) -> None:
		"""初始化海龟编辑器作品管理类"""
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
			"file_id": -1,  # 新文件通常用-1
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
