import hashlib
import json
import threading
import time
import uuid
from collections.abc import Callable
from contextlib import suppress
from enum import Enum
from typing import Any, cast

import httpx
import websocket


class CodemaoWorkEditor(Enum):
	NEMO = "NEMO"
	KITTEN = "KITTEN"
	KITTEN_N = "NEKO"
	COCO = "COCO"


class KittenCloudDataType(Enum):
	PRIVATE_VARIABLE = 0
	PUBLIC_VARIABLE = 1
	LIST = 2


class KittenCloudReceiveMessageType(Enum):
	JOIN = "connect_done"
	RECEIVE_ALL_DATA = "list_variables_done"
	UPDATE_PRIVATE_VARIABLE = "update_private_vars_done"
	RECEIVE_PRIVATE_VARIABLE_RANKING_LIST = "list_ranking_done"
	UPDATE_PUBLIC_VARIABLE = "update_vars_done"
	UPDATE_LIST = "update_lists_done"
	ILLEGAL_EVENT = "illegal_event_done"
	UPDATE_ONLINE_USER_NUMBER = "online_users_change"


class KittenCloudSendMessageType(Enum):
	JOIN = "join"
	GET_ALL_DATA = "list_variables"
	UPDATE_PRIVATE_VARIABLE = "update_private_vars"
	GET_PRIVATE_VARIABLE_RANKING_LIST = "list_ranking"
	UPDATE_PUBLIC_VARIABLE = "update_vars"
	UPDATE_LIST = "update_lists"


# 定义类型别名
CloudValueType = int | str
CloudListValueType = list[CloudValueType]
# 常量定义
HTTP_SUCCESS_CODE = 200
WEBSOCKET_PING_MESSAGE = "2"
WEBSOCKET_PONG_MESSAGE = "3"
WEBSOCKET_CONNECT_MESSAGE = "40"
WEBSOCKET_CONNECTED_MESSAGE = "40"
WEBSOCKET_EVENT_MESSAGE_PREFIX = "42"
WEBSOCKET_HANDSHAKE_MESSAGE_PREFIX = "0"


# 错误消息常量
class ErrorMessages:
	CALLBACK_EXECUTION = "回调执行错误"
	CLOUD_VARIABLE_CALLBACK = "云变量变更回调执行错误"
	RANKING_CALLBACK = "排行榜回调执行错误"
	OPERATION_CALLBACK = "操作回调执行错误"
	EVENT_CALLBACK = "事件回调执行错误"
	SEND_MESSAGE = "发送消息错误"
	CONNECTION = "连接错误"
	WEB_SOCKET_RUN = "WebSocket运行错误"
	CLOSE_CONNECTION = "关闭连接时出错"
	GET_SERVER_TIME = "获取服务器时间失败"
	HANDSHAKE_DATA_PARSE = "握手数据解析失败"
	HANDSHAKE_PROCESSING = "握手处理错误"
	JSON_PARSE = "JSON解析错误"
	CLOUD_MESSAGE_PROCESSING = "云消息处理错误"
	CREATE_DATA_ITEM = "创建数据项时出错"
	INVALID_RANKING_DATA = "无效的排行榜数据格式"
	PING_SEND = "发送 ping 失败"
	NO_PENDING_REQUESTS = "收到排行榜数据但没有待处理的请求"


# 魔法数值常量
class MagicNumbers:
	DEFAULT_RANKING_LIMIT = 31
	MAX_RECONNECT_ATTEMPTS = 5
	RECONNECT_INTERVAL = 8
	PING_INTERVAL_MS = 25000
	PING_TIMEOUT_MS = 5000
	WEBSOCKET_PING_INTERVAL = 20
	WEBSOCKET_PING_TIMEOUT = 10
	CONNECTION_TIMEOUT = 30
	DATA_TIMEOUT = 30
	WAIT_TIMEOUT = 30


class CodemaoAuth:
	def __init__(self, authorization_token: str | None = None) -> None:
		self.authorization_token = authorization_token
		self.client_id = str(uuid.uuid4())
		self.time_difference = 0

	@staticmethod
	def get_current_time() -> int:
		try:
			response = httpx.get("https://api.codemao.cn/coconut/clouddb/currentTime", timeout=10)
			if response.status_code == HTTP_SUCCESS_CODE:
				data = response.json()
				if isinstance(data, dict) and "data" in data:
					return data["data"]
				return cast("int", data)
		except Exception as e:
			print(f"{ErrorMessages.GET_SERVER_TIME}: {e}")
		return int(time.time())

	def get_calibrated_timestamp(self) -> int:
		if self.time_difference == 0:
			server_time = self.get_current_time()
			local_time = int(time.time())
			self.time_difference = local_time - server_time
		return int(time.time()) - self.time_difference

	def generate_device_auth(self) -> dict[str, Any]:
		timestamp = self.get_calibrated_timestamp()
		sign_text = f"pBlYqXbJDu{timestamp}{self.client_id}"
		sign = hashlib.sha256(sign_text.encode()).hexdigest().upper()
		return {"sign": sign, "timestamp": timestamp, "client_id": self.client_id}


class KittenCloudData:
	def __init__(self, connection: "KittenCloudFunction", cvid: str, name: str, value: CloudValueType | CloudListValueType) -> None:
		self.connection = connection
		self.cvid = cvid
		self.name = name
		self.value = value
		self._change_callbacks: list[Callable[..., None]] = []

	def on_change(self, callback: Callable[[CloudValueType | CloudListValueType, CloudValueType | CloudListValueType, str], None]) -> None:
		self._change_callbacks.append(callback)

	def emit_change(self, old_value: CloudValueType | CloudListValueType, new_value: CloudValueType | CloudListValueType, source: str) -> None:
		for callback in self._change_callbacks:
			try:
				callback(old_value, new_value, source)
			except Exception as e:
				print(f"{ErrorMessages.CALLBACK_EXECUTION}: {e}")


class KittenCloudVariable(KittenCloudData):
	def __init__(self, connection: "KittenCloudFunction", cvid: str, name: str, value: CloudValueType) -> None:
		super().__init__(connection, cvid, name, value)
		self._change_callbacks: list[Callable[[CloudValueType, CloudValueType, str], None]] = []

	def on_change(self, callback: Callable[[CloudValueType, CloudValueType, str], None]) -> None:
		self._change_callbacks.append(callback)

	def get(self) -> CloudValueType:
		return cast("CloudValueType", self.value)

	def set(self, value: CloudValueType) -> bool:
		if not isinstance(value, (int, str)):
			raise TypeError("云变量值必须是整数或字符串")
		old_value = self.value
		self.value = value
		self.emit_change(cast("CloudValueType", old_value), value, "local")
		return True

	def emit_change(self, old_value: CloudValueType, new_value: CloudValueType, source: str) -> None:
		for callback in self._change_callbacks:
			try:
				callback(old_value, new_value, source)
			except Exception as e:
				print(f"{ErrorMessages.CLOUD_VARIABLE_CALLBACK}: {e}")


class KittenCloudPrivateVariable(KittenCloudVariable):
	def __init__(self, connection: "KittenCloudFunction", cvid: str, name: str, value: CloudValueType) -> None:
		super().__init__(connection, cvid, name, value)
		self._ranking_callbacks: list[Callable[[list[dict[str, Any]]], None]] = []

	def on_ranking_received(self, callback: Callable[[list[dict[str, Any]]], None]) -> None:
		self._ranking_callbacks.append(callback)

	def emit_ranking(self, ranking_data: list[dict[str, Any]]) -> None:
		for callback in self._ranking_callbacks:
			try:
				callback(ranking_data)
			except Exception as e:
				print(f"{ErrorMessages.RANKING_CALLBACK}: {e}")

	def get_ranking_list(self, limit: int = MagicNumbers.DEFAULT_RANKING_LIMIT, order: int = -1) -> None:
		if not isinstance(limit, int) or limit <= 0:
			raise ValueError("限制数量必须是正整数")
		if order not in {1, -1}:
			raise ValueError("排序顺序必须是1(正序)或-1(逆序)")
		request_data = {"cvid": self.cvid, "limit": limit, "order_type": order}
		self.connection._send_message(KittenCloudSendMessageType.GET_PRIVATE_VARIABLE_RANKING_LIST, request_data)


class KittenCloudPublicVariable(KittenCloudVariable):
	pass


class KittenCloudList(KittenCloudData):
	def __init__(self, connection: "KittenCloudFunction", cvid: str, name: str, value: CloudListValueType) -> None:
		super().__init__(connection, cvid, name, value or [])
		self._operation_callbacks: dict[str, list[Callable[..., None]]] = {
			"push": [],
			"pop": [],
			"unshift": [],
			"shift": [],
			"insert": [],
			"remove": [],
			"replace": [],
			"clear": [],
			"replace_last": [],
		}

	def on_operation(self, operation: str, callback: Callable[..., None]) -> None:
		if operation in self._operation_callbacks:
			self._operation_callbacks[operation].append(callback)

	def _emit_operation(self, operation: str, *args: Any) -> None:
		for callback in self._operation_callbacks[operation]:
			try:
				callback(*args)
			except Exception as e:
				print(f"{ErrorMessages.OPERATION_CALLBACK}: {e}")

	def get(self, index: int) -> CloudValueType | None:
		if 0 <= index < len(self.value):
			return self.value[index]
		return None

	def push(self, item: CloudValueType) -> bool:
		if not isinstance(item, (int, str)):
			raise TypeError("列表元素必须是整数或字符串")
		self.value.append(item)
		self._emit_operation("push", item, len(self.value) - 1)
		return True

	def pop(self) -> CloudValueType | None:
		if self.value:
			item = self.value.pop()
			self._emit_operation("pop", item, len(self.value))
			return item
		return None

	def unshift(self, item: CloudValueType) -> bool:
		if not isinstance(item, (int, str)):
			raise TypeError("列表元素必须是整数或字符串")
		self.value.insert(0, item)
		self._emit_operation("unshift", item, 0)
		return True

	def shift(self) -> CloudValueType | None:
		if self.value:
			item = self.value.pop(0)
			self._emit_operation("shift", item, 0)
			return item
		return None

	def insert(self, index: int, item: CloudValueType) -> bool:
		if not isinstance(item, (int, str)):
			raise TypeError("列表元素必须是整数或字符串")
		if 0 <= index <= len(self.value):
			self.value.insert(index, item)
			self._emit_operation("insert", item, index)
			return True
		return False

	def remove(self, index: int) -> CloudValueType | None:
		if 0 <= index < len(self.value):
			item = self.value.pop(index)
			self._emit_operation("remove", item, index)
			return item
		return None

	def replace(self, index: int, item: CloudValueType) -> bool:
		if not isinstance(item, (int, str)):
			raise TypeError("列表元素必须是整数或字符串")
		if 0 <= index < len(self.value):
			old_item = self.value[index]
			self.value[index] = item
			self._emit_operation("replace", old_item, item, index)
			return True
		return False

	def replace_last(self, item: CloudValueType) -> bool:
		if not isinstance(item, (int, str)):
			raise TypeError("列表元素必须是整数或字符串")
		if self.value:
			old_item = self.value[-1]
			self.value[-1] = item
			self._emit_operation("replace_last", old_item, item)
			return True
		return False

	def clear(self) -> bool:
		old_value = self.value.copy()
		self.value.clear()
		self._emit_operation("clear", old_value)
		return True

	def length(self) -> int:
		return len(self.value)

	def index_of(self, item: CloudValueType) -> int:
		try:
			return self.value.index(item)
		except ValueError:
			return -1

	def last_index_of(self, item: CloudValueType) -> int:
		try:
			return len(self.value) - 1 - self.value[::-1].index(item)
		except ValueError:
			return -1

	def includes(self, item: CloudValueType) -> bool:
		return item in self.value

	def join(self, separator: str = ",") -> str:
		return separator.join(str(item) for item in self.value)

	def copy(self) -> list[CloudValueType]:
		return self.value.copy()

	def copy_from(self, source_list: list[CloudValueType]) -> bool:
		if not all(isinstance(item, (int, str)) for item in source_list):
			return False
		old_value = self.value.copy()
		self.value = source_list.copy()
		self.emit_change(old_value, self.value, "local")
		return True


class KittenCloudFunction:
	def __init__(self, work_id: int, editor: CodemaoWorkEditor = CodemaoWorkEditor.KITTEN, authorization_token: str | None = None) -> None:
		self.work_id = work_id
		self.editor = editor
		self.auth = CodemaoAuth(authorization_token)
		self.ws: websocket.WebSocketApp | None = None
		self.connected = False
		self.auto_reconnect = True
		self.reconnect_interval = MagicNumbers.RECONNECT_INTERVAL
		self.reconnect_attempts = 0
		self.max_reconnect_attempts = MagicNumbers.MAX_RECONNECT_ATTEMPTS
		self.private_variables: dict[str, KittenCloudPrivateVariable] = {}
		self.public_variables: dict[str, KittenCloudPublicVariable] = {}
		self.lists: dict[str, KittenCloudList] = {}
		self._ping_thread: threading.Thread | None = None
		self._callbacks: dict[str, list[Callable[..., None]]] = {
			"open": [],
			"close": [],
			"error": [],
			"message": [],
			"data_ready": [],
			"online_users_change": [],
			"ranking_received": [],
		}
		self.online_users = 0
		self.data_ready = False
		self._pending_ranking_requests: list[KittenCloudPrivateVariable] = []

	def on(self, event: str, callback: Callable[..., None]) -> None:
		if event in self._callbacks:
			self._callbacks[event].append(callback)

	def on_online_users_change(self, callback: Callable[[int, int], None]) -> None:
		self._callbacks["online_users_change"].append(callback)

	def on_data_ready(self, callback: Callable[[], None]) -> None:
		self._callbacks["data_ready"].append(callback)

	def on_ranking_received(self, callback: Callable[["KittenCloudPrivateVariable", list[dict[str, Any]]], None]) -> None:
		self._callbacks["ranking_received"].append(callback)

	def _emit_event(self, event: str, *args: Any) -> None:
		if event in self._callbacks:
			for callback in self._callbacks[event]:
				try:
					callback(*args)
				except Exception as e:
					print(f"{ErrorMessages.EVENT_CALLBACK}: {e}")

	def _get_websocket_url(self) -> str:
		base_params = {
			CodemaoWorkEditor.NEMO: {"authorization_type": 5, "stag": 2},
			CodemaoWorkEditor.KITTEN: {"authorization_type": 1, "stag": 1},
			CodemaoWorkEditor.KITTEN_N: {"authorization_type": 5, "stag": 3, "token": ""},
			CodemaoWorkEditor.COCO: {"authorization_type": 1, "stag": 1},
		}
		params = base_params.get(self.editor, base_params[CodemaoWorkEditor.KITTEN])
		params["EIO"] = 3
		params["transport"] = "websocket"
		params_str = "&".join([f"{k}={v}" for k, v in params.items()])
		return f"wss://socketcv.codemao.cn:9096/cloudstorage/?session_id={self.work_id}&{params_str}"

	def _get_websocket_headers(self) -> dict[str, str]:
		headers: dict[str, str] = {}
		device_auth = self.auth.generate_device_auth()
		headers["X-Creation-Tools-Device-Auth"] = json.dumps(device_auth)
		if self.auth.authorization_token:
			headers["Cookie"] = f"Authorization={self.auth.authorization_token}"
		return headers

	def _on_message(self, _ws: websocket.WebSocketApp, message: str) -> None:
		# 添加调试信息
		# print(f"收到消息: {message}")  # 取消注释这行来查看所有消息
		# 处理 ping 消息
		if message == WEBSOCKET_PING_MESSAGE:
			if self.ws:
				self.ws.send(WEBSOCKET_PONG_MESSAGE)
			return
		# 处理握手消息 - 需要解析握手数据并启动 ping
		if message.startswith(WEBSOCKET_HANDSHAKE_MESSAGE_PREFIX):
			try:
				# 解析握手数据,获取 ping 间隔和超时时间
				handshake_data = json.loads(message[1:])  # 去掉前缀 "0"
				ping_interval = handshake_data.get("pingInterval", MagicNumbers.PING_INTERVAL_MS)
				ping_timeout = handshake_data.get("pingTimeout", MagicNumbers.PING_TIMEOUT_MS)
				print(f"握手成功,ping间隔: {ping_interval}ms, ping超时: {ping_timeout}ms")  # 调试信息
				# 启动 ping 保活机制
				self._start_ping(ping_interval, ping_timeout)
				# 发送连接请求
				if self.ws:
					self.ws.send(WEBSOCKET_CONNECT_MESSAGE)
					print("已发送连接请求")  # 调试信息
			except json.JSONDecodeError as e:
				print(f"{ErrorMessages.HANDSHAKE_DATA_PARSE}: {e}, 消息: {message}")
			except Exception as e:
				print(f"{ErrorMessages.HANDSHAKE_PROCESSING}: {e}")
			return
		# 处理连接确认消息
		if message == WEBSOCKET_CONNECTED_MESSAGE:
			self.connected = True
			print("连接确认收到")  # 调试信息
			self._emit_event("open")
			# 连接建立后发送加入消息
			self._send_message(KittenCloudSendMessageType.JOIN, str(self.work_id))
			return
		# 处理事件消息
		if message.startswith(WEBSOCKET_EVENT_MESSAGE_PREFIX):
			data_str = message[2:]  # 去掉前缀 "42"
			try:
				data_list = json.loads(data_str)
				if isinstance(data_list, list) and len(data_list) >= 2:
					message_type = data_list[0]
					message_data = data_list[1]
					print(f"处理云消息: {message_type}, 数据: {message_data}")  # 调试信息
					self._handle_cloud_message(message_type, message_data)
			except json.JSONDecodeError as e:
				print(f"{ErrorMessages.JSON_PARSE}: {e}, 数据: {data_str}")
			return

	def _start_ping(self, interval: int, _time_out: int) -> None:
		"""启动 ping-pong 保活机制"""
		ping_active = True

		def ping_task() -> None:
			nonlocal ping_active
			while ping_active and self.connected:
				time.sleep(interval / 1000)  # 转换为秒
				if ping_active and self.connected and self.ws:
					try:
						self.ws.send(WEBSOCKET_PING_MESSAGE)  # 发送 "2"
						print(f"发送 ping, 间隔: {interval}ms")  # 调试用
					except Exception as e:
						print(f"{ErrorMessages.PING_SEND}: {e}")
						break

		# 停止之前的 ping 线程
		if self._ping_thread is not None:
			ping_active = False
			self._ping_thread = None
		ping_active = True
		self._ping_thread = threading.Thread(target=ping_task, daemon=True)
		self._ping_thread.start()
		print(f"Ping 线程已启动,间隔: {interval}ms")  # 调试信息

	def _handle_cloud_message(self, message_type: str, data: Any) -> None:
		try:
			if message_type == KittenCloudReceiveMessageType.JOIN.value:
				self._send_message(KittenCloudSendMessageType.GET_ALL_DATA, {})
			elif message_type == KittenCloudReceiveMessageType.RECEIVE_ALL_DATA.value:
				self._handle_receive_all_data(data)
			elif message_type == KittenCloudReceiveMessageType.UPDATE_PRIVATE_VARIABLE.value:
				self._handle_update_private_variable(data)
			elif message_type == KittenCloudReceiveMessageType.RECEIVE_PRIVATE_VARIABLE_RANKING_LIST.value:
				self._handle_receive_ranking_list(data)
			elif message_type == KittenCloudReceiveMessageType.UPDATE_PUBLIC_VARIABLE.value:
				self._handle_update_public_variable(data)
			elif message_type == KittenCloudReceiveMessageType.UPDATE_LIST.value:
				self._handle_update_list(data)
			elif message_type == KittenCloudReceiveMessageType.UPDATE_ONLINE_USER_NUMBER.value:
				self._handle_update_online_users(data)
			elif message_type == KittenCloudReceiveMessageType.ILLEGAL_EVENT.value:
				print(f"非法事件: {data}")
		except Exception as e:
			print(f"{ErrorMessages.CLOUD_MESSAGE_PROCESSING}: {e}")
			self._emit_event("error", e)

	def _handle_receive_all_data(self, data: list[dict[str, Any]]) -> None:
		for item in data:
			if not isinstance(item, dict):
				continue
			cvid = item.get("cvid")
			name = item.get("name")
			value = item.get("value")
			data_type = item.get("type")
			if not all([cvid, name, value is not None, data_type is not None]):
				continue
			try:
				if data_type == KittenCloudDataType.PRIVATE_VARIABLE.value:
					variable = KittenCloudPrivateVariable(self, str(cvid), str(name), cast("CloudValueType", value))
					self.private_variables[str(name)] = variable
					self.private_variables[str(cvid)] = variable
				elif data_type == KittenCloudDataType.PUBLIC_VARIABLE.value:
					variable = KittenCloudPublicVariable(self, str(cvid), str(name), cast("CloudValueType", value))
					self.public_variables[str(name)] = variable
					self.public_variables[str(cvid)] = variable
				elif data_type == KittenCloudDataType.LIST.value:
					if not isinstance(value, list):
						value = []
					cloud_list = KittenCloudList(self, str(cvid), str(name), cast("CloudListValueType", value))
					self.lists[str(name)] = cloud_list
					self.lists[str(cvid)] = cloud_list
			except Exception as e:
				print(f"{ErrorMessages.CREATE_DATA_ITEM}: {e}")
				continue
		self.data_ready = True
		self._emit_event("data_ready")

	def _handle_update_private_variable(self, data: dict[str, Any]) -> None:
		if "cvid" in data and "value" in data:
			cvid = data["cvid"]
			new_value = data["value"]
			for var in self.private_variables.values():
				if var.cvid == cvid:
					old_value = var.value
					var.value = cast("CloudValueType", new_value)
					var.emit_change(old_value, new_value, "cloud")
					break

	def _handle_receive_ranking_list(self, data: Any) -> None:
		if not self._pending_ranking_requests:
			print(ErrorMessages.NO_PENDING_REQUESTS)
			return
		variable = self._pending_ranking_requests.pop(0)
		if not isinstance(data, dict) or "items" not in data or not isinstance(data["items"], list):
			print(f"{ErrorMessages.INVALID_RANKING_DATA}: {data}")
			return
		ranking_data = [
			{"value": item["value"], "user": {"id": int(item["identifier"]), "nickname": item["nickname"], "avatar_url": item["avatar_url"]}}
			for item in data["items"]
			if isinstance(item, dict) and all(key in item for key in ["value", "nickname", "avatar_url", "identifier"])
		]
		variable.emit_ranking(ranking_data)
		self._emit_event("ranking_received", variable, ranking_data)

	def _handle_update_public_variable(self, data: Any) -> None:
		if data == "fail":
			return
		if isinstance(data, list):
			for item in data:
				if isinstance(item, dict) and "cvid" in item and "value" in item:
					cvid = item["cvid"]
					new_value = item["value"]
					for var in self.public_variables.values():
						if var.cvid == cvid:
							old_value = var.value
							var.value = cast("CloudValueType", new_value)
							var.emit_change(old_value, new_value, "cloud")
							break

	def _handle_update_list(self, data: dict[str, list[dict[str, Any]]]) -> None:
		"""处理列表更新操作"""
		for cvid, operations in data.items():
			if cvid in self.lists:
				cloud_list = self.lists[cvid]
				self._process_list_operations(cloud_list, operations)

	def _process_list_operations(self, cloud_list: KittenCloudList, operations: list[dict[str, Any]]) -> None:
		"""处理单个列表的操作"""
		for operation in operations:
			if not isinstance(operation, dict) or "action" not in operation:
				continue
			self._execute_list_operation(cloud_list, operation)

	def _execute_list_operation(self, cloud_list: KittenCloudList, operation: dict[str, Any]) -> None:
		"""执行具体的列表操作"""
		action = operation["action"]
		if action == "append" and "value" in operation:
			cloud_list.push(cast("CloudValueType", operation["value"]))
		elif action == "unshift" and "value" in operation:
			cloud_list.unshift(cast("CloudValueType", operation["value"]))
		elif action == "insert" and "nth" in operation and "value" in operation:
			index = cast("int", operation["nth"]) - 1
			cloud_list.insert(index, cast("CloudValueType", operation["value"]))
		elif action == "delete":
			self._handle_delete_operation(cloud_list, operation)
		elif action == "replace" and "nth" in operation and "value" in operation:
			self._handle_replace_operation(cloud_list, operation)

	@staticmethod
	def _handle_delete_operation(cloud_list: KittenCloudList, operation: dict[str, Any]) -> None:
		"""处理删除操作"""
		nth = operation.get("nth")
		if nth == "last":
			cloud_list.pop()
		elif nth == "all":
			cloud_list.clear()
		elif isinstance(nth, int):
			index = nth - 1
			cloud_list.remove(index)

	@staticmethod
	def _handle_replace_operation(cloud_list: KittenCloudList, operation: dict[str, Any]) -> None:
		"""处理替换操作"""
		nth = operation["nth"]
		value = cast("CloudValueType", operation["value"])
		if nth == "last":
			cloud_list.replace_last(value)
		elif isinstance(nth, int):
			index = nth - 1
			cloud_list.replace(index, value)

	def _handle_update_online_users(self, data: dict[str, Any]) -> None:
		if "total" in data and isinstance(data["total"], int):
			old_count = self.online_users
			self.online_users = data["total"]
			self._emit_event("online_users_change", old_count, self.online_users)

	def _on_open(self, _ws: websocket.WebSocketApp) -> None:
		self.connected = True
		self.reconnect_attempts = 0

	def _on_close(self, _ws: websocket.WebSocketApp, close_status_code: int, close_msg: str) -> None:
		self.connected = False
		self.data_ready = False
		self._emit_event("close", close_status_code, close_msg)
		if self.auto_reconnect and self.reconnect_attempts < self.max_reconnect_attempts:
			self.reconnect_attempts += 1
			threading.Timer(self.reconnect_interval, self.connect).start()

	def _on_error(self, _ws: websocket.WebSocketApp, error: Exception) -> None:
		self._emit_event("error", error)

	def _send_message(self, message_type: KittenCloudSendMessageType, data: Any) -> None:
		if self.ws and self.connected:
			# 正确的 Socket.IO 消息格式:42["message_type", data]
			message_content = [message_type.value, data]
			message = f"{WEBSOCKET_EVENT_MESSAGE_PREFIX}{json.dumps(message_content)}"
			try:
				print(f"发送消息: {message}")  # 调试用 - 取消注释这行
				self.ws.send(message)
			except Exception as e:
				print(f"{ErrorMessages.SEND_MESSAGE}: {e}")
				self._emit_event("error", e)
		else:
			print(f"无法发送消息,连接状态: {self.connected}, WebSocket: {self.ws is not None}")

	def connect(self) -> None:
		try:
			# 重置连接状态
			self.connected = False
			self.data_ready = False
			if self.ws:
				with suppress(Exception):
					self.ws.close()
			url = self._get_websocket_url()
			headers = self._get_websocket_headers()
			print(f"正在连接到: {url}")  # 调试信息
			self.ws = websocket.WebSocketApp(url, header=headers, on_open=self._on_open, on_message=self._on_message, on_close=self._on_close, on_error=self._on_error)

			def run_ws() -> None:
				try:
					if self.ws:
						# 设置 ping 参数,启用更详细的日志
						self.ws.run_forever(
							ping_interval=MagicNumbers.WEBSOCKET_PING_INTERVAL,  # 20秒发送一次ping
							ping_timeout=MagicNumbers.WEBSOCKET_PING_TIMEOUT,  # 10秒超时
						)
				except Exception as e:
					print(f"{ErrorMessages.WEB_SOCKET_RUN}: {e}")

			thread = threading.Thread(target=run_ws, daemon=True)
			thread.start()
		except Exception as e:
			print(f"{ErrorMessages.CONNECTION}: {e}")
			self._emit_event("error", e)
			if self.auto_reconnect and self.reconnect_attempts < self.max_reconnect_attempts:
				self.reconnect_attempts += 1
				print(f"尝试重新连接 ({self.reconnect_attempts}/{self.max_reconnect_attempts})...")
				threading.Timer(self.reconnect_interval, self.connect).start()

	def close(self) -> None:
		self.auto_reconnect = False
		self.connected = False
		# 停止 ping 线程
		if self._ping_thread is not None:
			self._ping_thread = None
		if self.ws:
			try:
				self.ws.close()
			except Exception as e:
				print(f"{ErrorMessages.CLOSE_CONNECTION}: {e}")

	def wait_for_connection(self, timeout: int = MagicNumbers.CONNECTION_TIMEOUT) -> bool:
		start_time = time.time()
		while time.time() - start_time < timeout:
			if self.connected:
				return True
			time.sleep(0.1)
		return False

	def wait_for_data(self, timeout: int = MagicNumbers.DATA_TIMEOUT) -> bool:
		start_time = time.time()
		while time.time() - start_time < timeout:
			if self.data_ready:
				return True
			time.sleep(0.1)
		return False

	def get_private_variable(self, name: str) -> KittenCloudPrivateVariable | None:
		return self.private_variables.get(name)

	def get_public_variable(self, name: str) -> KittenCloudPublicVariable | None:
		return self.public_variables.get(name)

	def get_list(self, name: str) -> KittenCloudList | None:
		return self.lists.get(name)

	def get_all_private_variables(self) -> dict[str, KittenCloudPrivateVariable]:
		return {k: v for k, v in self.private_variables.items() if not k.startswith("_")}

	def get_all_public_variables(self) -> dict[str, KittenCloudPublicVariable]:
		return {k: v for k, v in self.public_variables.items() if not k.startswith("_")}

	def get_all_lists(self) -> dict[str, KittenCloudList]:
		return {k: v for k, v in self.lists.items() if not k.startswith("_")}

	def set_private_variable(self, name: str, value: int | str) -> bool:
		variable = self.get_private_variable(name)
		if variable and variable.set(value):
			self._send_message(
				KittenCloudSendMessageType.UPDATE_PRIVATE_VARIABLE, [{"cvid": variable.cvid, "value": value, "param_type": "number" if isinstance(value, int) else "string"}]
			)
			return True
		return False

	def set_public_variable(self, name: str, value: int | str) -> bool:
		variable = self.get_public_variable(name)
		if variable and variable.set(value):
			self._send_message(
				KittenCloudSendMessageType.UPDATE_PUBLIC_VARIABLE,
				[{"action": "set", "cvid": variable.cvid, "value": value, "param_type": "number" if isinstance(value, int) else "string"}],
			)
			return True
		return False

	def get_private_variable_ranking(self, name: str, limit: int = MagicNumbers.DEFAULT_RANKING_LIMIT, order: int = -1) -> None:
		variable = self.get_private_variable(name)
		if variable:
			self._pending_ranking_requests.append(variable)
			variable.get_ranking_list(limit, order)

	def list_push(self, name: str, value: int | str) -> bool:
		cloud_list = self.get_list(name)
		if cloud_list and cloud_list.push(value):
			self._send_message(KittenCloudSendMessageType.UPDATE_LIST, {cloud_list.cvid: [{"action": "append", "value": value}]})
			return True
		return False

	def list_pop(self, name: str) -> bool:
		cloud_list = self.get_list(name)
		if cloud_list and cloud_list.pop() is not None:
			self._send_message(KittenCloudSendMessageType.UPDATE_LIST, {cloud_list.cvid: [{"action": "delete", "nth": "last"}]})
			return True
		return False

	def list_unshift(self, name: str, value: int | str) -> bool:
		cloud_list = self.get_list(name)
		if cloud_list and cloud_list.unshift(value):
			self._send_message(KittenCloudSendMessageType.UPDATE_LIST, {cloud_list.cvid: [{"action": "unshift", "value": value}]})
			return True
		return False

	def list_insert(self, name: str, index: int, value: int | str) -> bool:
		cloud_list = self.get_list(name)
		if cloud_list and cloud_list.insert(index, value):
			self._send_message(KittenCloudSendMessageType.UPDATE_LIST, {cloud_list.cvid: [{"action": "insert", "nth": index + 1, "value": value}]})
			return True
		return False

	def list_remove(self, name: str, index: int) -> bool:
		cloud_list = self.get_list(name)
		if cloud_list and cloud_list.remove(index) is not None:
			self._send_message(KittenCloudSendMessageType.UPDATE_LIST, {cloud_list.cvid: [{"action": "delete", "nth": index + 1}]})
			return True
		return False

	def list_replace(self, name: str, index: int, value: int | str) -> bool:
		cloud_list = self.get_list(name)
		if cloud_list and cloud_list.replace(index, value):
			self._send_message(KittenCloudSendMessageType.UPDATE_LIST, {cloud_list.cvid: [{"action": "replace", "nth": index + 1, "value": value}]})
			return True
		return False

	def list_replace_last(self, name: str, value: int | str) -> bool:
		cloud_list = self.get_list(name)
		if cloud_list and cloud_list.replace_last(value):
			self._send_message(KittenCloudSendMessageType.UPDATE_LIST, {cloud_list.cvid: [{"action": "replace", "nth": "last", "value": value}]})
			return True
		return False

	def list_clear(self, name: str) -> bool:
		cloud_list = self.get_list(name)
		if cloud_list and cloud_list.clear():
			self._send_message(KittenCloudSendMessageType.UPDATE_LIST, {cloud_list.cvid: [{"action": "delete", "nth": "all"}]})
			return True
		return False

	def print_all_data(self) -> None:
		print("\n" + "=" * 50)
		print("云数据汇总")
		print("=" * 50)
		print("\n=== 公有变量 ===")
		public_vars = self.get_all_public_variables()
		if public_vars:
			for name, variable in public_vars.items():
				print(f"  {name}: {variable.get()}")
		else:
			print("  无公有变量")
		print("\n=== 私有变量 ===")
		private_vars = self.get_all_private_variables()
		if private_vars:
			for name, variable in private_vars.items():
				print(f"  {name}: {variable.get()}")
		else:
			print("  无私有变量")
		print("\n=== 云列表 ===")
		lists = self.get_all_lists()
		if lists:
			for name, cloud_list in lists.items():
				print(f"  {name}: {cloud_list.value} (长度: {cloud_list.length()})")
		else:
			print("  无云列表")
		print(f"\n在线用户数: {self.online_users}")
		print("=" * 50)


def main() -> None:
	authorization_token = input("请输入你的Authorization token: ").strip()
	if not authorization_token:
		print("未提供token,使用匿名连接")
		authorization_token = None
	work_id_input = input("请输入作品ID: ").strip()
	if not work_id_input:
		print("作品ID不能为空")
		return
	try:
		work_id = int(work_id_input)
	except ValueError:
		print("作品ID必须是数字")
		return
	cloud = KittenCloudFunction(work_id=work_id, editor=CodemaoWorkEditor.KITTEN, authorization_token=authorization_token)

	def on_open() -> None:
		print("连接成功")

	def on_close(code: int, msg: str) -> None:
		print(f"连接关闭: {code} - {msg}")

	def on_error(error: Exception) -> None:
		print(f"错误: {error}")

	def on_data_ready() -> None:
		print("数据准备完成")
		cloud.print_all_data()

	def on_online_users_change(old_count: int, new_count: int) -> None:
		print(f"在线用户数变化: {old_count} -> {new_count}")

	def on_ranking_received(variable: KittenCloudPrivateVariable, ranking_data: list[dict[str, Any]]) -> None:
		print(f"\n=== {variable.name} 排行榜 ===")
		for i, item in enumerate(ranking_data, 1):
			user_info = item["user"]
			print(f"{i}. {item['value']} - {user_info['nickname']} (ID: {user_info['id']})")

	cloud.on("open", on_open)
	cloud.on("close", on_close)
	cloud.on("error", on_error)
	cloud.on_data_ready(on_data_ready)
	cloud.on_online_users_change(on_online_users_change)
	cloud.on_ranking_received(on_ranking_received)
	print("正在连接...")
	cloud.connect()
	print("等待连接建立...")
	if cloud.wait_for_connection(timeout=MagicNumbers.WAIT_TIMEOUT):
		print("连接建立成功,等待数据...")
		if cloud.wait_for_data(timeout=MagicNumbers.WAIT_TIMEOUT):
			print("数据加载完成!")
			private_vars = cloud.get_all_private_variables()
			if private_vars:
				first_var_name = next(iter(private_vars.keys()))
				print(f"\n获取 {first_var_name} 的排行榜...")
				cloud.get_private_variable_ranking(first_var_name, limit=10, order=-1)
		else:
			print("数据加载超时")
	else:
		print("连接超时")
	try:
		print("\n程序运行中,按 Ctrl+C 退出...")
		while True:
			time.sleep(1)
	except KeyboardInterrupt:
		print("\n正在关闭连接...")
		cloud.close()


def simple_test() -> None:
	"""简单的测试函数"""
	# 注意:这里使用了示例token,实际使用时应该从环境变量或输入获取
	authorization_token = "your_token_here"  # 替换为实际的token
	work_id = 57074555
	cloud = KittenCloudFunction(work_id, authorization_token=authorization_token)

	def on_open() -> None:
		print("✅ 连接成功")

	def on_data_ready() -> None:
		print("✅ 数据加载完成")
		print(f"私有变量数量: {len(cloud.private_variables)}")
		print(f"公有变量数量: {len(cloud.public_variables)}")
		print(f"云列表数量: {len(cloud.lists)}")
		cloud.print_all_data()

	cloud.on("open", on_open)
	cloud.on_data_ready(on_data_ready)
	cloud.connect()
	# 等待更长时间
	time.sleep(10)
	if not cloud.data_ready:
		print("❌ 数据仍未加载,可能原因:")
		print("   - 作品不存在云变量")
		print("   - token权限不足")
		print("   - 网络问题")
		print("   - 作品ID错误")


if __name__ == "__main__":
	# 可以选择运行简单测试或完整的主函数
	# simple_test()
	main()
