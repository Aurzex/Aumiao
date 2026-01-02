from src.utils import acquire
from src.utils.acquire import HTTPStatus
from src.utils.decorator import singleton


@singleton
class CookieManager:
	# 初始化函数, 创建一个 CodeMaoClient 对象
	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()

	# 应用 Cookie
	def apply_cookie(self, cookies: str) -> bool:
		"""
		将提供的 Cookie 应用到系统中
		Args:
			cookies: 需要应用的 Cookie 字符串
		Returns:
			如果 Cookie 应用成功返回 True, 否则返回 False
		"""
		payload = {"cookie": cookies, "do": "apply"}
		response = self._client.send_request(endpoint="https://shequ.pgaot.com/?mod=bcmcookieout", method="POST", payload=payload)
		return response.status_code == HTTPStatus.OK.value
