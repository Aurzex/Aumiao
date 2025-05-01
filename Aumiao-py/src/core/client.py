from collections import defaultdict
from collections.abc import Generator
from enum import Enum
from json import loads
from random import choice, randint
from typing import Any, Callable, Literal, TypedDict, cast, overload

from src.api import community, edu, forum, shop, user, whale, work
from src.utils import acquire, data, decorator, file, tool


class FormattedAnswer(TypedDict):
	question: str
	responses: list[str] | str


class ReplyType(Enum):
	WORK_COMMENT = "WORK_COMMENT"
	WORK_REPLY = "WORK_REPLY"
	# 其他类型同理


VALID_REPLY_TYPES = {"WORK_COMMENT", "WORK_REPLY", "WORK_REPLY_REPLY", "POST_COMMENT", "POST_REPLY", "POST_REPLY_REPLY"}
OK_CODE = 200


@decorator.singleton
class Union:
	# 初始化Union类
	def __init__(self) -> None:
		self.acquire = acquire.CodeMaoClient()
		self.cache = data.CacheManager().data
		self.community_obtain = community.Obtain()
		self.community_login = community.Login()
		self.community_motion = community.Motion()
		self.data = data.DataManager().data
		self.edu_obtain = edu.Obtain()
		self.edu_motion = edu.Motion()
		self.file = file.CodeMaoFile()
		self.forum_motion = forum.Motion()
		self.forum_obtain = forum.Obtain()
		self.setting = data.SettingManager().data
		self.shop_motion = shop.Motion()
		self.shop_obtain = shop.Obtain()
		self.tool_process = tool.CodeMaoProcess()
		self.tool_routine = tool.CodeMaoRoutine()
		self.user_motion = user.Motion()
		self.user_obtain = user.Obtain()
		self.whale_obtain = whale.Obtain()
		self.whale_motion = whale.Motion()
		self.whale_routine = whale.Routine()
		self.work_motion = work.Motion()
		self.work_obtain = work.Obtain()


ClassUnion = Union().__class__


@decorator.singleton
class Tool(ClassUnion):
	def __init__(self) -> None:
		super().__init__()
		self.cache_manager = data.CacheManager()  # 添加这行

	def message_report(self, user_id: str) -> None:
		# 获取用户荣誉信息

		response = self.user_obtain.get_user_honor(user_id=user_id)
		# 获取当前时间戳
		timestamp = self.community_obtain.get_timestamp()["data"]
		# 构造用户数据字典
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
		# 获取缓存数据
		before_data = self.cache_manager.data
		# 如果缓存数据不为空,则显示数据变化
		if before_data != {}:
			self.tool_routine.display_data_changes(
				before_data=before_data,
				after_data=user_data,
				metrics={
					"fans": "粉丝",
					"collected": "被收藏",
					"liked": "被赞",
					"view": "被预览",
				},
				date_field="timestamp",
			)
		# 更新缓存数据
		self.cache_manager.update(user_data)  # 使用管理器的 update 方法

	# 猜测手机号码(暴力枚举)
	def guess_phonenum(self, phonenum: str) -> int | None:
		# 枚举10000个四位数
		for i in range(10000):
			guess = f"{i:04d}"  # 格式化为四位数,前面补零
			test_string = int(phonenum.replace("****", guess))
			print(test_string)
			if self.user_motion.verify_phone(test_string):
				return test_string
		return None


@decorator.singleton
class Index(ClassUnion):
	def __init__(self) -> None:
		super().__init__()
		# 颜色配置
		self.COLOR_SLOGAN = "\033[38;5;80m"  # 湖水青-标语
		self.COLOR_VERSION = "\033[38;5;114m"  # 新芽绿-版本号
		self.COLOR_TITLE = "\033[38;5;75m"  # 晴空蓝-标题
		self.COLOR_LINK = "\033[4;38;5;183m"  # 薰衣草紫带下划线-链接
		self.COLOR_DATA = "\033[38;5;228m"  # 月光黄-数据
		self.COLOR_RESET = "\033[0m"  # 样式重置

	def index(self) -> None:
		"""打印引导界面"""
		# 打印slogan
		print(f"\n{self.COLOR_SLOGAN}{self.setting.PROGRAM.SLOGAN}{self.COLOR_RESET}")
		# 打印版本号
		print(f"{self.COLOR_VERSION}版本号: {self.setting.PROGRAM.VERSION}{self.COLOR_RESET}")

		title = f"{'*' * 22} 一言 {'*' * 22}"
		print(f"\n{self.COLOR_TITLE}{title}{self.COLOR_RESET}")
		lyric: str = self.acquire.send_request(endpoint="https://lty.vc/lyric", method="GET").text
		print(f"{self.COLOR_SLOGAN}{lyric}{self.COLOR_RESET}")
		# 打印公告标题
		title = f"{'*' * 22} 公告 {'*' * 22}"
		print(f"\n{self.COLOR_TITLE}{title}{self.COLOR_RESET}")
		# 打印链接
		print(f"{self.COLOR_LINK}编程猫社区行为守则 https://shequ.codemao.cn/community/1619098{self.COLOR_RESET}")
		print(f"{self.COLOR_LINK}2025编程猫拜年祭活动 https://shequ.codemao.cn/community/1619855{self.COLOR_RESET}")

		# 打印数据标题
		data_title = f"{'*' * 22} 数据 {'*' * 22}"
		print(f"\n{self.COLOR_DATA}{data_title}{self.COLOR_RESET}")
		# 调用数据报告
		Tool().message_report(user_id=self.data.ACCOUNT_DATA.id)
		# 分隔线
		print(f"{self.COLOR_TITLE}{'*' * 50}{self.COLOR_RESET}\n")


@decorator.singleton
class Obtain(ClassUnion):
	def __init__(self) -> None:
		super().__init__()

	# 获取新回复(传入参数就获取前*个回复,若没传入就获取新回复数量, 再获取新回复数量个回复)
	def get_new_replies(
		self,
		limit: int = 0,
		type_item: Literal["LIKE_FORK", "COMMENT_REPLY", "SYSTEM"] = "COMMENT_REPLY",
	) -> list[dict[str, str | int | dict]]:
		list_ = []
		# 获取新回复数量
		reply_num = self.community_obtain.get_message_count(method="web")[0]["count"]
		# 如果新回复数量为0且limit也为0,则返回空列表
		if reply_num == limit == 0:
			return [{}]
		# 如果limit为0,则获取新回复数量个回复,否则获取limit个回复
		result_num = reply_num if limit == 0 else limit
		offset = 0
		# 循环获取新回复
		while result_num >= 0:
			# 每次获取5个或剩余回复数量或200个回复
			limit = sorted([5, result_num, 200])[1]
			# 获取回复
			response = self.community_obtain.get_replies(types=type_item, limit=limit, offset=offset)
			# 将回复添加到列表中
			list_.extend(response["items"][:result_num])
			# 更新剩余回复数量
			result_num -= limit
			# 更新偏移量
			offset += limit
		return list_

	@overload
	def get_comments_detail_new(
		self,
		com_id: int,
		source: Literal["work", "post", "shop"],
		method: Literal["user_id", "comment_id"],
		max_limit: int | None = 200,
	) -> list[str]: ...

	@overload
	def get_comments_detail_new(
		self,
		com_id: int,
		source: Literal["work", "post", "shop"],
		method: Literal["comments"],
		max_limit: int | None = 200,
	) -> list[dict]: ...

	# 获取评论区信息
	def get_comments_detail_new(
		self,
		com_id: int,
		source: Literal["work", "post", "shop"],
		method: Literal["user_id", "comments", "comment_id"] = "user_id",
		max_limit: int | None = 200,
	) -> list[dict] | list[str]:
		"""获取结构化评论数据
		Args:
			com_id: 目标主体ID (作品/帖子/工作室ID)
			source: 数据来源 work=作品 post=帖子 shop=工作室
			method: 返回格式
				user_id -> 用户ID列表
				comment_id -> 评论ID列表
				comments -> 结构化评论数据
			max_limit: 最大获取数量
		Returns:
			根据method参数返回对应格式的数据
		"""
		# 预定义字段映射表
		SOURCE_CONFIG = {
			"work": (self.work_obtain.get_work_comments, "work_id", "reply_user"),
			"post": (self.forum_obtain.get_post_replies_posts, "ids", "user"),
			"shop": (self.shop_obtain.get_shop_discussion, "shop_id", "reply_user"),
		}

		# 验证来源有效性
		if source not in SOURCE_CONFIG:
			raise ValueError(f"不支持的来源类型: {source}，可用选项: {list(SOURCE_CONFIG.keys())}")

		# 获取基础数据
		method_func, id_key, user_field = SOURCE_CONFIG[source]
		comments = method_func(**{id_key: com_id, "limit": max_limit})

		# 定义处理函数
		def _extract_reply_user(reply: dict) -> int:
			"""提取回复用户ID"""
			return reply[user_field]["id"]

		def _generate_replies(comment: dict) -> Generator[dict]:
			"""生成回复数据"""
			if source == "post":
				yield from self.forum_obtain.get_reply_post_comments(post_id=comment["id"], limit=None)
			else:
				yield from comment.get("replies", {}).get("items", [])

		def _process_user_id() -> list[int]:
			"""提取用户ID列表"""
			user_ids = []
			for comment in comments:
				user_ids.append(comment["user"]["id"])
				user_ids.extend(_extract_reply_user(reply) for reply in _generate_replies(comment))
			return self.tool_process.deduplicate(user_ids)

		def _process_comment_id() -> list[str]:
			"""生成评论ID链"""
			comment_ids = []
			for comment in comments:
				comment_ids.append(str(comment["id"]))
				comment_ids.extend(f"{comment['id']}.{reply['id']}" for reply in _generate_replies(comment))
			return self.tool_process.deduplicate(comment_ids)

		def _process_detailed() -> list[dict]:
			"""构建结构化数据"""
			return [
				{
					"user_id": item["user"]["id"],
					"nickname": item["user"]["nickname"],
					"id": item["id"],
					"content": item["content"],
					"created_at": item["created_at"],
					"is_top": item.get("is_top", False),
					"replies": [
						{
							"id": r_item["id"],
							"content": r_item["content"],
							"created_at": r_item["created_at"],
							"user_id": _extract_reply_user(r_item),
							"nickname": r_item[user_field]["nickname"],
						}
						for r_item in _generate_replies(item)
					],
				}
				
				for item in comments
			]

		# 处理方法路由
		method_router = {
			"user_id": _process_user_id,
			"comment_id": _process_comment_id,
			"comments": _process_detailed,
		}

		if method not in method_router:
			raise ValueError(f"不支持的请求方法: {method}，可用选项: {list(method_router.keys())}")

		return method_router[method]()


@decorator.singleton
class Motion(ClassUnion):
	def __init__(self) -> None:
			super().__init__()
			# 配置不同来源的参数
			self.SOURCE_CONFIG = {
				"work": {
					"items": lambda: self.user_obtain.get_user_works_web(self.data.ACCOUNT_DATA.id, limit=None),
					"get_comments": lambda _id: Obtain().get_comments_detail_new(_id, "work", "comments"),
					"delete": self.work_motion.del_comment_work,
					"title_key": "work_name"
				},
				"post": {
					"items": lambda: self.forum_obtain.get_post_mine_all("created", limit=None),
					"get_comments": lambda _id: Obtain().get_comments_detail_new(_id, "post", "comments"),
					"delete": lambda _id, comment_id, **_: self.forum_motion.delete_comment_post_reply(
						comment_id, "comments" if _.get("is_reply") else "replies"),
					"title_key": "title"
				}
			}

	def clear_comments(
			self,
			source: Literal["work", "post"],
			action_type: Literal["ads", "duplicates", "blacklist"],
		) -> bool:
			"""清理评论核心方法
			Args:
				source: 数据来源 work=作品评论 post=帖子回复
				action_type: 处理类型 
					ads=广告评论 
					duplicates=重复刷屏
					blacklist=黑名单用户
			"""
			# 初始化配置参数
			config = self._get_source_config(source)
			params = {
				"ads": self.data.USER_DATA.ads,
				"blacklist": self.data.USER_DATA.black_room,
				"spam_max": self.setting.PARAMETER.spam_del_max,
			}

			# 收集待处理项
			target_lists = defaultdict(list)
			for item in config["items"]():
				self._process_item(item, config, action_type, params, target_lists)

			# 执行删除操作
			return self._execute_deletion(
				target_list=target_lists[action_type],
				delete_handler=config["delete"],
				label={
					"ads": "广告评论",
					"blacklist": "黑名单评论", 
					"duplicates": "刷屏评论"
				}[action_type]
			)

	def _get_source_config(self, source: str) -> dict:
			"""获取来源配置"""
			if source not in self.SOURCE_CONFIG:
				raise ValueError(f"不支持的来源类型: {source}")
			return self.SOURCE_CONFIG[source]

	def _process_item(
			self,
			item: dict,
			config: dict,
			action_type: str,
			params: dict,
			target_lists: defaultdict
		) -> None:
			"""处理单个作品/帖子"""
			item_id = int(item["id"])
			title = item[config["title_key"]]
			comments = config["get_comments"](item_id)

			# 分类型处理逻辑
			if action_type in ("ads", "blacklist"):
				self._find_abnormal_comments(comments, item_id, title, action_type, params, target_lists)
			elif action_type == "duplicates":
				self._find_duplicate_comments(comments, item_id, params, target_lists)

	def _find_abnormal_comments(
		self,
		comments: list,
		item_id: int,
		title: str,
		action_type: str,
		params: dict,
		target_lists: defaultdict
	) -> None:
		"""发现异常评论（广告/黑名单）"""
		for comment in comments:
			if comment.get("is_top"):
				continue  # 跳过置顶内容

			# 处理主评论
			if self._check_condition(comment, action_type, params):
				identifier = f"{item_id}.{comment['id']}:comment"
				# 修正参数顺序：添加action_type参数
				self._log_and_add(
					target_lists=target_lists,
					data=comment,
					identifier=identifier,
					title=title,
					action_type=action_type  # 正确传递action_type
				)

			# 处理回复
			for reply in comment.get("replies", []):
				if self._check_condition(reply, action_type, params):
					identifier = f"{item_id}.{reply['id']}:reply"
					# 修正参数顺序：添加action_type参数和parent_content
					self._log_and_add(
						target_lists=target_lists,
						data=reply,
						identifier=identifier,
						title=title,
						action_type=action_type,
						parent_content=comment["content"]  # 作为最后一个参数
					)

	def _check_condition(self, data: dict, action_type: str, params: dict) -> bool:
			"""检查评论是否符合处理条件"""
			content = data["content"].lower()
			user_id = str(data["user_id"])
			
			if action_type == "ads":
				
				return any(ad in content for ad in params["ads"])
			if action_type == "blacklist":
				return user_id in params["blacklist"]
			return False

	def _log_and_add(
		self,
		target_lists: defaultdict,
		data: dict,
		identifier: str,
		title: str,
		action_type: str,  
		parent_content: str = ""
	) -> None:
		"""记录日志并添加到处理列表"""
		log_template = {
			"ads": "广告{type} [{title}]{parent}：{content}",
			"blacklist": "黑名单{type} [{title}]{parent}：{nickname}"
		}[action_type]
		
		log_message = log_template.format(
			type="回复" if ":reply" in identifier else "评论",
			title=title,
			parent=f" ({parent_content})" if parent_content else "",
			content=data["content"],
			nickname=data["nickname"]
		)
		print(log_message)
		target_lists[action_type].append(identifier)

	def _find_duplicate_comments(
			self,
			comments: list,
			item_id: int,
			params: dict,
			target_lists: defaultdict
		) -> None:
			"""发现重复刷屏评论"""
			content_map = defaultdict(list)
			for comment in comments:
				self._track_comment(comment, item_id, content_map)
				for reply in comment.get("replies", []):
					self._track_comment(reply, item_id, content_map, is_reply=True)

			# 筛选达到阈值的评论
			for (uid, content), ids in content_map.items():
				if len(ids) >= params["spam_max"]:
					print(f"发现刷屏评论：用户{uid} 重复发送：{content} {len(ids)}次")
					target_lists["duplicates"].extend(ids)

	def _track_comment(
			self,
			data: dict,
			item_id: int,
			content_map: defaultdict,
			is_reply: bool = False
		) -> None:
			"""跟踪评论数据"""
			key = (data["user_id"], data["content"].lower())
			identifier = f"{item_id}.{data['id']}:{'reply' if is_reply else 'comment'}"
			content_map[key].append(identifier)

	@decorator.skip_on_error
	def _execute_deletion(
			self,
			target_list: list,
			delete_handler: Callable[[int, int, bool], bool],
			label: str
		) -> bool:
			"""执行删除操作（保留原有注释）
			
			注意：由于编程猫社区接口限制，需要先删除回复再删除主评论，
			通过反转列表实现从后往前删除，避免出现删除父级评论后无法删除子回复的情况
			"""
			if not target_list:
				print(f"未发现{label}")
				return True

			print(f"\n发现以下{label}（共{len(target_list)}条）：")
			for item in reversed(target_list):
				print(f" - {item.split(':')[0]}")

			if input(f"\n确认删除所有{label}？（Y/N）").lower() != "y":
				print("操作已取消")
				return True

			# 从最后一条开始删除（先删回复后删评论）
			for entry in reversed(target_list):
				parts = entry.split(':')[0].split('.')
				item_id, comment_id = map(int, parts)
				is_reply = ":reply" in entry
				
				if not delete_handler(item_id, comment_id, is_reply):
					print(f"删除失败：{entry}")
					return False
				print(f"已删除：{entry}")
			
			return True

	def clear_red_point(self, method: Literal["nemo", "web"] = "web") -> bool:
		"""清除未读消息红点提示
		Args:
			method: 处理模式 
				web - 网页端消息类型
				nemo - 客户端消息类型
		Returns:
			bool: 是否全部清除成功
		"""
		# 配置参数映射表
		METHOD_CONFIG = {
			"web": {
				"endpoint": "/web/message-record",
				"message_types": self.setting.PARAMETER.all_read_type,
				"check_keys": ["count"],  # 对应get_message_counts返回值的结构
			},
			"nemo": {
				"endpoint": "/nemo/v2/user/message/{type}",
				"message_types": [1, 3],  # 1:点赞收藏 3:fork
				"check_keys": ["like_collection_count", "comment_count", "re_create_count", "system_count"],
			}
		}

		# 验证方法有效性
		if method not in METHOD_CONFIG:
			raise ValueError(f"不支持的方法类型: {method}")

		config = METHOD_CONFIG[method]
		page_size = 200
		params = {"limit": page_size, "offset": 0}

		def is_all_cleared(counts: dict) -> bool:
			"""检查是否全部消息已读"""
			if method == "web":
				return all(count["count"] == 0 for count in counts[:3])
			return sum(counts[key] for key in config["check_keys"]) == 0

		def send_batch_requests() -> bool:
			"""批量发送标记已读请求"""
			responses = {}
			for msg_type in config["message_types"]:
				# 构造请求端点
				endpoint = config["endpoint"].format(type=msg_type) if "{" in config["endpoint"] else config["endpoint"]
				
				# 添加类型参数
				request_params = params.copy()
				if method == "web":
					request_params["query_type"] = msg_type

				# 发送请求
				response = self.acquire.send_request(
					endpoint=endpoint,
					method="GET",
					params=request_params
				)
				responses[msg_type] = response.status_code

			return all(code == OK_CODE for code in responses.values())

		try:
			while True:
				# 获取当前未读状态
				current_counts = self.community_obtain.get_message_count(method)
				if is_all_cleared(current_counts):
					return True

				# 批量处理当前页
				if not send_batch_requests():
					return False

				# 更新分页参数
				params["offset"] += page_size

		except Exception as e:
			print(f"清除红点过程中发生异常: {e}")
			return False

	# 给某人作品全点赞
	def like_all_work(self, user_id: str) -> bool:
		works_list = self.user_obtain.get_user_works_web(user_id, limit=None)
		for item in works_list:
			item["id"] = cast("int", item["id"])
			if not self.work_motion.like_work(work_id=item["id"]):
				return False
		return True

	def reply_work(self) -> bool:
		"""自动回复作品/帖子评论"""
		# 合并预处理和数据获取逻辑
		formatted_answers = {
			k: v.format(**self.data.INFO) if isinstance(v, str) else [i.format(**self.data.INFO) for i in v]
			for answer in self.data.USER_DATA.answers
			for k, v in answer.items()
		}
		formatted_replies = [r.format(**self.data.INFO) for r in self.data.USER_DATA.replies]

		# 获取并过滤有效回复（解决set类型问题）
		valid_types = list(VALID_REPLY_TYPES)  # 将set转为list
		new_replies = self.tool_process.filter_items_by_values(
			data=Obtain().get_new_replies(),
			id_path="type",
			values=valid_types,
		)

		for reply in new_replies:
			try:
				# 合并处理逻辑
				content = loads(reply["content"])
				msg = content["message"]
				reply_type = reply["type"]
				
				# 提取评论内容
				comment_text = msg["comment"] if reply_type in {"WORK_COMMENT", "POST_COMMENT"} else msg["reply"]
				
				# 匹配回复内容
				chosen = next(
					(choice(resp) for keyword, resp in formatted_answers.items() 
					if keyword in comment_text),
					choice(formatted_replies)
				)

				# 执行回复（解决source类型问题）
				source_type = cast(Literal['work', 'post'], 
								'work' if reply_type.startswith("WORK") else 'post')
				
				# 获取评论ID（解决find_prefix_suffix参数问题）
				comment_ids = [
					str(item) for item in Obtain().get_comments_detail_new(
						com_id=msg["business_id"],
						source=source_type,
						method="comment_id",
					) if isinstance(item, (int, str))
				]
				target_id = str(msg.get("reply_id", ""))
				
				if reply_type.endswith("_COMMENT"):
					comment_id = int(reply.get("reference_id", msg.get("comment_id", 0)))
					parent_id = 0
				else:
					parent_id = int(reply.get("reference_id", msg.get("replied_id", 0)))
					found = self.tool_routine.find_prefix_suffix(
						text=target_id,  # 添加text参数
						candidates=comment_ids
					)[0]
					comment_id = int(found) if found else 0
				print(f"\n{'='*30} 新回复 {'='*30}")
				print(f"类型: {reply_type}")

				# 提取评论内容
				comment_text = msg["comment"] if reply_type in {"WORK_COMMENT", "POST_COMMENT"} else msg["reply"]
				print(f"提取关键文本: {comment_text}")

				# 匹配回复内容（添加匹配提示）
				matched_keyword = None
				for keyword, resp in formatted_answers.items():
					if keyword in comment_text:
						matched_keyword = keyword
						chosen = choice(resp) if isinstance(resp, list) else resp
						print(f"匹配到关键字「{keyword}」")
						break
				
				if not matched_keyword:
					chosen = choice(formatted_replies)
					print("未匹配关键词，随机选择回复")

				print(f"最终选择回复: 【{chosen}】")

				# 调用API
				params = {
					"work_id": msg["business_id"],
					"comment_id": comment_id,
					"parent_id": parent_id,
					"comment": chosen,
					"return_data": True,
				} if source_type == "work" else {
					"reply_id": comment_id,
					"parent_id": parent_id,
					"content": chosen,
				}
				
				(self.work_motion.reply_work if source_type == "work" else self.forum_motion.reply_comment)(**params)
				print(f"已发送回复到{source_type}，评论ID: {comment_id}")

			except Exception as e:
				print(f"回复处理失败: {e}")
				continue

		return True

	# 工作室常驻置顶
	def top_work(self) -> None:
		detail = self.shop_obtain.get_shops_details()
		description = self.shop_obtain.get_shop_details(detail["work_subject_id"])["description"]
		self.shop_motion.update_shop_details(
			description=description,
			shop_id=detail["id"],
			name=detail["name"],
			preview_url=detail["preview_url"],
		)

	# 查看账户所有信息综合
	def get_account_all_data(self) -> dict[Any, Any]:
		# 创建一个空列表来存储所有字典
		all_data: list[dict] = []
		# 调用每个函数并将结果添加到列表中
		all_data.extend(
			(
				self.user_obtain.get_data_details(),
				self.user_obtain.get_data_level(),
				self.user_obtain.get_data_name(),
				self.user_obtain.get_data_privacy(),
				self.user_obtain.get_data_score(),
				self.user_obtain.get_data_profile("web"),
				self.user_obtain.get_data_tiger(),
				self.edu_obtain.get_data_details(),
			),
		)
		return self.tool_routine.merge_user_data(data_list=all_data)

	# 查看账户状态
	def get_account_status(self) -> str:
		status = self.user_obtain.get_data_details()
		return f"禁言状态{status['voice_forbidden']}, 签订友好条约{status['has_signed']}"



	def handle_report(self, admin_id: int) -> None:
			"""处理举报主入口"""
			# 类型明确的配置字典
			REPORT_CONFIG: dict[Literal["comment", "post", "discussion"], tuple] = {
				"comment": (self.whale_obtain.get_comment_report, "comment_source_object_id", "shop"),
				"post": (self.whale_obtain.get_post_report, "post_id", "forum"),
				"discussion": (self.whale_obtain.get_discussion_report, "post_id", "post")
			}

			for report_type, (fetcher, id_field, source_type) in REPORT_CONFIG.items():
				reports = fetcher(types="ALL" if report_type == "comment" else None, status="TOBEDONE", limit=None)
				for report in reports:
					self._process_report(
						report=report,
						report_type=report_type,  # 类型安全的report_type
						id_field=id_field,
						source_type=cast(Literal["shop", "post", "forum"], source_type),
						admin_id=admin_id
					)

			self.acquire.switch_account(token=self.acquire.token.average, identity="average")

	def _process_report(
			self, 
			report: dict, 
			report_type: Literal["comment", "post", "discussion"],
			id_field: str,
			source_type: Literal["shop", "post", "forum"],
			admin_id: int
		) -> None:
			"""处理单条举报"""
			# 显示基础信息
			print(f"\n{'='*50}")
			print(f"举报ID: {report['id']}")
			print(f"被举报内容: {report.get('content', report.get('title', ''))}")
			print(f"举报原因: {report['reason_content']}")

			while True:
				choice = input("选择操作: D-删除/S-禁言/P-通过/C-详情/F-检查违规/J-跳过: ").upper()
				valid_choices = {"D", "S", "P", "C", "F", "J"}
				
				if choice not in valid_choices:
					print("无效输入，请重新选择")
					continue
					
				if choice == "J":
					break
					
				if choice in {"D", "S", "P"}:
					self._handle_action(
						report=report,
						action=cast(Literal["D", "S", "P"], choice),  # 类型断言
						admin_id=admin_id,
						report_type=report_type
					)
					break
					
				if choice == "C":
					self._show_details(report, id_field, source_type)
					
				elif choice == "F":
					self._auto_check_violations(report, id_field, source_type)
	def _show_details(
			self,
			report: dict,
			id_field: str,
			source_type: Literal["shop", "post", "forum"]
		) -> None:
			"""显示举报详细信息"""
			print(f"\n{'='*30} 详细信息 {'='*30}")
			print(f"违规内容ID: {report[id_field]}")
			
			# 根据来源类型显示不同信息
			if source_type == "shop":
				print(f"工作室链接: https://shequ.codemao.cn/work_shop/{report[id_field]}")
			elif source_type == "post":
				print(f"帖子链接: https://shequ.codemao.cn/community/{report[id_field]}")
			else:
				print(f"论坛板块: {report.get('board_name', '未知')}")

			# 显示用户信息
			user_field = "comment_user" if source_type == "shop" else "post_user"
			print(f"被举报用户: {report[f'{user_field}_nickname']}")
			print(f"用户主页: https://shequ.codemao.cn/user/{report[f'{user_field}_id']}")

			# 显示时间信息
			post_details = self.forum_obtain.get_single_post_details(ids=report[id_field])
			print(f"发布时间: {self.tool_process.format_timestamp(post_details['created_at'])}")
			print(f"{'='*67}")

	def _auto_check_violations(
			self,
			report: dict,
			id_field: str,
			source_type: Literal["shop", "post", "forum"]
		) -> None:
			"""自动检查违规内容"""
			print(f"\n{'='*30} 违规检查 {'='*30}")
			source_id = int(report[id_field])
			
			# 获取相关评论
			comments = Obtain().get_comments_detail_new(
				com_id=source_id,
				source=cast(Literal["work", "post", "shop"], source_type),
				method="comments"
			)

			# 分析违规内容
			violators = defaultdict(list)
			for comment in comments:
				# 广告检测
				if any(ad in comment["content"].lower() for ad in self.data.USER_DATA.ads):
					violators[comment["user"]["id"]].append(comment["id"])
					print(f"⚠️ 发现广告内容：用户{comment['user']['id']} - {comment['content'][:30]}...")
				
				# 刷屏检测
				if len(comment["content"]) < 5:
					print(f"⚠️ 可疑短内容：用户{comment['user']['id']} - {comment['content'][:30]}...")

			# 执行批量举报
			if violators:
				confirm = input(f"发现{len(violators)}个违规用户，是否批量举报？(Y/N) ").upper()
				if confirm == "Y":
					self._batch_report(violators, source_id, source_type)
			else:
				print("✅ 未发现明显违规内容")
			print(f"{'='*67}")
	def _handle_action(
			self,
			report: dict,
			action: Literal["D", "S", "P"],
			admin_id: int,
			report_type: Literal["comment", "post", "discussion"]
		) -> None:
			"""执行处理动作"""
			handler_map: dict[Literal["comment", "post", "discussion"], Callable] = {
				"comment": self.whale_motion.handle_comment_report,
				"post": self.whale_motion.handle_post_report,
				"discussion": self.whale_motion.handle_discussion_report
			}
			
			status_map: dict[Literal["D", "S", "P"], Literal["DELETE", "MUTE_SEVEN_DAYS", "PASS"]] = {
				"D": "DELETE",
				"S": "MUTE_SEVEN_DAYS",
				"P": "PASS"
			}
			
			handler = handler_map[report_type]
			handler(
				report_id=report["id"],
				status=status_map[action],  # 类型安全的status
				admin_id=admin_id
			)

	def _switch_edu_accounts(self, limit: int = 20) -> Generator[tuple[str, str], None, None]:
			"""随机切换教育账号"""
			students = list(self.edu_obtain.get_students(limit=limit))
			while students:
				idx = randint(0, len(students) - 1)
				student = students.pop(idx)
				yield student["username"], self.edu_motion.reset_password(student["id"])["password"]

	def _batch_report(self, violators: dict[int, list[int]], source_id: int, source_type: Literal["forum", "work", "shop"]):
			"""批量举报处理"""
			account_pool = self._switch_edu_accounts(20)
			
			for uid, comment_ids in violators.items():
				for comment_id in comment_ids:
					for _ in range(3):  # 最大重试3次
						try:
							username, pwd = next(account_pool)
							self.community_login.login_password(username, pwd, "edu")
							self.report_work(
								source=cast(Literal["forum", "work", "shop"], source_type),
								target_id=comment_id,
								source_id=source_id,
								reason_id=7
							)
							print(f"举报成功：用户{uid} 评论{comment_id}")
							break
						except StopIteration:
							print("没有更多可用账号")
							return
						except Exception as e:
							print(f"举报失败：{e}")

	def report_work(
		self,
		source: Literal["forum", "work", "shop"],
		target_id: int,
		source_id: int,
		reason_id: Literal[0, 1, 2, 3, 4, 5, 6, 7, 8],
		parent_id: int | None = None,
		description: str = "",
		*,
		is_reply: bool = False,
	) -> bool:
		# 1: 违法违规; 2: 色情暴力
		# 3: 侵犯隐私; 4: 人身攻击
		# 5: 引战; 6: 垃圾广告
		# 7: 无意义刷屏; 8: 不良信息
		# 0: 自定义

		reason_content = self.community_obtain.get_report_reason()["items"][reason_id]["content"]
		match source:
			case "work":
				return self.work_motion.report_comment_work(work_id=target_id, comment_id=source_id, reason=reason_content)
			case "forum":
				source_ = "COMMENT" if is_reply else "REPLY"
				return self.forum_motion.report_reply_or_comment(comment_id=target_id, reason_id=reason_id, description=description, source=source_, return_data=False)
			case "shop":
				if is_reply:
					parent_id = cast("int", parent_id)
					return self.shop_motion.report_comment(
						comment_id=target_id,
						reason_content=reason_content,
						reason_id=reason_id,
						reporter_id=int(self.data.ACCOUNT_DATA.id),
						comment_parent_id=parent_id,
						description=description,
					)
				return self.shop_motion.report_comment(
					comment_id=target_id,
					reason_content=reason_content,
					reason_id=reason_id,
					reporter_id=int(self.data.ACCOUNT_DATA.id),
					description=description,
				)


# "POST_COMMENT",
# "POST_COMMENT_DELETE_FEEDBACK",
# "POST_DELETE_FEEDBACK",
# "POST_DISCUSSION_LIKED",
# "POST_REPLY",
# "POST_REPLY_AUTHOR",
# "POST_REPLY_REPLY",
# "POST_REPLY_REPLY_AUTHOR",
# "POST_REPLY_REPLY_FEEDBACK",
# "WORK_COMMENT",路人a评论{user}的作品
# "WORK_DISCUSSION_LIKED",
# "WORK_LIKE",
# "WORK_REPLY",路人a评论{user}在某个作品的评论
# "WORK_REPLY_AUTHOR",路人a回复{user}作品下路人b的某条评论
# "WORK_REPLY_REPLY",路人a回复{user}作品下路人b/a的评论下{user}的回复
# "WORK_REPLY_REPLY_AUTHOR",路人a回复{user}作品下路人b/a对某条评论的回复
# "WORK_REPLY_REPLY_FEEDBACK",路人a回复{user}在某个作品下发布的评论的路人b/a的回复
# "WORK_SHOP_REPL"
# "WORK_SHOP_USER_LEAVE",
