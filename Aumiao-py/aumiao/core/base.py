"""基础定义和核心 InfrastructureCoordinator 类"""

from collections import namedtuple
from collections.abc import Callable, Generator
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Literal, TypedDict, TypeVar

from aumiao.api import auth, community, edu, forum, library, shop, user, whale, work
from aumiao.api import auth as auth_ins
from aumiao.utils import data, decorator
from aumiao.utils import file as file_ins
from aumiao.utils import tool as tool_ins
from aumiao.utils.acquire import ClientFactory
from aumiao.utils.data import CacheManager, DataManager, HistoryManager, SettingManager
from aumiao.utils.decorator import singleton

# ==============================
# 类型变量定义
# ==============================
T = TypeVar("T")
ModuleType = TypeVar("ModuleType")
# ==============================
# 常量定义
# ==============================
# 数据大小限制
MAX_SIZE_BYTES: int = 15 * 1024 * 1024  # 15MB
REPORT_BATCH_THRESHOLD: int = 15
# 回复类型验证集
VALID_REPLY_TYPES: set[str] = {"WORK_COMMENT", "WORK_REPLY", "WORK_REPLY_REPLY", "POST_COMMENT", "POST_REPLY", "POST_REPLY_REPLY"}


class ReportRecord(TypedDict):
	"""举报记录类型"""

	item: "data.NestedDefaultDict"
	report_type: Literal["comment", "post", "discussion"]
	item_id: str
	content: str
	processed: bool
	action: str | None


# ==============================
# 配置类定义
# ==============================
@dataclass(frozen=True)
class HTTPConfig:
	"""HTTP 相关配置"""

	SUCCESS_CODE: int = 200
	CONNECTION_TIMEOUT: int = 30
	REQUEST_TIMEOUT: int = 10


@dataclass(frozen=True)
class WebSocketConfig:
	"""WebSocket 相关配置"""

	# ping 间隔: 60000ms, ping 超时: 180000ms
	PING_MESSAGE: str = "2"
	PONG_MESSAGE: str = "3"
	CONNECT_MESSAGE: str = "40"
	CONNECTED_MESSAGE: str = "40"
	EVENT_MESSAGE_PREFIX: str = "42"
	HANDSHAKE_MESSAGE_PREFIX: str = "0"
	TRANSPORT_TYPE: str = "websocket"
	PING_INTERVAL: int = 180
	PING_TIMEOUT: int = 60
	MESSAGE_TYPE_LENGTH: int = 2


@dataclass(frozen=True)
class DisplayConfig:
	"""显示相关配置"""

	MAX_DISPLAY_LENGTH: int = 50
	TRUNCATED_SUFFIX: str = "..."
	MAX_LIST_DISPLAY_ELEMENTS: int = 6
	PARTIAL_LIST_DISPLAY_COUNT: int = 3


@dataclass(frozen=True)
class DataConfig:
	"""数据相关配置"""

	DATA_TIMEOUT: int = 30
	DEFAULT_RANKING_LIMIT: int = 31
	MAX_INACTIVITY_TIME: int = 30
	MAX_RECONNECT_ATTEMPTS: int = 5
	PING_INTERVAL_MS: int = 25000
	PING_TIMEOUT_MS: int = 5000
	RECONNECT_INTERVAL: int = 8
	WAIT_TIMEOUT: int = 30


@dataclass(frozen=True)
class ValidationConfig:
	"""验证相关配置"""

	MIN_RANKING_LIMIT: int = 1
	MAX_RANKING_LIMIT: int = 31
	ASCENDING_ORDER: int = 1
	DESCENDING_ORDER: int = -1
	LIST_START_INDEX: int = 0
	FIRST_ELEMENT_INDEX: int = 0
	LAST_ELEMENT_INDEX: int = -1
	MIN_LIST_INDEX: int = 0
	MIN_LIST_OPERATION_ARGS: int = 2
	MIN_SET_ARGS: int = 2
	MIN_INSERT_ARGS: int = 2
	MIN_REMOVE_ARGS: int = 1
	MIN_REPLACE_ARGS: int = 2
	MIN_GET_ARGS: int = 1
	MIN_RANKING_ARGS: int = 1


@dataclass(frozen=True)
class ErrorMessages:
	"""错误消息常量"""

	CALLBACK_EXECUTION: str = "回调执行错误"
	CLOUD_VARIABLE_CALLBACK: str = "云变量变更回调执行错误"
	RANKING_CALLBACK: str = "排行榜回调执行错误"
	OPERATION_CALLBACK: str = "操作回调执行错误"
	EVENT_CALLBACK: str = "事件回调执行错误"
	SEND_MESSAGE: str = "发送消息错误"
	CONNECTION: str = "连接错误"
	WEB_SOCKET_RUN: str = "WebSocket 运行错误"
	CLOSE_CONNECTION: str = "关闭连接时出错"
	GET_SERVER_TIME: str = "获取服务器时间失败"
	HANDSHAKE_DATA_PARSE: str = "握手数据解析失败"
	HANDSHAKE_PROCESSING: str = "握手处理错误"
	JSON_PARSE: str = "JSON 解析错误"
	CLOUD_MESSAGE_PROCESSING: str = "云消息处理错误"
	CREATE_DATA_ITEM: str = "创建数据项时出错"
	INVALID_RANKING_DATA: str = "无效的排行榜数据格式"
	PING_SEND: str = "发送 ping 失败"
	NO_PENDING_REQUESTS: str = "收到排行榜数据但没有待处理的请求"
	INVALID_VARIABLE_TYPE: str = "云变量值必须是整数或字符串"
	INVALID_LIST_ITEM_TYPE: str = "列表元素必须是整数或字符串"
	INVALID_RANKING_ORDER: str = "排序顺序必须是 1 (正序) 或 - 1 (逆序)"
	INVALID_RANKING_LIMIT: str = "限制数量必须是正整数"


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


class ConnectionType(Enum):
	"""连接类型枚举"""

	PREVIOUS_STATEMENT = "previous_statement"
	NEXT_STATEMENT = "next_statement"
	INPUT_VALUE = "input_value"
	OUTPUT_VALUE = "output_value"


class ShadowType(Enum):
	"""影子积木类型枚举"""

	REGULAR = "regular"
	EMPTY = "empty"
	VALUE = "value"
	REPLACEABLE = "replaceable"
	STATEMENT = "statement"
	PARAMETER_SHADOW = "procedures_2_parameter_shadow"  # 新增:PROCEDURE 参数影子积木


class ShadowCategory(Enum):
	"""影子积木分类枚举"""

	DEFAULT_VALUE = "default_value"
	PLACEHOLDER = "placeholder"
	INPUT_TEMPLATE = "input_template"
	TOOLBOX_PREVIEW = "toolbox_preview"
	PARAMETER = "parameter"  # 新增: 参数影子积木


class ColorFormat(Enum):
	"""颜色格式枚举"""

	COLOR_PALETTE = auto()
	COLOR_STRING = auto()
	HSVA = auto()
	RGBA = auto()


class ControllerType(Enum):
	"""控制器类型枚举"""

	SLIDER = "SLIDER"
	COLOR_PICKER = "COLOR_PICKER"
	ANGLE_SCALE = "ANGLE_SCALE"


class BlockEventType(Enum):
	"""块事件类型枚举"""

	CREATE = "create"
	DELETE = "delete"
	CHANGE = "change"
	MOVE = "move"
	DRAG_AREA_CHANGE = "drag_area_change"
	END_DRAG = "end_drag"
	START_DRAG = "start_drag"


class NodeType(Enum):
	"""节点类型枚举"""

	ELEMENT_NODE = 1
	ATTRIBUTE_NODE = 2
	TEXT_NODE = 3


class FieldType(Enum):
	"""字段类型枚举"""

	TEXT = "text"
	NUMBER = "number"
	BOOLEAN = "boolean"
	DROPDOWN = "dropdown"
	COLOR = "color"
	VARIABLE = "variable"
	SPRITE = "sprite"
	STYLE = "style"
	AUDIO = "audio"
	LIST = "list"
	PROCEDURE = "procedure"
	BROADCAST = "broadcast"
	RANKING = "ranking"
	LAYER = "layer"
	ATTRIBUTE = "attribute"
	EFFECT = "effect"
	SCREEN = "screen"
	TRANSITION = "transition"
	KEY = "key"
	DIRECTION = "direction"
	COMPARISON = "comparison"
	OPERATOR = "operator"
	LOGIC = "logic"
	TRIG_FUNCTION = "trig_function"
	ROUNDING = "rounding"
	ARITHMETIC = "arithmetic"
	PEN_COLOR_PROPERTY = "pen_color_property"


class BlockCategory(Enum):
	"""块分类枚举"""

	EVENT = "event"
	CONTROL = "control"
	MOTION = "motion"
	APPEARANCE = "appearance"
	INTERACTION = "interaction"
	AUDIO = "audio"
	SENSING = "sensing"
	OPERATOR = "operator"
	VARIABLE = "variable"
	LIST = "list"
	PROCEDURE = "procedure"
	PEN = "pen"
	ANIMATION = "animation"
	CAMERA = "camera"
	COGNITIVE = "cognitive"
	AI_CHAT = "ai_chat"
	AI_CLASSIFY = "ai_classify"
	ONLINE = "online"
	JUDGE = "judge"
	MATH = "math"
	TEXT = "text"


class BlockType(Enum):
	"""所有块类型枚举"""

	# 事件类
	ON_RUNNING_GROUP_ACTIVATED = "on_running_group_activated"
	SPRITE_ON_TAP = "sprite_on_tap"
	ON_SWIPE = "on_swipe"
	ON_KEYDOWN = "on_keydown"
	ON_BUMP_ACTOR = "on_bump_actor"
	WHEN = "when"
	SELF_LISTEN = "self_listen"
	SELF_BROADCAST = "self_broadcast"
	SELF_BROADCAST_AND_WAIT = "self_broadcast_and_wait"
	RECEIVED_BROADCAST = "received_broadcast"
	SELF_LISTEN_WITH_PARAM = "self_listen_with_param"
	SELF_BROADCAST_WITH_PARAM = "self_broadcast_with_param"
	STOP = "stop"
	RESTART = "restart"
	SWITCH_TO_SCREEN = "switch_to_screen"
	SET_SCREEN_TRANSITION = "set_screen_transition"
	START_ON_CLICK = "start_on_click"
	GET_SCREENS = "get_screens"
	BROADCAST_INPUT = "broadcast_input"
	START_AS_A_MIRROR = "start_as_a_mirror"
	MIRROR = "mirror"
	DISPOSE_CLONE = "dispose_clone"
	GET_CURRENT_CLONE_INDEX = "get_current_clone_index"
	GET_CLONE_NUM = "get_clone_num"
	GET_CLONE_INDEX_PROPERTY = "get_clone_index_property"
	# 控制类
	REPEAT_FOREVER = "repeat_forever"
	REPEAT_N_TIMES = "repeat_n_times"
	TRAVERSE_NUMBER = "traverse_number"
	REPEAT_FOREVER_UNTIL = "repeat_forever_until"
	BREAK = "break"
	CONTROLS_IF = "controls_if"
	CONTROLS_IF_ELSE = "controls_if_else"
	WAIT = "wait"
	WAIT_UNTIL = "wait_until"
	CONSOLE_LOG = "console_log"
	WARP = "warp"
	TELL = "tell"
	SYNC_TELL = "sync_tell"
	# 动作 / 运动类
	SELF_GO_FORWARD = "self_go_forward"
	SELF_MOVE_SPECIFY = "self_move_specify"
	SELF_MOVE_TO = "self_move_to"
	SELF_SET_POSITION_X = "self_set_position_x"
	SELF_SET_POSITION_Y = "self_set_position_y"
	SELF_CHANGE_COORDINATE_X = "self_change_coordinate_x"
	SELF_CHANGE_COORDINATE_Y = "self_change_coordinate_y"
	SELF_GLIDE_TO = "self_glide_to"
	SELF_ROTATE = "self_rotate"
	SELF_ROTATE_AROUND = "self_rotate_around"
	SELF_POINT_TOWARDS = "self_point_towards"
	SELF_FACE_TO = "self_face_to"
	SELF_SET_DRAGGABLE = "self_set_draggable"
	SELF_SET_ROLE_CAMP = "self_set_role_camp"
	# 外观类
	SET_SPRITE_STYLE = "set_sprite_style"
	SELF_PREV_NEXT_STYLE = "self_prev_next_style"
	SELF_APPEAR = "self_appear"
	SELF_GRADUALLY_SHOW_HIDE = "self_gradually_show_hide"
	SET_SCALE = "set_scale"
	SELF_CHANGE_SCALE = "self_change_scale"
	SET_WIDTH_HEIGHT_SCALE = "set_width_height_scale"
	SELF_SET_EFFECT = "self_set_effect"
	SELF_CHANGE_EFFECT = "self_change_effect"
	CLEAR_ALL_EFFECTS = "clear_all_effects"
	SET_TOP_BOTTOM_LAYER = "set_top_bottom_layer"
	GET_STYLES = "get_styles"
	# 对话 / 界面类
	CREATE_STAGE_DIALOG = "create_stage_dialog"
	SELF_DIALOG_WAIT = "self_dialog_wait"
	SELF_DIALOG = "self_dialog"
	CLOSE_SELF_DIALOG = "close_self_dialog"
	SELF_ASK = "self_ask"
	GET_ANSWER = "get_answer"
	ASK_AND_CHOOSE = "ask_and_choose"
	TRANSLATE = "translate"
	TRANSLATE_RESULT = "translate_result"
	# 音频类
	PLAY_AUDIO = "play_audio"
	PLAY_AUDIO_AND_WAIT = "play_audio_and_wait"
	STOP_AUDIO = "stop_audio"
	SOUND_COLOR = "sound_color"
	VOICE_RECOGNITION = "voice_recognition"
	GET_VOICE_ANSWER = "get_voice_answer"
	GET_PLAY_AUDIO = "get_play_audio"
	# 检测类
	BUMP_INTO = "bump_into"
	BUMP_INTO_COLOR = "bump_into_color"
	OUT_OF_BOUNDARY = "out_of_boundary"
	COORDINATE_OF_SPRITE = "coordinate_of_sprite"
	STYLE_OF_SPRITE = "style_of_sprite"
	APPEARANCE_OF_SPRITE = "appearance_of_sprite"
	DISTANCE_TO = "distance_to"
	MOUSE_DOWN = "mouse_down"
	CHECK_KEY = "check_key"
	GET_MOUSE_INFO = "get_mouse_info"
	GET_ORIENTATION = "get_orientation"
	GET_TIME = "get_time"
	SET_TIMER_STATE = "set_timer_state"
	SHOW_HIDE_TIMER = "show_hide_timer"
	TIMER = "timer"
	# 运算类
	MATH_ARITHMETIC = "math_arithmetic"
	RANDOM_NUM = "random_num"
	LOGIC_COMPARE = "logic_compare"
	LOGIC_OPERATION = "logic_operation"
	LOGIC_NEGATE = "logic_negate"
	LOGIC_BOOLEAN = "logic_boolean"
	MATH_ROUND = "math_round"
	MATH_MODULO = "math_modulo"
	DIVISIBLE_BY = "divisible_by"
	TEXT_JOIN = "text_join"
	TEXT_SELECT = "text_select"
	TEXT_LENGTH = "text_length"
	TEXT_CONTAIN = "text_contain"
	CONVERT_TYPE = "convert_type"
	# 变量类
	VARIABLES_SET = "variables_set"
	CHANGE_VARIABLES = "change_variables"
	SHOW_HIDE_VARIABLES = "show_hide_variables"
	VARIABLES_GET = "variables_get"
	SCRIPT_VARIABLES = "script_variables"
	# 列表类
	LIST_APPEND = "list_append"
	LIST_INSERT_VALUE = "list_insert_value"
	DELETE_LIST_ITEM = "delete_list_item"
	REPLACE_LIST_ITEM = "replace_list_item"
	LIST_COPY = "list_copy"
	LIST_ITEM = "list_item"
	LIST_LENGTH = "list_length"
	LIST_INDEX_OF = "list_index_of"
	LIST_IS_EXIST = "list_is_exist"
	SHOW_HIDE_LIST = "show_hide_list"
	TEMPORARY_LIST = "temporary_list"
	# 画笔类
	SELF_PEN_DOWN = "self_pen_down"
	SELF_PEN_UP = "self_pen_up"
	CLEAR_DRAWING = "clear_drawing"
	SELF_SET_PEN_SIZE = "self_set_pen_size"
	SELF_CHANGE_PEN_SIZE = "self_change_pen_size"
	SELF_SET_PEN_COLOR = "self_set_pen_color"
	IMAGE_STAMP = "image_stamp"
	STAMP = "stamp"
	# 函数 / 过程类 - 根据文档更新
	PROCEDURES_DEFNORETURN = "procedures_2_defnoreturn"
	PROCEDURES_RETURN_VALUE = "procedures_2_return_value"
	PROCEDURES_CALLRETURN = "procedures_2_callreturn"
	PROCEDURES_CALLNORETURN = "procedures_2_callnoreturn"
	PROCEDURES_STABLE_PARAMETER = "procedures_2_stable_parameter"
	PROCEDURES_PARAMETER = "procedures_2_parameter"
	PROCEDURES_ACTOR_PARAM = "procedures_2_actor_param"
	PROCEDURES_PARAMETER_SHADOW = "procedures_2_parameter_shadow"  # 新增: 参数影子积木
	# 动画类
	SELF_STRESS_ANIMATION = "self_stress_animation"
	SELF_APPEAR_ANIMATION = "self_appear_animation"
	GLOBAL_ANIMATION = "global_animation"
	# 数值类
	MATH_NUMBER = "math_number"
	TEXT = "text"
	COLOR_SIZE_SLIDER = "color_size_slider"
	COLOR_PICKER = "color_picker"
	# 摄像头类
	OPEN_CLOSE_CAMERA = "open_hide_camera"
	SET_CAMERA_ALPHA = "set_camera_alpha"
	RECOGNIZE_BODY_PART = "recognize_body_part"
	BUMP_INTO_BODY_PART = "bump_into_body_part"
	MOVE_TO_BODY_PART = "move_to_body_part"
	FACE_TO_BODY_PART = "face_to_body_part"
	GET_POSITION_OF_BODY_PART = "get_position_of_body_part"
	RECOGNIZE_GESTURE = "recognize_gesture"
	# 认知 AI 类
	ENABLE_FACE_DETECT_BY_ACTOR = "enable_face_detect_by_actor"
	ENABLE_OBJECT_DETECT_BY_ACTOR = "enable_object_detect_by_actor"
	GET_FACE_DETECTION_RESULT = "get_face_detection_result"
	CHECK_EMOTION = "check_emotion"
	CHECK_GENDER = "check_gender"
	# AI 对话类
	AI_CHAT_ASK = "ai_chat_ask"
	AI_CHAT_ANSWER = "ai_chat_answer"
	SET_SYSTEM_PRESET = "set_system_preset"
	NEW_CONVERSATION = "new_conversation"
	# 分类 AI 类
	EVALUATE_ACTOR_STYLE = "evaluate_actor_style"
	EVALUATE_PHOTO = "evaluate_photo"
	EVALUATE_CAMERA = "evaluate_camera"
	GET_EVALUATE_CLASS_NAME = "get_evaluate_class_name"
	# 在线 / 排名类
	SHOW_HIDE_RANKING = "show_hide_ranking"
	UPDATE_RANKING = "update_ranking"
	USER_RANKING_INFO = "user_ranking_info"
	USERNAME_GET = "username_get"
	USER_ID_GET = "user_id_get"
	# 判题类
	SEND_JUDGE_RESULT = "send_judge_result"
	# 其他
	ON_BUMP_ACTOR_PARAM = "on_bump_actor_param"
	SELF_LISTEN_PARAM = "self_listen_param"
	TRAVERSE_NUMBER_PARAM = "traverse_number_param"
	MATH_NUMBER_WITH_SLIDER = "math_number_with_slider"
	MATH_COMPARE_NEQ = "math_compare_neq"
	MATH_COMPARE_GREATER = "math_compare_more"
	MATH_COMPARE_LESS = "math_compare_less"
	MATH_ARITHMETIC_POWER = "math_arithmetic_power"
	SHADOW_TEXT = "shadow_text"


# 块配置映射 - 更详细的配置
BLOCK_CONFIG: dict[BlockType, dict[str, Any]] = {
	# 事件类配置
	BlockType.ON_RUNNING_GROUP_ACTIVATED: {
		"category": BlockCategory.EVENT,
		"fields": [],
		"inputs": [],
		"output": False,
		"color": "#FFAB19",
		"can_have_previous": False,
		"can_have_next": True,
	},
	BlockType.SPRITE_ON_TAP: {
		"category": BlockCategory.EVENT,
		"fields": [],
		"inputs": [],
		"output": False,
		"color": "#FFAB19",
		"can_have_previous": False,
		"can_have_next": True,
	},
	# 控制类配置
	BlockType.REPEAT_FOREVER: {
		"category": BlockCategory.CONTROL,
		"fields": [],
		"inputs": ["STATEMENT"],
		"output": False,
		"color": "#FF8C1A",
		"can_have_previous": True,
		"can_have_next": True,
	},
	BlockType.WAIT: {
		"category": BlockCategory.CONTROL,
		"fields": [],
		"inputs": ["SECONDS"],
		"output": False,
		"color": "#FF8C1A",
		"can_have_previous": True,
		"can_have_next": True,
	},
	BlockType.CONTROLS_IF_ELSE: {
		"category": BlockCategory.CONTROL,
		"fields": [],
		"inputs": ["IF0", "DO0", "ELSE"],
		"output": False,
		"color": "#FF8C1A",
		"can_have_previous": True,
		"can_have_next": True,
	},
	# 运动类配置
	BlockType.SELF_MOVE_TO: {
		"category": BlockCategory.MOTION,
		"fields": [],
		"inputs": ["X", "Y"],
		"output": False,
		"color": "#4C97FF",
		"can_have_previous": True,
		"can_have_next": True,
	},
	# 外观类配置
	BlockType.SELF_DIALOG: {
		"category": BlockCategory.INTERACTION,
		"fields": [],
		"inputs": ["TEXT"],
		"output": False,
		"color": "#9966FF",
		"can_have_previous": True,
		"can_have_next": True,
	},
	# 数学类配置
	BlockType.MATH_NUMBER: {
		"category": BlockCategory.MATH,
		"fields": ["NUM"],
		"inputs": [],
		"output": True,
		"color": "#40BF4A",
		"can_have_previous": False,
		"can_have_next": False,
		"field_constraints": {
			"NUM": "*,*,*,true",  # 允许文本输入
		},
	},
	# 文本类配置
	BlockType.TEXT: {
		"category": BlockCategory.TEXT,
		"fields": ["TEXT"],
		"inputs": [],
		"output": True,
		"color": "#CF63CF",
		"can_have_previous": False,
		"can_have_next": False,
	},
	# 逻辑类配置
	BlockType.LOGIC_COMPARE: {
		"category": BlockCategory.OPERATOR,
		"fields": ["OP"],
		"inputs": ["A", "B"],
		"output": True,
		"color": "#40BF4A",
		"can_have_previous": False,
		"can_have_next": False,
	},
	# 过程类配置 - 根据文档更新
	BlockType.PROCEDURES_DEFNORETURN: {
		"category": BlockCategory.PROCEDURE,
		"fields": ["NAME"],
		"inputs": ["PROCEDURES_2_DEFNORETURN_DEFINE", "STACK"],
		"output": False,
		"color": "#FF6680",  # ORANGE_4
		"can_have_previous": True,
		"can_have_next": True,
		"style": "ORANGE_4",
		"extensions": ["procedures_defnoreturn"],
	},
	BlockType.PROCEDURES_RETURN_VALUE: {
		"category": BlockCategory.PROCEDURE,
		"fields": [],
		"inputs": ["PROCEDURES_2_DEFRETURN_RETURN", "VALUE"],
		"output": True,
		"color": "#FF6680",  # ORANGE_4
		"can_have_previous": False,
		"can_have_next": False,
		"style": "ORANGE_4",
	},
	BlockType.PROCEDURES_CALLNORETURN: {
		"category": BlockCategory.PROCEDURE,
		"fields": ["NAME"],
		"inputs": ["NAME"],  # 动态生成 ARG 输入项
		"output": False,
		"color": "#FF6680",  # ORANGE_4
		"can_have_previous": True,
		"can_have_next": True,
	},
	BlockType.PROCEDURES_CALLRETURN: {
		"category": BlockCategory.PROCEDURE,
		"fields": ["NAME"],
		"inputs": ["NAME"],  # 动态生成 ARG 输入项
		"output": True,
		"color": "#FF6680",  # ORANGE_4
		"can_have_previous": False,
		"can_have_next": False,
		"output_types": ["Number", "String", "Boolean", "Array"],
	},
	BlockType.PROCEDURES_STABLE_PARAMETER: {
		"category": BlockCategory.PROCEDURE,
		"fields": ["param_name", "param_default_value"],
		"inputs": [],
		"output": True,
		"color": "#FF6680",
		"can_have_previous": False,
		"can_have_next": False,
		"output_types": ["Number", "String", "Boolean"],
		"extensions": ["param_on_block"],
	},
	BlockType.PROCEDURES_PARAMETER: {
		"category": BlockCategory.PROCEDURE,
		"fields": ["param_name"],
		"inputs": [],
		"output": True,
		"color": "#FF6680",
		"can_have_previous": False,
		"can_have_next": False,
		"output_types": ["Number", "String", "Boolean"],
	},
	BlockType.PROCEDURES_PARAMETER_SHADOW: {
		"category": BlockCategory.PROCEDURE,
		"fields": ["name", "value"],
		"inputs": [],
		"output": True,
		"color": "#FF6680",
		"can_have_previous": False,
		"can_have_next": False,
		"is_shadow": True,
		"deletable": False,
	},
	# 逻辑布尔类
	BlockType.LOGIC_BOOLEAN: {
		"category": BlockCategory.OPERATOR,
		"fields": ["VALUE"],
		"inputs": [],
		"output": True,
		"color": "#40BF4A",
		"can_have_previous": False,
		"can_have_next": False,
		"options": {"VALUE": {"menu_generator_advanced": [["true", "true"], ["false", "false"]]}},
	},
}
# 颜色配置
COLOR_CONFIG: dict[BlockCategory, str] = {
	BlockCategory.EVENT: "#FFAB19",
	BlockCategory.CONTROL: "#FF8C1A",
	BlockCategory.MOTION: "#4C97FF",
	BlockCategory.APPEARANCE: "#9966FF",
	BlockCategory.INTERACTION: "#5CB1D6",
	BlockCategory.AUDIO: "#D65CD6",
	BlockCategory.SENSING: "#5CB1D6",
	BlockCategory.OPERATOR: "#40BF4A",
	BlockCategory.VARIABLE: "#FF8C1A",
	BlockCategory.LIST: "#FF6680",
	BlockCategory.PROCEDURE: "#FF6680",
	BlockCategory.PEN: "#009900",
	BlockCategory.ANIMATION: "#9966FF",
	BlockCategory.CAMERA: "#4C97FF",
	BlockCategory.COGNITIVE: "#FF6680",
	BlockCategory.AI_CHAT: "#40BF4A",
	BlockCategory.AI_CLASSIFY: "#CF63CF",
	BlockCategory.ONLINE: "#FFAB19",
	BlockCategory.JUDGE: "#FF8C1A",
	BlockCategory.MATH: "#40BF4A",
	BlockCategory.TEXT: "#CF63CF",
}
# 字段类型到值的映射
FIELD_TYPE_MAPPING: dict[FieldType, dict[str, Any]] = {
	FieldType.TEXT: {
		"default": "",
		"validator": lambda x: isinstance(x, str),
	},
	FieldType.NUMBER: {
		"default": 0,
		"validator": lambda x: isinstance(x, (int, float)),
	},
	FieldType.BOOLEAN: {
		"default": False,
		"validator": lambda x: isinstance(x, bool),
	},
	FieldType.COLOR: {
		"default": "#000000",
		"validator": lambda x: isinstance(x, str) and (x.startswith(("#", "rgb"))),
	},
}
# 块连接约束
CONNECTION_CONSTRAINTS: dict = {
	"output": ["input_value"],
	"previous_statement": ["next_statement"],
	"next_statement": ["previous_statement"],
	"input_value": ["output"],
}
# 默认项目配置
DEFAULT_PROJECT_CONFIG: dict = {
	"version": "0.20.0",
	"tool_type": "KN",
	"stage_size": {"width": 900.0, "height": 562.0},
	"timer_position": {"x": 720.0, "y": 12.0},
	"workspace_scroll_xy": {"x": 0.0, "y": 0.0},
	"background_color": "#FFFFFF",
}
# ==============================
# 数据结构定义
# ==============================
BatchGroup = namedtuple("BatchGroup", ["group_type", "group_key", "record_ids"])  # noqa: PYI024


@dataclass
class ActionConfig:
	"""操作配置 - 定义每个操作的行为"""

	key: str
	name: str
	description: str
	status: str  # 对应的状态值
	enabled: bool = True  # 是否启用该操作


@dataclass
class SourceConfigSimple:
	"""简化版数据源配置"""

	get_items: Callable[..., Any]
	get_comments: Callable[..., Any]
	delete: Callable[..., Any]
	title_key: str


@dataclass
class SourceConfig:
	"""举报源配置 - 定义每种举报类型的处理方法"""

	name: str
	# 数据获取方法
	fetch_total: Callable[..., dict]
	fetch_generator: Callable[..., Generator[dict]]
	# 处理动作方法
	handle_method: str
	# 字段映射
	content_field: str
	user_field: str
	source_id_field: str
	item_id_field: str
	source_name_field: str | None = None
	# 特殊检查
	special_check: Callable[..., bool] = field(default_factory=lambda: lambda: True)
	# 分块大小
	chunk_size: int = 100
	available_actions: list["ActionConfig"] | None = None

	def __post_init__(self) -> None:
		"""初始化后处理"""
		if self.available_actions is None:
			self.available_actions = []


# ==============================
# 模块管理器:类型友好版本
# ==============================
class ModuleManager:
	"""管理所有模块的延迟加载和缓存"""

	def __init__(self) -> None:
		self._modules: dict[str, Any] = {}
		self._module_creators: dict[str, Callable[[], Any]] = {}

	def register(self, name: str, creator: Callable[[], Any]) -> None:
		"""注册模块创建器"""
		self._module_creators[name] = creator

	def get(self, name: str) -> Any:
		"""获取模块实例(延迟加载)"""
		if name not in self._modules:
			if name not in self._module_creators:
				msg = f"模块 '{name}' 未注册"
				raise AttributeError(msg)
			self._modules[name] = self._module_creators[name]()
		return self._modules[name]

	def clear_cache(self, name: str | None = None) -> None:
		"""清除模块缓存"""
		if name:
			self._modules.pop(name, None)
		else:
			self._modules.clear()

	def list_available(self) -> list[str]:
		"""列出所有可用的模块"""
		return list(self._module_creators.keys())

	def list_loaded(self) -> list[str]:
		"""列出已加载的模块"""
		return list(self._modules.keys())


# ==============================
# 核心组件管理器
# ==============================
class CoreManager:
	"""管理立即加载的核心组件"""

	def __init__(self) -> None:
		# 立即初始化的核心组件
		self.client = ClientFactory().create_codemao_client()
		self.tool = tool_ins
		self.data_manager = DataManager()
		self.setting_manager = SettingManager()
		self.cache_manager = CacheManager()
		self.history_manager = HistoryManager()

	@property
	def data(self) -> ...:
		"""快捷访问数据"""
		return self.data_manager.data

	@property
	def setting(self) -> ...:
		"""快捷访问设置"""
		return self.setting_manager.data

	@property
	def cache(self) -> ...:
		"""快捷访问缓存"""
		return self.cache_manager.data

	@property
	def upload_history(self) -> ...:
		"""快捷访问历史记录"""
		return self.history_manager


# ==============================
# 基础设施协调器:类型友好主类
# ==============================
class InfrastructureCoordinator:
	"""
	基础设施协调器 - 类型友好版本
	使用明确的属性定义,确保类型检查器能识别所有属性
	"""

	def __init__(self) -> None:
		# 组合核心组件管理器
		self._core = CoreManager()
		# 组合模块管理器
		self._modules = ModuleManager()
		# 初始化模块注册表
		self._initialize_module_registry()

	def _initialize_module_registry(self) -> None:
		"""初始化模块注册表"""
		# API 模块

		api_modules = {
			"auth": auth.AuthManager,
			"community_motion": community.UserAction,
			"community_obtain": community.DataFetcher,
			"edu_motion": edu.UserAction,
			"edu_obtain": edu.DataFetcher,
			"forum_motion": forum.ForumActionHandler,
			"forum_obtain": forum.ForumDataFetcher,
			"novel_motion": library.NovelActionHandler,
			"novel_obtain": library.NovelDataFetcher,
			"shop_motion": shop.WorkshopActionHandler,
			"shop_obtain": shop.WorkshopDataFetcher,
			"user_motion": user.UserManager,
			"user_obtain": user.UserDataFetcher,
			"work_motion": work.BaseWorkManager,
			"work_obtain": work.WorkDataFetcher,
			"whale_motion": whale.ReportHandler,
			"whale_obtain": whale.ReportFetcher,
			# 工具模块
			"printer": tool_ins.Printer,
			"file": file_ins.CodeMaoFile,
		}
		for name, creator in api_modules.items():
			self._modules.register(name, creator)

	# ==============================
	# 公共接口
	# ==============================
	def register_module(self, name: str, creator: Callable[[], Any]) -> None:
		"""注册新模块"""
		self._modules.register(name, creator)

	def clear_module_cache(self, module_name: str | None = None) -> None:
		"""清除模块缓存"""
		self._modules.clear_cache(module_name)

	def list_available_modules(self) -> list[str]:
		"""列出所有可用模块"""
		return self._modules.list_available()

	def list_loaded_modules(self) -> list[str]:
		"""列出已加载的模块"""
		return self._modules.list_loaded()

	# ==============================
	# 核心组件属性(类型明确)
	# ==============================
	@property
	def client(self) -> Any:
		"""核心客户端"""
		return self._core.client

	@property
	def tool(self) -> Any:
		"""工具模块"""
		return self._core.tool

	@property
	def data(self) -> Any:
		"""数据"""
		return self._core.data

	@property
	def setting(self) -> Any:
		"""设置"""
		return self._core.setting

	@property
	def cache(self) -> Any:
		"""缓存"""
		return self._core.cache

	@property
	def upload_history(self) -> Any:
		"""上传历史"""
		return self._core.upload_history

	# ==============================
	# API 模块属性(延迟加载,类型明确)
	# ==============================
	@property
	def auth(self) -> "auth_ins.AuthManager":
		"""认证管理模块"""
		return self._modules.get("auth")

	@property
	def community_motion(self) -> "community.UserAction":
		"""社区动作模块"""
		return self._modules.get("community_motion")

	@property
	def community_obtain(self) -> "community.DataFetcher":
		"""社区数据获取模块"""
		return self._modules.get("community_obtain")

	@property
	def edu_motion(self) -> "edu.UserAction":
		"""教育动作模块"""
		return self._modules.get("edu_motion")

	@property
	def edu_obtain(self) -> "edu.DataFetcher":
		"""教育数据获取模块"""
		return self._modules.get("edu_obtain")

	@property
	def forum_motion(self) -> "forum.ForumActionHandler":
		"""论坛动作模块"""
		return self._modules.get("forum_motion")

	@property
	def forum_obtain(self) -> "forum.ForumDataFetcher":
		"""论坛数据获取模块"""
		return self._modules.get("forum_obtain")

	@property
	def novel_motion(self) -> "library.NovelActionHandler":
		"""小说动作模块"""
		return self._modules.get("novel_motion")

	@property
	def novel_obtain(self) -> "library.NovelDataFetcher":
		"""小说数据获取模块"""
		return self._modules.get("novel_obtain")

	@property
	def shop_motion(self) -> "shop.WorkshopActionHandler":
		"""商店动作模块"""
		return self._modules.get("shop_motion")

	@property
	def shop_obtain(self) -> "shop.WorkshopDataFetcher":
		"""商店数据获取模块"""
		return self._modules.get("shop_obtain")

	@property
	def user_motion(self) -> "user.UserManager":
		"""用户动作模块"""
		return self._modules.get("user_motion")

	@property
	def user_obtain(self) -> "user.UserDataFetcher":
		"""用户数据获取模块"""
		return self._modules.get("user_obtain")

	@property
	def work_motion(self) -> "work.BaseWorkManager":
		"""作品动作模块"""
		return self._modules.get("work_motion")

	@property
	def work_obtain(self) -> "work.WorkDataFetcher":
		"""作品数据获取模块"""
		return self._modules.get("work_obtain")

	@property
	def whale_motion(self) -> "whale.ReportHandler":
		"""鲸鱼报告动作模块"""
		return self._modules.get("whale_motion")

	@property
	def whale_obtain(self) -> "whale.ReportFetcher":
		"""鲸鱼报告数据获取模块"""
		return self._modules.get("whale_obtain")

	# ==============================
	# 工具模块属性(延迟加载,类型明确)
	# ==============================
	@property
	def printer(self) -> "tool_ins.Printer":
		"""打印工具模块"""
		return self._modules.get("printer")

	@property
	def file(self) -> "file_ins.CodeMaoFile":
		"""文件操作模块"""
		return self._modules.get("file")

	# ==============================
	# 动态模块访问(可选,用于访问动态注册的模块)
	# ==============================
	def get_module(self, name: str) -> Any:
		"""
		动态获取模块(用于访问动态注册的模块)
		这是类型安全的,因为调用者知道返回类型
		"""
		return self._modules.get(name)


# ==============================
# 类型存根(可选,用于 IDE 类型提示)
# ==============================
class _InfrastructureCoordinatorStub:
	"""
	类型存根类,用于 IDE 类型提示
	这不是实际代码,只是为类型检查器提供信息
	"""

	# 核心组件
	client: Any
	tool: Any
	data: Any
	setting: Any
	cache: Any
	upload_history: Any
	# API 模块
	auth: "auth.AuthManager"
	community_motion: "community.UserAction"
	community_obtain: "community.DataFetcher"
	edu_motion: "edu.UserAction"
	edu_obtain: "edu.DataFetcher"
	forum_motion: "forum.ForumActionHandler"
	forum_obtain: "forum.ForumDataFetcher"
	novel_motion: "library.NovelActionHandler"
	novel_obtain: "library.NovelDataFetcher"
	shop_motion: "shop.WorkshopActionHandler"
	shop_obtain: "shop.WorkshopDataFetcher"
	user_motion: "user.UserManager"
	user_obtain: "user.UserDataFetcher"
	work_motion: "work.BaseWorkManager"
	work_obtain: "work.WorkDataFetcher"
	whale_motion: "whale.ReportHandler"
	whale_obtain: "whale.ReportFetcher"
	# 工具模块
	printer: "tool_ins.Printer"
	file: "file_ins.CodeMaoFile"


# ==============================
# 单例包装:保持向后兼容
# ==============================
@singleton
class Union(InfrastructureCoordinator):
	"""
	保持原有 Union 类名,继承基础设施协调器
	提供全局单例访问
	"""


# ==============================
# 业务逻辑类(保持原样)
# ==============================
ClassUnion = Union().__class__
# ==============================
# 类型别名(用于类型注解)
# ==============================
InfraCoordinator = Union
"""基础设施协调器的类型别名"""


@decorator.singleton
class Index(ClassUnion):  # ty:ignore [unsupported-base]
	"""首页展示类"""

	# 颜色配置
	COLOR_DATA = "\033[38;5;228m"
	COLOR_LINK = "\033[4;38;5;183m"
	COLOR_RESET = "\033[0m"
	COLOR_SLOGAN = "\033[38;5;80m"
	COLOR_TITLE = "\033[38;5;75m"
	COLOR_VERSION = "\033[38;5;114m"

	def _print_title(self, title: str) -> None:
		"""打印标题"""
		print(f"\n {self.COLOR_TITLE}{'*' * 22} {title} {'*' * 22}{self.COLOR_RESET}")

	def _print_slogan(self) -> None:
		"""打印标语"""
		print(f"\n {self.COLOR_SLOGAN}{self.setting.PROGRAM.SLOGAN}{self.COLOR_RESET}")
		print(f"{self.COLOR_VERSION} 版本号: {self.setting.PROGRAM.VERSION}{self.COLOR_RESET}")

	def _print_lyric(self) -> None:
		"""打印歌词"""
		self._print_title("一言")
		lyric: str = self.client.send_request(endpoint="https://lty.vc/lyric", method="GET").text
		print(f"{self.COLOR_SLOGAN}{lyric}{self.COLOR_RESET}")

	def _print_announcements(self) -> None:
		"""打印公告"""
		self._print_title("公告")
		print(f"{self.COLOR_LINK} 编程猫社区行为守则 https://shequ.codemao.cn/community/1619098{self.COLOR_RESET}")
		print(f"{self.COLOR_LINK} 2025 编程猫拜年祭活动 https://shequ.codemao.cn/community/1619855{self.COLOR_RESET}")

	def _print_user_data(self) -> None:
		"""打印用户数据"""
		self._print_title("数据")
		if self.data.ACCOUNT_DATA.id:
			Tool().message_report(user_id=self.data.ACCOUNT_DATA.id)
			print(f"{self.COLOR_TITLE}{'*' * 50}{self.COLOR_RESET}\n")

	def index(self) -> None:
		"""显示首页"""
		self._print_slogan()
		# self._print_lyric()  # 暂时注释掉歌词显示
		self._print_announcements()
		self._print_user_data()


@decorator.singleton
class Tool(ClassUnion):  # ty:ignore [unsupported-base]
	"""工具类"""

	def __init__(self) -> None:
		super().__init__()
		self._cache_manager = data.CacheManager()

	def message_report(self, user_id: str) -> None:
		"""生成用户数据报告"""
		response = self.user_obtain.fetch_user_honors(user_id=user_id)
		timestamp = self.community_obtain.fetch_current_timestamp_10()["data"]
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
		# 如果有缓存数据, 进行对比分析
		if self._cache_manager.data:
			self.tool.DataAnalyzer().compare_datasets(
				before=self._cache_manager.data,
				after=user_data,
				metrics={
					"fans": "粉丝",
					"collected": "被收藏",
					"liked": "被赞",
					"view": "被预览",
				},
				timestamp_field="timestamp",
			)
		# 更新缓存
		self._cache_manager.update(user_data)
