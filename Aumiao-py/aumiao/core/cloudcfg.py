from collections.abc import Callable
from dataclasses import dataclass
from json import JSONDecodeError, dumps, loads
from threading import Lock, RLock, Thread, Timer, current_thread
from time import sleep, time
from typing import Any, Protocol, cast

from websocket import WebSocketApp

from aumiao.api import work
from aumiao.api.auth import CloudAuthenticator
from aumiao.core.models import (
	DataConfig,
	DataType,
	DisplayConfig,
	EditorType,
	ErrorMessages,
	ReceiveMessageType,
	SendMessageType,
	ValidationConfig,
	WebSocketConfig,
)


# neko (KittenN) 貌似不支持查询在线人数, 而排行榜数据需要反编译后获取 work_file ["rankings"]["rankingsDict"], 之后获取 rankingId 得到的 id 通过两个 api 进行更改和获取
# ==============================
# 命令模式接口
# ==============================
class Command(Protocol):
	"""命令接口"""

	def execute(self, connection: "CloudConnection") -> None: ...


@dataclass
class VariableUpdateCommand:
	"""变量更新命令"""

	command_type: str
	data: dict[str, Any]

	def execute(self, connection: "CloudConnection") -> None:
		if self.command_type == "update_private_vars":
			connection.send_message(SendMessageType.UPDATE_PRIVATE_VARIABLE, [self.data])
		elif self.command_type == "update_vars":
			connection.send_message(SendMessageType.UPDATE_PUBLIC_VARIABLE, [self.data])


@dataclass
class ListUpdateCommand:
	"""列表更新命令"""

	cvid: str
	operations: list[dict[str, Any]]

	def execute(self, connection: "CloudConnection") -> None:
		connection.send_message(SendMessageType.UPDATE_LIST, {self.cvid: self.operations})


# ==============================
# 类型别名定义 (Type Aliases)
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
# 工具类 (Utilities)
# ==============================
class DisplayHelper:
	"""显示辅助类 - 使用外部导入的 DisplayConfig"""

	@staticmethod
	def truncate_value(value: Any, max_length: int = DisplayConfig.MAX_DISPLAY_LENGTH) -> str:
		"""截断过长的值用于显示"""
		if isinstance(value, (int, float, bool)):
			return str(value)
		str_value = str(value)
		if len(str_value) <= max_length:
			return str_value
		# 对于列表的特殊处理
		if isinstance(value, list):
			if len(value) <= DisplayConfig.MAX_LIST_DISPLAY_ELEMENTS:
				return str(value)
			first_part = value[: DisplayConfig.PARTIAL_LIST_DISPLAY_COUNT]
			last_part = value[-DisplayConfig.PARTIAL_LIST_DISPLAY_COUNT :]
			return f"[{', '.join(map(str, first_part))}, ..., {', '.join(map(str, last_part))}]"
		# 对于长字符串
		half_length = max_length // 2 - len(DisplayConfig.TRUNCATED_SUFFIX) // 2
		return f"{str_value[:half_length]}{DisplayConfig.TRUNCATED_SUFFIX}{str_value[-half_length:]}"


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


# ==============================
# 命令工厂
# ==============================
class CommandFactory:
	"""命令工厂类"""

	@staticmethod
	def create_variable_command(command_type: str, data: dict[str, Any]) -> VariableUpdateCommand:
		"""创建变量更新命令"""
		return VariableUpdateCommand(command_type, data)

	@staticmethod
	def create_list_command(cvid: str, operations: list[dict[str, Any]]) -> ListUpdateCommand:
		"""创建列表更新命令"""
		return ListUpdateCommand(cvid, operations)


# ==============================
# 内部实现 (Core Implementation)
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

	def remove_change_callback(self, callback: Callable[..., None]) -> None:
		"""移除数据变更回调"""
		if callback in self._change_callbacks:
			self._change_callbacks.remove(callback)

	def emit_change(self, old_value: CloudValueType | CloudListValueType, new_value: CloudValueType | CloudListValueType, source: str) -> None:
		"""触发数据变更回调"""
		for callback in self._change_callbacks[:]:
			try:
				callback(old_value, new_value, source)
			except Exception as error:
				print(f"{ErrorMessages.CALLBACK_EXECUTION}: {error}")


class CloudVariable(CloudDataItem):
	"""云变量基类"""

	def __init__(self, connection: "CloudConnection", cloud_variable_id: str, name: str, value: CloudValueType) -> None:
		# 调用父类初始化, 父类会创建_change_callbacks 列表
		super().__init__(connection, cloud_variable_id, name, value)
		# 注意: 我们不在这里重新定义_change_callbacks, 而是使用父类的
		# 父类的_change_callbacks 类型是 list [Callable [..., None]]
		# 但我们需要确保注册的回调是 ChangeCallbackType 类型

	def on_change(self, callback: ChangeCallbackType) -> None:
		"""注册变量变更回调"""
		# 将 ChangeCallbackType 添加到父类的回调列表中
		self._change_callbacks.append(callback)

	def remove_change_callback(self, callback: ChangeCallbackType) -> None:
		"""移除变量变更回调"""
		if callback in self._change_callbacks:
			self._change_callbacks.remove(callback)

	def get(self) -> CloudValueType:
		"""获取变量值"""
		return cast("CloudValueType", self.value)

	def set(self, value: CloudValueType) -> bool:
		"""设置变量值"""
		if not isinstance(value, (int, str)):
			raise TypeError(ErrorMessages.INVALID_VARIABLE_TYPE)
		old_value = self.value
		self.value = value
		self.emit_change(old_value, value, "local")
		return True

	def emit_change(self, old_value: CloudValueType | CloudListValueType, new_value: CloudValueType | CloudListValueType, source: str) -> None:
		"""触发变量变更回调"""
		if not isinstance(old_value, (int, str)) or not isinstance(new_value, (int, str)):
			print(f"警告: 云变量值类型不匹配, 期望 int 或 str, 得到 old_value: {type(old_value)}, new_value: {type(new_value)}")
			return
		for callback in self._change_callbacks[:]:
			try:
				callback(old_value, new_value, source)
			except Exception as error:
				print(f"{ErrorMessages.CLOUD_VARIABLE_CALLBACK}: {error}")


class PrivateCloudVariable(CloudVariable):
	"""私有云变量类"""

	def __init__(self, connection: "CloudConnection", cloud_variable_id: str, name: str, value: CloudValueType) -> None:
		super().__init__(connection, cloud_variable_id, name, value)
		self._ranking_callbacks: list[RankingCallbackType] = []

	def on_ranking_received(self, callback: RankingCallbackType) -> None:
		"""注册排行榜数据接收回调"""
		self._ranking_callbacks.append(callback)

	def remove_ranking_callback(self, callback: RankingCallbackType) -> None:
		"""移除排行榜数据接收回调"""
		if callback in self._ranking_callbacks:
			self._ranking_callbacks.remove(callback)

	def emit_ranking(self, ranking_data: list[dict[str, Any]]) -> None:
		"""触发排行榜数据接收回调"""
		for callback in self._ranking_callbacks[:]:
			try:
				callback(ranking_data)
			except Exception as error:
				print(f"{ErrorMessages.RANKING_CALLBACK}: {error}")

	def get_ranking_list(self, limit: int = DataConfig.DEFAULT_RANKING_LIMIT, order: int = ValidationConfig.DESCENDING_ORDER) -> None:
		"""获取排行榜列表"""
		if not isinstance(limit, int) or limit <= 0:
			raise ValueError(ErrorMessages.INVALID_RANKING_LIMIT)
		if order not in {ValidationConfig.ASCENDING_ORDER, ValidationConfig.DESCENDING_ORDER}:
			raise ValueError(ErrorMessages.INVALID_RANKING_ORDER)
		request_data = {"cvid": self.cloud_variable_id, "limit": limit, "order_type": order}
		self.connection.send_message(SendMessageType.GET_PRIVATE_VARIABLE_RANKING_LIST, request_data)


class PublicCloudVariable(CloudVariable):
	"""公有云变量类"""


class CloudList(CloudDataItem):
	"""云列表类"""

	def __init__(self, connection: "CloudConnection", cloud_variable_id: str, name: str, value: CloudListValueType) -> None:
		super().__init__(connection, cloud_variable_id, name, value or [])
		# 注意: 我们不需要在 CloudList 中重新定义_change_callbacks
		# 使用父类的回调列表, 类型为 list [Callable [..., None]]
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

	def emit_change(self, old_value: CloudValueType | CloudListValueType, new_value: CloudValueType | CloudListValueType, source: str) -> None:
		"""触发数据变更回调"""
		if not isinstance(old_value, list) or not isinstance(new_value, list):
			print(f"警告: 云列表值类型不匹配, 期望 list, 得到 old_value: {type(old_value)}, new_value: {type(new_value)}")
			return
		for callback in self._change_callbacks[:]:
			try:
				callback(old_value, new_value, source)
			except Exception as error:
				print(f"{ErrorMessages.CALLBACK_EXECUTION}: {error}")

	def on_operation(self, operation: str, callback: ListOperationCallbackType) -> None:
		"""注册列表操作回调"""
		if operation in self._operation_callbacks:
			self._operation_callbacks[operation].append(callback)

	def remove_operation_callback(self, operation: str, callback: ListOperationCallbackType) -> None:
		"""移除列表操作回调"""
		if operation in self._operation_callbacks and callback in self._operation_callbacks[operation]:
			self._operation_callbacks[operation].remove(callback)

	def _emit_operation(self, operation: str, *args: object) -> None:
		"""触发列表操作回调"""
		for callback in self._operation_callbacks[operation][:]:
			try:
				callback(*args)
			except Exception as error:
				print(f"{ErrorMessages.OPERATION_CALLBACK}: {error}")

	def get(self, index: int) -> CloudValueType | None:
		"""获取指定位置的元素"""
		if isinstance(self.value, list) and ValidationConfig.MIN_LIST_INDEX <= index < len(self.value):
			return self.value[index]
		return None

	def push(self, item: CloudValueType) -> bool:
		"""向列表末尾添加元素"""
		if not isinstance(item, (int, str)):
			raise TypeError(ErrorMessages.INVALID_LIST_ITEM_TYPE)
		if isinstance(self.value, list):
			self.value.append(item)
			self._emit_operation("push", item, len(self.value) - 1)
			return True
		return False

	def pop(self) -> CloudValueType | None:
		"""移除并返回列表最后一个元素"""
		if isinstance(self.value, list) and self.value:
			item = self.value.pop()
			self._emit_operation("pop", item, len(self.value))
			return cast("CloudValueType", item)
		return None

	def unshift(self, item: CloudValueType) -> bool:
		"""向列表开头添加元素"""
		if not isinstance(item, (int, str)):
			raise TypeError(ErrorMessages.INVALID_LIST_ITEM_TYPE)
		if isinstance(self.value, list):
			self.value.insert(ValidationConfig.FIRST_ELEMENT_INDEX, item)
			self._emit_operation("unshift", item, ValidationConfig.FIRST_ELEMENT_INDEX)
			return True
		return False

	def shift(self) -> CloudValueType | None:
		"""移除并返回列表第一个元素"""
		if isinstance(self.value, list) and self.value:
			item = self.value.pop(ValidationConfig.FIRST_ELEMENT_INDEX)
			self._emit_operation("shift", item, ValidationConfig.FIRST_ELEMENT_INDEX)
			return cast("CloudValueType", item)
		return None

	def insert(self, index: int, item: CloudValueType) -> bool:
		"""在指定位置插入元素"""
		if not isinstance(item, (int, str)):
			raise TypeError(ErrorMessages.INVALID_LIST_ITEM_TYPE)
		if isinstance(self.value, list) and ValidationConfig.MIN_LIST_INDEX <= index <= len(self.value):
			self.value.insert(index, item)
			self._emit_operation("insert", item, index)
			return True
		return False

	def remove(self, index: int) -> CloudValueType | None:
		"""移除指定位置的元素"""
		if isinstance(self.value, list) and ValidationConfig.MIN_LIST_INDEX <= index < len(self.value):
			item = self.value.pop(index)
			self._emit_operation("remove", item, index)
			return cast("CloudValueType", item)
		return None

	def replace(self, index: int, item: CloudValueType) -> bool:
		"""替换指定位置的元素"""
		if not isinstance(item, (int, str)):
			raise TypeError(ErrorMessages.INVALID_LIST_ITEM_TYPE)
		if isinstance(self.value, list) and ValidationConfig.MIN_LIST_INDEX <= index < len(self.value):
			old_item = self.value[index]
			self.value[index] = item
			self._emit_operation("replace", old_item, item, index)
			return True
		return False

	def replace_last(self, item: CloudValueType) -> bool:
		"""替换列表最后一个元素"""
		if not isinstance(item, (int, str)):
			raise TypeError(ErrorMessages.INVALID_LIST_ITEM_TYPE)
		if isinstance(self.value, list) and self.value:
			old_item = self.value[ValidationConfig.LAST_ELEMENT_INDEX]
			self.value[ValidationConfig.LAST_ELEMENT_INDEX] = item
			self._emit_operation("replace_last", old_item, item)
			return True
		return False

	def clear(self) -> bool:
		"""清空列表所有元素"""
		if isinstance(self.value, list):
			old_value = self.value.copy()
			self.value.clear()
			self._emit_operation("clear", old_value)
			return True
		return False

	def length(self) -> int:
		"""获取列表长度"""
		if isinstance(self.value, list):
			return len(self.value)
		return 0

	def index_of(self, item: CloudValueType) -> int:
		"""查找元素第一次出现的索引"""
		try:
			if isinstance(self.value, list):
				return self.value.index(item)
		except ValueError:
			return -1
		return -1

	def last_index_of(self, item: CloudValueType) -> int:
		"""查找元素最后一次出现的索引"""
		try:
			if isinstance(self.value, list) and self.value:
				return len(self.value) - 1 - self.value[::-1].index(item)
		except ValueError:
			return -1
		return -1

	def includes(self, item: CloudValueType) -> bool:
		"""检查列表是否包含指定元素"""
		if isinstance(self.value, list):
			return item in self.value
		return False

	def join(self, separator: str = ",") -> str:
		"""将列表元素连接为字符串"""
		if isinstance(self.value, list):
			return separator.join(str(item) for item in self.value)
		return ""

	def copy(self) -> list[CloudValueType]:
		"""返回列表的浅拷贝"""
		if isinstance(self.value, list):
			return self.value.copy()
		return []

	def copy_from(self, source_list: list[CloudValueType]) -> bool:
		"""从源列表复制数据"""
		if source_list and not isinstance(source_list[0], (int, str)):
			return False
		if isinstance(self.value, list):
			old_value = self.value.copy()
			self.value = source_list.copy()
			self.emit_change(old_value, self.value, "local")
			return True
		return False


class CloudConnection:
	"""云连接核心类"""

	def __init__(self, work_id: int, editor: EditorType | None = None, authorization_token: str | None = None) -> None:
		self._ping_thread: Thread | None = None
		self.authenticator = CloudAuthenticator(authorization_token)
		self.auto_reconnect = True
		self.connected = False
		self.editor = editor
		self.lists: dict[str, CloudList] = {}
		self.max_reconnect_attempts = DataConfig.MAX_RECONNECT_ATTEMPTS
		self.private_variables: dict[str, PrivateCloudVariable] = {}
		self.public_variables: dict[str, PublicCloudVariable] = {}
		self.reconnect_attempts = 0
		self.reconnect_interval = DataConfig.RECONNECT_INTERVAL
		self.websocket_client: WebSocketApp | None = None
		self.work_id = work_id
		self._callbacks: dict[str, list[Callable[..., None]]] = {
			"open": [],
			"close": [],
			"error": [],
			"message": [],
			"data_ready": [],
			"online_users_change": [],
			"ranking_received": [],
			"server_close": [],
		}
		self._connection_lock = RLock()
		self._is_closing = False
		self._join_sent = False
		self._last_activity_time = 0.0
		self._lists_lock = RLock()
		self._pending_ranking_requests: list[PrivateCloudVariable] = []
		self._pending_requests_lock = Lock()
		self._ping_active = False
		self._ping_interval = 0
		self._ping_timeout = 0
		self._variables_lock = RLock()
		self._websocket_thread: Thread | None = None
		self._work_info: WorkInfo | None = None
		self.data_ready = False
		self.online_users = 0
		self._last_ping_time: float = 0.0
		self._last_pong_time: float = 0.0
		self._ping_interval: int = DataConfig.PING_INTERVAL_MS
		self._ping_timeout: int = DataConfig.PING_TIMEOUT_MS
		self._heartbeat_timer: Timer | None = None
		self._command_queue: list[Command] = []  # 使用命令对象队列
		self._command_queue_lock = RLock()
		self._upload_timer: Timer | None = None
		self._upload_interval: float = 0.1

	def _queue_variable_command(self, command_type: str, data: dict[str, Any]) -> None:
		"""将变量更新命令加入队列"""
		command = CommandFactory.create_variable_command(command_type, data)
		self._queue_command(command)

	def _queue_list_command(self, cvid: str, operations: list[dict[str, Any]]) -> None:
		"""将列表更新命令加入队列"""
		command = CommandFactory.create_list_command(cvid, operations)
		self._queue_command(command)

	def _queue_command(self, command: Command) -> None:
		"""将命令加入队列等待批量上传"""
		with self._command_queue_lock:
			self._command_queue.append(command)
			if self._upload_timer is None:
				self._upload_timer = Timer(self._upload_interval, self._upload_batch)
				self._upload_timer.daemon = True
				self._upload_timer.start()

	def _upload_batch(self) -> None:
		"""批量上传队列中的命令"""
		with self._command_queue_lock:
			if not self.connected or not self.websocket_client or self._is_closing:
				self._command_queue.clear()
				self._upload_timer = None
				return
			if not self._command_queue:
				self._upload_timer = None
				return
			# 分组命令
			variable_commands: list[VariableUpdateCommand] = []
			list_commands: dict[str, ListUpdateCommand] = {}
			for command in self._command_queue:
				if isinstance(command, VariableUpdateCommand):
					variable_commands.append(command)
				elif isinstance(command, ListUpdateCommand):
					if command.cvid not in list_commands:
						list_commands[command.cvid] = command
					else:
						# 合并相同 cvid 的操作
						list_commands[command.cvid].operations.extend(command.operations)
			# 清空队列
			self._command_queue.clear()
		try:
			# 执行批量命令
			# 合并变量命令
			if variable_commands:
				private_updates: list[dict[str, Any]] = []
				public_updates: list[dict[str, Any]] = []
				for cmd in variable_commands:
					if cmd.command_type == "update_private_vars":
						private_updates.append(cmd.data)
					elif cmd.command_type == "update_vars":
						public_updates.append(cmd.data)
				if private_updates:
					self.send_message(SendMessageType.UPDATE_PRIVATE_VARIABLE, private_updates)
				if public_updates:
					self.send_message(SendMessageType.UPDATE_PUBLIC_VARIABLE, public_updates)
			# 执行列表命令
			for list_cmd in list_commands.values():
				list_cmd.execute(self)
		except Exception as e:
			print(f"批量上传失败: {e}")
			# 将失败的命令重新加入队列
			with self._command_queue_lock:
				self._command_queue.extend(variable_commands)
				self._command_queue.extend(list_commands.values())
		finally:
			with self._command_queue_lock:
				self._upload_timer = None
				if self._command_queue and not self._upload_timer:
					self._upload_timer = Timer(self._upload_interval, self._upload_batch)
					self._upload_timer.daemon = True
					self._upload_timer.start()

	def _get_work_info(self) -> WorkInfo:
		"""获取作品信息"""
		if self._work_info is None:
			try:
				headers = {}
				if self.authenticator.authorization_token:
					headers["Cookie"] = f"Authorization={self.authenticator.authorization_token}"
				response = work.WorkDataFetcher().fetch_work_details(self.work_id)
				try:
					self._work_info = WorkInfo(response)
					print(f"✓ 作品: {self._work_info.name}")
					print(f"✓ 类型: {self._work_info.type}")
				except Exception:
					print("获取作品信息失败")
					self._work_info = WorkInfo({"id": self.work_id, "name": "未知作品", "type": "KITTEN"})
			except Exception as e:
				print(f"获取作品信息失败: {e}")
				self._work_info = WorkInfo({"id": self.work_id, "name": "未知作品", "type": "KITTEN"})
		return self._work_info

	def _determine_editor_type(self) -> EditorType:
		"""根据作品类型确定编辑器类型"""
		work_info = self._get_work_info()
		work_type = work_info.type
		if work_type == "WOOD":
			msg = "不支持 WOOD 作品类型"
			raise ValueError(msg)
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

	def remove_callback(self, event: str, callback: Callable[..., None]) -> None:
		"""移除事件回调"""
		if event in self._callbacks and callback in self._callbacks[event]:
			self._callbacks[event].remove(callback)

	def clear_callbacks(self, event: str | None = None) -> None:
		"""清除事件回调"""
		if event is not None:
			if event in self._callbacks:
				self._callbacks[event].clear()
		else:
			for callbacks in self._callbacks.values():
				callbacks.clear()

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
		# 如果正在关闭, 不触发事件
		if self._is_closing:
			return
		if event in self._callbacks:
			# 创建回调列表的副本, 避免在迭代时被修改
			callbacks_copy = self._callbacks[event].copy()
			for callback in callbacks_copy:
				try:
					callback(*args)
				except Exception as error:
					print(f"{ErrorMessages.EVENT_CALLBACK}: {error}")

	def _get_websocket_url(self) -> str:
		"""获取 WebSocket 连接 URL"""
		if self.editor is None:
			self.editor = self._determine_editor_type()
		editor_params = {
			EditorType.NEMO: {"authorization_type": "5", "stag": "2"},
			EditorType.KITTEN: {"authorization_type": "1", "stag": "1"},
			EditorType.KITTEN_N: {"authorization_type": "5", "stag": "3"},
			EditorType.COCO: {"authorization_type": "1", "stag": "1"},
		}
		params = editor_params.get(self.editor, editor_params[EditorType.KITTEN])
		params["EIO"] = "3"
		params["transport"] = WebSocketConfig.TRANSPORT_TYPE
		params_str = "&".join([f"{k}={v}" for k, v in params.items()])
		return f"wss://socketcv.codemao.cn:9096/cloudstorage/?session_id={self.work_id}&{params_str}"

	def _get_websocket_headers(self) -> dict[str, str]:
		"""获取 WebSocket 请求头"""
		headers: dict[str, str] = {}
		device_auth = self.authenticator.generate_x_device_auth()
		headers["X-Creation-Tools-Device-Auth"] = dumps(device_auth)
		if self.authenticator.authorization_token:
			headers["Cookie"] = f"Authorization={self.authenticator.authorization_token}"
		return headers

	def _on_message(self, _ws: WebSocketApp, message: str | bytes) -> None:
		"""WebSocket 消息处理"""
		if self._is_closing:
			return
		self._last_activity_time = time()
		try:
			if isinstance(message, bytes):
				try:
					message_str = message.decode("utf-8")
				except UnicodeDecodeError:
					return
			else:
				message_str = str(message)
			# 处理 ping/pong 消息
			if message_str in {WebSocketConfig.PING_MESSAGE, WebSocketConfig.PONG_MESSAGE}:
				return
			# 处理不同类型消息
			if message_str.startswith(WebSocketConfig.HANDSHAKE_MESSAGE_PREFIX):
				self._handle_handshake_message(message_str)
				return
			if message_str == WebSocketConfig.CONNECTED_MESSAGE:
				self._handle_connected_message()
				return
			if message_str.startswith(WebSocketConfig.SERVER_CLOSED_MESSAGE):
				# 服务器关闭请求在单独线程中处理
				Thread(target=self._handle_server_close_request, daemon=True).start()
				return
			if message_str.startswith(WebSocketConfig.EVENT_MESSAGE_PREFIX):
				self._handle_event_message(message_str)
				return
			# 记录未知消息
			if len(message_str) < 50:
				print(f"收到未知消息: {message_str}")
			else:
				print(f"收到未知消息: {message_str[:50]}...")
		except Exception as error:
			print(f"处理消息时出错: {error}")

	def _handle_handshake_message(self, message: str) -> None:
		"""处理握手消息"""
		try:
			handshake_data = loads(message[1:])
			self._ping_interval = handshake_data.get("pingInterval", 25000)
			self._ping_timeout = handshake_data.get("pingTimeout", 60000)
			print(f"✓ 握手成功, ping 间隔: {self._ping_interval} ms, ping 超时: {self._ping_timeout} ms")
			if self.websocket_client:
				self.websocket_client.send(WebSocketConfig.CONNECT_MESSAGE)
				print("✓ 已发送连接请求")
		except Exception as error:
			print(f"{ErrorMessages.HANDSHAKE_PROCESSING}: {error}")

	def _handle_connected_message(self) -> None:
		"""处理连接确认消息"""
		with self._connection_lock:
			self.connected = True
			self.reconnect_attempts = 0
		print("✓ 连接确认收到")
		self._emit_event("open")
		if not self._join_sent:
			self._join_sent = True
			Timer(0.5, self._send_join_message).start()

	def _handle_event_message(self, message: str) -> None:
		"""处理事件消息"""
		if self._is_closing or not self.connected:
			return
		try:
			data_str = message[WebSocketConfig.MESSAGE_TYPE_LENGTH :]
			data_list = loads(data_str)
			if isinstance(data_list, list) and len(data_list) >= 2:
				message_type = data_list[0]
				message_data = data_list[1]
				print(f"处理云消息: {message_type}, 数据: {DisplayHelper.truncate_value(message_data)}")
				if isinstance(message_data, str):
					try:
						parsed_data = loads(message_data)
						message_data = parsed_data
					except JSONDecodeError:
						print(f"警告: 无法解析消息数据为 JSON: {message_data[:100]}...")
				self._handle_cloud_message(message_type, message_data)
		except JSONDecodeError as error:
			print(f"{ErrorMessages.JSON_PARSE}: {error}, 数据: {DisplayHelper.truncate_value(message)}")
		except Exception as error:
			print(f"处理事件消息时发生未知错误: {error}")

	def _handle_server_close_request(self) -> None:
		"""处理服务器发送的关闭请求 (类型 41)"""
		print("收到服务器关闭请求 (类型 41)")
		# 首先检查是否已经在关闭过程中
		if self._is_closing:
			return
		# 发送服务器关闭事件
		server_close_reason = "服务器主动要求关闭连接"
		self._emit_event("server_close", {"type": "server_close", "reason": server_close_reason, "timestamp": time(), "code": 1000})
		# 设置关闭标志
		self._is_closing = True
		# 在单独的线程中执行清理和重连, 避免阻塞当前消息处理线程

		def cleanup_and_reconnect() -> None:
			# 清理连接
			self._cleanup_connection()
			# 检查是否应该重连
			should_reconnect = False
			if self.auto_reconnect and not self._is_closing and self.reconnect_attempts < self.max_reconnect_attempts:
				should_reconnect = True
			if should_reconnect:
				self.reconnect_attempts += 1
				delay = min(self.reconnect_interval * (2 ** (self.reconnect_attempts - 1)), 300)
				print(f"服务器要求关闭, 尝试重新连接 ({self.reconnect_attempts}/{self.max_reconnect_attempts}), 等待 {delay} 秒...")
				sleep(delay)
				self._safe_reconnect()
			else:
				print("服务器关闭连接, 重连已禁用或已达最大重试次数")

		# 在新线程中执行清理和重连
		cleanup_thread = Thread(target=cleanup_and_reconnect, daemon=True)
		cleanup_thread.start()

	def _send_join_message(self) -> None:
		"""发送加入消息"""
		if self.connected and self.websocket_client:
			print("发送 JOIN 消息...")
			self.send_message(SendMessageType.JOIN, str(self.work_id))

	def _start_ping(self, interval: int) -> None:
		"""启动 ping 线程"""
		if self._ping_thread is not None:
			self._ping_active = False
			self._ping_thread.join(timeout=1.0)
		self._ping_active = True

		def ping_task() -> None:
			while self._ping_active and self.connected:
				sleep(interval / 1000)
				if self._ping_active and self.connected and self.websocket_client:
					try:
						self.websocket_client.send(WebSocketConfig.PING_MESSAGE)
					except Exception as error:
						print(f"{ErrorMessages.PING_SEND}: {error}")
						break

		self._ping_thread = Thread(target=ping_task, daemon=True)
		self._ping_thread.start()

	def _stop_ping(self) -> None:
		"""停止 ping 线程"""
		self._ping_active = False
		if self._ping_thread and self._ping_thread.is_alive():
			# 检查不是当前线程
			if self._ping_thread != current_thread():
				self._ping_thread.join(timeout=1.0)
			self._ping_thread = None

	def _handle_cloud_message(self, message_type: str, data: dict[str, Any] | list[Any] | str) -> None:
		"""处理云消息"""
		if self._is_closing or not self.connected:
			return
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
				handler(data)  # pyright: ignore [reportArgumentType]  # ty:ignore [invalid-argument-type]
			else:
				print(f"未知消息类型: {message_type}, 数据: {DisplayHelper.truncate_value(data)}")
		except Exception as error:
			print(f"{ErrorMessages.CLOUD_MESSAGE_PROCESSING}: {error}")
			self._emit_event("error", error)

	def _handle_join_message(self, _data: object) -> None:
		"""处理加入消息"""
		print("✓ 连接加入成功, 请求所有数据...")
		self.send_message(SendMessageType.GET_ALL_DATA, {})

	def _handle_receive_all_data(self, data: list[dict[str, Any]]) -> None:
		"""处理接收完整数据消息"""
		print(f"收到完整数据: {DisplayHelper.truncate_value(data)}")
		if isinstance(data, str):
			try:
				data = loads(data)
			except JSONDecodeError as e:
				print(f"数据解析失败: {e}")
				return
		if not isinstance(data, list):
			print(f"数据格式错误, 期望列表, 得到: {type(data)}")
			print(f"原始数据: {DisplayHelper.truncate_value(data)}")
			return
		for item in data:
			if isinstance(item, dict):
				self._create_data_item(item)
			else:
				print(f"警告: 数据项不是字典类型: {type(item)}")
		self.data_ready = True
		print(f"✓ 数据准备完成! 私有变量: {len(self.private_variables)}, 公有变量: {len(self.public_variables)}, 列表: {len(self.lists)}")
		self._emit_event("data_ready")

	def _create_data_item(self, item: dict[str, Any]) -> None:
		"""创建数据项"""
		try:
			cloud_variable_id = item.get("cvid")
			name = item.get("name")
			value = item.get("value")
			data_type: int = cast("int", item.get("type"))
			if not all([cloud_variable_id, name, value is not None, data_type is not None]):
				print(f"数据项缺少必要字段: {DisplayHelper.truncate_value(item)}")
				return
			try:
				data_type = int(data_type)
			except (ValueError, TypeError):
				print(f"无效的数据类型: {data_type}")
				return
			if data_type == DataType.PRIVATE_VARIABLE.value:
				if not isinstance(value, (int, str)):
					print(f"警告: 私有变量值类型错误, 期望 int 或 str, 得到 {type(value)}")
					try:
						value = int(value) if isinstance(value, (float, bool)) else str(value)
					except Exception:
						value = str(value)
				self._create_private_variable(str(cloud_variable_id), str(name), value)
			elif data_type == DataType.PUBLIC_VARIABLE.value:
				if not isinstance(value, (int, str)):
					print(f"警告: 公有变量值类型错误, 期望 int 或 str, 得到 {type(value)}")
					try:
						value = int(value) if isinstance(value, (float, bool)) else str(value)
					except Exception:
						value = str(value)
				self._create_public_variable(str(cloud_variable_id), str(name), value)
			elif data_type == DataType.LIST.value:
				if not isinstance(value, list):
					print(f"警告: 列表数据不是列表类型, 进行转换: {type(value)} -> list")
					value = []
				validated_list: CloudListValueType = []
				if isinstance(value, list):
					for item_val in value:
						if isinstance(item_val, (int, str)):
							validated_list.append(item_val)
						else:
							try:
								if isinstance(item_val, (float, bool)):
									validated_list.append(int(item_val))
								else:
									validated_list.append(str(item_val))
							except Exception:
								validated_list.append(str(item_val))
				self._create_cloud_list(str(cloud_variable_id), str(name), validated_list)
			else:
				print(f"未知数据类型: {data_type}")
		except Exception as error:
			print(f"{ErrorMessages.CREATE_DATA_ITEM}: {error}, 数据: {DisplayHelper.truncate_value(item)}")

	def _create_private_variable(self, cloud_variable_id: str, name: str, value: CloudValueType) -> None:
		"""创建私有变量"""
		variable = PrivateCloudVariable(self, cloud_variable_id, name, value)
		with self._variables_lock:
			self.private_variables[name] = variable
			self.private_variables[cloud_variable_id] = variable

	def _create_public_variable(self, cloud_variable_id: str, name: str, value: CloudValueType) -> None:
		"""创建公有变量"""
		variable = PublicCloudVariable(self, cloud_variable_id, name, value)
		with self._variables_lock:
			self.public_variables[name] = variable
			self.public_variables[cloud_variable_id] = variable

	def _create_cloud_list(self, cloud_variable_id: str, name: str, value: CloudListValueType) -> None:
		"""创建云列表"""
		cloud_list = CloudList(self, cloud_variable_id, name, value)
		with self._lists_lock:
			self.lists[name] = cloud_list
			self.lists[cloud_variable_id] = cloud_list

	def _handle_update_private_variable(self, data: dict[str, Any]) -> None:
		"""处理更新私有变量消息"""
		if isinstance(data, dict) and "cvid" in data and "value" in data:
			data = cast("dict", data)
			cloud_variable_id = str(data["cvid"])
			new_value = data["value"]
			if not isinstance(new_value, (int, str)):
				print(f"警告: 私有变量值类型错误: {type(new_value)}")
				return
			for variable in self.private_variables.values():
				if variable.cloud_variable_id == cloud_variable_id:
					old_value = variable.value
					variable.value = new_value
					variable.emit_change(old_value, new_value, "cloud")
					break

	def _handle_receive_ranking_list(self, data: dict[str, Any]) -> None:
		"""处理接收排行榜列表消息"""
		with self._pending_requests_lock:
			if not self._pending_ranking_requests:
				print(ErrorMessages.NO_PENDING_REQUESTS)
				return
			variable = self._pending_ranking_requests.pop(0)
		if not isinstance(data, dict):
			print(f"{ErrorMessages.INVALID_RANKING_DATA}: {DisplayHelper.truncate_value(data)}")
			return
		ranking_data: list[dict[str, Any]] = []
		items = data.get("items")
		if not isinstance(items, list):
			print(f"警告: items 不是列表类型: {type(items)}")
			return
		for item in items:
			if isinstance(item, dict):
				try:
					value = item.get("value")
					identifier = item.get("identifier")
					nickname = item.get("nickname")
					avatar_url = item.get("avatar_url")
					if all([value is not None, identifier is not None, nickname is not None, avatar_url is not None]):
						ranking_data.append(
							{
								"value": value,
								"user": {
									"id": int(str(identifier)),
									"nickname": str(nickname),
									"avatar_url": str(avatar_url),
								},
							},
						)
				except (ValueError, TypeError) as e:
					print(f"排行榜数据解析错误: {e}")
		variable.emit_ranking(ranking_data)
		self._emit_event("ranking_received", variable, ranking_data)

	def _handle_update_public_variable(self, data: object) -> None:
		"""处理更新公有变量消息"""
		if data == "fail":
			return
		if isinstance(data, list):
			for item in data:
				if isinstance(item, dict) and "cvid" in item and "value" in item:
					item = cast("dict", item)
					cloud_variable_id = item["cvid"]
					new_value = item["value"]
					for variable in self.public_variables.values():
						if variable.cloud_variable_id == cloud_variable_id:
							old_value = variable.value
							variable.value = new_value
							variable.emit_change(old_value, new_value, "cloud")
							break

	def _handle_update_list(self, data: dict[str, list[dict[str, Any]]]) -> None:
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

	def _handle_update_online_users(self, data: dict[str, Any]) -> None:
		"""处理更新在线用户数消息"""
		if isinstance(data, dict) and "total" in data and isinstance(data["total"], int):
			old_count = self.online_users
			self.online_users = data["total"]
			self._emit_event("online_users_change", old_count, self.online_users)

	@staticmethod
	def _handle_illegal_event(_data: object) -> None:
		"""处理非法事件消息"""
		print("检测到非法事件")

	def _on_open(self, _ws: WebSocketApp) -> None:
		"""WebSocket 连接打开回调"""
		with self._connection_lock:
			self.connected = True
			self.reconnect_attempts = 0
		print("✓ WebSocket 连接已建立")
		self._emit_event("open")

	def _on_close(self, _ws: WebSocketApp, close_status_code: int, close_msg: str) -> None:
		"""WebSocket 连接关闭回调"""
		with self._connection_lock:
			was_connected = self.connected
			self.connected = False
			self.data_ready = False
			self._join_sent = False
		self._stop_ping()
		close_type = "unknown_close"
		close_desc = f"正常关闭: {close_status_code} - {close_msg}"
		print(f"WebSocket 连接已关闭: {close_desc}")
		self._emit_event("close", {"type": close_type, "code": close_status_code, "reason": close_msg, "timestamp": time(), "was_connected": was_connected})
		if was_connected and self.auto_reconnect and not self._is_closing:
			if self.reconnect_attempts < self.max_reconnect_attempts:
				self.reconnect_attempts += 1
				delay = min(self.reconnect_interval * (2 ** (self.reconnect_attempts - 1)), 300)
				print(f"尝试重新连接 ({self.reconnect_attempts}/{self.max_reconnect_attempts}), 等待 {delay} 秒...")
				Timer(delay, self._safe_reconnect).start()
			else:
				print(f"已达到最大重连次数 ({self.max_reconnect_attempts}), 停止重连")

	def _safe_reconnect(self) -> None:
		"""安全重连"""
		with self._connection_lock:
			if self.connected or self._is_closing:
				return
		print("开始重连...")
		try:
			self.connect()
		except Exception as e:
			print(f"重连失败: {e}")
			# 继续尝试重连
			if self.auto_reconnect and self.reconnect_attempts < self.max_reconnect_attempts:
				self.reconnect_attempts += 1
				delay = min(self.reconnect_interval * (2 ** (self.reconnect_attempts - 1)), 300)
				print(f"重连失败, 下次尝试 ({self.reconnect_attempts}/{self.max_reconnect_attempts}) 等待 {delay} 秒...")
				Timer(delay, self._safe_reconnect).start()

	def _on_error(self, _ws: WebSocketApp, error: Exception) -> None:
		"""WebSocket 错误回调"""
		print(f"WebSocket 错误: {error}")
		self._emit_event("error", error)

	def send_message(self, message_type: SendMessageType, data: dict[str, Any] | list[Any] | str) -> None:
		"""发送消息到云服务器"""
		if not self.websocket_client or not self.connected:
			print("错误: 连接未就绪, 无法发送消息")
			return
		message_content = [message_type.value, data]
		message = f"{WebSocketConfig.EVENT_MESSAGE_PREFIX}{dumps(message_content)}"
		try:
			self.websocket_client.send(message)
			self._last_activity_time = time()
		except Exception as error:
			print(f"{ErrorMessages.SEND_MESSAGE}: {error}")
			self._emit_event("error", error)

	def _cleanup_connection(self) -> None:
		"""清理连接资源"""
		# 设置关闭标志
		self._is_closing = True
		# 停止批量上传定时器
		with self._command_queue_lock:
			if self._upload_timer:
				self._upload_timer.cancel()
				self._upload_timer = None
			self._command_queue.clear()
		# 停止心跳定时器
		if self._heartbeat_timer:
			self._heartbeat_timer.cancel()
			self._heartbeat_timer = None
		# 停止 ping 线程
		self._stop_ping()
		# 关闭 WebSocket 连接
		if self.websocket_client:
			try:
				# 使用异步关闭避免阻塞
				def close_ws() -> None:
					self.websocket_client.close()  # pyright: ignore [reportOptionalMemberAccess]  # ty:ignore [possibly-missing-attribute]

				# 在新线程中关闭 WebSocket
				close_thread = Thread(target=close_ws, daemon=True)
				close_thread.start()
				close_thread.join(timeout=1.0)
			except Exception:  # noqa: S110
				pass
			finally:
				self.websocket_client = None
		# 等待 WebSocket 线程结束
		if self._websocket_thread and self._websocket_thread.is_alive():
			# 检查不是当前线程
			if self._websocket_thread != current_thread():
				self._websocket_thread.join(timeout=2.0)
			self._websocket_thread = None
		# 清除所有数据
		with self._variables_lock:
			self.private_variables.clear()
			self.public_variables.clear()
		with self._lists_lock:
			self.lists.clear()
		# 清除工作信息缓存
		self._work_info = None
		with self._connection_lock:
			self.connected = False
			self.data_ready = False
			self._join_sent = False
		with self._pending_requests_lock:
			self._pending_ranking_requests.clear()
		# 重置状态
		self.online_users = 0
		self._last_activity_time = 0.0
		self._last_ping_time = 0.0
		self._last_pong_time = 0.0
		self.reconnect_attempts = 0
		# 重置关闭标志
		self._is_closing = False
		# 清除事件回调, 保留 server_close
		for event_name in self._callbacks:
			if event_name != "server_close":
				self._callbacks[event_name].clear()

	def connect(self) -> None:
		"""建立云连接"""
		if self._is_closing:
			return
		try:
			self._cleanup_connection()
			with self._connection_lock:
				self.connected = False
				self.data_ready = False
				self._join_sent = False
				self._last_activity_time = 0.0
				self.private_variables.clear()
				self.public_variables.clear()
				self.lists.clear()
			url = self._get_websocket_url()
			headers = self._get_websocket_headers()
			print(f"正在连接到: {url}")
			self.websocket_client = WebSocketApp(
				url,
				header=headers,
				on_open=self._on_open,
				on_message=self._on_message,
				on_close=self._on_close,
				on_error=self._on_error,
			)

			def run_websocket() -> None:
				try:
					if self.websocket_client:
						self.websocket_client.run_forever(
							ping_interval=WebSocketConfig.PING_INTERVAL,
							ping_timeout=WebSocketConfig.PING_TIMEOUT,
							skip_utf8_validation=True,
						)
				except Exception as error:
					print(f"{ErrorMessages.WEB_SOCKET_RUN}: {error}")

			self._websocket_thread = Thread(target=run_websocket, daemon=True)
			self._websocket_thread.start()
		except Exception as error:
			print(f"{ErrorMessages.CONNECTION}: {error}")
			self._emit_event("error", error)

	def close(self) -> None:
		"""关闭云连接"""
		self._is_closing = True
		self.auto_reconnect = False
		with self._connection_lock:
			was_connected = self.connected
			self.connected = False
		if was_connected:
			print("正在关闭连接...")
		self._cleanup_connection()
		print("连接已关闭")

	def check_connection_health(self) -> bool:
		"""检查连接健康状态"""
		if not self.connected:
			return False
		if self._last_activity_time > 0:
			inactive_time = time() - self._last_activity_time
			if inactive_time > DataConfig.MAX_INACTIVITY_TIME:
				print(f"连接空闲超时: {inactive_time:.1f} 秒")
				return False
		return True

	def wait_for_connection(self, timeout: int = 30) -> bool:
		"""等待连接建立"""
		start_time = time()
		last_log_time = start_time
		while time() - start_time < timeout:
			if self.connected:
				print("✓ 连接已建立")
				return True
			current_time = time()
			if current_time - last_log_time >= 3:
				elapsed = current_time - start_time
				print(f"等待连接中... 已等待 {elapsed:.1f} 秒")
				last_log_time = current_time
			sleep(0.1)
		print(f"连接超时, 等待 {timeout} 秒后仍未建立连接")
		return False

	def wait_for_data(self, timeout: int = DataConfig.DATA_TIMEOUT) -> bool:
		"""等待数据加载完成"""
		start_time = time()
		last_log_time = start_time
		while time() - start_time < timeout:
			if self.data_ready:
				print("✓ 数据加载完成!")
				return True
			current_time = time()
			if current_time - last_log_time >= 5:
				elapsed = current_time - start_time
				print(f"等待数据中... 已等待 {elapsed:.1f} 秒, 连接状态: {self.connected}")
				last_log_time = current_time
			sleep(0.1)
		print(f"数据加载超时, 等待 {timeout} 秒后仍未收到数据")
		print(f"最终状态 - 连接: {self.connected}, 数据就绪: {self.data_ready}")
		return False

	def get_private_variable(self, name: str) -> PrivateCloudVariable | None:
		"""获取私有变量"""
		with self._variables_lock:
			if name in self.private_variables:
				return self.private_variables[name]
			try:
				if name.isdigit():
					return self.private_variables.get(name)
			except (AttributeError, ValueError):
				pass
			return None

	def get_public_variable(self, name: str) -> PublicCloudVariable | None:
		"""获取公有变量"""
		with self._variables_lock:
			if name in self.public_variables:
				return self.public_variables[name]
			try:
				if name.isdigit():
					return self.public_variables.get(name)
			except (AttributeError, ValueError):
				pass
			return None

	def get_list(self, name: str) -> CloudList | None:
		"""获取云列表"""
		with self._lists_lock:
			if name in self.lists:
				return self.lists[name]
			try:
				if name.isdigit():
					return self.lists.get(name)
			except (AttributeError, ValueError):
				pass
			return None

	def get_all_private_variables(self) -> dict[str, PrivateCloudVariable]:
		"""获取所有私有变量"""
		with self._variables_lock:
			return {k: v for k, v in self.private_variables.items() if not k.isdigit()}

	def get_all_public_variables(self) -> dict[str, PublicCloudVariable]:
		"""获取所有公有变量"""
		with self._variables_lock:
			return {k: v for k, v in self.public_variables.items() if not k.isdigit()}

	def get_all_lists(self) -> dict[str, CloudList]:
		"""获取所有云列表"""
		with self._lists_lock:
			return {k: v for k, v in self.lists.items() if not k.isdigit()}

	def set_private_variable(self, name: str, value: int | str) -> bool:
		"""设置私有变量值 - 支持批量上传"""
		variable = self.get_private_variable(name)
		if variable and variable.set(value):
			command_data = {"cvid": variable.cloud_variable_id, "value": value, "param_type": "number" if isinstance(value, int) else "string"}
			self._queue_variable_command("update_private_vars", command_data)
			return True
		return False

	def set_public_variable(self, name: str, value: int | str) -> bool:
		"""设置公有变量值 - 支持批量上传"""
		variable = self.get_public_variable(name)
		if variable and variable.set(value):
			command_data = {"action": "set", "cvid": variable.cloud_variable_id, "value": value, "param_type": "number" if isinstance(value, int) else "string"}
			self._queue_variable_command("update_vars", command_data)
			return True
		return False

	def list_push(self, name: str, value: int | str) -> bool:
		"""向列表末尾添加元素 - 支持批量上传"""
		cloud_list = self.get_list(name)
		if cloud_list and cloud_list.push(value):
			operations = [{"action": "append", "value": value}]
			self._queue_list_command(cloud_list.cloud_variable_id, operations)
			return True
		return False

	def get_private_variable_ranking(self, variable_name: str, limit: int = DataConfig.DEFAULT_RANKING_LIMIT, order: int = ValidationConfig.DESCENDING_ORDER) -> None:
		"""获取私有变量排行榜"""
		variable = self.get_private_variable(variable_name)
		if variable:
			variable.get_ranking_list(limit, order)
		else:
			print(f"未找到私有变量: {variable_name}")

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
				print(f"{name}: {value_display}")
		else:
			print("无公有变量")
		print("\n=== 私有变量 ===")
		private_vars = self.get_all_private_variables()
		if private_vars:
			for name, variable in private_vars.items():
				value_display = DisplayHelper.truncate_value(variable.get())
				print(f"{name}: {value_display}")
		else:
			print("无私有变量")
		print("\n=== 云列表 ===")
		lists = self.get_all_lists()
		if lists:
			for name, cloud_list in lists.items():
				value_display = DisplayHelper.truncate_value(cloud_list.value)
				print(f"{name}: {value_display} (长度: {cloud_list.length()})")
		else:
			print("无云列表")
		print(f"\n 在线用户数: {self.online_users}")
		print("=" * 50)
		# ==============================


# 高级接口 (API Layer)
# ==============================
class CloudAPI:
	"""高级 API 接口 - 提供简洁的云数据操作接口"""

	def __init__(self, work_id: int, editor: EditorType | None = None, authorization_token: str | None = None) -> None:
		self._connection = CloudConnection(work_id, editor, authorization_token)
		self._data_ready_callbacks: list[Callable[[], None]] = []
		self._online_users_callbacks: list[Callable[[int, int], None]] = []
		self._ranking_callbacks: list[Callable[[PrivateCloudVariable, list[dict[str, Any]]], None]] = []
		# 注册内部回调
		self._connection.on_data_ready(self._handle_data_ready)
		self._connection.on_online_users_change(self._handle_online_users_change)
		self._connection.on_ranking_received(self._handle_ranking_received)

	def _handle_data_ready(self) -> None:
		"""处理数据就绪事件"""
		for callback in self._data_ready_callbacks:
			try:
				callback()
			except Exception as error:
				print(f"{ErrorMessages.CALLBACK_EXECUTION}: {error}")

	def _handle_online_users_change(self, old_count: int, new_count: int) -> None:
		"""处理在线用户数变更事件"""
		for callback in self._online_users_callbacks:
			try:
				callback(old_count, new_count)
			except Exception as error:
				print(f"{ErrorMessages.CALLBACK_EXECUTION}: {error}")

	def _handle_ranking_received(self, variable: PrivateCloudVariable, ranking_data: list[dict[str, Any]]) -> None:
		"""处理排行榜数据接收事件"""
		for callback in self._ranking_callbacks:
			try:
				callback(variable, ranking_data)
			except Exception as error:
				print(f"{ErrorMessages.CALLBACK_EXECUTION}: {error}")

	# ========== 连接管理 ==========
	def connect(self, *, wait_for_data: bool = True, timeout: int = 30) -> bool:
		"""建立连接并等待数据
		Args:
			wait_for_data: 是否等待数据加载完成
			timeout: 超时时间 (秒)
		Returns:
			bool: 连接和数据加载是否成功
		"""
		try:
			self._connection.connect()
			# 等待连接建立
			if not self._connection.wait_for_connection(timeout):
				return False
			# 等待数据加载
			if wait_for_data:
				return self._connection.wait_for_data(timeout)
		except Exception as error:
			print(f"连接失败: {error}")
			return False
		else:
			return True

	def disconnect(self) -> None:
		"""断开连接"""
		self._connection.close()

	def is_connected(self) -> bool:
		"""检查是否已连接"""
		return self._connection.connected

	def is_data_ready(self) -> bool:
		"""检查数据是否就绪"""
		return self._connection.data_ready

	def get_online_users(self) -> int:
		"""获取在线用户数"""
		return self._connection.online_users

	# ========== 事件监听 ==========
	def on_data_ready(self, callback: Callable[[], None]) -> None:
		"""注册数据就绪回调"""
		self._data_ready_callbacks.append(callback)

	def on_online_users_change(self, callback: Callable[[int, int], None]) -> None:
		"""注册在线用户数变更回调"""
		self._online_users_callbacks.append(callback)

	def on_ranking_received(self, callback: Callable[[PrivateCloudVariable, list[dict[str, Any]]], None]) -> None:
		"""注册排行榜数据接收回调"""
		self._ranking_callbacks.append(callback)

	# ========== 变量操作 ==========
	def get_private_variable(self, name: str) -> PrivateCloudVariable | None:
		"""获取私有变量"""
		return self._connection.get_private_variable(name)

	def get_public_variable(self, name: str) -> PublicCloudVariable | None:
		"""获取公有变量"""
		return self._connection.get_public_variable(name)

	def get_list(self, name: str) -> CloudList | None:
		"""获取云列表"""
		return self._connection.get_list(name)

	def set_private_variable(self, name: str, value: int | str) -> bool:
		"""设置私有变量值"""
		return self._connection.set_private_variable(name, value)

	def set_public_variable(self, name: str, value: int | str) -> bool:
		"""设置公有变量值"""
		return self._connection.set_public_variable(name, value)

	# ========== 列表操作 ==========
	def list_push(self, name: str, value: int | str) -> bool:
		"""向列表末尾添加元素"""
		return self._connection.list_push(name, value)

	def list_pop(self, name: str) -> bool:
		"""移除列表最后一个元素"""
		return self._connection.list_pop(name)

	def list_unshift(self, name: str, value: int | str) -> bool:
		"""向列表开头添加元素"""
		return self._connection.list_unshift(name, value)

	def list_shift(self, name: str) -> bool:
		"""移除列表第一个元素"""
		return self._connection.list_shift(name)

	def list_insert(self, name: str, index: int, value: int | str) -> bool:
		"""在列表指定位置插入元素"""
		return self._connection.list_insert(name, index, value)

	def list_remove(self, name: str, index: int) -> bool:
		"""移除列表指定位置的元素"""
		return self._connection.list_remove(name, index)

	def list_replace(self, name: str, index: int, value: int | str) -> bool:
		"""替换列表指定位置的元素"""
		return self._connection.list_replace(name, index, value)

	def list_replace_last(self, name: str, value: int | str) -> bool:
		"""替换列表最后一个元素"""
		return self._connection.list_replace_last(name, value)

	def list_clear(self, name: str) -> bool:
		"""清空列表所有元素"""
		return self._connection.list_clear(name)

	# ========== 排行榜操作 ==========
	def get_ranking(self, variable_name: str, limit: int = 10, order: int = -1) -> None:
		"""获取私有变量排行榜"""
		self._connection.get_private_variable_ranking(variable_name, limit, order)

	# ========== 数据查询 ==========
	def get_all_variables(self) -> dict[str, dict[str, Any]]:
		"""获取所有变量信息"""
		return {"private_variables": self.get_all_private_variables(), "public_variables": self.get_all_public_variables(), "lists": self.get_all_lists()}

	def get_all_private_variables(self) -> dict[str, CloudValueType]:
		"""获取所有私有变量"""
		result = {}
		for name, var in self._connection.get_all_private_variables().items():
			result[name] = var.get()
		return result

	def get_all_public_variables(self) -> dict[str, CloudValueType]:
		"""获取所有公有变量"""
		result = {}
		for name, var in self._connection.get_all_public_variables().items():
			result[name] = var.get()
		return result

	def get_all_lists(self) -> dict[str, list[CloudValueType]]:
		"""获取所有云列表"""
		result = {}
		for name, lst in self._connection.get_all_lists().items():
			result[name] = lst.copy()
		return result

	def print_summary(self) -> None:
		"""打印数据摘要"""
		self._connection.print_all_data()


# ==============================
# 实用工具类
# ==============================
class CloudManager:
	"""云数据管理器 - 提供批量操作和同步方法"""

	def __init__(self, work_id: int, editor: EditorType | None = None, authorization_token: str | None = None) -> None:
		self.api = CloudAPI(work_id, editor, authorization_token)

	def connect_and_wait(self, timeout: int = 30) -> bool:
		"""连接并等待数据就绪"""
		return self.api.connect(wait_for_data=True, timeout=timeout)

	def batch_set_variables(self, variables: dict[str, int | str], variable_type: str = "private") -> dict[str, bool]:
		"""批量设置变量值
		Args:
			variables: {变量名: 值} 的字典
			variable_type: 变量类型 ("private" 或 "public")
		Returns:
			dict: 每个变量的设置结果
		"""
		results = {}
		if variable_type == "private":
			for name, value in variables.items():
				results[name] = self.api.set_private_variable(name, value)
		else:
			for name, value in variables.items():
				results[name] = self.api.set_public_variable(name, value)
		return results

	def batch_list_operations(self, operations: list[tuple]) -> list[bool]:
		"""批量执行列表操作
		Args:
			operations: 操作列表, 格式:
				- 简单操作: ("pop", "list_name") 或 ("shift", "list_name") 或 ("clear", "list_name")
				- 带一个参数的操作: ("push", "list_name", value) 或 ("unshift", "list_name", value) 或 ("replace_last", "list_name", value)
				- 带两个参数的操作: ("insert", "list_name", index, value) 或 ("replace", "list_name", index, value) 或 ("remove", "list_name", index)
		Returns:
			list: 每个操作的结果
		"""
		results = []
		for operation in operations:
			if not operation or len(operation) < 2:
				results.append(False)
				continue
			op_name = operation[0]
			list_name = operation[1]
			try:
				if op_name == "push" and len(operation) >= 3:
					results.append(self.api.list_push(list_name, operation[2]))
				elif op_name == "pop":
					results.append(self.api.list_pop(list_name))
				elif op_name == "unshift" and len(operation) >= 3:
					results.append(self.api.list_unshift(list_name, operation[2]))
				elif op_name == "shift":
					results.append(self.api.list_shift(list_name))
				elif op_name == "insert" and len(operation) >= 4:
					results.append(self.api.list_insert(list_name, operation[2], operation[3]))
				elif op_name == "remove" and len(operation) >= 3:
					results.append(self.api.list_remove(list_name, operation[2]))
				elif op_name == "replace" and len(operation) >= 4:
					results.append(self.api.list_replace(list_name, operation[2], operation[3]))
				elif op_name == "replace_last" and len(operation) >= 3:
					results.append(self.api.list_replace_last(list_name, operation[2]))
				elif op_name == "clear":
					results.append(self.api.list_clear(list_name))
				else:
					print(f"未知操作或参数不足: {op_name}")
					results.append(False)
			except Exception as error:
				print(f"操作 {op_name} 失败: {error}")
				results.append(False)
		return results

	def subscribe_to_variable(self, variable_name: str, callback: Callable[[CloudValueType, CloudValueType, str], None], variable_type: str = "private") -> bool:
		"""订阅变量变更
		Args:
			variable_name: 变量名
			callback: 变更回调函数
			variable_type: 变量类型 ("private" 或 "public")
		Returns:
			bool: 订阅是否成功
		"""
		var = self.api.get_private_variable(variable_name) if variable_type == "private" else self.api.get_public_variable(variable_name)
		if var:
			var.on_change(callback)
			return True
		return False

	def subscribe_to_list(self, list_name: str, operation: str, callback: ListOperationCallbackType) -> bool:
		"""订阅列表操作
		Args:
			list_name: 列表名
			operation: 操作类型 ("push", "pop" 等)
			callback: 操作回调函数
		Returns:
			bool: 订阅是否成功
		"""
		lst = self.api.get_list(list_name)
		if lst:
			lst.on_operation(operation, callback)
			return True
		return False


# ==============================
# 快速启动工具
# ==============================
def create_cloud_client(work_id: int, editor: EditorType | None = None, authorization_token: str | None = None) -> CloudAPI:
	"""快速创建云客户端
	Args:
		work_id: 作品 ID
		editor: 编辑器类型 (可选)
		authorization_token: 授权令牌 (可选)
	Returns:
		CloudAPI: 配置好的 API 实例
	"""
	return CloudAPI(work_id, editor, authorization_token)


def create_cloud_manager(work_id: int, editor: EditorType | None = None, authorization_token: str | None = None) -> CloudManager:
	"""快速创建云管理器
	Args:
		work_id: 作品 ID
		editor: 编辑器类型 (可选)
		authorization_token: 授权令牌 (可选)
	Returns:
		CloudManager: 配置好的管理器实例
	"""
	return CloudManager(work_id, editor, authorization_token)
