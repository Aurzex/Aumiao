from src.utils import data, decorator

from .union import ClassUnion


@decorator.singleton
class Tool(ClassUnion):
	def __init__(self) -> None:
		super().__init__()
		self.cache_manager = data.CacheManager()

	def message_report(self, user_id: str) -> None:
		response = self.user_obtain.fetch_user_honors(user_id=user_id)
		timestamp = self.community_obtain.fetch_current_timestamp()["data"]

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

		if self.cache_manager.data:
			self.tool.DataAnalyzer().compare_datasets(
				before=self.cache_manager.data,
				after=user_data,
				metrics={
					"fans": "粉丝",
					"collected": "被收藏",
					"liked": "被赞",
					"view": "被预览",
				},
				timestamp_field="timestamp",
			)
		self.cache_manager.update(user_data)

	def guess_phone_num(self, phone_num: str) -> int | None:
		for i in range(10000):
			guess = f"{i:04d}"
			test_string = int(phone_num.replace("****", guess))
			if self.user_motion.verify_phone_number(test_string):
				return test_string
		return None
