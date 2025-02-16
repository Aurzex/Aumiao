from src.utils import acquire
from src.utils.acquire import HTTPSTATUS
from src.utils.decorator import singleton


@singleton
class PickDuck:
	# 初始化函数,创建一个CodeMaoClient对象
	def __init__(self) -> None:
		self.acquire = acquire.CodeMaoClient()

	# 发送请求,获取cookie
	def cookie_out(self, cookies: str) -> bool:
		# 构造请求数据
		data = {"cookie": cookies, "do": "apply"}

		response = self.acquire.send_request(endpoint="https://shequ.pgaot.com/?mod=bcmcookieout", method="POST", payload=data)
		# 判断请求是否成功
		return response.status_code == HTTPSTATUS.OK
