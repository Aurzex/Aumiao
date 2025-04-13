from collections.abc import Generator
from typing import Literal, cast

from src.utils import acquire
from src.utils.acquire import HTTPSTATUS
from src.utils.decorator import singleton


@singleton
class Obtain:
	def __init__(self) -> None:
		# 初始化获取数据对象
		self.acquire = acquire.CodeMaoClient()

	# 获取某人账号信息
	def get_user_details(self, user_id: str) -> dict:
		# 发送GET请求获取用户详细信息
		response = self.acquire.send_request(method="GET", endpoint=f"/api/user/info/detail/{user_id}")
		return response.json()

	# 获取用户荣誉
	def get_user_honor(self, user_id: str) -> dict:
		# 发送GET请求获取用户荣誉
		params = {"user_id": user_id}
		response = self.acquire.send_request(
			endpoint="/creation-tools/v1/user/center/honor",
			method="GET",
			params=params,
		)

		return response.json()

	# 获取用户精确数据
	def get_user_business(self, user_id: str) -> dict:
		# 发送GET请求获取用户精确数据
		params = {"user_id": user_id}
		response = self.acquire.send_request(endpoint="/nemo/v2/works/business/total", method="GET", params=params)
		return response.json()

	# 获取某人账号信息(简略)
	def get_user_info(self, user_id: str) -> dict:
		# 发送GET请求获取用户简略信息
		params = {"user_id": user_id}
		response = self.acquire.send_request(method="GET", endpoint="/nemo/v2/user/dynamic/info", params=params)
		return response.json()

	# 获取账户信息(详细)
	def get_data_details(self) -> dict:
		# 发送GET请求获取账户详细信息
		response = self.acquire.send_request(
			method="GET",
			endpoint="/web/users/details",
		)
		return response.json()

	# BUG 貌似api不起作用
	# 获取账户信息(简略)
	# def get_data_info(self) -> dict:
	# 	response = self.acquire.send_request(
	# 		method="GET",
	# 		endpoint="/web/user/info",
	# 	)

	# 	return response.json()

	# 获取账户信息
	def get_data_profile(self, method: Literal["web", "app"]) -> dict:
		response = self.acquire.send_request(method="GET", endpoint=f"/tiger/v3/{method}/accounts/profile")
		return response.json()

	# 获取账户安全信息
	def get_data_privacy(self) -> dict:
		response = self.acquire.send_request(method="GET", endpoint="/tiger/v3/web/accounts/privacy")
		return response.json()

	# 获取账户信息
	def get_data_tiger(self) -> dict:
		response = self.acquire.send_request(endpoint="/tiger/user", method="GET")
		return response.json()

	# 获取用户点赞,再创作,收藏分
	def get_data_score(self) -> dict:
		response = self.acquire.send_request(endpoint="/nemo/v3/user/grade/details", method="GET")
		return response.json()

	# 获取用户等级
	def get_data_level(self) -> dict:
		response = self.acquire.send_request(endpoint="/nemo/v3/user/level/info", method="GET")
		return response.json()

	# 获取用户姓名
	def get_data_name(self) -> dict:
		response = self.acquire.send_request(endpoint="/api/v2/pc/lesson/user/info", method="GET")
		return response.json()

	# 获取个人作品列表的函数
	def get_user_works_web(self, user_id: str, types: Literal["newest", "hot"] = "newest", limit: int | None = 5) -> Generator[dict]:
		params = {
			"type": types,
			"user_id": user_id,
			"offset": 0,
			"limit": 5,
		}
		return self.acquire.fetch_data(
			endpoint="/creation-tools/v2/user/center/work-list",
			params=params,
			total_key="total",
			limit=limit,
		)

	# 搜索用户作品
	def search_data_works_nemo(self, query: str, query_type: str = "name", page: int = 1, limit: int = 10) -> dict:
		params = {
			"query": query,
			"query_type": query_type,
			"page": page,
			"limit": limit,
		}
		response = self.acquire.send_request(endpoint="tiger/nemo/user/works/search", method="GET", params=params)
		return response.json()

	# 获取用户云端作品
	def get_works_cloud(self, types: Literal["nemo", "kitten"], limit: int = 10, offset: int = 0) -> dict:
		if types == "nemo":
			work_type = 8
		elif types == "kitten":
			work_type = 1
		params = {"limit": limit, "offset": offset, "work_type": work_type}
		response = self.acquire.send_request(endpoint="/creation-tools/v1/works/list/user", params=params, method="GET")
		return response.json()

	# 获取用户nemo作品
	def get_works_nemo_published(self, method: Literal["published"], limit: int | None = 15) -> Generator[dict]:
		params = {"limit": 15, "offset": 0}
		return self.acquire.fetch_data(
			endpoint=f"/nemo/v2/works/list/user/{method}",
			params=params,
			limit=limit,
		)

	# 获取用户KN作品
	def get_works_kn(
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
		# kn获取全部作品示例链接:https://api-creation.codemao.cn/neko/works/v2/list/user?name=&limit=24&offset=0&status=1&work_business_classify=1
		if method == "published":
			url = "https://api-creation.codemao.cn/neko/works/list/user/published"
		elif method == "total":
			url = "https://api-creation.codemao.cn/neko/works/v2/list/user"
		params = {"offset": 0, "limit": 15}
		params = cast(dict, params)
		params.update(extra_params or {})
		return self.acquire.fetch_data(endpoint=url, params=params, limit=limit)

	# 获取用户kitten作品列表
	def get_works_kitten(
		self,
		version: Literal["KITTEN_V4", "KITTEN_V3"],
		status: Literal["PUBLISHED", "UNPUBLISHED", "all"],
		work_status: Literal["SHOW"] = "SHOW",
		limit: int | None = 30,
	) -> Generator[dict]:
		params = {
			"offset": 0,
			"limit": 30,
			"version_no": version,
			"work_status": work_status,
			"published_status": status,
		}
		return self.acquire.fetch_data(
			endpoint="https://api-creation.codemao.cn/kitten/common/work/list2",
			params=params,
			limit=limit,
		)

	# 获取用户nemo作品列表
	def get_works_nemo(self, status: Literal["PUBLISHED", "UNPUBLISHED", "all"], limit: int | None = 30) -> Generator[dict]:
		params = {"offset": 0, "limit": 30, "published_status": status}
		return self.acquire.fetch_data(
			endpoint="/creation-tools/v1/works/list",
			params=params,
			limit=limit,
		)

	# 获取用户海龟编辑器作品列表
	def get_works_wood(
		self,
		status: Literal["PUBLISHED", "UNPUBLISHED"],
		language_type: int = 0,
		work_status: Literal["SHOW"] = "SHOW",
		limit: int | None = 30,
	) -> Generator[dict]:
		params = {
			"offset": 0,
			"limit": 30,
			"language_type": language_type,
			"work_status": work_status,
			"published_status": status,
		}
		return self.acquire.fetch_data(
			endpoint="https://api-creation.codemao.cn/wood/comm/work/list",
			params=params,
			limit=limit,
		)

	# 获取用户box作品列表
	def get_works_box(self, status: Literal["all", "PUBLISHED", "UNPUBLISHED"], work_status: Literal["SHOW"] = "SHOW", limit: int | None = 30) -> Generator[dict]:
		params = {
			"offset": 0,
			"limit": 30,
			"work_status": work_status,
			"published_status": status,
		}
		return self.acquire.fetch_data(
			endpoint="https://api-creation.codemao.cn/box/v2/work/list",
			params=params,
			limit=limit,
		)

	# 获取用户小说列表
	def get_works_fanfic(self, fiction_status: Literal["SHOW"] = "SHOW", limit: int | None = 30) -> Generator[dict]:
		params = {"offset": 0, "limit": 30, "fiction_status": fiction_status}
		return self.acquire.fetch_data(
			endpoint="/web/fanfic/my/new",
			params=params,
			limit=limit,
		)

	# 获取用户coco作品列表
	# TODO@Aurzex: 参数不确定
	def get_works_coco(self, status: int = 1, *, published: bool = True, limit: int | None = 30) -> Generator[dict]:
		params = {
			"offset": 0,
			"limit": 30,
			"status": status,
			"published": published,
		}
		return self.acquire.fetch_data(
			endpoint="https://api-creation.codemao.cn/coconut/web/work/list",
			params=params,
			data_key="data.items",
			total_key="data.total",
			limit=limit,
		)

	# 获取粉丝列表
	def get_user_fans(self, user_id: str, limit: int = 15) -> Generator[dict]:
		params = {
			"user_id": user_id,
			"offset": 0,
			"limit": 15,
		}
		return self.acquire.fetch_data(
			endpoint="/creation-tools/v1/user/fans",
			params=params,
			total_key="total",
			limit=limit,
		)

	# 获取关注列表
	def get_user_follows(self, user_id: str, limit: int = 15) -> Generator[dict]:
		params = {
			"user_id": user_id,
			"offset": 0,
			"limit": 15,
		}
		return self.acquire.fetch_data(
			endpoint="/creation-tools/v1/user/followers",
			params=params,
			total_key="total",
			limit=limit,
		)

	# 获取用户收藏的作品的信息
	def get_user_collects(self, user_id: str, limit: int = 5) -> Generator[dict]:
		params = {
			"user_id": user_id,
			"offset": 0,
			"limit": 5,
		}
		return self.acquire.fetch_data(
			endpoint="/creation-tools/v1/user/center/collect/list",
			params=params,
			total_key="total",
			limit=limit,
		)

	# 获取用户头像框列表
	def get_user_avatar_frame(self) -> dict:
		response = self.acquire.send_request(
			endpoint="/creation-tools/v1/user/avatar-frame/list",
			method="GET",
		)
		return response.json()

	# 获取用户是否为新用户
	def get_is_new_user(self) -> dict:
		response = self.acquire.send_request(endpoint="https://api-creation.codemao.cn/neko/works/isNewUser", method="GET")
		return response.json()


@singleton
class Motion:
	def __init__(self) -> None:
		# 初始化acquire对象
		self.acquire = acquire.CodeMaoClient()

	def set_data_doing(self, doing: str) -> bool:
		"""发送PUT请求,设置正在做的事"""
		response = self.acquire.send_request(endpoint="/nemo/v2/user/basic", method="PUT", payload={"doing": doing})
		# 返回请求状态码是否为200
		return response.status_code == HTTPSTATUS.OK

	def set_data_username(self, username: str) -> bool:
		"""发送PATCH请求,设置登录用户名(实验性功能)"""
		response = self.acquire.send_request(
			endpoint="/tiger/v3/web/accounts/username",
			method="PATCH",
			payload={"username": username},
		)
		# 返回请求状态码是否为204
		return response.status_code == HTTPSTATUS.NO_CONTENT

	def verify_phone(self, phone_num: int) -> dict:
		"""发送GET请求,验证手机号"""
		params = {"phone_number": phone_num}
		response = self.acquire.send_request(endpoint="/web/users/phone_number/is_consistent", method="GET", params=params)
		# 返回请求结果
		return response.json()

	def modify_password(self, old_password: str, new_password: str) -> bool:
		"""发送PATCH请求,修改密码"""
		data = {
			"old_password": old_password,
			"password": new_password,
			"confirm_password": new_password,
		}
		response = self.acquire.send_request(
			endpoint="/tiger/v3/web/accounts/password",
			method="PATCH",
			payload=data,
		)
		# 返回请求状态码是否为204
		return response.status_code == HTTPSTATUS.NO_CONTENT

	def modify_phonenum_captcha(self, old_phonenum: int, new_phonenum: int) -> bool:
		"""发送POST请求,修改手机号(获取验证码)"""
		data = {"phone_number": new_phonenum, "old_phone_number": old_phonenum}
		response = self.acquire.send_request(
			endpoint="/tiger/v3/web/accounts/captcha/phone/change",
			method="POST",
			payload=data,
		)
		# 返回请求状态码是否为204
		return response.status_code == HTTPSTATUS.NO_CONTENT

	def modify_phonenum(self, captcha: int, phonenum: int) -> bool:
		"""发送PATCH请求,修改手机号"""
		data = {"phone_number": phonenum, "captcha": captcha}
		response = self.acquire.send_request(
			endpoint="/tiger/v3/web/accounts/phone/change",
			method="PATCH",
			payload=data,
		)
		# 返回请求结果
		return response.json()

	def set_nemo_basic(self, nickname: str, description: str) -> bool:
		"""设置nemo头像,昵称,个性签名"""
		data = {key: value for key, value in [("nickname", nickname), ("description", description)] if value is not None}
		if not data:
			msg = "至少需要传入一个参数"
			raise ValueError(msg)
		response = self.acquire.send_request(endpoint="/nemo/v2/user/basic", method="PUT", payload=data)
		# 返回请求状态码是否为200
		return response.status_code == HTTPSTATUS.OK

	def cancel_avatar_frame(self) -> bool:
		"""取消设置头像框"""
		response = self.acquire.send_request(
			endpoint="/creation-tools/v1/user/avatar-frame/cancel",
			method="PUT",
		)
		# 返回请求状态码是否为200
		return response.status_code == HTTPSTATUS.OK

	# id 2,3,4 代表Lv2,3,4头像框
	def set_avatar_frame(self, frame_id: Literal[2, 3, 4]) -> bool:
		"""设置头像框"""
		response = self.acquire.send_request(
			endpoint=f"/creation-tools/v1/user/avatar-frame/{frame_id}",
			method="PUT",
		)
		# 返回请求状态码是否为200
		return response.status_code == HTTPSTATUS.OK

	# 设置info
	# birthday值为timestamp
	# sex中0为女,1为男
	# /tiger/v3/web/accounts/info
	def set_data_info(
		self,
		avatar_url: str,
		nickname: str,
		birthday: int,
		description: str,
		fullname: str,
		qq: str,
		sex: Literal[0, 1],
	) -> bool:
		# 发送PATCH请求,设置info
		data = {
			"avatar_url": avatar_url,
			"nickname": nickname,
			"birthday": birthday,
			"description": description,
			"fullname": fullname,
			"qq": qq,
			"sex": sex,
		}
		response = self.acquire.send_request(
			endpoint="/tiger/v3/web/accounts/info",
			method="PATCH",
			payload=data,
		)
		# 返回请求状态码是否为204
		return response.status_code == HTTPSTATUS.NO_CONTENT
