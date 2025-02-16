import importlib
from sys import argv
from types import ModuleType
from typing import TYPE_CHECKING

# Nuitka 编译兼容性处理 --------------------------------------------------------
# 以下代码仅在编译时执行,用于确保 Nuitka 能正确打包子模块
_is_compiling = any("nuitka" in arg.lower() for arg in argv)

# 类型检查时显式导入 (仅供 IDE 识别)
if TYPE_CHECKING or _is_compiling:
	from .api import community, edu, forum, library, pickduck, shop, user, whale, work  # noqa: F401
	from .core import client  # noqa: F401
	from .utils import data, decorator  # noqa: F401

# 修改后的 __all__ 列表,确保包含你需要的模块
# __all__ = ["client", "community", "data", "decorator", "edu", "forum", "library", "pickduck", "shop", "user", "whale", "work"]

# 已加载的模块缓存字典
__loaded_modules: dict[str, ModuleType] = {}

# 定义模块导入映射
_module_paths = {
	"client": ".core.client",
	"data": ".utils.data",
	"decorator": ".utils.decorator",  #  装饰器模块
	"community": ".api.community",  #  社区模块
	"edu": ".api.edu",  #  教育模块
	"forum": ".api.forum",  #  论坛模块
	"library": ".api.library",  #  图书馆模块
	"pickduck": ".api.pickduck",  #  点鸭模块
	"shop": ".api.shop",  #  商店模块
	"user": ".api.user",  #  用户模块
	"whale": ".api.whale",  #  Whale模块
	"work": ".api.work",  #  工作模块
}

__all__ = list(_module_paths.keys())  # type: ignore # | __all__  # noqa: PGH003


def __getattr__(name: str) -> ModuleType:
	"""实现动态延迟加载"""
	if name in __all__:
		if name not in __loaded_modules:
			# 动态导入模块 (实际运行时加载)
			module = importlib.import_module(_module_paths.get(name, ".{name}"), __package__)
			__loaded_modules[name] = module
		return __loaded_modules[name]
	# 如果没有找到相应的模块,抛出 AttributeError
	msg = f"module {__name__!r} has no attribute {name!r}"
	raise AttributeError(msg)


def __dir__() -> list[str]:
	"""增强 IDE 自动补全支持"""
	return sorted([*__all__, "__version__"])
