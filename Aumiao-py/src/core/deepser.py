import json
import random
import ssl
import string
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any
from urllib.parse import quote

from websocket import WebSocketApp


class CodeMaoAIChat:
	"""CodeMao AI Chat Client - 精简优化版"""

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
		# 回调管理和数据存储
		self._stream_callbacks: list[Callable[[str, str], None]] = []
		self._user_info: dict[str, Any] = {}
		self._conversation_history: list[dict[str, str]] = []
		self._current_conversation_id = self._generate_session_id()

	def _log(self, message: str) -> None:
		"""日志输出"""
		if self.verbose:
			print(message)

	def add_stream_callback(self, callback: Callable[[str, str], None]) -> None:
		"""添加流式回调函数"""
		self._stream_callbacks.append(callback)

	def remove_stream_callback(self, callback: Callable[[str, str], None]) -> None:
		"""移除流式回调函数"""
		if callback in self._stream_callbacks:
			self._stream_callbacks.remove(callback)

	def _emit_stream_event(self, content: str, event_type: str) -> None:
		"""触发流式事件"""
		for callback in self._stream_callbacks:
			try:
				callback(content, event_type)
			except Exception as e:
				self._log(f"回调错误: {e}")

	def _handle_event(self, event_name: str, payload: dict[str, Any]) -> None:
		"""统一事件处理"""
		event_handlers = {
			"on_connect_ack": self._handle_connect_ack,
			"join_ack": self._handle_join_ack,
			"preset_chat_message_ack": lambda _: self._log("预设消息确认"),
			"get_text2Img_remaining_times_ack": self._handle_remaining_times,
			"chat_ack": self._handle_chat_ack,
		}
		if handler := event_handlers.get(event_name):
			handler(payload)

	def _handle_connect_ack(self, payload: dict[str, Any]) -> None:
		"""处理连接确认"""
		if payload.get("code") == 1:
			self._user_info.update(payload.get("data", {}))
			self._log(f"连接确认 - 剩余对话次数: {self._user_info.get('chat_count', '未知')}")

	def _handle_join_ack(self, payload: dict[str, Any]) -> None:
		"""处理加入确认"""
		if payload.get("code") == 1:
			data = payload.get("data", {})
			self.user_id = data.get("user_id")
			self.search_session = data.get("search_session")
			self._log(f"加入成功 - 用户ID: {self.user_id}, 会话: {self.search_session}")
			self._send_preset_messages()

	def _handle_remaining_times(self, payload: dict[str, Any]) -> None:
		"""处理剩余次数查询"""
		if payload.get("code") == 1:
			data = payload.get("data", {})
			self._user_info["remaining_image_times"] = data.get("remaining_times")
			self._log(f"剩余图片生成次数: {data.get('remaining_times', '未知')}")

	def _handle_chat_ack(self, payload: dict[str, Any]) -> None:
		"""处理聊天回复"""
		if payload.get("code") != 1:
			return
		data = payload.get("data", {})
		content_type = data.get("content_type")
		content = data.get("content", "")
		handlers = {
			"stream_output_begin": self._handle_stream_begin,
			"stream_output_content": self._handle_stream_content,
			"stream_output_end": self._handle_stream_end,
		}
		if handler := handlers.get(content_type):
			handler(data, content)

	def _handle_stream_begin(self, data: dict[str, Any], _content: str) -> None:
		"""处理流开始"""
		self.session_id = data.get("session_id")
		self.current_response = ""
		self.is_receiving_response = True
		self._emit_stream_event("", "start")

	def _handle_stream_content(self, _data: dict[str, Any], content: str) -> None:
		"""处理流内容"""
		if self.is_receiving_response:
			self.current_response += content
			self._emit_stream_event(content, "text")

	def _handle_stream_end(self, _data: dict[str, Any], _content: str) -> None:
		"""处理流结束"""
		self.is_receiving_response = False
		self._emit_stream_event(self.current_response, "end")
		# 将AI回复添加到对话历史
		if self.current_response:
			self._conversation_history.append({"role": "assistant", "content": self.current_response})

	def on_message(self, _ws: object, message: str) -> None:
		"""WebSocket消息处理"""
		try:
			if message.startswith("0"):  # 连接确认
				self._log("连接建立")
			elif message.startswith("3"):  # ping
				if self.ws:
					self.ws.send("2")  # pong
			elif message.startswith("40"):  # 连接成功
				self._log("Socket.IO连接成功")
			elif message.startswith("42"):  # 事件消息
				event_data = json.loads(message[2:])
				self._handle_event(event_data[0], event_data[1] if len(event_data) > 1 else {})
		except Exception as e:
			self._log(f"消息处理错误: {e}")
			self._emit_stream_event(str(e), "error")

	def _send_preset_messages(self) -> None:
		"""发送预设消息"""
		if self.connected and self.ws:
			self.ws.send('42["preset_chat_message",{"turn_count":5,"system_content_enum":"default"}]')
			self.ws.send('42["get_text2Img_remaining_times"]')

	def on_error(self, _ws: object, error: object) -> None:
		"""WebSocket错误处理"""
		error_msg = f"WebSocket错误: {error}"
		self._log(error_msg)
		self._emit_stream_event(error_msg, "error")

	def on_close(self, _ws: object, _close_status_code: int | None = None, _close_msg: str | None = None) -> None:
		"""WebSocket关闭处理"""
		self._log("连接关闭")
		self.connected = False

	def on_open(self, ws: WebSocketApp) -> None:
		"""WebSocket打开处理"""
		self._log("WebSocket连接建立")
		self.connected = True
		ws.send("40")

		def send_join() -> None:
			time.sleep(1)
			ws.send('42["join"]')

		threading.Thread(target=send_join, daemon=True).start()

	def _build_websocket_url(self) -> str:
		"""构建WebSocket URL"""
		params = {"stag": 6, "rf": "", "token": self.token, "source_label": "kn", "question_type": "undefined", "EIO": 3, "transport": "websocket"}
		query_string = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
		return f"wss://cr-aichat.codemao.cn/aichat/?{query_string}"

	def connect(self) -> bool:
		"""连接到WebSocket服务器"""
		if not self.token:
			self._log("错误: 未提供token")
			return False
		self._log("连接到服务器...")
		self.ws = WebSocketApp(
			self._build_websocket_url(),
			on_message=self.on_message,
			on_error=self.on_error,
			on_close=self.on_close,
			on_open=self.on_open,  # type: ignore  # noqa: PGH003
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
		# 等待连接建立
		timeout = 10
		start_time = time.time()
		while not self.connected and time.time() - start_time < timeout:
			time.sleep(0.1)
		return self.connected

	@staticmethod
	def _generate_session_id() -> str:
		"""生成会话ID"""
		return "".join(random.choices(string.ascii_lowercase + string.digits, k=13))

	def send_message(self, message: str, *, include_history: bool = True) -> bool:
		"""发送聊天消息"""
		if not self.connected or not self.ws:
			self._log("错误: 未连接到服务器")
			return False
		if self.is_receiving_response:
			self._log("请等待上一条回复完成...")
			return False
		# 添加用户消息到历史记录
		self._conversation_history.append({"role": "user", "content": message})
		# 构建消息数据
		messages = self._conversation_history if include_history and len(self._conversation_history) > 1 else [{"role": "user", "content": message}]
		chat_data = {"session_id": self._current_conversation_id, "messages": messages, "chat_type": "chat_v3", "msg_channel": 0}
		message_str = f'42["chat",{json.dumps(chat_data, ensure_ascii=False)}]'
		self.ws.send(message_str)
		self._log(f"消息已发送: {message}")
		return True

	def wait_for_response_start(self, timeout: int = 10) -> bool:
		"""等待AI开始回复"""
		start_time = time.time()
		while not self.is_receiving_response and time.time() - start_time < timeout:
			time.sleep(0.1)
		return self.is_receiving_response

	def wait_for_response(self, timeout: int = 60) -> bool:
		"""等待当前回复完成"""
		start_time = time.time()
		while self.is_receiving_response and time.time() - start_time < timeout:
			time.sleep(0.1)
		return not self.is_receiving_response

	def send_and_wait(self, message: str, *, include_history: bool = True, response_timeout: int = 60) -> bool:
		"""发送消息并等待回复完成(推荐使用)"""
		if not self.send_message(message=message, include_history=include_history):
			return False
		# 等待AI开始回复
		if not self.wait_for_response_start(timeout=10):
			self._log("AI未开始回复")
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
		self._log("新对话已创建")

	def get_conversation_history(self) -> list[dict[str, str]]:
		"""获取当前对话历史"""
		return self._conversation_history.copy()

	def get_conversation_count(self) -> int:
		"""获取当前对话轮数"""
		return len([msg for msg in self._conversation_history if msg["role"] == "user"])

	def close(self) -> None:
		"""关闭连接"""
		if self.ws:
			self.ws.close()
		self.connected = False


class CodeMaoTool:
	"""工具类 - 提供便捷的聊天方法"""

	def __init__(self) -> None:
		pass

	@staticmethod
	def stream_chat(token: str, message: str, timeout: int = 60) -> str:
		"""直接流式打印AI回复的便捷函数"""
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

	def interactive_chat(self, token: str) -> None:
		"""交互式聊天会话"""
		client = self.create_chat_session(token)

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
					for i, msg in enumerate(history[-6:], 1):
						role = "你" if msg["role"] == "user" else "AI"
						content_preview = msg["content"][:50] + "..." if len(msg["content"]) > 50 else msg["content"]  # noqa: PLR2004
						print(f"  {i}. {role}: {content_preview}")
					continue
				print("AI: ", end="", flush=True)
				if not client.send_and_wait(user_input, response_timeout=60):
					print("\n回复超时或失败")
		except KeyboardInterrupt:
			print("\n\n聊天结束")
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


class CodeMaoAIClient:
	"""CodeMao AI Chat Client - 多token管理版本"""

	def __init__(self, tokens: list[str], *, verbose: bool = False) -> None:
		self.tokens = tokens
		self.current_token_index = 0
		self.verbose = verbose
		self._clients: dict[str, CodeMaoAIChat] = {}

	def _get_current_token(self) -> str:
		"""获取当前token"""
		return self.tokens[self.current_token_index]

	def _switch_to_next_token(self) -> bool:
		"""切换到下一个token"""
		if len(self.tokens) <= 1:
			return False
		old_index = self.current_token_index
		self.current_token_index = (self.current_token_index + 1) % len(self.tokens)
		if self.verbose:
			print(f"Token切换: 从索引 {old_index} 切换到 {self.current_token_index}")
		return True

	def _get_or_create_client(self, token: str) -> CodeMaoAIChat:
		"""获取或创建客户端实例"""
		if token not in self._clients:
			self._clients[token] = CodeMaoAIChat(token, verbose=self.verbose)
		return self._clients[token]

	def _check_token_quota(self, client: CodeMaoAIChat) -> bool:
		"""检查token配额"""
		try:
			user_info = client.get_user_info()
			chat_count = user_info.get("chat_count", 0)
			if self.verbose:
				print(f"当前token剩余对话次数: {chat_count}")
			return chat_count >= 2  # 剩余次数大于等于2次认为充足  # noqa: PLR2004, TRY300
		except Exception as e:
			if self.verbose:
				print(f"检查配额失败: {e}")
			return True  # 如果检查失败,继续使用当前token

	def stream_chat_with_prompt(self, message: str, prompt: str = "", timeout: int = 60) -> Iterator[str]:
		max_retries = len(self.tokens)
		for retry in range(max_retries):
			current_token = self._get_current_token()
			if self.verbose:
				print(f"尝试使用token索引 {self.current_token_index} (尝试 {retry + 1}/{max_retries})")
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
						print(f"Token {self.current_token_index} 配额不足,尝试切换")
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
					client.current_response = ""
				# 发送用户消息并流式返回
				yield from self._stream_user_message(client, message, timeout)
				return  # 成功则直接返回  # noqa: TRY300
			except Exception as e:
				if self.verbose:
					print(f"Token {self.current_token_index} 处理失败: {e}")
				self._switch_to_next_token()
				continue
			finally:
				client.close()
		yield f"错误: 所有token都尝试失败,共尝试了 {max_retries} 次"

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
			yield "错误: AI未开始回复"
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
		print("AI: ", end="", flush=True)
		for chunk in self.stream_chat_with_prompt(message, prompt, timeout):
			print(chunk, end="", flush=True)
			full_response.append(chunk)
		print()
		return "".join(full_response)

	def batch_check_quotas(self) -> dict[str, Any]:
		"""批量检查所有token的配额"""
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
