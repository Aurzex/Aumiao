from collections.abc import Generator
from typing import Literal

from src.utils import acquire, tool
from src.utils.acquire import HTTPSTATUS
from src.utils.decorator import singleton

select = Literal["POST", "DELETE"]


@singleton
class Motion:
	def __init__(self) -> None:
		# 初始化Motion类,创建一个CodeMaoClient实例
		self.acquire = acquire.CodeMaoClient()

	# 新建kitten作品
	def create_work_kitten(
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
		# 创建一个kitten作品
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
		# 发送请求
		response = self.acquire.send_request(
			endpoint="https://api-creation.codemao.cn/kitten/r2/work",
			method="POST",
			payload=data,
		)
		# 返回响应
		return response.json()

	# 发布kitten作品
	def publish_work_kitten(
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
		# 发布一个kitten作品
		# fork_enable: 0表示不开源,1表示开源
		# if_default_cover: 1表示使用默认封面,2表示自定义封面
		# 构造请求参数
		# description: 作品描述,operation:操作说明
		# 获取数据
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
		response = self.acquire.send_request(
			endpoint=f"https://api-creation.codemao.cn/kitten/r2/work/{work_id}/publish",
			method="PUT",
			payload=data,
		)
		# 返回响应
		return response.status_code == HTTPSTATUS.OK

	# 新建KN作品/更新作品信息
	# 更新作品时会在更新之前运行该函数,之后再publish
	def create_work_kn(
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
		# 创建一个KN作品/更新作品信息
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
		response = self.acquire.send_request(
			endpoint="https://api-creation.codemao.cn/neko/works",
			method="POST",
			payload=data,
		)
		# 返回响应
		return response.json()

	# 发布KN作品
	def publish_work_kn(
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
		# 发布一个KN作品
		# fork_enable: 0表示不开源,1表示开源,2表示对粉丝开源
		# if_default_cover: 1表示使用默认封面,2表示自定义封面
		# description: 作品描述,operation:操作说明
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
		response = self.acquire.send_request(
			endpoint=f"https://api-creation.codemao.cn/neko/community/work/publish/{work_id}",
			method="POST",
			payload=data,
		)
		return response.status_code == HTTPSTATUS.OK

	# 关注的函数
	def follow_work(self, user_id: int, method: select = "POST") -> bool:
		response = self.acquire.send_request(
			endpoint=f"/nemo/v2/user/{user_id}/follow",
			method=method,
			payload={},
		)

		return response.status_code == HTTPSTATUS.NO_CONTENT

	# 收藏的函数
	def collection_work(self, work_id: int, method: select = "POST") -> bool:
		response = self.acquire.send_request(
			endpoint=f"/nemo/v2/works/{work_id}/collection",
			method=method,
			payload={},
		)
		return response.status_code == HTTPSTATUS.OK

	# 点赞的函数
	def like_work(self, work_id: int, method: select = "POST") -> bool:
		# 对某个作品进行点赞
		response = self.acquire.send_request(
			endpoint=f"/nemo/v2/works/{work_id}/like",
			method=method,
			payload={},
		)
		return response.status_code == HTTPSTATUS.OK

	# 分享的函数
	def share_work(self, work_id: int) -> bool:
		response = self.acquire.send_request(
			endpoint=f"/nemo/v2/works/{work_id}/share",
			method="POST",
			payload={},
		)
		return response.status_code == HTTPSTATUS.OK

	# 对某个作品进行评论的函数
	def comment_work(self, work_id: int, comment: str, emoji: str | None = None, *, return_data: bool = False) -> bool | dict:
		response = self.acquire.send_request(
			endpoint=f"/creation-tools/v1/works/{work_id}/comment",
			method="POST",
			payload={
				"content": comment,
				"emoji_content": emoji,
			},
		)
		return response.json() if return_data else response.status_code == HTTPSTATUS.CREATED

	# 对某个作品下评论进行回复
	def reply_work(
		self,
		comment: str,
		work_id: int,
		comment_id: int,
		parent_id: int = 0,
		*,
		return_data: bool = False,
	) -> bool | dict:
		data = {"parent_id": parent_id, "content": comment}
		response = self.acquire.send_request(
			endpoint=f"/creation-tools/v1/works/{work_id}/comment/{comment_id}/reply",
			method="POST",
			payload=data,
		)
		return response.json() if return_data else response.status_code == HTTPSTATUS.CREATED

	# 删除作品某个评论或评论的回复(评论和回复都会分配一个唯一id)
	def del_comment_work(self, work_id: int, comment_id: int, **_: object) -> bool:
		response = self.acquire.send_request(
			endpoint=f"/creation-tools/v1/works/{work_id}/comment/{comment_id}",
			method="DELETE",
		)
		return response.status_code == HTTPSTATUS.NO_CONTENT

	# 对某个作品举报
	def report_work(self, describe: str, reason: str, work_id: int) -> bool:
		data = {
			"work_id": work_id,
			"report_reason": reason,
			"report_describe": describe,
		}

		response = self.acquire.send_request(endpoint="/nemo/v2/report/work", method="POST", payload=data)
		return response.status_code == HTTPSTATUS.OK

	# 设置某个评论置顶
	def set_comment_top(
		self,
		method: Literal["PUT", "DELETE"],
		work_id: int,
		comment_id: int,
		*,
		return_data: bool = False,
	) -> bool:
		response = self.acquire.send_request(endpoint=f"/creation-tools/v1/works/{work_id}/comment/{comment_id}/top", method=method, payload={})

		return response.json() if return_data else response.status_code == HTTPSTATUS.NO_CONTENT

	# 点赞作品的评论
	def like_comment_work(self, work_id: int, comment_id: int, method: select = "POST") -> bool:
		response = self.acquire.send_request(endpoint=f"/creation-tools/v1/works/{work_id}/comment/{comment_id}/liked", method=method, payload={})
		return response.status_code == HTTPSTATUS.CREATED

	# 举报作品的评论
	def report_comment_work(self, work_id: int, comment_id: int, reason: str) -> bool:
		data = {
			"comment_id": comment_id,
			"report_reason": reason,
		}
		response = self.acquire.send_request(
			endpoint=f"/creation-tools/v1/works/{work_id}/comment/report",
			method="POST",
			payload=data,
		)
		return response.status_code == HTTPSTATUS.OK

	# 将一个作品设置为协作作品
	def set_coll_work(self, work_id: int) -> bool:
		response = self.acquire.send_request(
			endpoint=f"https://socketcoll.codemao.cn/coll/kitten/{work_id}",
			method="POST",
			payload={},
		)
		return response.status_code == HTTPSTATUS.OK

	# 删除一个未发布的作品
	def delete_temp_work_kitten(self, work_id: int) -> bool:
		response = self.acquire.send_request(
			endpoint=f"https://api-creation.codemao.cn/kitten/common/work/{work_id}/temporarily",
			method="DELETE",
		)
		return response.status_code == HTTPSTATUS.OK

	# 删除一个kn作品
	# force疑似1为网页端删除,2为手机端删除
	def delete_temp_work_kn(self, work_id: int, force: Literal[1, 2]) -> bool:
		params = {"force": force}
		response = self.acquire.send_request(
			endpoint=f"https://api-creation.codemao.cn/neko/works/{work_id}",
			method="DELETE",
			params=params,
		)
		return response.status_code == HTTPSTATUS.OK

	# 取消发布一个已发布的作品
	def unpublish_work(self, work_id: int) -> bool:
		response = self.acquire.send_request(
			endpoint=f"/tiger/work/{work_id}/unpublish",
			method="PATCH",
			payload={},
		)
		return response.status_code == HTTPSTATUS.NO_CONTENT

	# 取消发布一个已发布的作品
	def unpublish_work_web(self, work_id: int) -> bool:
		response = self.acquire.send_request(
			endpoint=f"/web/works/r2/unpublish/{work_id}",
			method="PUT",
			payload={},
		)
		return response.status_code == HTTPSTATUS.OK

	# 取消发布一个已发布的KN作品
	def unpublish_kn_work(self, work_id: int) -> bool:
		response = self.acquire.send_request(
			endpoint=f"https://api-creation.codemao.cn/neko/community/work/unpublish/{work_id}",
			method="PUT",
		)
		return response.status_code == HTTPSTATUS.OK

	# 清空回收站kitten作品
	def clear_recycle_kitten_works(self) -> bool:
		response = self.acquire.send_request(
			endpoint="https://api-creation.codemao.cn/work/user/works/permanently",
			method="DELETE",
		)

		return response.status_code == HTTPSTATUS.NO_CONTENT

	#  清空回收站KN作品
	def clear_recycle_kn_works(self) -> bool:
		response = self.acquire.send_request(
			endpoint="https://api-creation.codemao.cn/neko/works/permanently",
			method="DELETE",
		)

		return response.status_code == HTTPSTATUS.OK

	# 重命名作品
	# TODO@Aurzex: work_type未知,应该是作品标签?work_type可有可无,抓包抓出来有个值为8
	def rename_work(
		self,
		work_id: int,
		name: str,
		work_type: int | None = None,
		*,
		is_check_name: Literal[True, False] = False,
	) -> bool:
		response = self.acquire.send_request(
			endpoint=f"/tiger/work/works/{work_id}/rename",
			method="PATCH",
			params={"is_check_name": is_check_name, "name": name, "work_type": work_type},
		)
		return response.status_code == HTTPSTATUS.OK


@singleton
class Obtain:
	def __init__(self) -> None:
		# 初始化获取数据类
		self.acquire = acquire.CodeMaoClient()
		self.tool = tool.CodeMaoProcess()

	# 获取评论区评论
	def get_work_comments(self, work_id: int, limit: int = 15) -> Generator:
		# 设置参数
		params = {"limit": 15, "offset": 0}
		# 获取数据
		return self.acquire.fetch_data(
			endpoint=f"/creation-tools/v1/works/{work_id}/comments",
			params=params,
			total_key="page_total",
			limit=limit,
			args={},
		)

	# 获取作品信息
	def get_work_detail(self, work_id: int) -> dict:
		# 发送请求获取数据
		response = self.acquire.send_request(
			endpoint=f"/creation-tools/v1/works/{work_id}",
			method="GET",
		)
		# 返回数据
		return response.json()

	# 获取kitten作品信息
	def get_kitten_work_detail(self, work_id: int) -> dict:
		# 发送请求获取数据
		response = self.acquire.send_request(
			endpoint=f"https://api-creation.codemao.cn/kitten/work/detail/{work_id}",
			method="GET",
		)
		# 返回数据
		return response.json()

	# 获取KN作品信息
	def get_kn_work_detail(self, work_id: int) -> dict:
		# 发送请求获取数据
		response = self.acquire.send_request(
			endpoint=f"https://api-creation.codemao.cn/neko/works/{work_id}",
			method="GET",
		)
		# 返回数据
		return response.json()

	# 获取KN作品信息
	# KN作品发布需要审核,发布后该接口不断定时获取数据
	# #若接口数据返回正常,则表示发布成功,并将KN作品编辑页面的发布按钮改为更新
	def get_kn_work_info(self, work_id: int) -> dict:
		# 发送请求获取数据
		response = self.acquire.send_request(
			endpoint=f"https://api-creation.codemao.cn/neko/community/work/detail/{work_id}",
			method="GET",
		)
		# 返回数据
		return response.json()

	# 获取KN作品状态
	def get_kn_work_status(self, work_id: int) -> dict:
		# 发送请求获取数据
		response = self.acquire.send_request(
			endpoint=f"https://api-creation.codemao.cn/neko/works/status/{work_id}",
			method="GET",
		)
		# 返回数据
		return response.json()

	# 获取其他作品推荐_web端
	def get_other_recommended_web(self, work_id: int) -> dict:
		# 发送请求获取数据
		response = self.acquire.send_request(
			endpoint=f"/nemo/v2/works/web/{work_id}/recommended",
			method="GET",
		)
		# 返回数据
		return response.json()

	# 获取其他作品推荐_nemo端
	def get_other_recommended_nemo(self, work_id: int) -> dict:
		# 设置参数
		params = {"work_id": work_id}
		# 发送请求获取数据
		response = self.acquire.send_request(
			endpoint="/nemo/v3/work-details/recommended/list",
			method="GET",
			params=params,
		)
		# 返回数据
		return response.json()

	# 获取作品信息(info)
	def get_work_info(self, work_id: int) -> dict:
		# 发送请求获取数据
		response = self.acquire.send_request(endpoint=f"/api/work/info/{work_id}", method="GET")
		# 返回数据
		return response.json()

	# 获取作品标签
	def get_work_label(self, work_id: int) -> dict:
		# 设置参数
		params = {"work_id": work_id}
		# 发送请求获取数据
		response = self.acquire.send_request(
			endpoint="/creation-tools/v1/work-details/work-labels",
			method="GET",
			params=params,
		)
		# 返回数据
		return response.json()

	# 获取所有kitten作品标签
	def get_kitten_work_label(self) -> dict:
		# 发送请求获取数据
		response = self.acquire.send_request(endpoint="https://api-creation.codemao.cn/kitten/work/labels", method="GET")
		return response.json()

	# 获取所有kitten默认封面
	def get_kitten_default_cover(self) -> dict:
		response = self.acquire.send_request(
			endpoint="https://api-creation.codemao.cn/kitten/work/cover/defaultCovers",
			method="GET",
		)
		return response.json()

	# TODO@Aurzex: 功能未知
	def get_works_recent_cover(self, work_id: int) -> dict:
		response = self.acquire.send_request(
			endpoint=f"https://api-creation.codemao.cn/kitten/work/cover/{work_id}/recentCovers",
			method="GET",
		)
		return response.json()

	# 检查作品名称是否可用
	def check_work_name(self, name: str, work_id: int) -> dict:
		params = {"name": name, "work_id": work_id}
		response = self.acquire.send_request(endpoint="/tiger/work/checkname", method="GET", params=params)
		return response.json()

	# 获取作者更多作品
	def get_author_work(self, user_id: str) -> dict:
		response = self.acquire.send_request(endpoint=f"/web/works/users/{user_id}", method="GET")
		return response.json()

	# 获取作品源码
	def get_work_source(self, work_id: int) -> dict:
		response = self.acquire.send_request(
			endpoint=f"/creation-tools/v1/works/{work_id}/source/public",
			method="GET",
		)
		return response.json()

	# 获取最新作品
	def discover_works_new_web(self, limit: int, offset: int = 0, *, origin: bool = False) -> dict:
		extra_params = {"work_origin_type": "ORIGINAL_WORK"} if origin else {}
		params = {**extra_params, "limit": limit, "offset": offset}
		response = self.acquire.send_request(
			endpoint="/creation-tools/v1/pc/discover/newest-work",
			method="GET",
			params=params,
		)  # 为防止封号,limit建议调大
		return response.json()

	# 获取最新或最热作品
	def discover_works_subject_web(self, limit: int, offset: int = 0, subject_id: int = 0) -> dict:
		extra_params = {"subject_id": subject_id} if subject_id else {}
		params = {**extra_params, "limit": limit, "offset": offset}
		response = self.acquire.send_request(
			endpoint="/creation-tools/v1/pc/discover/subject-work",
			method="GET",
			params=params,
		)  # 为防止封号,limit建议调大
		return response.json()

	# 获取推荐作品(nemo端)
	def discover_works_nemo(self) -> dict:
		response = self.acquire.send_request(endpoint="/creation-tools/v1/home/discover", method="GET")
		return response.json()

	# 获取nemo端最新作品
	def discover_works_new_nemo(
		self,
		types: Literal["course-work", "template", "original", "fork"],
		limit: int = 15,
		offset: int = 0,
	) -> dict:
		params = {"limit": limit, "offset": offset}
		response = self.acquire.send_request(endpoint=f"/nemo/v3/newest/work/{types}/list", method="GET", params=params)
		return response.json()

	# 获取随机作品主题
	def get_subject_random_nemo(self) -> list[int]:
		response = self.acquire.send_request(endpoint="/nemo/v3/work-subject/random", method="GET")
		return response.json()

	# 获取作品主题介绍
	def get_subject_info_nemo(self, ids: int) -> dict:
		response = self.acquire.send_request(endpoint=f"/nemo/v3/work-subject/{ids}/info", method="GET")
		return response.json()

	# 获取作品主题下作品
	def get_subject_work_nemo(self, ids: int, limit: int = 15, offset: int = 0) -> dict:
		params = {"limit": limit, "offset": offset}
		response = self.acquire.send_request(endpoint=f"/nemo/v3/work-subject/{ids}/works", method="GET", params=params)
		return response.json()

	# /nemo/v3/work-subject/home?offset=0&limit=15
	# 获取各个主题下的作品
	def get_subject_works_nemo(self, limit: int = 15, offset: int = 0) -> dict:
		params = {"limit": limit, "offset": offset}
		response = self.acquire.send_request(endpoint="/nemo/v3/work-subject/home", method="GET", params=params)
		return response.json()

	# 获取协作邀请码
	def get_coll_code(self, work_id: int, method: Literal["GET", "DELETE"] = "GET") -> dict:
		response = self.acquire.send_request(
			endpoint=f"https://socketcoll.codemao.cn/coll/kitten/collaborator/code/{work_id}",
			method=method,
		)
		return response.json()

	# 获取协作者列表
	def get_coll_list(self, work_id: int, limit: int | None = 100) -> Generator[dict]:
		params = {"current_page": 1, "page_size": 100}
		return self.acquire.fetch_data(
			endpoint=f"https://socketcoll.codemao.cn/coll/kitten/collaborator/{work_id}",
			params=params,
			total_key="data.total",
			data_key="data.items",
			pagination_method="page",
			args={"amount": "current_page", "remove": "page_size"},
			limit=limit,
		)

	# TODO@Aurzex: 功能存疑
	# 获取kitten作品合作者
	def get_collaboration(self, work_id: int) -> dict:
		response = self.acquire.send_request(
			endpoint=f"https://api-creation.codemao.cn/collaboration/user/{work_id}",
			method="GET",
		)
		return response.json()

	# 获取作品再创作情况_web端
	def get_recreate_info_web(self, work_id: int) -> dict:
		response = self.acquire.send_request(
			endpoint=f"/tiger/work/tree/{work_id}",
			method="GET",
		)
		return response.json()

	# 获取作品再创作情况_nemo端
	def get_recreate_info_nemo(self, work_id: int) -> dict:
		response = self.acquire.send_request(
			endpoint=f"/nemo/v2/works/root/{work_id}",
			method="GET",
		)
		return response.json()

	# 获取KN作品历史版本
	def get_works_kn_archive(self, work_id: int) -> dict:
		response = self.acquire.send_request(
			endpoint=f"https://api-creation.codemao.cn/neko/works/archive/{work_id}",
			method="GET",
		)
		return response.json()

	# 获取回收站作品列表
	def get_recycle_kitten_works(self, version_no: Literal["KITTEN_V3", "KITTEN_V4"], work_status: str = "CYCLED", limit: int | None = 30) -> Generator[dict]:
		params = {
			"limit": 30,
			"offset": 0,
			"version_no": version_no,
			"work_status": work_status,
		}
		return self.acquire.fetch_data(
			endpoint="https://api-creation.codemao.cn/tiger/work/recycle/list",
			params=params,
			limit=limit,
		)

	# 获取回收站海龟编辑器作品列表
	def get_recycle_wood_works(self, language_type: int = 0, work_status: str = "CYCLED", published_status: str = "undefined", limit: int | None = 30) -> Generator[dict]:
		params = {
			"limit": 30,
			"offset": 0,
			"language_type": language_type,
			"work_status": work_status,
			"published_status": published_status,
		}
		return self.acquire.fetch_data(
			endpoint="https://api-creation.codemao.cn/wood/comm/work/list",
			params=params,
			limit=limit,
		)

	# 获取代码岛回收站作品列表
	def get_recycle_box_works(self, work_status: str = "CYCLED", limit: int | None = 30) -> Generator[dict]:
		params = {
			"limit": 30,
			"offset": 0,
			"work_status": work_status,
		}
		return self.acquire.fetch_data(
			endpoint="https://api-creation.codemao.cn/box/v2/work/list",
			params=params,
			limit=limit,
		)

	# 获取回收站小说列表
	def get_recycle_fanfic_works(self, fiction_status: str = "CYCLED", limit: int | None = 30) -> Generator[dict]:
		params = {
			"limit": 30,
			"offset": 0,
			"fiction_status": fiction_status,
		}
		return self.acquire.fetch_data(
			endpoint="/web/fanfic/my/new",
			params=params,
			limit=limit,
		)

	# 获取回收站KN作品列表
	def get_recycle_kn_works(self, name: str = "", work_business_classify: int = 1, limit: int | None = 24) -> Generator[dict]:
		params = {
			"name": name,
			"limit": 24,
			"offset": 0,
			"status": -99,
			"work_business_classify": work_business_classify,
		}
		return self.acquire.fetch_data(
			endpoint="https://api-creation.codemao.cn/neko/works/v2/list/user",
			params=params,
			limit=limit,
		)

	# 按关键词搜索KN全部作品
	def search_works_kn(self, name: str, status: int = 1, work_business_classify: int = 1, limit: int | None = 24) -> Generator[dict]:
		params = {
			"name": name,
			"limit": 24,
			"offset": 0,
			"status": status,
			"work_business_classify": work_business_classify,
		}
		return self.acquire.fetch_data(
			endpoint="https://api-creation.codemao.cn/neko/works/v2/list/user",
			params=params,
			limit=limit,
		)

	# 按关键词搜索KN已发布作品
	def search_works_kn_published(self, name: str, work_business_classify: int = 1, limit: int | None = 24) -> Generator[dict]:
		params = {
			"name": name,
			"limit": 24,
			"offset": 0,
			"work_business_classify": work_business_classify,
		}
		return self.acquire.fetch_data(
			endpoint="https://api-creation.codemao.cn/neko/works/list/user/published",
			params=params,
			limit=limit,
		)

	# TODO@Aurzex: 待确认
	# 获取KN作品变量列表
	def get_works_kn_variables(self, work_id: int) -> dict:
		response = self.acquire.send_request(
			endpoint=f"https://socketcv.codemao.cn/neko/cv/list/variables/{work_id}",
			method="GET",
		)
		return response.json()

	# 获取积木/角色背包列表
	def get_block_character_package(self, types: Literal["block", "character"], limit: int = 16, offset: int = 0) -> dict:
		if types == "block":
			_type = 1
		elif types == "character":
			_type = 0
		# type 1 角色背包 0 积木背包
		# limit 获取积木默认16个,角色默认20个
		params = {
			"type": _type,
			"limit": limit,
			"offset": offset,
		}
		response = self.acquire.send_request(
			endpoint="https://api-creation.codemao.cn/neko/package/list",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取动态里面的作品(包括收藏的作品,关注的人的作品)
	def get_dynamic_works(self, limit: int = 15, offset: int = 0) -> dict:
		params = {
			"limit": limit,
			"offset": offset,
		}
		response = self.acquire.send_request(
			endpoint="/nemo/v3/work/dynamic",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取动态推荐的人
	def get_dynamic_focus_user(self) -> dict:
		response = self.acquire.send_request(
			endpoint="/nemo/v3/dynamic/focus/user/recommend",
			method="GET",
		)
		return response.json()
