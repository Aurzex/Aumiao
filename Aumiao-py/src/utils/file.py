import json
from pathlib import Path
from typing import Literal

from src.utils.decorator import singleton


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

	@staticmethod
	def file_write(
		path: Path,
		content: str | bytes | dict | list[str],
		method: str = "w",
		encoding: str = "utf-8",
	) -> None:
		# 确保父目录存在
		path.parent.mkdir(parents=True, exist_ok=True)
		# 根据内容类型自动决定模式和编码
		mode = method
		kwargs = {}
		if isinstance(content, (str, dict, list)):
			# 文本模式需指定编码
			kwargs["encoding"] = encoding
			if "b" in mode:
				# 禁止文本内容使用二进制模式
				msg = f"文本内容不能使用二进制模式: {mode}"
				raise ValueError(msg)
		elif isinstance(content, bytes):
			# 字节内容强制使用二进制模式
			if "b" not in mode:
				mode += "b"
		else:
			msg = "不支持的内容类型"
			raise TypeError(msg)
		# 打开文件并写入
		with Path.open(path, mode, **kwargs) as f:
			if isinstance(content, (str, bytes)):
				f.write(content)
			elif isinstance(content, dict):
				json_str = json.dumps(content, ensure_ascii=False, indent=4)
				f.write(json_str)
			elif isinstance(content, list):
				f.writelines(line + "\n" for line in content)

	@staticmethod
	def read_line(path: Path) -> list[str]:
		lines = []
		with Path.open(self=path, encoding="utf-8") as f:
			lines.extend(line.strip() for line in f)
		return lines
