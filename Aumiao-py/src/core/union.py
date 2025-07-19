from src.api import community, edu, forum, library, shop, user, whale, work
from src.utils import acquire, data, decorator, file, tool


@decorator.singleton
class Union:
	def __init__(self) -> None:
		self.acquire = acquire.CodeMaoClient()
		self.cache = data.CacheManager().data
		self.community_login = community.AuthManager()
		self.community_motion = community.UserAction()
		self.community_obtain = community.DataFetcher()
		self.data = data.DataManager().data
		self.edu_motion = edu.UserAction()
		self.edu_obtain = edu.DataFetcher()
		self.file = file.CodeMaoFile()
		self.forum_motion = forum.ForumActionHandler()
		self.forum_obtain = forum.ForumDataFetcher()
		self.setting = data.SettingManager().data
		self.shop_motion = shop.WorkshopActionHandler()
		self.shop_obtain = shop.WorkshopDataFetcher()
		self.tool = tool
		self.user_motion = user.UserManager()
		self.user_obtain = user.UserDataFetcher()
		self.whale_motion = whale.ReportHandler()
		self.whale_obtain = whale.ReportFetcher()
		self.whale_routine = whale.AuthManager()
		self.work_motion = work.WorkManager()
		self.work_obtain = work.WorkDataFetcher()
		self.library_obtain = library.NovelDataFetcher()


ClassUnion = Union().__class__
