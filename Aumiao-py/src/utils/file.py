import json
from pathlib import Path
from typing import Literal

from .decorator import singleton


@singleton
class CodeMaoFile:
	# 检查文件
	@staticmethod
	def check_file(path: Path) -> bool:
		# 尝试打开文件
		try:
			with Path.open(path):
				return True
		# 如果打开文件失败,打印错误信息并返回False
		except OSError as err:
			print(err)
			return False

	@staticmethod
	def validate_json(json_string: str | bytes) -> str | Literal[False]:
		# 尝试解析JSON字符串
		try:
			return json.loads(json_string)
		# 如果解析失败,打印错误信息并返回False
		except ValueError as err:
			print(err)
			return False

	# 从配置文件加载账户信息
	def file_load(self, path: Path, _type: Literal["txt", "json"]) -> dict | str:
		# 检查文件是否存在
		self.check_file(path=path)
		# 打开文件并读取内容
		with Path.open(self=path, encoding="utf-8") as file:
			data: str = file.read()
			# 根据文件类型解析内容
			if _type == "json":
				return json.loads(data) if data else {}
			if _type == "txt":
				return data
			# 如果文件类型不支持,抛出异常
			msg = "不支持的读取方法"
			raise ValueError(msg)

	# 将文本写入到指定文件
	@staticmethod
	def file_write(
		path: Path,
		content: str | bytes | dict | list[str],
		method: str = "w",
	) -> None:
		# 检查文件是否存在
		# self.check_file(path=path)
		# 打开文件并写入内容
		with Path.open(self=path, mode=method) as file:
			if isinstance(content, str):
				file.write(content + "\n")
			elif isinstance(content, bytes):
				file.write(content)
			elif isinstance(content, dict):
				file.write(json.dumps(obj=content, ensure_ascii=False, indent=4, sort_keys=True))
			elif isinstance(content, list):
				for line in content:
					file.write(line + "\n")
			# 如果内容类型不支持,抛出异常
			else:
				msg = "不支持的写入方法"
				raise TypeError(msg)
