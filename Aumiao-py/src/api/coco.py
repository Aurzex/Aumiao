from collections.abc import Generator

from src.utils import acquire
from src.utils.decorator import singleton


@singleton
class CoconutDataFetcher:
	def __init__(self) -> None:
		self.acquire = acquire.CodeMaoClient()

	# 获取coco课程
	def fetch_coco_courses(self) -> dict:
		"""获取Coco平台的主要课程列表"""
		response = self.acquire.send_request(
			endpoint="https://api-creation.codemao.cn/coconut/primary-course/list",
			method="GET",
		)
		return response.json()

	# 获取自定义控件列表
	def fetch_widgets(self, limit: int | None = 100) -> Generator[dict]:
		"""获取Coconut平台的自定义控件列表

		Args:
			limit: 限制返回的控件数量,None表示获取全部

		Returns:
			生成器,每次生成一个控件信息字典
		"""
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

	# 获取示范教程
	def fetch_sample_courses(self) -> dict:
		"""获取Coconut平台的示范教程列表"""
		response = self.acquire.send_request(endpoint="https://api-creation.codemao.cn/coconut/sample/list", method="GET")
		return response.json()

	# 获取白名单作品链接
	def fetch_whitelisted_works(self) -> dict:
		"""获取Coconut平台的白名单作品链接"""
		response = self.acquire.send_request(endpoint="https://static.codemao.cn/coco/whitelist.json", method="GET")
		return response.json()
