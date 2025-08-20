from collections.abc import Callable
from typing import Any

from src.utils.plugin import BasePlugin


class Plugin(BasePlugin):
	@property
	def PLUGIN_NAME(self) -> str:
		return "GreetingPlugin"

	@property
	def PLUGIN_DESCRIPTION(self) -> str:
		return "一个简单的问候插件，提供多种问候功能"

	@property
	def PLUGIN_VERSION(self) -> str:
		return "1.0.0"

	@property
	def PLUGIN_CONFIG_SCHEMA(self) -> dict[str, Any]:
		return {"default_greeting": str, "use_uppercase": bool, "max_repeat_count": int}

	@property
	def PLUGIN_DEFAULT_CONFIG(self) -> dict[str, Any]:
		return {"default_greeting": "Hello", "use_uppercase": False, "max_repeat_count": 3}

	def __init__(self):
		super().__init__()
		self.config = {}

	def on_load(self, config: dict[str, Any]) -> None:
		super().on_load(config)
		self.config = config
		print(f"[GreetingPlugin] 配置已加载: {config}")

	def on_unload(self) -> None:
		super().on_unload()
		print("[GreetingPlugin] 插件已卸载")

	def register(self) -> dict[str, tuple[Callable, str]]:
		return {"greet": (self.greet, "向指定的人问候"), "greet_many": (self.greet_many, "向多个人问候"), "repeat_greeting": (self.repeat_greeting, "重复问候指定次数")}

	def greet(self, name: str = "World") -> str:
		"""向指定的人问候"""
		greeting = self.config.get("default_greeting", "Hello")
		message = f"{greeting}, {name}!"

		if self.config.get("use_uppercase", False):
			message = message.upper()

		print(message)
		return message

	def greet_many(self, name1: str, name2: str = "", name3: str = "") -> list[str]:
		"""向多个人问候

		Args:
		    name1: 第一个人的名字 (必需)
		    name2: 第二个人的名字 (可选)
		    name3: 第三个人的名字 (可选)
		"""
		names = [name1]
		if name2:
			names.append(name2)
		if name3:
			names.append(name3)

		results = []
		for name in names:
			results.append(self.greet(name))
		return results

	def repeat_greeting(self, name: str = "World", count: int = 1) -> list[str]:
		"""重复问候指定次数

		Args:
		    name: 要问候的人名
		    count: 重复次数 (最大不超过配置中的max_repeat_count)
		"""
		max_count = self.config.get("max_repeat_count", 3)
		actual_count = min(count, max_count)

		results = []
		for _ in range(actual_count):
			results.append(self.greet(name))

		return results
