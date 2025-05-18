from collections.abc import Generator
from typing import Literal

from requests import Response

from src.utils import acquire, tool
from src.utils.acquire import HTTPSTATUS
from src.utils.decorator import singleton


# sb编程猫,params中的{"_": timestamp}可以替换为{"TIME": timestamp}
@singleton
class Motion:
	def __init__(self) -> None:
		# 初始化CodeMaoClient对象
		self.acquire = acquire.CodeMaoClient()
		self.tool = tool

	# 更改姓名
	def update_name(self, user_id: int, real_name: str) -> bool:
		# 获取时间戳
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		# 构造参数
		params = {"TIME": timestamp, "userId": user_id, "realName": real_name}

		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/account/updateName",
			method="GET",
			params=params,
		)

		return response.status_code == HTTPSTATUS.OK.value

	# 创建班级
	def create_class(self, name: str) -> dict:
		data = {"name": name}

		response = self.acquire.send_request(endpoint="https://eduzone.codemao.cn/edu/zone/class", method="POST", payload=data)
		# 返回响应数据
		return response.json()

	# 删除班级
	def delete_class(self, class_id: int) -> bool:
		# 获取时间戳
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		# 构造参数
		params = {"TIME": timestamp}

		response = self.acquire.send_request(
			endpoint=f"https://eduzone.codemao.cn/edu/zone/class/{class_id}",
			method="DELETE",
			params=params,
		)
		return response.status_code == HTTPSTATUS.NO_CONTENT.value

	# 班级内新建学生账号
	def create_student(self, name: list[str], class_id: int) -> bool:
		data = {"student_names": name}

		response = self.acquire.send_request(
			endpoint=f"https://eduzone.codemao.cn/edu/zone/class/{class_id}/students",
			method="POST",
			payload=data,
		)
		# 这个api需要验证headers中的Accept-Language,否则报403
		return response.status_code == HTTPSTATUS.OK.value

	# 重置密码
	def reset_password(self, stu_id: int) -> dict:
		response = self.acquire.send_request(
			endpoint=f"https://eduzone.codemao.cn/edu/zone/students/{stu_id}/password",
			method="PATCH",
			payload={},
		)
		# {"id":405584024,"password":"805753"}
		return response.json()

	# 批量重置密码(返回xlsx文件)
	def reset_password_list(self, stu_list: list[int]) -> Response:
		return self.acquire.send_request(endpoint="https://eduzone.codemao.cn/edu/zone/students/password", method="PATCH", payload={"student_id": stu_list})

	# 删除班级内学生
	def remove_student(self, stu_id: int) -> bool:
		data = {}
		response = self.acquire.send_request(
			endpoint=f"https://eduzone.codemao.cn/edu/zone/student/remove/{stu_id}",
			method="POST",
			payload=data,
		)
		return response.status_code == HTTPSTATUS.OK.value

	# 添加、修改自定义备课包
	# patch为修改信息,post用于创建备课包
	def add_customized_package(self, method: Literal["POST", "PATCH"], avatar_url: str, description: str, name: str, *, return_data: bool = True) -> dict | bool:
		data = {"avatar_url": avatar_url, "description": description, "name": name}

		response = self.acquire.send_request(endpoint="https://eduzone.codemao.cn/edu/zone/lesson/customized/packages", method=method, payload=data)

		return response.json() if return_data else response.status_code == HTTPSTATUS.OK.value
		# 返回响应数据或请求状态码是否为200

	# 删除作品
	def delete_work(self, work_id: int) -> bool:
		response = self.acquire.send_request(
			endpoint=f"https://eduzone.codemao.cn/edu/zone/work/{work_id}/delete",
			method="POST",
			payload={},
		)
		return response.status_code == HTTPSTATUS.OK.value

	# 移除班级内的学生至无班级学生
	def remove_student_to_no_class(self, class_id: int, stu_id: int) -> bool:
		params = {"student_ids[]": stu_id}
		response = self.acquire.send_request(
			endpoint=f"https://eduzone.codemao.cn/edu/zone/class/{class_id}/students",
			method="DELETE",
			params=params,
		)
		return response.status_code == HTTPSTATUS.NO_CONTENT.value

	# 获取活动课程包
	def get_activity_package_open(self, package_id: int) -> dict:
		payload = {"packageId": package_id}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/activity/open/package",
			method="POST",
			payload=payload,
		)
		return response.json()

	# 获取活动课程包
	def get_activity_package(self) -> dict:
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/activity/list/activity/package",
			method="POST",
			payload={},
		)
		return response.json()

	# 标记所有消息为已读
	def mark_all_message_read(self) -> bool:
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/invite/message/all/read",
			method="POST",
			payload={},
		)
		return response.status_code == HTTPSTATUS.OK.value

	# 给学生作品评分
	# score取值范围为0-25
	def evaluate_student_work(self, work_id: int, work_name: str, artistic_score: int, creative_sore: int, commentary: str, logical_score: int, programming_score: int) -> bool:
		data = {
			"artistic_score": artistic_score,
			"commentary": commentary,
			"creative_score": creative_sore,
			"id": work_id,
			"logical_score": logical_score,
			"programming_score": programming_score,
			"work_name": work_name,
		}

		response = self.acquire.send_request(endpoint="https://eduzone.codemao.cn/edu/zone/work/manager/works/scores", method="PATCH", payload=data)
		return response.status_code == HTTPSTATUS.NO_CONTENT.value

	# 邀请学生
	# TODO@Aurzex: type是否为1待确认
	# class_id为你想要让学生进的班级id
	# type为0时按用户名邀请,为1时按手机号邀请
	# identity为想要邀请的列表
	def invite_student_to_class(self, class_id: int, types: Literal["0", "1"], identity: list[str | int]) -> bool:
		data = {"identity": identity, "type": types, "classId": class_id}
		response = self.acquire.send_request(
			endpoint=f"https://eduzone.codemao.cn/edu/zone/class/{class_id}/students/invite",
			method="POST",
			payload=data,
		)
		return response.status_code == HTTPSTATUS.OK.value

	# 接受邀请(学生)
	# message_id在get_invite_message中获取
	def accept_invitation(self, message_id: int) -> bool:
		response = self.acquire.send_request(
			endpoint=f"https://eduzone.codemao.cn/edu/zone/invite/student/message/{message_id}/accept",
			method="POST",
			payload={},
		)
		return response.status_code == HTTPSTATUS.OK.value


@singleton
class Obtain:
	def __init__(self) -> None:
		# 初始化获取CodeMaoClient对象
		self.acquire = acquire.CodeMaoClient()
		self.tool = tool

	# 获取个人信息
	def get_data_details(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}

		response = self.acquire.send_request(endpoint="https://eduzone.codemao.cn/edu/zone", method="GET", params=params)
		return response.json()

	# 猜测返回的role_id当值为20001时为学生账号,10002为教师账号
	# 获取账户状态
	def get_account_status(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		# 设置参数
		params = {"TIME": timestamp}

		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/api/home/account",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取未读消息数
	def get_message_count(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		# 设置参数
		params = {"TIME": timestamp}

		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/system/message/unread/num",
			method="GET",
			params=params,
		)
		# 返回响应数据
		return response.json()

	# 获取通知公告消息列表
	def get_message_list(self, limit: int | None = 10) -> Generator[dict]:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"page": 1, "limit": 10, "TIME": timestamp}
		return self.acquire.fetch_data(
			endpoint="https://eduzone.codemao.cn/edu/zone/system/message/list",
			params=params,
			pagination_method="page",
			config={"amount_key": "limit", "offset_key": "page"},
			limit=limit,
		)

	# 获取消息提醒列表
	def get_message_remind(self, limit: int | None = 10) -> Generator[dict]:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"page": 1, "limit": 10, "TIME": timestamp}
		return self.acquire.fetch_data(
			endpoint="https://eduzone.codemao.cn/edu/zone/invite/teacher/messages",
			params=params,
			pagination_method="page",
			config={"amount_key": "limit", "offset_key": "page"},
			limit=limit,
		)

	# 获取学校分类列表
	def get_school_label(self) -> dict:
		# 获取时间戳
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		# 设置参数
		params = {"TIME": timestamp}

		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/school/open/grade/list",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取所有班级
	def get_classes(self, method: Literal["detail", "simple"] = "simple", limit: int | None = 20) -> dict | Generator:
		if method == "simple":
			# 发送GET请求获取简单班级信息
			classes = self.acquire.send_request(
				endpoint="https://eduzone.codemao.cn/edu/zone/classes/simple",
				method="GET",
			).json()
		elif method == "detail":
			# 发送GET请求获取详细班级信息
			url = "https://eduzone.codemao.cn/edu/zone/classes/"
			timestamp = self.tool.TimeUtils().current_timestamp(13)
			# 设置请求参数
			params = {"page": 1, "TIME": timestamp}

			# 发送GET请求获取详细班级信息
			classes = self.acquire.fetch_data(
				endpoint=url,
				params=params,
				pagination_method="page",
				config={"offset_key": "page", "response_amount_key": "limit"},
				limit=limit,
			)
		else:
			return None
		return classes

	# 获取删除学生记录
	def get_record_del(self, limit: int | None = 20) -> Generator[dict]:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"page": 1, "limit": 10, "TIME": timestamp}
		return self.acquire.fetch_data(
			endpoint="https://eduzone.codemao.cn/edu/zone/student/remove/record",
			params=params,
			pagination_method="page",
			config={"amount_key": "limit", "offset_key": "page"},
			limit=limit,
		)

	# 获取班级内全部学生
	def get_students(self, invalid: int = 1, limit: int | None = 100) -> Generator[dict]:
		# invalid为1时为已加入班级学生,为0则反之
		data = {"invalid": invalid}
		params = {"page": 1, "limit": 100}
		return self.acquire.fetch_data(
			endpoint="https://eduzone.codemao.cn/edu/zone/students",
			params=params,
			payload=data,
			fetch_method="POST",
			pagination_method="page",
			config={"amount_key": "limit", "offset_key": "page"},
			limit=limit,
		)

	# 获取新闻
	def get_menus(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/api/home/eduzone/menus",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取banner
	def get_banner(self, type_id: Literal[101, 106] = 101) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp, "type_id": type_id}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/api/home/banners",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取服务器时间
	# params可以不添加
	def get_sever_time(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/base/server/time",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取各部分开启状态
	def get_package_status(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/lessons/person/package/remind/status",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取conf
	def get_conf(self, tag: Literal["teacher_guided_wechat_link"]) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp, "tag": tag}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/base/general/conf",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取账户多余info
	def get_extend_info(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/user-extend/info",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取小黑板记录
	def get_board_record(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/operation/records",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取授课状态
	def get_teaching_status(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/teaching/class/remind",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取信息栏信息
	def get_homepage_info(self) -> dict:
		# "total_works": 作品数
		# "behavior_score": 课堂表现分
		# "average_score": 作品平均分
		# "high_score": 作品最高分
		# -------------
		# "total_classes": 班级数
		# "activated_students": 激活学生数
		# "total_periods": 上课数
		# "total_works": 作品数
		# "average_score": 作品平均分
		# "high_score": 作品最高分

		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/homepage/statistic",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取所有工具
	def get_homepage_menus(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/homepage/menus",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取云端存储的所有平台的作品
	# mark_status中1为已评分,2为未评分
	# updated_at_from&updated_at_to按字面意思,传参时为timestamp
	# max_score&min_score按字面意思,传参时值为0-100,且都为整十数
	# teachingRecordId为上课记录id
	# status为发布状态,100为已发布,1为未发布
	# name用于区分作品名
	# type为作品类型,源码编辑器为1,海龟编辑器2.0(c++)为16,代码岛2.0为5,海龟编辑器为7,nemo为8
	# version用于区分源码编辑器4.0和源码编辑器,在请求中,源码编辑器4.0的version为4,源码编辑器不填
	# 返回数据中的praise_times为点赞量
	# 返回数据中的language_type貌似用来区分海龟编辑器2.0(c++)与海龟编辑器,海龟编辑器的language_type为3
	def get_all_works(self, limit: int | None = 50) -> Generator[dict]:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"page": 1, "TIME": timestamp}
		return self.acquire.fetch_data(
			endpoint="https://eduzone.codemao.cn/edu/zone/work/manager/student/works",
			params=params,
			pagination_method="page",
			config={"offset_key": "page", "response_amount_key": "limit"},
			limit=limit,
		)

	# 获取老师管理的作品
	# class_id为班级id,mark_status为评分状态,max_score&min_score为分数范围,name为作品名
	# status为发布状态,updated_at_from&updated_at_to为时间戳范围,username为学生id
	# type为作品类型,teachingRecordId为上课记录id
	def get_teacher_works(self, limit: int | None = 50) -> Generator[dict]:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"page": 1, "TIME": timestamp}
		return self.acquire.fetch_data(
			endpoint="https://eduzone.codemao.cn/edu/zone/work/manager/works",
			params=params,
			pagination_method="page",
			config={"offset_key": "page", "response_amount_key": "limit"},
			limit=limit,
		)

	# 获取我的作品
	# mark_status为评分状态,max_score&min_score为分数范围,name为作品名
	# status为发布状态,updated_at_from&updated_at_to为时间戳范围
	def get_my_works(self, limit: int | None = 50) -> Generator[dict]:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"page": 1, "TIME": timestamp}
		return self.acquire.fetch_data(
			endpoint="https://eduzone.codemao.cn/edu/zone/work/manager/self/works",
			params=params,
			pagination_method="page",
			config={"offset_key": "page", "response_amount_key": "limit"},
			limit=limit,
		)

	# 获取周作品统计数据
	# year传参示例:2024,class_id为None时返回全部班级的数据
	def get_work_statistics(self, class_id: int | None, year: int, month: int) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		formatted_month = f"{month:02d}"
		params = {"TIME": timestamp, "year": year, "month": formatted_month, "class_id": class_id}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/work/manager/works/statistics",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取上课记录
	def get_teaching_record(self, limit: int | None = 10) -> Generator[dict]:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"page": 1, "TIME": timestamp, "limit": 10}
		return self.acquire.fetch_data(
			endpoint="https://eduzone.codemao.cn/edu/zone/teaching/record/list",
			params=params,
			pagination_method="page",
			config={"amount_key": "limit", "offset_key": "page"},
			limit=limit,
		)

	# 获取教授班级(需要教师号)
	def get_teaching_classes(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/teaching/class/teacher/list",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取info(需要教师账号)
	def get_data_info(self, unit_id: int) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp, "unitId": unit_id}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/school/info",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取官方课程包
	def get_official_package(self, limit: int | None = 150) -> Generator[dict]:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp, "pacakgeEntryType": 0, "topicType": "all", "topicId": "all", "tagId": "all", "page": 1, "limit": 150}
		return self.acquire.fetch_data(
			endpoint="https://eduzone.codemao.cn/edu/zone/lesson/offical/packages",
			params=params,
			pagination_method="page",
			config={"amount_key": "limit", "offset_key": "page"},
			limit=limit,
		)

	# 获取官方课程包主题
	def get_official_package_topic(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp, "pacakgeEntryType": 0, "topicType": "all"}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/lessons/official/packages/topics",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取官方课程包tag
	def get_official_package_tags(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp, "pacakgeEntryType": 0, "topicType": "all"}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/lessons/official/packages/topics/all/tags",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取我的备课包(需要教师号)
	def get_customized_package(self, limit: int | None = 100) -> Generator[dict]:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp, "page": 1, "limit": 100}
		return self.acquire.fetch_data(
			endpoint="https://eduzone.codemao.cn/edu/zone/lesson/offical/packages",
			params=params,
			pagination_method="page",
			config={"amount_key": "limit", "offset_key": "page"},
			limit=limit,
		)

	# 获取自定义备课包信息/删除备课包
	def get_customized_package_info(self, package_id: int, method: Literal["GET", "DELETE"]) -> dict | bool:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint=f"https://eduzone.codemao.cn/edu/zone/lesson/customized/packages/{package_id}",
			method=method,
			params=params,
		)
		return response.json() if method == "GET" else response.status_code == HTTPSTATUS.OK.value

	# 获取自定义备课包内容
	def get_customized_package_lesson(self, package_id: int, limit: int) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp, "limit": limit, "package_id": package_id}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/lesson/customized/package/lessons",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取加入班级的邀请列表
	def get_invite_message(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/invite/student/message/next",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取即将过期的课程包(教师)
	def get_expired_lesson(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/lesson/offical/packages/expired",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取组织id
	def get_organization_ids(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"CMTIME": timestamp}
		response = self.acquire.send_request(endpoint="https://static.codemao.cn/teacher-edu/organization_ids.json", method="GET", params=params)
		return response.json()

	# 获取报告信息
	def get_report_info(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/analysis/report/info",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取课程报告
	def get_course_report(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/analysis/student/course",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取课程包报告
	def get_package_report(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/analysis/student/packages",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取班级报告
	def get_class_report(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/analysis/student/class/info",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取作品报告
	def get_works_report(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/analysis/student/works/situations",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取作品星级报告
	def get_works_star_report(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/analysis/student/works/star/info",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取能力报告
	def get_ability_report(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/analysis/student/ability/dimensions",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取雷达图报告
	def get_radar_chart_report(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/analysis/student/ability/radars",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取艺术报告
	def get_artistic_report(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/analysis/student/ability/artistic/dimensions",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取逻辑报告
	def get_logical_report(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/analysis/student/ability/logical/dimensions",
			method="GET",
			params=params,
		)
		return response.json()

	# 获取编程报告
	def get_programming_report(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/analysis/student/ability/programming/dimensions",
			method="GET",
			params=params,
		)
		return response.json()
