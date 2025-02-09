import importlib
from sys import argv
from types import ModuleType
from typing import TYPE_CHECKING

# Nuitka 编译兼容性处理 --------------------------------------------------------
# 以下代码仅在编译时执行,用于确保 Nuitka 能正确打包子模块
_is_compiling = any("nuitka" in arg.lower() for arg in argv)

# 类型检查时显式导入 (仅供 IDE 识别)
if TYPE_CHECKING or _is_compiling:
	from .api import community, edu, forum, library, pickduck, shop, user, whale, work
	from .core import client
	from .utils import data, decorator

# 修改后的 __all__ 列表,确保包含你需要的模块
__all__ = ["client", "community", "data", "decorator", "edu", "forum", "library", "pickduck", "shop", "user", "whale", "work"]

# 已加载的模块缓存字典
__loaded_modules: dict[str, ModuleType] = {}

# 定义模块导入映射
_module_paths = {
	"client": ".core.client",
	"data": ".utils.data",
	"decorator": ".utils.decorator",
	"community": ".api.community",
	"edu": ".api.edu",
	"forum": ".api.forum",
	"library": ".api.library",
	"pickduck": ".api.pickduck",
	"shop": ".api.shop",
	"user": ".api.user",
	"whale": ".api.whale",
	"work": ".api.work",
}


def __getattr__(name: str) -> ModuleType:
	"""实现动态延迟加载"""
	if name in __all__:
		if name not in __loaded_modules:
			# 动态导入模块 (实际运行时加载)
			module = importlib.import_module(_module_paths[name], __package__) if name in _module_paths else importlib.import_module(f".{name}", __package__)
			__loaded_modules[name] = module
		return __loaded_modules[name]
	# 如果没有找到相应的模块,抛出 AttributeError
	msg = f"module {__name__!r} has no attribute {name!r}"
	raise AttributeError(msg)


def __dir__() -> list[str]:
	"""增强 IDE 自动补全支持"""
	return sorted([*__all__, "__version__"])
