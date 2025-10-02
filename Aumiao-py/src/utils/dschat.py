import json
import random
import ssl
import string
import threading
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

from websocket import WebSocketApp


class CodeMaoAIChat:
	"""
	CodeMao AI Chat Client
	A Python client for interacting with CodeMao AI chat service via WebSocket.
	Args:
		token (str): Authentication token
		verbose (bool, optional): Whether to show detailed logs. Defaults to True.
	"""

	def __init__(self, token: str, *, verbose: bool = False) -> None:
		self.ws: WebSocketApp | None = None
		self.token = token
		self.connected = False
		self.session_id: str | None = None
		self.search_session: str | None = None
		self.user_id: str | None = None
		self.current_response = ""
		self.is_receiving_response = False
		self.verbose = verbose
		self._stream_callbacks: list[Callable[[str, str], None]] = []
		# 用户信息缓存
		self._user_info: dict[str, Any] = {}
		# 对话历史管理
		self._conversation_history: list[dict[str, str]] = []
		self._current_conversation_id: str = self._generate_session_id()

	def _log(self, message: str) -> None:
		"""Log output - only in verbose mode"""
		if self.verbose:
			print(message)

	def add_stream_callback(self, callback: Callable[[str, str], None]) -> None:
		"""
		Add stream callback function
		Args:
			callback: Callback function that receives two parameters:
				- content: the text content
				- event_type: 'start', 'text', 'end', or 'error'
		"""
		self._stream_callbacks.append(callback)

	def remove_stream_callback(self, callback: Callable[[str, str], None]) -> None:
		"""Remove stream callback function"""
		if callback in self._stream_callbacks:
			self._stream_callbacks.remove(callback)

	def _emit_stream_event(self, content: str, event_type: str) -> None:
		"""Emit stream event to all callbacks"""
		for callback in self._stream_callbacks:
			try:
				callback(content, event_type)
			except Exception as e:
				self._log(f"Callback error: {e}")

	def _handle_event(self, event_name: str, payload: dict[str, Any]) -> None:
		"""Handle specific events"""
		event_handlers: dict[str, Callable[[dict[str, Any]], None]] = {
			"on_connect_ack": self._handle_connect_ack,
			"join_ack": self._handle_join_ack,
			"preset_chat_message_ack": lambda _: self._log("Preset message confirmed"),
			"get_text2Img_remaining_times_ack": self._handle_remaining_times,
			"chat_ack": self._handle_chat_ack,
		}
		handler = event_handlers.get(event_name)
		if handler:
			handler(payload)

	def _handle_connect_ack(self, payload: dict[str, Any]) -> None:
		"""Handle connection acknowledgment event"""
		if payload.get("code") == 1:
			data = payload.get("data", {})
			self._user_info.update(data)
			self._log(f"Connection confirmed - Remaining chat count: {data.get('chat_count', 'Unknown')}")

	def _handle_join_ack(self, payload: dict[str, Any]) -> None:
		"""Handle join acknowledgment event"""
		if payload.get("code") == 1:
			data = payload.get("data", {})
			self.user_id = data.get("user_id")
			self.search_session = data.get("search_session")
			self._log(f"Join successful - User ID: {self.user_id}, Session: {self.search_session}")
			self._send_preset_messages()

	def _handle_remaining_times(self, payload: dict[str, Any]) -> None:
		"""Handle remaining times query"""
		if payload.get("code") == 1:
			data = payload.get("data", {})
			self._user_info.update({"remaining_image_times": data.get("remaining_times")})
			self._log(f"Remaining image generation times: {data.get('remaining_times', 'Unknown')}")

	def _handle_chat_ack(self, payload: dict[str, Any]) -> None:
		"""Handle chat reply event"""
		code = payload.get("code")
		data = payload.get("data", {})
		if code == 1:
			content_type = data.get("content_type")
			content = data.get("content", "")
			handlers: dict[str, Callable[[dict[str, Any], str], None]] = {
				"stream_output_begin": self._handle_stream_begin,
				"stream_output_content": self._handle_stream_content,
				"stream_output_end": self._handle_stream_end,
			}
			handler = handlers.get(content_type)
			if handler:
				handler(data, content)

	def _handle_stream_begin(self, data: dict[str, Any], _content: str) -> None:
		"""Handle stream output start"""
		self.session_id = data.get("session_id")
		self.current_response = ""
		self.is_receiving_response = True
		self._emit_stream_event("", "start")

	def _handle_stream_content(self, _data: dict[str, Any], content: str) -> None:
		"""Handle stream output content"""
		if self.is_receiving_response:
			self.current_response += content
			self._emit_stream_event(content, "text")

	def _handle_stream_end(self, _data: dict[str, Any], _content: str) -> None:
		"""Handle stream output end"""
		self.is_receiving_response = False
		self._emit_stream_event(self.current_response, "end")
		# 将AI回复添加到对话历史
		if self.current_response:
			self._conversation_history.append({"role": "assistant", "content": self.current_response})

	def on_message(self, _ws: object, message: str) -> None:
		"""Handle received messages"""
		try:
			if message.startswith("0"):  # Connection confirmation
				self._log("Connection established")
				data = json.loads(message[1:])
				self._log(f"Session ID: {data.get('sid')}")
			elif message.startswith("3"):  # ping
				if self.ws:
					self.ws.send("2")  # pong
			elif message.startswith("40"):  # Connection successful
				self._log("Socket.IO connection successful")
			elif message.startswith("42"):  # Event message
				event_data = json.loads(message[2:])
				self._handle_event(event_data[0], event_data[1] if len(event_data) > 1 else {})
		except Exception as e:
			self._log(f"Message processing error: {e}")
			self._emit_stream_event(str(e), "error")

	def _send_preset_messages(self) -> None:
		"""Send preset messages"""
		if self.connected and self.ws:
			self.ws.send('42["preset_chat_message",{"turn_count":5,"system_content_enum":"default"}]')
			self.ws.send('42["get_text2Img_remaining_times"]')

	def on_error(self, _ws: object, error: object) -> None:
		error_msg = f"WebSocket error: {error}"
		self._log(error_msg)
		self._emit_stream_event(error_msg, "error")

	def on_close(self, _ws: object, _close_status_code: int | None = None, _close_msg: str | None = None) -> None:
		self._log("Connection closed")
		self.connected = False

	def on_open(self, ws: WebSocketApp) -> None:
		self._log("WebSocket connection established")
		self.connected = True
		ws.send("40")

		def send_join() -> None:
			time.sleep(1)
			ws.send('42["join"]')

		threading.Thread(target=send_join, daemon=True).start()

	def _build_websocket_url(self) -> str:
		"""Build WebSocket URL"""
		params = {"stag": 6, "rf": "", "token": self.token, "source_label": "kn", "question_type": "undefined", "EIO": 3, "transport": "websocket"}
		query_string = "&".join([f"{k}={quote(str(v))}" for k, v in params.items()])
		return f"wss://cr-aichat.codemao.cn/aichat/?{query_string}"

	def connect(self) -> bool:
		"""Connect to WebSocket server"""
		if not self.token:
			self._log("Error: No token provided")
			return False
		self._log("Connecting to server...")
		self.ws = WebSocketApp(
			self._build_websocket_url(),
			on_message=self.on_message,
			on_error=self.on_error,
			on_close=self.on_close,
			on_open=self.on_open,  # pyright: ignore[reportArgumentType]
			header={
				"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0",
				"Origin": "https://kn.codemao.cn",
				"Accept-Encoding": "gzip, deflate, br, zstd",
				"Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
				"Cache-Control": "no-cache",
				"Pragma": "no-cache",
			},
		)

		def run_websocket() -> None:
			if self.ws:
				self.ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE}, ping_interval=30, ping_timeout=10)

		thread = threading.Thread(target=run_websocket, daemon=True)
		thread.start()
		# Wait for connection to be established
		timeout = 10
		start_time = time.time()
		while not self.connected and time.time() - start_time < timeout:
			time.sleep(0.1)
		return self.connected

	@staticmethod
	def _generate_session_id() -> str:
		"""Generate session ID"""
		return "".join(random.choices(string.ascii_lowercase + string.digits, k=13))

	def send_message(self, message: str, *, include_history: bool = True) -> bool:
		"""
		Send chat message
		Args:
			message: 要发送的消息
			include_history: 是否包含对话历史
		"""
		if not self.connected or not self.ws:
			self._log("Error: Not connected to server")
			return False
		if self.is_receiving_response:
			self._log("Please wait for the previous reply to complete...")
			return False
		# 将用户消息添加到对话历史
		self._conversation_history.append({"role": "user", "content": message})
		# 将用户消息添加到对话历史
		self._conversation_history.append({"role": "user", "content": message})
		# 构建消息数据
		messages = self._conversation_history if include_history and len(self._conversation_history) > 1 else [{"role": "user", "content": message}]
		chat_data = {"session_id": self._current_conversation_id, "messages": messages, "chat_type": "chat_v3", "msg_channel": 0}
		message_str = f'42["chat",{json.dumps(chat_data, ensure_ascii=False)}]'
		self.ws.send(message_str)
		self._log(f"Message sent: {message}")
		return True

	def wait_for_response_start(self, timeout: int = 10) -> bool:
		"""
		等待AI开始回复
		Args:
			timeout: 超时时间(秒)
		Returns:
			是否成功开始回复
		"""
		start_time = time.time()
		while not self.is_receiving_response and time.time() - start_time < timeout:
			time.sleep(0.1)
		return self.is_receiving_response

	def wait_for_response(self, timeout: int = 60) -> bool:
		"""Wait for current response to complete"""
		start_time = time.time()
		while self.is_receiving_response and time.time() - start_time < timeout:
			time.sleep(0.1)
		return not self.is_receiving_response

	def send_and_wait(self, message: str, *, include_history: bool = True, response_timeout: int = 60) -> bool:
		"""
		发送消息并等待回复完成(推荐使用这个方法)
		Args:
			message: 要发送的消息
			include_history: 是否包含对话历史
			response_timeout: 回复超时时间(秒)
		Returns:
			是否成功完成对话
		"""
		if not self.send_message(message=message, include_history=include_history):
			return False
		# 等待AI开始回复
		if not self.wait_for_response_start(timeout=10):
			self._log("AI未开始回复")
			return False
		# 等待回复完成
		return self.wait_for_response(timeout=response_timeout)

	def get_user_info(self) -> dict[str, Any]:
		"""
		获取用户信息
		Returns:
			包含用户信息的字典
		"""
		return {"user_id": self.user_id, **self._user_info}

	def new_conversation(self) -> None:
		"""
		创建新对话,清空对话历史
		"""
		self._conversation_history.clear()
		self._current_conversation_id = self._generate_session_id()
		self._log("新对话已创建")

	def get_conversation_history(self) -> list[dict[str, str]]:
		"""
		获取当前对话历史
		Returns:
			对话历史列表
		"""
		return self._conversation_history.copy()

	def get_conversation_count(self) -> int:
		"""
		获取当前对话轮数
		Returns:
			对话轮数(用户消息数)
		"""
		return len([msg for msg in self._conversation_history if msg["role"] == "user"])

	def close(self) -> None:
		"""Close connection"""
		if self.ws:
			self.ws.close()
		self.connected = False


def stream_chat(token: str, message: str, timeout: int = 60) -> str:
	"""
	直接流式打印AI回复的便捷函数(单次对话)
	Args:
		token: 认证token
		message: 要发送的消息
		timeout: 超时时间(秒)
	Returns:
		完整的回复内容
	"""
	client = CodeMaoAIChat(token=token, verbose=False)
	full_response = []

	def stream_handler(content: str, event_type: str) -> None:
		if event_type == "text":
			print(content, end="", flush=True)
			full_response.append(content)
		elif event_type == "end":
			full_response.append(content)
			print()  # 换行

	client.add_stream_callback(stream_handler)
	try:
		if client.connect():
			# 等待初始化
			time.sleep(2)
			# 使用新的send_and_wait方法
			if client.send_and_wait(message, include_history=False, response_timeout=timeout):
				pass  # 回复已完成
			else:
				print("对话失败")
		else:
			print("连接失败")
	finally:
		client.close()
	return "".join(full_response)


def create_chat_session(token: str) -> CodeMaoAIChat:
	"""
	创建支持连续对话的聊天会话
	Args:
		token: 认证token
	Returns:
		CodeMaoAIChat 实例
	"""
	client = CodeMaoAIChat(token=token, verbose=False)
	if client.connect():
		time.sleep(2)  # 等待初始化
		return client
	msg = "连接失败"
	raise ConnectionError(msg)


def interactive_chat(token: str) -> None:
	"""
	交互式聊天会话,支持连续对话和新对话创建
	Args:
		token: 认证token
	"""
	client = create_chat_session(token)

	def stream_handler(content: str, event_type: str) -> None:
		if event_type == "text":
			print(content, end="", flush=True)
		elif event_type == "end":
			print()  # 换行

	client.add_stream_callback(stream_handler)
	print("=== CodeMao AI 聊天 ===")
	print("输入消息开始聊天")
	print("输入 '/new' 创建新对话")
	print("输入 '/history' 查看对话历史")
	print("输入 '/quit' 退出")
	print("=" * 20)
	try:
		while True:
			user_input = input("\n你: ").strip()
			if not user_input:
				continue
			if user_input.lower() in {"/quit", "/exit", "退出"}:
				break
			if user_input.lower() == "/new":
				client.new_conversation()
				print("🆕 已创建新对话")
				continue
			if user_input.lower() == "/history":
				history = client.get_conversation_history()
				print(f"对话历史 ({client.get_conversation_count()} 轮):")
				for i, msg in enumerate(history[-6:], 1):  # 显示最近6条
					role = "你" if msg["role"] == "user" else "AI"
					content_preview = msg["content"][:50] + "..." if len(msg["content"]) > 50 else msg["content"]  # noqa: PLR2004
					print(f"  {i}. {role}: {content_preview}")
				continue
			# 发送消息并等待回复 - 使用新的send_and_wait方法
			print("AI: ", end="", flush=True)
			if client.send_and_wait(user_input, response_timeout=60):
				# 回复已完成,继续下一轮
				pass
			else:
				print("\n回复超时或失败")
	except KeyboardInterrupt:
		print("\n\n聊天结束")
	finally:
		client.close()


def get_user_quota(token: str) -> dict[str, Any]:
	"""
	快速获取用户配额信息
	Args:
		token: 认证token
	Returns:
		用户配额信息字典
	"""
	client = CodeMaoAIChat(token=token, verbose=False)
	try:
		if client.connect():
			# 等待用户信息加载完成
			time.sleep(3)
			return client.get_user_info()
		return {"error": "连接失败"}
	finally:
		client.close()
