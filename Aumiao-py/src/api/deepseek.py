import json
import random
import ssl
import string
import threading
import time
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

import websocket

if TYPE_CHECKING:
	from collections.abc import Callable


class CodeMaoAIChat:
	def __init__(self, token: str | None = None) -> None:
		self.ws: websocket.WebSocketApp | None = None
		self.token = token
		self.connected = False
		self.session_id: str | None = None
		self.search_session: str | None = None
		self.user_id: str | None = None
		self.current_response = ""
		self.is_receiving_response = False

	def _handle_event(self, event_name: str, payload: dict[str, Any]) -> None:
		"""处理具体事件"""
		event_handlers: dict[str, Callable[[dict[str, Any]], None]] = {
			"on_connect_ack": self._handle_connect_ack,
			"join_ack": self._handle_join_ack,
			"preset_chat_message_ack": lambda _: print("预设消息确认"),
			"get_text2Img_remaining_times_ack": self._handle_remaining_times,
			"chat_ack": self._handle_chat_ack,
		}
		handler = event_handlers.get(event_name)
		if handler:
			handler(payload)

	@staticmethod
	def _handle_connect_ack(payload: dict[str, Any]) -> None:
		"""处理连接确认事件"""
		if payload.get("code") == 1:
			data = payload.get("data", {})
			print(f"连接确认 - 剩余聊天次数: {data.get('chat_count', '未知')}")

	def _handle_join_ack(self, payload: dict[str, Any]) -> None:
		"""处理加入确认事件"""
		if payload.get("code") == 1:
			data = payload.get("data", {})
			self.user_id = data.get("user_id")
			self.search_session = data.get("search_session")
			print(f"加入成功 - 用户ID: {self.user_id}, 会话: {self.search_session}")
			self._send_preset_messages()

	@staticmethod
	def _handle_remaining_times(payload: dict[str, Any]) -> None:
		"""处理剩余次数查询"""
		data = payload.get("data", {})
		print(f"剩余图片生成次数: {data.get('remaining_times', '未知')}")

	def _handle_chat_ack(self, payload: dict[str, Any]) -> None:
		"""处理聊天回复事件"""
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
		"""处理流式输出开始"""
		self.session_id = data.get("session_id")
		self.current_response = ""
		self.is_receiving_response = True
		print("\nAI: ", end="", flush=True)

	def _handle_stream_content(self, _data: dict[str, Any], content: str) -> None:
		"""处理流式输出内容"""
		if self.is_receiving_response:
			self.current_response += content
			print(content, end="", flush=True)

	def _handle_stream_end(self, _data: dict[str, Any], _content: str) -> None:
		"""处理流式输出结束"""
		self.is_receiving_response = False
		print(f"\n\n完整回复: {self.current_response}")
		print("=" * 50)

	def on_message(self, _ws: object, message: str) -> None:
		"""处理接收到的消息"""
		try:
			if message.startswith("0"):  # 连接确认
				print("连接已建立")
				data = json.loads(message[1:])
				print(f"Session ID: {data.get('sid')}")
			elif message.startswith("3"):  # ping
				if self.ws:
					self.ws.send("2")  # pong
			elif message.startswith("40"):  # 连接成功
				print("Socket.IO连接成功")
			elif message.startswith("42"):  # 事件消息
				event_data = json.loads(message[2:])
				self._handle_event(event_data[0], event_data[1] if len(event_data) > 1 else {})
		except Exception as e:
			print(f"消息处理错误: {e}")

	def _send_preset_messages(self) -> None:
		"""发送预设消息"""
		if self.connected and self.ws:
			self.ws.send('42["preset_chat_message",{"turn_count":5,"system_content_enum":"default"}]')
			self.ws.send('42["get_text2Img_remaining_times"]')

	@staticmethod
	def on_error(_ws: object, error: object) -> None:
		print(f"WebSocket错误: {error}")

	def on_close(self, _ws: object, _close_status_code: int | None = None, _close_msg: str | None = None) -> None:
		print("连接已关闭")
		self.connected = False

	def on_open(self, ws: ...) -> None:
		print("WebSocket连接已建立")
		self.connected = True
		ws.send("40")

		def send_join() -> None:
			time.sleep(1)
			ws.send('42["join"]')

		threading.Thread(target=send_join, daemon=True).start()

	def _build_websocket_url(self) -> str:
		"""构建WebSocket URL"""
		params = {"stag": 6, "rf": "", "token": self.token, "source_label": "kn", "question_type": "undefined", "EIO": 3, "transport": "websocket"}
		query_string = "&".join([f"{k}={quote(str(v))}" for k, v in params.items()])
		return f"wss://cr-aichat.codemao.cn/aichat/?{query_string}"

	def connect(self) -> bool:
		"""连接到WebSocket服务器"""
		if not self.token:
			print("错误: 未提供token")
			return False
		print("正在连接到服务器...")
		self.ws = websocket.WebSocketApp(
			self._build_websocket_url(),
			on_message=self.on_message,
			on_error=self.on_error,
			on_close=self.on_close,
			on_open=self.on_open,
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

	def send_message(self, message: str) -> bool:
		"""发送聊天消息"""
		if not self.connected or not self.ws:
			print("错误: 未连接到服务器")
			return False
		if self.is_receiving_response:
			print("请等待上一个回复完成...")
			return False
		chat_data = {"session_id": self._generate_session_id(), "messages": [{"role": "user", "content": message}], "chat_type": "chat_v3", "msg_channel": 0}
		message_str = f'42["chat",{json.dumps(chat_data, ensure_ascii=False)}]'
		self.ws.send(message_str)
		print(f"\n你: {message}")
		return True

	def start_chat(self) -> None:
		"""开始交互式聊天"""
		if not self.connect():
			return
		print("\n连接成功!")
		print("输入你的消息 (输入 'quit' 退出):")
		try:
			while self.connected:
				if self.is_receiving_response:
					time.sleep(0.1)
					continue
				user_input = input("\n> ").strip()
				if user_input.lower() in {"quit", "exit", "退出"}:
					break
				if user_input:
					self.send_message(user_input)
					wait_count = 0
					while not self.is_receiving_response and wait_count < 50:  # noqa: PLR2004
						time.sleep(0.1)
						wait_count += 1
				else:
					print("请输入有效内容")
		except KeyboardInterrupt:
			print("\n程序被用户中断")
		except EOFError:
			print("\n输入结束")
		finally:
			if self.ws:
				self.ws.close()


def main() -> None:
	print("=" * 60)
	print("           CodeMao AI 聊天客户端")
	print("=" * 60)
	token = input("请输入你的token: ").strip()
	if not token:
		print("错误: token不能为空")
		return
	chat_client = CodeMaoAIChat(token=token)
	chat_client.start_chat()


if __name__ == "__main__":
	main()
