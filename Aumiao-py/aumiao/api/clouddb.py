from typing import Any

from aumiao.utils import acquire
from aumiao.utils.decorator import singleton


@singleton
class Ranking:
	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()

	def update_ranking_list(self, data: dict) -> dict:
		"""
		更新排行榜 (全量更新)
		Args:
			data: 排行榜数据
		Returns:
			更新结果
		"""
		response = self._client.send_request(
			endpoint="/neko/ranking-list/fullUpdate",
			method="PUT",
			payload=data,
			base_url_key="creation",
		)
		return response.json()

	def clear_ranking_list(self, ranking_id: str) -> dict:
		"""
		清空排行榜
		Args:
			ranking_id: 排行榜 ID
		Returns:
			清空结果
		"""
		params = {"id": ranking_id}
		response = self._client.send_request(
			endpoint="/neko/ranking-list/clear",
			method="PUT",
			params=params,
			base_url_key="creation",
		)
		return response.json()

	def fetch_ranking_records(self, ranking_id: str, work_id: int) -> dict:
		"""
		获取排行榜记录
		Args:
			ranking_id: 排行榜 ID
			work_id: 作品 ID
		Returns:
			排行榜记录列表
		"""
		params = {"id": ranking_id, "work_id": work_id}
		response = self._client.send_request(
			endpoint="/neko/ranking-list/record/list",
			method="GET",
			params=params,
			base_url_key="creation",
		)
		return response.json()

	def add_ranking_record(self, work_id: int, value: str, ranking_id: int) -> dict:
		"""
		添加排行榜记录
		Args:
			data: 记录数据
		Returns:
			添加结果
		"""
		data = {"work_id": work_id, "value": value, "id": ranking_id}
		response = self._client.send_request(
			endpoint="/neko/ranking-list/record",
			method="POST",
			payload=data,
			base_url_key="creation",
		)
		return response.json()

	def create_ranking_list(self, data: dict) -> dict:
		"""
		创建排行榜
		Args:
			data: 排行榜数据
		Returns:
			创建结果
		"""
		response = self._client.send_request(
			endpoint="/neko/ranking-list",
			method="POST",
			payload=data,
			base_url_key="creation",
		)
		return response.json()

	def delete_ranking_list(self, ranking_id: str, work_id: int) -> dict:
		"""
		删除排行榜
		Args:
			ranking_id: 排行榜 ID
			work_id: 作品 ID
		Returns:
			删除结果
		"""
		params = {"id": ranking_id, "work_id": work_id}
		response = self._client.send_request(
			endpoint=f"/neko/ranking-list/{ranking_id}",
			method="DELETE",
			params=params,
			base_url_key="creation",
		)
		return response.json()


@singleton
class CoconutCloud:
	def __init__(self) -> None:
		self._client = acquire.CodeMaoClient()

	def set_dictionary_value(self, dict_id: str, key: str, value: Any) -> dict:
		"""
		设置云字典键值
		Args:
			dict_id: 字典 ID
			key: 键名
			value: 值
		Returns:
			操作结果
		"""
		data = {"key": key, "type": type(value).__name__, "value": value}
		response = self._client.send_request(
			endpoint=f"/coconut/webdb/try/dict/{dict_id}/set",
			method="POST",
			payload=data,
			base_url_key="creation",
		)
		return response.json()

	def delete_dictionary_key(self, dict_id: str, key: str) -> dict:
		"""
		删除云字典键
		Args:
			dict_id: 字典 ID
			key: 键名
		Returns:
			操作结果
		"""
		params = {"key": key}
		response = self._client.send_request(
			endpoint=f"/coconut/webdb/try/dict/{dict_id}/remove",
			method="DELETE",
			params=params,
			base_url_key="creation",
		)
		return response.json()

	def clear_dictionary(self, dict_id: str) -> dict:
		"""
		清空云字典
		Args:
			dict_id: 字典 ID
		Returns:
			操作结果
		"""
		response = self._client.send_request(
			endpoint=f"/coconut/webdb/try/dict/clear/{dict_id}",
			method="DELETE",
			base_url_key="creation",
		)
		return response.json()

	def get_dictionary_keys(self, dict_id: str) -> list:
		"""
		获取云字典所有键
		Args:
			dict_id: 字典 ID
		Returns:
			键名列表
		"""
		response = self._client.send_request(
			endpoint=f"/coconut/webdb/try/dict/{dict_id}/keys",
			method="GET",
			base_url_key="creation",
		)
		return response.json()

	def get_dictionary_value(self, dict_id: str, key: str) -> Any:
		"""
		获取云字典值
		Args:
			dict_id: 字典 ID
			key: 键名
		Returns:
			键值
		"""
		params = {"key": key}
		response = self._client.send_request(
			endpoint=f"/coconut/webdb/try/dict/{dict_id}/getvalue",
			method="GET",
			params=params,
			base_url_key="creation",
		)
		return response.json()

	def query_table(self, table_id: str, queries: list) -> dict:
		"""
		查询云数据表
		Args:
			table_id: 表 ID
			queries: 查询条件列表
		Returns:
			查询结果
		"""
		data = {"querys": {"querys": queries}}  # spellchecker:disable-line
		response = self._client.send_request(
			endpoint=f"/coconut/clouddb/runtime/{table_id}/select",
			method="POST",
			payload=data,
			base_url_key="creation",
		)
		return response.json()

	def update_table_rows(self, table_id: str, queries: list, values: list) -> dict:
		"""
		更新云数据表
		Args:
			table_id: 表 ID
			queries: 查询条件列表
			values: 更新值列表
		Returns:
			更新结果
		"""
		data = {"querys": {"querys": queries}, "values": values}  # spellchecker:disable-line
		response = self._client.send_request(
			endpoint=f"/coconut/clouddb/runtime/{table_id}/update",
			method="PUT",
			payload=data,
			base_url_key="creation",
		)
		return response.json()

	def insert_table_rows(self, table_id: str, values: list) -> dict:
		"""
		插入云数据表行
		Args:
			table_id: 表 ID
			values: 值列表
		Returns:
			插入结果
		"""
		data = {"values": values}
		response = self._client.send_request(
			endpoint=f"/coconut/clouddb/runtime/{table_id}/insert",
			method="POST",
			payload=data,
			base_url_key="creation",
		)
		return response.json()

	def delete_table_rows(self, table_id: str, queries: list) -> dict:
		"""
		删除云数据表行
		Args:
			table_id: 表 ID
			queries: 查询条件列表
		Returns:
			删除结果
		"""
		data = {"querys": {"querys": queries}}  # spellchecker:disable-line
		response = self._client.send_request(
			endpoint=f"/coconut/clouddb/runtime/{table_id}/delete",
			method="PUT",
			payload=data,
			base_url_key="creation",
		)
		return response.json()

	def clear_table(self, table_id: str) -> dict:
		"""
		清空云数据表
		Args:
			table_id: 表 ID
		Returns:
			清空结果
		"""
		response = self._client.send_request(
			endpoint=f"/coconut/clouddb/v2/runtime/{table_id}/clear",
			method="PUT",
			base_url_key="creation",
		)
		return response.json()

	def get_table_row_count(self, table_id: str) -> dict:
		"""
		获取云数据表行数
		Args:
			table_id: 表 ID
		Returns:
			行数信息
		"""
		params = {"type": "RECORD"}
		response = self._client.send_request(
			endpoint=f"/coconut/clouddb/runtime/{table_id}/count",
			method="GET",
			params=params,
			base_url_key="creation",
		)
		return response.json()

	def get_table_info(self, table_ids: list) -> list:
		"""
		获取云数据表信息
		Args:
			table_ids: 表 ID 列表
		Returns:
			表信息列表
		"""
		ids_str = ",".join(table_ids)
		params = {"db_ids": ids_str}
		response = self._client.send_request(
			endpoint="/coconut/clouddb/v2/runtime/list",
			method="GET",
			params=params,
			base_url_key="creation",
		)
		return response.json()

	def load_work_data(self, work_id: int, channel: str) -> dict:
		"""
		加载作品数据
		Args:
			work_id: 作品 ID
			channel: 通道 ("0": H5, "1": 社区)
		Returns:
			作品数据
		"""
		params = {"channel": channel}
		response = self._client.send_request(
			endpoint=f"/coconut/web/work/{work_id}/load",
			method="GET",
			params=params,
			base_url_key="creation",
		)
		return response.json()
