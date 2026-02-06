from collections.abc import Generator
from typing import Literal, cast

from aumiao.utils import acquire
from aumiao.utils.acquire import HTTPStatus
from aumiao.utils.decorator import singleton


@singleton
class UserDataFetcher:
	def __init__(self) -> None:
		"""初始化用户数据获取类"""
		self._client = acquire.CodeMaoClient()

	# 2026/1/19 日测试报错 410 , 推测 api 已经弃用
	# 2026/2/2日又可以了(())
	def fetch_user_profile(self, user_id: int) -> dict:
		"""获取用户详细信息"""
		response = self._client.send_request(method="GET", endpoint=f"/api/user/info/detail/{user_id}")
		return response.json()

	def fetch_user_tiger(self, user_id: int) -> dict:
		"""获取用户 Tiger 信息"""
		response = self._client.send_request(method="GET", endpoint=f"/tiger/user/{user_id}")
		return response.json()

	def fetch_user_info(self, user_id: int) -> dict:
		"""获取用户 info 信息"""
		response = self._client.send_request(
			method="GET",
			endpoint=f"/web/api/user/info/detail/{user_id}",
		)
		return response.json()

	def fetch_user_honors(self, user_id: int) -> dict:
		"""获取用户荣誉信息"""
		params = {"user_id": user_id}
		response = self._client.send_request(
			endpoint="/creation-tools/v1/user/center/honor",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_user_metrics(self, user_id: int) -> dict:
		"""获取用户业务数据指标"""
		params = {"user_id": user_id}
		response = self._client.send_request(endpoint="/nemo/v2/works/business/total", method="GET", params=params)
		return response.json()

	def fetch_user_intro(self, user_id: int) -> dict:
		"""获取用户基本信息"""
		params = {"user_id": user_id}
		response = self._client.send_request(method="GET", endpoint="/nemo/v2/user/dynamic/info", params=params)
		return response.json()

	def fetch_user_dynamic(self, user_id: int) -> dict:
		"""获取用户动态信息"""
		response = self._client.send_request(endpoint=f"/api/user/dynamic/{user_id}", method="GET")
		return response.json()

	def fetch_user_studio(self, user_id: int) -> dict:
		"""获取用户加入的工作室信息"""
		response = self._client.send_request(endpoint=f"/web/work-shops/{user_id}/participators", method="GET")
		return response.json()

	# 获取账户信息 (简略)
	def get_account_info(self) -> dict:
		response = self._client.send_request(
			method="GET",
			endpoint="/web/api/user/info",
		)
		return response.json()

	def fetch_account_details(self) -> dict:
		"""获取当前账号详细信息"""
		response = self._client.send_request(
			method="GET",
			endpoint="/web/users/details",
		)
		return response.json()

	def fetch_account_platform_profile(self, method: Literal["web", "app"]) -> dict:
		"""获取平台账号资料"""
		response = self._client.send_request(method="GET", endpoint=f"/tiger/v3/{method}/accounts/profile")
		return response.json()

	def fetch_account_privacy(self) -> dict:
		"""获取账号隐私设置"""
		response = self._client.send_request(method="GET", endpoint="/tiger/v3/web/accounts/privacy")
		return response.json()

	def fetch_account_tiger(self) -> dict:
		"""获取 Tiger 账号信息"""
		response = self._client.send_request(endpoint="/tiger/user", method="GET")
		return response.json()

	def fetch_account_scores(self) -> dict:
		"""获取用户评分数据 (点赞 / 再创作 / 收藏)"""
		response = self._client.send_request(endpoint="/nemo/v3/user/grade/details", method="GET")
		return response.json()

	def fetch_account_level(self) -> dict:
		"""获取用户等级信息"""
		response = self._client.send_request(endpoint="/nemo/v3/user/level/info", method="GET")
		return response.json()

	def fetch_account_dynamic(self) -> dict:
		"""获取用户动态信息"""
		response = self._client.send_request(endpoint="/api/user/dynamic", method="GET")
		return response.json()

	def fetch_account_works(self) -> dict:
		"""获取用户作品"""
		response = self._client.send_request(endpoint="/api/work/list", method="GET")
		return response.json()

	# 获取用户注册时间
	def fetch_account_register_time(self) -> dict:
		response = self._client.send_request(endpoint="/nemo/new-people/user-info", method="GET")
		return response.json()

	# 可能会返回 {"code":6404,"msg":"未绑定手机号"}, 从而可以检测是否绑定手机号
	def fetch_account_lesson_info(self) -> dict:
		"""获取课程账号信息 (可用于检测手机号绑定状态)"""
		response = self._client.send_request(endpoint="/api/v2/pc/lesson/user/info", method="GET")
		return response.json()

	def fetch_user_works_web_gen(self, user_id: int, types: Literal["newest", "hot"] = "newest", limit: int | None = 5) -> Generator[dict]:
		"""获取用户作品列表生成器 (Web 端)"""
		params = {
			"type": types,
			"user_id": user_id,
			"offset": 0,
			"limit": 5,
		}
		return self._client.fetch_paginated_data(
			endpoint="/creation-tools/v2/user/center/work-list",
			params=params,
			total_key="total",
			limit=limit,
		)

	def search_user_works_nemo(self, query: str, query_type: str = "name", page: int = 1, limit: int = 10) -> dict:
		"""搜索用户作品 (Nemo 端)"""
		params = {
			"query": query,
			"query_type": query_type,
			"page": page,
			"limit": limit,
		}
		response = self._client.send_request(endpoint="tiger/nemo/user/works/search", method="GET", params=params)
		return response.json()

	def fetch_cloud_works(self, types: Literal["nemo", "kitten"], limit: int = 10, offset: int = 0) -> dict:
		"""获取用户云端作品"""
		work_type = 8 if types == "nemo" else 1
		params = {"limit": limit, "offset": offset, "work_type": work_type}
		response = self._client.send_request(endpoint="/creation-tools/v1/works/list/user", params=params, method="GET")
		return response.json()

	def fetch_user_certificate(self, user_id: int) -> dict:
		"""获取用户证书信息"""
		params = {"user_id": user_id}
		response = self._client.send_request(endpoint="https://api-wechatsbp-codemaster.codemao.cn/user/info/certificate", method="GET", params=params)
		return response.json()

	def fetch_published_nemo_works_gen(self, method: Literal["published"], limit: int | None = 15) -> Generator[dict]:
		"""获取用户已发布 Nemo 作品生成器"""
		params = {"limit": 15, "offset": 0}
		return self._client.fetch_paginated_data(
			endpoint=f"/nemo/v2/works/list/user/{method}",
			params=params,
			limit=limit,
		)

	def fetch_kn_works_gen(
		self,
		method: Literal["published", "total"],
		extra_params: (dict[Literal["name", "limit", "offset", "status", "work_business_classify"], str | int] | None) = None,
		limit: int | None = 15,
	) -> Generator[dict]:
		"""获取用户 KN 作品生成器"""
		url = "https://api-creation.codemao.cn/neko/works/list/user/published" if method == "published" else "https://api-creation.codemao.cn/neko/works/v2/list/user"
		params = {"offset": 0, "limit": 15}
		params = cast("dict", params)
		params.update(extra_params or {})
		return self._client.fetch_paginated_data(endpoint=url, params=params, limit=limit)

	def fetch_kitten_works_gen(
		self,
		version: Literal["KITTEN_V4", "KITTEN_V3"],
		status: Literal["PUBLISHED", "UNPUBLISHED", "all"],
		work_status: Literal["SHOW"] = "SHOW",
		limit: int | None = 30,
	) -> Generator[dict]:
		"""获取用户 Kitten 作品生成器"""
		params = {
			"offset": 0,
			"limit": 30,
			"version_no": version,
			"work_status": work_status,
			"published_status": status,
		}
		return self._client.fetch_paginated_data(
			endpoint="https://api-creation.codemao.cn/kitten/common/work/list2",
			params=params,
			limit=limit,
		)

	def fetch_nemo_works_gen(self, status: Literal["PUBLISHED", "UNPUBLISHED", "all"], limit: int | None = 30) -> Generator[dict]:
		"""获取用户 Nemo 作品生成器"""
		params = {"offset": 0, "limit": 30, "published_status": status}
		return self._client.fetch_paginated_data(
			endpoint="/creation-tools/v1/works/list",
			params=params,
			limit=limit,
		)

	def fetch_wood_works_gen(
		self,
		status: Literal["PUBLISHED", "UNPUBLISHED"],
		language_type: int = 0,
		work_status: Literal["SHOW"] = "SHOW",
		limit: int | None = 30,
	) -> Generator[dict]:
		"""获取用户海龟编辑器作品生成器"""
		params = {
			"offset": 0,
			"limit": 30,
			"language_type": language_type,
			"work_status": work_status,
			"published_status": status,
		}
		return self._client.fetch_paginated_data(
			endpoint="https://api-creation.codemao.cn/wood/comm/work/list",
			params=params,
			limit=limit,
		)

	def fetch_box_works_gen(self, status: Literal["all", "PUBLISHED", "UNPUBLISHED"], work_status: Literal["SHOW"] = "SHOW", limit: int | None = 30) -> Generator[dict]:
		"""获取用户 Box 作品生成器"""
		params = {
			"offset": 0,
			"limit": 30,
			"work_status": work_status,
			"published_status": status,
		}
		return self._client.fetch_paginated_data(
			endpoint="https://api-creation.codemao.cn/box/v2/work/list",
			params=params,
			limit=limit,
		)

	def fetch_fanfics_gen(self, fiction_status: Literal["SHOW"] = "SHOW", limit: int | None = 30) -> Generator[dict]:
		"""获取用户小说生成器"""
		params = {"offset": 0, "limit": 30, "fiction_status": fiction_status}
		return self._client.fetch_paginated_data(
			endpoint="/web/fanfic/my/new",
			params=params,
			limit=limit,
		)

	def fetch_coco_works_gen(self, status: int = 1, *, published: bool = True, limit: int | None = 30) -> Generator[dict]:
		"""获取用户 Coco 作品生成器"""
		params = {
			"offset": 0,
			"limit": 30,
			"status": status,
			"published": published,
		}
		return self._client.fetch_paginated_data(
			endpoint="https://api-creation.codemao.cn/coconut/web/work/list",
			params=params,
			data_key="data.items",
			total_key="data.total",
			limit=limit,
		)

	def fetch_followers_gen(self, user_id: int, limit: int | None = 15) -> Generator[dict]:
		"""获取用户粉丝列表生成器"""
		params = {
			"user_id": user_id,
			"offset": 0,
			"limit": 15,
		}
		return self._client.fetch_paginated_data(
			endpoint="/creation-tools/v1/user/fans",
			params=params,
			total_key="total",
			limit=limit,
		)

	def fetch_following_gen(self, user_id: int, limit: int = 15) -> Generator[dict]:
		"""获取用户关注列表生成器"""
		params = {
			"user_id": user_id,
			"offset": 0,
			"limit": 15,
		}
		return self._client.fetch_paginated_data(
			endpoint="/creation-tools/v1/user/followers",
			params=params,
			total_key="total",
			limit=limit,
		)

	def fetch_published_works(self, user_id: int, types: list[Literal[1, 3, 5]], limit: int = 10) -> dict:
		"""获取用户已发布作品"""
		params = {
			"user_id": user_id,
			"types": ",".join(map(str, types)),
			"limit": limit,
		}
		response = self._client.send_request(
			endpoint="/web/api/user/works/published",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_user_attention(self, user_id: int, limit: int = 10) -> dict:
		"""获取用户关注列表"""
		params = {
			"user_id": user_id,
			"limit": limit,
		}
		response = self._client.send_request(
			endpoint="/web/api/user/me/attention",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_user_collections(self, user_id: int, types: list[Literal[1, 3, 5]], limit: int = 10) -> dict:
		"""获取用户收藏的作品"""
		params = {
			"user_id": user_id,
			"types": ",".join(map(str, types)),
			"limit": limit,
		}
		response = self._client.send_request(
			endpoint="/web/api/user/works/collection",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_collections_gen(self, user_id: int, limit: int = 5) -> Generator[dict]:
		"""获取用户收藏作品生成器"""
		# 2026/1/19 日发现 api 已经更新到 v2,v1 可以正常使用
		params = {
			"user_id": user_id,
			"offset": 0,
			"limit": 5,
		}
		return self._client.fetch_paginated_data(
			endpoint="/creation-tools/v2/user/center/collect/list",
			params=params,
			total_key="total",
			limit=limit,
		)

	# 旧版头像 https://static-platform.codemao.cn/avatar/default/v1_user_001.png
	# 新版头像 https://cdn-community.codemao.cn/community_frontend/community_default_avatar/avatar_300x300_01.jpg

	def fetch_avatar_frames(self) -> dict:
		"""获取用户头像框列表"""
		response = self._client.send_request(
			endpoint="/creation-tools/v1/user/avatar-frame/list",
			method="GET",
		)
		return response.json()

	def check_new_user_status(self) -> dict:
		"""检查用户是否为新用户"""
		response = self._client.send_request(endpoint="https://api-creation.codemao.cn/neko/works/isNewUser", method="GET")
		return response.json()


@singleton
class UserManager:
	def __init__(self) -> None:
		"""初始化用户管理类"""
		self._client = acquire.CodeMaoClient()

	def update_status(self, doing: str | None, avatar: str | None) -> bool:
		"""更新用户状态"""
		data = {key: value for key, value in {"doing": doing, "avatar_url": avatar}.items() if value is not None}
		response = self._client.send_request(endpoint="/nemo/v2/user/basic", method="PUT", payload=data)
		return response.status_code == HTTPStatus.OK.value

	def update_username(self, username: str) -> bool:
		"""更改用户名 (实验性功能)"""
		msg = "此为实验性功能"
		raise ValueError(msg)
		response = self._client.send_request(
			endpoint="/tiger/v3/web/accounts/username",
			method="PATCH",
			payload={"username": username},
		)
		return response.status_code == HTTPStatus.NO_CONTENT.value

	def validate_phone_number(self, phone_num: int) -> dict:
		"""验证手机号码"""
		params = {"phone_number": phone_num}
		response = self._client.send_request(endpoint="/web/users/phone_number/is_consistent", method="GET", params=params)
		return response.json()

	def update_password(self, old_password: str, new_password: str) -> bool:
		"""修改密码"""
		data = {
			"old_password": old_password,
			"password": new_password,
			"confirm_password": new_password,
		}
		response = self._client.send_request(
			endpoint="/tiger/v3/web/accounts/password",
			method="PATCH",
			payload=data,
		)
		return response.status_code == HTTPStatus.NO_CONTENT.value

	def execute_request_phone_change_verification(self, old_phonenum: int, new_phonenum: int) -> bool:
		"""请求更换手机号验证码"""
		data = {"phone_number": new_phonenum, "old_phone_number": old_phonenum}
		response = self._client.send_request(
			endpoint="/tiger/v3/web/accounts/captcha/phone/change",
			method="POST",
			payload=data,
		)
		return response.status_code == HTTPStatus.NO_CONTENT.value

	def update_phone_number(self, captcha: int, phonenum: int) -> bool:
		"""更新手机号码"""
		data = {"phone_number": phonenum, "captcha": captcha}
		response = self._client.send_request(
			endpoint="/tiger/v3/web/accounts/phone/change",
			method="PATCH",
			payload=data,
		)
		return response.json()

	def delete_avatar_frame(self) -> bool:
		"""移除头像框"""
		response = self._client.send_request(
			endpoint="/creation-tools/v1/user/avatar-frame/cancel",
			method="PUT",
		)
		return response.status_code == HTTPStatus.OK.value

	def execute_apply_avatar_frame(self, frame_id: Literal[2, 3, 4]) -> bool:
		"""应用头像框 frame_id: 头像框 ID (2=Lv2,3=Lv3,4=Lv4)"""
		response = self._client.send_request(
			endpoint=f"/creation-tools/v1/user/avatar-frame/{frame_id}",
			method="PUT",
		)
		return response.status_code == HTTPStatus.OK.value

	def update_profile_details(
		self,
		avatar_url: str,
		nickname: str,
		birthday: int,
		description: str,
		fullname: str,
		qq: str,
		sex: Literal[0, 1],
	) -> bool:
		"""更新个人资料详细信息 sex: 性别 (0 = 女,1 = 男)"""
		data = {
			"avatar_url": avatar_url,
			"nickname": nickname,
			"birthday": birthday,
			"description": description,
			"fullname": fullname,
			"qq": qq,
			"sex": sex,
		}
		response = self._client.send_request(
			endpoint="/tiger/v3/web/accounts/info",
			method="PATCH",
			payload=data,
		)
		return response.status_code == HTTPStatus.NO_CONTENT.value

	def update_profile_cover(self, cover_url: str) -> bool:
		"""
		更新个人主页封面
		Args:
			cover_url: 封面 URL (预设封面:
				https://static.codemao.cn/nemo/cover/cover_mountain.png
				https://static.codemao.cn/nemo/cover/cover_moon.png
				https://static.codemao.cn/nemo/cover/cover_sunrise.png
				https://static.codemao.cn/nemo/cover/cover_forest.png)
		Returns:
			更新是否成功
		"""
		data = {"preview": cover_url}
		response = self._client.send_request(
			endpoint="/nemo/v2/user/preview",
			method="POST",
			payload=data,
		)
		return response.status_code == HTTPStatus.OK.value

	def delete_user(self, reason: str, *, return_data: bool = False) -> dict | bool:
		data = {"closeReason": reason}
		response = self._client.send_request(endpoint="/tiger/v3/web/accounts/close", method="POST", payload=data)
		return response.json() if return_data else response.status_code == HTTPStatus.OK


# TODO@Aurzex: 待完善
# /tiger/v3/web/accounts/captcha/password/update
# 发送修改密码的短信验证码
# /tiger/v3/web/accounts/password/phone
# 通过短信验证码修改密码
# /tiger/v3/web/accounts/tokens/convert
# 获取用户访问令牌 (Token)


# **Kitten相关:**
# - https://kitten.codemao.cn/
# - https://kitten4.codemao.cn/
# - https://edu-kitten.codemao.cn/
# - https://old-kitten.codemao.cn/
# - https://kitten-exam.codemao.cn/
# - https://dead-kitten.codemao.cn/

# **Nemo (Kitten·N) 相关:**
# - https://kn.codemao.cn/
# - https://kn.codemao.cn/editor/
# - https://kn.codemao.cn/editor/?ai_chatbot=deepseek

# **其他产品/平台:**
# - https://www.code.game/home
# - https://rocket-viewer.codemao.cn/
# - https://aichat.codemao.cn/
# - https://maochat.codemao.cn/
# - https://science.codemao.cn/
# - https://box.codemao.cn/
# - https://mcpe.codemao.cn/

# **社区与内容:**
# - https://c.codemao.cn/
# - https://staging-shequ.codemao.cn/community
# - https://c.codemao.cn/?guest=1
# - https://c.codemao.cn/course
# - https://c.codemao.cn/discover
# - https://c.codemao.cn/work_shop
# - https://c.codemao.cn/wiki
# - https://c.codemao.cn/mall
# - https://c.codemao.cn/download?type=download

# **管理与工具:**
# - https://internal-account.codemao.cn/
# - https://internal-account.codemao.cn/login
# - https://cloud-space.codemao.cn/login
# - https://arena-admin.codemao.cn/
# - https://tob-admin.codemao.cn/#/user/login
# - https://whale.codemao.cn/report-work

# **文档:**
# - https://docs.codemao.cn/kitten/code/docs.html
