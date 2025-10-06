from collections.abc import Generator
from typing import Literal, cast

from src.utils import acquire
from src.utils.acquire import HTTPSTATUS
from src.utils.decorator import singleton


@singleton
class UserDataFetcher:
	def __init__(self) -> None:
		"""初始化用户数据获取类"""
		self._client = acquire.CodeMaoClient()

	# BUG 貌似api不起作用
	# 获取账户信息(简略)
	# def get_data_info(self) -> dict:
	# 	response = self._client.send_request(
	# 		method="GET",
	# 		endpoint="/web/user/info",
	# 	)
	# 	return response.json()
	def fetch_user_profile(self, user_id: str) -> dict:
		"""
		获取用户详细信息
		Args:
			user_id: 用户ID
		Returns:
			用户详细信息字典
		"""
		response = self._client.send_request(method="GET", endpoint=f"/api/user/info/detail/{user_id}")
		return response.json()

	def fetch_user_honors(self, user_id: str) -> dict:
		"""
		获取用户荣誉信息
		Args:
			user_id: 用户ID
		Returns:
			用户荣誉信息字典
		"""
		params = {"user_id": user_id}
		response = self._client.send_request(
			endpoint="/creation-tools/v1/user/center/honor",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_user_metrics(self, user_id: str) -> dict:
		"""
		获取用户业务数据指标
		Args:
			user_id: 用户ID
		Returns:
			用户业务数据字典
		"""
		params = {"user_id": user_id}
		response = self._client.send_request(endpoint="/nemo/v2/works/business/total", method="GET", params=params)
		return response.json()

	def fetch_basic_user_info(self, user_id: str) -> dict:
		"""
		获取用户基本信息
		Args:
			user_id: 用户ID
		Returns:
			用户基本信息字典
		"""
		params = {"user_id": user_id}
		response = self._client.send_request(method="GET", endpoint="/nemo/v2/user/dynamic/info", params=params)
		return response.json()

	def fetch_account_details(self) -> dict:
		"""
		获取当前账号详细信息
		Returns:
			账号详细信息字典
		"""
		response = self._client.send_request(
			method="GET",
			endpoint="/web/users/details",
		)
		return response.json()

	def fetch_platform_profile(self, method: Literal["web", "app"]) -> dict:
		"""
		获取平台账号资料
		Args:
			method: 平台类型(web或app)
		Returns:
			平台账号资料字典
		"""
		response = self._client.send_request(method="GET", endpoint=f"/tiger/v3/{method}/accounts/profile")
		return response.json()

	def fetch_privacy_settings(self) -> dict:
		"""
		获取账号隐私设置
		Returns:
			隐私设置字典
		"""
		response = self._client.send_request(method="GET", endpoint="/tiger/v3/web/accounts/privacy")
		return response.json()

	def fetch_tiger_account_info(self) -> dict:
		"""
		获取Tiger账号信息
		Returns:
			Tiger账号信息字典
		"""
		response = self._client.send_request(endpoint="/tiger/user", method="GET")
		return response.json()

	def fetch_account_scores(self) -> dict:
		"""
		获取用户评分数据(点赞/再创作/收藏)
		Returns:
			用户评分数据字典
		"""
		response = self._client.send_request(endpoint="/nemo/v3/user/grade/details", method="GET")
		return response.json()

	def fetch_account_level(self) -> dict:
		"""
		获取用户等级信息
		Returns:
			用户等级信息字典
		"""
		response = self._client.send_request(endpoint="/nemo/v3/user/level/info", method="GET")
		return response.json()

	# 获取用户注册时间
	def fetch_account_register_time(self) -> dict:
		response = self._client.send_request(endpoint="/nemo/new-people/user-info", method="GET")
		return response.json()

	# 可能会返回{"code":6404,"msg":"未绑定手机号"},从而可以检测是否绑定手机号
	def fetch_lesson_account_info(self) -> dict:
		"""
		获取课程账号信息(可用于检测手机号绑定状态)
		Returns:
			课程账号信息字典
		"""
		response = self._client.send_request(endpoint="/api/v2/pc/lesson/user/info", method="GET")
		return response.json()

	def fetch_user_works_web_gen(self, user_id: str, types: Literal["newest", "hot"] = "newest", limit: int | None = 5) -> Generator[dict]:
		"""
		获取用户作品列表生成器(Web端)
		Args:
			user_id: 用户ID
			types: 排序类型(newest=最新,hot=热门)
			limit: 获取数量限制(可选)
		Returns:
			作品列表生成器
		"""
		params = {
			"type": types,
			"user_id": user_id,
			"offset": 0,
			"limit": 5,
		}
		return self._client.fetch_data(
			endpoint="/creation-tools/v2/user/center/work-list",
			params=params,
			total_key="total",
			limit=limit,
		)

	def search_user_works_nemo(self, query: str, query_type: str = "name", page: int = 1, limit: int = 10) -> dict:
		"""
		搜索用户作品(Nemo端)
		Args:
			query: 搜索关键词
			query_type: 搜索类型(默认为按名称)
			page: 页码(可选)
			limit: 每页数量(可选)
		Returns:
			搜索结果字典
		"""
		params = {
			"query": query,
			"query_type": query_type,
			"page": page,
			"limit": limit,
		}
		response = self._client.send_request(endpoint="tiger/nemo/user/works/search", method="GET", params=params)
		return response.json()

	def fetch_cloud_works(self, types: Literal["nemo", "kitten"], limit: int = 10, offset: int = 0) -> dict:
		"""
		获取用户云端作品
		Args:
			types: 作品类型(nemo或kitten)
			limit: 获取数量(可选)
			offset: 偏移量(可选)
		Returns:
			云端作品字典
		"""
		work_type = 8 if types == "nemo" else 1
		params = {"limit": limit, "offset": offset, "work_type": work_type}
		response = self._client.send_request(endpoint="/creation-tools/v1/works/list/user", params=params, method="GET")
		return response.json()

	def fetch_published_nemo_works_gen(self, method: Literal["published"], limit: int | None = 15) -> Generator[dict]:
		"""
		获取用户已发布Nemo作品生成器
		Args:
			method: 方法类型(目前仅支持published)
			limit: 获取数量限制(可选)
		Returns:
			作品生成器
		"""
		params = {"limit": 15, "offset": 0}
		return self._client.fetch_data(
			endpoint=f"/nemo/v2/works/list/user/{method}",
			params=params,
			limit=limit,
		)

	def fetch_kn_works_gen(
		self,
		method: Literal["published", "total"],
		extra_params: (
			dict[
				Literal["name", "limit", "offset", "status", "work_business_classify"],
				str | int,
			]
			| None
		) = None,
		limit: int | None = 15,
	) -> Generator[dict]:
		"""
		获取用户KN作品生成器
		Args:
			method: 方法类型(published=已发布,total=全部)
			extra_params: 额外参数(可选)
			limit: 获取数量限制(可选)
		Returns:
			KN作品生成器
		"""
		url = "https://api-creation.codemao.cn/neko/works/list/user/published" if method == "published" else "https://api-creation.codemao.cn/neko/works/v2/list/user"
		params = {"offset": 0, "limit": 15}
		params = cast("dict", params)
		params.update(extra_params or {})
		return self._client.fetch_data(endpoint=url, params=params, limit=limit)

	def fetch_kitten_works_gen(
		self,
		version: Literal["KITTEN_V4", "KITTEN_V3"],
		status: Literal["PUBLISHED", "UNPUBLISHED", "all"],
		work_status: Literal["SHOW"] = "SHOW",
		limit: int | None = 30,
	) -> Generator[dict]:
		"""
		获取用户Kitten作品生成器
		Args:
			version: Kitten版本
			status: 作品状态
			work_status: 作品显示状态(可选)
			limit: 获取数量限制(可选)
		Returns:
			Kitten作品生成器
		"""
		params = {
			"offset": 0,
			"limit": 30,
			"version_no": version,
			"work_status": work_status,
			"published_status": status,
		}
		return self._client.fetch_data(
			endpoint="https://api-creation.codemao.cn/kitten/common/work/list2",
			params=params,
			limit=limit,
		)

	def fetch_nemo_works_gen(self, status: Literal["PUBLISHED", "UNPUBLISHED", "all"], limit: int | None = 30) -> Generator[dict]:
		"""
		获取用户Nemo作品生成器
		Args:
			status: 作品状态
			limit: 获取数量限制(可选)
		Returns:
			Nemo作品生成器
		"""
		params = {"offset": 0, "limit": 30, "published_status": status}
		return self._client.fetch_data(
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
		"""
		获取用户海龟编辑器作品生成器
		Args:
			status: 作品状态
			language_type: 语言类型(可选)
			work_status: 作品显示状态(可选)
			limit: 获取数量限制(可选)
		Returns:
			海龟作品生成器
		"""
		params = {
			"offset": 0,
			"limit": 30,
			"language_type": language_type,
			"work_status": work_status,
			"published_status": status,
		}
		return self._client.fetch_data(
			endpoint="https://api-creation.codemao.cn/wood/comm/work/list",
			params=params,
			limit=limit,
		)

	def fetch_box_works_gen(self, status: Literal["all", "PUBLISHED", "UNPUBLISHED"], work_status: Literal["SHOW"] = "SHOW", limit: int | None = 30) -> Generator[dict]:
		"""
		获取用户Box作品生成器
		Args:
			status: 作品状态
			work_status: 作品显示状态(可选)
			limit: 获取数量限制(可选)
		Returns:
			Box作品生成器
		"""
		params = {
			"offset": 0,
			"limit": 30,
			"work_status": work_status,
			"published_status": status,
		}
		return self._client.fetch_data(
			endpoint="https://api-creation.codemao.cn/box/v2/work/list",
			params=params,
			limit=limit,
		)

	def fetch_fanfics_gen(self, fiction_status: Literal["SHOW"] = "SHOW", limit: int | None = 30) -> Generator[dict]:
		"""
		获取用户小说生成器
		Args:
			fiction_status: 小说状态(可选)
			limit: 获取数量限制(可选)
		Returns:
			小说生成器
		"""
		params = {"offset": 0, "limit": 30, "fiction_status": fiction_status}
		return self._client.fetch_data(
			endpoint="/web/fanfic/my/new",
			params=params,
			limit=limit,
		)

	def fetch_coco_works_gen(self, status: int = 1, *, published: bool = True, limit: int | None = 30) -> Generator[dict]:
		"""
		获取用户Coco作品生成器
		Args:
			status: 作品状态(可选)
			published: 是否已发布(可选)
			limit: 获取数量限制(可选)
		Returns:
			Coco作品生成器
		"""
		params = {
			"offset": 0,
			"limit": 30,
			"status": status,
			"published": published,
		}
		return self._client.fetch_data(
			endpoint="https://api-creation.codemao.cn/coconut/web/work/list",
			params=params,
			data_key="data.items",
			total_key="data.total",
			limit=limit,
		)

	def fetch_followers_gen(self, user_id: str, limit: int = 15) -> Generator[dict]:
		"""
		获取用户粉丝列表生成器
		Args:
			user_id: 用户ID
			limit: 获取数量限制(可选)
		Returns:
			粉丝列表生成器
		"""
		params = {
			"user_id": user_id,
			"offset": 0,
			"limit": 15,
		}
		return self._client.fetch_data(
			endpoint="/creation-tools/v1/user/fans",
			params=params,
			total_key="total",
			limit=limit,
		)

	def fetch_following_gen(self, user_id: str, limit: int = 15) -> Generator[dict]:
		"""
		获取用户关注列表生成器
		Args:
			user_id: 用户ID
			limit: 获取数量限制(可选)
		Returns:
			关注列表生成器
		"""
		params = {
			"user_id": user_id,
			"offset": 0,
			"limit": 15,
		}
		return self._client.fetch_data(
			endpoint="/creation-tools/v1/user/followers",
			params=params,
			total_key="total",
			limit=limit,
		)

	def fetch_collections_gen(self, user_id: str, limit: int = 5) -> Generator[dict]:
		"""
		获取用户收藏作品生成器
		Args:
			user_id: 用户ID
			limit: 获取数量限制(可选)
		Returns:
			收藏作品生成器
		"""
		params = {
			"user_id": user_id,
			"offset": 0,
			"limit": 5,
		}
		return self._client.fetch_data(
			endpoint="/creation-tools/v1/user/center/collect/list",
			params=params,
			total_key="total",
			limit=limit,
		)

	def fetch_avatar_frames(self) -> dict:
		"""
		获取用户头像框列表
		Returns:
			头像框列表字典
		"""
		response = self._client.send_request(
			endpoint="/creation-tools/v1/user/avatar-frame/list",
			method="GET",
		)
		return response.json()

	def check_new_user_status(self) -> dict:
		"""
		检查用户是否为新用户
		Returns:
			新用户状态字典
		"""
		response = self._client.send_request(endpoint="https://api-creation.codemao.cn/neko/works/isNewUser", method="GET")
		return response.json()


@singleton
class UserManager:
	def __init__(self) -> None:
		"""初始化用户管理类"""
		self._client = acquire.CodeMaoClient()

	def update_status(self, doing: str) -> bool:
		"""
		更新用户状态
		Args:
			doing: 状态文本
		Returns:
			更新是否成功
		"""
		response = self._client.send_request(endpoint="/nemo/v2/user/basic", method="PUT", payload={"doing": doing})
		return response.status_code == HTTPSTATUS.OK.value

	def update_username(self, username: str) -> bool:
		"""
		更改用户名(实验性功能)
		Args:
			username: 新用户名
		Returns:
			更改是否成功
		"""
		msg = "此为实验性功能"
		raise ValueError(msg)
		response = self._client.send_request(
			endpoint="/tiger/v3/web/accounts/username",
			method="PATCH",
			payload={"username": username},
		)
		return response.status_code == HTTPSTATUS.NO_CONTENT.value

	def validate_phone_number(self, phone_num: int) -> dict:
		"""
		验证手机号码
		Args:
			phone_num: 手机号码
		Returns:
			验证结果字典
		"""
		params = {"phone_number": phone_num}
		response = self._client.send_request(endpoint="/web/users/phone_number/is_consistent", method="GET", params=params)
		return response.json()

	def update_password(self, old_password: str, new_password: str) -> bool:
		"""
		修改密码
		Args:
			old_password: 旧密码
			new_password: 新密码
		Returns:
			修改是否成功
		"""
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
		return response.status_code == HTTPSTATUS.NO_CONTENT.value

	def execute_request_phone_change_verification(self, old_phonenum: int, new_phonenum: int) -> bool:
		"""
		请求更换手机号验证码
		Args:
			old_phonenum: 旧手机号
			new_phonenum: 新手机号
		Returns:
			请求是否成功
		"""
		data = {"phone_number": new_phonenum, "old_phone_number": old_phonenum}
		response = self._client.send_request(
			endpoint="/tiger/v3/web/accounts/captcha/phone/change",
			method="POST",
			payload=data,
		)
		return response.status_code == HTTPSTATUS.NO_CONTENT.value

	def update_phone_number(self, captcha: int, phonenum: int) -> bool:
		"""
		更新手机号码
		Args:
			captcha: 验证码
			phonenum: 新手机号
		Returns:
			更新是否成功
		"""
		data = {"phone_number": phonenum, "captcha": captcha}
		response = self._client.send_request(
			endpoint="/tiger/v3/web/accounts/phone/change",
			method="PATCH",
			payload=data,
		)
		return response.json()

	def update_profile_basic(self, nickname: str, description: str) -> bool:
		"""
		更新个人资料基本信息
		Args:
			nickname: 昵称
			description: 个人描述
		Returns:
			更新是否成功
		"""
		data = {key: value for key, value in [("nickname", nickname), ("description", description)] if value is not None}
		if not data:
			msg = "至少需要传入一个参数"
			raise ValueError(msg)
		response = self._client.send_request(endpoint="/nemo/v2/user/basic", method="PUT", payload=data)
		return response.status_code == HTTPSTATUS.OK.value

	def delete_avatar_frame(self) -> bool:
		"""
		移除头像框
		Returns:
			移除是否成功
		"""
		response = self._client.send_request(
			endpoint="/creation-tools/v1/user/avatar-frame/cancel",
			method="PUT",
		)
		return response.status_code == HTTPSTATUS.OK.value

	def execute_apply_avatar_frame(self, frame_id: Literal[2, 3, 4]) -> bool:
		"""
		应用头像框
		Args:
			frame_id: 头像框ID(2=Lv2,3=Lv3,4=Lv4)
		Returns:
			应用是否成功
		"""
		response = self._client.send_request(
			endpoint=f"/creation-tools/v1/user/avatar-frame/{frame_id}",
			method="PUT",
		)
		return response.status_code == HTTPSTATUS.OK.value

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
		"""
		更新个人资料详细信息
		Args:
			avatar_url: 头像URL
			nickname: 昵称
			birthday: 生日时间戳
			description: 个人描述
			fullname: 全名
			qq: QQ号
			sex: 性别(0=女,1=男)
		Returns:
			更新是否成功
		"""
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
		return response.status_code == HTTPSTATUS.NO_CONTENT.value

	def update_profile_cover(self, cover_url: str) -> bool:
		"""
		更新个人主页封面
		Args:
			cover_url: 封面URL(预设封面:
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
		return response.status_code == HTTPSTATUS.OK.value

	def delete_user(self, reason: str, *, return_data: bool = False) -> dict | bool:
		data = {"closeReason": reason}
		response = self._client.send_request(endpoint="/tiger/v3/web/accounts/close", method="POST", payload=data)
		return response.json() if return_data else response.status_code == HTTPSTATUS.OK


# TODO@Aurzex: 待完善
# /tiger/v3/web/accounts/captcha/password/update
# 发送修改密码的短信验证码

# /tiger/v3/web/accounts/password/phone
# 通过短信验证码修改密码

# /tiger/v3/web/accounts/tokens/convert
# 获取用户访问令牌(Token)
