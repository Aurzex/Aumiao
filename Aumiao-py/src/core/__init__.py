import importlib
import sys
from sys import argv
from types import ModuleType
from typing import TYPE_CHECKING, Final

# 版本信息 (新增)
__version__ = "2.4.0"

# Nuitka 编译兼容性处理 --------------------------------------------------------
# 更可靠的编译环境检测方式 (同时检查 nuitka 参数和 __compiled__ 属性)
_is_compiling: bool = any("nuitka" in arg.lower() for arg in argv) or hasattr(sys, "_nuitka_compiled")

# 类型检查时显式导入 (仅供 IDE 识别)
if TYPE_CHECKING or _is_compiling:
	# 显式导入所有子模块以确保类型系统识别
	from . import base, process, retrieve, services

# 模块路径映射 (使用 Final 类型提示)
_MODULE_PATHS: Final[dict[str, str]] = {"base": ".core.base", "process": ".core.process", "retrieve": ".core.retrieve", "services": ".core.services"}

# 导出列表 (根据映射自动生成)
__all__: list[str] = [  # noqa: PLE0604
	*list(_MODULE_PATHS.keys()),
	"__version__",
	"base",
	"process",
	"retrieve",
	"services",
]  # type: ignore  # noqa: PGH003

# 模块缓存 (使用弱引用字典可考虑 WeakValueDictionary)
_LOADED_MODULES: dict[str, ModuleType] = {}


def __getattr__(name: str) -> ModuleType:
	"""实现按需动态加载模块 (PEP 562)

	Args:
		name: 请求的模块名称

	Returns:
		加载完成的模块对象

	Raises:
		AttributeError: 当请求不存在的模块时
	"""
	# 优先检查缓存
	if name in _LOADED_MODULES:
		return _LOADED_MODULES[name]

	# 验证模块名称合法性
	if name not in _MODULE_PATHS:
		msg = f"module {__name__!r} has no attribute {name!r}"
		raise AttributeError(msg)

	try:
		# 动态导入模块
		module = importlib.import_module(name=_MODULE_PATHS[name], package=__package__)
		# 缓存模块引用
		_LOADED_MODULES[name] = module
	except ImportError as e:
		# 转换异常类型并提供更清晰的错误信息
		msg = f"Failed to import module {name!r} from {__name__}"
		raise AttributeError(msg) from e
	else:
		return module


def __dir__() -> list[str]:
	"""返回模块的公共接口列表 (包含版本信息)"""
	return sorted(__all__)
