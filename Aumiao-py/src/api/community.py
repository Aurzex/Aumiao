from collections.abc import Generator
from functools import lru_cache
from typing import Any, Literal

from src.utils import acquire, data, tool
from src.utils.acquire import HTTPSTATUS
from src.utils.decorator import singleton


# 编程猫所有api中若包含v2等字样,表示第几版本,同样比它低的版本也可使用
@singleton
class AuthManager:
	"""
	概述:用户登录
	参数:
	`identity (str)`: 用户身份标识。
	`password (str)`: 用户密码。
	`pid (str = "65edCTyg")`: 请求的 PID,用于标识请求来源。
	返回值:
	str | None: 函数返回一个字符串,表示登录请求的响应结果。如果请求失败,则返回 None。
	"""

	def __init__(self) -> None:
		# 初始化CodeMaoClient和CodeMaoProcess对象
		self._client = acquire.CodeMaoClient()
		# 获取设置数据
		self.tool = tool
		self.setting = data.SettingManager().data

	# 密码登录函数
	def authenticate_with_password(
		self,
		identity: str,
		password: str,
		pid: str = "65edCTyg",
		status: Literal["judgement", "average", "edu"] = "average",
	) -> dict:
		# cookies = utils.dict_from_cookiejar(response.cookies)
		#   soup = BeautifulSoup(
		#       send_request("https://shequ.codemao.cn", "GET").text,
		#       "html.parser",
		#   )
		#   见https://api.docs.codemao.work/user/login?id=pid
		#   pid = loads(soup.find_all("script")[0].string.split("=")[1])["pid"]
		# 发送登录请求
		self._client.switch_account(token="", identity="blank")  # 切换账号
		response = self._client.send_request(
			endpoint="/tiger/v3/web/accounts/login",
			method="POST",
			payload={
				"identity": identity,
				"password": password,
				"pid": pid,
			},
		)
		# 更新cookies
		# if save_status:
		# 	self._client.update_cookies(response.cookies)
		self._client.switch_account(token=response.json()["auth"]["token"], identity=status)
		return response.json()

	# cookie登录
	def authenticate_with_cookies(
		self,
		cookies: str,
		status: Literal["judgement", "average", "edu"] = "average",
	) -> bool | None:
		try:
			# 将cookie字符串转换为字典
			cookie = dict([item.split("=", 1) for item in cookies.split("; ")])
			# 检查是否合规,不能放到headers中
		except (KeyError, ValueError) as err:
			print(f"表达式输入不合法 {err}")
			return False
		# 发送登录请求
		self._client.send_request(
			endpoint=self.setting.PARAMETER.cookie_check_url,
			method="POST",
			payload={},
			headers={**self._client.headers, "cookie": cookies},
		)
		# 更新cookies
		# self._client.update_cookies(cookie)
		self._client.switch_account(cookie["authorization"], identity=status)
		return None

	# token登录(毛毡最新登录方式)
	def authenticate_with_token(
		self,
		identity: str,
		password: str,
		pid: str = "65edCTyg",
		status: Literal["judgement", "average", "edu"] = "average",
	) -> dict:
		timestamp = DataFetcher().fetch_current_timestamp_10()["data"]
		response = self._get_login_ticket(identity=identity, timestamp=timestamp, pid=pid)
		ticket = response["ticket"]
		resp = self._get_login_security_info(identity=identity, password=password, ticket=ticket, pid=pid)
		self._client.switch_account(token=resp["auth"]["token"], identity=status)
		return resp

	# 返回完整cookie
	def fetch_auth_details(self, token: str) -> dict[str, Any]:
		# uuid_ca = uuid.uuid1()
		# token_ca = {"authorization": token, "__ca_uid_key__": str(uuid_ca)}
		# 无上面这两句会缺少__ca_uid_key__
		token_ca = {"authorization": token}
		cookie_str = self.tool.DataConverter().convert_cookie(token_ca)  # 将cookie转换为字符串
		headers = {**self._client.headers, "cookie": cookie_str}  # 添加cookie到headers中
		response = self._client.send_request(method="GET", endpoint="/web/users/details", headers=headers)  # 发送请求获取用户详情
		auth = response.cookies.get_dict()  # pyright: ignore[reportGeneralTypeIssues] # 获取cookie
		return {**token_ca, **auth}  # 返回完整cookie

	# 退出登录
	def execute_logout(self, method: Literal["web", "app"]) -> bool:
		# 发送请求,请求路径为/tiger/v3/{method}/accounts/logout,请求方法为POST,请求体为空
		response = self._client.send_request(
			endpoint=f"/tiger/v3/{method}/accounts/logout",
			method="POST",
			payload={},
		)
		# 返回响应状态码是否为204
		return response.status_code == HTTPSTATUS.NO_CONTENT.value

	# 登录信息
	def _get_login_security_info(
		self,
		identity: str,
		password: str,
		ticket: str,
		pid: str = "65edCTyg",
		agreement_ids: list = [-1],
	) -> dict:
		# 创建一个字典,包含用户名、密码、pid和agreement_ids
		data = {
			"identity": identity,
			"password": password,
			"pid": pid,
			"agreement_ids": agreement_ids,
		}
		# 发送POST请求,获取登录安全信息
		response = self._client.send_request(
			endpoint="/tiger/v3/web/accounts/login/security",
			method="POST",
			payload=data,
			headers={**self._client.headers, "x-captcha-ticket": ticket},
		)
		# 更新cookies
		# self._client.update_cookies(response.cookies)
		# 返回响应的json数据
		return response.json()

	# 登录ticket获取
	def _get_login_ticket(
		self,
		identity: str | int,
		timestamp: int,
		scene: str | None = None,
		pid: str = "65edCTyg",
		deviced: str | None = None,
	) -> dict:
		# 可填可不填
		# uuid_ca = uuid.uuid1()
		# _ca = {"__ca_uid_key__": str(uuid_ca)}
		# cookie_str = self.tool_process.convert_cookie_to_str(_ca)
		# headers = {**self._client.HEADERS, "cookie": cookie_str}
		data = {
			"identity": identity,
			"scene": scene,
			"pid": pid,
			"deviceId": deviced,
			"timestamp": timestamp,
		}
		response = self._client.send_request(
			endpoint="https://open-service.codemao.cn/captcha/rule/v3",
			method="POST",
			payload=data,
			# headers=headers,
		)
		# self._client.update_cookies(response.cookies)
		return response.json()


@singleton
class DataFetcher:
	def __init__(self) -> None:
		# 初始化acquire对象
		self._client = acquire.CodeMaoClient()

	# 获取随机昵称
	def fetch_random_nickname(self) -> str:
		# 发送GET请求,获取随机昵称
		response = self._client.send_request(
			method="GET",
			endpoint="/api/user/random/nickname",
		)
		# 返回响应中的昵称
		return response.json()["data"]["nickname"]

	# 获取新消息数量
	def fetch_message_count(self, method: Literal["web", "nemo"]) -> dict:
		# 根据方法选择不同的url
		if method == "web":
			url = "/web/message-record/count"
		elif method == "nemo":
			url = "/nemo/v2/user/message/count"
		else:
			msg = "不支持的方法"
			raise ValueError(msg)
		# 发送GET请求,获取新消息数量
		record = self._client.send_request(
			endpoint=url,
			method="GET",
		)
		# 返回响应
		return record.json()

	# 获取回复
	def fetch_replies(
		self,
		types: Literal["LIKE_FORK", "COMMENT_REPLY", "SYSTEM"],
		limit: int = 15,
		offset: int = 0,
	) -> dict:
		# 构造参数
		params = {"query_type": types, "limit": limit, "offset": offset}
		# 获取前*个回复
		response = self._client.send_request(
			endpoint="/web/message-record",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取nemo消息
	def fetch_nemo_messages(self, types: Literal["fork", "like"]) -> dict:
		extra_url = 1 if types == "like" else 3
		url = f"/nemo/v2/user/message/{extra_url}"
		response = self._client.send_request(endpoint=url, method="GET")
		return response.json()

	# 获取点个猫更新
	def fetch_pickcat_update(self) -> dict:
		response = self._client.send_request(endpoint="https://update.codemao.cn/updatev2/appsdk", method="GET")
		return response.json()

	# 获取kitten4更新
	def fetch_kitten4_update(self) -> dict:
		time_stamp = self.fetch_current_timestamp_10()["data"]
		params = {"TIME": time_stamp}
		response = self._client.send_request(endpoint="https://kn-cdn.codemao.cn/kitten4/application/kitten4_update_info.json", method="GET", params=params)
		return response.json()

	# 获取kitten更新
	def fetch_kitten_update(self) -> dict:
		time_stamp = self.fetch_current_timestamp_10()["data"]
		params = {"timeStamp": time_stamp}
		response = self._client.send_request(endpoint="https://kn-cdn.codemao.cn/application/kitten_update_info.json", method="GET", params=params)
		return response.json()

	# 获取海龟编辑器更新
	def fetch_wood_editor_update(self) -> dict:
		time_stamp = self.fetch_current_timestamp_10()["data"]
		params = {"timeStamp": time_stamp}
		response = self._client.send_request(endpoint="https://static-am.codemao.cn/wood/client/xp/prod/package.json", method="GET", params=params)
		return response.json()

	# 获取源码智造编辑器更新
	def fetch_matrix_editor_update(self) -> dict:
		time_stamp = self.fetch_current_timestamp_10()["data"]
		params = {"timeStamp": time_stamp}
		response = self._client.send_request(endpoint="https://public-static-edu.codemao.cn/matrix/publish/desktop_matrix.json", method="GET", params=params)
		return response.json()

	# 获取时间戳
	def fetch_current_timestamp_10(self) -> dict:
		response = self._client.send_request(endpoint="/coconut/clouddb/currentTime", method="GET")
		return response.json()

	def fetch_current_timestamp_13(self) -> dict:
		response = self._client.send_request(endpoint="https://time.codemao.cn/time/current", method="GET")
		return response.json()

	# 获取推荐头图
	def fetch_web_banners(
		self,
		types: (Literal["FLOAT_BANNER", "OFFICIAL", "CODE_TV", "WOKE_SHOP", "MATERIAL_NORMAL"] | None) = None,
	) -> dict:
		# 所有:不设置type,首页:OFFICIAL, 工作室页:WORK_SHOP
		# 素材页:MATERIAL_NORMAL, 右下角浮动区域:FLOAT_BANNER, 编程TV:CODE_TV
		params = {"type": types}
		response = self._client.send_request(endpoint="/web/banners/all", method="GET", params=params)
		return response.json()

	# 获取推荐头图
	def fetch_nemo_banners(self, types: Literal[1, 2, 3]) -> dict:
		# 1:点个猫推荐页 2:点个猫主题页 3:点个猫课程页
		params = {"banner_type": types}
		response = self._client.send_request(endpoint="/nemo/v2/home/banners", method="GET", params=params)
		return response.json()

	# 获取举报类型
	@lru_cache  # noqa: B019
	def fetch_report_reasons(self) -> dict:
		response = self._client.send_request(endpoint="/web/reports/reasons/all", method="GET")
		return response.json()

	# 获取nemo配置
	# TODO@Aurzex: 待完善
	def _fetch_nemo_config(self) -> str:
		response = self._client.send_request(endpoint="https://nemo.codemao.cn/config", method="GET")
		return response.json()

	# 获取社区网络服务
	def fetch_community_config(self) -> dict:
		response = self._client.send_request(endpoint="https://c.codemao.cn/config", method="GET")
		return response.json()

	# 获取编程猫网络服务
	def fetch_client_config(self) -> dict:
		response = self._client.send_request(endpoint="https://player.codemao.cn/new/client_config.json", method="GET")
		return response.json()

	# 获取编程猫首页作品
	def fetch_recommended_works(self, types: Literal[1, 2]) -> dict:
		# 1为点猫精选,2为新作喵喵看
		params = {"type": types}
		response = self._client.send_request(
			endpoint="/creation-tools/v1/pc/home/recommend-work",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取nemo端新作喵喵看作品
	def fetch_new_recommend_works(self, limit: int = 15, offset: int = 0) -> dict:
		params = {"limit": limit, "offset": offset}
		response = self._client.send_request(endpoint="/nemo/v3/new-recommend/more/list", method="GET", params=params)
		return response.json()

	# 获取编程猫nemo作品推荐
	def fetch_recommended_works_nemo(self) -> dict:
		response = self._client.send_request(endpoint="/nemo/v2/system/recommended/pool", method="GET")
		return response.json()

	# 获取编程猫首页推荐channel
	def fetch_work_channels(self, types: Literal["KITTEN", "NEMO"]) -> dict:
		params = {"type": types}
		response = self._client.send_request(
			endpoint="/web/works/channels/list",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取指定channel
	def fetch_channel_works(self, channel_id: int, types: Literal["KITTEN", "NEMO"], limit: int = 5, page: int = 1) -> dict:
		params = {"type": types, "page": page, "limit": limit}
		response = self._client.send_request(
			endpoint=f"/web/works/channels/{channel_id}/works",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取社区星推荐
	def fetch_recommended_users(self) -> dict:
		response = self._client.send_request(endpoint="/web/users/recommended", method="GET")
		return response.json()

	# 获取训练师小课堂
	def fetch_training_courses(self) -> dict:
		response = self._client.send_request(endpoint="https://backend.box3.fun/diversion/codemao/post", method="GET")
		return response.json()

	# 获取KN课程
	def fetch_kn_courses(self) -> dict:
		response = self._client.send_request(endpoint="/creation-tools/v1/home/especially/course", method="GET")
		return response.json()

	# 获取KN公开课
	def fetch_public_courses_gen(self, limit: int | None = 10) -> Generator[dict]:
		params = {"limit": 10, "offset": 0}
		return self._client.fetch_data(
			endpoint="https://api-creation.codemao.cn/neko/course/publish/list",
			params=params,
			limit=limit,
			total_key="total_course",
			# total_key也可设置为"course_page.total",
			data_key="course_page.items",
		)

	# 获取KN模板作品
	# subject_id为一时返回基础指南,为2时返回进阶指南
	def fetch_sample_works(self, subject_id: Literal[1, 2]) -> dict:
		params = {"subject_id": subject_id}
		response = self._client.send_request(endpoint="https://api-creation.codemao.cn/neko/sample/list", params=params, method="GET")
		return response.json()

	# 获取社区各个部分开启状态
	# TODO@Aurzex: 待完善
	def fetch_community_status(self, types: Literal["WEB_FORUM_STATUS", "WEB_FICTION_STATUS"]) -> dict:
		response = self._client.send_request(endpoint=f"/web/config/tab/on-off/status?config_type={types}", method="GET")
		return response.json()

	# 获取kitten编辑页面精选活动
	def fetch_kitten_activities(self) -> dict:
		response = self._client.send_request(
			endpoint="https://api-creation.codemao.cn/kitten/activity/choiceness/list",
			method="GET",
		)
		return response.json()

	# 获取nemo端教程合集
	def fetch_course_packages_gen(self, platform: int = 1, limit: int | None = 50) -> Generator[dict]:
		params = {"limit": 50, "offset": 0, "platform": platform}
		return self._client.fetch_data(
			endpoint="/creation-tools/v1/course/package/list",
			params=params,
			limit=limit,
		)

	# 获取nemo教程
	def fetch_course_details_gen(self, course_package_id: int, limit: int | None = 50) -> Generator[dict]:
		# course_package_id由fetch_course_packages_gen中获取
		params = {
			"course_package_id": course_package_id,
			"limit": 50,
			"offset": 0,
		}
		return self._client.fetch_data(
			endpoint="/creation-tools/v1/course/list/search",
			params=params,
			data_key="course_page.items",
			limit=limit,
			# 参数中total_key也可用total_course
		)

	# 获取教学计划
	# TODO @Aurzex: 未知
	def fetch_teaching_plans_gen(self, limit: int = 100) -> Generator[dict]:
		params = {"limit": limit, "offset": 0}
		return self._client.fetch_data(endpoint="https://api-creation.codemao.cn/neko/teaching-plan/list/team", params=params, limit=limit)


@singleton
class UserAction:
	def __init__(self) -> None:
		# 初始化CodeMaoClient对象
		self._client = acquire.CodeMaoClient()

	# 签订友好协议
	def execute_sign_agreement(self) -> bool:
		response = self._client.send_request(endpoint="/nemo/v3/user/level/signature", method="POST")
		return response.status_code == HTTPSTATUS.OK.value

	# 获取用户协议
	def fetch_agreements(self) -> dict:
		response = self._client.send_request(endpoint="/tiger/v3/web/accounts/agreements", method="GET")
		return response.json()

	# 注册
	def create_account(
		self,
		identity: str,
		password: str,
		captcha: str,
		pid: str = "65edCTyg",
		agreement_ids: list = [186, 13],
	) -> dict:
		data = {
			"identity": identity,
			"password": password,
			"captcha": captcha,
			"pid": pid,
			"agreement_ids": agreement_ids,
		}
		response = self._client.send_request(
			endpoint="/tiger/v3/web/accounts/register/phone/with-agreement",
			method="POST",
			payload=data,
		)
		return response.json()

	# 删除消息
	def delete_message(self, message_id: int) -> bool:
		response = self._client.send_request(
			endpoint=f"/web/message-record/{message_id}",
			method="DELETE",
		)
		return response.status_code == HTTPSTATUS.NO_CONTENT.value
