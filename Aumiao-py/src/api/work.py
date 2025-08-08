from collections.abc import Generator
from typing import Literal

from src.utils import acquire
from src.utils.acquire import HTTPSTATUS
from src.utils.decorator import singleton

# 定义HTTP方法选择类型
SelectMethod = Literal["POST", "DELETE"]


@singleton
class WorkManager:
	def __init__(self) -> None:
		"""初始化作品管理类,创建CodeMaoClient实例"""
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
		创建Kitten作品
		Args:
			name: 作品名称
			work_url: 作品URL
			preview: 预览图URL
			version: 作品版本
			orientation: 作品方向(1=横屏,2=竖屏)
			sample_id: 样本ID(可选)
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
			endpoint="https://api-creation.codemao.cn/kitten/r2/work",
			method="POST",
			payload=data,
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
		发布Kitten作品
		Args:
			work_id: 作品ID
			name: 作品名称
			description: 作品描述
			operation: 操作说明
			labels: 作品标签列表
			cover_url: 封面URL
			bcmc_url: BCMC URL
			work_url: 作品URL
			fork_enable: 是否允许分叉(0=不允许,1=允许)
			if_default_cover: 封面类型(1=默认,2=自定义)
			version: 作品版本
			cover_type: 封面类型(可选)
			user_labels: 用户标签列表(可选)
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
			endpoint=f"https://api-creation.codemao.cn/kitten/r2/work/{work_id}/publish",
			method="PUT",
			payload=data,
		)
		return response.status_code == HTTPSTATUS.OK.value

	def create_kn_work(
		self,
		name: str,
		bcm_version: str,
		preview_url: str,
		work_url: str,
		save_type: int = 1,
		stage_type: int = 1,
		work_classify: int = 0,
		hardware_mode: int = 1,
		blink_mode: str = "",
		n_blocks: int = 0,
		n_roles: int = 2,
	) -> dict:
		"""
		创建KN作品或更新作品信息
		Args:
			name: 作品名称
			bcm_version: BCM版本
			preview_url: 预览URL
			work_url: 作品URL
			save_type: 保存类型(可选)
			stage_type: 舞台类型(可选)
			work_classify: 作品分类(可选)
			hardware_mode: 硬件模式(可选)
			blink_mode: 闪烁模式(可选)
			n_blocks: 积木数量(可选)
			n_roles: 角色数量(可选)
		Returns:
			创建的作品信息字典
		"""
		data = {
			"name": name,
			"bcm_version": bcm_version,
			"preview_url": preview_url,
			"work_url": work_url,
			"save_type": save_type,
			"stage_type": stage_type,
			"work_classify": work_classify,
			"hardware_mode": hardware_mode,
			"blink_mode": blink_mode,
			"n_blocks": n_blocks,
			"n_roles": n_roles,
		}
		response = self._client.send_request(
			endpoint="https://api-creation.codemao.cn/neko/works",
			method="POST",
			payload=data,
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
		发布KN作品
		Args:
			work_id: 作品ID
			name: 作品名称
			preview_url: 预览URL
			description: 作品描述
			operation: 操作说明
			fork_enable: 分叉权限(0=不允许,1=允许,2=仅粉丝允许)
			if_default_cover: 封面类型(1=默认,2=自定义)
			bcmc_url: BCMC URL
			work_url: 作品URL
			bcm_version: BCM版本
			cover_url: 封面URL(可选)
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
			endpoint=f"https://api-creation.codemao.cn/neko/community/work/publish/{work_id}",
			method="POST",
			payload=data,
		)
		return response.status_code == HTTPSTATUS.OK.value

	def execute_toggle_follow(self, user_id: int, method: SelectMethod = "POST") -> bool:
		"""
		关注或取消关注用户
		Args:
			user_id: 用户ID
			method: HTTP方法(POST=关注,DELETE=取消关注)
		Returns:
			操作是否成功
		"""
		response = self._client.send_request(
			endpoint=f"/nemo/v2/user/{user_id}/follow",
			method=method,
			payload={},
		)
		return response.status_code == HTTPSTATUS.NO_CONTENT.value

	def execute_toggle_collection(self, work_id: int, method: SelectMethod = "POST") -> bool:
		"""
		收藏或取消收藏作品
		Args:
			work_id: 作品ID
			method: HTTP方法(POST=收藏,DELETE=取消收藏)
		Returns:
			操作是否成功
		"""
		response = self._client.send_request(
			endpoint=f"/nemo/v2/works/{work_id}/collection",
			method=method,
			payload={},
		)
		return response.status_code == HTTPSTATUS.OK.value

	def execute_toggle_like(self, work_id: int, method: SelectMethod = "POST") -> bool:
		"""
		点赞或取消点赞作品
		Args:
			work_id: 作品ID
			method: HTTP方法(POST=点赞,DELETE=取消点赞)
		Returns:
			操作是否成功
		"""
		response = self._client.send_request(
			endpoint=f"/nemo/v2/works/{work_id}/like",
			method=method,
			payload={},
		)
		return response.status_code == HTTPSTATUS.OK.value

	def execute_share_work(self, work_id: int) -> bool:
		"""
		分享作品
		Args:
			work_id: 作品ID
		Returns:
			分享是否成功
		"""
		response = self._client.send_request(
			endpoint=f"/nemo/v2/works/{work_id}/share",
			method="POST",
			payload={},
		)
		return response.status_code == HTTPSTATUS.OK.value

	def create_work_comment(self, work_id: int, comment: str, emoji: str | None = None, *, return_data: bool = False) -> bool | dict:
		"""
		添加作品评论
		Args:
			work_id: 作品ID
			comment: 评论内容
			emoji: 表情内容(可选)
			return_data: 是否返回完整响应数据
		Returns:
			操作结果(成功状态或完整响应数据)
		"""
		response = self._client.send_request(
			endpoint=f"/creation-tools/v1/works/{work_id}/comment",
			method="POST",
			payload={
				"content": comment,
				"emoji_content": emoji,
			},
		)
		return response.json() if return_data else response.status_code == HTTPSTATUS.CREATED.value

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
			work_id: 作品ID
			comment_id: 评论ID
			parent_id: 父评论ID(可选)
			return_data: 是否返回完整响应数据
		Returns:
			操作结果(成功状态或完整响应数据)
		"""
		data = {"parent_id": parent_id, "content": comment}
		response = self._client.send_request(
			endpoint=f"/creation-tools/v1/works/{work_id}/comment/{comment_id}/reply",
			method="POST",
			payload=data,
		)
		return response.json() if return_data else response.status_code == HTTPSTATUS.CREATED.value

	def delete_comment(self, work_id: int, comment_id: int, **_: object) -> bool:
		"""
		删除作品评论
		Args:
			work_id: 作品ID
			comment_id: 评论ID
		Returns:
			删除是否成功
		"""
		response = self._client.send_request(
			endpoint=f"/creation-tools/v1/works/{work_id}/comment/{comment_id}",
			method="DELETE",
		)
		return response.status_code == HTTPSTATUS.NO_CONTENT.value

	def execute_report_work(self, describe: str, reason: str, work_id: int) -> bool:
		"""
		举报作品
		Args:
			describe: 举报描述
			reason: 举报原因
			work_id: 作品ID
		Returns:
			举报是否成功
		"""
		data = {
			"work_id": work_id,
			"report_reason": reason,
			"report_describe": describe,
		}
		response = self._client.send_request(endpoint="/nemo/v2/report/work", method="POST", payload=data)
		return response.status_code == HTTPSTATUS.OK.value

	def execute_toggle_comment_pin(
		self,
		method: Literal["PUT", "DELETE"],
		work_id: int,
		comment_id: int,
		*,
		return_data: bool = False,
	) -> bool:
		"""
		置顶或取消置顶评论
		Args:
			method: HTTP方法(PUT=置顶,DELETE=取消置顶)
			work_id: 作品ID
			comment_id: 评论ID
			return_data: 是否返回完整响应数据
		Returns:
			操作结果(成功状态或完整响应数据)
		"""
		response = self._client.send_request(endpoint=f"/creation-tools/v1/works/{work_id}/comment/{comment_id}/top", method=method, payload={})
		return response.json() if return_data else response.status_code == HTTPSTATUS.NO_CONTENT.value

	def execute_toggle_comment_like(self, work_id: int, comment_id: int, method: SelectMethod = "POST") -> bool:
		"""
		点赞或取消点赞评论
		Args:
			work_id: 作品ID
			comment_id: 评论ID
			method: HTTP方法(POST=点赞,DELETE=取消点赞)
		Returns:
			操作是否成功
		"""
		response = self._client.send_request(
			endpoint=f"/creation-tools/v1/works/{work_id}/comment/{comment_id}/liked",
			method=method,
			payload={},
		)
		return response.status_code == HTTPSTATUS.CREATED.value

	def execute_report_comment(self, work_id: int, comment_id: int, reason: str) -> bool:
		"""
		举报作品评论
		Args:
			work_id: 作品ID
			comment_id: 评论ID
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
		return response.status_code == HTTPSTATUS.OK.value

	def execute_enable_collaboration(self, work_id: int) -> bool:
		"""
		启用作品协作功能
		Args:
			work_id: 作品ID
		Returns:
			操作是否成功
		"""
		response = self._client.send_request(
			endpoint=f"https://socketcoll.codemao.cn/coll/kitten/{work_id}",
			method="POST",
			payload={},
		)
		return response.status_code == HTTPSTATUS.OK.value

	def delete_kitten_draft(self, work_id: int) -> bool:
		"""
		删除未发布的Kitten作品草稿
		Args:
			work_id: 作品ID
		Returns:
			删除是否成功
		"""
		response = self._client.send_request(
			endpoint=f"https://api-creation.codemao.cn/kitten/common/work/{work_id}/temporarily",
			method="DELETE",
		)
		return response.status_code == HTTPSTATUS.OK.value

	def delete_kn_draft(self, work_id: int, force: Literal[1, 2]) -> bool:
		"""
		删除未发布的KN作品草稿
		Args:
			work_id: 作品ID
			force: 强制删除模式(1=网页端,2=手机端)
		Returns:
			删除是否成功
		"""
		params = {"force": force}
		response = self._client.send_request(
			endpoint=f"https://api-creation.codemao.cn/neko/works/{work_id}",
			method="DELETE",
			params=params,
		)
		return response.status_code == HTTPSTATUS.OK.value

	def execute_unpublish_work(self, work_id: int) -> bool:
		"""
		取消发布作品
		Args:
			work_id: 作品ID
		Returns:
			操作是否成功
		"""
		response = self._client.send_request(
			endpoint=f"/tiger/work/{work_id}/unpublish",
			method="PATCH",
			payload={},
		)
		return response.status_code == HTTPSTATUS.NO_CONTENT.value

	def execute_unpublish_work_web(self, work_id: int) -> bool:
		"""
		通过Web端取消发布作品
		Args:
			work_id: 作品ID
		Returns:
			操作是否成功
		"""
		response = self._client.send_request(
			endpoint=f"/web/works/r2/unpublish/{work_id}",
			method="PUT",
			payload={},
		)
		return response.status_code == HTTPSTATUS.OK.value

	def execute_unpublish_kn_work(self, work_id: int) -> bool:
		"""
		取消发布KN作品
		Args:
			work_id: 作品ID
		Returns:
			操作是否成功
		"""
		response = self._client.send_request(
			endpoint=f"https://api-creation.codemao.cn/neko/community/work/unpublish/{work_id}",
			method="PUT",
		)
		return response.status_code == HTTPSTATUS.OK.value

	def execute_empty_kitten_trash(self) -> bool:
		"""
		清空Kitten作品回收站
		Returns:
			操作是否成功
		"""
		response = self._client.send_request(
			endpoint="https://api-creation.codemao.cn/work/user/works/permanently",
			method="DELETE",
		)
		return response.status_code == HTTPSTATUS.NO_CONTENT.value

	def execute_empty_kn_trash(self) -> bool:
		"""
		清空KN作品回收站
		Returns:
			操作是否成功
		"""
		response = self._client.send_request(
			endpoint="https://api-creation.codemao.cn/neko/works/permanently",
			method="DELETE",
		)
		return response.status_code == HTTPSTATUS.OK.value

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
			work_id: 作品ID
			name: 新名称
			work_type: 作品类型(可选)
			is_check_name: 是否检查名称有效性(可选)
		Returns:
			重命名是否成功
		"""
		response = self._client.send_request(
			endpoint=f"/tiger/work/works/{work_id}/rename",
			method="PATCH",
			params={"is_check_name": is_check_name, "name": name, "work_type": work_type},
		)
		return response.status_code == HTTPSTATUS.OK.value


@singleton
class WorkDataFetcher:
	def __init__(self) -> None:
		"""初始化作品数据获取类"""
		self._client = acquire.CodeMaoClient()

	def fetch_work_comments_gen(self, work_id: int, limit: int = 15) -> Generator:
		"""
		获取作品评论生成器
		Args:
			work_id: 作品ID
			limit: 获取评论数量限制
		Returns:
			评论数据生成器
		"""
		params = {"limit": 15, "offset": 0}
		return self._client.fetch_data(
			endpoint=f"/creation-tools/v1/works/{work_id}/comments",
			params=params,
			total_key="page_total",
			limit=limit,
		)

	def fetch_work_details(self, work_id: int) -> dict:
		"""
		获取作品详细信息
		Args:
			work_id: 作品ID
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
		获取Kitten作品详细信息
		Args:
			work_id: 作品ID
		Returns:
			Kitten作品详细信息字典
		"""
		response = self._client.send_request(
			endpoint=f"https://api-creation.codemao.cn/kitten/work/detail/{work_id}",
			method="GET",
		)
		return response.json()

	def fetch_kn_work_details(self, work_id: int) -> dict:
		"""
		获取KN作品详细信息
		Args:
			work_id: 作品ID
		Returns:
			KN作品详细信息字典
		"""
		response = self._client.send_request(
			endpoint=f"https://api-creation.codemao.cn/neko/works/{work_id}",
			method="GET",
		)
		return response.json()

	def fetch_kn_publish_status(self, work_id: int) -> dict:
		"""
		获取KN作品发布状态
		Args:
			work_id: 作品ID
		Returns:
			发布状态信息字典
		"""
		response = self._client.send_request(
			endpoint=f"https://api-creation.codemao.cn/neko/community/work/detail/{work_id}",
			method="GET",
		)
		return response.json()

	def fetch_kn_work_state(self, work_id: int) -> dict:
		"""
		获取KN作品状态
		Args:
			work_id: 作品ID
		Returns:
			作品状态信息字典
		"""
		response = self._client.send_request(
			endpoint=f"https://api-creation.codemao.cn/neko/works/status/{work_id}",
			method="GET",
		)
		return response.json()

	def fetch_web_recommendations(self, work_id: int) -> dict:
		"""
		获取Web端相关作品推荐
		Args:
			work_id: 作品ID
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
		获取Nemo端相关作品推荐
		Args:
			work_id: 作品ID
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
			work_id: 作品ID
		Returns:
			作品元数据字典
		"""
		response = self._client.send_request(endpoint=f"/api/work/info/{work_id}", method="GET")
		return response.json()

	def fetch_work_tags(self, work_id: int) -> dict:
		"""
		获取作品标签
		Args:
			work_id: 作品ID
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
		获取所有Kitten作品标签
		Returns:
			Kitten标签列表字典
		"""
		response = self._client.send_request(endpoint="https://api-creation.codemao.cn/kitten/work/labels", method="GET")
		return response.json()

	def fetch_kitten_default_covers(self) -> dict:
		"""
		获取Kitten默认封面
		Returns:
			默认封面列表字典
		"""
		response = self._client.send_request(
			endpoint="https://api-creation.codemao.cn/kitten/work/cover/defaultCovers",
			method="GET",
		)
		return response.json()

	def fetch_recent_covers(self, work_id: int) -> dict:
		"""
		获取作品最近使用的封面
		Args:
			work_id: 作品ID
		Returns:
			最近封面列表字典
		"""
		response = self._client.send_request(
			endpoint=f"https://api-creation.codemao.cn/kitten/work/cover/{work_id}/recentCovers",
			method="GET",
		)
		return response.json()

	def validate_work_name(self, name: str, work_id: int) -> dict:
		"""
		验证作品名称是否可用
		Args:
			name: 作品名称
			work_id: 作品ID(可选)
		Returns:
			验证结果字典
		"""
		params = {"name": name, "work_id": work_id}
		response = self._client.send_request(endpoint="/tiger/work/checkname", method="GET", params=params)
		return response.json()

	def fetch_author_portfolio(self, user_id: str) -> dict:
		"""
		获取作者作品集
		Args:
			user_id: 用户ID
		Returns:
			作者作品集字典
		"""
		response = self._client.send_request(endpoint=f"/web/works/users/{user_id}", method="GET")
		return response.json()

	def fetch_work_source_code(self, work_id: int) -> dict:
		"""
		获取作品源代码
		Args:
			work_id: 作品ID
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
		获取Web端最新作品
		Args:
			limit: 获取数量
			offset: 偏移量(可选)
			origin: 是否只获取原创作品(可选)
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
		获取Web端主题作品
		Args:
			limit: 获取数量
			offset: 偏移量(可选)
			subject_id: 主题ID(可选)
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
		获取Nemo端发现页作品
		Returns:
			发现页作品列表字典
		"""
		response = self._client.send_request(endpoint="/creation-tools/v1/home/discover", method="GET")
		return response.json()

	def fetch_new_works_nemo(
		self,
		types: Literal["course-work", "template", "original", "fork"],
		limit: int = 15,
		offset: int = 0,
	) -> dict:
		"""
		获取Nemo端最新作品
		Args:
			types: 作品类型
			limit: 获取数量(可选)
			offset: 偏移量(可选)
		Returns:
			最新作品列表字典
		"""
		params = {"limit": limit, "offset": offset}
		response = self._client.send_request(endpoint=f"/nemo/v3/newest/work/{types}/list", method="GET", params=params)
		return response.json()

	def fetch_random_subjects(self) -> list[int]:
		"""
		获取随机作品主题ID列表
		Returns:
			主题ID列表
		"""
		response = self._client.send_request(endpoint="/nemo/v3/work-subject/random", method="GET")
		return response.json()

	def fetch_subject_details(self, ids: int) -> dict:
		"""
		获取主题详细信息
		Args:
			ids: 主题ID
		Returns:
			主题信息字典
		"""
		response = self._client.send_request(endpoint=f"/nemo/v3/work-subject/{ids}/info", method="GET")
		return response.json()

	def fetch_subject_works(self, ids: int, limit: int = 15, offset: int = 0) -> dict:
		"""
		获取主题下作品
		Args:
			ids: 主题ID
			limit: 获取数量(可选)
			offset: 偏移量(可选)
		Returns:
			主题作品列表字典
		"""
		params = {"limit": limit, "offset": offset}
		response = self._client.send_request(endpoint=f"/nemo/v3/work-subject/{ids}/works", method="GET", params=params)
		return response.json()

	def fetch_all_subject_works(self, limit: int = 15, offset: int = 0) -> dict:
		"""
		获取所有主题作品
		Args:
			limit: 获取数量(可选)
			offset: 偏移量(可选)
		Returns:
			主题作品列表字典
		"""
		params = {"limit": limit, "offset": offset}
		response = self._client.send_request(endpoint="/nemo/v3/work-subject/home", method="GET", params=params)
		return response.json()

	def manage_collaboration_code(self, work_id: int, method: Literal["GET", "DELETE"] = "GET") -> dict:
		"""
		获取或删除协作邀请码
		Args:
			work_id: 作品ID
			method: HTTP方法(GET=获取,DELETE=删除)
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
			work_id: 作品ID
			limit: 获取数量限制(可选)
		Returns:
			协作者列表生成器
		"""
		params = {"current_page": 1, "page_size": 100}
		return self._client.fetch_data(
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
			work_id: 作品ID
		Returns:
			协作状态字典
		"""
		response = self._client.send_request(
			endpoint=f"https://api-creation.codemao.cn/collaboration/user/{work_id}",
			method="GET",
		)
		return response.json()

	def fetch_work_lineage_web(self, work_id: int) -> dict:
		"""
		获取Web端作品谱系
		Args:
			work_id: 作品ID
		Returns:
			谱系信息字典
		"""
		response = self._client.send_request(endpoint=f"/tiger/work/tree/{work_id}", method="GET")
		return response.json()

	def fetch_work_lineage_nemo(self, work_id: int) -> dict:
		"""
		获取Nemo端作品谱系
		Args:
			work_id: 作品ID
		Returns:
			谱系信息字典
		"""
		response = self._client.send_request(endpoint=f"/nemo/v2/works/root/{work_id}", method="GET")
		return response.json()

	def fetch_kn_work_versions(self, work_id: int) -> dict:
		"""
		获取KN作品历史版本
		Args:
			work_id: 作品ID
		Returns:
			版本历史字典
		"""
		response = self._client.send_request(
			endpoint=f"https://api-creation.codemao.cn/neko/works/archive/{work_id}",
			method="GET",
		)
		return response.json()

	def fetch_kitten_trash_gen(self, version_no: Literal["KITTEN_V3", "KITTEN_V4"], work_status: str = "CYCLED", limit: int | None = 30) -> Generator[dict]:
		"""
		获取Kitten回收站作品生成器
		Args:
			version_no: 版本号
			work_status: 作品状态(可选)
			limit: 获取数量限制(可选)
		Returns:
			回收站作品生成器
		"""
		params = {
			"limit": 30,
			"offset": 0,
			"version_no": version_no,
			"work_status": work_status,
		}
		return self._client.fetch_data(
			endpoint="https://api-creation.codemao.cn/tiger/work/recycle/list",
			params=params,
			limit=limit,
		)

	def fetch_wood_trash_gen(self, language_type: int = 0, work_status: str = "CYCLED", published_status: str = "undefined", limit: int | None = 30) -> Generator[dict]:
		"""
		获取海龟编辑器回收站作品生成器
		Args:
			language_type: 语言类型(可选)
			work_status: 作品状态(可选)
			published_status: 发布状态(可选)
			limit: 获取数量限制(可选)
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
		return self._client.fetch_data(
			endpoint="https://api-creation.codemao.cn/wood/comm/work/list",
			params=params,
			limit=limit,
		)

	def fetch_box_trash_gen(self, work_status: str = "CYCLED", limit: int | None = 30) -> Generator[dict]:
		"""
		获取代码岛回收站作品生成器
		Args:
			work_status: 作品状态(可选)
			limit: 获取数量限制(可选)
		Returns:
			回收站作品生成器
		"""
		params = {
			"limit": 30,
			"offset": 0,
			"work_status": work_status,
		}
		return self._client.fetch_data(
			endpoint="https://api-creation.codemao.cn/box/v2/work/list",
			params=params,
			limit=limit,
		)

	def fetch_fiction_trash_gen(self, fiction_status: str = "CYCLED", limit: int | None = 30) -> Generator[dict]:
		"""
		获取小说回收站生成器
		Args:
			fiction_status: 小说状态(可选)
			limit: 获取数量限制(可选)
		Returns:
			回收站生成器
		"""
		params = {
			"limit": 30,
			"offset": 0,
			"fiction_status": fiction_status,
		}
		return self._client.fetch_data(
			endpoint="/web/fanfic/my/new",
			params=params,
			limit=limit,
		)

	def fetch_kn_trash_gen(self, name: str = "", work_business_classify: int = 1, limit: int | None = 24) -> Generator[dict]:
		"""
		获取KN回收站作品生成器
		Args:
			name: 搜索名称(可选)
			work_business_classify: 作品业务分类(可选)
			limit: 获取数量限制(可选)
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
		return self._client.fetch_data(
			endpoint="https://api-creation.codemao.cn/neko/works/v2/list/user",
			params=params,
			limit=limit,
		)

	def search_kn_works_gen(self, name: str, status: int = 1, work_business_classify: int = 1, limit: int | None = 24) -> Generator[dict]:
		"""
		搜索KN作品生成器
		Args:
			name: 搜索名称
			status: 作品状态(可选)
			work_business_classify: 作品业务分类(可选)
			limit: 获取数量限制(可选)
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
		return self._client.fetch_data(
			endpoint="https://api-creation.codemao.cn/neko/works/v2/list/user",
			params=params,
			limit=limit,
		)

	def search_published_kn_works_gen(self, name: str, work_business_classify: int = 1, limit: int | None = 24) -> Generator[dict]:
		"""
		搜索已发布KN作品生成器
		Args:
			name: 搜索名称
			work_business_classify: 作品业务分类(可选)
			limit: 获取数量限制(可选)
		Returns:
			作品生成器
		"""
		params = {
			"name": name,
			"limit": 24,
			"offset": 0,
			"work_business_classify": work_business_classify,
		}
		return self._client.fetch_data(
			endpoint="https://api-creation.codemao.cn/neko/works/list/user/published",
			params=params,
			limit=limit,
		)

	def fetch_kn_variables(self, work_id: int) -> dict:
		"""
		获取KN作品变量列表
		Args:
			work_id: 作品ID
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
			types: 资源类型(block=积木,character=角色)
			limit: 获取数量(可选)
			offset: 偏移量(可选)
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
			endpoint="https://api-creation.codemao.cn/neko/package/list",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_activity_feed(self, limit: int = 15, offset: int = 0) -> dict:
		"""
		获取动态作品
		Args:
			limit: 获取数量(可选)
			offset: 偏移量(可选)
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
			limit: 获取数量(可选)
			offset: 偏移量(可选)
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
		通过名称搜索作品(版本2)
		Args:
			name: 搜索名称
			limit: 获取数量(可选)
			offset: 偏移量(可选)
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
