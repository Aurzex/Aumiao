import copy
import json
import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from src.core.base import BlockCategory, BlockType, EColorFormat, FieldType


# ============================================================================
# 核心数据类 - 合并两版,增强兼容性
# ============================================================================
@dataclass
class Color:
	"""颜色类"""

	r: int = 0
	g: int = 0
	b: int = 0
	a: float = 1.0

	def __init__(self, color_str: str = "#000000") -> None:
		"""从字符串初始化颜色"""
		self.set(color_str)

	def set(self, color_str: str) -> bool:
		"""设置颜色值"""
		if color_str.startswith("#"):
			hex_length = 7  # #RRGGBB
			hex_length_with_alpha = 9  # #RRGGBBAA
			if len(color_str) == hex_length:
				self.r = int(color_str[1:3], 16)
				self.g = int(color_str[3:5], 16)
				self.b = int(color_str[5:7], 16)
			elif len(color_str) == hex_length_with_alpha:
				self.r = int(color_str[1:3], 16)
				self.g = int(color_str[3:5], 16)
				self.b = int(color_str[5:7], 16)
				self.a = int(color_str[7:9], 16) / 255.0
			return True
		if color_str.startswith("rgba"):
			match = re.match(r"rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)", color_str)
			if match:
				self.r = int(match.group(1))
				self.g = int(match.group(2))
				self.b = int(match.group(3))
				self.a = float(match.group(4))
				return True
		return False

	def to_string(self) -> str:
		"""转换为字符串"""
		return f"rgba({self.r},{self.g},{self.b},{self.a})"

	def to_hex(self) -> str:
		"""转换为HEX格式"""
		return f"#{self.r:02x}{self.g:02x}{self.b:02x}"


@dataclass
class CommentJson:
	"""注释JSON结构"""

	id: str
	parent_id: str | None = None
	text: str = ""
	pinned: bool = False
	size: list[float] | None = None
	location: list[float] | None = None
	auto_layout: bool = False
	color_theme: str | None = None

	def to_dict(self) -> dict[str, Any]:
		"""转换为字典"""
		result: dict[str, Any] = {
			"id": self.id,
			"text": self.text,
			"pinned": self.pinned,
			"auto_layout": self.auto_layout,
		}
		if self.parent_id is not None:
			result["parent_id"] = self.parent_id
		if self.size is not None:
			result["size"] = self.size.copy()
		if self.location is not None:
			result["location"] = self.location.copy()
		if self.color_theme is not None:
			result["color_theme"] = self.color_theme
		return result


@dataclass
class ConnectionJson:
	"""连接JSON结构"""

	type: str
	input_type: str | None = None
	input_name: str | None = None

	def to_dict(self) -> dict[str, Any]:
		"""转换为字典"""
		result: dict[str, Any] = {"type": self.type}
		if self.input_type is not None:
			result["input_type"] = self.input_type
		if self.input_name is not None:
			result["input_name"] = self.input_name
		return result


@dataclass
class Block:
	"""代码块实例 - 增强版,合并两版优点"""

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
	# 新增字段,用于网页端解析
	field_constraints: dict[str, Any] = field(default_factory=dict)
	field_extra_attr: dict[str, Any] = field(default_factory=dict)

	def __post_init__(self) -> None:
		"""初始化后处理"""
		# 确保ID存在
		if not self.id:
			self.id = str(uuid.uuid4())
		# 确保字段存在
		if not self.fields:
			self.fields = {}
		if not self.shadows:
			self.shadows = {}
		if not self.inputs:
			self.inputs = {}
		if not self.statements:
			self.statements = {}

	def to_dict(self) -> dict[str, Any]:
		"""转换为字典 - 完全兼容网页端格式"""
		result: dict[str, Any] = {
			"type": self.type,
			"id": self.id,
			"is_shadow": self.is_shadow,
			"collapsed": self.collapsed,
			"disabled": self.disabled,
			"deletable": self.deletable,
			"movable": self.movable,
			"editable": self.editable,
			"visible": self.visible,
			"shadows": self.shadows.copy(),
			"fields": self.fields.copy(),
			"field_constraints": self.field_constraints.copy(),
			"field_extra_attr": self.field_extra_attr.copy(),
			"mutation": self.mutation,
			"is_output": self.is_output,
		}
		# 可选字段
		if self.comment is not None:
			result["comment"] = self.comment
		if self.location is not None:
			result["location"] = self.location.copy()
		if self.parent_id is not None:
			result["parent_id"] = self.parent_id
		if self.shield:
			result["shield"] = self.shield
		# 递归处理输入
		if self.inputs:
			inputs_dict: dict[str, Any] = {}
			for key, block in self.inputs.items():
				if block:
					inputs_dict[key] = block.to_dict()
			if inputs_dict:
				result["inputs"] = inputs_dict
		# 递归处理语句
		if self.statements:
			statements_dict: dict[str, Any] = {}
			for key, blocks in self.statements.items():
				if blocks:
					statements_dict[key] = blocks[0].to_dict()
			if statements_dict:
				result["statements"] = statements_dict
		# 处理下一个块
		if self.next:
			result["next"] = self.next.to_dict()
		return result

	@classmethod
	def from_dict(cls, data: dict[str, Any]) -> "Block":
		"""从字典创建块"""
		block = cls(
			id=data.get("id", str(uuid.uuid4())),
			type=data.get("type", ""),
			fields=data.get("fields", {}),
			shadows=data.get("shadows", {}),
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
			field_constraints=data.get("field_constraints", {}),
			field_extra_attr=data.get("field_extra_attr", {}),
		)
		# 递归创建输入块
		if "inputs" in data:
			for key, input_data in data["inputs"].items():
				if input_data and isinstance(input_data, dict):
					block.inputs[key] = cls.from_dict(input_data)
		# 递归创建语句块
		if "statements" in data:
			for key, statement_data in data["statements"].items():
				if statement_data and isinstance(statement_data, dict):
					block.statements[key] = [cls.from_dict(statement_data)]
		# 处理下一个块
		if data.get("next"):
			block.next = cls.from_dict(data["next"])
		return block

	def get_all_blocks(self) -> Sequence["Block"]:
		"""获取此块及其所有子块"""
		blocks: list[Block] = []
		visited: set[str] = set()
		stack: list[Block] = [self]
		while stack:
			current = stack.pop()
			if current.id in visited:
				continue
			visited.add(current.id)
			blocks.append(current)
			# 添加输入块到栈
			stack.extend(input_block for input_block in current.inputs.values() if input_block and input_block.id not in visited)
			# 添加语句块到栈
			for statement_blocks in current.statements.values():
				stack.extend(block for block in statement_blocks if block.id not in visited)
			# 添加下一个块到栈
			if current.next and current.next.id not in visited:
				stack.append(current.next)
		return blocks

	def find_block(self, block_id: str) -> Optional["Block"]:
		"""查找指定ID的块"""
		for block in self.get_all_blocks():
			if block.id == block_id:
				return block
		return None

	def fix_for_web(self) -> None:
		"""修复块以支持网页端解析"""
		# 确保必需字段存在
		if self.type == BlockType.PROCEDURES_CALLNORETURN.value and ("PROCEDURE" not in self.fields or not self.fields["PROCEDURE"]):
			self.fields["PROCEDURE"] = f"procedure_{self.id[:8]}"
		# 确保mutation存在(对于过程块)
		if self.type in {BlockType.PROCEDURES_CALLNORETURN.value, BlockType.PROCEDURES_CALLRETURN.value} and not self.mutation:
			self._create_default_mutation()
		# 确保输入不为空
		for input_name, input_block in self.inputs.items():
			if input_block is None:
				self.inputs[input_name] = self._create_default_input_block(input_name)

	def _create_default_mutation(self) -> None:
		"""创建默认mutation"""
		if self.type in {BlockType.PROCEDURES_CALLNORETURN.value, BlockType.PROCEDURES_CALLRETURN.value}:
			proc_name = self.fields.get("PROCEDURE", f"procedure_{self.id[:8]}")
			self.mutation = f'<mutation name="{proc_name}" def_id=""></mutation>'

	@staticmethod
	def _create_default_input_block(input_name: str) -> Optional["Block"]:
		"""创建默认输入块"""
		if "SECONDS" in input_name or "TIME" in input_name:
			return Block(type=BlockType.MATH_NUMBER.value, fields={"NUM": "1"}, is_output=True)
		if "VALUE" in input_name:
			return Block(type=BlockType.MATH_NUMBER.value, fields={"NUM": "0"}, is_output=True)
		if "CONDITION" in input_name or "IF" in input_name:
			return Block(type=BlockType.LOGIC_BOOLEAN.value, fields={"VALUE": "true"}, is_output=True)
		return None


@dataclass
class Actor:
	"""角色 - 增强版"""

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
	image_resources: list[str] = field(default_factory=list)
	neko_block_json_list: list[dict] = field(default_factory=list)

	def __post_init__(self) -> None:
		"""初始化后处理"""
		if not self.neko_block_json_list and self.blocks:
			self.neko_block_json_list = [block.to_dict() for block in self.blocks]

	def to_dict(self) -> dict[str, Any]:
		"""转换为字典"""
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
		"""从字典创建角色"""
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
		# 加载块
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
	"""场景 - 增强版"""

	id: str
	name: str
	screen_name: str = "屏幕"
	styles: list[str] = field(default_factory=list)
	actor_ids: list[str] = field(default_factory=list)
	visible: bool = True
	current_style_id: str = ""
	blocks: list[Block] = field(default_factory=list)
	background_color: str = "#FFFFFF"
	background_image: str | None = None
	neko_block_json_list: list[dict] = field(default_factory=list)

	def __post_init__(self) -> None:
		"""初始化后处理"""
		if not self.neko_block_json_list and self.blocks:
			self.neko_block_json_list = [block.to_dict() for block in self.blocks]

	def to_dict(self) -> dict[str, Any]:
		"""转换为字典"""
		result: dict[str, Any] = {
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
		if self.background_image is not None:
			result["backgroundImage"] = self.background_image
		return result

	@classmethod
	def from_dict(cls, data: dict[str, Any]) -> "Scene":
		"""从字典创建场景"""
		scene = cls(
			id=data["id"],
			name=data.get("name", ""),
			screen_name=data.get("screenName", "屏幕"),
			styles=data.get("styles", []),
			actor_ids=data.get("actorIds", []),
			visible=data.get("visible", True),
			current_style_id=data.get("currentStyleId", ""),
			background_color=data.get("backgroundColor", "#FFFFFF"),
			background_image=data.get("backgroundImage"),
		)
		# 加载块
		blocks_data = data.get("nekoBlockJsonList", [])
		scene.blocks = [Block.from_dict(block_data) for block_data in blocks_data]
		return scene


@dataclass
class WorkspaceData:
	"""工作区数据 ,增强兼容性"""

	blocks: dict[str, Block] = field(default_factory=dict)
	comments: dict[str, CommentJson] = field(default_factory=dict)
	connections: dict[str, dict[str, ConnectionJson]] = field(default_factory=dict)

	def to_dict(self) -> dict[str, Any]:
		"""转换为字典"""
		return {
			"blocks": {bid: block.to_dict() for bid, block in self.blocks.items()},
			"comments": {cid: comment.to_dict() for cid, comment in self.comments.items()},
			"connections": {bid: {target_id: conn.to_dict() for target_id, conn in target_conns.items()} for bid, target_conns in self.connections.items()},
		}

	@classmethod
	def from_dict(cls, data: dict[str, Any]) -> "WorkspaceData":
		"""从字典创建工作区数据"""
		ws = cls()
		# 加载块
		for block_id, block_data in data.get("blocks", {}).items():
			ws.blocks[block_id] = Block.from_dict(block_data)
		# 加载注释
		for comment_id, comment_data in data.get("comments", {}).items():
			ws.comments[comment_id] = CommentJson(**comment_data)
		# 加载连接
		for block_id, target_conns in data.get("connections", {}).items():
			ws.connections[block_id] = {}
			for target_id, conn_data in target_conns.items():
				ws.connections[block_id][target_id] = ConnectionJson(**conn_data)
		return ws

	def add_block(self, block: Block) -> None:
		"""添加块"""
		self.blocks[block.id] = block

	def add_comment(self, comment: CommentJson) -> None:
		"""添加注释"""
		self.comments[comment.id] = comment

	def connect_blocks(self, source_id: str, target_id: str, conn_type: str, input_name: str | None = None) -> None:
		"""连接两个块"""
		if source_id not in self.connections:
			self.connections[source_id] = {}
		conn = ConnectionJson(type=conn_type)
		if conn_type == "input":
			conn.input_type = "value"
			conn.input_name = input_name
		self.connections[source_id][target_id] = conn


# ============================================================================
# KN项目核心类 - 完整重构版
# ============================================================================
class KNProject:
	"""KN项目 - 完整重构版,合并两版优点"""

	def __init__(self, project_name: str = "未命名项目") -> None:
		self.project_name = project_name
		self.version = "0.20.0"
		self.tool_type = "KN"
		# 核心数据
		self.scenes: dict[str, Scene] = {}
		self.current_scene_id: str = ""
		self.sort_list: list[str] = []
		self.actors: dict[str, Actor] = {}
		# 资源数据 - 合并两版
		self.styles: dict[str, Any] = {}
		self.variables: dict[str, Any] = {}
		self.lists: dict[str, Any] = {}
		self.broadcasts: dict[str, Any] = {}
		self.audios: dict[str, Any] = {}
		self.procedures: dict[str, Any] = {}
		# 工作区数据
		self.workspace = WorkspaceData()
		# 其他设置
		self.stage_size = {"width": 900, "height": 562}
		self.timer_position = {"x": 720, "y": 12}
		self.filepath: Path | None = None
		self.resources: dict[str, Any] = {}
		self.project_folder: Path | None = None

	@classmethod
	def load_from_file(cls, filepath: str | Path) -> "KNProject":
		"""从文件加载项目"""
		filepath = Path(filepath)
		with filepath.open("r", encoding="utf-8") as f:
			data = json.load(f)
		project = cls.load_from_dict(data)
		project.filepath = filepath
		project.project_folder = filepath.parent
		return project

	@classmethod
	def load_from_dict(cls, data: dict[str, Any]) -> "KNProject":
		"""从字典创建项目"""
		project = cls(data.get("projectName", "未命名项目"))
		# 基础信息
		project.version = data.get("version", "0.20.0")
		project.tool_type = data.get("toolType", "KN")
		project.stage_size = data.get("stageSize", {"width": 900, "height": 562})
		project.timer_position = data.get("timerPosition", {"x": 720, "y": 12})
		# 资源
		project.styles = data.get("styles", {}).get("stylesDict", {})
		project.variables = data.get("variables", {}).get("variablesDict", {})
		project.lists = data.get("lists", {}).get("listsDict", {})
		project.broadcasts = data.get("broadcasts", {}).get("broadcastsDict", {})
		project.audios = data.get("audios", {}).get("audiosDict", {})
		project.procedures = data.get("procedures", {}).get("proceduresDict", {})
		# 场景
		scenes_data = data.get("scenes", {})
		scenes_dict = scenes_data.get("scenesDict", {})
		for scene_id, scene_data in scenes_dict.items():
			project.scenes[scene_id] = Scene.from_dict(scene_data)
		project.current_scene_id = scenes_data.get("currentSceneId", "")
		project.sort_list = scenes_data.get("sortList", [])
		# 角色
		actors_dict = data.get("actors", {}).get("actorsDict", {})
		for actor_id, actor_data in actors_dict.items():
			project.actors[actor_id] = Actor.from_dict(actor_data)
		# 工作区数据
		if "blocks" in data or "connections" in data or "comments" in data:
			project.workspace = WorkspaceData.from_dict(data)
		else:
			# 如果没有独立的工作区数据,从场景和角色中收集块
			project._collect_blocks_to_workspace()
		return project

	def _collect_blocks_to_workspace(self) -> None:
		"""从场景和角色中收集块到工作区"""
		# 清空工作区
		self.workspace = WorkspaceData()
		# 收集场景的块
		for scene in self.scenes.values():
			for block in scene.blocks:
				self.workspace.add_block(block)
		# 收集角色的块
		for actor in self.actors.values():
			for block in actor.blocks:
				self.workspace.add_block(block)
		# TODO: 收集连接信息(需要从块结构中解析)

	def to_dict(self) -> dict[str, Any]:
		"""转换为完整项目JSON - 完全匹配网页端格式"""
		# 构建项目数据结构
		project_dict: dict[str, Any] = {
			"projectName": self.project_name,
			"version": self.version,
			"toolType": self.tool_type,
			"stageSize": self.stage_size,
			"timerPosition": self.timer_position,
			# 资源部分
			"styles": {"stylesDict": self.styles},
			"variables": {"variablesDict": self.variables},
			"lists": {"listsDict": self.lists},
			"broadcasts": {"broadcastsDict": self.broadcasts},
			"audios": {"audiosDict": self.audios},
			"procedures": {"proceduresDict": self.procedures},
			# 场景部分
			"scenes": {
				"scenesDict": {scene_id: scene.to_dict() for scene_id, scene in self.scenes.items()},
				"currentSceneId": self.current_scene_id,
				"sortList": self.sort_list.copy(),
			},
			# 角色部分
			"actors": {"actorsDict": {actor_id: actor.to_dict() for actor_id, actor in self.actors.items()}},
		}
		# 添加工作区数据
		workspace_dict = self.workspace.to_dict()
		project_dict.update(workspace_dict)
		return project_dict

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
		print(f"项目已保存: {filepath}")

	def create_simple_project(self) -> None:
		"""创建简单示例项目"""
		# 添加默认变量
		var_id = str(uuid.uuid4())
		self.variables[var_id] = {"id": var_id, "name": "我的变量", "value": 0, "isGlobal": True}
		# 添加默认音频
		audio_id = str(uuid.uuid4())
		self.audios[audio_id] = {"id": audio_id, "name": "音频1", "audioUrl": "", "volume": 100}
		# 添加默认样式
		style_id = str(uuid.uuid4())
		self.styles[style_id] = {"id": style_id, "name": "样式1"}
		# 添加默认角色
		actor_id = str(uuid.uuid4())
		self.actors[actor_id] = Actor(
			id=actor_id,
			name="角色1",
			position={"x": 0, "y": 0},
			scale=100.0,
			rotation=0.0,
			visible=True,
			locked=False,
			draggable=True,
			rotation_type="all around",
			styles=[],
			current_style_id="",
		)
		# 添加默认场景
		scene_id = str(uuid.uuid4())
		self.scenes[scene_id] = Scene(
			id=scene_id,
			name="场景1",
			screen_name="屏幕",
			styles=[],
			actor_ids=[actor_id],
			visible=True,
			current_style_id="",
			background_color="#FFFFFF",
		)
		self.current_scene_id = scene_id
		self.sort_list = [scene_id]
		print(f"创建了简单项目: {self.project_name}")

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

	def add_block_to_actor(self, actor_id: str, block: Block) -> bool:
		"""添加块到角色"""
		if actor_id not in self.actors:
			return False
		# 添加到角色
		self.actors[actor_id].blocks.append(block)
		# 同时添加到工作区
		self.workspace.add_block(block)
		return True

	def add_block_to_scene(self, scene_id: str, block: Block) -> bool:
		"""添加块到场景"""
		if scene_id not in self.scenes:
			return False
		# 添加到场景
		self.scenes[scene_id].blocks.append(block)
		# 同时添加到工作区
		self.workspace.add_block(block)
		return True

	def get_all_blocks(self) -> list[Block]:
		"""获取项目中所有块"""
		all_blocks: list[Block] = []
		visited: set[str] = set()
		# 收集所有起始块
		stack: list[Block] = []
		# 场景的块
		for scene in self.scenes.values():
			stack.extend(scene.blocks)
		# 角色的块
		for actor in self.actors.values():
			stack.extend(actor.blocks)
		# 工作区的块
		stack.extend(self.workspace.blocks.values())
		# 迭代遍历
		while stack:
			block = stack.pop()
			if block.id in visited:
				continue
			visited.add(block.id)
			all_blocks.append(block)
			# 递归处理输入
			stack.extend(input_block for input_block in block.inputs.values() if input_block and input_block.id not in visited)
			# 递归处理语句
			for stmt_blocks in block.statements.values():
				stack.extend(stmt_block for stmt_block in stmt_blocks if stmt_block.id not in visited)
			# 处理下一个块
			if block.next and block.next.id not in visited:
				stack.append(block.next)
		return all_blocks

	def find_block(self, block_id: str) -> Block | None:
		"""在项目中查找代码块"""
		for block in self.get_all_blocks():
			if block.id == block_id:
				return block
		return None

	def fix_for_web(self) -> None:
		"""修复项目以支持网页端解析"""
		print("开始修复项目以支持网页端解析...")
		# 修复所有块
		all_blocks = self.get_all_blocks()
		for block in all_blocks:
			block.fix_for_web()
		# 确保有必要的资源
		if not self.variables:
			self.add_variable("变量1", 0)
			print("添加默认变量")
		if not self.audios:
			audio_id = str(uuid.uuid4())
			self.audios[audio_id] = {"id": audio_id, "name": "音频1", "audioUrl": "", "volume": 100}
			print("添加默认音频")
		if not self.styles:
			style_id = str(uuid.uuid4())
			self.styles[style_id] = {"id": style_id, "name": "样式1"}
			print("添加默认样式")
		print("项目修复完成!")


# ============================================================================
# 积木块构建器 ,增强兼容性
# ============================================================================
class BlockBuilder:
	"""积木块构建器 - 辅助创建符合JavaScript结构的积木块"""

	@staticmethod
	def create_number_block(value: float, block_id: str | None = None) -> Block:
		"""创建数字块"""
		if block_id is None:
			block_id = f"math_number_{uuid.uuid4().hex[:8]}"
		return Block(
			type=BlockType.MATH_NUMBER.value,
			id=block_id,
			fields={"NUM": str(value)},
			is_output=True,
			editable=True,
		)

	@staticmethod
	def create_text_block(text: str, block_id: str | None = None) -> Block:
		"""创建文本块"""
		if block_id is None:
			block_id = f"text_{uuid.uuid4().hex[:8]}"
		return Block(type=BlockType.TEXT.value, id=block_id, fields={"TEXT": text}, is_output=True, editable=True)

	@staticmethod
	def create_boolean_block(*, value: bool, block_id: str | None = None) -> Block:
		"""创建布尔值块"""
		if block_id is None:
			block_id = f"logic_boolean_{uuid.uuid4().hex[:8]}"
		bool_value = "TRUE" if value else "FALSE"
		return Block(
			type=BlockType.LOGIC_BOOLEAN.value,
			id=block_id,
			fields={"BOOL": bool_value},
			is_output=True,
			editable=True,
		)

	@staticmethod
	def create_variable_get(variable_name: str, block_id: str | None = None) -> Block:
		"""创建获取变量块"""
		if block_id is None:
			block_id = f"variables_get_{uuid.uuid4().hex[:8]}"
		return Block(
			type=BlockType.VARIABLES_GET.value,
			id=block_id,
			fields={"VAR": variable_name},
			is_output=True,
			editable=True,
		)

	@staticmethod
	def create_variable_set(variable_name: str, value: Any, block_id: str | None = None) -> Block:
		"""创建设置变量块"""
		if block_id is None:
			block_id = f"variables_set_{uuid.uuid4().hex[:8]}"
		# 创建值块
		if isinstance(value, (int, float)):
			value_block = BlockBuilder.create_number_block(value)
		elif isinstance(value, str):
			value_block = BlockBuilder.create_text_block(value)
		else:
			value_block = BlockBuilder.create_text_block(str(value))
		# 创建设置块
		block = Block(
			type=BlockType.VARIABLES_SET.value,
			id=block_id,
			fields={"VAR": variable_name},
			shadows={"VALUE": f'<shadow type="math_number"><field name="NUM">{value}</field></shadow>'},
			editable=True,
		)
		block.inputs["VALUE"] = value_block
		return block

	@staticmethod
	def create_color_picker(
		color_hex: str = "#E8308C",
		format_: EColorFormat = EColorFormat.ColorPalette,
		block_id: str | None = None,
	) -> Block:
		"""创建颜色选择器块"""
		if block_id is None:
			block_id = f"color_picker_{uuid.uuid4().hex[:8]}"
		# 根据格式创建不同的块结构
		fields = {"COLOR_PALETTE": color_hex} if format_ == EColorFormat.ColorPalette else {}
		mutation = f'<mutation format="{format_.value}" color="{color_hex}"></mutation>'
		return Block(
			type=BlockType.COLOR_PICKER.value,
			id=block_id,
			fields=fields,
			mutation=mutation,
			is_output=True,
			editable=True,
		)

	@staticmethod
	def create_controls_if(
		condition: Block | None = None,
		then_blocks: list[Block] | None = None,
		else_if_count: int = 0,
		else_count: int = 0,
		block_id: str | None = None,
	) -> Block:
		"""创建条件判断块"""
		if block_id is None:
			block_id = f"controls_if_{uuid.uuid4().hex[:8]}"
		# 创建mutation
		mutation = "<mutation"
		if else_if_count > 0:
			mutation += f' elseif="{else_if_count}"'
		if else_count > 0:
			mutation += ' else="1"'
		mutation += "></mutation>"
		# 创建默认条件
		if condition is None:
			condition = BlockBuilder.create_boolean_block(value=True)
		block = Block(type=BlockType.CONTROLS_IF.value, id=block_id, mutation=mutation, editable=True)
		if condition:
			block.inputs["IF"] = condition
		if then_blocks:
			block.statements["THEN"] = then_blocks
		return block

	@staticmethod
	def create_procedure_call(procedure_name: str, *, has_return: bool = False, block_id: str | None = None) -> Block:
		"""创建过程调用块"""
		block_type = BlockType.PROCEDURES_CALLRETURN.value if has_return else BlockType.PROCEDURES_CALLNORETURN.value
		if block_id is None:
			block_id = f"{block_type}_{uuid.uuid4().hex[:8]}"
		mutation = f'<mutation name="{procedure_name}" def_id=""></mutation>'
		return Block(
			type=block_type,
			id=block_id,
			fields={"PROCEDURE": procedure_name},
			mutation=mutation,
			is_output=has_return,
			editable=True,
		)


# ============================================================================
# 块定义管理器
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


class BlockDefinitionManager:
	"""块定义管理器"""

	def __init__(self) -> None:
		self.definitions: dict[str, BlockDefinition] = {}
		self.categories: dict[str, list[str]] = {}
		self._initialize_definitions()

	def _initialize_definitions(self) -> None:
		"""初始化块定义"""
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
		# 外观类
		self._add_definition(
			block_type=BlockType.SELF_APPEAR.value,
			name="显示/隐藏",
			category=BlockCategory.APPEARANCE.value,
			color="#FF66CC",
			fields={"STATE": FieldType.BOOLEAN},
			can_have_next=True,
			default_fields={"STATE": "true"},
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
		print(f"已初始化 {len(self.definitions)} 种块定义")

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


# ============================================================================
# JSON转换工具类 ,增强版
# ============================================================================
class JsonConverter:
	"""JSON转换工具 - 处理JavaScript和Python之间的转换"""

	@staticmethod
	def block_to_json(block_dict: dict[str, Any]) -> dict[str, Any]:
		"""转换块数据到JavaScript兼容格式"""
		result: dict[str, Any] = {
			"type": block_dict.get("type", ""),
			"id": block_dict.get("id", str(uuid.uuid4())),
			"comment": block_dict.get("comment"),
			"is_shadow": block_dict.get("is_shadow", False),
			"collapsed": block_dict.get("collapsed", False),
			"disabled": block_dict.get("disabled", False),
			"deletable": block_dict.get("deletable", True),
			"movable": block_dict.get("movable", True),
			"editable": block_dict.get("editable", True),
			"visible": block_dict.get("visible", "visible"),
			"shadows": block_dict.get("shadows", {}),
			"fields": block_dict.get("fields", {}),
			"field_constraints": block_dict.get("field_constraints", {}),
			"field_extra_attr": block_dict.get("field_extra_attr", {}),
			"mutation": block_dict.get("mutation", ""),
			"is_output": block_dict.get("is_output", False),
			"parent_id": block_dict.get("parent_id"),
		}
		# 处理位置
		if "location" in block_dict:
			result["location"] = block_dict["location"]
		return result

	@staticmethod
	def comment_to_json(comment_dict: dict[str, Any]) -> dict[str, Any]:
		"""转换注释数据到JavaScript兼容格式"""
		result: dict[str, Any] = {
			"id": comment_dict.get("id", str(uuid.uuid4())),
			"parent_id": comment_dict.get("parent_id"),
			"text": comment_dict.get("text", ""),
			"pinned": comment_dict.get("pinned", False),
			"auto_layout": comment_dict.get("auto_layout", False),
		}
		# 处理可选字段
		if "size" in comment_dict:
			result["size"] = comment_dict["size"]
		if "location" in comment_dict:
			result["location"] = comment_dict["location"]
		if "color_theme" in comment_dict:
			result["color_theme"] = comment_dict["color_theme"]
		return result

	@staticmethod
	def workspace_to_json(workspace_data: WorkspaceData) -> dict[str, Any]:
		"""转换工作区数据到JavaScript兼容格式"""
		return workspace_data.to_dict()

	@staticmethod
	def fix_for_web(project_dict: dict[str, Any]) -> dict[str, Any]:
		"""修复项目数据以支持网页端解析"""
		fixed_dict = copy.deepcopy(project_dict)
		# 确保必需的资源存在
		if not fixed_dict.get("variables", {}).get("variablesDict"):
			fixed_dict.setdefault("variables", {})["variablesDict"] = {str(uuid.uuid4()): {"id": str(uuid.uuid4()), "name": "变量1", "value": 0, "isGlobal": True}}
		if not fixed_dict.get("audios", {}).get("audiosDict"):
			fixed_dict.setdefault("audios", {})["audiosDict"] = {str(uuid.uuid4()): {"id": str(uuid.uuid4()), "name": "音频1", "audioUrl": "", "volume": 100}}
		if not fixed_dict.get("styles", {}).get("stylesDict"):
			fixed_dict.setdefault("styles", {})["stylesDict"] = {str(uuid.uuid4()): {"id": str(uuid.uuid4()), "name": "样式1"}}
		# 确保所有块都有正确的结构
		if "blocks" in fixed_dict:
			for block_id, block_data in list(fixed_dict["blocks"].items()):
				# 确保必需字段存在
				if "type" not in block_data:
					block_data["type"] = "unknown"
				if "id" not in block_data:
					block_data["id"] = block_id
				# 确保字段字典存在
				if "fields" not in block_data:
					block_data["fields"] = {}
				if "shadows" not in block_data:
					block_data["shadows"] = {}
				if "field_constraints" not in block_data:
					block_data["field_constraints"] = {}
				if "field_extra_attr" not in block_data:
					block_data["field_extra_attr"] = {}
		return fixed_dict


# ============================================================================
# 验证工具类 - 合并两版
# ============================================================================
class ProjectValidator:
	"""项目验证工具"""

	@staticmethod
	def validate_project(project: KNProject) -> dict[str, list[str]]:
		"""验证项目完整性"""
		issues: dict[str, list[str]] = {}
		# 1. 验证块结构
		for block_id, block in project.workspace.blocks.items():
			block_issues = []
			# 检查必需字段
			if not block.type:
				block_issues.append("缺少类型(type)")
			if not block.id:
				block_issues.append("缺少ID")
			# 检查字段约束
			for field_name, constraints in block.field_constraints.items():
				if "min" not in constraints or "max" not in constraints:
					block_issues.append(f"字段 {field_name} 约束不完整")
			if block_issues:
				issues[f"块 {block_id[:8]} ({block.type})"] = block_issues
		# 2. 验证引用
		# 检查变量引用
		for var_id in project.variables:
			var_refs = ProjectValidator._find_variable_references(project, var_id)
			if not var_refs:
				issues.setdefault("未使用的变量", []).append(var_id)
		# 3. 验证场景-角色引用
		for scene_id, scene in project.scenes.items():
			for actor_id in scene.actor_ids:
				if actor_id not in project.actors:
					issues.setdefault("无效的角色引用", []).append(f"场景 {scene.name if hasattr(scene, 'name') else scene_id}: 引用不存在的角色 {actor_id}")
		return issues

	@staticmethod
	def _find_variable_references(project: KNProject, var_id: str) -> list[str]:
		"""查找变量引用"""
		refs: list[str] = []
		# 在工作区块中查找
		for block_id, block in project.workspace.blocks.items():
			for field_name, field_value in block.fields.items():
				if field_value == var_id:
					refs.append(f"块 {block_id[:8]}: 字段 {field_name}")
		# 在角色块中查找
		for actor in project.actors.values():
			for block in actor.blocks:
				for field_name, field_value in block.fields.items():
					if field_value == var_id:
						refs.append(f"角色 {actor.name}: {field_name}")
		return refs

	@staticmethod
	def auto_fix_project(project: KNProject) -> dict[str, int]:
		"""自动修复项目问题"""
		fixes: dict[str, int] = {
			"修复孤儿块": 0,
			"修复重复ID": 0,
			"修复缺失字段": 0,
		}
		# 修复重复ID
		seen_ids: set[str] = set()
		for block_id in list(project.workspace.blocks.keys()):
			if block_id in seen_ids:
				# 生成新ID
				new_id = str(uuid.uuid4())
				project.workspace.blocks[new_id] = project.workspace.blocks.pop(block_id)
				project.workspace.blocks[new_id].id = new_id
				fixes["修复重复ID"] += 1
			seen_ids.add(block_id)
		# 修复缺失字段
		for block in project.workspace.blocks.values():
			if not hasattr(block, "fields"):
				block.fields = {}
				fixes["修复缺失字段"] += 1
			if not hasattr(block, "shadows"):
				block.shadows = {}
				fixes["修复缺失字段"] += 1
		return fixes


# ============================================================================
# KN项目编辑器 - 完整增强版
# ============================================================================
class KNEditor:
	"""KN项目编辑器核心类 - 完整增强版"""

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
		self.project.create_simple_project()
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

	def validate_block(self, block: Block) -> list[str]:
		"""验证块的完整性"""
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
		return errors

	def validate_project(self) -> dict[str, list[str]]:
		"""验证整个项目"""
		return ProjectValidator.validate_project(self.project)

	def generate_python_code(self, block: Block | None = None, indent: int = 0) -> str:  # noqa: PLR0911
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
		if block.type == BlockType.ON_RUNNING_GROUP_ACTIVATED.value:
			code = f"{indent_str}# 当程序启动时\n"
			if block.next:
				code += self.generate_python_code(block.next, indent)
			return code
		if block.type == BlockType.SELF_DIALOG.value:
			text = block.fields.get("TEXT", "")
			code = f'{indent_str}print("{text}")\n'
			if block.next:
				code += self.generate_python_code(block.next, indent)
			return code
		if block.type == BlockType.SELF_MOVE_TO.value:
			x = self._get_input_value(block, "X", "0")
			y = self._get_input_value(block, "Y", "0")
			code = f"{indent_str}move_to({x}, {y})\n"
			if block.next:
				code += self.generate_python_code(block.next, indent)
			return code
		# 默认处理
		code = f"{indent_str}# {definition.name}\n"
		if block.fields:
			for field_name, field_value in block.fields.items():
				code += f"{indent_str}#   {field_name}: {field_value}\n"
		if block.next:
			code += self.generate_python_code(block.next, indent)
		return code

	def _get_input_value(self, block: Block, input_name: str, default: str) -> str:
		"""获取输入块的值"""
		if input_block := block.inputs.get(input_name):
			if input_block.type == BlockType.MATH_NUMBER.value:
				return input_block.fields.get("NUM", default)
			if input_block.type == BlockType.TEXT.value:
				return f'"{input_block.fields.get("TEXT", default)}"'
			if input_block.type == BlockType.VARIABLES_GET.value:
				return input_block.fields.get("VARIABLE", default)
		# 尝试从字段获取
		if input_name in block.fields:
			value = block.fields[input_name]
			if self._is_valid_number(value):
				return str(value)
		return default

	@staticmethod
	def _is_valid_number(value: Any) -> bool:
		"""检查是否为有效数字"""
		try:
			float(str(value))
		except (ValueError, TypeError):
			return False
		else:
			return True

	def add_block(self, block_type: str, location: tuple[float, float] | None = None, fields: dict[str, Any] | None = None) -> Block | None:
		"""添加新代码块"""
		definition = self.block_defs.get_definition(block_type)
		if not definition:
			print(f"未知的块类型: {block_type}")
			return None
		new_block = Block(type=block_type)
		# 设置默认字段
		for field_name, field_value in definition.default_fields.items():
			new_block.fields[field_name] = field_value
		# 设置自定义字段
		if fields:
			for field_name, field_value in fields.items():
				if field_name in definition.fields:
					new_block.fields[field_name] = field_value
		# 设置位置
		if location:
			new_block.location = list(location)
		# 添加到当前实体
		_, entity = self.get_current_entity()
		if entity:
			entity.blocks.append(new_block)
			self.selected_block = new_block
			return new_block
		return None

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


# ============================================================================
# 辅助函数
# ============================================================================


def create_demo_project() -> KNProject:
	"""创建演示项目"""
	project = KNProject("演示项目")
	project.create_simple_project()
	# 获取第一个角色和场景
	first_actor_id = next(iter(project.actors.keys()))
	first_scene_id = next(iter(project.scenes.keys()))
	# 创建一些示例块
	builder = BlockBuilder()
	# 1. 创建开始事件块
	start_block = Block(type=BlockType.ON_RUNNING_GROUP_ACTIVATED.value, id="start_event_1", location=[100, 100])
	project.add_block_to_scene(first_scene_id, start_block)
	# 2. 创建说话块
	say_block = Block(type=BlockType.SELF_DIALOG.value, id="say_block_1", fields={"TEXT": "你好,世界!"}, location=[100, 150])
	project.add_block_to_actor(first_actor_id, say_block)
	# 3. 连接块
	project.workspace.connect_blocks(source_id=start_block.id, target_id=say_block.id, conn_type="next")
	# 4. 创建变量块
	var_get_block = builder.create_variable_get("我的变量")
	project.add_block_to_actor(first_actor_id, var_get_block)
	# 5. 创建颜色选择器
	color_block = builder.create_color_picker("#FF5733")
	project.add_block_to_actor(first_actor_id, color_block)
	# 验证项目
	issues = ProjectValidator.validate_project(project)
	if issues:
		print("项目验证发现问题:")
		for category, issue_list in issues.items():
			print(f"  {category}:")
			for issue in issue_list[:3]:
				print(f"    - {issue}")
	# 自动修复
	fixes = ProjectValidator.auto_fix_project(project)
	if fixes:
		print("自动修复结果:")
		for fix_type, count in fixes.items():
			if count > 0:
				print(f"  {fix_type}: {count}处")
	return project


def open_existing_project_for_editing(filepath: str | Path) -> tuple[KNEditor, bool]:
	"""
	打开已有作品进行编辑
	参数:
		filepath: 项目文件路径(.kn格式)
	返回:
		tuple[KNEditor, bool]: (编辑器实例, 是否成功加载)
	"""
	editor = KNEditor()
	try:
		# 1. 加载项目文件
		editor.load_project(filepath)
		# 2. 修复项目以支持网页端
		editor.project.fix_for_web()
		# 3. 自动验证项目完整性
		validation_results = editor.validate_project()
		if validation_results:
			print("项目验证发现以下问题:")
			for category, errors in validation_results.items():
				print(f"\n{category}:")
				for error in errors[:5]:
					print(f"  - {error}")
				if len(errors) > 5:  # noqa: PLR2004
					print(f"  还有 {len(errors) - 5} 个问题...")
		# 4. 创建备份
		if editor.project.filepath:
			backup_folder = editor.project.filepath.parent / "backups"
			backup_folder.mkdir(parents=True, exist_ok=True)
			timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # noqa: DTZ005
			backup_file = backup_folder / f"{editor.project.project_name}_{timestamp}.kn.backup"
			editor.project.save_to_file(backup_file)
			print(f"\n已创建项目备份: {backup_file}")
		# 5. 自动选择默认编辑对象
		if editor.project.scenes:
			# 选择第一个场景
			first_scene_id = next(iter(editor.project.scenes.keys()))
			editor.select_scene(first_scene_id)
			print(f"已选择场景: {editor.current_scene.name if editor.current_scene else first_scene_id}")
		# 6. 显示项目信息
		print("\n项目信息:")
		print(f"  名称: {editor.project.project_name}")
		print(f"  版本: {editor.project.version}")
		print(f"  场景数: {len(editor.project.scenes)}")
		print(f"  角色数: {len(editor.project.actors)}")
		total_blocks = len(editor.project.get_all_blocks())
		print(f"  总代码块数: {total_blocks}")
	except FileNotFoundError:
		print(f"错误: 找不到文件 {filepath}")
		return editor, False
	except json.JSONDecodeError as e:
		print(f"错误: 文件格式错误 - {e}")
		return editor, False
	except Exception as e:
		print(f"错误: 加载项目失败 - {e}")
		return editor, False
	else:
		return editor, True
