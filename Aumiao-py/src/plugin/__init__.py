import importlib
from types import ModuleType
from typing import TYPE_CHECKING

# 类型检查时显式导入 (仅供 IDE 识别)
if TYPE_CHECKING:
	from . import chatmindai, dashscope  # noqa: TC004

# 修改后的 __all__ 列表,确保包含你需要的模块

__all__ = ["chatmindai", "dashscope"]

# 已加载的模块缓存字典
__loaded_modules: dict[str, ModuleType] = {}


def __getattr__(name: str) -> ModuleType:
	"""实现动态延迟加载"""
	if name in __all__:
		if name not in __loaded_modules:
			# 动态导入模块 (实际运行时加载)
			module = importlib.import_module(f".{name}", __package__)
			__loaded_modules[name] = module
		return __loaded_modules[name]
	# 如果没有找到相应的模块,抛出 AttributeError
	msg = f"module {__name__!r} has no attribute {name!r}"
	raise AttributeError(msg)


def __dir__() -> list[str]:
	"""增强 IDE 自动补全支持"""
	return sorted(__all__)
