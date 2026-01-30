"""基础定义和核心 InfrastructureCoordinator 类"""

from collections.abc import Callable
from typing import Any

from aumiao.api import auth, community, edu, forum, library, shop, user, whale, work
from aumiao.api import auth as auth_ins
from aumiao.utils import data, decorator
from aumiao.utils import file as file_ins
from aumiao.utils import tool as tool_ins
from aumiao.utils.acquire import ClientFactory, CodeMaoClient
from aumiao.utils.data import CacheManager, CodeMaoCache, CodeMaoData, CodeMaoSetting, DataManager, HistoryManager, SettingManager
from aumiao.utils.decorator import singleton
from aumiao.utils.tool import ToolKitFactory

toolkit = tool_ins.ToolKitFactory()


# ==============================
# 模块管理器: 类型友好版本
# ==============================
class ModuleManager:
	"""管理所有模块的延迟加载和缓存"""

	def __init__(self) -> None:
		self._modules: dict[str, Any] = {}
		self._module_creators: dict[str, Callable[[], Any]] = {}

	def register(self, name: str, creator: Callable[[], Any]) -> None:
		"""注册模块创建器"""
		self._module_creators[name] = creator

	def get(self, name: str) -> Any:
		"""获取模块实例 (延迟加载)"""
		if name not in self._modules:
			if name not in self._module_creators:
				msg = f"模块 '{name}' 未注册"
				raise AttributeError(msg)
			self._modules[name] = self._module_creators[name]()
		return self._modules[name]

	def clear_cache(self, name: str | None = None) -> None:
		"""清除模块缓存"""
		if name:
			self._modules.pop(name, None)
		else:
			self._modules.clear()

	def list_available(self) -> list[str]:
		"""列出所有可用的模块"""
		return list(self._module_creators.keys())

	def list_loaded(self) -> list[str]:
		"""列出已加载的模块"""
		return list(self._modules.keys())


# ==============================
# 核心组件管理器
# ==============================
class CoreManager:
	"""管理立即加载的核心组件"""

	def __init__(self) -> None:
		# 立即初始化的核心组件
		self.client = ClientFactory().create_codemao_client()
		self.toolkit = toolkit
		self.data_manager = DataManager()
		self.setting_manager = SettingManager()
		self.cache_manager = CacheManager()
		self.history_manager = HistoryManager()

	@property
	def data(self) -> CodeMaoData:
		"""快捷访问数据"""
		return self.data_manager.data

	@property
	def data_man(self) -> DataManager:
		"""快捷访问数据"""
		return self.data_manager

	@property
	def setting(self) -> CodeMaoSetting:
		"""快捷访问设置"""
		return self.setting_manager.data

	@property
	def cache(self) -> CodeMaoCache:
		"""快捷访问缓存"""
		return self.cache_manager.data

	@property
	def upload_history(self) -> HistoryManager:
		"""快捷访问历史记录"""
		return self.history_manager


# ==============================
# 基础设施协调器: 类型友好主类
# ==============================
class InfrastructureCoordinator:
	"""
	基础设施协调器 - 类型友好版本
	使用明确的属性定义, 确保类型检查器能识别所有属性
	"""

	def __init__(self) -> None:
		# 组合核心组件管理器
		self._core = CoreManager()
		# 组合模块管理器
		self._modules = ModuleManager()
		# 初始化模块注册表
		self._initialize_module_registry()

	def _initialize_module_registry(self) -> None:
		"""初始化模块注册表"""
		# API 模块
		api_modules = {
			"auth": auth.AuthManager,
			"community_motion": community.UserAction,
			"community_obtain": community.DataFetcher,
			"edu_motion": edu.UserAction,
			"edu_obtain": edu.DataFetcher,
			"forum_motion": forum.ForumActionHandler,
			"forum_obtain": forum.ForumDataFetcher,
			"novel_motion": library.NovelActionHandler,
			"novel_obtain": library.NovelDataFetcher,
			"shop_motion": shop.WorkshopActionHandler,
			"shop_obtain": shop.WorkshopDataFetcher,
			"user_motion": user.UserManager,
			"user_obtain": user.UserDataFetcher,
			"work_motion": work.BaseWorkManager,
			"work_obtain": work.WorkDataFetcher,
			"whale_motion": whale.ReportHandler,
			"whale_obtain": whale.ReportFetcher,
			# 工具模块
			"printer": tool_ins.OutputHandler,
			"file": file_ins.CodeMaoFile,
		}
		for name, creator in api_modules.items():
			self._modules.register(name, creator)

	# ==============================
	# 公共接口
	# ==============================
	def register_module(self, name: str, creator: Callable[[], Any]) -> None:
		"""注册新模块"""
		self._modules.register(name, creator)

	def clear_module_cache(self, module_name: str | None = None) -> None:
		"""清除模块缓存"""
		self._modules.clear_cache(module_name)

	def list_available_modules(self) -> list[str]:
		"""列出所有可用模块"""
		return self._modules.list_available()

	def list_loaded_modules(self) -> list[str]:
		"""列出已加载的模块"""
		return self._modules.list_loaded()

	# ==============================
	# 核心组件属性 (类型明确)
	# ==============================
	@property
	def client(self) -> CodeMaoClient:
		"""核心客户端"""
		return self._core.client

	@property
	def toolkit(self) -> ToolKitFactory:
		"""工具模块"""
		return self._core.toolkit

	@property
	def data(self) -> CodeMaoData:
		"""数据"""
		return self._core.data

	@property
	def data_man(self) -> DataManager:
		"""快捷访问数据"""
		return self._core.data_man

	@property
	def setting(self) -> CodeMaoSetting:
		"""设置"""
		return self._core.setting

	@property
	def cache(self) -> CodeMaoCache:
		"""缓存"""
		return self._core.cache

	@property
	def upload_history(self) -> HistoryManager:
		"""上传历史"""
		return self._core.upload_history

	# ==============================
	# API 模块属性 (延迟加载, 类型明确)
	# ==============================
	@property
	def auth(self) -> "auth_ins.AuthManager":
		"""认证管理模块"""
		return self._modules.get("auth")

	@property
	def community_motion(self) -> "community.UserAction":
		"""社区动作模块"""
		return self._modules.get("community_motion")

	@property
	def community_obtain(self) -> "community.DataFetcher":
		"""社区数据获取模块"""
		return self._modules.get("community_obtain")

	@property
	def edu_motion(self) -> "edu.UserAction":
		"""教育动作模块"""
		return self._modules.get("edu_motion")

	@property
	def edu_obtain(self) -> "edu.DataFetcher":
		"""教育数据获取模块"""
		return self._modules.get("edu_obtain")

	@property
	def forum_motion(self) -> "forum.ForumActionHandler":
		"""论坛动作模块"""
		return self._modules.get("forum_motion")

	@property
	def forum_obtain(self) -> "forum.ForumDataFetcher":
		"""论坛数据获取模块"""
		return self._modules.get("forum_obtain")

	@property
	def novel_motion(self) -> "library.NovelActionHandler":
		"""小说动作模块"""
		return self._modules.get("novel_motion")

	@property
	def novel_obtain(self) -> "library.NovelDataFetcher":
		"""小说数据获取模块"""
		return self._modules.get("novel_obtain")

	@property
	def shop_motion(self) -> "shop.WorkshopActionHandler":
		"""商店动作模块"""
		return self._modules.get("shop_motion")

	@property
	def shop_obtain(self) -> "shop.WorkshopDataFetcher":
		"""商店数据获取模块"""
		return self._modules.get("shop_obtain")

	@property
	def user_motion(self) -> "user.UserManager":
		"""用户动作模块"""
		return self._modules.get("user_motion")

	@property
	def user_obtain(self) -> "user.UserDataFetcher":
		"""用户数据获取模块"""
		return self._modules.get("user_obtain")

	@property
	def work_motion(self) -> "work.BaseWorkManager":
		"""作品动作模块"""
		return self._modules.get("work_motion")

	@property
	def work_obtain(self) -> "work.WorkDataFetcher":
		"""作品数据获取模块"""
		return self._modules.get("work_obtain")

	@property
	def whale_motion(self) -> "whale.ReportHandler":
		"""鲸鱼报告动作模块"""
		return self._modules.get("whale_motion")

	@property
	def whale_obtain(self) -> "whale.ReportFetcher":
		"""鲸鱼报告数据获取模块"""
		return self._modules.get("whale_obtain")

	# ==============================
	# 工具模块属性 (延迟加载, 类型明确)
	# ==============================
	@property
	def printer(self) -> "tool_ins.OutputHandler":
		"""打印工具模块"""
		return self._modules.get("printer")

	@property
	def file(self) -> "file_ins.CodeMaoFile":
		"""文件操作模块"""
		return self._modules.get("file")

	# ==============================
	# 动态模块访问 (可选, 用于访问动态注册的模块)
	# ==============================
	def get_module(self, name: str) -> Any:
		"""
		动态获取模块 (用于访问动态注册的模块)
		这是类型安全的, 因为调用者知道返回类型
		"""
		return self._modules.get(name)


# ==============================
# 单例包装: 保持向后兼容
# ==============================
@singleton
class Union(InfrastructureCoordinator):
	"""
	保持原有 Union 类名, 继承基础设施协调器
	提供全局单例访问
	"""


# ==============================
# 业务逻辑类 (保持原样)
# ==============================
ClassUnion = Union().__class__
# ==============================
# 类型别名 (用于类型注解)
# ==============================
InfraCoordinator = Union
"""基础设施协调器的类型别名"""


@decorator.singleton
class Index(ClassUnion):  # ty:ignore [unsupported-base]
	"""首页展示类"""

	# 颜色配置
	COLOR_DATA = "\033[38;5;228m"
	COLOR_LINK = "\033[4;38;5;183m"
	COLOR_RESET = "\033[0m"
	COLOR_SLOGAN = "\033[38;5;80m"
	COLOR_TITLE = "\033[38;5;75m"
	COLOR_VERSION = "\033[38;5;114m"

	def _print_title(self, title: str) -> None:
		"""打印标题"""
		print(f"\n {self.COLOR_TITLE}{'*' * 22} {title} {'*' * 22}{self.COLOR_RESET}")

	def _print_slogan(self) -> None:
		"""打印标语"""
		print(f"\n {self.COLOR_SLOGAN}{self.setting.PROGRAM.SLOGAN}{self.COLOR_RESET}")
		print(f"{self.COLOR_VERSION} 版本号: {self.setting.PROGRAM.VERSION}{self.COLOR_RESET}")

	def _print_lyric(self) -> None:
		"""打印歌词"""
		self._print_title("一言")
		lyric: str = self.client.send_request(endpoint="https://lty.vc/lyric", method="GET").text
		print(f"{self.COLOR_SLOGAN}{lyric}{self.COLOR_RESET}")

	def _print_announcements(self) -> None:
		"""打印公告"""
		self._print_title("公告")
		print(f"{self.COLOR_LINK} 编程猫社区行为守则 https://shequ.codemao.cn/community/1619098 {self.COLOR_RESET}")
		print(f"{self.COLOR_LINK} 2025 编程猫拜年祭活动 https://shequ.codemao.cn/community/1619855 {self.COLOR_RESET}")

	def _print_user_data(self) -> None:
		"""打印用户数据"""
		self._print_title("数据")
		if self.data.ACCOUNT_DATA.id:
			Tool().message_report(user_id=self.data.ACCOUNT_DATA.id)
			print(f"{self.COLOR_TITLE}{'*' * 50}{self.COLOR_RESET}\n")

	def index(self) -> None:
		"""显示首页"""
		self._print_slogan()
		# self._print_lyric()  # 暂时注释掉歌词显示
		self._print_announcements()
		self._print_user_data()


@decorator.singleton
class Tool(ClassUnion):  # ty:ignore [unsupported-base]
	"""工具类"""

	def __init__(self) -> None:
		super().__init__()
		self._cache_manager = data.CacheManager()

	def message_report(self, user_id: int) -> None:
		"""生成用户数据报告"""
		response = self.user_obtain.fetch_user_honors(user_id=user_id)
		timestamp = self.community_obtain.fetch_current_timestamp_10()["data"]
		user_data = {
			"user_id": response["user_id"],
			"nickname": response["nickname"],
			"level": response["author_level"],
			"fans": response["fans_total"],
			"collected": response["collected_total"],
			"liked": response["liked_total"],
			"view": response["view_times"],
			"timestamp": timestamp,
		}
		# 如果有缓存数据, 进行对比分析
		if self._cache_manager.data:
			self.toolkit.create_data_analyzer().compare_datasets(
				before=self._cache_manager.data,
				after=user_data,
				metrics={
					"fans": "粉丝",
					"collected": "被收藏",
					"liked": "被赞",
					"view": "被预览",
				},
				timestamp_field="timestamp",
			)
		# 更新缓存
		self._cache_manager.update(user_data)
