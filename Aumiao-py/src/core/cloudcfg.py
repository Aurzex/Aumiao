import cmd
import hashlib
import json
import shlex
import threading
import time
import traceback
import uuid
from collections.abc import Callable
from contextlib import suppress
from enum import Enum
from typing import Any, cast

import httpx
import websocket

# 常量定义
HTTP_SUCCESS_CODE = 200
WEBSOCKET_PING_MESSAGE = "2"
WEBSOCKET_PONG_MESSAGE = "3"
WEBSOCKET_CONNECT_MESSAGE = "40"
WEBSOCKET_CONNECTED_MESSAGE = "40"
WEBSOCKET_EVENT_MESSAGE_PREFIX = "42"
WEBSOCKET_HANDSHAKE_MESSAGE_PREFIX = "0"
# 错误消息常量
ERROR_CALLBACK_EXECUTION = "回调执行错误"
ERROR_CLOUD_VARIABLE_CALLBACK = "云变量变更回调执行错误"
ERROR_RANKING_CALLBACK = "排行榜回调执行错误"
ERROR_OPERATION_CALLBACK = "操作回调执行错误"
ERROR_EVENT_CALLBACK = "事件回调执行错误"
ERROR_SEND_MESSAGE = "发送消息错误"
ERROR_CONNECTION = "连接错误"
ERROR_WEB_SOCKET_RUN = "WebSocket运行错误"
ERROR_CLOSE_CONNECTION = "关闭连接时出错"
ERROR_GET_SERVER_TIME = "获取服务器时间失败"
ERROR_HANDSHAKE_DATA_PARSE = "握手数据解析失败"
ERROR_HANDSHAKE_PROCESSING = "握手处理错误"
ERROR_JSON_PARSE = "JSON解析错误"
ERROR_CLOUD_MESSAGE_PROCESSING = "云消息处理错误"
ERROR_CREATE_DATA_ITEM = "创建数据项时出错"
ERROR_INVALID_RANKING_DATA = "无效的排行榜数据格式"
ERROR_PING_SEND = "发送 ping 失败"
ERROR_NO_PENDING_REQUESTS = "收到排行榜数据但没有待处理的请求"
# 魔法数值常量
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
MESSAGE_TYPE_LENGTH = 2
WEBSOCKET_TRANSPORT_TYPE = "websocket"  # 修复类型错误


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
			error_msg = f"{ERROR_GET_SERVER_TIME}: {e}"
			print(error_msg)
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
				error_msg = f"{ERROR_CALLBACK_EXECUTION}: {e}"
				print(error_msg)


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
			error_msg = "云变量值必须是整数或字符串"
			raise TypeError(error_msg)
		old_value = self.value
		self.value = value
		self.emit_change(cast("CloudValueType", old_value), value, "local")
		return True

	def emit_change(self, old_value: CloudValueType | CloudListValueType, new_value: CloudValueType | CloudListValueType, source: str) -> None:
		"""修复方法重写不兼容问题"""
		if not isinstance(old_value, (int, str)) or not isinstance(new_value, (int, str)):
			print(f"警告: 云变量值类型不匹配, 期望 int 或 str, 得到 old_value: {type(old_value)}, new_value: {type(new_value)}")
			return
		old_value_cast = cast("CloudValueType", old_value)
		new_value_cast = cast("CloudValueType", new_value)
		for callback in self._change_callbacks:
			try:
				callback(old_value_cast, new_value_cast, source)
			except Exception as e:
				error_msg = f"{ERROR_CLOUD_VARIABLE_CALLBACK}: {e}"
				print(error_msg)


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
				error_msg = f"{ERROR_RANKING_CALLBACK}: {e}"
				print(error_msg)

	def get_ranking_list(self, limit: int = DEFAULT_RANKING_LIMIT, order: int = -1) -> None:
		if not isinstance(limit, int) or limit <= 0:
			error_msg = "限制数量必须是正整数"
			raise ValueError(error_msg)
		if order not in {1, -1}:
			error_msg = "排序顺序必须是1(正序)或-1(逆序)"
			raise ValueError(error_msg)
		request_data = {"cvid": self.cvid, "limit": limit, "order_type": order}
		self.connection.send_message(KittenCloudSendMessageType.GET_PRIVATE_VARIABLE_RANKING_LIST, request_data)


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
				error_msg = f"{ERROR_OPERATION_CALLBACK}: {e}"
				print(error_msg)

	def get(self, index: int) -> CloudValueType | None:
		if 0 <= index < len(self.value):
			return self.value[index]
		return None

	def push(self, item: CloudValueType) -> bool:
		if not isinstance(item, (int, str)):
			error_msg = "列表元素必须是整数或字符串"
			raise TypeError(error_msg)
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
			error_msg = "列表元素必须是整数或字符串"
			raise TypeError(error_msg)
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
			error_msg = "列表元素必须是整数或字符串"
			raise TypeError(error_msg)
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
			error_msg = "列表元素必须是整数或字符串"
			raise TypeError(error_msg)
		if 0 <= index < len(self.value):
			old_item = self.value[index]
			self.value[index] = item
			self._emit_operation("replace", old_item, item, index)
			return True
		return False

	def replace_last(self, item: CloudValueType) -> bool:
		if not isinstance(item, (int, str)):
			error_msg = "列表元素必须是整数或字符串"
			raise TypeError(error_msg)
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
		self.reconnect_interval = RECONNECT_INTERVAL
		self.reconnect_attempts = 0
		self.max_reconnect_attempts = MAX_RECONNECT_ATTEMPTS
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
		self._ping_active = False
		self._join_sent = False  # 新增:标记是否已发送JOIN消息

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
					error_msg = f"{ERROR_EVENT_CALLBACK}: {e}"
					print(error_msg)

	def _get_websocket_url(self) -> str:
		base_params = {
			CodemaoWorkEditor.NEMO: {"authorization_type": 5, "stag": 2},
			CodemaoWorkEditor.KITTEN: {"authorization_type": 1, "stag": 1},
			CodemaoWorkEditor.KITTEN_N: {"authorization_type": 5, "stag": 3, "token": ""},
			CodemaoWorkEditor.COCO: {"authorization_type": 1, "stag": 1},
		}
		params = base_params.get(self.editor, base_params[CodemaoWorkEditor.KITTEN])
		params["EIO"] = "3"  # Engine.IO 版本
		params["transport"] = WEBSOCKET_TRANSPORT_TYPE
		params_str = "&".join([f"{k}={v}" for k, v in params.items()])
		return f"wss://socketcv.codemao.cn:9096/cloudstorage/?session_id={self.work_id}&{params_str}"

	def _get_websocket_headers(self) -> dict[str, str]:
		headers: dict[str, str] = {}
		device_auth = self.auth.generate_device_auth()
		headers["X-Creation-Tools-Device-Auth"] = json.dumps(device_auth)
		if self.auth.authorization_token:
			headers["Cookie"] = f"Authorization={self.auth.authorization_token}"
		return headers

	def _on_message(self, _ws: websocket.WebSocketApp, message: str | bytes) -> None:
		if isinstance(message, bytes):
			message = message.decode("utf-8")
		message_str = str(message)  # 确保是字符串类型
		# 处理ping-pong
		if message_str == WEBSOCKET_PING_MESSAGE:
			if self.ws:
				self.ws.send(WEBSOCKET_PONG_MESSAGE)
			return
		# 处理握手
		if message_str.startswith(WEBSOCKET_HANDSHAKE_MESSAGE_PREFIX):
			try:
				handshake_data = json.loads(message_str[1:])
				ping_interval = handshake_data.get("pingInterval", PING_INTERVAL_MS)
				ping_timeout = handshake_data.get("pingTimeout", PING_TIMEOUT_MS)
				print(f"握手成功,ping间隔: {ping_interval}ms, ping超时: {ping_timeout}ms")
				self._start_ping(ping_interval, ping_timeout)
				# 发送连接请求
				if self.ws:
					self.ws.send(WEBSOCKET_CONNECT_MESSAGE)
					print("已发送连接请求")
			except Exception as e:
				error_msg = f"{ERROR_HANDSHAKE_PROCESSING}: {e}"
				print(error_msg)
			return
		# 处理连接确认
		if message_str == WEBSOCKET_CONNECTED_MESSAGE:
			self.connected = True
			print("连接确认收到")
			self._emit_event("open")
			# 延迟发送JOIN消息,确保连接稳定
			if not self._join_sent:
				self._join_sent = True
				threading.Timer(0.5, self._send_join_message).start()
			return
		# 处理事件消息
		if message_str.startswith(WEBSOCKET_EVENT_MESSAGE_PREFIX):
			data_str = message_str[MESSAGE_TYPE_LENGTH:]
			try:
				data_list = json.loads(data_str)
				if isinstance(data_list, list) and len(data_list) >= 2:
					message_type = data_list[0]
					message_data = data_list[1]
					print(f"处理云消息: {message_type}, 数据: {message_data}")
					if isinstance(message_data, str):
						message_data = json.loads(message_data)
					self._handle_cloud_message(message_type, message_data)
			except json.JSONDecodeError as e:
				error_msg = f"{ERROR_JSON_PARSE}: {e}, 数据: {data_str}"
				print(error_msg)
			return

	def _send_join_message(self) -> None:
		"""发送JOIN消息"""
		if self.connected and self.ws:
			print("发送JOIN消息...")
			self.send_message(KittenCloudSendMessageType.JOIN, str(self.work_id))

	def _start_ping(self, interval: int, _timeout: int) -> None:
		"""启动 ping-pong 保活机制"""
		if self._ping_thread is not None:
			self._ping_active = False
			self._ping_thread.join(timeout=1.0)
		self._ping_active = True

		def ping_task() -> None:
			while self._ping_active and self.connected:
				time.sleep(interval / 1000)
				if self._ping_active and self.connected and self.ws:
					try:
						self.ws.send(WEBSOCKET_PING_MESSAGE)
						print(f"发送 ping, 间隔: {interval}ms")
					except Exception as e:
						error_msg = f"{ERROR_PING_SEND}: {e}"
						print(error_msg)
						break

		self._ping_thread = threading.Thread(target=ping_task, daemon=True)
		self._ping_thread.start()
		print(f"Ping 线程已启动,间隔: {interval}ms")

	def _stop_ping(self) -> None:
		"""停止 ping 线程"""
		self._ping_active = False
		if self._ping_thread is not None:
			self._ping_thread.join(timeout=2.0)
			self._ping_thread = None

	def _handle_cloud_message(self, message_type: str, data: dict[str, Any] | list[Any] | str) -> None:
		try:
			print(f"处理云消息: {message_type}, 数据: {data}")
			if message_type == KittenCloudReceiveMessageType.JOIN.value:
				print("连接加入成功,请求所有数据...")
				self.send_message(KittenCloudSendMessageType.GET_ALL_DATA, {})
			elif message_type == KittenCloudReceiveMessageType.RECEIVE_ALL_DATA.value:
				print("收到完整数据响应")
				self._handle_receive_all_data(data)
			elif message_type == KittenCloudReceiveMessageType.UPDATE_PRIVATE_VARIABLE.value:
				print("更新私有变量")
				self._handle_update_private_variable(data)
			elif message_type == KittenCloudReceiveMessageType.RECEIVE_PRIVATE_VARIABLE_RANKING_LIST.value:
				print("收到排行榜数据")
				self._handle_receive_ranking_list(data)
			elif message_type == KittenCloudReceiveMessageType.UPDATE_PUBLIC_VARIABLE.value:
				print("更新公有变量")
				self._handle_update_public_variable(data)
			elif message_type == KittenCloudReceiveMessageType.UPDATE_LIST.value:
				print("更新列表")
				self._handle_update_list(data)
			elif message_type == KittenCloudReceiveMessageType.UPDATE_ONLINE_USER_NUMBER.value:
				print("更新在线用户数")
				self._handle_update_online_users(data)
			elif message_type == KittenCloudReceiveMessageType.ILLEGAL_EVENT.value:
				print(f"非法事件: {data}")
			else:
				print(f"未知消息类型: {message_type}, 数据: {data}")
		except Exception as e:
			error_msg = f"{ERROR_CLOUD_MESSAGE_PROCESSING}: {e}"
			print(error_msg)
			traceback.print_exc()
			self._emit_event("error", e)

	def _handle_receive_all_data(self, data: list[dict[str, Any]] | Any) -> None:
		"""完善的数据接收处理"""
		print(f"收到完整数据: {data}")
		if not isinstance(data, list):
			print(f"数据格式错误,期望列表,得到: {type(data)}")
			return
		for item in data:
			if not isinstance(item, dict):
				print(f"数据项格式错误: {item}")
				continue
			try:
				cvid = item.get("cvid")
				name = item.get("name")
				value = item.get("value")
				data_type = item.get("type")
				if not all([cvid, name, value is not None, data_type is not None]):
					print(f"数据项缺少必要字段: {item}")
					continue
				print(f"处理数据项: {name}({cvid}) = {value}, 类型: {data_type}")
				if data_type == KittenCloudDataType.PRIVATE_VARIABLE.value:
					variable = KittenCloudPrivateVariable(self, str(cvid), str(name), cast("CloudValueType", value))
					self.private_variables[str(name)] = variable
					self.private_variables[str(cvid)] = variable
					print(f"创建私有变量: {name}")
				elif data_type == KittenCloudDataType.PUBLIC_VARIABLE.value:
					variable = KittenCloudPublicVariable(self, str(cvid), str(name), cast("CloudValueType", value))
					self.public_variables[str(name)] = variable
					self.public_variables[str(cvid)] = variable
					print(f"创建公有变量: {name}")
				elif data_type == KittenCloudDataType.LIST.value:
					if not isinstance(value, list):
						value = []
					cloud_list = KittenCloudList(self, str(cvid), str(name), cast("CloudListValueType", value))
					self.lists[str(name)] = cloud_list
					self.lists[str(cvid)] = cloud_list
					print(f"创建云列表: {name}, 长度: {len(value)}")
			except Exception as e:
				error_msg = f"{ERROR_CREATE_DATA_ITEM}: {e}, 数据: {item}"
				print(error_msg)
				continue
		self.data_ready = True
		print(f"数据准备完成! 私有变量: {len(self.private_variables)}, 公有变量: {len(self.public_variables)}, 列表: {len(self.lists)}")
		self._emit_event("data_ready")

	def _handle_update_private_variable(self, data: dict[str, Any] | Any) -> None:
		if isinstance(data, dict) and "cvid" in data and "value" in data:
			cvid = data["cvid"]
			new_value = data["value"]
			for var in self.private_variables.values():
				if var.cvid == cvid:
					old_value = var.value
					var.value = cast("CloudValueType", new_value)
					var.emit_change(old_value, new_value, "cloud")
					break

	def _handle_receive_ranking_list(self, data: dict[str, Any] | Any) -> None:
		if not self._pending_ranking_requests:
			print(ERROR_NO_PENDING_REQUESTS)
			return
		variable = self._pending_ranking_requests.pop(0)
		if not isinstance(data, dict) or "items" not in data or not isinstance(data["items"], list):
			error_msg = f"{ERROR_INVALID_RANKING_DATA}: {data}"
			print(error_msg)
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

	def _handle_update_list(self, data: dict[str, list[dict[str, Any]]] | Any) -> None:
		"""处理列表更新操作"""
		if not isinstance(data, dict):
			return
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

	def _handle_update_online_users(self, data: dict[str, Any] | Any) -> None:
		if isinstance(data, dict) and "total" in data and isinstance(data["total"], int):
			old_count = self.online_users
			self.online_users = data["total"]
			self._emit_event("online_users_change", old_count, self.online_users)

	def _on_open(self, _ws: websocket.WebSocketApp) -> None:
		self.connected = True
		self.reconnect_attempts = 0

	def _on_close(self, _ws: websocket.WebSocketApp, close_status_code: int, close_msg: str) -> None:
		self.connected = False
		self.data_ready = False
		self._join_sent = False  # 重置JOIN标记
		self._stop_ping()
		self._emit_event("close", close_status_code, close_msg)
		if self.auto_reconnect and self.reconnect_attempts < self.max_reconnect_attempts:
			self.reconnect_attempts += 1
			threading.Timer(self.reconnect_interval, self.connect).start()

	def _on_error(self, _ws: websocket.WebSocketApp, error: Exception) -> None:
		self._emit_event("error", error)

	def send_message(self, message_type: KittenCloudSendMessageType, data: dict[str, Any] | list[Any] | str) -> None:
		if self.ws and self.connected:
			# 使用正确的Socket.IO格式
			message_content = [message_type.value, data]
			message = f"{WEBSOCKET_EVENT_MESSAGE_PREFIX}{json.dumps(message_content)}"
			try:
				print(f"发送消息: {message}")
				self.ws.send(message)
			except Exception as e:
				error_msg = f"{ERROR_SEND_MESSAGE}: {e}"
				print(error_msg)
				self._emit_event("error", e)
		else:
			print(f"无法发送消息,连接状态: {self.connected}, WebSocket: {self.ws is not None}")

	def connect(self) -> None:
		"""改进的连接方法"""
		try:
			self.connected = False
			self.data_ready = False
			self._join_sent = False  # 重置JOIN标记
			self.private_variables.clear()
			self.public_variables.clear()
			self.lists.clear()
			if self.ws:
				with suppress(Exception):
					self.ws.close()
			url = self._get_websocket_url()
			headers = self._get_websocket_headers()
			print(f"正在连接到: {url}")
			print(f"请求头: {headers}")
			self.ws = websocket.WebSocketApp(url, header=headers, on_open=self._on_open, on_message=self._on_message, on_close=self._on_close, on_error=self._on_error)

			def run_ws() -> None:
				try:
					if self.ws:
						self.ws.run_forever(
							ping_interval=30,
							ping_timeout=10,
							skip_utf8_validation=True,
						)
				except Exception as e:
					error_msg = f"{ERROR_WEB_SOCKET_RUN}: {e}"
					print(error_msg)

			thread = threading.Thread(target=run_ws, daemon=True)
			thread.start()
		except Exception as e:
			error_msg = f"{ERROR_CONNECTION}: {e}"
			print(error_msg)
			self._emit_event("error", e)

	def close(self) -> None:
		self.auto_reconnect = False
		self.connected = False
		self._stop_ping()
		if self.ws:
			try:
				self.ws.close()
			except Exception as e:
				error_msg = f"{ERROR_CLOSE_CONNECTION}: {e}"
				print(error_msg)

	def wait_for_connection(self, timeout: int = CONNECTION_TIMEOUT) -> bool:
		"""等待连接建立完成"""
		start_time = time.time()
		last_log_time = start_time
		while time.time() - start_time < timeout:
			if self.connected:
				return True
			# 每3秒输出一次状态
			current_time = time.time()
			if current_time - last_log_time >= 3:
				elapsed = current_time - start_time
				print(f"等待连接中... 已等待 {elapsed:.1f} 秒")
				last_log_time = current_time
			time.sleep(0.1)
		print(f"连接超时,等待 {timeout} 秒后仍未建立连接")
		return False

	def wait_for_data(self, timeout: int = DATA_TIMEOUT) -> bool:
		"""等待数据加载完成,带详细日志"""
		start_time = time.time()
		last_log_time = start_time
		while time.time() - start_time < timeout:
			if self.data_ready:
				print("数据加载完成!")
				return True
			# 每5秒输出一次状态
			current_time = time.time()
			if current_time - last_log_time >= 5:
				elapsed = current_time - start_time
				print(f"等待数据中... 已等待 {elapsed:.1f} 秒, 连接状态: {self.connected}")
				last_log_time = current_time
			time.sleep(0.1)
		print(f"数据加载超时,等待 {timeout} 秒后仍未收到数据")
		print(f"最终状态 - 连接: {self.connected}, 数据就绪: {self.data_ready}")
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
			self.send_message(
				KittenCloudSendMessageType.UPDATE_PRIVATE_VARIABLE, [{"cvid": variable.cvid, "value": value, "param_type": "number" if isinstance(value, int) else "string"}]
			)
			return True
		return False

	def set_public_variable(self, name: str, value: int | str) -> bool:
		variable = self.get_public_variable(name)
		if variable and variable.set(value):
			self.send_message(
				KittenCloudSendMessageType.UPDATE_PUBLIC_VARIABLE,
				[{"action": "set", "cvid": variable.cvid, "value": value, "param_type": "number" if isinstance(value, int) else "string"}],
			)
			return True
		return False

	def get_private_variable_ranking(self, name: str, limit: int = DEFAULT_RANKING_LIMIT, order: int = -1) -> None:
		variable = self.get_private_variable(name)
		if variable:
			self._pending_ranking_requests.append(variable)
			variable.get_ranking_list(limit, order)

	def list_push(self, name: str, value: int | str) -> bool:
		cloud_list = self.get_list(name)
		if cloud_list and cloud_list.push(value):
			self.send_message(KittenCloudSendMessageType.UPDATE_LIST, {cloud_list.cvid: [{"action": "append", "value": value}]})
			return True
		return False

	def list_pop(self, name: str) -> bool:
		cloud_list = self.get_list(name)
		if cloud_list and cloud_list.pop() is not None:
			self.send_message(KittenCloudSendMessageType.UPDATE_LIST, {cloud_list.cvid: [{"action": "delete", "nth": "last"}]})
			return True
		return False

	def list_unshift(self, name: str, value: int | str) -> bool:
		cloud_list = self.get_list(name)
		if cloud_list and cloud_list.unshift(value):
			self.send_message(KittenCloudSendMessageType.UPDATE_LIST, {cloud_list.cvid: [{"action": "unshift", "value": value}]})
			return True
		return False

	def list_shift(self, name: str) -> bool:
		cloud_list = self.get_list(name)
		if cloud_list and cloud_list.shift() is not None:
			self.send_message(KittenCloudSendMessageType.UPDATE_LIST, {cloud_list.cvid: [{"action": "delete", "nth": 1}]})
			return True
		return False

	def list_insert(self, name: str, index: int, value: int | str) -> bool:
		cloud_list = self.get_list(name)
		if cloud_list and cloud_list.insert(index, value):
			self.send_message(KittenCloudSendMessageType.UPDATE_LIST, {cloud_list.cvid: [{"action": "insert", "nth": index + 1, "value": value}]})
			return True
		return False

	def list_remove(self, name: str, index: int) -> bool:
		cloud_list = self.get_list(name)
		if cloud_list and cloud_list.remove(index) is not None:
			self.send_message(KittenCloudSendMessageType.UPDATE_LIST, {cloud_list.cvid: [{"action": "delete", "nth": index + 1}]})
			return True
		return False

	def list_replace(self, name: str, index: int, value: int | str) -> bool:
		cloud_list = self.get_list(name)
		if cloud_list and cloud_list.replace(index, value):
			self.send_message(KittenCloudSendMessageType.UPDATE_LIST, {cloud_list.cvid: [{"action": "replace", "nth": index + 1, "value": value}]})
			return True
		return False

	def list_replace_last(self, name: str, value: int | str) -> bool:
		cloud_list = self.get_list(name)
		if cloud_list and cloud_list.replace_last(value):
			self.send_message(KittenCloudSendMessageType.UPDATE_LIST, {cloud_list.cvid: [{"action": "replace", "nth": "last", "value": value}]})
			return True
		return False

	def list_clear(self, name: str) -> bool:
		cloud_list = self.get_list(name)
		if cloud_list and cloud_list.clear():
			self.send_message(KittenCloudSendMessageType.UPDATE_LIST, {cloud_list.cvid: [{"action": "delete", "nth": "all"}]})
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


class CloudCLI(cmd.Cmd):
	"""云数据交互式命令行界面"""

	def __init__(self, cloud: KittenCloudFunction) -> None:
		super().__init__()
		self.cloud = cloud
		self.prompt = "云数据> "
		self.intro = "欢迎使用云数据交互式命令行!输入 help 或 ? 查看可用命令。"

	def preloop(self) -> None:
		"""在循环开始前检查连接状态"""
		if not self.cloud.connected:
			print("警告:云连接未建立,请先等待连接成功")

	def do_status(self, arg: str) -> None:
		"""查看连接状态和数据状态"""
		print(f"连接状态: {'已连接' if self.cloud.connected else '未连接'}")
		print(f"数据就绪: {'是' if self.cloud.data_ready else '否'}")
		print(f"在线用户: {self.cloud.online_users}")

	def do_list(self, arg: str) -> None:
		"""列出所有数据
		用法: list [type]
		type: private(私有变量) / public(公有变量) / lists(列表) / all(全部)"""
		args = shlex.split(arg)
		show_type = args[0] if args else "all"
		show_types = {"all", "private", "public", "lists"}
		if show_type not in show_types:
			print(f"错误:类型必须是 {', '.join(show_types)} 之一")
			return
		if show_type in {"all", "private"}:
			print("\n=== 私有变量 ===")
			private_vars = self.cloud.get_all_private_variables()
			if private_vars:
				for name, var in private_vars.items():
					print(f"  {name}: {var.get()}")
			else:
				print("  无私有变量")
		if show_type in {"all", "public"}:
			print("\n=== 公有变量 ===")
			public_vars = self.cloud.get_all_public_variables()
			if public_vars:
				for name, var in public_vars.items():
					print(f"  {name}: {var.get()}")
			else:
				print("  无公有变量")
		if show_type in {"all", "lists"}:
			print("\n=== 云列表 ===")
			lists = self.cloud.get_all_lists()
			if lists:
				for name, cloud_list in lists.items():
					print(f"  {name}: {cloud_list.value} (长度: {cloud_list.length()})")
			else:
				print("  无云列表")

	def do_get(self, arg: str) -> None:
		"""获取特定变量的值
		用法: get <变量名>"""
		if not arg:
			print("错误:请指定变量名")
			return
		name = arg.strip()
		# 尝试在私有变量中查找
		private_var = self.cloud.get_private_variable(name)
		if private_var:
			print(f"私有变量 {name}: {private_var.get()}")
			return
		# 尝试在公有变量中查找
		public_var = self.cloud.get_public_variable(name)
		if public_var:
			print(f"公有变量 {name}: {public_var.get()}")
			return
		# 尝试在列表中查找
		cloud_list = self.cloud.get_list(name)
		if cloud_list:
			print(f"云列表 {name}: {cloud_list.value} (长度: {cloud_list.length()})")
			return
		print(f"错误:未找到变量或列表 '{name}'")

	def do_set_private(self, arg: str) -> None:
		"""设置私有变量的值
		用法: set_private <变量名> <值>"""
		args = shlex.split(arg)
		if len(args) < 2:
			print("错误:用法: set_private <变量名> <值>")
			return
		name = args[0]
		value = args[1]
		# 尝试转换为数字
		try:
			if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
				value = int(value)
		except Exception:
			pass  # 保持为字符串
		if self.cloud.set_private_variable(name, value):
			print(f"成功设置私有变量 {name} = {value}")
		else:
			print(f"错误:设置私有变量失败,请检查变量名 '{name}'")

	def do_set_public(self, arg: str) -> None:
		"""设置公有变量的值
		用法: set_public <变量名> <值>"""
		args = shlex.split(arg)
		if len(args) < 2:
			print("错误:用法: set_public <变量名> <值>")
			return
		name = args[0]
		value = args[1]
		# 尝试转换为数字
		try:
			if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
				value = int(value)
		except Exception:
			pass  # 保持为字符串
		if self.cloud.set_public_variable(name, value):
			print(f"成功设置公有变量 {name} = {value}")
		else:
			print(f"错误:设置公有变量失败,请检查变量名 '{name}'")

	def do_list_operations(self, arg: str) -> None:
		"""云列表操作
		用法:
			list_operations push <列表名> <值>      # 追加元素
			list_operations pop <列表名>            # 弹出最后一个元素
			list_operations unshift <列表名> <值>   # 在开头添加元素
			list_operations shift <列表名>          # 移除第一个元素
			list_operations insert <列表名> <位置> <值>  # 在指定位置插入
			list_operations remove <列表名> <位置>  # 移除指定位置元素
			list_operations replace <列表名> <位置> <值> # 替换指定位置元素
			list_operations clear <列表名>          # 清空列表
			list_operations get <列表名> <位置>     # 获取指定位置元素
		"""
		args = shlex.split(arg)
		if len(args) < 2:
			print("错误:参数不足")
			self.help_list_operations()
			return
		operation = args[0]
		list_name = args[1]
		cloud_list = self.cloud.get_list(list_name)
		if not cloud_list:
			print(f"错误:未找到列表 '{list_name}'")
			return
		if operation == "push":
			if len(args) < 3:
				print("错误:需要提供要添加的值")
				return
			value = args[2]
			try:
				if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
					value = int(value)
			except Exception:
				pass  # 保持为字符串
			if self.cloud.list_push(list_name, value):
				print(f"成功向列表 {list_name} 添加元素: {value}")
			else:
				print("添加元素失败")
		elif operation == "pop":
			if self.cloud.list_pop(list_name):
				print(f"成功弹出列表 {list_name} 的最后一个元素")
			else:
				print("弹出元素失败")
		elif operation == "unshift":
			if len(args) < 3:
				print("错误:需要提供要添加的值")
				return
			value = args[2]
			try:
				if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
					value = int(value)
			except Exception:
				pass  # 保持为字符串
			if self.cloud.list_unshift(list_name, value):
				print(f"成功在列表 {list_name} 开头添加元素: {value}")
			else:
				print("添加元素失败")
		elif operation == "shift":
			if self.cloud.list_shift(list_name):
				print(f"成功移除列表 {list_name} 的第一个元素")
			else:
				print("移除元素失败")
		elif operation == "insert":
			if len(args) < 4:
				print("错误:需要提供位置和值")
				return
			try:
				index = int(args[2])
				value = args[3]
				try:
					if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
						value = int(value)
				except Exception:
					pass  # 保持为字符串
				if self.cloud.list_insert(list_name, index, value):
					print(f"成功在列表 {list_name} 的位置 {index} 插入元素: {value}")
				else:
					print("插入元素失败")
			except ValueError:
				print("错误:位置必须是数字")
		elif operation == "remove":
			if len(args) < 3:
				print("错误:需要提供位置")
				return
			try:
				index = int(args[2])
				if self.cloud.list_remove(list_name, index):
					print(f"成功移除列表 {list_name} 位置 {index} 的元素")
				else:
					print("移除元素失败")
			except ValueError:
				print("错误:位置必须是数字")
		elif operation == "replace":
			if len(args) < 4:
				print("错误:需要提供位置和新值")
				return
			try:
				index = int(args[2])
				value = args[3]
				try:
					if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
						value = int(value)
				except Exception:
					pass  # 保持为字符串
				if self.cloud.list_replace(list_name, index, value):
					print(f"成功替换列表 {list_name} 位置 {index} 的元素为: {value}")
				else:
					print("替换元素失败")
			except ValueError:
				print("错误:位置必须是数字")
		elif operation == "clear":
			if self.cloud.list_clear(list_name):
				print(f"成功清空列表 {list_name}")
			else:
				print("清空列表失败")
		elif operation == "get":
			if len(args) < 3:
				print("错误:需要提供位置")
				return
			try:
				index = int(args[2])
				value = cloud_list.get(index)
				if value is not None:
					print(f"列表 {list_name} 位置 {index} 的元素: {value}")
				else:
					print(f"错误:位置 {index} 超出范围")
			except ValueError:
				print("错误:位置必须是数字")
		else:
			print(f"错误:未知操作 '{operation}'")
			self.help_list_operations()

	def help_list_operations(self) -> None:
		"""显示列表操作帮助"""
		print("""
	列表操作命令:
	list_operations push <列表名> <值>      - 向列表末尾添加元素
	list_operations pop <列表名>            - 移除并返回列表最后一个元素
	list_operations unshift <列表名> <值>   - 向列表开头添加元素
	list_operations shift <列表名>          - 移除并返回列表第一个元素
	list_operations insert <列表名> <位置> <值> - 在指定位置插入元素
	list_operations remove <列表名> <位置>  - 移除指定位置的元素
	list_operations replace <列表名> <位置> <值> - 替换指定位置的元素
	list_operations clear <列表名>          - 清空列表所有元素
	list_operations get <列表名> <位置>     - 获取指定位置的元素
			""")

	def do_ranking(self, arg: str) -> None:
		"""获取私有变量的排行榜
		用法: ranking <变量名> [数量] [排序]
		数量: 默认10,最大31
		排序: 1(升序) 或 -1(降序,默认)"""
		args = shlex.split(arg)
		if not args:
			print("错误:请指定变量名")
			return
		name = args[0]
		limit = 10
		order = -1
		if len(args) > 1:
			try:
				limit = int(args[1])
				if limit <= 0 or limit > DEFAULT_RANKING_LIMIT:
					print(f"警告:数量范围1-{DEFAULT_RANKING_LIMIT},使用默认值10")
					limit = 10
			except ValueError:
				print("错误:数量必须是数字")
				return
		if len(args) > 2:
			try:
				order = int(args[2])
				if order not in {1, -1}:
					print("错误:排序必须是1(升序)或-1(降序)")
					return
			except ValueError:
				print("错误:排序必须是数字")
				return
		variable = self.cloud.get_private_variable(name)
		if not variable:
			print(f"错误:未找到私有变量 '{name}'")
			return
		print(f"获取 {name} 的排行榜...")
		self.cloud.get_private_variable_ranking(name, limit, order)

	def do_refresh(self, arg: str) -> None:
		"""刷新显示所有数据"""
		self.cloud.print_all_data()

	def do_online(self, arg: str) -> None:
		"""查看在线用户数"""
		print(f"当前在线用户: {self.cloud.online_users}")

	def do_exit(self, arg: str) -> bool:
		"""退出程序"""
		print("正在关闭连接...")
		self.cloud.close()
		return True

	def do_quit(self, arg: str) -> bool:
		"""退出程序"""
		return self.do_exit(arg)

	def do_EOF(self, arg: str) -> bool:  # type: ignore
		"""Ctrl+D 退出"""
		print()
		return self.do_exit(arg)


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
	# 创建云连接
	cloud = KittenCloudFunction(work_id=work_id, editor=CodemaoWorkEditor.KITTEN, authorization_token=authorization_token)

	def on_data_ready() -> None:
		print("数据准备完成!")
		cloud.print_all_data()
		print("\n现在你可以使用命令行界面操作云数据了。")

	def on_online_users_change(old_count: int, new_count: int) -> None:
		print(f"\n[系统] 在线用户数变化: {old_count} -> {new_count}")

	def on_ranking_received(variable: KittenCloudPrivateVariable, ranking_data: list[dict[str, Any]]) -> None:
		print(f"\n=== {variable.name} 排行榜 ===")
		for i, item in enumerate(ranking_data, 1):
			user_info = item["user"]
			print(f"{i}. {item['value']} - {user_info['nickname']} (ID: {user_info['id']})")
		print("云数据> ", end="", flush=True)

	# 注册事件回调
	cloud.on_data_ready(on_data_ready)
	cloud.on_online_users_change(on_online_users_change)
	cloud.on_ranking_received(on_ranking_received)
	print("正在连接...")
	cloud.connect()
	print("等待连接建立...")
	if cloud.wait_for_connection(timeout=30):
		print("连接建立成功,等待数据...")
		if cloud.wait_for_data(timeout=30):
			print("数据加载完成,启动命令行界面...")
			# 启动命令行界面
			cli = CloudCLI(cloud)
			try:
				cli.cmdloop()
			except KeyboardInterrupt:
				print("\n接收到中断信号,正在退出...")
				cloud.close()
		else:
			print("数据加载超时")
			cloud.close()
	else:
		print("连接超时")
		cloud.close()


if __name__ == "__main__":
	main()
