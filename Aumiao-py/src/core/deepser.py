import json
import random
import string
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any, ClassVar
from urllib.parse import quote

from websocket import WebSocketApp


# ==================== 配置管理 ====================
class CodeMaoConfig:
	"""配置管理类"""

	# WebSocket 配置
	WS_BASE_URL = "wss://cr-aichat.codemao.cn/aichat/"
	WS_PARAMS: ClassVar = {
		"stag": 6,
		"rf": "",
		"source_label": "kn",
		"question_type": "undefined",
		"EIO": 3,
		"transport": "websocket",
	}
	# 请求头配置
	HEADERS: ClassVar = {
		"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0",
		"Origin": "https://kn.codemao.cn",
		"Accept-Encoding": "gzip, deflate, br, zstd",
		"Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
		"Cache-Control": "no-cache",
		"Pragma": "no-cache",
	}
	# SSL 配置
	SSL_OPTIONS: ClassVar = {"cert_reqs": 0}
	# 超时配置
	CONNECT_TIMEOUT = 10
	RESPONSE_START_TIMEOUT = 10
	RESPONSE_TIMEOUT = 60
	# 其他配置
	PING_INTERVAL = 30
	PING_TIMEOUT = 10

	@classmethod
	def build_websocket_url(cls, token: str) -> str:
		"""构建 WebSocket URL"""
		params = {**cls.WS_PARAMS, "token": token}
		query_string = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
		return f"{cls.WS_BASE_URL}?{query_string}"


# ==================== 事件处理器 ====================
class EventHandler:
	"""事件处理器基类"""

	def __init__(self, *, verbose: bool = False) -> None:
		self.verbose = verbose
		self._callbacks = []

	def add_callback(self, callback: Callable[[str, str], None]) -> None:
		"""添加回调函数"""
		self._callbacks.append(callback)

	def remove_callback(self, callback: Callable[[str, str], None]) -> None:
		"""移除回调函数"""
		if callback in self._callbacks:
			self._callbacks.remove(callback)

	def emit_event(self, content: str, event_type: str) -> None:
		"""触发事件"""
		for callback in self._callbacks:
			try:
				callback(content, event_type)
			except Exception as e:
				self.log(f"回调错误: {e}")

	def handle_event(self, event_name: str, payload: dict[str, Any]) -> None:
		"""处理事件 - 由子类实现"""
		msg = "子类必须实现 handle_event 方法"
		raise NotImplementedError(msg)

	def log(self, message: str) -> None:
		"""日志输出"""
		if self.verbose:
			print(message)


# ==================== WebSocket 连接管理 ====================
class WebSocketManager:
	"""WebSocket 连接管理器"""

	def __init__(self, token: str, event_handler: EventHandler) -> None:
		self.token = token
		self.handler = event_handler
		self.ws: WebSocketApp | None = None
		self.connected = False

	def connect(self) -> bool:
		"""连接到 WebSocket 服务器"""
		if not self.token:
			self.handler.log("错误: 未提供 token")
			return False
		self.handler.log("连接到服务器...")
		self.ws = WebSocketApp(
			CodeMaoConfig.build_websocket_url(self.token),
			on_message=self._on_message,
			on_error=self._on_error,
			on_close=self._on_close,
			on_open=self._on_open,
			header=CodeMaoConfig.HEADERS,
		)

		def run_websocket() -> None:
			if self.ws:
				self.ws.run_forever(
					sslopt=CodeMaoConfig.SSL_OPTIONS,
					ping_interval=CodeMaoConfig.PING_INTERVAL,
					ping_timeout=CodeMaoConfig.PING_TIMEOUT,
				)

		thread = threading.Thread(target=run_websocket, daemon=True)
		thread.start()
		# 等待连接建立
		timeout = CodeMaoConfig.CONNECT_TIMEOUT
		start_time = time.time()
		while not self.connected and time.time() - start_time < timeout:
			time.sleep(0.1)
		return self.connected

	def _on_message(self, _ws: object, message: str) -> None:
		"""WebSocket 消息处理"""
		try:
			if message.startswith("0"):  # 连接确认
				self.handler.log("连接建立")
			elif message.startswith("3"):  # ping
				if self.ws:
					self.ws.send("2")  # pong
			elif message.startswith("40"):  # 连接成功
				self.handler.log("Socket.IO 连接成功")
			elif message.startswith("42"):  # 事件消息
				event_data = json.loads(message[2:])
				self.handler.handle_event(event_data[0], event_data[1] if len(event_data) > 1 else {})
		except Exception as e:
			self.handler.log(f"消息处理错误: {e}")
			self.handler.emit_event(str(e), "error")

	def _on_error(self, _ws: object, error: object) -> None:
		"""WebSocket 错误处理"""
		error_msg = f"WebSocket 错误: {error}"
		self.handler.log(error_msg)
		self.handler.emit_event(error_msg, "error")

	def _on_close(self, _ws: object, _close_status_code: int | None = None, _close_msg: str | None = None) -> None:
		"""WebSocket 关闭处理"""
		self.handler.log("连接关闭")
		self.connected = False

	def _on_open(self, ws: WebSocketApp) -> None:
		"""WebSocket 打开处理"""
		self.handler.log("WebSocket 连接建立")
		self.connected = True
		ws.send("40")

		def send_join() -> None:
			time.sleep(1)
			ws.send('42 ["join"]')

		threading.Thread(target=send_join, daemon=True).start()

	def send(self, message: str) -> None:
		"""发送消息"""
		if self.ws and self.connected:
			self.ws.send(message)

	def close(self) -> None:
		"""关闭连接"""
		if self.ws:
			self.ws.close()
		self.connected = False


# ==================== AI 聊天核心实现 ====================
class CodeMaoAICore(EventHandler):
	"""CodeMao AI 聊天核心实现"""

	def __init__(self, token: str, *, verbose: bool = False) -> None:
		super().__init__(verbose=verbose)
		self.token = token
		self.ws_manager = WebSocketManager(token, self)
		# 状态管理
		self.session_id: str | None = None
		self.search_session: str | None = None
		self.user_id: str | None = None
		self.current_response = ""
		self.is_receiving_response = False
		# 数据存储
		self._user_info: dict[str, Any] = {}
		self._conversation_history: list[dict[str, str]] = []
		self._current_conversation_id = self._generate_session_id()

	@staticmethod
	def _generate_session_id() -> str:
		"""生成会话 ID"""
		return "".join(random.choices(string.ascii_lowercase + string.digits, k=13))

	def handle_event(self, event_name: str, payload: dict[str, Any]) -> None:
		"""处理事件"""
		handlers = {
			"on_connect_ack": self._handle_connect_ack,
			"join_ack": self._handle_join_ack,
			"preset_chat_message_ack": lambda _: self.log("预设消息确认"),
			"get_text2Img_remaining_times_ack": self._handle_remaining_times,
			"chat_ack": self._handle_chat_ack,
		}
		if handler := handlers.get(event_name):
			handler(payload)

	def _handle_connect_ack(self, payload: dict[str, Any]) -> None:
		"""处理连接确认"""
		if payload.get("code") == 1:
			self._user_info.update(payload.get("data", {}))
			self.log(f"连接确认 - 剩余对话次数: {self._user_info.get('chat_count', ' 未知 ')}")

	def _handle_join_ack(self, payload: dict[str, Any]) -> None:
		"""处理加入确认"""
		if payload.get("code") == 1:
			data = payload.get("data", {})
			self.user_id = data.get("user_id")
			self.search_session = data.get("search_session")
			self.log(f"加入成功 - 用户 ID: {self.user_id}, 会话: {self.search_session}")
			self._send_preset_messages()

	def _handle_remaining_times(self, payload: dict[str, Any]) -> None:
		"""处理剩余次数查询"""
		if payload.get("code") == 1:
			data = payload.get("data", {})
			self._user_info["remaining_image_times"] = data.get("remaining_times")
			self.log(f"剩余图片生成次数: {data.get('remaining_times', ' 未知 ')}")

	def _handle_chat_ack(self, payload: dict[str, Any]) -> None:
		"""处理聊天回复"""
		if payload.get("code") != 1:
			return
		data = payload.get("data", {})
		content_type = data.get("content_type")
		content = data.get("content", "")
		if content_type == "stream_output_begin":
			self.session_id = data.get("session_id")
			self.current_response = ""
			self.is_receiving_response = True
			self.emit_event("", "start")
		elif content_type == "stream_output_content":
			if self.is_receiving_response:
				self.current_response += content
				self.emit_event(content, "text")
		elif content_type == "stream_output_end":
			self.is_receiving_response = False
			self.emit_event(self.current_response, "end")
			# 将 AI 回复添加到对话历史
			if self.current_response:
				self._conversation_history.append({"role": "assistant", "content": self.current_response})

	def _send_preset_messages(self) -> None:
		"""发送预设消息"""
		if self.ws_manager.connected:
			self.ws_manager.send('42 ["preset_chat_message",{"turn_count":5,"system_content_enum":"default"}]')
			self.ws_manager.send('42 ["get_text2Img_remaining_times"]')

	def connect(self) -> bool:
		"""连接到服务器"""
		return self.ws_manager.connect()

	def send_message(self, message: str, *, include_history: bool = True) -> bool:
		"""发送聊天消息"""
		if not self.ws_manager.connected:
			self.log("错误: 未连接到服务器")
			return False
		if self.is_receiving_response:
			self.log("请等待上一条回复完成...")
			return False
		# 添加用户消息到历史记录
		self._conversation_history.append({"role": "user", "content": message})
		# 构建消息数据
		messages = (
			self._conversation_history
			if include_history and len(self._conversation_history) > 1
			else [
				{"role": "user", "content": message},
			]
		)
		chat_data = {
			"session_id": self._current_conversation_id,
			"messages": messages,
			"chat_type": "chat_v3",
			"msg_channel": 0,
		}
		message_str = f'42 ["chat",{json.dumps(chat_data, ensure_ascii=False)}]'
		self.ws_manager.send(message_str)
		self.log(f"消息已发送: {message}")
		return True

	def wait_for_response_start(self, timeout: int = CodeMaoConfig.RESPONSE_START_TIMEOUT) -> bool:
		"""等待 AI 开始回复"""
		start_time = time.time()
		while not self.is_receiving_response and time.time() - start_time < timeout:
			time.sleep(0.1)
		return self.is_receiving_response

	def wait_for_response(self, timeout: int = CodeMaoConfig.RESPONSE_TIMEOUT) -> bool:
		"""等待当前回复完成"""
		start_time = time.time()
		while self.is_receiving_response and time.time() - start_time < timeout:
			time.sleep(0.1)
		return not self.is_receiving_response

	def send_and_wait(self, message: str, *, include_history: bool = True, response_timeout: int = CodeMaoConfig.RESPONSE_TIMEOUT) -> bool:
		"""发送消息并等待回复完成"""
		if not self.send_message(message=message, include_history=include_history):
			return False
		# 等待 AI 开始回复
		if not self.wait_for_response_start():
			self.log("AI 未开始回复")
			return False
		# 等待回复完成
		return self.wait_for_response(timeout=response_timeout)

	def get_user_info(self) -> dict[str, Any]:
		"""获取用户信息"""
		return {"user_id": self.user_id, **self._user_info}

	def new_conversation(self) -> None:
		"""创建新对话"""
		self._conversation_history.clear()
		self._current_conversation_id = self._generate_session_id()
		self.log("新对话已创建")

	def get_conversation_history(self) -> list[dict[str, str]]:
		"""获取当前对话历史"""
		return self._conversation_history.copy()

	def get_conversation_count(self) -> int:
		"""获取当前对话轮数"""
		return len([msg for msg in self._conversation_history if msg["role"] == "user"])

	def close(self) -> None:
		"""关闭连接"""
		self.ws_manager.close()


# ==================== 高级接口类 ====================
class CodeMaoAIChat:
	"""CodeMao AI 聊天客户端 - 高级接口"""

	def __init__(self, token: str, *, verbose: bool = False) -> None:
		self._core = CodeMaoAICore(token, verbose=verbose)

	def connect(self) -> bool:
		"""连接到服务器"""
		return self._core.connect()

	def send_message(self, message: str, *, include_history: bool = True) -> bool:
		"""发送聊天消息"""
		return self._core.send_message(message, include_history=include_history)

	def send_and_wait(self, message: str, *, include_history: bool = True, response_timeout: int = CodeMaoConfig.RESPONSE_TIMEOUT) -> bool:
		"""发送消息并等待回复完成"""
		return self._core.send_and_wait(message, include_history=include_history, response_timeout=response_timeout)

	def wait_for_response_start(self, timeout: int = CodeMaoConfig.RESPONSE_START_TIMEOUT) -> bool:
		return self._core.wait_for_response_start(timeout)

	def wait_for_response(self, timeout: int = CodeMaoConfig.RESPONSE_TIMEOUT) -> bool:
		return self._core.wait_for_response(timeout)

	def add_stream_callback(self, callback: Callable[[str, str], None]) -> None:
		"""添加流式回调函数"""
		self._core.add_callback(callback)

	def remove_stream_callback(self, callback: Callable[[str, str], None]) -> None:
		"""移除流式回调函数"""
		self._core.remove_callback(callback)

	def get_user_info(self) -> dict[str, Any]:
		"""获取用户信息"""
		return self._core.get_user_info()

	def new_conversation(self) -> None:
		"""创建新对话"""
		self._core.new_conversation()

	def get_conversation_history(self) -> list[dict[str, str]]:
		"""获取当前对话历史"""
		return self._core.get_conversation_history()

	def get_conversation_count(self) -> int:
		"""获取当前对话轮数"""
		return self._core.get_conversation_count()

	def close(self) -> None:
		"""关闭连接"""
		self._core.close()


# ==================== 工具类 ====================
class CodeMaoTool:
	"""工具类 - 提供便捷的聊天方法"""

	@staticmethod
	def stream_chat(token: str, message: str, timeout: int = 60) -> str:
		"""直接流式打印 AI 回复的便捷函数"""
		client = CodeMaoAIChat(token=token, verbose=False)
		full_response = []

		def stream_handler(content: str, event_type: str) -> None:
			if event_type == "text":
				print(content, end="", flush=True)
				full_response.append(content)
			elif event_type == "end":
				full_response.append(content)
				print()

		client.add_stream_callback(stream_handler)
		try:
			if client.connect():
				time.sleep(2)
				client.send_and_wait(message, include_history=False, response_timeout=timeout)
			else:
				print("连接失败")
		finally:
			client.close()
		return "".join(full_response)

	@staticmethod
	def create_chat_session(token: str) -> CodeMaoAIChat:
		"""创建支持连续对话的聊天会话"""
		client = CodeMaoAIChat(token=token, verbose=False)
		if client.connect():
			time.sleep(2)
			return client
		msg = "连接失败"
		raise ConnectionError(msg)

	@staticmethod
	def interactive_chat(token: str) -> None:
		"""交互式聊天会话"""
		client = CodeMaoTool.create_chat_session(token)

		def stream_handler(content: str, event_type: str) -> None:
			if event_type == "text":
				print(content, end="", flush=True)
			elif event_type == "end":
				print()

		client.add_stream_callback(stream_handler)
		print("=== CodeMao AI 聊天 ===")
		print("输入消息开始聊天")
		print("输入 '/new' 创建新对话")
		print("输入 '/history' 查看对话历史")
		print("输入 '/quit' 退出")
		print("=" * 20)
		try:
			while True:
				user_input = input("\n 你:").strip()
				if not user_input:
					continue
				if user_input.lower() in {"/quit", "/exit", "退出"}:
					break
				if user_input.lower() == "/new":
					client.new_conversation()
					print("已创建新对话")
					continue
				if user_input.lower() == "/history":
					history = client.get_conversation_history()
					print(f"对话历史 ({client.get_conversation_count()} 轮):")
					for i, msg in enumerate(history[-6:], 1):
						role = "你" if msg["role"] == "user" else "AI"
						content_preview = msg["content"][:50] + "..." if len(msg["content"]) > 50 else msg["content"]
						print(f"{i}. {role}: {content_preview}")
					continue
				print("AI:", end="", flush=True)
				if not client.send_and_wait(user_input, response_timeout=60):
					print("\n 回复超时或失败")
		except KeyboardInterrupt:
			print("\n\n 聊天结束")
		finally:
			client.close()

	@staticmethod
	def get_user_quota(token: str) -> dict[str, Any]:
		"""快速获取用户配额信息"""
		client = CodeMaoAIChat(token=token, verbose=False)
		try:
			if client.connect():
				time.sleep(3)
				return client.get_user_info()
			return {"error": "连接失败"}
		finally:
			client.close()


# ==================== 多 token 管理 ====================
class CodeMaoAIClient:
	"""CodeMao AI 聊天客户端 - 多 token 管理版本"""

	def __init__(self, tokens: list[str], *, verbose: bool = False) -> None:
		self.tokens = tokens
		self.current_token_index = 0
		self.verbose = verbose
		self._clients: dict[str, CodeMaoAIChat] = {}

	def _get_current_token(self) -> str:
		"""获取当前 token"""
		return self.tokens[self.current_token_index]

	def _switch_to_next_token(self) -> bool:
		"""切换到下一个 token"""
		if len(self.tokens) <= 1:
			return False
		old_index = self.current_token_index
		self.current_token_index = (self.current_token_index + 1) % len(self.tokens)
		if self.verbose:
			print(f"Token 切换: 从索引 {old_index} 切换到 {self.current_token_index}")
		return True

	def _get_or_create_client(self, token: str) -> CodeMaoAIChat:
		"""获取或创建客户端实例"""
		if token not in self._clients:
			self._clients[token] = CodeMaoAIChat(token, verbose=self.verbose)
		return self._clients[token]

	def _check_token_quota(self, client: CodeMaoAIChat) -> bool:
		"""检查 token 配额"""
		try:
			user_info = client.get_user_info()
			chat_count = user_info.get("chat_count", 0)
			if self.verbose:
				print(f"当前 token 剩余对话次数: {chat_count}")
			return chat_count >= 2  # 剩余次数大于等于 2 次认为充足  # noqa: TRY300
		except Exception as e:
			if self.verbose:
				print(f"检查配额失败: {e}")
			return True  # 如果检查失败, 继续使用当前 token

	def stream_chat_with_prompt(self, message: str, prompt: str = "", timeout: int = 60) -> Iterator[str]:
		max_retries = len(self.tokens)
		for retry in range(max_retries):
			current_token = self._get_current_token()
			if self.verbose:
				print(f"尝试使用 token 索引 {self.current_token_index} (尝试 {retry + 1}/{max_retries})")
			client = self._get_or_create_client(current_token)
			try:
				if not client.connect():
					if self.verbose:
						print(f"Token {self.current_token_index} 连接失败")
					self._switch_to_next_token()
					continue
				time.sleep(2)
				# 检查配额
				if not self._check_token_quota(client):
					if self.verbose:
						print(f"Token {self.current_token_index} 配额不足, 尝试切换")
					self._switch_to_next_token()
					continue
				# 发送提示词
				if prompt:
					if self.verbose:
						print("发送系统提示词...")
					client.new_conversation()
					if not client.send_and_wait(prompt, include_history=False, response_timeout=timeout):
						if self.verbose:
							print("提示词发送失败")
						self._switch_to_next_token()
						continue
				# 发送用户消息并流式返回
				yield from self._stream_user_message(client, message, timeout)
			except Exception as e:
				if self.verbose:
					print(f"Token {self.current_token_index} 处理失败: {e}")
				self._switch_to_next_token()
				continue
			else:
				return
			finally:
				client.close()
		yield f"错误: 所有 token 都尝试失败, 共尝试了 {max_retries} 次"

	def _stream_user_message(self, client: CodeMaoAIChat, message: str, timeout: int) -> Iterator[str]:
		full_response = []
		response_complete = threading.Event()

		def stream_handler(content: str, event_type: str) -> None:
			if event_type == "text":
				full_response.append(content)
			elif event_type == "end":
				response_complete.set()
			elif event_type == "error":
				if self.verbose:
					print(f"流式输出错误: {content}")
				response_complete.set()

		client.add_stream_callback(stream_handler)
		if not client.send_message(message, include_history=True):
			yield "错误: 发送消息失败"
			return
		if not client.wait_for_response_start(timeout=10):
			yield "错误: AI 未开始回复"
			return
		# 流式返回内容
		start_time = time.time()
		last_content_length = 0
		while not response_complete.is_set() and (time.time() - start_time) < timeout:
			current_content = "".join(full_response)
			if len(current_content) > last_content_length:
				new_content = current_content[last_content_length:]
				yield new_content
				last_content_length = len(current_content)
			time.sleep(0.1)
		# 返回剩余内容
		final_content = "".join(full_response)
		if len(final_content) > last_content_length:
			yield final_content[last_content_length:]
		client.remove_stream_callback(stream_handler)

	def print_stream_response(self, message: str, prompt: str = "", timeout: int = 60) -> str:
		"""打印流式回复的便捷方法"""
		full_response = []
		print("AI:", end="", flush=True)
		for chunk in self.stream_chat_with_prompt(message, prompt, timeout):
			print(chunk, end="", flush=True)
			full_response.append(chunk)
		print()
		return "".join(full_response)

	def batch_check_quotas(self) -> dict[str, Any]:
		"""批量检查所有 token 的配额"""
		quotas = {}
		for i, token in enumerate(self.tokens):
			try:
				client = CodeMaoAIChat(token, verbose=False)
				if client.connect():
					time.sleep(2)
					user_info = client.get_user_info()
					quotas[f"token_{i}"] = {
						"chat_count": user_info.get("chat_count", "未知"),
						"user_id": user_info.get("user_id", "未知"),
						"remaining_image_times": user_info.get("remaining_image_times", "未知"),
					}
				else:
					quotas[f"token_{i}"] = {"error": "连接失败"}
				client.close()
			except Exception as e:
				quotas[f"token_{i}"] = {"error": str(e)}
		return quotas
