from collections.abc import Callable
from typing import Any

from aumiao.api import auth, clouddb, codegame, community, edu, forum, library, pickduck, shop, user, whale, work
from aumiao.utils.acquire import ClientFactory, CodeMaoClient
from aumiao.utils.data import CacheManager, CodeMaoFile, DataManager, HistoryManager, NestedDefaultDict, PathConfig, SettingManager
from aumiao.utils.decorator import singleton
from aumiao.utils.tool import OutputHandler, ToolKitFactory


# 模块管理器
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


# 核心组件管理器
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


# 基础设施协调器
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
		# 认证模块
		self._modules.register("auth_manager", auth.AuthManager)
		self._modules.register("cloud_authenticator", auth.CloudAuthenticator)

		# 云数据库模块
		self._modules.register("ranking_manager", clouddb.Ranking)
		self._modules.register("coconut_cloud_database", clouddb.CoconutCloud)

		# 代码游戏模块
		self._modules.register("oversea_data_client", codegame.OverseaDataClient)
		self._modules.register("user_action_handler", codegame.UserActionHandler)

		# 社区模块
		self._modules.register("community_data_fetcher", community.DataFetcher)
		self._modules.register("community_action_handler", community.UserAction)

		# 教育模块
		self._modules.register("education_action_handler", edu.UserAction)
		self._modules.register("education_data_fetcher", edu.DataFetcher)

		# 论坛模块
		self._modules.register("forum_data_fetcher", forum.ForumDataFetcher)
		self._modules.register("forum_action_handler", forum.ForumActionHandler)

		# 图书馆模块
		self._modules.register("cartoon_data_fetcher", library.CartoonDataFetcher)
		self._modules.register("novel_data_fetcher", library.NovelDataFetcher)
		self._modules.register("novel_action_handler", library.NovelActionHandler)
		self._modules.register("book_data_fetcher", library.BookDataFetcher)
		self._modules.register("book_action_handler", library.BookActionHandler)

		# Pickduck模块
		self._modules.register("cookie_manager", pickduck.CookieManager)

		# 工坊模块
		self._modules.register("workshop_data_fetcher", shop.WorkshopDataFetcher)
		self._modules.register("workshop_action_handler", shop.WorkshopActionHandler)

		# 用户模块
		self._modules.register("user_data_fetcher", user.UserDataFetcher)
		self._modules.register("user_manager", user.UserManager)

		# 鲸鱼模块
		self._modules.register("report_data_fetcher", whale.ReportFetcher)
		self._modules.register("report_action_handler", whale.ReportHandler)

		# 作品模块
		self._modules.register("base_work_operations", work.BaseWorkOperations)
		self._modules.register("comment_operations", work.CommentOperations)
		self._modules.register("kitten_work_manager", work.KittenWorkManager)
		self._modules.register("neko_work_manager", work.NekoWorkManager)
		self._modules.register("wood_work_manager", work.WoodWorkManager)
		self._modules.register("coco_work_manager", work.CocoWorkManager)
		self._modules.register("collaboration_manager", work.CollaborationManager)
		self._modules.register("ai_services", work.AIServices)
		self._modules.register("teaching_plan_manager", work.TeachingPlanManager)
		self._modules.register("image_classify_manager", work.ImageClassifyManager)
		self._modules.register("package_manager", work.PackageManager)
		self._modules.register("sample_manager", work.SampleManager)
		self._modules.register("work_data_fetcher", work.WorkDataFetcher)

		# 工具模块
		self._modules.register("cache_manager_tool", CacheManager)
		self._modules.register("history_manager_tool", HistoryManager)
		self._modules.register("nested_defaultdict_tool", NestedDefaultDict)
		self._modules.register("file_manager_tool", CodeMaoFile)
		self._modules.register("output_handler_tool", OutputHandler)

	# 核心组件属性
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
		"""数据管理器"""
		return self._core.data_manager

	@property
	def path_config(self) -> PathConfig:
		"""路径配置管理器"""
		return self._core.path_config

	@property
	def setting_manager(self) -> SettingManager:
		"""设置管理器"""
		return self._core.setting_manager

	# 认证模块属性
	@property
	def auth_manager(self) -> "auth.AuthManager":
		"""认证管理模块"""
		return self._modules.get("auth_manager")

	@property
	def cloud_authenticator(self) -> "auth.CloudAuthenticator":
		"""云认证模块"""
		return self._modules.get("cloud_authenticator")

	# 云数据库模块属性
	@property
	def ranking_manager(self) -> "clouddb.Ranking":
		"""排行榜管理模块"""
		return self._modules.get("ranking_manager")

	@property
	def coconut_cloud_database(self) -> "clouddb.CoconutCloud":
		"""椰子云数据库模块"""
		return self._modules.get("coconut_cloud_database")

	# 代码游戏模块属性
	@property
	def oversea_data_client(self) -> "codegame.OverseaDataClient":
		"""海外数据客户端模块"""
		return self._modules.get("oversea_data_client")

	@property
	def user_action_handler(self) -> "codegame.UserActionHandler":
		"""用户动作处理模块"""
		return self._modules.get("user_action_handler")

	# 社区模块属性
	@property
	def community_data_fetcher(self) -> "community.DataFetcher":
		"""社区数据获取模块"""
		return self._modules.get("community_data_fetcher")

	@property
	def community_action_handler(self) -> "community.UserAction":
		"""社区动作处理模块"""
		return self._modules.get("community_action_handler")

	# 教育模块属性
	@property
	def education_action_handler(self) -> "edu.UserAction":
		"""教育动作处理模块"""
		return self._modules.get("education_action_handler")

	@property
	def education_data_fetcher(self) -> "edu.DataFetcher":
		"""教育数据获取模块"""
		return self._modules.get("education_data_fetcher")

	# 论坛模块属性
	@property
	def forum_data_fetcher(self) -> "forum.ForumDataFetcher":
		"""论坛数据获取模块"""
		return self._modules.get("forum_data_fetcher")

	@property
	def forum_action_handler(self) -> "forum.ForumActionHandler":
		"""论坛动作处理模块"""
		return self._modules.get("forum_action_handler")

	# 图书馆模块属性
	@property
	def cartoon_data_fetcher(self) -> "library.CartoonDataFetcher":
		"""漫画数据获取模块"""
		return self._modules.get("cartoon_data_fetcher")

	@property
	def novel_data_fetcher(self) -> "library.NovelDataFetcher":
		"""小说数据获取模块"""
		return self._modules.get("novel_data_fetcher")

	@property
	def novel_action_handler(self) -> "library.NovelActionHandler":
		"""小说动作处理模块"""
		return self._modules.get("novel_action_handler")

	@property
	def book_data_fetcher(self) -> "library.BookDataFetcher":
		"""书籍数据获取模块"""
		return self._modules.get("book_data_fetcher")

	@property
	def book_action_handler(self) -> "library.BookActionHandler":
		"""书籍动作处理模块"""
		return self._modules.get("book_action_handler")

	# Pickduck模块属性
	@property
	def cookie_manager(self) -> "pickduck.CookieManager":
		"""Cookie管理模块"""
		return self._modules.get("cookie_manager")

	# 工坊模块属性
	@property
	def workshop_data_fetcher(self) -> "shop.WorkshopDataFetcher":
		"""工坊数据获取模块"""
		return self._modules.get("workshop_data_fetcher")

	@property
	def workshop_action_handler(self) -> "shop.WorkshopActionHandler":
		"""工坊动作处理模块"""
		return self._modules.get("workshop_action_handler")

	# 用户模块属性
	@property
	def user_data_fetcher(self) -> "user.UserDataFetcher":
		"""用户数据获取模块"""
		return self._modules.get("user_data_fetcher")

	@property
	def user_manager(self) -> "user.UserManager":
		"""用户管理模块"""
		return self._modules.get("user_manager")

	# 鲸鱼模块属性
	@property
	def report_data_fetcher(self) -> "whale.ReportFetcher":
		"""报告数据获取模块"""
		return self._modules.get("report_data_fetcher")

	@property
	def report_action_handler(self) -> "whale.ReportHandler":
		"""报告动作处理模块"""
		return self._modules.get("report_action_handler")

	# 作品模块属性
	@property
	def base_work_operations(self) -> "work.BaseWorkOperations":
		"""基础作品操作模块"""
		return self._modules.get("base_work_operations")

	@property
	def comment_operations(self) -> "work.CommentOperations":
		"""评论操作模块"""
		return self._modules.get("comment_operations")

	@property
	def kitten_work_manager(self) -> "work.KittenWorkManager":
		"""Kitten作品管理模块"""
		return self._modules.get("kitten_work_manager")

	@property
	def neko_work_manager(self) -> "work.NekoWorkManager":
		"""Neko作品管理模块"""
		return self._modules.get("neko_work_manager")

	@property
	def wood_work_manager(self) -> "work.WoodWorkManager":
		"""Wood作品管理模块"""
		return self._modules.get("wood_work_manager")

	@property
	def coco_work_manager(self) -> "work.CocoWorkManager":
		"""Coco作品管理模块"""
		return self._modules.get("coco_work_manager")

	@property
	def collaboration_manager(self) -> "work.CollaborationManager":
		"""协作管理模块"""
		return self._modules.get("collaboration_manager")

	@property
	def ai_services(self) -> "work.AIServices":
		"""AI服务模块"""
		return self._modules.get("ai_services")

	@property
	def teaching_plan_manager(self) -> "work.TeachingPlanManager":
		"""教学计划管理模块"""
		return self._modules.get("teaching_plan_manager")

	@property
	def image_classify_manager(self) -> "work.ImageClassifyManager":
		"""图像分类管理模块"""
		return self._modules.get("image_classify_manager")

	@property
	def package_manager(self) -> "work.PackageManager":
		"""包管理模块"""
		return self._modules.get("package_manager")

	@property
	def sample_manager(self) -> "work.SampleManager":
		"""示例管理模块"""
		return self._modules.get("sample_manager")

	@property
	def work_data_fetcher(self) -> "work.WorkDataFetcher":
		"""作品数据获取模块"""
		return self._modules.get("work_data_fetcher")

	# 工具模块属性
	@property
	def cache_manager_tool(self) -> "CacheManager":
		"""缓存管理工具模块"""
		return self._modules.get("cache_manager_tool")

	@property
	def history_manager_tool(self) -> "HistoryManager":
		"""历史管理工具模块"""
		return self._modules.get("history_manager_tool")

	@property
	def nested_defaultdict_tool(self) -> "NestedDefaultDict":
		"""嵌套字典工具模块"""
		return self._modules.get("nested_defaultdict_tool")

	@property
	def file_manager_tool(self) -> "CodeMaoFile":
		"""文件管理工具模块"""
		return self._modules.get("file_manager_tool")

	@property
	def output_handler_tool(self) -> "OutputHandler":
		"""输出处理工具模块"""
		return self._modules.get("output_handler_tool")

	# 动态模块访问
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
		response: dict = coordinator.user_data_fetcher.fetch_user_honors(user_id=user_id)
		timestamp: int = coordinator.community_data_fetcher.fetch_current_timestamp_10()["data"]
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
		if coordinator.cache_manager_tool.data:
			coordinator.toolkit.create_data_analyzer().compare_datasets(
				before=coordinator.cache_manager_tool.data,
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
		coordinator.cache_manager_tool.update(user_data)
