from collections.abc import Generator

from src.utils import acquire
from src.utils.decorator import singleton


@singleton
class Obtain:
	def __init__(self) -> None:
		# 初始化CodeMaoClient对象
		self.acquire = acquire.CodeMaoClient()

	# 获取coco课程
	def get_coco_course(self) -> dict:
		response = self.acquire.send_request(
			endpoint="https://api-creation.codemao.cn/coconut/primary-course/list",
			method="GET",
		)
		return response.json()

	# 获取自定义控件?
	def get_wight(self, limit: int | None = 100) -> Generator:
		params = {"current_page": 1, "page_size": 100}
		return self.acquire.fetch_data(
			endpoint="https://api-creation.codemao.cn/coconut/web/widget/list",
			params=params,
			total_key="data.total",
			data_key="data.items",
			pagination_method="page",
			limit=limit,
			config={"amount_key": "page_size", "offset_key": "current_page"},
		)

	# 获取示范教程?
	def get_course(self) -> dict:
		response = self.acquire.send_request(endpoint="https://api-creation.codemao.cn/coconut/sample/list", method="GET")
		return response.json()

	# 获取白名单作品链接?
	def get_white_list(self) -> dict:
		response = self.acquire.send_request(endpoint="https://static.codemao.cn/coco/whitelist.json", method="GET")
		return response.json()
