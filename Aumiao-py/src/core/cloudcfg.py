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

# ==============================
# 常量定义
# ==============================
# HTTP 相关常量
HTTP_SUCCESS_CODE = 200
CONNECTION_TIMEOUT = 30
REQUEST_TIMEOUT = 10
# WebSocket 消息类型常量
WEBSOCKET_PING_MESSAGE = "2"
WEBSOCKET_PONG_MESSAGE = "3"
WEBSOCKET_CONNECT_MESSAGE = "40"
WEBSOCKET_CONNECTED_MESSAGE = "40"
WEBSOCKET_EVENT_MESSAGE_PREFIX = "42"
WEBSOCKET_HANDSHAKE_MESSAGE_PREFIX = "0"
# 配置常量
MAX_DISPLAY_LENGTH = 50
TRUNCATED_SUFFIX = "..."
DEFAULT_RANKING_LIMIT = 31
MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_INTERVAL = 8
PING_INTERVAL_MS = 25000
PING_TIMEOUT_MS = 5000
WEBSOCKET_PING_INTERVAL = 20
WEBSOCKET_PING_TIMEOUT = 10
DATA_TIMEOUT = 30
WAIT_TIMEOUT = 30
MESSAGE_TYPE_LENGTH = 2
WEBSOCKET_TRANSPORT_TYPE = "websocket"
# 魔法数值常量(用于替换代码中的魔法数字)
MIN_RANKING_LIMIT = 1
MAX_RANKING_LIMIT = 31
ASCENDING_ORDER = 1
DESCENDING_ORDER = -1
LIST_START_INDEX = 0
FIRST_ELEMENT_INDEX = 0
LAST_ELEMENT_INDEX = -1
MIN_LIST_INDEX = 0
MAX_LIST_DISPLAY_ELEMENTS = 6
PARTIAL_LIST_DISPLAY_COUNT = 3
# 新增常量修复魔法数值问题
MIN_LIST_OPERATION_ARGS = 2
MIN_SET_ARGS = 2
MIN_INSERT_ARGS = 2
MIN_REMOVE_ARGS = 1
MIN_REPLACE_ARGS = 2
MIN_GET_ARGS = 1
MIN_RANKING_ARGS = 1
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
ERROR_INVALID_VARIABLE_TYPE = "云变量值必须是整数或字符串"
ERROR_INVALID_LIST_ITEM_TYPE = "列表元素必须是整数或字符串"
ERROR_INVALID_RANKING_ORDER = "排序顺序必须是1(正序)或-1(逆序)"
ERROR_INVALID_RANKING_LIMIT = "限制数量必须是正整数"


# ==============================
# 枚举类型定义
# ==============================
class EditorType(Enum):
	"""编辑器类型枚举"""

	NEMO = "NEMO"
	KITTEN = "KITTEN"
	KITTEN_N = "NEKO"
	COCO = "COCO"


class DataType(Enum):
	"""云数据类型枚举"""

	PRIVATE_VARIABLE = 0
	PUBLIC_VARIABLE = 1
	LIST = 2


class ReceiveMessageType(Enum):
	"""接收消息类型枚举"""

	JOIN = "connect_done"
	RECEIVE_ALL_DATA = "list_variables_done"
	UPDATE_PRIVATE_VARIABLE = "update_private_vars_done"
	RECEIVE_PRIVATE_VARIABLE_RANKING_LIST = "list_ranking_done"
	UPDATE_PUBLIC_VARIABLE = "update_vars_done"
	UPDATE_LIST = "update_lists_done"
	ILLEGAL_EVENT = "illegal_event_done"
	UPDATE_ONLINE_USER_NUMBER = "online_users_change"


class SendMessageType(Enum):
	"""发送消息类型枚举"""

	JOIN = "join"
	GET_ALL_DATA = "list_variables"
	UPDATE_PRIVATE_VARIABLE = "update_private_vars"
	GET_PRIVATE_VARIABLE_RANKING_LIST = "list_ranking"
	UPDATE_PUBLIC_VARIABLE = "update_vars"
	UPDATE_LIST = "update_lists"


# ==============================
# 类型别名定义
# ==============================
CloudValueType = int | str
CloudListValueType = list[CloudValueType]
ChangeCallbackType = Callable[[CloudValueType, CloudValueType, str], None]
ListOperationCallbackType = Callable[..., None]
RankingCallbackType = Callable[[list[dict[str, Any]]], None]
OnlineUsersCallbackType = Callable[[int, int], None]
DataReadyCallbackType = Callable[[], None]
RankingReceivedCallbackType = Callable[["PrivateCloudVariable", list[dict[str, Any]]], None]


# ==============================
# 工具类
# ==============================
class DisplayHelper:
	"""显示辅助类,处理长文本截断和格式化显示"""

	@staticmethod
	def truncate_value(value: Any, max_length: int = MAX_DISPLAY_LENGTH) -> str:  # noqa: ANN401
		"""截断过长的值用于显示"""
		if isinstance(value, (int, float, bool)):
			return str(value)
		str_value = str(value)
		if len(str_value) <= max_length:
			return str_value
		# 对于列表,显示前几个和后几个元素
		if isinstance(value, list):
			if len(value) <= MAX_LIST_DISPLAY_ELEMENTS:
				return str(value)
			first_part = value[:PARTIAL_LIST_DISPLAY_COUNT]
			last_part = value[-PARTIAL_LIST_DISPLAY_COUNT:]
			return f"[{', '.join(map(str, first_part))}, ..., {', '.join(map(str, last_part))}]"
		# 对于长字符串,截取前后部分
		half_length = max_length // 2 - len(TRUNCATED_SUFFIX) // 2
		return f"{str_value[:half_length]}{TRUNCATED_SUFFIX}{str_value[-half_length:]}"


class WorkInfo:
	"""作品信息容器"""

	def __init__(self, data: dict[str, Any]) -> None:
		self.id = data["id"]
		self.name = data.get("work_name", data.get("name", "未知作品"))
		self.type = data.get("type", "NEMO")
		self.version = data.get("bcm_version", "0.16.2")
		self.user_id = data.get("user_id", 0)
		self.preview_url = data.get("preview", "")
		self.source_urls = data.get("source_urls", data.get("work_urls", []))


class CloudAuthenticator:
	"""云服务认证管理器"""

	def __init__(self, authorization_token: str | None = None) -> None:
		self.authorization_token = authorization_token
		self.client_id = str(uuid.uuid4())
		self.time_difference = 0

	@staticmethod
	def get_current_time() -> int:
		"""获取服务器当前时间"""
		try:
			response = httpx.get("https://api.codemao.cn/coconut/clouddb/currentTime", timeout=REQUEST_TIMEOUT)
			if response.status_code == HTTP_SUCCESS_CODE:
				data: dict | str = response.json()
				if isinstance(data, dict) and "data" in data:
					return data["data"]
				return int(cast("str", data))
		except Exception as error:
			print(f"{ERROR_GET_SERVER_TIME}: {error}")
		return int(time.time())

	def get_calibrated_timestamp(self) -> int:
		"""获取校准后的时间戳"""
		if self.time_difference == 0:
			server_time = self.get_current_time()
			local_time = int(time.time())
			self.time_difference = local_time - server_time
		return int(time.time()) - self.time_difference

	def generate_device_auth(self) -> dict[str, Any]:
		"""生成设备认证信息"""
		timestamp = self.get_calibrated_timestamp()
		sign_text = f"pBlYqXbJDu{timestamp}{self.client_id}"
		sign = hashlib.sha256(sign_text.encode()).hexdigest().upper()
		return {"sign": sign, "timestamp": timestamp, "client_id": self.client_id}


# ==============================
# 云数据核心类
# ==============================
class CloudDataItem:
	"""云数据项基类"""

	def __init__(self, connection: "CloudConnection", cloud_variable_id: str, name: str, value: CloudValueType | CloudListValueType) -> None:
		self.connection = connection
		self.cloud_variable_id = cloud_variable_id
		self.name = name
		self.value = value
		self._change_callbacks: list[Callable[..., None]] = []

	def on_change(self, callback: Callable[..., None]) -> None:
		"""注册数据变更回调"""
		self._change_callbacks.append(callback)

	def emit_change(self, old_value: CloudValueType | CloudListValueType, new_value: CloudValueType | CloudListValueType, source: str) -> None:
		"""触发数据变更回调"""
		for callback in self._change_callbacks:
			try:
				callback(old_value, new_value, source)
			except Exception as error:
				print(f"{ERROR_CALLBACK_EXECUTION}: {error}")


class CloudVariable(CloudDataItem):
	"""云变量基类"""

	def __init__(self, connection: "CloudConnection", cloud_variable_id: str, name: str, value: CloudValueType) -> None:
		super().__init__(connection, cloud_variable_id, name, value)
		self._change_callbacks: list[ChangeCallbackType] = []

	def on_change(self, callback: ChangeCallbackType) -> None:
		"""注册变量变更回调"""
		self._change_callbacks.append(callback)

	def get(self) -> CloudValueType:
		"""获取变量值"""
		return self.value

	def set(self, value: CloudValueType) -> bool:
		"""设置变量值"""
		if not isinstance(value, (int, str)):
			raise TypeError(ERROR_INVALID_VARIABLE_TYPE)
		old_value = self.value
		self.value = value
		self.emit_change(old_value, value, "local")
		return True

	def emit_change(self, old_value: CloudValueType | CloudListValueType, new_value: CloudValueType | CloudListValueType, source: str) -> None:
		"""触发变量变更回调"""
		if not isinstance(old_value, (int, str)) or not isinstance(new_value, (int, str)):
			print(f"警告: 云变量值类型不匹配, 期望 int 或 str, 得到 old_value: {type(old_value)}, new_value: {type(new_value)}")
			return
		old_value_cast = old_value
		new_value_cast = new_value
		for callback in self._change_callbacks:
			try:
				callback(old_value_cast, new_value_cast, source)
			except Exception as error:
				print(f"{ERROR_CLOUD_VARIABLE_CALLBACK}: {error}")


class PrivateCloudVariable(CloudVariable):
	"""私有云变量类"""

	def __init__(self, connection: "CloudConnection", cloud_variable_id: str, name: str, value: CloudValueType) -> None:
		super().__init__(connection, cloud_variable_id, name, value)
		self._ranking_callbacks: list[RankingCallbackType] = []

	def on_ranking_received(self, callback: RankingCallbackType) -> None:
		"""注册排行榜数据接收回调"""
		self._ranking_callbacks.append(callback)

	def emit_ranking(self, ranking_data: list[dict[str, Any]]) -> None:
		"""触发排行榜数据接收回调"""
		for callback in self._ranking_callbacks:
			try:
				callback(ranking_data)
			except Exception as error:
				print(f"{ERROR_RANKING_CALLBACK}: {error}")

	def get_ranking_list(self, limit: int = DEFAULT_RANKING_LIMIT, order: int = DESCENDING_ORDER) -> None:
		"""获取排行榜列表"""
		if not isinstance(limit, int) or limit <= 0:
			raise ValueError(ERROR_INVALID_RANKING_LIMIT)
		if order not in {ASCENDING_ORDER, DESCENDING_ORDER}:
			raise ValueError(ERROR_INVALID_RANKING_ORDER)
		request_data = {"cvid": self.cloud_variable_id, "limit": limit, "order_type": order}
		self.connection.send_message(SendMessageType.GET_PRIVATE_VARIABLE_RANKING_LIST, request_data)


class PublicCloudVariable(CloudVariable):
	"""公有云变量类"""


class CloudList(CloudDataItem):
	"""云列表类"""

	def __init__(self, connection: "CloudConnection", cloud_variable_id: str, name: str, value: CloudListValueType) -> None:
		super().__init__(connection, cloud_variable_id, name, value or [])
		self._operation_callbacks: dict[str, list[ListOperationCallbackType]] = {
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

	def on_operation(self, operation: str, callback: ListOperationCallbackType) -> None:
		"""注册列表操作回调"""
		if operation in self._operation_callbacks:
			self._operation_callbacks[operation].append(callback)

	def _emit_operation(self, operation: str, *args: object) -> None:
		"""触发列表操作回调"""
		for callback in self._operation_callbacks[operation]:
			try:
				callback(*args)
			except Exception as error:
				print(f"{ERROR_OPERATION_CALLBACK}: {error}")

	def get(self, index: int) -> CloudValueType | None:
		"""获取指定位置的元素"""
		if MIN_LIST_INDEX <= index < len(self.value):
			return self.value[index]
		return None

	def push(self, item: CloudValueType) -> bool:
		"""向列表末尾添加元素"""
		if not isinstance(item, (int, str)):
			raise TypeError(ERROR_INVALID_LIST_ITEM_TYPE)
		self.value.append(item)
		self._emit_operation("push", item, len(self.value) - 1)
		return True

	def pop(self) -> CloudValueType | None:
		"""移除并返回列表最后一个元素"""
		if self.value:
			item = self.value.pop()
			self._emit_operation("pop", item, len(self.value))
			return item
		return None

	def unshift(self, item: CloudValueType) -> bool:
		"""向列表开头添加元素"""
		if not isinstance(item, (int, str)):
			raise TypeError(ERROR_INVALID_LIST_ITEM_TYPE)
		self.value.insert(FIRST_ELEMENT_INDEX, item)
		self._emit_operation("unshift", item, FIRST_ELEMENT_INDEX)
		return True

	def shift(self) -> CloudValueType | None:
		"""移除并返回列表第一个元素"""
		if self.value:
			item = self.value.pop(FIRST_ELEMENT_INDEX)
			self._emit_operation("shift", item, FIRST_ELEMENT_INDEX)
			return item
		return None

	def insert(self, index: int, item: CloudValueType) -> bool:
		"""在指定位置插入元素"""
		if not isinstance(item, (int, str)):
			raise TypeError(ERROR_INVALID_LIST_ITEM_TYPE)
		if MIN_LIST_INDEX <= index <= len(self.value):
			self.value.insert(index, item)
			self._emit_operation("insert", item, index)
			return True
		return False

	def remove(self, index: int) -> CloudValueType | None:
		"""移除指定位置的元素"""
		if MIN_LIST_INDEX <= index < len(self.value):
			item = self.value.pop(index)
			self._emit_operation("remove", item, index)
			return item
		return None

	def replace(self, index: int, item: CloudValueType) -> bool:
		"""替换指定位置的元素"""
		if not isinstance(item, (int, str)):
			raise TypeError(ERROR_INVALID_LIST_ITEM_TYPE)
		if MIN_LIST_INDEX <= index < len(self.value):
			old_item = self.value[index]
			self.value[index] = item
			self._emit_operation("replace", old_item, item, index)
			return True
		return False

	def replace_last(self, item: CloudValueType) -> bool:
		"""替换列表最后一个元素"""
		if not isinstance(item, (int, str)):
			raise TypeError(ERROR_INVALID_LIST_ITEM_TYPE)
		if self.value:
			old_item = self.value[LAST_ELEMENT_INDEX]
			self.value[LAST_ELEMENT_INDEX] = item
			self._emit_operation("replace_last", old_item, item)
			return True
		return False

	def clear(self) -> bool:
		"""清空列表所有元素"""
		old_value = self.value.copy()
		self.value.clear()
		self._emit_operation("clear", old_value)
		return True

	def length(self) -> int:
		"""获取列表长度"""
		return len(self.value)

	def index_of(self, item: CloudValueType) -> int:
		"""查找元素第一次出现的索引"""
		try:
			return self.value.index(item)
		except ValueError:
			return -1

	def last_index_of(self, item: CloudValueType) -> int:
		"""查找元素最后一次出现的索引"""
		try:
			return len(self.value) - 1 - self.value[::-1].index(item)
		except ValueError:
			return -1

	def includes(self, item: CloudValueType) -> bool:
		"""检查列表是否包含指定元素"""
		return item in self.value

	def join(self, separator: str = ",") -> str:
		"""将列表元素连接为字符串"""
		return separator.join(str(item) for item in self.value)

	def copy(self) -> list[CloudValueType]:
		"""返回列表的浅拷贝"""
		return self.value.copy()

	def copy_from(self, source_list: list[CloudValueType]) -> bool:
		"""从源列表复制数据"""
		if not all(isinstance(item, (int, str)) for item in source_list):
			return False
		old_value = self.value.copy()
		self.value = source_list.copy()
		self.emit_change(old_value, self.value, "local")
		return True


class CloudConnection:
	"""云连接核心类,负责WebSocket连接和消息处理"""

	def __init__(self, work_id: int, editor: EditorType | None = None, authorization_token: str | None = None) -> None:
		self.work_id = work_id
		self.editor = editor
		self.authenticator = CloudAuthenticator(authorization_token)
		self.websocket_client: websocket.WebSocketApp | None = None
		self.connected = False
		self.auto_reconnect = True
		self.reconnect_interval = RECONNECT_INTERVAL
		self.reconnect_attempts = 0
		self.max_reconnect_attempts = MAX_RECONNECT_ATTEMPTS
		self.private_variables: dict[str, PrivateCloudVariable] = {}
		self.public_variables: dict[str, PublicCloudVariable] = {}
		self.lists: dict[str, CloudList] = {}
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
		self._pending_ranking_requests: list[PrivateCloudVariable] = []
		self._ping_active = False
		self._join_sent = False
		self._work_info: WorkInfo | None = None

	def _get_work_info(self) -> WorkInfo:
		"""获取作品信息"""
		if self._work_info is None:
			try:
				raw_info = httpx.get(
					f"https://api.codemao.cn/creation-tools/v1/works/{self.work_id}",
					headers={"Cookie": f"Authorization={self.authenticator.authorization_token}"} if self.authenticator.authorization_token else {},
				).json()
				self._work_info = WorkInfo(raw_info)
				print(f"✓ 作品: {self._work_info.name}")
				print(f"✓ 类型: {self._work_info.type}")
			except Exception as e:
				print(f"获取作品信息失败: {e}")
				# 默认使用KITTEN类型
				self._work_info = WorkInfo({"id": self.work_id, "name": "未知作品", "type": "KITTEN"})
		return self._work_info

	def _determine_editor_type(self) -> EditorType:
		"""根据作品类型确定编辑器类型"""
		work_info = self._get_work_info()
		work_type = work_info.type
		# 根据作品类型映射到对应的编辑器类型
		editor_mapping = {
			"KITTEN": EditorType.KITTEN,
			"KITTEN2": EditorType.KITTEN,
			"KITTEN3": EditorType.KITTEN,
			"KITTEN4": EditorType.KITTEN,
			"NEKO": EditorType.KITTEN_N,
			"NEMO": EditorType.NEMO,
			"COCO": EditorType.COCO,
		}
		return editor_mapping.get(work_type, EditorType.KITTEN)

	def on(self, event: str, callback: Callable[..., None]) -> None:
		"""注册事件回调"""
		if event in self._callbacks:
			self._callbacks[event].append(callback)

	def on_online_users_change(self, callback: OnlineUsersCallbackType) -> None:
		"""注册在线用户数变更回调"""
		self._callbacks["online_users_change"].append(callback)

	def on_data_ready(self, callback: DataReadyCallbackType) -> None:
		"""注册数据就绪回调"""
		self._callbacks["data_ready"].append(callback)

	def on_ranking_received(self, callback: RankingReceivedCallbackType) -> None:
		"""注册排行榜数据接收回调"""
		self._callbacks["ranking_received"].append(callback)

	def _emit_event(self, event: str, *args: object) -> None:
		"""触发事件回调"""
		if event in self._callbacks:
			for callback in self._callbacks[event]:
				try:
					callback(*args)
				except Exception as error:
					print(f"{ERROR_EVENT_CALLBACK}: {error}")

	def _get_websocket_url(self) -> str:
		"""获取WebSocket连接URL"""
		# 如果未指定编辑器类型,自动根据作品类型确定
		if self.editor is None:
			self.editor = self._determine_editor_type()
		editor_params = {
			EditorType.NEMO: {"authorization_type": "5", "stag": "2"},
			EditorType.KITTEN: {"authorization_type": "1", "stag": "1"},
			EditorType.KITTEN_N: {"authorization_type": "5", "stag": "3", "token": ""},
			EditorType.COCO: {"authorization_type": "1", "stag": "1"},
		}
		params = editor_params.get(self.editor, editor_params[EditorType.KITTEN])
		params["EIO"] = "3"
		params["transport"] = WEBSOCKET_TRANSPORT_TYPE
		params_str = "&".join([f"{k}={v}" for k, v in params.items()])
		return f"wss://socketcv.codemao.cn:9096/cloudstorage/?session_id={self.work_id}&{params_str}"

	def _get_websocket_headers(self) -> dict[str, str]:
		"""获取WebSocket请求头"""
		headers: dict[str, str] = {}
		device_auth = self.authenticator.generate_device_auth()
		headers["X-Creation-Tools-Device-Auth"] = json.dumps(device_auth)
		if self.authenticator.authorization_token:
			headers["Cookie"] = f"Authorization={self.authenticator.authorization_token}"
		return headers

	def _on_message(self, _ws: websocket.WebSocketApp, message: str | bytes) -> None:
		"""WebSocket消息处理"""
		if isinstance(message, bytes):
			message = message.decode("utf-8")
		message_str = str(message)
		# 处理ping消息
		if message_str == WEBSOCKET_PING_MESSAGE:
			if self.websocket_client:
				self.websocket_client.send(WEBSOCKET_PONG_MESSAGE)
			return
		# 处理握手消息
		if message_str.startswith(WEBSOCKET_HANDSHAKE_MESSAGE_PREFIX):
			self._handle_handshake_message(message_str)
			return
		# 处理连接确认消息
		if message_str == WEBSOCKET_CONNECTED_MESSAGE:
			self._handle_connected_message()
			return
		# 处理事件消息
		if message_str.startswith(WEBSOCKET_EVENT_MESSAGE_PREFIX):
			self._handle_event_message(message_str)
			return

	def _handle_handshake_message(self, message: str) -> None:
		"""处理握手消息"""
		try:
			handshake_data = json.loads(message[1:])
			ping_interval = handshake_data.get("pingInterval", PING_INTERVAL_MS)
			ping_timeout = handshake_data.get("pingTimeout", PING_TIMEOUT_MS)
			print(f"握手成功, ping间隔: {ping_interval}ms, ping超时: {ping_timeout}ms")
			self._start_ping(ping_interval, ping_timeout)
			if self.websocket_client:
				self.websocket_client.send(WEBSOCKET_CONNECT_MESSAGE)
				print("已发送连接请求")
		except Exception as error:
			print(f"{ERROR_HANDSHAKE_PROCESSING}: {error}")

	def _handle_connected_message(self) -> None:
		"""处理连接确认消息"""
		self.connected = True
		print("连接确认收到")
		self._emit_event("open")
		if not self._join_sent:
			self._join_sent = True
			threading.Timer(0.5, self._send_join_message).start()

	def _handle_event_message(self, message: str) -> None:
		"""处理事件消息"""
		data_str = message[MESSAGE_TYPE_LENGTH:]
		try:
			data_list = json.loads(data_str)
			if isinstance(data_list, list) and len(data_list) >= 2:  # noqa: PLR2004
				message_type = data_list[0]
				message_data = data_list[1]
				print(f"处理云消息: {message_type}, 数据: {DisplayHelper.truncate_value(message_data)}")
				if isinstance(message_data, str):
					message_data = json.loads(message_data)
				self._handle_cloud_message(message_type, message_data)
		except json.JSONDecodeError as error:
			print(f"{ERROR_JSON_PARSE}: {error}, 数据: {DisplayHelper.truncate_value(data_str)}")

	def _send_join_message(self) -> None:
		"""发送加入消息"""
		if self.connected and self.websocket_client:
			print("发送JOIN消息...")
			self.send_message(SendMessageType.JOIN, str(self.work_id))

	def _start_ping(self, interval: int, _timeout: int) -> None:
		"""启动ping线程"""
		if self._ping_thread is not None:
			self._ping_active = False
			self._ping_thread.join(timeout=1.0)
		self._ping_active = True

		def ping_task() -> None:
			while self._ping_active and self.connected:
				time.sleep(interval / 1000)
				if self._ping_active and self.connected and self.websocket_client:
					try:
						self.websocket_client.send(WEBSOCKET_PING_MESSAGE)
					except Exception as error:
						print(f"{ERROR_PING_SEND}: {error}")
						break

		self._ping_thread = threading.Thread(target=ping_task, daemon=True)
		self._ping_thread.start()

	def _stop_ping(self) -> None:
		"""停止ping线程"""
		self._ping_active = False
		if self._ping_thread is not None:
			self._ping_thread.join(timeout=2.0)
			self._ping_thread = None

	def _handle_cloud_message(self, message_type: str, data: dict[str, Any] | list[Any] | str) -> None:
		"""处理云消息"""
		try:
			message_handlers = {
				ReceiveMessageType.JOIN.value: self._handle_join_message,
				ReceiveMessageType.RECEIVE_ALL_DATA.value: self._handle_receive_all_data,
				ReceiveMessageType.UPDATE_PRIVATE_VARIABLE.value: self._handle_update_private_variable,
				ReceiveMessageType.RECEIVE_PRIVATE_VARIABLE_RANKING_LIST.value: self._handle_receive_ranking_list,
				ReceiveMessageType.UPDATE_PUBLIC_VARIABLE.value: self._handle_update_public_variable,
				ReceiveMessageType.UPDATE_LIST.value: self._handle_update_list,
				ReceiveMessageType.UPDATE_ONLINE_USER_NUMBER.value: self._handle_update_online_users,
				ReceiveMessageType.ILLEGAL_EVENT.value: self._handle_illegal_event,
			}
			handler = message_handlers.get(message_type)
			if handler:
				handler(data)
			else:
				print(f"未知消息类型: {message_type}, 数据: {DisplayHelper.truncate_value(data)}")
		except Exception as error:
			print(f"{ERROR_CLOUD_MESSAGE_PROCESSING}: {error}")
			traceback.print_exc()
			self._emit_event("error", error)

	def _handle_join_message(self, _data: object) -> None:
		"""处理加入消息"""
		print("连接加入成功, 请求所有数据...")
		self.send_message(SendMessageType.GET_ALL_DATA, {})

	def _handle_receive_all_data(self, data: list[dict[str, Any]] | object) -> None:
		"""处理接收完整数据消息"""
		print(f"收到完整数据: {DisplayHelper.truncate_value(data)}")
		if not isinstance(data, list):
			print(f"数据格式错误, 期望列表, 得到: {type(data)}")
			return
		for item in data:
			self._create_data_item(item)
		self.data_ready = True
		print(f"数据准备完成! 私有变量: {len(self.private_variables)}, 公有变量: {len(self.public_variables)}, 列表: {len(self.lists)}")
		self._emit_event("data_ready")

	def _create_data_item(self, item: dict[str, Any]) -> None:
		"""创建数据项"""
		try:
			cloud_variable_id = item.get("cvid")
			name = item.get("name")
			value = cast("CloudValueType", item.get("value"))
			data_type: int = cast("int", item.get("type"))
			if not all([cloud_variable_id, name, value is not None, data_type is not None]):
				print(f"数据项缺少必要字段: {DisplayHelper.truncate_value(item)}")
				return
			data_creators = {
				DataType.PRIVATE_VARIABLE.value: self._create_private_variable,
				DataType.PUBLIC_VARIABLE.value: self._create_public_variable,
				DataType.LIST.value: self._create_cloud_list,
			}
			creator = data_creators.get(data_type)
			if creator:
				creator(str(cloud_variable_id), str(name), value)
			else:
				print(f"未知数据类型: {data_type}")
		except Exception as error:
			print(f"{ERROR_CREATE_DATA_ITEM}: {error}, 数据: {DisplayHelper.truncate_value(item)}")

	def _create_private_variable(self, cloud_variable_id: str, name: str, value: CloudValueType) -> None:
		"""创建私有变量"""
		variable = PrivateCloudVariable(self, cloud_variable_id, name, value)
		self.private_variables[name] = variable
		self.private_variables[cloud_variable_id] = variable

	def _create_public_variable(self, cloud_variable_id: str, name: str, value: CloudValueType) -> None:
		"""创建公有变量"""
		variable = PublicCloudVariable(self, cloud_variable_id, name, value)
		self.public_variables[name] = variable
		self.public_variables[cloud_variable_id] = variable

	def _create_cloud_list(self, cloud_variable_id: str, name: str, value: object) -> None:
		"""创建云列表"""
		if not isinstance(value, list):
			value = []
		cloud_list = CloudList(self, cloud_variable_id, name, value)
		self.lists[name] = cloud_list
		self.lists[cloud_variable_id] = cloud_list

	def _handle_update_private_variable(self, data: dict[str, Any] | object) -> None:
		"""处理更新私有变量消息"""
		if isinstance(data, dict) and "cvid" in data and "value" in data:
			cloud_variable_id = data["cvid"]
			new_value = data["value"]
			for variable in self.private_variables.values():
				if variable.cloud_variable_id == cloud_variable_id:
					old_value = variable.value
					variable.value = new_value
					variable.emit_change(old_value, new_value, "cloud")
					break

	def _handle_receive_ranking_list(self, data: dict[str, Any] | object) -> None:
		"""处理接收排行榜列表消息"""
		if not self._pending_ranking_requests:
			print(ERROR_NO_PENDING_REQUESTS)
			return
		variable = self._pending_ranking_requests.pop(0)
		if not isinstance(data, dict) or "items" not in data or not isinstance(data["items"], list):
			print(f"{ERROR_INVALID_RANKING_DATA}: {DisplayHelper.truncate_value(data)}")
			return
		ranking_data = [
			{"value": item["value"], "user": {"id": int(item["identifier"]), "nickname": item["nickname"], "avatar_url": item["avatar_url"]}}
			for item in data["items"]
			if isinstance(item, dict) and all(key in item for key in ["value", "nickname", "avatar_url", "identifier"])
		]
		variable.emit_ranking(ranking_data)
		self._emit_event("ranking_received", variable, ranking_data)

	def _handle_update_public_variable(self, data: object) -> None:
		"""处理更新公有变量消息"""
		if data == "fail":
			return
		if isinstance(data, list):
			for item in data:
				if isinstance(item, dict) and "cvid" in item and "value" in item:
					cloud_variable_id = item["cvid"]
					new_value = item["value"]
					for variable in self.public_variables.values():
						if variable.cloud_variable_id == cloud_variable_id:
							old_value = variable.value
							variable.value = new_value
							variable.emit_change(old_value, new_value, "cloud")
							break

	def _handle_update_list(self, data: dict[str, list[dict[str, Any]]] | object) -> None:
		"""处理更新列表消息"""
		if not isinstance(data, dict):
			return
		for cloud_variable_id, operations in data.items():
			if cloud_variable_id in self.lists:
				cloud_list = self.lists[cloud_variable_id]
				self._process_list_operations(cloud_list, operations)

	def _process_list_operations(self, cloud_list: CloudList, operations: list[dict[str, Any]]) -> None:
		"""处理列表操作"""
		for operation in operations:
			if not isinstance(operation, dict) or "action" not in operation:
				continue
			self._execute_list_operation(cloud_list, operation)

	def _execute_list_operation(self, cloud_list: CloudList, operation: dict[str, Any]) -> None:
		"""执行列表操作"""
		action = operation["action"]
		operation_handlers = {
			"append": lambda: cloud_list.push(operation["value"]),
			"unshift": lambda: cloud_list.unshift(operation["value"]),
			"insert": lambda: cloud_list.insert(operation["nth"] - 1, operation["value"]),
			"delete": lambda: self._handle_delete_operation(cloud_list, operation),
			"replace": lambda: self._handle_replace_operation(cloud_list, operation),
		}
		handler = operation_handlers.get(action)
		if handler:
			handler()

	@staticmethod
	def _handle_delete_operation(cloud_list: CloudList, operation: dict[str, Any]) -> None:
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
	def _handle_replace_operation(cloud_list: CloudList, operation: dict[str, Any]) -> None:
		"""处理替换操作"""
		nth = operation["nth"]
		value = operation["value"]
		if nth == "last":
			cloud_list.replace_last(value)
		elif isinstance(nth, int):
			index = nth - 1
			cloud_list.replace(index, value)

	def _handle_update_online_users(self, data: dict[str, Any] | object) -> None:
		"""处理更新在线用户数消息"""
		if isinstance(data, dict) and "total" in data and isinstance(data["total"], int):
			old_count = self.online_users
			self.online_users = data["total"]
			self._emit_event("online_users_change", old_count, self.online_users)

	@staticmethod
	def _handle_illegal_event(_data: object) -> None:
		"""处理非法事件消息"""
		print("检测到非法事件")

	def _on_open(self, _ws: websocket.WebSocketApp) -> None:
		"""WebSocket连接打开回调"""
		self.connected = True
		self.reconnect_attempts = 0

	def _on_close(self, _ws: websocket.WebSocketApp, close_status_code: int, close_msg: str) -> None:
		"""WebSocket连接关闭回调"""
		self.connected = False
		self.data_ready = False
		self._join_sent = False
		self._stop_ping()
		self._emit_event("close", close_status_code, close_msg)
		if self.auto_reconnect and self.reconnect_attempts < self.max_reconnect_attempts:
			self.reconnect_attempts += 1
			threading.Timer(self.reconnect_interval, self.connect).start()

	def _on_error(self, _ws: websocket.WebSocketApp, error: Exception) -> None:
		"""WebSocket错误回调"""
		self._emit_event("error", error)

	def send_message(self, message_type: SendMessageType, data: dict[str, Any] | list[Any] | str) -> None:
		"""发送消息到云服务器"""
		if self.websocket_client and self.connected:
			message_content = [message_type.value, data]
			message = f"{WEBSOCKET_EVENT_MESSAGE_PREFIX}{json.dumps(message_content)}"
			try:
				self.websocket_client.send(message)
			except Exception as error:
				print(f"{ERROR_SEND_MESSAGE}: {error}")
				self._emit_event("error", error)
		else:
			print(f"无法发送消息, 连接状态: {self.connected}, WebSocket: {self.websocket_client is not None}")

	def connect(self) -> None:
		"""建立云连接"""
		try:
			self.connected = False
			self.data_ready = False
			self._join_sent = False
			self.private_variables.clear()
			self.public_variables.clear()
			self.lists.clear()
			if self.websocket_client:
				with suppress(Exception):
					self.websocket_client.close()
			url = self._get_websocket_url()
			headers = self._get_websocket_headers()
			print(f"正在连接到: {url}")
			self.websocket_client = websocket.WebSocketApp(
				url, header=headers, on_open=self._on_open, on_message=self._on_message, on_close=self._on_close, on_error=self._on_error
			)

			def run_websocket() -> None:
				"""运行WebSocket客户端"""
				try:
					if self.websocket_client:
						self.websocket_client.run_forever(
							ping_interval=WEBSOCKET_PING_INTERVAL,
							ping_timeout=WEBSOCKET_PING_TIMEOUT,
							skip_utf8_validation=True,
						)
				except Exception as error:
					print(f"{ERROR_WEB_SOCKET_RUN}: {error}")

			thread = threading.Thread(target=run_websocket, daemon=True)
			thread.start()
		except Exception as error:
			print(f"{ERROR_CONNECTION}: {error}")
			self._emit_event("error", error)

	def close(self) -> None:
		"""关闭云连接"""
		self.auto_reconnect = False
		self.connected = False
		self._stop_ping()
		if self.websocket_client:
			try:
				self.websocket_client.close()
			except Exception as error:
				print(f"{ERROR_CLOSE_CONNECTION}: {error}")

	def wait_for_connection(self, timeout: int = CONNECTION_TIMEOUT) -> bool:
		"""等待连接建立"""
		start_time = time.time()
		last_log_time = start_time
		while time.time() - start_time < timeout:
			if self.connected:
				return True
			current_time = time.time()
			if current_time - last_log_time >= 3:  # noqa: PLR2004
				elapsed = current_time - start_time
				print(f"等待连接中... 已等待 {elapsed:.1f} 秒")
				last_log_time = current_time
			time.sleep(0.1)
		print(f"连接超时, 等待 {timeout} 秒后仍未建立连接")
		return False

	def wait_for_data(self, timeout: int = DATA_TIMEOUT) -> bool:
		"""等待数据加载完成"""
		start_time = time.time()
		last_log_time = start_time
		while time.time() - start_time < timeout:
			if self.data_ready:
				print("数据加载完成!")
				return True
			current_time = time.time()
			if current_time - last_log_time >= 5:  # noqa: PLR2004
				elapsed = current_time - start_time
				print(f"等待数据中... 已等待 {elapsed:.1f} 秒, 连接状态: {self.connected}")
				last_log_time = current_time
			time.sleep(0.1)
		print(f"数据加载超时, 等待 {timeout} 秒后仍未收到数据")
		print(f"最终状态 - 连接: {self.connected}, 数据就绪: {self.data_ready}")
		return False

	def get_private_variable(self, name: str) -> PrivateCloudVariable | None:
		"""获取私有变量"""
		return self.private_variables.get(name)

	def get_public_variable(self, name: str) -> PublicCloudVariable | None:
		"""获取公有变量"""
		return self.public_variables.get(name)

	def get_list(self, name: str) -> CloudList | None:
		"""获取云列表"""
		return self.lists.get(name)

	def get_all_private_variables(self) -> dict[str, PrivateCloudVariable]:
		"""获取所有私有变量"""
		return {k: v for k, v in self.private_variables.items() if not k.startswith("_")}

	def get_all_public_variables(self) -> dict[str, PublicCloudVariable]:
		"""获取所有公有变量"""
		return {k: v for k, v in self.public_variables.items() if not k.startswith("_")}

	def get_all_lists(self) -> dict[str, CloudList]:
		"""获取所有云列表"""
		return {k: v for k, v in self.lists.items() if not k.startswith("_")}

	def set_private_variable(self, name: str, value: int | str) -> bool:
		"""设置私有变量值"""
		variable = self.get_private_variable(name)
		if variable and variable.set(value):
			self.send_message(
				SendMessageType.UPDATE_PRIVATE_VARIABLE, [{"cvid": variable.cloud_variable_id, "value": value, "param_type": "number" if isinstance(value, int) else "string"}]
			)
			return True
		return False

	def set_public_variable(self, name: str, value: int | str) -> bool:
		"""设置公有变量值"""
		variable = self.get_public_variable(name)
		if variable and variable.set(value):
			self.send_message(
				SendMessageType.UPDATE_PUBLIC_VARIABLE,
				[{"action": "set", "cvid": variable.cloud_variable_id, "value": value, "param_type": "number" if isinstance(value, int) else "string"}],
			)
			return True
		return False

	def get_private_variable_ranking(self, name: str, limit: int = DEFAULT_RANKING_LIMIT, order: int = DESCENDING_ORDER) -> None:
		"""获取私有变量排行榜"""
		variable = self.get_private_variable(name)
		if variable:
			self._pending_ranking_requests.append(variable)
			variable.get_ranking_list(limit, order)

	def list_push(self, name: str, value: int | str) -> bool:
		"""向列表末尾添加元素"""
		cloud_list = self.get_list(name)
		if cloud_list and cloud_list.push(value):
			self.send_message(SendMessageType.UPDATE_LIST, {cloud_list.cloud_variable_id: [{"action": "append", "value": value}]})
			return True
		return False

	def list_pop(self, name: str) -> bool:
		"""移除列表最后一个元素"""
		cloud_list = self.get_list(name)
		if cloud_list and cloud_list.pop() is not None:
			self.send_message(SendMessageType.UPDATE_LIST, {cloud_list.cloud_variable_id: [{"action": "delete", "nth": "last"}]})
			return True
		return False

	def list_unshift(self, name: str, value: int | str) -> bool:
		"""向列表开头添加元素"""
		cloud_list = self.get_list(name)
		if cloud_list and cloud_list.unshift(value):
			self.send_message(SendMessageType.UPDATE_LIST, {cloud_list.cloud_variable_id: [{"action": "unshift", "value": value}]})
			return True
		return False

	def list_shift(self, name: str) -> bool:
		"""移除列表第一个元素"""
		cloud_list = self.get_list(name)
		if cloud_list and cloud_list.shift() is not None:
			self.send_message(SendMessageType.UPDATE_LIST, {cloud_list.cloud_variable_id: [{"action": "delete", "nth": 1}]})
			return True
		return False

	def list_insert(self, name: str, index: int, value: int | str) -> bool:
		"""在列表指定位置插入元素"""
		cloud_list = self.get_list(name)
		if cloud_list and cloud_list.insert(index, value):
			self.send_message(SendMessageType.UPDATE_LIST, {cloud_list.cloud_variable_id: [{"action": "insert", "nth": index + 1, "value": value}]})
			return True
		return False

	def list_remove(self, name: str, index: int) -> bool:
		"""移除列表指定位置的元素"""
		cloud_list = self.get_list(name)
		if cloud_list and cloud_list.remove(index) is not None:
			self.send_message(SendMessageType.UPDATE_LIST, {cloud_list.cloud_variable_id: [{"action": "delete", "nth": index + 1}]})
			return True
		return False

	def list_replace(self, name: str, index: int, value: int | str) -> bool:
		"""替换列表指定位置的元素"""
		cloud_list = self.get_list(name)
		if cloud_list and cloud_list.replace(index, value):
			self.send_message(SendMessageType.UPDATE_LIST, {cloud_list.cloud_variable_id: [{"action": "replace", "nth": index + 1, "value": value}]})
			return True
		return False

	def list_replace_last(self, name: str, value: int | str) -> bool:
		"""替换列表最后一个元素"""
		cloud_list = self.get_list(name)
		if cloud_list and cloud_list.replace_last(value):
			self.send_message(SendMessageType.UPDATE_LIST, {cloud_list.cloud_variable_id: [{"action": "replace", "nth": "last", "value": value}]})
			return True
		return False

	def list_clear(self, name: str) -> bool:
		"""清空列表所有元素"""
		cloud_list = self.get_list(name)
		if cloud_list and cloud_list.clear():
			self.send_message(SendMessageType.UPDATE_LIST, {cloud_list.cloud_variable_id: [{"action": "delete", "nth": "all"}]})
			return True
		return False

	def print_all_data(self) -> None:
		"""打印所有云数据"""
		print("\n" + "=" * 50)
		print("云数据汇总")
		print("=" * 50)
		print("\n=== 公有变量 ===")
		public_vars = self.get_all_public_variables()
		if public_vars:
			for name, variable in public_vars.items():
				value_display = DisplayHelper.truncate_value(variable.get())
				print(f"  {name}: {value_display}")
		else:
			print("  无公有变量")
		print("\n=== 私有变量 ===")
		private_vars = self.get_all_private_variables()
		if private_vars:
			for name, variable in private_vars.items():
				value_display = DisplayHelper.truncate_value(variable.get())
				print(f"  {name}: {value_display}")
		else:
			print("  无私有变量")
		print("\n=== 云列表 ===")
		lists = self.get_all_lists()
		if lists:
			for name, cloud_list in lists.items():
				value_display = DisplayHelper.truncate_value(cloud_list.value)
				print(f"  {name}: {value_display} (长度: {cloud_list.length()})")
		else:
			print("  无云列表")
		print(f"\n在线用户数: {self.online_users}")
		print("=" * 50)


class CloudManager:
	"""云数据管理器,提供高级API"""

	def __init__(self, work_id: int, editor: EditorType | None = None, authorization_token: str | None = None) -> None:
		self.connection = CloudConnection(work_id, editor, authorization_token)

	def connect(self, *, wait_for_data: bool = True) -> bool:
		"""连接并等待数据就绪"""
		self.connection.connect()
		if not self.connection.wait_for_connection():
			return False
		if wait_for_data:
			return self.connection.wait_for_data()
		return True

	def close(self) -> None:
		"""关闭连接"""
		self.connection.close()

	def get_available_variables(self) -> dict[str, list[str]]:
		"""获取所有可用变量信息"""
		return {
			"private_variables": list(self.connection.get_all_private_variables().keys()),
			"public_variables": list(self.connection.get_all_public_variables().keys()),
			"lists": list(self.connection.get_all_lists().keys()),
		}


class CloudCommandLineInterface(cmd.Cmd):
	"""云数据交互式命令行界面"""

	def __init__(self, cloud_manager: CloudManager) -> None:
		super().__init__()
		self.manager = cloud_manager
		self.connection = cloud_manager.connection
		self.prompt = "云数据> "
		self.intro = self._get_welcome_message()

	def _get_welcome_message(self) -> str:
		"""生成欢迎消息,包含可用变量信息"""
		welcome = "欢迎使用云数据交互式命令行! 输入 help 或 ? 查看可用命令。\n"
		if self.connection.data_ready:
			available = self.manager.get_available_variables()
			welcome += "\n当前可用数据:\n"
			if available["private_variables"]:
				welcome += f"  私有变量: {', '.join(available['private_variables'])}\n"
			if available["public_variables"]:
				welcome += f"  公有变量: {', '.join(available['public_variables'])}\n"
			if available["lists"]:
				welcome += f"  云列表: {', '.join(available['lists'])}\n"
		return welcome

	def preloop(self) -> None:
		"""在循环开始前检查连接状态"""
		if not self.connection.connected:
			print("警告: 云连接未建立, 请先等待连接成功")

	def cmdloop(self, intro: str | None = None) -> None:
		"""重写cmdloop以支持动态更新提示符"""
		self.preloop()
		if intro is not None:
			self.intro = intro
		if self.intro:
			print(self.intro)
		stop = None
		while not stop:
			try:
				# 动态更新提示符显示状态
				status_indicator = "✓" if self.connection.connected else "✗"
				data_indicator = "✓" if self.connection.data_ready else "✗"
				self.prompt = f"云数据[{status_indicator}{data_indicator}]> "
				line = input(self.prompt)
				line = self.precmd(line)
				stop = self.onecmd(line)
				stop = self.postcmd(stop, line)
			except KeyboardInterrupt:
				print("\n使用 'exit' 命令退出程序")
			except EOFError:
				print()
				break

	def do_status(self, _arg: str) -> None:
		"""查看连接状态和数据状态"""
		print(f"连接状态: {'已连接' if self.connection.connected else '未连接'}")
		print(f"数据就绪: {'是' if self.connection.data_ready else '否'}")
		print(f"在线用户: {self.connection.online_users}")
		if self.connection.data_ready:
			available = self.manager.get_available_variables()
			print("\n可用数据统计:")
			print(f"  私有变量: {len(available['private_variables'])} 个")
			print(f"  公有变量: {len(available['public_variables'])} 个")
			print(f"  云列表: {len(available['lists'])} 个")

	def do_available(self, arg: str) -> None:  # noqa: PLR0912
		"""显示所有可用变量和列表
		用法: available [详细]"""
		if not self.connection.data_ready:
			print("数据尚未就绪, 请等待连接完成")
			return
		available = self.manager.get_available_variables()
		show_details = arg.strip().lower() in {"详细", "detail", "verbose"}
		print("\n" + "=" * 40)
		print("可用数据列表")
		print("=" * 40)
		print("\n=== 私有变量 ===")
		if available["private_variables"]:
			for name in available["private_variables"]:
				var = self.connection.get_private_variable(name)
				if var and show_details:
					value_display = DisplayHelper.truncate_value(var.get())
					print(f"  {name}: {value_display}")
				else:
					print(f"  {name}")
		else:
			print("  无私有变量")
		print("\n=== 公有变量 ===")
		if available["public_variables"]:
			for name in available["public_variables"]:
				var = self.connection.get_public_variable(name)
				if var and show_details:
					value_display = DisplayHelper.truncate_value(var.get())
					print(f"  {name}: {value_display}")
				else:
					print(f"  {name}")
		else:
			print("  无公有变量")
		print("\n=== 云列表 ===")
		if available["lists"]:
			for name in available["lists"]:
				cloud_list = self.connection.get_list(name)
				if cloud_list and show_details:
					value_display = DisplayHelper.truncate_value(cloud_list.value)
					print(f"  {name}: {value_display} (长度: {cloud_list.length()})")
				else:
					print(f"  {name}")
		else:
			print("  无云列表")

	def do_list(self, arg: str) -> None:
		"""列出所有数据
		用法: list [type]
		type: private(私有变量) / public(公有变量) / lists(列表) / all(全部)"""
		args = shlex.split(arg)
		show_type = args[0] if args else "all"
		valid_types = {"all", "private", "public", "lists"}
		if show_type not in valid_types:
			print(f"错误: 类型必须是 {', '.join(valid_types)} 之一")
			return
		if show_type in {"all", "private"}:
			print("\n=== 私有变量 ===")
			private_vars = self.connection.get_all_private_variables()
			if private_vars:
				for name, var in private_vars.items():
					value_display = DisplayHelper.truncate_value(var.get())
					print(f"  {name}: {value_display}")
			else:
				print("  无私有变量")
		if show_type in {"all", "public"}:
			print("\n=== 公有变量 ===")
			public_vars = self.connection.get_all_public_variables()
			if public_vars:
				for name, var in public_vars.items():
					value_display = DisplayHelper.truncate_value(var.get())
					print(f"  {name}: {value_display}")
			else:
				print("  无公有变量")
		if show_type in {"all", "lists"}:
			print("\n=== 云列表 ===")
			lists = self.connection.get_all_lists()
			if lists:
				for name, cloud_list in lists.items():
					value_display = DisplayHelper.truncate_value(cloud_list.value)
					print(f"  {name}: {value_display} (长度: {cloud_list.length()})")
			else:
				print("  无云列表")

	def do_get(self, arg: str) -> None:
		"""获取特定变量的值
		用法: get <变量名>"""
		if not arg:
			print("错误: 请指定变量名")
			return
		name = arg.strip()
		private_var = self.connection.get_private_variable(name)
		if private_var:
			value_display = DisplayHelper.truncate_value(private_var.get())
			print(f"私有变量 {name}: {value_display}")
			return
		public_var = self.connection.get_public_variable(name)
		if public_var:
			value_display = DisplayHelper.truncate_value(public_var.get())
			print(f"公有变量 {name}: {value_display}")
			return
		cloud_list = self.connection.get_list(name)
		if cloud_list:
			value_display = DisplayHelper.truncate_value(cloud_list.value)
			print(f"云列表 {name}: {value_display} (长度: {cloud_list.length()})")
			return
		print(f"错误: 未找到变量或列表 '{name}'")
		print("使用 'available' 命令查看所有可用变量")

	def do_set_private(self, arg: str) -> None:
		"""设置私有变量的值
		用法: set_private <变量名> <值>"""
		args = shlex.split(arg)
		if len(args) < MIN_SET_ARGS:
			print("错误: 用法: set_private <变量名> <值>")
			print("使用 'available' 查看可用私有变量")
			return
		name = args[0]
		value = args[1]
		value = self._parse_value(value)
		if self.connection.set_private_variable(name, value):
			print(f"成功设置私有变量 {name} = {value}")
		else:
			print(f"错误: 设置私有变量失败, 请检查变量名 '{name}'")
			print("使用 'available' 查看可用私有变量")

	def do_set_public(self, arg: str) -> None:
		"""设置公有变量的值
		用法: set_public <变量名> <值>"""
		args = shlex.split(arg)
		if len(args) < MIN_SET_ARGS:
			print("错误: 用法: set_public <变量名> <值>")
			print("使用 'available' 查看可用公有变量")
			return
		name = args[0]
		value = args[1]
		value = self._parse_value(value)
		if self.connection.set_public_variable(name, value):
			print(f"成功设置公有变量 {name} = {value}")
		else:
			print(f"错误: 设置公有变量失败, 请检查变量名 '{name}'")
			print("使用 'available' 查看可用公有变量")

	@staticmethod
	def _parse_value(value: str) -> int | str:
		"""解析输入的值,尝试转换为整数"""
		try:
			if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
				return int(value)
		except Exception:  # noqa: S110
			pass
		return value

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
		if len(args) < MIN_LIST_OPERATION_ARGS:
			print("错误: 参数不足")
			self.help_list_operations()
			return
		operation = args[0]
		list_name = args[1]
		cloud_list = self.connection.get_list(list_name)
		if not cloud_list:
			print(f"错误: 未找到列表 '{list_name}'")
			print("使用 'available' 查看可用列表")
			return
		operation_handlers = {
			"push": self._handle_list_push,
			"pop": self._handle_list_pop,
			"unshift": self._handle_list_unshift,
			"shift": self._handle_list_shift,
			"insert": self._handle_list_insert,
			"remove": self._handle_list_remove,
			"replace": self._handle_list_replace,
			"clear": self._handle_list_clear,
			"get": self._handle_list_get,
		}
		handler = operation_handlers.get(operation)
		if handler:
			handler(cloud_list, args[2:])
		else:
			print(f"错误: 未知操作 '{operation}'")
			self.help_list_operations()

	def _handle_list_push(self, cloud_list: CloudList, args: list[str]) -> None:
		"""处理列表push操作"""
		if len(args) < MIN_GET_ARGS:
			print("错误: 需要提供要添加的值")
			return
		value = self._parse_value(args[0])
		if self.connection.list_push(cloud_list.name, value):
			print(f"成功向列表 {cloud_list.name} 添加元素: {value}")
		else:
			print("添加元素失败")

	def _handle_list_pop(self, cloud_list: CloudList, _args: list[str]) -> None:
		"""处理列表pop操作"""
		if self.connection.list_pop(cloud_list.name):
			print(f"成功从列表 {cloud_list.name} 弹出最后一个元素")
		else:
			print("弹出元素失败")

	def _handle_list_unshift(self, cloud_list: CloudList, args: list[str]) -> None:
		"""处理列表unshift操作"""
		if len(args) < MIN_GET_ARGS:
			print("错误: 需要提供要添加的值")
			return
		value = self._parse_value(args[0])
		if self.connection.list_unshift(cloud_list.name, value):
			print(f"成功向列表 {cloud_list.name} 开头添加元素: {value}")
		else:
			print("添加元素失败")

	def _handle_list_shift(self, cloud_list: CloudList, _args: list[str]) -> None:
		"""处理列表shift操作"""
		if self.connection.list_shift(cloud_list.name):
			print(f"成功从列表 {cloud_list.name} 移除第一个元素")
		else:
			print("移除元素失败")

	def _handle_list_insert(self, cloud_list: CloudList, args: list[str]) -> None:
		"""处理列表insert操作"""
		if len(args) < MIN_INSERT_ARGS:
			print("错误: 需要提供位置和值")
			return
		try:
			index = int(args[0])
			value = self._parse_value(args[1])
			if self.connection.list_insert(cloud_list.name, index, value):
				print(f"成功在列表 {cloud_list.name} 位置 {index} 插入元素: {value}")
			else:
				print("插入元素失败")
		except ValueError:
			print("错误: 位置必须是整数")

	def _handle_list_remove(self, cloud_list: CloudList, args: list[str]) -> None:
		"""处理列表remove操作"""
		if len(args) < MIN_REMOVE_ARGS:
			print("错误: 需要提供位置")
			return
		try:
			index = int(args[0])
			if self.connection.list_remove(cloud_list.name, index):
				print(f"成功从列表 {cloud_list.name} 位置 {index} 移除元素")
			else:
				print("移除元素失败")
		except ValueError:
			print("错误: 位置必须是整数")

	def _handle_list_replace(self, cloud_list: CloudList, args: list[str]) -> None:
		"""处理列表replace操作"""
		if len(args) < MIN_REPLACE_ARGS:
			print("错误: 需要提供位置和值")
			return
		try:
			index = int(args[0])
			value = self._parse_value(args[1])
			if self.connection.list_replace(cloud_list.name, index, value):
				print(f"成功替换列表 {cloud_list.name} 位置 {index} 的元素为: {value}")
			else:
				print("替换元素失败")
		except ValueError:
			print("错误: 位置必须是整数")

	def _handle_list_clear(self, cloud_list: CloudList, _args: list[str]) -> None:
		"""处理列表clear操作"""
		if self.connection.list_clear(cloud_list.name):
			print(f"成功清空列表 {cloud_list.name}")
		else:
			print("清空列表失败")

	@staticmethod
	def _handle_list_get(cloud_list: CloudList, args: list[str]) -> None:
		"""处理列表get操作"""
		if len(args) < MIN_GET_ARGS:
			print("错误: 需要提供位置")
			return
		try:
			index = int(args[0])
			value = cloud_list.get(index)
			if value is not None:
				print(f"列表 {cloud_list.name} 位置 {index} 的元素: {value}")
			else:
				print(f"错误: 位置 {index} 超出范围")
		except ValueError:
			print("错误: 位置必须是整数")

	@staticmethod
	def help_list_operations() -> None:
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
		数量: 默认10, 最大31
		排序: 1(升序) 或 -1(降序, 默认)"""
		args = shlex.split(arg)
		if not args:
			print("错误: 请指定变量名")
			print("使用 'available' 查看可用私有变量")
			return
		name = args[0]
		limit = 10
		order = DESCENDING_ORDER
		if len(args) > 1:
			try:
				limit = int(args[1])
				if limit < MIN_RANKING_LIMIT or limit > MAX_RANKING_LIMIT:
					print(f"警告: 数量范围{MIN_RANKING_LIMIT}-{MAX_RANKING_LIMIT}, 使用默认值10")
					limit = 10
			except ValueError:
				print("错误: 数量必须是数字")
				return
		if len(args) > 2:  # noqa: PLR2004
			try:
				order = int(args[2])
				if order not in {ASCENDING_ORDER, DESCENDING_ORDER}:
					print("错误: 排序必须是1(升序)或-1(降序)")
					return
			except ValueError:
				print("错误: 排序必须是数字")
				return
		variable = self.connection.get_private_variable(name)
		if not variable:
			print(f"错误: 未找到私有变量 '{name}'")
			print("使用 'available' 查看可用私有变量")
			return
		print(f"获取 {name} 的排行榜...")
		self.connection.get_private_variable_ranking(name, limit, order)

	def do_refresh(self, _arg: str) -> None:
		"""刷新显示所有数据"""
		self.connection.print_all_data()

	def do_online(self, _arg: str) -> None:
		"""查看在线用户数"""
		print(f"当前在线用户: {self.connection.online_users}")

	def do_exit(self, _arg: str) -> bool:
		"""退出程序"""
		print("正在关闭连接...")
		self.manager.close()
		return True

	def do_quit(self, _arg: str) -> bool:
		"""退出程序"""
		return self.do_exit(_arg)

	def do_eof(self, _arg: str) -> bool:
		"""Ctrl+D 退出"""
		print()
		return self.do_exit(_arg)
