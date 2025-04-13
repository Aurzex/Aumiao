from src.utils import acquire

version = "2024.7.14"

HEADERS = acquire.CodeMaoClient().headers


class Login:
	# 初始化Login类,创建一个CodeMaoClient对象
	def __init__(self) -> None:
		self.acquire = acquire.CodeMaoClient()

	# 登录函数,接收手机号和密码,返回登录结果
	def login(self, phonenum: int, password: str) -> dict:
		# 构造请求数据
		data = {"phonenum": phonenum, "password": password}
		# 发送请求
		response = self.acquire.send_request(endpoint="https://x.chatmindai.net/api/user/login", method="POST", payload=data)
		# 返回响应结果
		return response.json()

	# 更新token函数,接收token,更新全局变量HEADERS中的Authorization字段
	def update_token(self, token: str) -> None:
		global HEADERS  # noqa: PLW0602
		HEADERS["Authorization"] = f"Bearer {token}"


class User:
	# 初始化User类,创建一个CodeMaoClient对象
	def __init__(self) -> None:
		self.acquire = acquire.CodeMaoClient()

	# 获取用户余额
	def get_balance(self) -> dict:
		# 发送GET请求,获取用户余额
		response = self.acquire.send_request(
			endpoint="https://x.chatmindai.net/api/apiCount/query",
			method="GET",
			headers=HEADERS,
		)
		# 返回响应的JSON数据
		return response.json()

	# 获取用户详细信息
	def get_details(self) -> dict:
		# 发送POST请求,获取用户详细信息
		response = self.acquire.send_request(
			endpoint="https://x.chatmindai.net/api/user/getUserSelfBigData",
			method="POST",
			payload={},
			headers=HEADERS,
		)
		# 返回响应的JSON数据
		return response.json()


class Explore:
	# 初始化Explore类,创建一个CodeMaoClient对象
	def __init__(self) -> None:
		self.acquire = acquire.CodeMaoClient()

	# 获取模型列表
	def get_models(
		self,
		page: int = 1,
		limit: int = 6,
		category: str = "recommend",
		originpage: str = "",
		searchValue: str = "",  # noqa: N803
	) -> dict:
		# 如果originpage不为空,则使用originpage,否则使用category
		originpage = originpage if originpage != "" else category
		# 构造请求数据
		data = {
			"pageIndex": page,
			"pageSize": limit,
			"data": {
				"categoryName": category,
				"orderType": originpage,
				"searchValue": searchValue,
			},
		}
		# 发送请求
		response = self.acquire.send_request(
			endpoint="https://x.chatmindai.net/api/model/query",
			method="POST",
			payload=data,
			headers=HEADERS,
		)
		# 返回响应数据
		return response.json()

	# 获取排行榜
	def get_rank(self, method: str) -> dict:
		# 根据method参数,设置不同的url
		if method == "user":
			url = "https://x.chatmindai.net/api/market/userRank"

		elif method == "model":
			url = "https://x.chatmindai.net/api/market/modelRank"
		elif method == "today":
			url = "https://x.chatmindai.net/api/market/modelHeatAddRank"
		else:
			url = ""

		# 发送请求
		response = self.acquire.send_request(endpoint=url, method="POST", payload={}, headers=HEADERS)
		# 返回响应数据
		return response.json()


class Chat:
	# 初始化Chat类,创建一个CodeMaoClient对象
	def __init__(self) -> None:
		self.acquire = acquire.CodeMaoClient()

	# 获取聊天记录
	def get_chats(self) -> dict:
		# 发送GET请求,获取聊天记录
		response = self.acquire.send_request(
			endpoint="https://x.chatmindai.net/api/chat/queryChats",
			method="GET",
			headers=HEADERS,
		)
		return response.json()

	# 获取聊天历史记录
	def get_chat_history(self, ids: str, page: int = 1, limit: int = 15) -> dict:
		# 构造请求数据
		data = {
			"data": {"chatid": ids},
			"pageIndex": page,
			"pageSize": limit,
		}

		# 发送POST请求,获取聊天历史记录
		response = self.acquire.send_request(
			endpoint="https://x.chatmindai.net/api/chat/queryPagesChatItems",
			method="POST",
			payload=data,
			headers=HEADERS,
		)
		return response.json()

	# 发送聊天消息
	def chat(self, chatid: str, modelid: str, message: str, context_analyse: int = 1) -> dict:
		# context_analyse为上下文分析,开启为1,关闭为0
		data = {
			"message": message,
			"chatid": chatid,
			"roleid": modelid,
			"isContextEnabled": context_analyse,
		}

		# 发送POST请求,发送聊天消息
		response = self.acquire.send_request(
			endpoint="https://x.chatmindai.net/api/chat-process",
			method="POST",
			payload=data,
			headers=HEADERS,
		)
		return response.json()

	# 保存聊天记录
	def save_chat(self) -> dict:
		# 构造请求数据
		data = {
			"chatid": "",  # ai回答
			"humanid": "",  # 随机生成: p938bndy9lvueh5fok61721280190544
			"assistantid": "",  # 随机生成: fiz55pci3fobe7g00j91721280158062
			"chattitle": "",  # 默认为首次对话prompt
			"prompt": "",  # 人类提问内容
			"answer": "",  # 机器人回答
			"chattime": "2024-07-17 16:51:02",  # 时间
			"humantime": "2024-07-17 16:50:58",  # 时间
			"assistanttime": "2024-07-17 16:51:02",  # 时间
			"model": "qwen2-72B-Instruct",  # 模型
			"questionList": [],  # 未知
			"roleAvatar": "https://cravatar.cn/avatar/ef166b47449cc7e4e71cec1a2f826a70?s=200&d=mp",
			# ai头像可以随便上传
			"roleId": "bmi5aruzldsb1za2m5d1718161196283",  # 每个角色被赋予唯一id
			"sensitive": False,  # 未知
		}
		# 发送POST请求,保存聊天记录
		response = self.acquire.send_request(
			endpoint="https://x.chatmindai.net/api/chat/saveConversation",
			method="POST",
			payload=data,
			headers=HEADERS,
		)
		return response.json()


class Model:
	# 初始化函数,创建一个CodeMaoClient对象
	def __init__(self) -> None:
		self.acquire = acquire.CodeMaoClient()

	# 根据id获取模型详情
	def get_model_details(self, ids: str) -> dict:
		# 发送请求,获取模型详情
		response = self.acquire.send_request(
			endpoint="https://x.chatmindai.net/api/model/getModelDetailsInfo",
			method="POST",
			payload={"roleId": ids},
			headers=HEADERS,
		)
		# 返回响应的json数据
		return response.json()
