from src.utils import acquire
from src.utils.acquire import HTTPSTATUS
from src.utils.decorator import singleton


@singleton
class CookieManager:
	# 初始化函数,创建一个CodeMaoClient对象
	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()

	# 应用Cookie
	def apply_cookie(self, cookies: str) -> bool:
		"""
		将提供的Cookie应用到系统中
		Args:
			cookies: 需要应用的Cookie字符串
		Returns:
			如果Cookie应用成功返回True,否则返回False
		"""
		payload = {"cookie": cookies, "do": "apply"}
		response = self._client.send_request(endpoint="https://shequ.pgaot.com/?mod=bcmcookieout", method="POST", payload=payload)
		return response.status_code == HTTPSTATUS.OK.value
