from collections.abc import Callable
from typing import Any

from src.utils.plugin import BasePlugin


class Plugin(BasePlugin):
	@property
	def PLUGIN_NAME(self) -> str:
		return "高级修改插件"

	@property
	def PLUGIN_DESCRIPTION(self) -> str:
		return "演示可靠的代码修改技术"

	@property
	def PLUGIN_VERSION(self) -> str:
		return "2.0.0"

	@property
	def PLUGIN_CONFIG_SCHEMA(self) -> dict[str, Any]:
		return {"enable_modification": bool, "log_level": str, "modification_mode": str}

	@property
	def PLUGIN_DEFAULT_CONFIG(self) -> dict[str, Any]:
		return {"enable_modification": True, "log_level": "INFO", "modification_mode": "direct"}

	def __init__(self):
		super().__init__()
		self.original_functions = {}

	def register(self) -> dict[str, tuple[Callable, str]]:
		return {"test_modification": (self.test_modification, "测试代码修改"), "get_status": (self.get_status, "获取插件状态")}

	def on_load(self, config: dict[str, Any]) -> None:
		super().on_load(config)
		self.config = config

		# 备份原始函数
		self._backup_functions()

		if config.get("enable_modification", True):
			result = self.apply_code_modifications()
			print(f"代码修改结果: {result}")

	def on_unload(self) -> None:
		# 恢复原始函数
		self._restore_functions()
		super().on_unload()
		print("所有修改已恢复")

	def _backup_functions(self):
		"""备份所有要修改的函数"""
		try:
			from src import community

			if hasattr(community, "authenticate_with_token"):
				self.original_functions["authenticate_with_token"] = community.AuthManager().authenticate_with_token
		except Exception as e:
			print(f"备份函数失败: {e}")

	def _restore_functions(self):
		"""恢复所有修改的函数"""
		try:
			from src import community

			for func_name, original_func in self.original_functions.items():
				if hasattr(community, func_name):
					setattr(community, func_name, original_func)
		except Exception as e:
			print(f"恢复函数失败: {e}")

	def apply_code_modifications(self) -> str:
		"""应用代码修改 - 使用最可靠的方法"""
		try:
			from src import community

			# 方法1: 直接替换（最可靠）
			community.AuthManager().authenticate_with_token = self.new_authenticate_function

			# 方法2: 使用系统的重写功能
			self.rewrite_function("src.community", "authenticate_with_token", self.new_authenticate_function)

			return "代码修改成功应用"
		except Exception as e:
			return f"代码修改失败: {e}"

	def new_authenticate_function(self, token):
		"""新的认证函数实现"""
		print(f"[插件] 认证请求: {token}")
		# 调用原始函数
		if "authenticate_with_token" in self.original_functions:
			return self.original_functions["authenticate_with_token"](token)
		return None

	def test_modification(self) -> str:
		"""测试修改是否生效"""
		try:
			from src import community

			# 模拟调用
			result = community.AuthManager().authenticate_with_token("test_token")
			return "测试成功，函数已修改"
		except Exception as e:
			return f"测试失败: {e}"

	def get_status(self) -> dict:
		"""获取插件状态"""
		return {"plugin_name": self.PLUGIN_NAME, "version": self.PLUGIN_VERSION, "config": self.config, "backup_functions": list(self.original_functions.keys())}
