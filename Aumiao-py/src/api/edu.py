from collections.abc import Generator
from typing import Literal

from requests import Response

from src.utils import acquire, tool
from src.utils.acquire import HTTPSTATUS
from src.utils.decorator import singleton


# sb编程猫,params中的{"_": timestamp}可以替换为{"TIME": timestamp}
@singleton
class UserAction:
	def __init__(self) -> None:
		self.acquire = acquire.CodeMaoClient()
		self.tool = tool

	def change_real_name(self, user_id: int, real_name: str) -> bool:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp, "userId": user_id, "realName": real_name}

		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/account/updateName",
			method="GET",
			params=params,
		)
		return response.status_code == HTTPSTATUS.OK.value

	def create_class(self, name: str) -> dict:
		data = {"name": name}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/class",
			method="POST",
			payload=data,
		)
		return response.json()

	def delete_class(self, class_id: int) -> bool:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}

		response = self.acquire.send_request(
			endpoint=f"https://eduzone.codemao.cn/edu/zone/class/{class_id}",
			method="DELETE",
			params=params,
		)
		return response.status_code == HTTPSTATUS.NO_CONTENT.value

	def add_students(self, name: list[str], class_id: int) -> bool:
		data = {"student_names": name}
		response = self.acquire.send_request(
			endpoint=f"https://eduzone.codemao.cn/edu/zone/class/{class_id}/students",
			method="POST",
			payload=data,
		)
		return response.status_code == HTTPSTATUS.OK.value

	def reset_student_password(self, stu_id: int) -> dict:
		response = self.acquire.send_request(
			endpoint=f"https://eduzone.codemao.cn/edu/zone/students/{stu_id}/password",
			method="PATCH",
			payload={},
		)
		return response.json()

	def bulk_reset_passwords(self, stu_list: list[int]) -> Response:
		return self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/students/password",
			method="PATCH",
			payload={"student_id": stu_list},
		)

	def remove_student_from_class(self, stu_id: int) -> bool:
		response = self.acquire.send_request(
			endpoint=f"https://eduzone.codemao.cn/edu/zone/student/remove/{stu_id}",
			method="POST",
			payload={},
		)
		return response.status_code == HTTPSTATUS.OK.value

	def manage_lesson_package(
		self,
		method: Literal["POST", "PATCH"],
		avatar_url: str,
		description: str,
		name: str,
		*,
		return_data: bool = True,
	) -> dict | bool:
		data = {"avatar_url": avatar_url, "description": description, "name": name}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/lesson/customized/packages",
			method=method,
			payload=data,
		)
		return response.json() if return_data else response.status_code == HTTPSTATUS.OK.value

	def remove_work(self, work_id: int) -> bool:
		response = self.acquire.send_request(
			endpoint=f"https://eduzone.codemao.cn/edu/zone/work/{work_id}/delete",
			method="POST",
			payload={},
		)
		return response.status_code == HTTPSTATUS.OK.value

	def transfer_to_unassigned(self, class_id: int, stu_id: int) -> bool:
		params = {"student_ids[]": stu_id}
		response = self.acquire.send_request(
			endpoint=f"https://eduzone.codemao.cn/edu/zone/class/{class_id}/students",
			method="DELETE",
			params=params,
		)
		return response.status_code == HTTPSTATUS.NO_CONTENT.value

	def fetch_activity_package_details(self, package_id: int) -> dict:
		payload = {"packageId": package_id}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/activity/open/package",
			method="POST",
			payload=payload,
		)
		return response.json()

	def fetch_activity_packages(self) -> dict:
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/activity/list/activity/package",
			method="POST",
			payload={},
		)
		return response.json()

	def mark_all_messages_as_read(self) -> bool:
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/invite/message/all/read",
			method="POST",
			payload={},
		)
		return response.status_code == HTTPSTATUS.OK.value

	def grade_student_work(
		self,
		work_id: int,
		work_name: str,
		artistic_score: int,
		creative_sore: int,
		commentary: str,
		logical_score: int,
		programming_score: int,
	) -> bool:
		data = {
			"artistic_score": artistic_score,
			"commentary": commentary,
			"creative_score": creative_sore,
			"id": work_id,
			"logical_score": logical_score,
			"programming_score": programming_score,
			"work_name": work_name,
		}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/work/manager/works/scores",
			method="PATCH",
			payload=data,
		)
		return response.status_code == HTTPSTATUS.NO_CONTENT.value

	def invite_to_class(
		self,
		class_id: int,
		types: Literal["0", "1"],
		identity: list[str | int],
	) -> bool:
		data = {"identity": identity, "type": types, "classId": class_id}
		response = self.acquire.send_request(
			endpoint=f"https://eduzone.codemao.cn/edu/zone/class/{class_id}/students/invite",
			method="POST",
			payload=data,
		)
		return response.status_code == HTTPSTATUS.OK.value

	def accept_class_invite(self, message_id: int) -> bool:
		response = self.acquire.send_request(
			endpoint=f"https://eduzone.codemao.cn/edu/zone/invite/student/message/{message_id}/accept",
			method="POST",
			payload={},
		)
		return response.status_code == HTTPSTATUS.OK.value

	def upgrade_to_teacher(
		self,
		user_id: int,
		real_name: str,
		grade: list[str],
		school_id: int,
		school_name: str,
		school_type: int,
		country_id: str,
		province_id: int,
		city_id: int,
		district_id: int,
		teacher_card_number: str,
	) -> bool:
		data = {
			"id": user_id,
			"real_name": real_name,
			"grade": grade,
			"schoolId": school_id,
			"schoolName": school_name,
			"schoolType": school_type,
			"country_id": country_id,
			"province_id": province_id,
			"city_id": city_id,
			"district_id": district_id,
			"teacherCardNumber": teacher_card_number,
		}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/sign/login/teacher/info/improve",
			method="POST",
			payload=data,
		)
		return response.status_code == HTTPSTATUS.OK.value


@singleton
class DataFetcher:
	def __init__(self) -> None:
		self.acquire = acquire.CodeMaoClient()
		self.tool = tool

	def fetch_user_profile(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_account_role(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/api/home/account",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_unread_message_count(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/system/message/unread/num",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_notices_generator(self, limit: int | None = 10) -> Generator[dict]:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"page": 1, "limit": 10, "TIME": timestamp}
		return self.acquire.fetch_data(
			endpoint="https://eduzone.codemao.cn/edu/zone/system/message/list",
			params=params,
			pagination_method="page",
			config={"amount_key": "limit", "offset_key": "page"},
			limit=limit,
		)

	def fetch_reminders_generator(self, limit: int | None = 10) -> Generator[dict]:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"page": 1, "limit": 10, "TIME": timestamp}
		return self.acquire.fetch_data(
			endpoint="https://eduzone.codemao.cn/edu/zone/invite/teacher/messages",
			params=params,
			pagination_method="page",
			config={"amount_key": "limit", "offset_key": "page"},
			limit=limit,
		)

	def fetch_school_categories(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/school/open/grade/list",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_classrooms(self, method: Literal["detail", "simple"] = "simple", limit: int | None = 20) -> dict | Generator:
		if method == "simple":
			response = self.acquire.send_request(
				endpoint="https://eduzone.codemao.cn/edu/zone/classes/simple",
				method="GET",
			)
			return response.json()
		if method == "detail":
			timestamp = self.tool.TimeUtils().current_timestamp(13)
			params = {"page": 1, "TIME": timestamp}
			return self.acquire.fetch_data(
				endpoint="https://eduzone.codemao.cn/edu/zone/classes/",
				params=params,
				pagination_method="page",
				config={"offset_key": "page", "response_amount_key": "limit"},
				limit=limit,
			)
		return None

	def fetch_student_removal_records_generator(self, limit: int | None = 20) -> Generator[dict]:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"page": 1, "limit": 10, "TIME": timestamp}
		return self.acquire.fetch_data(
			endpoint="https://eduzone.codemao.cn/edu/zone/student/remove/record",
			params=params,
			pagination_method="page",
			config={"amount_key": "limit", "offset_key": "page"},
			limit=limit,
		)

	def fetch_class_students_generator(self, invalid: int = 1, limit: int | None = 100) -> Generator[dict]:
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

	def fetch_navigation_menus(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/api/home/eduzone/menus",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_banners(self, type_id: Literal[101, 106] = 101) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp, "type_id": type_id}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/api/home/banners",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_server_time(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/base/server/time",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_lesson_package_status(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/lessons/person/package/remind/status",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_configuration(self, tag: Literal["teacher_guided_wechat_link"]) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp, "tag": tag}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/base/general/conf",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_extended_profile(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/user-extend/info",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_operation_logs(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/operation/records",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_teaching_status(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/teaching/class/remind",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_dashboard_stats(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/homepage/statistic",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_tool_menu(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/homepage/menus",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_all_works_generator(self, limit: int | None = 50) -> Generator[dict]:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"page": 1, "TIME": timestamp}
		return self.acquire.fetch_data(
			endpoint="https://eduzone.codemao.cn/edu/zone/work/manager/student/works",
			params=params,
			pagination_method="page",
			config={"offset_key": "page", "response_amount_key": "limit"},
			limit=limit,
		)

	def fetch_managed_works_generator(self, limit: int | None = 50) -> Generator[dict]:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"page": 1, "TIME": timestamp}
		return self.acquire.fetch_data(
			endpoint="https://eduzone.codemao.cn/edu/zone/work/manager/works",
			params=params,
			pagination_method="page",
			config={"offset_key": "page", "response_amount_key": "limit"},
			limit=limit,
		)

	def fetch_personal_works_generator(self, limit: int | None = 50) -> Generator[dict]:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"page": 1, "TIME": timestamp}
		return self.acquire.fetch_data(
			endpoint="https://eduzone.codemao.cn/edu/zone/work/manager/self/works",
			params=params,
			pagination_method="page",
			config={"offset_key": "page", "response_amount_key": "limit"},
			limit=limit,
		)

	def fetch_work_analytics(self, class_id: int | None, year: int, month: int) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		formatted_month = f"{month:02d}"
		params = {
			"TIME": timestamp,
			"year": year,
			"month": formatted_month,
			"class_id": class_id,
		}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/work/manager/works/statistics",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_teaching_records_generator(self, limit: int | None = 10) -> Generator[dict]:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"page": 1, "TIME": timestamp, "limit": 10}
		return self.acquire.fetch_data(
			endpoint="https://eduzone.codemao.cn/edu/zone/teaching/record/list",
			params=params,
			pagination_method="page",
			config={"amount_key": "limit", "offset_key": "page"},
			limit=limit,
		)

	def fetch_teaching_classes(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/teaching/class/teacher/list",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_school_info(self, unit_id: int) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp, "unitId": unit_id}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/school/info",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_official_lesson_packages_generator(self, limit: int | None = 150) -> Generator[dict]:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {
			"TIME": timestamp,
			"pacakgeEntryType": 0,
			"topicType": "all",
			"topicId": "all",
			"tagId": "all",
			"page": 1,
			"limit": 150,
		}
		return self.acquire.fetch_data(
			endpoint="https://eduzone.codemao.cn/edu/zone/lesson/offical/packages",
			params=params,
			pagination_method="page",
			config={"amount_key": "limit", "offset_key": "page"},
			limit=limit,
		)

	def fetch_lesson_topics(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp, "pacakgeEntryType": 0, "topicType": "all"}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/lessons/official/packages/topics",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_lesson_tags(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp, "pacakgeEntryType": 0, "topicType": "all"}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/lessons/official/packages/topics/all/tags",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_custom_lesson_packages_generator(self, limit: int | None = 100) -> Generator[dict]:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp, "page": 1, "limit": 100}
		return self.acquire.fetch_data(
			endpoint="https://eduzone.codemao.cn/edu/zone/lesson/offical/packages",
			params=params,
			pagination_method="page",
			config={"amount_key": "limit", "offset_key": "page"},
			limit=limit,
		)

	def manage_custom_package(self, package_id: int, method: Literal["GET", "DELETE"]) -> dict | bool:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint=f"https://eduzone.codemao.cn/edu/zone/lesson/customized/packages/{package_id}",
			method=method,
			params=params,
		)
		return response.json() if method == "GET" else response.status_code == HTTPSTATUS.OK.value

	def fetch_custom_package_contents(self, package_id: int, limit: int) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp, "limit": limit, "package_id": package_id}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/lesson/customized/package/lessons",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_class_invites(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/invite/student/message/next",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_expiring_lessons(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/lesson/offical/packages/expired",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_organization_ids(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"CMTIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://static.codemao.cn/teacher-edu/organization_ids.json",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_report_metadata(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/analysis/report/info",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_course_analytics(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/analysis/student/course",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_lesson_package_analytics(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/analysis/student/packages",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_classroom_analytics(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/analysis/student/class/info",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_work_performance(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/analysis/student/works/situations",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_work_ratings(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/analysis/student/works/star/info",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_skill_assessment(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/analysis/student/ability/dimensions",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_skill_radar(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/analysis/student/ability/radars",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_art_skills(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/analysis/student/ability/artistic/dimensions",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_logic_skills(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/analysis/student/ability/logical/dimensions",
			method="GET",
			params=params,
		)
		return response.json()

	def fetch_coding_skills(self) -> dict:
		timestamp = self.tool.TimeUtils().current_timestamp(13)
		params = {"TIME": timestamp}
		response = self.acquire.send_request(
			endpoint="https://eduzone.codemao.cn/edu/zone/analysis/student/ability/programming/dimensions",
			method="GET",
			params=params,
		)
		return response.json()
