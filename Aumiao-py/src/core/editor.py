"""
KN项目编辑器 - 完整增强版
包含:块验证、代码生成、批量操作、错误恢复、性能优化功能
"""

import copy
import json
import uuid
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional


# ============================================================================
# 枚举定义(保持不变)
# ============================================================================
class BlockType(Enum):
	"""所有块类型的枚举 - 完整列表"""

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
	# 动作/运动类
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
	# 对话/界面类
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
	# 函数/过程类
	PROCEDURES_CALLNORETURN = "procedures_2_callnoreturn"
	PROCEDURES_CALLRETURN = "procedures_2_callreturn"
	# 动画类
	SELF_STRESS_ANIMATION = "self_stress_animation"
	SELF_APPEAR_ANIMATION = "self_appear_animation"
	GLOBAL_ANIMATION = "global_animation"
	# 数值类
	MATH_NUMBER = "math_number"
	TEXT = "text"
	COLOR_SIZE_SLIDER = "color_size_slider"
	# 摄像头类
	OPEN_CLOSE_CAMERA = "open_hide_camera"
	SET_CAMERA_ALPHA = "set_camera_alpha"
	RECOGNIZE_BODY_PART = "recognize_body_part"
	BUMP_INTO_BODY_PART = "bump_into_body_part"
	MOVE_TO_BODY_PART = "move_to_body_part"
	FACE_TO_BODY_PART = "face_to_body_part"
	GET_POSITION_OF_BODY_PART = "get_position_of_body_part"
	RECOGNIZE_GESTURE = "recognize_gesture"
	# 认知AI类
	ENABLE_FACE_DETECT_BY_ACTOR = "enable_face_detect_by_actor"
	ENABLE_OBJECT_DETECT_BY_ACTOR = "enable_object_detect_by_actor"
	GET_FACE_DETECTION_RESULT = "get_face_detection_result"
	CHECK_EMOTION = "check_emotion"
	CHECK_GENDER = "check_gender"
	# AI对话类
	AI_CHAT_ASK = "ai_chat_ask"
	AI_CHAT_ANSWER = "ai_chat_answer"
	SET_SYSTEM_PRESET = "set_system_preset"
	NEW_CONVERSATION = "new_conversation"
	# 分类AI类
	EVALUATE_ACTOR_STYLE = "evaluate_actor_style"
	EVALUATE_PHOTO = "evaluate_photo"
	EVALUATE_CAMERA = "evaluate_camera"
	GET_EVALUATE_CLASS_NAME = "get_evaluate_class_name"
	# 在线/排名类
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
	PROCEDURES_ACTOR_PARAM = "procedures_2_actor_param"
	MATH_NUMBER_WITH_SLIDER = "math_number_with_slider"
	MATH_COMPARE_NEQ = "math_compare_neq"
	MATH_COMPARE_GREATER = "math_compare_more"
	MATH_COMPARE_LESS = "math_compare_less"
	MATH_ARITHMETIC_POWER = "math_arithmetic_power"
	SHADOW_TEXT = "shadow_text"


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


# ============================================================================
# 数据类定义(保持不变)
# ============================================================================
@dataclass
class BlockDefinition:
	"""块类型定义"""

	type: str
	name: str
	category: str
	color: str
	icon: str | None = None
	fields: dict[str, FieldType] = field(default_factory=dict)
	inputs: dict[str, str | list[str]] = field(default_factory=dict)
	statements: list[str] = field(default_factory=list)
	has_shadow: bool = False
	can_have_next: bool = False
	is_output: bool = False
	description: str = ""
	default_fields: dict[str, Any] = field(default_factory=dict)
	default_inputs: dict[str, Any] = field(default_factory=dict)
	required_fields: list[str] = field(default_factory=list)
	required_inputs: list[str] = field(default_factory=list)

	def __post_init__(self) -> None:
		if not self.name:
			self.name = self.type.replace("_", " ").title()


@dataclass
class Block:
	"""代码块实例"""

	id: str = field(default_factory=lambda: str(uuid.uuid4()))
	type: str = ""
	fields: dict[str, Any] = field(default_factory=dict)
	shadows: dict[str, Any] = field(default_factory=dict)
	inputs: dict[str, Optional["Block"]] = field(default_factory=dict)
	statements: dict[str, list["Block"]] = field(default_factory=dict)
	next: Optional["Block"] = None
	location: list[float] | None = None
	shield: bool = False
	comment: str | None = None
	collapsed: bool = False
	disabled: bool = False
	deletable: bool = True
	movable: bool = True
	editable: bool = True
	visible: str = "visible"
	is_shadow: bool = False
	parent_id: str | None = None
	mutation: str = ""
	is_output: bool = False

	def to_dict(self) -> dict[str, Any]:
		result: dict[str, Any] = {
			"type": self.type,
			"id": self.id,
			"fields": self.fields.copy(),
			"shield": self.shield,
			"collapsed": self.collapsed,
			"disabled": self.disabled,
			"deletable": self.deletable,
			"movable": self.movable,
			"editable": self.editable,
			"visible": self.visible,
			"is_shadow": self.is_shadow,
			"is_output": self.is_output,
		}
		if self.mutation:
			result["mutation"] = self.mutation
		if self.shadows:
			result["shadows"] = self.shadows
		if self.location:
			result["location"] = self.location
		if self.comment:
			result["comment"] = self.comment
		if self.parent_id:
			result["parent_id"] = self.parent_id
		# 递归处理输入
		if self.inputs:
			result["inputs"] = {}
			for key, block in self.inputs.items():
				if block:
					result["inputs"][key] = block.to_dict()
		# 递归处理语句
		if self.statements:
			result["statements"] = {}
			for key, blocks in self.statements.items():
				if blocks:
					result["statements"][key] = blocks[0].to_dict()
		# 处理下一个块
		if self.next:
			result["next"] = self.next.to_dict()
		return result

	@classmethod
	def from_dict(cls, data: dict[str, Any]) -> "Block":
		"""从字典创建块"""
		block = cls(
			id=data.get("id", str(uuid.uuid4())),
			type=data["type"],
			fields=data.get("fields", {}),
			shadows=data.get("shadows", {}),
			shield=data.get("shield", False),
			location=data.get("location"),
			comment=data.get("comment"),
			collapsed=data.get("collapsed", False),
			disabled=data.get("disabled", False),
			deletable=data.get("deletable", True),
			movable=data.get("movable", True),
			editable=data.get("editable", True),
			visible=data.get("visible", "visible"),
			is_shadow=data.get("is_shadow", False),
			is_output=data.get("is_output", False),
			parent_id=data.get("parent_id"),
			mutation=data.get("mutation", ""),
		)
		# 递归创建输入块
		if "inputs" in data:
			for key, input_data in data["inputs"].items():
				if input_data:
					block.inputs[key] = cls.from_dict(input_data)
		# 递归创建语句块
		if "statements" in data:
			for key, statement_data in data["statements"].items():
				if statement_data:
					block.statements[key] = [cls.from_dict(statement_data)]
		# 处理下一个块
		if data.get("next"):
			block.next = cls.from_dict(data["next"])
		return block

	def get_all_blocks(self) -> Sequence["Block"]:
		"""获取此块及其所有子块 - 使用Sequence协变"""
		blocks: list[Block] = [self]
		# 遍历输入
		for input_block in self.inputs.values():
			if input_block:
				blocks.extend(input_block.get_all_blocks())
		# 遍历语句
		for statement_blocks in self.statements.values():
			for block in statement_blocks:
				blocks.extend(block.get_all_blocks())
		# 遍历下一个块
		if self.next:
			blocks.extend(self.next.get_all_blocks())
		return blocks

	def find_block(self, block_id: str) -> Optional["Block"]:
		"""查找指定ID的块"""
		if self.id == block_id:
			return self
		for input_block in self.inputs.values():
			if input_block:
				found = input_block.find_block(block_id)
				if found:
					return found
		for statement_blocks in self.statements.values():
			for block in statement_blocks:
				found = block.find_block(block_id)
				if found:
					return found
		if self.next:
			return self.next.find_block(block_id)
		return None


@dataclass
class Actor:
	"""角色"""

	id: str
	name: str
	position: dict[str, float] = field(default_factory=lambda: {"x": 0, "y": 0})
	scale: float = 100.0
	rotation: float = 0.0
	visible: bool = True
	locked: bool = False
	styles: list[str] = field(default_factory=list)
	current_style_id: str = ""
	blocks: list[Block] = field(default_factory=list)
	draggable: bool = True
	rotation_type: str = "all around"
	# 新增:资源引用
	image_resources: list[str] = field(default_factory=list)  # 引用的图片资源ID

	def to_dict(self) -> dict[str, Any]:
		return {
			"id": self.id,
			"name": self.name,
			"position": self.position,
			"scale": self.scale,
			"rotation": self.rotation,
			"visible": self.visible,
			"locked": self.locked,
			"draggable": self.draggable,
			"rotationType": self.rotation_type,
			"styles": self.styles.copy(),
			"currentStyleId": self.current_style_id,
			"nekoBlockJsonList": [block.to_dict() for block in self.blocks],
		}

	@classmethod
	def from_dict(cls, data: dict[str, Any]) -> "Actor":
		actor = cls(
			id=data["id"],
			name=data.get("name", ""),
			position=data.get("position", {"x": 0, "y": 0}),
			scale=data.get("scale", 100.0),
			rotation=data.get("rotation", 0.0),
			visible=data.get("visible", True),
			locked=data.get("locked", False),
			draggable=data.get("draggable", True),
			rotation_type=data.get("rotationType", "all around"),
			styles=data.get("styles", []),
			current_style_id=data.get("currentStyleId", ""),
		)
		blocks_data = data.get("nekoBlockJsonList", [])
		actor.blocks = [Block.from_dict(block_data) for block_data in blocks_data]
		return actor

	def add_block(self, block_type: str, **kwargs: Any) -> Block:
		"""添加代码块"""
		block = Block(type=block_type, **kwargs)
		self.blocks.append(block)
		return block

	def add_move_block(self, x: float, y: float) -> Block:
		"""添加移动块"""
		block = self.add_block("self_move_to")
		block.inputs["X"] = Block(type="math_number", fields={"NUM": str(x)})
		block.inputs["Y"] = Block(type="math_number", fields={"NUM": str(y)})
		return block

	def add_say_block(self, text: str) -> Block:
		"""添加说话块"""
		block = self.add_block("self_dialog")
		block.inputs["TEXT"] = Block(type="text", fields={"TEXT": text})
		return block

	def add_wait_block(self, seconds: float) -> Block:
		"""添加等待块"""
		block = self.add_block("wait")
		block.inputs["SECONDS"] = Block(type="math_number", fields={"NUM": str(seconds)})
		return block


@dataclass
class Scene:
	"""场景"""

	id: str
	name: str
	screen_name: str = "屏幕"
	styles: list[str] = field(default_factory=list)
	actor_ids: list[str] = field(default_factory=list)
	visible: bool = True
	current_style_id: str = ""
	blocks: list[Block] = field(default_factory=list)
	background_color: str = "#FFFFFF"
	background_image: str | None = None  # 引用的背景图片资源ID

	def to_dict(self) -> dict[str, Any]:
		return {
			"id": self.id,
			"name": self.name,
			"screenName": self.screen_name,
			"styles": self.styles.copy(),
			"actorIds": self.actor_ids.copy(),
			"visible": self.visible,
			"currentStyleId": self.current_style_id,
			"backgroundColor": self.background_color,
			"nekoBlockJsonList": [block.to_dict() for block in self.blocks],
		}

	@classmethod
	def from_dict(cls, data: dict[str, Any]) -> "Scene":
		scene = cls(
			id=data["id"],
			name=data.get("name", ""),
			screen_name=data.get("screenName", "屏幕"),
			styles=data.get("styles", []),
			actor_ids=data.get("actorIds", []),
			visible=data.get("visible", True),
			current_style_id=data.get("currentStyleId", ""),
			background_color=data.get("backgroundColor", "#FFFFFF"),
		)
		blocks_data = data.get("nekoBlockJsonList", [])
		scene.blocks = [Block.from_dict(block_data) for block_data in blocks_data]
		return scene


@dataclass
class KNProject:
	"""完整的KN项目"""

	project_name: str = "未命名项目"
	scenes: dict[str, Scene] = field(default_factory=dict)
	current_scene_id: str = ""
	sort_list: list[str] = field(default_factory=list)
	styles: dict[str, Any] = field(default_factory=dict)  # 简化,实际需要Style类
	stage_size: dict[str, int] = field(default_factory=lambda: {"width": 900, "height": 562})
	variables: dict[str, Any] = field(default_factory=dict)
	lists: dict[str, Any] = field(default_factory=dict)
	broadcasts: dict[str, Any] = field(default_factory=dict)
	actors: dict[str, Actor] = field(default_factory=dict)
	audios: dict[str, Any] = field(default_factory=dict)
	procedures: dict[str, Any] = field(default_factory=dict)
	version: str = "0.20.0"
	tool_type: str = "KN"
	timer_position: dict[str, float] = field(default_factory=lambda: {"x": 720, "y": 12})
	filepath: Path | None = None
	# 新增:资源管理
	resources: dict[str, Any] = field(default_factory=dict)
	project_folder: Path | None = None

	@classmethod
	def load_from_file(cls, filepath: str | Path) -> "KNProject":
		filepath = Path(filepath)
		with filepath.open(encoding="utf-8") as f:
			data = json.load(f)
		project = cls.load_from_dict(data)
		project.filepath = filepath
		project.project_folder = filepath.parent
		return project

	@classmethod
	def load_from_dict(cls, data: dict[str, Any]) -> "KNProject":
		project = cls(
			project_name=data.get("projectName", "未命名项目"),
			current_scene_id=data.get("scenes", {}).get("currentSceneId", ""),
			sort_list=data.get("scenes", {}).get("sortList", []),
			version=data.get("version", "0.20.0"),
			tool_type=data.get("toolType", "KN"),
			timer_position=data.get("timerPosition", {"x": 720, "y": 12}),
		)
		# 加载场景
		scenes_dict = data.get("scenes", {}).get("scenesDict", {})
		for scene_id, scene_data in scenes_dict.items():
			scene = Scene.from_dict(scene_data)
			blocks_data = scene_data.get("nekoBlockJsonList", [])
			scene.blocks = [Block.from_dict(block_data) for block_data in blocks_data]
			project.scenes[scene_id] = scene
		# 加载角色
		actors_dict = data.get("actors", {}).get("actorsDict", {})
		for actor_id, actor_data in actors_dict.items():
			project.actors[actor_id] = Actor.from_dict(actor_data)
		# 简化其他数据的加载
		project.styles = data.get("styles", {}).get("stylesDict", {})
		project.variables = data.get("variables", {}).get("variablesDict", {})
		project.lists = data.get("lists", {}).get("listsDict", {})
		project.broadcasts = data.get("broadcasts", {}).get("broadcastsDict", {})
		project.audios = data.get("audios", {}).get("audiosDict", {})
		project.procedures = data.get("procedures", {}).get("proceduresDict", {})
		project.stage_size = data.get("stageSize", {"width": 900, "height": 562})
		return project

	def to_dict(self) -> dict[str, Any]:
		result: dict[str, Any] = {
			"projectName": self.project_name,
			"scenes": {
				"scenesDict": {scene_id: scene.to_dict() for scene_id, scene in self.scenes.items()},
				"currentSceneId": self.current_scene_id,
				"sortList": self.sort_list.copy(),
			},
			"styles": {"stylesDict": self.styles},
			"stageSize": self.stage_size.copy(),
			"variables": {"variablesDict": self.variables},
			"lists": {"listsDict": self.lists},
			"broadcasts": {"broadcastsDict": self.broadcasts},
			"actors": {"actorsDict": {actor_id: actor.to_dict() for actor_id, actor in self.actors.items()}},
			"audios": {"audiosDict": self.audios},
			"procedures": {"proceduresDict": self.procedures},
			"version": self.version,
			"toolType": self.tool_type,
			"timerPosition": self.timer_position,
		}
		return result

	def save_to_file(self, filepath: str | Path | None = None) -> None:
		"""保存项目到文件"""
		if filepath is None:
			if self.filepath is None:
				msg = "没有指定文件路径"
				raise ValueError(msg)
			filepath = self.filepath
		else:
			filepath = Path(filepath)
		self.project_folder = filepath.parent
		self.filepath = filepath
		data = self.to_dict()
		with filepath.open("w", encoding="utf-8") as f:
			json.dump(data, f, ensure_ascii=False, indent=2)

	def add_actor(self, name: str, position: dict[str, float] | None = None) -> str:
		"""添加角色"""
		actor_id = str(uuid.uuid4())
		actor = Actor(id=actor_id, name=name, position=position or {"x": 0, "y": 0})
		self.actors[actor_id] = actor
		return actor_id

	def add_scene(self, name: str, screen_name: str = "屏幕") -> str:
		"""添加场景"""
		scene_id = str(uuid.uuid4())
		scene = Scene(id=scene_id, name=name, screen_name=screen_name)
		self.scenes[scene_id] = scene
		self.sort_list.append(scene_id)
		if not self.current_scene_id:
			self.current_scene_id = scene_id
		return scene_id

	def add_variable(self, name: str, value: Any = 0, *, is_global: bool = True) -> str:
		"""添加变量"""
		var_id = str(uuid.uuid4())
		variable = {"id": var_id, "name": name, "value": value, "isGlobal": is_global}
		self.variables[var_id] = variable
		return var_id

	def get_all_blocks(self) -> list[Block]:
		"""获取项目中所有块"""
		all_blocks = []
		# 场景的块
		for scene in self.scenes.values():
			all_blocks.extend(scene.blocks)
			for block in scene.blocks:
				all_blocks.extend(block.get_all_blocks())
		# 角色的块
		for actor in self.actors.values():
			all_blocks.extend(actor.blocks)
			for block in actor.blocks:
				all_blocks.extend(block.get_all_blocks())
		return all_blocks

	def find_block(self, block_id: str) -> Block | None:
		"""在项目中查找代码块"""
		for block in self.get_all_blocks():
			if block.id == block_id:
				return block
		return None


# ============================================================================
# KN项目编辑器 - 增强版
# ============================================================================
class KNEditor:
	"""KN项目编辑器核心类 - 增强版"""

	MAX_UNDO_STACK_SIZE = 50

	def __init__(self, project: KNProject | None = None) -> None:
		self.project = project or KNProject()
		self.block_defs = BlockDefinitionManager()
		self.current_actor: Actor | None = None
		self.current_procedure: Any | None = None
		self.current_scene: Scene | None = None
		self.selected_block: Block | None = None
		self.undo_stack: list[dict[str, Any]] = []
		self.redo_stack: list[dict[str, Any]] = []
		self.selection_history: list[str] = []

	def load_project(self, filepath: str | Path) -> None:
		"""加载项目文件"""
		self.project = KNProject.load_from_file(filepath)
		print(f"已加载项目: {self.project.project_name}")

	def save_project(self, filepath: str | Path | None = None) -> None:
		"""保存项目文件"""
		self.project.save_to_file(filepath)
		if filepath:
			print(f"项目已保存: {filepath}")
		elif self.project.filepath:
			print(f"项目已保存: {self.project.filepath}")

	def create_new_project(self, project_name: str = "新项目") -> None:
		"""创建新项目"""
		self.project = KNProject(project_name=project_name)
		scene_id = self.project.add_scene("场景1")
		self.select_scene(scene_id)
		actor_id = self.project.add_actor("角色1")
		self.select_actor(actor_id)
		print(f"已创建新项目: {project_name}")

	def select_actor(self, actor_id: str) -> bool:
		"""选择角色"""
		if actor_id in self.project.actors:
			self.current_actor = self.project.actors[actor_id]
			self.current_procedure = None
			self.current_scene = None
			self.selection_history.append(f"actor:{actor_id}")
			return True
		return False

	def select_scene(self, scene_id: str) -> bool:
		"""选择场景"""
		if scene_id in self.project.scenes:
			self.current_scene = self.project.scenes[scene_id]
			self.current_actor = None
			self.current_procedure = None
			self.selection_history.append(f"scene:{scene_id}")
			return True
		return False

	def get_current_entity(self) -> tuple[str, Actor | Any | Scene | None]:
		"""获取当前选择的实体"""
		if self.current_actor:
			return ("actor", self.current_actor)
		if self.current_procedure:
			return ("procedure", self.current_procedure)
		if self.current_scene:
			return ("scene", self.current_scene)
		return ("none", None)

	def get_current_blocks(self) -> list[Block]:
		"""获取当前选中对象的代码块"""
		_, entity = self.get_current_entity()
		if entity:
			return entity.blocks
		return []

	# ============================================================================
	# 1. 块验证功能
	# ============================================================================
	def validate_block(self, block: Block) -> list[str]:
		"""验证块的完整性,返回错误列表"""
		errors: list[str] = []
		definition = self.block_defs.get_definition(block.type)
		if not definition:
			errors.append(f"未知块类型: {block.type}")
			return errors
		# 检查必需字段
		for field_name in definition.required_fields:
			if field_name not in block.fields:
				errors.append(f"缺少必需字段: {field_name}")
			elif block.fields[field_name] is None or not block.fields[field_name]:
				errors.append(f"字段 {field_name} 不能为空")
		# 检查字段类型
		for field_name, field_type in definition.fields.items():
			if field_name in block.fields:
				value = block.fields[field_name]
				if field_type == FieldType.NUMBER:
					if not _is_valid_number(value):
						errors.append(f"字段 {field_name} 应为数字,实际为: {value}")
				elif field_type == FieldType.BOOLEAN and value not in {"true", "false", True, False}:
					errors.append(f"字段 {field_name} 应为布尔值,实际为: {value}")
		# 检查必需输入
		for input_name in definition.required_inputs:
			if input_name not in block.inputs and input_name not in block.shadows:
				errors.append(f"缺少必需输入: {input_name}")
			elif input_name in block.inputs and block.inputs[input_name] is None:
				errors.append(f"输入 {input_name} 不能为空")
		# 检查输入块的有效性(递归)
		for input_name, input_block in block.inputs.items():
			if input_block:
				input_errors = self.validate_block(input_block)
				errors.extend(f"输入 {input_name}: {err}" for err in input_errors)
		# 检查语句块的有效性(递归)
		for stmt_name, stmt_blocks in block.statements.items():
			for stmt_block in stmt_blocks:
				stmt_errors = self.validate_block(stmt_block)
				errors.extend(f"语句 {stmt_name}: {err}" for err in stmt_errors)
		# 检查下一个块
		if block.next:
			next_errors = self.validate_block(block.next)
			errors.extend(f"下一个块: {err}" for err in next_errors)
		return errors

	def validate_project(self) -> dict[str, list[str]]:
		"""验证整个项目,返回验证结果"""
		results: dict[str, list[str]] = {}
		# 验证所有块
		all_blocks = self.project.get_all_blocks()
		for block in all_blocks:
			errors = self.validate_block(block)
			if errors:
				results[f"块 {block.id[:8]} ({block.type})"] = errors
		# 验证变量引用
		variable_refs = self._find_all_variable_references()
		for var_id in self.project.variables:
			if var_id not in variable_refs:
				results.setdefault("未使用的变量", []).append(var_id)
		# 验证角色引用
		for scene in self.project.scenes.values():
			for actor_id in scene.actor_ids:
				if actor_id not in self.project.actors:
					results.setdefault("无效的角色引用", []).append(f"场景 {scene.name}: 引用不存在的角色 {actor_id}")
		return results

	def _find_all_variable_references(self) -> set[str]:
		"""查找所有变量引用"""
		refs: set[str] = set()
		for block in self.project.get_all_blocks():
			# 检查块字段中的变量引用
			for field_value in block.fields.values():
				if isinstance(field_value, str) and field_value.startswith("var_"):
					refs.add(field_value[4:])  # 去掉 "var_" 前缀
			# 递归检查输入和语句
			refs.update(self._find_variable_refs_in_block(block))
		return refs

	def _find_variable_refs_in_block(self, block: Block) -> set[str]:
		"""在块及其子块中查找变量引用"""
		refs: set[str] = set()
		# 检查输入块
		for input_block in block.inputs.values():
			if input_block:
				refs.update(self._find_variable_refs_in_block(input_block))
		# 检查语句块
		for stmt_blocks in block.statements.values():
			for stmt_block in stmt_blocks:
				refs.update(self._find_variable_refs_in_block(stmt_block))
		# 检查下一个块
		if block.next:
			refs.update(self._find_variable_refs_in_block(block.next))
		return refs

	def auto_fix_block(self, block: Block) -> list[str]:
		"""自动修复块的常见问题"""
		fixes: list[str] = []
		definition = self.block_defs.get_definition(block.type)
		if not definition:
			return fixes
		# 填充缺失的默认字段
		for field_name, field_value in definition.default_fields.items():
			if field_name not in block.fields:
				block.fields[field_name] = field_value
				fixes.append(f"填充默认字段: {field_name} = {field_value}")
		# 填充缺失的默认输入
		for input_name, default_input in definition.default_inputs.items():
			if input_name not in block.inputs and input_name not in block.shadows and isinstance(default_input, str):
				default_block = Block(type=default_input)
				block.inputs[input_name] = default_block
				fixes.append(f"创建默认输入: {input_name}")
		# 修复无效的数字字段
		for field_name, field_type in definition.fields.items():
			if field_type == FieldType.NUMBER and field_name in block.fields:
				value = block.fields[field_name]
				if not _is_valid_number(value):
					block.fields[field_name] = "0"
					fixes.append(f"修复无效数字: {field_name} -> 0")
		# 递归修复子块
		for input_name, input_block in block.inputs.items():
			if input_block:
				sub_fixes = self.auto_fix_block(input_block)
				fixes.extend(f"输入 {input_name}: {fix}" for fix in sub_fixes)
		for stmt_name, stmt_blocks in block.statements.items():
			for stmt_block in stmt_blocks:
				sub_fixes = self.auto_fix_block(stmt_block)
				fixes.extend(f"语句 {stmt_name}: {fix}" for fix in sub_fixes)
		if block.next:
			sub_fixes = self.auto_fix_block(block.next)
			for fix in sub_fixes:
				fixes.append(f"下一个块: {fix}")
		return fixes

	# ============================================================================
	# 2. 代码生成器
	# ============================================================================
	def generate_python_code(self, block: Block | None = None, indent: int = 0) -> str:
		"""将块转换为Python代码"""
		if block is None:
			# 生成当前选中实体的所有代码
			_, entity = self.get_current_entity()
			if not entity:
				return "# 没有选中的实体\n"
			code_lines = [self.generate_python_code(blk) for blk in entity.blocks]
			return "\n".join(code_lines)
		indent_str = "    " * indent
		definition = self.block_defs.get_definition(block.type)
		if not definition:
			return f"{indent_str}# 未知块: {block.type}\n"
		# 根据块类型生成代码
		if block.type == "on_running_group_activated":
			code = f"{indent_str}# 当程序启动时\n"
			if block.next:
				code += self.generate_python_code(block.next, indent)
			return code
		if block.type == "self_dialog":
			text = block.fields.get("TEXT", "")
			code = f'{indent_str}print("{text}")\n'
			if block.next:
				code += self.generate_python_code(block.next, indent)
			return code
		if block.type == "self_move_to":
			x = self._get_input_value(block, "X", "0")
			y = self._get_input_value(block, "Y", "0")
			code = f"{indent_str}move_to({x}, {y})\n"
			if block.next:
				code += self.generate_python_code(block.next, indent)
			return code
		if block.type == "wait":
			seconds = self._get_input_value(block, "SECONDS", "1")
			code = f"{indent_str}time.sleep({seconds})\n"
			if block.next:
				code += self.generate_python_code(block.next, indent)
			return code
		if block.type == "repeat_n_times":
			times = self._get_input_value(block, "TIMES", "10")
			code = f"{indent_str}for i in range({times}):\n"
			if "DO" in block.statements:
				for stmt_block in block.statements["DO"]:
					code += self.generate_python_code(stmt_block, indent + 1)
			if block.next:
				code += self.generate_python_code(block.next, indent)
			return code
		if block.type == "repeat_forever":
			code = f"{indent_str}while True:\n"
			if "DO" in block.statements:
				for stmt_block in block.statements["DO"]:
					code += self.generate_python_code(stmt_block, indent + 1)
			if block.next:
				code += self.generate_python_code(block.next, indent)
			return code
		if block.type == "controls_if":
			condition = self._get_input_value(block, "IF", "True")
			code = f"{indent_str}if {condition}:\n"
			if "THEN" in block.statements:
				for stmt_block in block.statements["THEN"]:
					code += self.generate_python_code(stmt_block, indent + 1)
			if block.next:
				code += self.generate_python_code(block.next, indent)
			return code
		if block.type == "variables_set":
			var_name = block.fields.get("VARIABLE", "var")
			value = self._get_input_value(block, "VALUE", "0")
			code = f"{indent_str}{var_name} = {value}\n"
			if block.next:
				code += self.generate_python_code(block.next, indent)
			return code
		if block.type == "change_variables":
			var_name = block.fields.get("VARIABLE", "var")
			value = self._get_input_value(block, "VALUE", "1")
			code = f"{indent_str}{var_name} += {value}\n"
			if block.next:
				code += self.generate_python_code(block.next, indent)
			return code
		if block.type == "play_audio":
			audio_name = block.fields.get("AUDIO", "")
			code = f"{indent_str}play_sound('{audio_name}')\n"
			if block.next:
				code += self.generate_python_code(block.next, indent)
			return code
		# 默认处理:转换为注释
		code = f"{indent_str}# {definition.name}\n"
		if block.fields:
			for field_name, field_value in block.fields.items():
				code += f"{indent_str}#   {field_name}: {field_value}\n"
		# 处理子块
		for input_name, input_block in block.inputs.items():
			if input_block:
				code += f"{indent_str}# 输入 {input_name}:\n"
				code += self.generate_python_code(input_block, indent + 1)
		for stmt_name, stmt_blocks in block.statements.items():
			if stmt_blocks:
				code += f"{indent_str}# 语句 {stmt_name}:\n"
				for stmt_block in stmt_blocks:
					code += self.generate_python_code(stmt_block, indent + 1)
		if block.next:
			code += self.generate_python_code(block.next, indent)
		return code

	def _get_input_value(self, block: Block, input_name: str, default: str) -> str:
		"""获取输入块的值"""
		if input_block := block.inputs.get(input_name):
			if input_block.type == "math_number":
				return input_block.fields.get("NUM", default)
			if input_block.type == "text":
				return f'"{input_block.fields.get("TEXT", default)}"'
			if input_block.type == "variables_get":
				return input_block.fields.get("VARIABLE", default)
		# 尝试从字段获取
		if input_name in block.fields:
			value = block.fields[input_name]
			if _is_valid_number(value):
				return str(value)
		return default

	def generate_pseudocode(self, block: Block | None = None, indent: int = 0) -> str:
		"""生成伪代码(类似Scratch的块描述)"""
		if block is None:
			_, entity = self.get_current_entity()
			if not entity:
				return "# 没有选中的实体\n"
			code_lines = [self.generate_pseudocode(blk) for blk in entity.blocks]
			return "\n".join(code_lines)
		indent_str = "  " * indent
		definition = self.block_defs.get_definition(block.type)
		if not definition:
			return f"{indent_str}[未知块: {block.type}]\n"
		# 根据块类型生成伪代码
		if block.type == "on_running_group_activated":
			code = f"{indent_str}当程序启动时\n"
			if block.next:
				code += self.generate_pseudocode(block.next, indent)
			return code
		if block.type == "self_dialog":
			text = block.fields.get("TEXT", "")
			code = f"{indent_str}说:{text}\n"
			if block.next:
				code += self.generate_pseudocode(block.next, indent)
			return code
		if block.type == "self_move_to":
			x = _get_pseudocode_value(block, "X", "0")
			y = _get_pseudocode_value(block, "Y", "0")
			code = f"{indent_str}移动到X:{x} Y:{y}\n"
			if block.next:
				code += self.generate_pseudocode(block.next, indent)
			return code
		if block.type == "wait":
			seconds = _get_pseudocode_value(block, "SECONDS", "1")
			code = f"{indent_str}等待 {seconds} 秒\n"
			if block.next:
				code += self.generate_pseudocode(block.next, indent)
			return code
		if block.type == "repeat_n_times":
			times = _get_pseudocode_value(block, "TIMES", "10")
			code = f"{indent_str}重复 {times} 次:\n"
			if "DO" in block.statements:
				for stmt_block in block.statements["DO"]:
					code += self.generate_pseudocode(stmt_block, indent + 1)
			if block.next:
				code += self.generate_pseudocode(block.next, indent)
			return code
		# 默认处理
		code = f"{indent_str}[{definition.name}]\n"
		if block.next:
			code += self.generate_pseudocode(block.next, indent)
		return code

	# ============================================================================
	# 3. 批量操作功能
	# ============================================================================
	def batch_update_variables(self, updates: dict[str, Any]) -> None:
		"""批量更新变量"""
		self._save_state()
		for var_id, new_value in updates.items():
			if var_id in self.project.variables:
				if isinstance(self.project.variables[var_id], dict):
					self.project.variables[var_id]["value"] = new_value
				else:
					# 如果是Variable对象
					self.project.variables[var_id].value = new_value
		print(f"已批量更新 {len(updates)} 个变量")

	def batch_update_actors(self, updates: dict[str, dict[str, Any]]) -> None:
		"""批量更新角色属性"""
		self._save_state()
		for actor_id, properties in updates.items():
			if actor_id in self.project.actors:
				actor = self.project.actors[actor_id]
				for prop_name, prop_value in properties.items():
					if hasattr(actor, prop_name):
						setattr(actor, prop_name, prop_value)
					elif prop_name == "position" and isinstance(prop_value, dict) and "x" in prop_value and "y" in prop_value:
						actor.position = prop_value
		print(f"已批量更新 {len(updates)} 个角色")

	def duplicate_actor_with_code(self, actor_id: str, new_name: str) -> str:
		"""复制角色及其所有代码"""
		if actor_id not in self.project.actors:
			print(f"角色不存在: {actor_id}")
			return ""
		self._save_state()
		original = self.project.actors[actor_id]
		# 深拷贝角色
		import copy

		new_actor = copy.deepcopy(original)
		new_actor.id = str(uuid.uuid4())
		new_actor.name = new_name
		# 重新生成所有块的ID
		block_id_map = {}
		for block in new_actor.blocks:
			old_id = block.id
			new_id = str(uuid.uuid4())
			block_id_map[old_id] = new_id
			block.id = new_id

		def update_block_ids(block: Block) -> None:
			if block.id in block_id_map:
				block.id = block_id_map[block.id]
			# 更新输入块
			for input_block in block.inputs.values():
				if input_block:
					update_block_ids(input_block)
			# 更新语句块
			for stmt_blocks in block.statements.values():
				for stmt_block in stmt_blocks:
					update_block_ids(stmt_block)
			# 更新下一个块
			if block.next:
				update_block_ids(block.next)

		for block in new_actor.blocks:
			update_block_ids(block)
		# 添加到项目
		self.project.actors[new_actor.id] = new_actor
		# 添加到当前场景
		if self.current_scene and actor_id in self.current_scene.actor_ids:
			self.current_scene.actor_ids.append(new_actor.id)
		print(f"已复制角色: {original.name} -> {new_name} (包含 {len(new_actor.blocks)} 个代码块)")
		return new_actor.id

	def batch_create_blocks(self, block_specs: list[dict[str, Any]]) -> list[Block]:
		"""批量创建代码块"""
		self._save_state()
		created_blocks: list[Block] = []
		for spec in block_specs:
			block_type = spec.get("type", "")
			if not block_type:
				continue
			block = Block(type=block_type)
			# 设置字段
			if "fields" in spec:
				block.fields.update(spec["fields"])
			# 设置位置
			if "location" in spec:
				block.location = spec["location"]
			# 添加到当前实体
			_, entity = self.get_current_entity()
			if entity:
				entity.blocks.append(block)
				created_blocks.append(block)
		print(f"已批量创建 {len(created_blocks)} 个代码块")
		return created_blocks

	def batch_delete_blocks(self, block_ids: list[str]) -> int:
		"""批量删除代码块"""
		self._save_state()
		deleted_count = 0
		for block_id in block_ids:
			if self.delete_block(block_id):
				deleted_count += 1
		print(f"已批量删除 {deleted_count} 个代码块")
		return deleted_count

	def batch_move_actors(self, moves: dict[str, dict[str, float]]) -> None:
		"""批量移动角色位置"""
		self._save_state()
		for actor_id, position in moves.items():
			if actor_id in self.project.actors:
				self.project.actors[actor_id].position = {"x": position.get("x", 0), "y": position.get("y", 0)}
		print(f"已批量移动 {len(moves)} 个角色")

	# ============================================================================
	# 4. 错误恢复机制
	# ============================================================================
	def auto_fix_project(self) -> dict[str, list[str]]:
		"""自动修复项目中的问题"""
		fixes: dict[str, list[str]] = {}
		# 1. 修复孤儿块
		orphan_fixes = self._fix_orphan_blocks()
		if orphan_fixes:
			fixes["修复孤儿块"] = orphan_fixes
		# 2. 修复无效引用
		ref_fixes = self._fix_invalid_references()
		if ref_fixes:
			fixes["修复无效引用"] = ref_fixes
		# 3. 修复重复ID
		id_fixes = self._fix_duplicate_ids()
		if id_fixes:
			fixes["修复重复ID"] = id_fixes
		# 4. 自动修复所有块
		block_fixes = []
		for block in self.project.get_all_blocks():
			block_fixes.extend(self.auto_fix_block(block))
		if block_fixes:
			fixes["自动修复块"] = block_fixes[:10]  # 只显示前10个
		# 5. 重建缺失的数据结构
		struct_fixes = self._rebuild_missing_structures()
		if struct_fixes:
			fixes["重建数据结构"] = struct_fixes
		return fixes

	def _fix_orphan_blocks(self) -> list[str]:
		"""修复孤儿块(没有父块的顶级块)"""
		fixes: list[str] = []
		# 收集所有有父块的块ID
		parented_blocks: set[str] = set()
		for block in self.project.get_all_blocks():
			for input_block in block.inputs.values():
				if input_block:
					parented_blocks.update(b.id for b in input_block.get_all_blocks())
			for stmt_blocks in block.statements.values():
				for stmt_block in stmt_blocks:
					parented_blocks.update(b.id for b in stmt_block.get_all_blocks())
			if block.next:
				parented_blocks.update(b.id for b in block.next.get_all_blocks())
		# 检查每个实体的顶级块
		for scene in self.project.scenes.values():
			for block in scene.blocks[:]:  # 创建副本以便修改
				if block.id in parented_blocks:
					# 这个块已经有父块,从场景中移除
					scene.blocks.remove(block)
					fixes.append(f"从场景 {scene.name} 移除孤儿块: {block.id[:8]}")
		for actor in self.project.actors.values():
			for block in actor.blocks[:]:
				if block.id in parented_blocks:
					actor.blocks.remove(block)
					fixes.append(f"从角色 {actor.name} 移除孤儿块: {block.id[:8]}")
		return fixes

	def _fix_invalid_references(self) -> list[str]:
		"""修复无效引用"""
		fixes: list[str] = []
		# 修复场景中的无效角色引用
		for scene in self.project.scenes.values():
			valid_actor_ids = []
			for actor_id in scene.actor_ids:
				if actor_id in self.project.actors:
					valid_actor_ids.append(actor_id)
				else:
					fixes.append(f"从场景 {scene.name} 移除无效角色引用: {actor_id}")
			# 更新场景的角色ID列表
			scene.actor_ids = valid_actor_ids
		# 修复变量引用
		all_blocks = self.project.get_all_blocks()
		for block in all_blocks:
			self._fix_block_references(block, fixes)
		return fixes

	def _fix_block_references(self, block: Block, fixes: list[str]) -> None:
		"""修复块中的引用"""
		# 修复变量引用
		for field_name, field_value in list(block.fields.items()):
			if field_name.endswith("_VARIABLE") and isinstance(field_value, str) and field_value not in self.project.variables:
				# 创建缺失的变量
				var_id = str(uuid.uuid4())
				self.project.variables[var_id] = {"id": var_id, "name": field_value, "value": 0, "isGlobal": True}
				fixes.append(f"创建缺失变量: {field_value}")
		# 递归修复子块
		for input_block in block.inputs.values():
			if input_block:
				self._fix_block_references(input_block, fixes)
		for stmt_blocks in block.statements.values():
			for stmt_block in stmt_blocks:
				self._fix_block_references(stmt_block, fixes)
		if block.next:
			self._fix_block_references(block.next, fixes)

	def _fix_duplicate_ids(self) -> list[str]:
		"""修复重复的ID"""
		fixes: list[str] = []
		seen_ids: set[str] = set()
		# 检查角色ID
		for actor_id in list(self.project.actors.keys()):
			if actor_id in seen_ids:
				# 创建新的ID
				new_id = str(uuid.uuid4())
				actor = self.project.actors.pop(actor_id)
				actor.id = new_id
				self.project.actors[new_id] = actor
				fixes.append(f"修复重复角色ID: {actor_id[:8]} -> {new_id[:8]}")
			seen_ids.add(actor_id)
		# 检查场景ID
		for scene_id in list(self.project.scenes.keys()):
			if scene_id in seen_ids:
				new_id = str(uuid.uuid4())
				scene = self.project.scenes.pop(scene_id)
				scene.id = new_id
				self.project.scenes[new_id] = scene
				fixes.append(f"修复重复场景ID: {scene_id[:8]} -> {new_id[:8]}")
			seen_ids.add(scene_id)
		# 检查块ID
		block_id_map = {}
		all_blocks = self.project.get_all_blocks()
		for block in all_blocks:
			if block.id in seen_ids:
				new_id = str(uuid.uuid4())
				block_id_map[block.id] = new_id
				block.id = new_id
				fixes.append(f"修复重复块ID: {block.id[:8]}")
			seen_ids.add(block.id)
		# 更新块引用
		for block in all_blocks:
			self._update_block_references(block, block_id_map)
		return fixes

	def _update_block_references(self, block: Block, id_map: dict[str, str]) -> None:
		"""更新块中的ID引用"""
		# 更新父ID
		if block.parent_id and block.parent_id in id_map:
			block.parent_id = id_map[block.parent_id]
		# 递归更新子块
		for input_block in block.inputs.values():
			if input_block:
				self._update_block_references(input_block, id_map)
		for stmt_blocks in block.statements.values():
			for stmt_block in stmt_blocks:
				self._update_block_references(stmt_block, id_map)
		if block.next:
			self._update_block_references(block.next, id_map)

	def _rebuild_missing_structures(self) -> list[str]:
		"""重建缺失的数据结构"""
		fixes: list[str] = []
		# 确保当前场景ID有效
		if self.project.current_scene_id and self.project.current_scene_id not in self.project.scenes:
			if self.project.scenes:
				self.project.current_scene_id = next(iter(self.project.scenes.keys()))
				fixes.append(f"重置当前场景ID为: {self.project.current_scene_id[:8]}")
			else:
				self.project.current_scene_id = ""
				fixes.append("清空无效的当前场景ID")
		# 确保排序列表与场景匹配
		valid_sort_list = []
		for scene_id in self.project.sort_list:
			if scene_id in self.project.scenes:
				valid_sort_list.append(scene_id)
			else:
				fixes.append(f"从排序列表中移除无效场景: {scene_id}")
		# 添加缺失的场景到排序列表
		for scene_id in self.project.scenes:
			if scene_id not in valid_sort_list:
				valid_sort_list.append(scene_id)
				fixes.append(f"添加场景到排序列表: {scene_id[:8]}")
		self.project.sort_list = valid_sort_list
		return fixes

	def create_backup(self, backup_folder: Path | None = None) -> Path:
		"""创建项目备份"""
		if backup_folder is None:
			backup_folder = self.project.filepath.parent / "backups" if self.project.filepath else Path.cwd() / "backups"
		backup_folder.mkdir(parents=True, exist_ok=True)
		timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
		backup_file = backup_folder / f"{self.project.project_name}_{timestamp}.kn.backup"
		# 保存当前状态
		data = self.project.to_dict()
		with backup_file.open("w", encoding="utf-8") as f:
			json.dump(data, f, ensure_ascii=False, indent=2)
		print(f"已创建备份: {backup_file}")
		return backup_file

	# ============================================================================
	# 5. 性能优化功能
	# ============================================================================
	def optimize_project(self) -> dict[str, int]:
		"""优化项目性能"""
		results: dict[str, int] = {}
		# 1. 移除未使用的资源
		unused_resources = self._remove_unused_resources()
		results["移除未使用的资源"] = unused_resources
		# 2. 压缩块ID
		compressed_blocks = self._compress_block_ids()
		results["压缩块ID"] = compressed_blocks
		# 3. 合并重复块
		merged_blocks = self._merge_duplicate_blocks()
		results["合并重复块"] = merged_blocks
		# 4. 清理空块
		cleaned_blocks = self._clean_empty_blocks()
		results["清理空块"] = cleaned_blocks
		# 5. 优化变量存储
		optimized_vars = self._optimize_variables()
		results["优化变量"] = optimized_vars
		total_optimized = sum(results.values())
		if total_optimized > 0:
			print(f"项目优化完成,共优化 {total_optimized} 个项目")
		return results

	def _remove_unused_resources(self) -> int:
		"""删除未使用的资源"""
		if not hasattr(self.project, "resources"):
			return 0
		used_resources: set[str] = set()
		# 收集使用的样式
		for actor in self.project.actors.values():
			used_resources.update(actor.styles)
			if actor.current_style_id:
				used_resources.add(actor.current_style_id)
		# 收集场景背景
		for scene in self.project.scenes.values():
			if scene.background_image:
				used_resources.add(scene.background_image)
		# 收集音频引用(简化处理)
		all_blocks = self.project.get_all_blocks()
		for block in all_blocks:
			if block.type == "play_audio":
				audio_id = block.fields.get("AUDIO", "")
				if audio_id:
					used_resources.add(audio_id)
		# 删除未使用的资源
		unused = [resource_id for resource_id in list(self.project.resources.keys()) if resource_id not in used_resources]
		for resource_id in unused:
			del self.project.resources[resource_id]
		return len(unused)

	def _compress_block_ids(self) -> int:
		"""压缩块ID(将长UUID替换为短ID)"""
		all_blocks = self.project.get_all_blocks()
		# 创建ID映射
		id_map: dict[str, str] = {}
		short_id_counter = 1
		for block in all_blocks:
			if len(block.id) > 8:  # 只压缩长ID
				short_id = f"b{short_id_counter}"
				id_map[block.id] = short_id
				block.id = short_id
				short_id_counter += 1
		# 更新块引用
		for block in all_blocks:
			self._update_block_references(block, id_map)
		return len(id_map)

	def _merge_duplicate_blocks(self) -> int:
		"""合并完全相同的块"""
		merged_count = 0
		all_blocks = self.project.get_all_blocks()
		# 计算块的哈希值
		block_hashes: dict[str, list[Block]] = {}

		def block_hash(block: Block) -> int:
			"""计算块的哈希值"""
			parts = [block.type, str(sorted(block.fields.items())), str(block.mutation)]
			return hash("|".join(parts))

		# 按哈希值分组
		for block in all_blocks:
			h = str(block_hash(block))
			if h not in block_hashes:
				block_hashes[h] = []
			block_hashes[h].append(block)
		# 合并相同哈希的块
		for blocks in block_hashes.values():
			if len(blocks) > 1:
				# 保留第一个,用它的ID替换其他的
				keep_block = blocks[0]
				for block in blocks[1:]:
					# 替换引用
					self._replace_block_reference(block.id, keep_block.id)
					merged_count += 1
		return merged_count

	def _replace_block_reference(self, old_id: str, new_id: str) -> None:
		"""替换块引用"""
		for block in self.project.get_all_blocks():
			# 检查输入
			for input_name, input_block in list(block.inputs.items()):
				if input_block and input_block.id == old_id:
					# 需要找到新的块
					new_block = self.project.find_block(new_id)
					if new_block:
						block.inputs[input_name] = new_block
			# 检查语句
			for stmt_blocks in list(block.statements.values()):
				for i, stmt_block in enumerate(stmt_blocks):
					if stmt_block.id == old_id:
						new_block = self.project.find_block(new_id)
						if new_block:
							stmt_blocks[i] = new_block
			# 检查下一个块
			if block.next and block.next.id == old_id:
				new_block = self.project.find_block(new_id)
				if new_block:
					block.next = new_block

	def _clean_empty_blocks(self) -> int:
		"""清理空块(没有内容的块)"""
		cleaned_count = 0

		def is_empty_block(block: Block) -> bool:
			"""检查是否为空块"""
			# 某些块类型允许为空
			if block.type in {"comment", "separator"}:
				return False
			# 没有字段、输入、语句和下一个块
			return not block.fields and not any(block.inputs.values()) and not any(block.statements.values()) and not block.next and not block.comment

		# 检查每个实体的块
		for scene in self.project.scenes.values():
			original_count = len(scene.blocks)
			scene.blocks = [b for b in scene.blocks if not is_empty_block(b)]
			cleaned_count += original_count - len(scene.blocks)
		for actor in self.project.actors.values():
			original_count = len(actor.blocks)
			actor.blocks = [b for b in actor.blocks if not is_empty_block(b)]
			cleaned_count += original_count - len(actor.blocks)
		return cleaned_count

	def _optimize_variables(self) -> int:
		"""优化变量存储"""
		optimized_count = 0
		# 1. 移除未使用的变量
		variable_refs = self._find_all_variable_references()
		unused_vars = [var_id for var_id in list(self.project.variables.keys()) if var_id not in variable_refs]
		for var_id in unused_vars:
			del self.project.variables[var_id]
			optimized_count += 1
		# 2. 合并相同值的变量
		value_map: dict[str, list[str]] = {}
		for var_id, var_data in self.project.variables.items():
			value = str(var_data.get("value", "")) if isinstance(var_data, dict) else str(var_data.value)
			if value not in value_map:
				value_map[value] = []
			value_map[value].append(var_id)
		# 对于每个值,保留第一个变量,其他变量引用它
		for var_ids in value_map.values():
			if len(var_ids) > 1:
				keep_id = var_ids[0]
				for var_id in var_ids[1:]:
					# 替换引用
					self._replace_variable_reference(var_id, keep_id)
					# 移除重复变量
					if var_id in self.project.variables:
						del self.project.variables[var_id]
						optimized_count += 1
		return optimized_count

	def _replace_variable_reference(self, old_id: str, new_id: str) -> None:
		"""替换变量引用"""
		for block in self.project.get_all_blocks():
			for field_name, field_value in list(block.fields.items()):
				if field_value == old_id:
					block.fields[field_name] = new_id

	# ============================================================================
	# 原有功能(需要添加_ save_state调用)
	# ============================================================================
	def add_block(
		self,
		block_type: str,
		location: tuple[float, float] | None = None,
		fields: dict[str, Any] | None = None,
	) -> Block | None:
		"""添加新代码块"""
		self._save_state()
		definition = self.block_defs.get_definition(block_type)
		if not definition:
			print(f"未知的块类型: {block_type}")
			return None
		new_block = Block(type=block_type)
		for field_name, field_value in definition.default_fields.items():
			new_block.fields[field_name] = field_value
		if fields:
			for field_name, field_value in fields.items():
				if field_name in definition.fields:
					new_block.fields[field_name] = field_value
		if location:
			new_block.location = list(location)
		_, entity = self.get_current_entity()
		if entity:
			entity.blocks.append(new_block)
			self.selected_block = new_block
			return new_block
		return None

	def delete_block(self, block_id: str) -> bool:
		"""删除代码块"""
		self._save_state()
		blocks = self.get_current_blocks()
		for i, block in enumerate(blocks):
			if block.id == block_id:
				del blocks[i]
				return True
		for block in self.project.get_all_blocks():
			found = self._delete_block_recursive(block, block_id)
			if found:
				return True
		return False

	def _delete_block_recursive(self, parent_block: Block, block_id: str) -> bool:
		"""递归删除块"""
		for input_name, input_block in list(parent_block.inputs.items()):
			if input_block:
				if input_block.id == block_id:
					parent_block.inputs[input_name] = None
					return True
				found = self._delete_block_recursive(input_block, block_id)
				if found:
					return True
		for stmt_blocks in list(parent_block.statements.values()):
			for i, stmt_block in enumerate(stmt_blocks):
				if stmt_block.id == block_id:
					del stmt_blocks[i]
					return True
				found = self._delete_block_recursive(stmt_block, block_id)
				if found:
					return True
		if parent_block.next:
			if parent_block.next.id == block_id:
				parent_block.next = None
				return True
			found = self._delete_block_recursive(parent_block.next, block_id)
			if found:
				return True
		return False

	def _save_state(self) -> None:
		"""保存当前状态到撤销栈"""
		state = copy.deepcopy(asdict(self.project))
		self.undo_stack.append(state)
		self.redo_stack.clear()
		if len(self.undo_stack) > self.MAX_UNDO_STACK_SIZE:
			self.undo_stack.pop(0)

	def undo(self) -> bool:
		"""撤销操作"""
		if not self.undo_stack:
			return False
		current_state = copy.deepcopy(asdict(self.project))
		self.redo_stack.append(current_state)
		prev_state = self.undo_stack.pop()
		try:
			self.project = KNProject.load_from_dict(prev_state)
			return True
		except Exception as e:
			print(f"撤销操作失败: {e}")
			return False

	def redo(self) -> bool:
		"""重做操作"""
		if not self.redo_stack:
			return False
		current_state = copy.deepcopy(asdict(self.project))
		self.undo_stack.append(current_state)
		next_state = self.redo_stack.pop()
		try:
			self.project = KNProject.load_from_dict(next_state)
			return True
		except Exception as e:
			print(f"重做操作失败: {e}")
			return False

	def print_block_tree(self, block: Block | None = None, indent: int = 0) -> None:
		"""打印代码块树"""
		if block is None:
			blocks = self.get_current_blocks()
			print(f"\n代码块列表 (共 {len(blocks)} 个):")
			print("=" * 60)
			if not blocks:
				print("(无代码块)")
				return
			for i, blk in enumerate(blocks):
				print(f"[{i}] ", end="")
				self._print_single_block(blk, indent)
			return
		self._print_single_block(block, indent)

	def _print_single_block(self, block: Block, indent: int = 0) -> None:
		"""打印单个块及其子块"""
		indent_str = "  " * indent
		definition = self.block_defs.get_definition(block.type)
		block_name = definition.name if definition else block.type
		display_parts = [block_name]
		if block.fields:
			field_strs = []
			for field_name, field_value in block.fields.items():
				if definition and field_name in definition.fields:
					field_strs.append(f"{field_name}: {field_value}")
			if field_strs:
				display_parts.append(f"{{{', '.join(field_strs)}}}")
		block_id_short = block.id[:8] if block.id else "unknown"
		print(f"{indent_str}├─ {' '.join(display_parts)} ({block_id_short})")
		for input_name, input_block in block.inputs.items():
			if input_block:
				print(f"{indent_str}│  ├─ {input_name}:")
				self._print_single_block(input_block, indent + 2)
		for stmt_name, stmt_blocks in block.statements.items():
			if stmt_blocks:
				print(f"{indent_str}│  ├─ {stmt_name}:")
				for stmt_block in stmt_blocks:
					self._print_single_block(stmt_block, indent + 2)
		if block.next:
			print(f"{indent_str}│  └─ next:")
			self._print_single_block(block.next, indent + 2)

	# ============================================================================
	# 演示和测试方法
	# ============================================================================
	def demo_all_features(self) -> None:
		"""演示所有增强功能"""
		print("=" * 60)
		print("KN项目编辑器增强功能演示")
		print("=" * 60)
		# 1. 创建测试项目
		self.create_new_project("增强功能演示项目")
		# 2. 添加测试角色和代码
		actor_id = self.project.add_actor("测试角色", {"x": 100, "y": 100})
		self.select_actor(actor_id)
		# 添加一些代码块
		start_block = self.add_block("on_running_group_activated")
		say_block = self.add_block("self_dialog", fields={"TEXT": "你好!"})
		move_block = self.add_block("self_move_to", fields={"X": "200", "Y": "200"})
		# 连接块
		if start_block and say_block:
			start_block.next = say_block
		if say_block and move_block:
			say_block.next = move_block
		# 3. 演示块验证
		print("\n1. 块验证功能:")
		print("-" * 40)
		# 创建一个有问题的块
		bad_block = Block(type="self_move_to")
		errors = self.validate_block(bad_block)
		print(f"验证有问题的块: {len(errors)} 个错误")
		for err in errors[:3]:  # 只显示前3个错误
			print(f"  - {err}")
		# 自动修复
		fixes = self.auto_fix_block(bad_block)
		print(f"自动修复: {len(fixes)} 个修复")
		for fix in fixes[:3]:
			print(f"  - {fix}")
		# 4. 演示代码生成
		print("\n2. 代码生成功能:")
		print("-" * 40)
		python_code = self.generate_python_code(start_block)
		print("生成的Python代码:")
		print(python_code[:200] + "..." if len(python_code) > 200 else python_code)
		pseudo_code = self.generate_pseudocode(start_block)
		print("\n生成的伪代码:")
		print(pseudo_code)
		# 5. 演示批量操作
		print("\n3. 批量操作功能:")
		print("-" * 40)
		# 批量创建变量
		variables_to_create = [{"name": "分数", "value": 0}, {"name": "生命", "value": 3}, {"name": "速度", "value": 5}]
		for var in variables_to_create:
			self.project.add_variable(str(var["name"]), var["value"])
		print(f"批量创建了 {len(variables_to_create)} 个变量")
		# 复制角色
		new_actor_id = self.duplicate_actor_with_code(actor_id, "复制的角色")
		if new_actor_id:
			print(f"成功复制角色: {actor_id[:8]} -> {new_actor_id[:8]}")
		# 6. 演示错误恢复
		print("\n4. 错误恢复功能:")
		print("-" * 40)
		# 创建一个无效的引用
		if self.current_scene:
			self.current_scene.actor_ids.append("invalid_actor_id")
		# 运行错误修复
		fixes_result = self.auto_fix_project()
		for category, fix_list in fixes_result.items():
			print(f"{category}: {len(fix_list)} 个修复")
			for fix in fix_list[:2]:  # 只显示前2个
				print(f"  - {fix}")
		# 7. 演示性能优化
		print("\n5. 性能优化功能:")
		print("-" * 40)
		# 添加一些重复的块
		for _ in range(3):
			self.add_block("wait", fields={"SECONDS": "1"})
		# 运行优化
		results = self.optimize_project()
		for operation, count in results.items():
			print(f"{operation}: {count}")
		print("\n演示完成!")
		print("=" * 60)


# ============================================================================
# 辅助函数
# ============================================================================
def _is_valid_number(value: Any) -> bool:
	"""检查是否为有效数字"""
	try:
		float(str(value))

	except (ValueError, TypeError):
		return False
	else:
		return True


def _get_pseudocode_value(block: Block, input_name: str, default: str) -> str:
	"""获取伪代码中的值"""
	if block.inputs.get(input_name):
		input_block = block.inputs[input_name]
		if not input_block:
			return default
		if input_block.type == "math_number":
			return input_block.fields.get("NUM", default)
		if input_block.type == "text":
			return input_block.fields.get("TEXT", default)
	if input_name in block.fields:
		return str(block.fields[input_name])
	return default


# ============================================================================
# 块定义管理器 - 增强版
# ============================================================================
class BlockDefinitionManager:
	"""块定义管理器 - 增强版"""

	def __init__(self) -> None:
		self.definitions: dict[str, BlockDefinition] = {}
		self.categories: dict[str, list[str]] = {}
		self._initialize_definitions()

	def _initialize_definitions(self) -> None:
		"""初始化块定义 - 增强版,包含必需字段信息"""
		# 事件类
		self._add_definition(
			block_type=BlockType.ON_RUNNING_GROUP_ACTIVATED.value,
			name="当程序启动时",
			category=BlockCategory.EVENT.value,
			color="#FF7F27",
			statements=["DO"],
			can_have_next=True,
		)
		# 控制类
		self._add_definition(
			block_type=BlockType.REPEAT_FOREVER.value,
			name="重复执行",
			category=BlockCategory.CONTROL.value,
			color="#D63AFF",
			statements=["DO"],
			can_have_next=True,
		)
		self._add_definition(
			block_type=BlockType.REPEAT_N_TIMES.value,
			name="重复执行...次",
			category=BlockCategory.CONTROL.value,
			color="#D63AFF",
			fields={"TIMES": FieldType.NUMBER},
			inputs={"TIMES": BlockType.MATH_NUMBER.value},
			statements=["DO"],
			can_have_next=True,
			default_fields={"TIMES": "10"},
			required_inputs=["TIMES"],
		)
		self._add_definition(
			block_type=BlockType.WAIT.value,
			name="等待...秒",
			category=BlockCategory.CONTROL.value,
			color="#D63AFF",
			inputs={"SECONDS": BlockType.MATH_NUMBER.value},
			can_have_next=True,
			required_inputs=["SECONDS"],
		)
		self._add_definition(
			block_type=BlockType.CONTROLS_IF.value,
			name="如果...那么",
			category=BlockCategory.CONTROL.value,
			color="#FFBF00",
			inputs={"IF": BlockType.LOGIC_BOOLEAN.value},
			statements=["THEN"],
			can_have_next=True,
			required_inputs=["IF"],
		)
		# 运动类
		self._add_definition(
			block_type=BlockType.SELF_MOVE_TO.value,
			name="移动到X: Y:",
			category=BlockCategory.MOTION.value,
			color="#4C97FF",
			inputs={"X": BlockType.MATH_NUMBER.value, "Y": BlockType.MATH_NUMBER.value},
			can_have_next=True,
			required_inputs=["X", "Y"],
		)
		self._add_definition(
			block_type=BlockType.SELF_GO_FORWARD.value,
			name="移动...步",
			category=BlockCategory.MOTION.value,
			color="#4C97FF",
			inputs={"STEPS": BlockType.MATH_NUMBER.value},
			can_have_next=True,
			required_inputs=["STEPS"],
		)
		# 外观/交互类
		self._add_definition(
			block_type=BlockType.SELF_DIALOG.value,
			name="说...",
			category=BlockCategory.INTERACTION.value,
			color="#9966FF",
			inputs={"TEXT": BlockType.TEXT.value},
			can_have_next=True,
			required_inputs=["TEXT"],
		)
		self._add_definition(
			block_type=BlockType.SELF_ASK.value,
			name="询问...并等待",
			category=BlockCategory.INTERACTION.value,
			color="#9966FF",
			inputs={"QUESTION": BlockType.TEXT.value},
			can_have_next=True,
			required_inputs=["QUESTION"],
		)
		# 音频类
		self._add_definition(
			block_type=BlockType.PLAY_AUDIO.value,
			name="播放音频",
			category=BlockCategory.AUDIO.value,
			color="#D65F8A",
			fields={"AUDIO": FieldType.AUDIO},
			can_have_next=True,
			required_fields=["AUDIO"],
		)
		# 变量类
		self._add_definition(
			block_type=BlockType.VARIABLES_SET.value,
			name="将变量设为",
			category=BlockCategory.VARIABLE.value,
			color="#FF8C1A",
			fields={"VARIABLE": FieldType.VARIABLE},
			inputs={"VALUE": BlockType.MATH_NUMBER.value},
			can_have_next=True,
			required_fields=["VARIABLE"],
			required_inputs=["VALUE"],
		)
		self._add_definition(
			block_type=BlockType.CHANGE_VARIABLES.value,
			name="将变量增加",
			category=BlockCategory.VARIABLE.value,
			color="#FF8C1A",
			fields={"VARIABLE": FieldType.VARIABLE},
			inputs={"VALUE": BlockType.MATH_NUMBER.value},
			can_have_next=True,
			required_fields=["VARIABLE"],
			required_inputs=["VALUE"],
		)
		self._add_definition(
			block_type=BlockType.VARIABLES_GET.value,
			name="变量",
			category=BlockCategory.VARIABLE.value,
			color="#FF8C1A",
			fields={"VARIABLE": FieldType.VARIABLE},
			is_output=True,
			required_fields=["VARIABLE"],
		)
		# 数值类
		self._add_definition(
			block_type=BlockType.MATH_NUMBER.value,
			name="数字",
			category=BlockCategory.MATH.value,
			color="#5CB1D6",
			fields={"NUM": FieldType.NUMBER},
			is_output=True,
			default_fields={"NUM": "0"},
		)
		self._add_definition(
			block_type=BlockType.MATH_ARITHMETIC.value,
			name="算术运算",
			category=BlockCategory.MATH.value,
			color="#5CB1D6",
			fields={"OP": FieldType.ARITHMETIC},
			inputs={"A": BlockType.MATH_NUMBER.value, "B": BlockType.MATH_NUMBER.value},
			is_output=True,
			default_fields={"OP": "add"},
			required_inputs=["A", "B"],
		)
		self._add_definition(
			block_type=BlockType.RANDOM_NUM.value,
			name="在...到...之间取随机数",
			category=BlockCategory.MATH.value,
			color="#5CB1D6",
			inputs={"FROM": BlockType.MATH_NUMBER.value, "TO": BlockType.MATH_NUMBER.value},
			is_output=True,
			required_inputs=["FROM", "TO"],
		)
		# 文本类
		self._add_definition(
			block_type=BlockType.TEXT.value,
			name="文本",
			category=BlockCategory.TEXT.value,
			color="#FFD166",
			fields={"TEXT": FieldType.TEXT},
			is_output=True,
			default_fields={"TEXT": ""},
		)
		self._add_definition(
			block_type=BlockType.TEXT_JOIN.value,
			name="连接文本",
			category=BlockCategory.TEXT.value,
			color="#FFD166",
			inputs={"TEXT1": BlockType.TEXT.value, "TEXT2": BlockType.TEXT.value},
			is_output=True,
			required_inputs=["TEXT1", "TEXT2"],
		)
		# 逻辑类
		self._add_definition(
			block_type=BlockType.LOGIC_COMPARE.value,
			name="比较",
			category=BlockCategory.OPERATOR.value,
			color="#5CB1D6",
			fields={"OP": FieldType.COMPARISON},
			inputs={"A": BlockType.MATH_NUMBER.value, "B": BlockType.MATH_NUMBER.value},
			is_output=True,
			default_fields={"OP": "="},
			required_inputs=["A", "B"],
		)
		self._add_definition(
			block_type=BlockType.LOGIC_BOOLEAN.value,
			name="布尔值",
			category=BlockCategory.OPERATOR.value,
			color="#5CB1D6",
			fields={"VALUE": FieldType.BOOLEAN},
			is_output=True,
			default_fields={"VALUE": "true"},
		)
		self._add_definition(
			block_type=BlockType.LOGIC_OPERATION.value,
			name="逻辑运算",
			category=BlockCategory.OPERATOR.value,
			color="#5CB1D6",
			fields={"OP": FieldType.LOGIC},
			inputs={"A": BlockType.LOGIC_BOOLEAN.value, "B": BlockType.LOGIC_BOOLEAN.value},
			is_output=True,
			default_fields={"OP": "and"},
			required_inputs=["A", "B"],
		)
		print(f"已初始化 {len(self.definitions)} 种块定义(增强版)")

	def _add_definition(
		self,
		block_type: str,
		name: str,
		category: str,
		color: str,
		fields: dict[str, FieldType] | None = None,
		inputs: dict[str, str | list[str]] | None = None,
		statements: list[str] | None = None,
		*,
		has_shadow: bool = False,
		can_have_next: bool = False,
		is_output: bool = False,
		icon: str | None = None,
		description: str = "",
		default_fields: dict[str, Any] | None = None,
		default_inputs: dict[str, Any] | None = None,
		required_fields: list[str] | None = None,
		required_inputs: list[str] | None = None,
	) -> None:
		"""添加块定义"""
		self.definitions[block_type] = BlockDefinition(
			type=block_type,
			name=name,
			category=category,
			color=color,
			icon=icon,
			fields=fields or {},
			inputs=inputs or {},
			statements=statements or [],
			has_shadow=has_shadow,
			can_have_next=can_have_next,
			is_output=is_output,
			description=description,
			default_fields=default_fields or {},
			default_inputs=default_inputs or {},
			required_fields=required_fields or [],
			required_inputs=required_inputs or [],
		)
		if category not in self.categories:
			self.categories[category] = []
		self.categories[category].append(block_type)

	def get_definition(self, block_type: str) -> BlockDefinition | None:
		"""获取块定义"""
		return self.definitions.get(block_type)

	def get_blocks_by_category(self, category: str) -> list[BlockDefinition]:
		"""按分类获取块定义"""
		block_types = self.categories.get(category, [])
		return [self.definitions[t] for t in block_types if t in self.definitions]
