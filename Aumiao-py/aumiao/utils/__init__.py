import importlib
import sys
from sys import argv
from types import ModuleType
from typing import TYPE_CHECKING, Final

__version__: Final[str] = "2.7.0"

# 编译环境检测
_is_compiling: bool = hasattr(sys, "_nuitka_compiled") or hasattr(sys, "frozen") or any("nuitka" in arg.lower() for arg in argv)

# 类型检查支持
if TYPE_CHECKING or _is_compiling:
	from . import acquire, data, decorator, tool

# 模块路径映射
_MODULE_PATHS: Final[dict[str, str]] = {"acquire": ".utils.acquire", "data": ".utils.data", "decorator": ".utils.decorator", "tool": ".utils.tool"}

# 固定的导出列表
__all__: Final[tuple[str, ...]] = ("__version__", "acquire", "data", "decorator", "tool")

# 模块缓存
_LOADED_MODULES: dict[str, ModuleType] = {}


def __getattr__(name: str) -> ModuleType:
	"""按需动态加载模块"""
	if name in _LOADED_MODULES:
		return _LOADED_MODULES[name]

	if name not in _MODULE_PATHS:
		msg = f"module {__name__!r} has no attribute {name!r}"
		raise AttributeError(msg)

	try:
		module = importlib.import_module(name=_MODULE_PATHS[name], package=__package__)
		_LOADED_MODULES[name] = module
	except ImportError as e:
		msg = f"Module {name!r} not available in compiled build" if _is_compiling else f"Failed to import module {name!r}: {e!s}"
		raise AttributeError(msg) from e
	else:
		return module


def __dir__() -> list[str]:
	"""返回排序后的公共接口列表"""
	return sorted(__all__)


# 编译时确保所有模块都被引用
if _is_compiling:
	# 这些引用确保编译时包含所有模块
	_ = acquire, data, decorator, tool
