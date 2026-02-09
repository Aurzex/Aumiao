from collections.abc import Callable
from typing import Any

from aumiao.api import auth, community, edu, forum, library, shop, user, whale, work
from aumiao.utils.acquire import ClientFactory, CodeMaoClient
from aumiao.utils.data import CacheManager, CodeMaoFile, DataManager, HistoryManager, NestedDefaultDict, PathConfig, SettingManager
from aumiao.utils.decorator import singleton
from aumiao.utils.tool import OutputHandler, ToolKitFactory


# ==============================
# 模块管理器: 类型友好版本
# ==============================
@singleton
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
@singleton
class CoreManager:
	"""管理立即加载的核心组件"""

	def __init__(self) -> None:
		# 立即初始化的核心组件
		self.client = ClientFactory().create_codemao_client()
		self.toolkit = ToolKitFactory()
		self.data_manager = DataManager()
		self.path_config = PathConfig()
		self.setting_manager = SettingManager()


# ==============================
# 基础设施协调器: 类型友好主类
# ==============================
@singleton
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
		api_modules: dict = {
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
			"cache_manager": CacheManager,
			"history_manager": HistoryManager,
			"nested_defaultdict": NestedDefaultDict,
			"file_manager": CodeMaoFile,
			# 工具模块
			"printer": OutputHandler,
		}
		for name, creator in api_modules.items():
			self._modules.register(name, creator)

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
	def data_manager(self) -> DataManager:
		"""数据"""
		return self._core.data_manager

	@property
	def path_config(self) -> PathConfig:
		"""数据"""
		return self._core.path_config

	@property
	def setting_manager(self) -> SettingManager:
		"""设置"""
		return self._core.setting_manager

	# ==============================
	# API 模块属性 (延迟加载, 类型明确)
	# ==============================
	@property
	def auth_manager(self) -> "auth.AuthManager":
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

	@property
	def cache_manager(self) -> "CacheManager":
		"""缓存"""
		return self._modules.get("cache_manager")

	@property
	def history_manager(self) -> "HistoryManager":
		"""上传历史"""
		return self._modules.get("history_manager")

	@property
	def nested_defaultdict(self) -> "NestedDefaultDict":
		"""嵌套字典"""
		return self._modules.get("nested_defaultdict")

	@property
	def file_manager(self) -> "CodeMaoFile":
		"""文件写入"""
		return self._modules.get("file_manager")

	# ==============================
	# 工具模块属性 (延迟加载, 类型明确)
	# ==============================
	@property
	def printer(self) -> "OutputHandler":
		"""打印工具模块"""
		return self._modules.get("printer")

	# ==============================
	# 动态模块访问 (可选, 用于访问动态注册的模块)
	# ==============================
	def get_module(self, name: str) -> Any:
		"""
		动态获取模块 (用于访问动态注册的模块)
		这是类型安全的, 因为调用者知道返回类型
		"""
		return self._modules.get(name)


coordinator = InfrastructureCoordinator()


@singleton
class Index:
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
		print(f"\n {self.COLOR_SLOGAN}{coordinator.setting_manager.data.PROGRAM.SLOGAN}{self.COLOR_RESET}")
		print(f"{self.COLOR_VERSION} 版本号: {coordinator.setting_manager.data.PROGRAM.VERSION}{self.COLOR_RESET}")

	def _print_lyric(self) -> None:
		"""打印歌词"""
		self._print_title("一言")
		lyric: str = coordinator.client.send_request(endpoint="https://lty.vc/lyric", method="GET").text
		print(f"{self.COLOR_SLOGAN}{lyric}{self.COLOR_RESET}")

	def _print_announcements(self) -> None:
		"""打印公告"""
		self._print_title("公告")
		print(f"{self.COLOR_LINK} 编程猫社区行为守则 https://shequ.codemao.cn/community/1619098 {self.COLOR_RESET}")
		print(f"{self.COLOR_LINK} 2025 编程猫拜年祭活动 https://shequ.codemao.cn/community/1619855 {self.COLOR_RESET}")

	def _print_user_data(self) -> None:
		"""打印用户数据"""
		self._print_title("数据")
		if coordinator.data_manager.data.ACCOUNT_DATA.id:
			Tool().message_report(user_id=coordinator.data_manager.data.ACCOUNT_DATA.id)
			print(f"{self.COLOR_TITLE}{'*' * 50}{self.COLOR_RESET}\n")

	def index(self) -> None:
		"""显示首页"""
		self._print_slogan()
		# self._print_lyric()  # 暂时注释掉歌词显示
		self._print_announcements()
		self._print_user_data()


@singleton
class Tool:
	"""工具类"""

	def __init__(self) -> None:
		super().__init__()

	@staticmethod
	def message_report(user_id: int) -> None:
		"""生成用户数据报告"""
		response: dict = coordinator.user_obtain.fetch_user_honors(user_id=user_id)
		timestamp: int = coordinator.community_obtain.fetch_current_timestamp_10()["data"]
		user_data: dict = {
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
		if coordinator.cache_manager.data:
			coordinator.toolkit.create_data_analyzer().compare_datasets(
				before=coordinator.cache_manager.data,
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
		coordinator.cache_manager.update(user_data)
