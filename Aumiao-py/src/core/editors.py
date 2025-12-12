from __future__ import annotations

import contextlib
import html  # 将import移到顶部
import json
import operator
import re
import uuid
import xml.etree.ElementTree as ET  # noqa: S405
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar, cast

from src.core.base import BlockCategory, BlockType, ColorFormat, ConnectionType, ShadowCategory, ShadowType

T = TypeVar("T")
U = TypeVar("U")


class TypeChecker:
	"""类型检查工具"""

	@staticmethod
	def is_valid_color(color_str: str) -> bool:  # noqa: PLR0911
		"""检查是否为有效颜色字符串"""
		if not color_str:
			return False
		# 检查HEX格式
		if color_str.startswith("#"):
			hex_part = color_str[1:]
			return len(hex_part) in {3, 4, 6, 8} and all(c in "0123456789ABCDEFabcdef" for c in hex_part)
		# 检查RGBA格式
		if color_str.startswith("rgba("):
			match = re.match(r"rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)", color_str)
			if match:
				try:
					r, g, b, a = match.groups()
					return 0 <= int(r) <= 255 and 0 <= int(g) <= 255 and 0 <= int(b) <= 255 and 0 <= float(a) <= 1
				except (ValueError, TypeError):
					return False
		# 检查RGB格式
		if color_str.startswith("rgb("):
			match = re.match(r"rgb\((\d+),\s*(\d+),\s*(\d+)\)", color_str)
			if match:
				try:
					r, g, b = match.groups()
					return 0 <= int(r) <= 255 and 0 <= int(g) <= 255 and 0 <= int(b) <= 255
				except (ValueError, TypeError):
					return False
		return False

	@staticmethod
	def is_valid_number(value: Any) -> bool:
		"""检查是否为有效数字"""
		if isinstance(value, (int, float)):
			return True
		if isinstance(value, str):
			try:
				float(value)
			except ValueError:
				return False
			else:
				return True
		return False

	@staticmethod
	def is_valid_boolean(value: Any) -> bool:
		"""检查是否为有效布尔值"""
		if isinstance(value, bool):
			return True
		if isinstance(value, str):
			return value.upper() in {"TRUE", "FALSE", "YES", "NO", "1", "0"}
		if isinstance(value, int):
			return value in {0, 1}
		return False


class JSONConverter:
	"""JSON转换工具(类型安全)"""

	@staticmethod
	def ensure_dict(
		obj: Any,
		default: dict[str, Any] | None = None,
	) -> dict[str, Any]:
		"""确保对象是字典"""
		if isinstance(obj, dict):
			return obj
		if default is not None:
			return default.copy()
		return {}

	@staticmethod
	def ensure_list(obj: Any, default: list[Any] | None = None) -> list[Any]:
		"""确保对象是列表"""
		if isinstance(obj, list):
			return obj
		if default is not None:
			return default.copy()
		return []

	@staticmethod
	def ensure_str(obj: Any, default: str = "") -> str:
		"""确保对象是字符串"""
		if isinstance(obj, str):
			return obj
		return str(obj) if obj is not None else default

	@staticmethod
	def ensure_int(obj: Any, default: int = 0) -> int:
		"""确保对象是整数"""
		if isinstance(obj, int):
			return obj
		try:
			return int(obj) if obj is not None else default
		except (ValueError, TypeError):
			return default

	@staticmethod
	def ensure_float(obj: Any, default: float = 0.0) -> float:
		"""确保对象是浮点数"""
		if isinstance(obj, (int, float)):
			return float(obj)
		try:
			return float(obj) if obj is not None else default
		except (ValueError, TypeError):
			return default

	@staticmethod
	def ensure_bool(obj: Any, *, default: bool = False) -> bool:
		"""确保对象是布尔值"""
		if isinstance(obj, bool):
			return obj
		if isinstance(obj, str):
			return obj.upper() in {"TRUE", "YES", "1"}
		if isinstance(obj, int):
			return bool(obj)
		return default


# ============================================================================
# 核心数据类
# ============================================================================
@dataclass
class Color:
	"""颜色类(增强版)"""

	r: int = 0
	g: int = 0
	b: int = 0
	a: float = 1.0

	def __init__(self, color_str: str = "#000000") -> None:
		"""从字符串初始化颜色"""
		if not self.set(color_str):
			# 设置默认颜色
			self.r = 0
			self.g = 0
			self.b = 0
			self.a = 1.0

	def set(self, color_str: str) -> bool:  # noqa: PLR0911
		"""设置颜色值"""
		if not color_str:
			return False
		# 处理HEX格式
		if color_str.startswith("#"):
			hex_str = color_str[1:]
			length = len(hex_str)
			if length == 3:  # #RGB
				self.r = int(hex_str[0] * 2, 16)
				self.g = int(hex_str[1] * 2, 16)
				self.b = int(hex_str[2] * 2, 16)
				self.a = 1.0
				return True
			if length == 4:  # #RGBA
				self.r = int(hex_str[0] * 2, 16)
				self.g = int(hex_str[1] * 2, 16)
				self.b = int(hex_str[2] * 2, 16)
				self.a = int(hex_str[3] * 2, 16) / 255.0
				return True
			if length == 6:  # #RRGGBB
				self.r = int(hex_str[0:2], 16)
				self.g = int(hex_str[2:4], 16)
				self.b = int(hex_str[4:6], 16)
				self.a = 1.0
				return True
			if length == 8:  # #RRGGBBAA
				self.r = int(hex_str[0:2], 16)
				self.g = int(hex_str[2:4], 16)
				self.b = int(hex_str[4:6], 16)
				self.a = int(hex_str[6:8], 16) / 255.0
				return True
		# 处理RGBA格式
		if color_str.startswith("rgba("):
			match = re.match(
				r"rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)",
				color_str,
			)
			if match:
				try:
					self.r = int(match.group(1))
					self.g = int(match.group(2))
					self.b = int(match.group(3))
					self.a = float(match.group(4))
				except (ValueError, TypeError):
					return False
				else:
					return True
		# 处理RGB格式
		if color_str.startswith("rgb("):
			match = re.match(r"rgb\((\d+),\s*(\d+),\s*(\d+)\)", color_str)
			if match:
				try:
					self.r = int(match.group(1))
					self.g = int(match.group(2))
					self.b = int(match.group(3))
					self.a = 1.0
				except (ValueError, TypeError):
					return False
				else:
					return True
		return False

	def to_string(self, *, formats: ColorFormat = ColorFormat.RGBA) -> str:
		"""转换为字符串"""
		if formats == ColorFormat.COLOR_STRING:
			return self.to_hex()
		if formats == ColorFormat.RGBA:
			return f"rgba({self.r},{self.g},{self.b},{self.a})"
		if formats == ColorFormat.COLOR_PALETTE:
			return f"#{self.r:02x}{self.g:02x}{self.b:02x}"
		return f"rgba({self.r},{self.g},{self.b},{self.a})"

	def to_hex(self, *, include_alpha: bool = False) -> str:
		"""转换为HEX格式"""
		if include_alpha:
			alpha = int(self.a * 255)
			return f"#{self.r:02x}{self.g:02x}{self.b:02x}{alpha:02x}"
		return f"#{self.r:02x}{self.g:02x}{self.b:02x}"

	def to_dict(self) -> dict[str, Any]:
		"""转换为字典"""
		return {
			"r": self.r,
			"g": self.g,
			"b": self.b,
			"a": self.a,
			"hex": self.to_hex(),
			"rgba": self.to_string(formats=ColorFormat.RGBA),
		}

	@classmethod
	def from_dict(cls, data: dict[str, Any]) -> Color:
		"""从字典创建"""
		if "hex" in data:
			return cls(data["hex"])
		if "rgba" in data:
			return cls(data["rgba"])
		color = cls()
		color.r = JSONConverter.ensure_int(data.get("r"), 0)
		color.g = JSONConverter.ensure_int(data.get("g"), 0)
		color.b = JSONConverter.ensure_int(data.get("b"), 0)
		color.a = JSONConverter.ensure_float(data.get("a"), 1.0)
		return color

	def __repr__(self) -> str:
		return f"Color(r={self.r}, g={self.g}, b={self.b}, a={self.a})"


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

	@classmethod
	def from_dict(cls, data: dict[str, Any]) -> ConnectionJson:
		"""从字典创建"""
		return cls(
			type=JSONConverter.ensure_str(data.get("type")),
			input_type=data.get("input_type"),
			input_name=data.get("input_name"),
		)


@dataclass
class CommentJson:
	"""注释JSON结构"""

	id: str
	text: str = ""
	parent_id: str | None = None
	pinned: bool = False
	size: list[float] | None = None
	location: list[float] | None = None
	auto_layout: bool = False
	color_theme: str | None = None

	def __post_init__(self) -> None:
		"""初始化后处理"""
		if not self.id:
			self.id = str(uuid.uuid4())

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

	@classmethod
	def from_dict(cls, data: dict[str, Any]) -> CommentJson:
		"""从字典创建"""
		return cls(
			id=JSONConverter.ensure_str(data.get("id"), str(uuid.uuid4())),
			text=JSONConverter.ensure_str(data.get("text")),
			parent_id=data.get("parent_id"),
			pinned=JSONConverter.ensure_bool(data.get("pinned", False)),
			size=JSONConverter.ensure_list(data.get("size")),
			location=JSONConverter.ensure_list(data.get("location")),
			auto_layout=JSONConverter.ensure_bool(data.get("auto_layout", False)),
			color_theme=data.get("color_theme"),
		)


# ============================================================================
# 影子积木XML解析器
# ============================================================================
@dataclass
class ShadowXML:
	"""影子积木XML解析器"""

	xml_string: str
	type: str = ""
	id: str = ""
	visible: bool = True
	inline: bool = False
	fields: dict[str, str] = field(default_factory=dict)

	@classmethod
	def from_xml(cls, xml_str: str) -> ShadowXML:
		"""从XML字符串创建影子积木"""
		if not xml_str or not xml_str.strip():
			return cls("", "", "", True, False, {})  # noqa: FBT003
		try:
			# 清理XML字符串
			cleaned = html.unescape(xml_str)
			# 解析XML
			root = ET.fromstring(cleaned)  # noqa: S314
			# 提取字段
			fields = {}
			for field_elem in root.findall("field"):
				name = field_elem.get("name")
				if name:
					fields[name] = field_elem.text or ""
			return cls(
				xml_string=xml_str,
				type=root.get("type", ""),
				id=root.get("id", ""),
				visible=root.get("visible", "visible") == "visible",
				inline=root.get("inline", "false") == "true",
				fields=fields,
			)
		except ET.ParseError:
			# 返回原始XML
			return cls(xml_string=xml_str)

	def to_dict(self) -> dict[str, Any]:
		"""转换为字典"""
		return {
			"xml_string": self.xml_string,
			"type": self.type,
			"id": self.id,
			"visible": self.visible,
			"inline": self.inline,
			"fields": self.fields.copy(),
		}


@dataclass
class ShadowManager:
	"""影子积木管理器"""

	shadow_blocks: dict[str, ShadowBlock] = field(default_factory=dict)
	parent_child_map: dict[str, list[str]] = field(default_factory=dict)
	input_shadow_map: dict[str, dict[str, str]] = field(default_factory=dict)

	def add_shadow_block(
		self,
		shadow_block: ShadowBlock,
		parent_id: str | None = None,
	) -> str:
		"""添加影子积木"""
		self.shadow_blocks[shadow_block.id] = shadow_block
		# 记录父子关系
		if parent_id is not None:
			shadow_block.parent_id = parent_id
			if parent_id not in self.parent_child_map:
				self.parent_child_map[parent_id] = []
			self.parent_child_map[parent_id].append(shadow_block.id)
		# 记录输入影子映射
		if parent_id is not None and shadow_block.input_name is not None:
			if parent_id not in self.input_shadow_map:
				self.input_shadow_map[parent_id] = {}
			self.input_shadow_map[parent_id][shadow_block.input_name] = shadow_block.id
		return shadow_block.id

	def remove_shadow_block(self, shadow_id: str) -> bool:
		"""移除影子积木"""
		if shadow_id not in self.shadow_blocks:
			return False
		shadow_block = self.shadow_blocks[shadow_id]
		parent_id = shadow_block.parent_id
		# 清理父子关系
		if parent_id is not None and parent_id in self.parent_child_map:
			if shadow_id in self.parent_child_map[parent_id]:
				self.parent_child_map[parent_id].remove(shadow_id)
			if not self.parent_child_map[parent_id]:
				del self.parent_child_map[parent_id]
		# 清理输入映射
		if parent_id is not None and parent_id in self.input_shadow_map:
			if shadow_block.input_name is not None and shadow_block.input_name in self.input_shadow_map[parent_id]:
				del self.input_shadow_map[parent_id][shadow_block.input_name]
			if not self.input_shadow_map[parent_id]:
				del self.input_shadow_map[parent_id]
		# 移除影子积木
		del self.shadow_blocks[shadow_id]
		return True

	def get_shadows_by_parent(self, parent_id: str) -> list[ShadowBlock]:
		"""获取父积木的所有影子积木"""
		if parent_id not in self.parent_child_map:
			return []
		shadows: list[ShadowBlock] = [self.shadow_blocks[shadow_id] for shadow_id in self.parent_child_map[parent_id] if shadow_id in self.shadow_blocks]
		return shadows

	def get_input_shadow(
		self,
		parent_id: str,
		input_name: str,
	) -> ShadowBlock | None:
		"""获取指定输入的影子积木"""
		if parent_id in self.input_shadow_map and input_name in self.input_shadow_map[parent_id]:
			shadow_id = self.input_shadow_map[parent_id][input_name]
			return self.shadow_blocks.get(shadow_id)
		return None

	def to_dict(self) -> dict[str, Any]:
		"""转换为字典"""
		return {
			"shadow_blocks": {k: v.to_dict() for k, v in self.shadow_blocks.items()},
			"parent_child_map": self.parent_child_map.copy(),
			"input_shadow_map": self.input_shadow_map.copy(),
		}

	@classmethod
	def from_dict(cls, data: dict[str, Any]) -> ShadowManager:
		"""从字典创建"""
		manager = cls()
		# 加载影子积木
		for shadow_id, shadow_data in JSONConverter.ensure_dict(
			data.get("shadow_blocks"),
		).items():
			shadow_block = ShadowBlock.from_dict(shadow_data)
			manager.shadow_blocks[shadow_id] = shadow_block
		# 加载关系映射
		manager.parent_child_map = JSONConverter.ensure_dict(
			data.get("parent_child_map"),
		).copy()
		manager.input_shadow_map = JSONConverter.ensure_dict(
			data.get("input_shadow_map"),
		).copy()
		return manager


# ============================================================================
# KN积木块系统(匹配实际JSON结构)
# ============================================================================
@dataclass
class Block:
	"""KN积木结构 - 匹配实际JSON数据结构"""

	# KN实际JSON字段
	id: str = field(default_factory=lambda: str(uuid.uuid4()))
	type: str = ""
	location: list[float] | None = None
	shield: bool = False
	parent_id: str | None = None
	mutation: str = ""
	is_output: bool = False
	is_shadow: bool = False
	fields: dict[str, Any] = field(default_factory=dict)
	field_constraints: dict[str, Any] = field(default_factory=dict)
	field_extra_attr: dict[str, Any] = field(default_factory=dict)
	# 特殊字段 - 实际KN结构
	shadows: dict[str, str] = field(default_factory=dict)  # XML字符串
	inputs: dict[str, dict] = field(default_factory=dict)  # 嵌套字典
	statements: dict[str, dict] = field(default_factory=dict)  # 嵌套字典
	next: dict | None = None  # 嵌套字典,非Block对象引用
	# 内部操作字段(保留,但不输出到JSON)
	collapsed: bool = False
	disabled: bool = False
	deletable: bool = True
	movable: bool = True
	editable: bool = True
	visible: str = "visible"  # 保持为字符串类型以兼容原有代码
	comment: str | None = None
	# 影子积木管理器(保留,用于内部操作)
	shadow_manager: Any | None = field(default_factory=lambda: None)
	_parsed_shadows: dict[str, ShadowXML] = field(default_factory=dict)

	def __post_init__(self) -> None:
		"""初始化后处理"""
		if not self.id:
			self.id = str(uuid.uuid4())
		if not self.fields:
			self.fields = {}
		if not self.shadows:
			self.shadows = {}
		if not self.inputs:
			self.inputs = {}
		if not self.statements:
			self.statements = {}
		if not self.field_constraints:
			self.field_constraints = {}
		if not self.field_extra_attr:
			self.field_extra_attr = {}

	def to_dict(self) -> dict[str, Any]:
		"""转换为字典 - 匹配KN输出格式"""
		result: dict[str, Any] = {
			"id": self.id,
			"type": self.type,
			"shield": self.shield,
			"fields": self.fields.copy(),
			"shadows": self.shadows.copy(),
			"mutation": self.mutation,
			"is_output": self.is_output,
			"is_shadow": self.is_shadow,
			"field_constraints": self.field_constraints.copy(),
			"field_extra_attr": self.field_extra_attr.copy(),
		}
		if self.location is not None:
			result["location"] = self.location.copy()
		if self.parent_id is not None:
			result["parent_id"] = self.parent_id
		# 处理inputs - 保持原始字典结构
		if self.inputs:
			result["inputs"] = self.inputs.copy()
		# 处理statements - 保持原始字典结构
		if self.statements:
			result["statements"] = self.statements.copy()
		# 处理next - 保持字典结构
		if self.next is not None:
			result["next"] = self.next
		return result

	@classmethod
	def from_dict(cls, data: dict[str, Any]) -> Block:
		"""从字典创建块 - 匹配KN实际JSON结构"""
		# 检查是否为过程调用块
		block_type = JSONConverter.ensure_str(data.get("type"))
		fields = JSONConverter.ensure_dict(data.get("fields"))
		# 如果是过程调用,特殊处理
		if block_type in {"procedures_2_callnoreturn", "procedures_2_callreturn"}:
			return cls._create_procedure_call_block(data, block_type)
		# 创建基础块对象
		block = cls(
			id=JSONConverter.ensure_str(data.get("id"), str(uuid.uuid4())),
			type=block_type,
			location=JSONConverter.ensure_list(data.get("location")),
			shield=JSONConverter.ensure_bool(data.get("shield", False)),
			parent_id=data.get("parent_id"),
			mutation=JSONConverter.ensure_str(data.get("mutation", "")),
			is_output=JSONConverter.ensure_bool(data.get("is_output", False)),
			is_shadow=JSONConverter.ensure_bool(data.get("is_shadow", False)),
			fields=fields,
			field_constraints=JSONConverter.ensure_dict(data.get("field_constraints", {})),
			field_extra_attr=JSONConverter.ensure_dict(data.get("field_extra_attr", {})),
			shadows=JSONConverter.ensure_dict(data.get("shadows", {})),
		)
		# 处理inputs - 保持为嵌套字典,不转换为Block对象
		inputs_data = data.get("inputs", {})
		if isinstance(inputs_data, dict):
			block.inputs.update(inputs_data)
		# 处理statements - 保持为嵌套字典
		statements_data = data.get("statements", {})
		if isinstance(statements_data, dict):
			block.statements.update(statements_data)
		# 处理next - 保持为字典
		next_data = data.get("next")
		if isinstance(next_data, dict):
			block.next = next_data
		return block

	@classmethod
	def _create_procedure_call_block(cls, data: dict[str, Any], block_type: str) -> Block:
		"""创建过程调用块"""
		block_id = JSONConverter.ensure_str(data.get("id"), str(uuid.uuid4()))
		fields = JSONConverter.ensure_dict(data.get("fields", {}))
		mutation = JSONConverter.ensure_str(data.get("mutation", ""))
		# 解析mutation获取过程ID和参数信息
		procedure_id = fields.get("NAME", "")
		params_info = cls._parse_procedure_mutation(mutation)
		block = cls(
			id=block_id,
			type=block_type,
			fields=fields,
			mutation=mutation,
			parent_id=data.get("parent_id"),
			location=JSONConverter.ensure_list(data.get("location")),
			shield=JSONConverter.ensure_bool(data.get("shield", False)),
		)
		# 设置过程调用的参数
		block.fields["procedure_id"] = procedure_id
		block.fields["params_info"] = params_info
		# 处理输入参数
		if "inputs" in data:
			inputs_dict = JSONConverter.ensure_dict(data.get("inputs"))
			block.inputs.update(inputs_dict)
		# 处理下一个块
		if data.get("next"):
			block.next = data["next"]
		return block

	@classmethod
	def _parse_procedure_mutation(cls, mutation_xml: str) -> dict[str, Any]:
		"""解析过程调用的mutation XML"""
		if not mutation_xml:
			return {}
		try:
			root = ET.fromstring(mutation_xml)  # noqa: S314
			result: dict[str, Any] = {
				"def_id": root.get("def_id", ""),
				"name": root.get("name", ""),
				"type": root.get("type", "NORMAL"),
				"args": [],
			}
			# 解析参数
			for arg_elem in root.findall("arg"):
				arg_info = {
					"id": arg_elem.get("id", ""),
					"content": arg_elem.get("content", ""),
					"type": arg_elem.get("type", ""),
				}
				result["args"].append(arg_info)
		except ET.ParseError:
			# 如果XML解析失败,返回空字典
			return {}
		else:
			return result

	def get_all_blocks(self) -> list[Block]:
		"""获取此块及其所有子块"""
		blocks: list[Block] = []
		visited: set[str] = set()

		def collect_blocks(block_data: dict) -> None:
			"""递归收集块"""
			if "id" not in block_data or block_data["id"] in visited:
				return
			# 创建块对象
			block = Block.from_dict(block_data)
			visited.add(block.id)
			blocks.append(block)
			# 递归处理输入
			for input_data in block.inputs.values():
				if isinstance(input_data, dict):
					collect_blocks(input_data)
			# 递归处理语句
			for stmt_data in block.statements.values():
				if isinstance(stmt_data, dict):
					collect_blocks(stmt_data)
			# 处理下一个块
			if block.next is not None and isinstance(block.next, dict):
				collect_blocks(block.next)

		# 从当前块开始收集
		collect_blocks(self.to_dict())
		return blocks

	def find_block(self, block_id: str) -> Block | None:
		"""查找指定ID的块"""
		for block in self.get_all_blocks():
			if block.id == block_id:
				return block
		return None

	def parse_shadows(self) -> dict[str, ShadowXML]:
		"""解析影子积木XML"""
		if not self._parsed_shadows:
			self._parsed_shadows = {}
			for key, xml_str in self.shadows.items():
				if xml_str:
					self._parsed_shadows[key] = ShadowXML.from_xml(xml_str)
		return self._parsed_shadows

	def to_xml(
		self,
		*,
		include_shadows: bool = True,
		include_location: bool = True,
	) -> str:
		"""转换为XML字符串"""
		# 创建根元素
		root = ET.Element("shadow" if self.is_shadow else "block")
		root.set("type", self.type)
		root.set("id", self.id)
		# 添加位置信息
		if include_location and self.location is not None and len(self.location) >= 2:
			root.set("x", str(self.location[0]))
			root.set("y", str(self.location[1]))
		# 处理mutation
		if self.mutation:
			try:
				mutation_elem = ET.fromstring(self.mutation)  # noqa: S314
				root.append(mutation_elem)
			except ET.ParseError:
				mutation_elem = ET.Element("mutation")
				root.append(mutation_elem)
		# 处理字段
		for field_name, field_value in self.fields.items():
			if field_value is not None:
				field_elem = ET.Element("field")
				field_elem.set("name", field_name)
				field_elem.text = str(field_value)
				root.append(field_elem)
		# 处理影子积木(转换为XML元素)
		if include_shadows and self.shadows:
			for shadow_name, shadow_xml in self.shadows.items():
				if shadow_xml:
					try:
						shadow_elem = ET.fromstring(shadow_xml)  # noqa: S314
						shadow_elem.set("name", shadow_name)
						root.append(shadow_elem)
					except ET.ParseError:
						pass
		return ET.tostring(root, encoding="unicode", xml_declaration=False)

	@classmethod
	def from_xml(cls, xml_str: str) -> Block:
		"""从XML字符串创建积木块"""
		try:
			root = ET.fromstring(xml_str)  # noqa: S314
		except ET.ParseError as e:
			error_msg = f"XML解析错误: {e}"
			raise ValueError(error_msg) from e
		# 解析基本属性
		block_type = root.get("type", "")
		block_id = root.get("id", str(uuid.uuid4()))
		is_shadow = root.tag in {"shadow", "empty"}
		# 创建块
		block = cls(
			id=block_id,
			type=block_type,
			is_shadow=is_shadow,
			editable=root.tag != "empty",
		)
		# 解析位置
		x = root.get("x")
		y = root.get("y")
		if x is not None and y is not None:
			try:
				block.location = [float(x), float(y)]
			except ValueError:
				block.location = [0.0, 0.0]
		# 解析特殊属性
		if root.get("disabled") == "true":
			block.disabled = True
		if root.get("collapsed") == "true":
			block.collapsed = True
		if root.get("deletable") == "false":
			block.deletable = False
		if root.get("movable") == "false":
			block.movable = False
		if root.get("editable") == "false":
			block.editable = False
		visible = root.get("visible")
		if visible is not None:
			block.visible = visible
		# 解析mutation
		mutation_elem = root.find("mutation")
		if mutation_elem is not None:
			block.mutation = ET.tostring(mutation_elem, encoding="unicode")
		# 解析字段
		for field_elem in root.findall("field"):
			field_name = field_elem.get("name")
			if field_name is not None and field_elem.text is not None:
				block.fields[field_name] = field_elem.text
		return block

	def add_shadow(
		self,
		shadow_block: ShadowBlock,
		input_name: str | None = None,
	) -> str:
		"""添加影子积木"""
		shadow_block.parent_id = self.id
		shadow_block.input_name = input_name
		# 由于新版没有shadow_manager,我们简化处理
		if self.shadow_manager is None:
			self.shadow_manager = ShadowManager()
		return self.shadow_manager.add_shadow_block(shadow_block, self.id)

	def get_shadows(self) -> list[ShadowBlock]:
		"""获取所有影子积木"""
		if self.shadow_manager is None:
			return []
		return self.shadow_manager.get_shadows_by_parent(self.id)

	def get_input_shadow(self, input_name: str) -> ShadowBlock | None:
		"""获取指定输入的影子积木"""
		if self.shadow_manager is None:
			return None
		return self.shadow_manager.get_input_shadow(self.id, input_name)


# ============================================================================
# 自定义函数/过程类
# ============================================================================
@dataclass
class Procedure:
	"""自定义函数/过程类"""

	id: str
	name: str
	type: str = "NORMAL"  # NORMAL, DEFINE, etc.
	params: list[dict[str, Any]] = field(default_factory=list)
	blocks: list[Block] = field(default_factory=list)
	workspace_scroll_xy: dict[str, float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0})
	comments: dict[str, Any] = field(default_factory=dict)

	def __post_init__(self) -> None:
		"""初始化后处理"""
		if not self.id:
			self.id = str(uuid.uuid4())

	def to_dict(self) -> dict[str, Any]:
		"""转换为字典"""
		return {
			"id": self.id,
			"name": self.name,
			"type": self.type,
			"params": self.params.copy(),
			"nekoBlockJsonList": [block.to_dict() for block in self.blocks],
			"workspaceScrollXy": self.workspace_scroll_xy.copy(),
			"comments": self.comments.copy(),
		}

	@classmethod
	def from_dict(cls, data: dict[str, Any]) -> Procedure:
		"""从字典创建过程"""
		proc = cls(
			id=JSONConverter.ensure_str(data.get("id"), str(uuid.uuid4())),
			name=JSONConverter.ensure_str(data.get("name")),
			type=JSONConverter.ensure_str(data.get("type", "NORMAL")),
			params=JSONConverter.ensure_list(data.get("params")),
			workspace_scroll_xy=JSONConverter.ensure_dict(data.get("workspaceScrollXy", {"x": 0.0, "y": 0.0})),
			comments=JSONConverter.ensure_dict(data.get("comments", {})),
		)
		# 加载块
		blocks_data = JSONConverter.ensure_list(data.get("nekoBlockJsonList"))
		for block_data in blocks_data:
			if isinstance(block_data, dict):
				proc.blocks.append(Block.from_dict(block_data))
		return proc

	def add_block(self, block_type: str, **kwargs: Any) -> Block:
		"""添加代码块到过程"""
		block = Block(type=block_type, **kwargs)
		self.blocks.append(block)
		return block

	def get_param_names(self) -> list[str]:
		"""获取参数名称列表"""
		return [param.get("name", "") for param in self.params if isinstance(param, dict)]


# ============================================================================
# 原有影子积木系统(保留以支持原有代码)
# ============================================================================
@dataclass
class ShadowBlock:
	"""影子积木(完整版) - 保留以支持原有代码"""

	id: str = field(default_factory=lambda: str(uuid.uuid4()))
	type: str = ""
	shadow_type: ShadowType = ShadowType.REGULAR
	category: ShadowCategory = ShadowCategory.DEFAULT_VALUE
	fields: dict[str, Any] = field(default_factory=dict)
	mutation: str = ""
	is_output: bool = False
	editable: bool = True
	deletable: bool = False
	movable: bool = False
	visible: bool = True
	disabled: bool = False
	collapsed: bool = False
	location: list[float] | None = None
	parent_id: str | None = None
	connection_type: ConnectionType | None = None
	input_name: str | None = None
	# 影子积木特定属性
	is_detachable: bool = True
	is_replaceable: bool = True
	can_have_inputs: bool = True
	can_be_replaced: bool = True
	keeps_value: bool = False
	default_value: Any = None
	value_type: str | None = None
	# 约束条件
	field_constraints: dict[str, dict[str, Any]] = field(default_factory=dict)
	connection_constraints: dict[str, Any] = field(default_factory=dict)

	def __post_init__(self) -> None:
		"""初始化后处理"""
		if not self.id:
			self.id = str(uuid.uuid4())
		if not self.fields:
			self.fields = {}
		if not self.field_constraints:
			self.field_constraints = {}
		if not self.connection_constraints:
			self.connection_constraints = {}
		# 根据影子类型设置属性
		if self.shadow_type == ShadowType.EMPTY:
			self.editable = False
			self.is_detachable = False
			self.can_have_inputs = False
		elif self.shadow_type == ShadowType.REPLACEABLE:
			self.is_detachable = True
			self.can_be_replaced = True

	def to_dict(self) -> dict[str, Any]:
		"""转换为字典"""
		result: dict[str, Any] = {
			"id": self.id,
			"type": self.type,
			"shadow_type": self.shadow_type.value,
			"category": self.category.value,
			"fields": self.fields.copy(),
			"mutation": self.mutation,
			"is_output": self.is_output,
			"editable": self.editable,
			"deletable": self.deletable,
			"movable": self.movable,
			"visible": self.visible,
			"disabled": self.disabled,
			"collapsed": self.collapsed,
			"is_detachable": self.is_detachable,
			"is_replaceable": self.is_replaceable,
			"can_have_inputs": self.can_have_inputs,
			"can_be_replaced": self.can_be_replaced,
			"keeps_value": self.keeps_value,
			"default_value": self.default_value,
			"value_type": self.value_type,
			"field_constraints": self.field_constraints.copy(),
			"connection_constraints": self.connection_constraints.copy(),
		}
		if self.location is not None:
			result["location"] = self.location.copy()
		if self.parent_id is not None:
			result["parent_id"] = self.parent_id
		if self.connection_type is not None:
			result["connection_type"] = self.connection_type.value
		if self.input_name is not None:
			result["input_name"] = self.input_name
		return result

	@classmethod
	def from_dict(cls, data: dict[str, Any]) -> ShadowBlock:
		"""从字典创建"""
		connection_type = None
		if "connection_type" in data:
			try:
				connection_type = ConnectionType(data["connection_type"])
			except ValueError:
				connection_type = None
		return cls(
			id=JSONConverter.ensure_str(data.get("id"), str(uuid.uuid4())),
			type=JSONConverter.ensure_str(data.get("type")),
			shadow_type=ShadowType(data.get("shadow_type", "regular")),
			category=ShadowCategory(data.get("category", "default_value")),
			fields=JSONConverter.ensure_dict(data.get("fields")),
			mutation=JSONConverter.ensure_str(data.get("mutation")),
			is_output=JSONConverter.ensure_bool(data.get("is_output", False)),
			editable=JSONConverter.ensure_bool(data.get("editable", True)),
			deletable=JSONConverter.ensure_bool(data.get("deletable", False)),
			movable=JSONConverter.ensure_bool(data.get("movable", False)),
			visible=JSONConverter.ensure_bool(data.get("visible", True)),
			disabled=JSONConverter.ensure_bool(data.get("disabled", False)),
			collapsed=JSONConverter.ensure_bool(data.get("collapsed", False)),
			location=JSONConverter.ensure_list(data.get("location")),
			parent_id=data.get("parent_id"),
			connection_type=connection_type,
			input_name=data.get("input_name"),
			is_detachable=JSONConverter.ensure_bool(
				data.get("is_detachable", True),
			),
			is_replaceable=JSONConverter.ensure_bool(
				data.get("is_replaceable", True),
			),
			can_have_inputs=JSONConverter.ensure_bool(
				data.get("can_have_inputs", True),
			),
			can_be_replaced=JSONConverter.ensure_bool(
				data.get("can_be_replaced", True),
			),
			keeps_value=JSONConverter.ensure_bool(data.get("keeps_value", False)),
			default_value=data.get("default_value"),
			value_type=data.get("value_type"),
			field_constraints=JSONConverter.ensure_dict(
				data.get("field_constraints"),
			),
			connection_constraints=JSONConverter.ensure_dict(
				data.get("connection_constraints"),
			),
		)


# ============================================================================
# KN项目解析器
# ============================================================================
class KNProjectParser:
	"""KN项目解析器"""

	@staticmethod
	def parse_nested_structure(data: dict, all_blocks_flat: dict[str, dict], parent_id: str | None = None) -> None:
		"""递归收集嵌套结构中的所有块"""
		if not isinstance(data, dict) or "type" not in data:
			return
		block_id = data.get("id", str(uuid.uuid4()))
		# 保存原始数据
		if block_id not in all_blocks_flat:
			all_blocks_flat[block_id] = data
		# 设置parent_id
		data["parent_id"] = parent_id
		# 递归处理inputs
		inputs = data.get("inputs", {})
		for input_data in inputs.values():
			if isinstance(input_data, dict):
				KNProjectParser.parse_nested_structure(
					input_data,
					all_blocks_flat,
					block_id,
				)
		# 递归处理statements
		statements = data.get("statements", {})
		for stmt_data in statements.values():
			if isinstance(stmt_data, dict):
				KNProjectParser.parse_nested_structure(
					stmt_data,
					all_blocks_flat,
					block_id,
				)
		# 递归处理next
		next_data = data.get("next")
		if isinstance(next_data, dict):
			KNProjectParser.parse_nested_structure(
				next_data,
				all_blocks_flat,
				block_id,
			)

	@staticmethod
	def build_blocks_from_flat(all_blocks_flat: dict[str, dict]) -> dict[str, Block]:
		"""从平面数据构建Block对象"""
		blocks = {}
		for block_id, block_data in all_blocks_flat.items():
			blocks[block_id] = Block.from_dict(block_data)
		return blocks


# ============================================================================
# 角色和场景类(保持原样)
# ============================================================================
@dataclass
class Actor:
	"""角色(增强版)"""

	id: str
	name: str
	position: dict[str, float] = field(
		default_factory=lambda: {"x": 0.0, "y": 0.0},
	)
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

	def __post_init__(self) -> None:
		"""初始化后处理"""
		if not self.id:
			self.id = str(uuid.uuid4())

	def to_dict(self) -> dict[str, Any]:
		"""转换为字典"""
		return {
			"id": self.id,
			"name": self.name,
			"position": self.position.copy(),
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
	def from_dict(cls, data: dict[str, Any]) -> Actor:
		"""从字典创建角色"""
		actor = cls(
			id=JSONConverter.ensure_str(data.get("id"), str(uuid.uuid4())),
			name=JSONConverter.ensure_str(data.get("name")),
			position=JSONConverter.ensure_dict(
				data.get("position", {"x": 0.0, "y": 0.0}),
			),
			scale=JSONConverter.ensure_float(data.get("scale", 100.0)),
			rotation=JSONConverter.ensure_float(data.get("rotation", 0.0)),
			visible=JSONConverter.ensure_bool(data.get("visible", True)),
			locked=JSONConverter.ensure_bool(data.get("locked", False)),
			draggable=JSONConverter.ensure_bool(data.get("draggable", True)),
			rotation_type=JSONConverter.ensure_str(
				data.get("rotationType", "all around"),
			),
			styles=JSONConverter.ensure_list(data.get("styles")),
			current_style_id=JSONConverter.ensure_str(
				data.get("currentStyleId"),
			),
		)
		# 加载块
		blocks_data = JSONConverter.ensure_list(data.get("nekoBlockJsonList"))
		for block_data in blocks_data:
			if isinstance(block_data, dict):
				actor.blocks.append(Block.from_dict(block_data))
		return actor

	def add_block(self, block_type: str, **kwargs: Any) -> Block:
		"""添加代码块"""
		block = Block(type=block_type, **kwargs)
		self.blocks.append(block)
		return block

	def add_move_block(self, x: float, y: float) -> Block:
		"""添加移动块"""
		block = self.add_block(BlockType.SELF_MOVE_TO.value)
		block.inputs["X"] = {"type": BlockType.MATH_NUMBER.value, "fields": {"NUM": str(x)}}
		block.inputs["Y"] = {"type": BlockType.MATH_NUMBER.value, "fields": {"NUM": str(y)}}
		return block

	def add_say_block(self, text: str) -> Block:
		"""添加说话块"""
		block = self.add_block(BlockType.SELF_DIALOG.value)
		block.inputs["TEXT"] = {"type": BlockType.TEXT.value, "fields": {"TEXT": text}}
		return block

	def add_wait_block(self, seconds: float) -> Block:
		"""添加等待块"""
		block = self.add_block(BlockType.WAIT.value)
		block.inputs["SECONDS"] = {"type": BlockType.MATH_NUMBER.value, "fields": {"NUM": str(seconds)}}
		return block


@dataclass
class Scene:
	"""场景(增强版)"""

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

	def __post_init__(self) -> None:
		"""初始化后处理"""
		if not self.id:
			self.id = str(uuid.uuid4())

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
	def from_dict(cls, data: dict[str, Any]) -> Scene:
		"""从字典创建场景"""
		scene = cls(
			id=JSONConverter.ensure_str(data.get("id"), str(uuid.uuid4())),
			name=JSONConverter.ensure_str(data.get("name")),
			screen_name=JSONConverter.ensure_str(
				data.get("screenName", "屏幕"),
			),
			styles=JSONConverter.ensure_list(data.get("styles")),
			actor_ids=JSONConverter.ensure_list(data.get("actorIds")),
			visible=JSONConverter.ensure_bool(data.get("visible", True)),
			current_style_id=JSONConverter.ensure_str(
				data.get("currentStyleId"),
			),
			background_color=JSONConverter.ensure_str(
				data.get("backgroundColor", "#FFFFFF"),
			),
			background_image=data.get("backgroundImage"),
		)
		# 加载块
		blocks_data = JSONConverter.ensure_list(data.get("nekoBlockJsonList"))
		for block_data in blocks_data:
			if isinstance(block_data, dict):
				scene.blocks.append(Block.from_dict(block_data))
		return scene

	def add_block(self, block_type: str, **kwargs: Any) -> Block:
		"""添加代码块"""
		block = Block(type=block_type, **kwargs)
		self.blocks.append(block)
		return block

	def add_start_block(self) -> Block:
		"""添加程序启动块"""
		return self.add_block(BlockType.ON_RUNNING_GROUP_ACTIVATED.value)


# ============================================================================
# 工作区数据
# ============================================================================
@dataclass
class WorkspaceData:
	"""工作区数据"""

	blocks: dict[str, Block] = field(default_factory=dict)
	comments: dict[str, CommentJson] = field(default_factory=dict)
	connections: dict[str, dict[str, ConnectionJson]] = field(
		default_factory=dict,
	)

	def to_dict(self) -> dict[str, Any]:
		"""转换为字典"""
		return {
			"blocks": {bid: block.to_dict() for bid, block in self.blocks.items()},
			"comments": {cid: comment.to_dict() for cid, comment in self.comments.items()},
			"connections": {bid: {target_id: conn.to_dict() for target_id, conn in target_conns.items()} for bid, target_conns in self.connections.items()},
		}

	@classmethod
	def from_dict(cls, data: dict[str, Any]) -> WorkspaceData:
		"""从字典创建工作区数据"""
		ws = cls()
		# 加载块
		for block_id, block_data in JSONConverter.ensure_dict(
			data.get("blocks"),
		).items():
			ws.blocks[block_id] = Block.from_dict(block_data)
		# 加载注释
		for comment_id, comment_data in JSONConverter.ensure_dict(
			data.get("comments"),
		).items():
			ws.comments[comment_id] = CommentJson.from_dict(comment_data)
		# 加载连接
		for block_id, target_conns in JSONConverter.ensure_dict(
			data.get("connections"),
		).items():
			ws.connections[block_id] = {}
			for target_id, conn_data in JSONConverter.ensure_dict(
				target_conns,
			).items():
				ws.connections[block_id][target_id] = ConnectionJson.from_dict(
					conn_data,
				)
		return ws

	def add_block(self, block: Block) -> None:
		"""添加块"""
		self.blocks[block.id] = block

	def add_comment(self, comment: CommentJson) -> None:
		"""添加注释"""
		self.comments[comment.id] = comment

	def connect_blocks(
		self,
		source_id: str,
		target_id: str,
		conn_type: str,
		input_name: str | None = None,
	) -> None:
		"""连接两个块"""
		if source_id not in self.connections:
			self.connections[source_id] = {}
		conn = ConnectionJson(type=conn_type)
		if conn_type == "input":
			conn.input_type = "value"
			conn.input_name = input_name
		self.connections[source_id][target_id] = conn


# ============================================================================
# KN项目主类(修正版)
# ============================================================================
class KNProject:
	"""KN项目(完整重构版)"""

	def __init__(self, project_name: str = "未命名项目") -> None:
		self.project_name: str = project_name
		self.version: str = "0.20.0"
		self.tool_type: str = "KN"
		# 核心数据
		self.scenes: dict[str, Scene] = {}
		self.current_scene_id: str = ""
		self.sort_list: list[str] = []
		self.actors: dict[str, Actor] = {}
		# 资源数据
		self.styles: dict[str, Any] = {}
		self.variables: dict[str, Any] = {}
		self.lists: dict[str, Any] = {}
		self.broadcasts: dict[str, Any] = {}
		self.audios: dict[str, Any] = {}
		self.procedures: dict[str, Any] = {}
		# 工作区数据
		self.workspace: WorkspaceData = WorkspaceData()
		# 其他设置
		self.stage_size: dict[str, float] = {"width": 900.0, "height": 562.0}
		self.timer_position: dict[str, float] = {"x": 720.0, "y": 12.0}
		self.workspace_scroll_xy: dict[str, float] = {"x": 0.0, "y": 0.0}
		self.filepath: Path | None = None
		self.resources: dict[str, Any] = {}
		self.project_folder: Path | None = None

	@classmethod
	def load_from_dict(cls, data: dict[str, Any]) -> KNProject:  # noqa: PLR0914
		"""从JSON字典加载项目 - 修正版"""
		project = cls(
			JSONConverter.ensure_str(data.get("projectName", "未命名项目")),
		)
		# 基础信息
		project.version = JSONConverter.ensure_str(
			data.get("version", "0.20.0"),
		)
		project.tool_type = JSONConverter.ensure_str(data.get("toolType", "KN"))
		project.stage_size = JSONConverter.ensure_dict(
			data.get("stageSize", {"width": 900.0, "height": 562.0}),
		)
		project.timer_position = JSONConverter.ensure_dict(
			data.get("timerPosition", {"x": 720.0, "y": 12.0}),
		)
		project.workspace_scroll_xy = JSONConverter.ensure_dict(
			data.get("workspaceScrollXy", {"x": 0.0, "y": 0.0}),
		)
		# 解析样式
		styles_data = data.get("styles", {})
		styles_dict = JSONConverter.ensure_dict(styles_data.get("stylesDict", {}))
		for style_id, style_data in styles_dict.items():
			project.styles[style_id] = {
				"id": style_id,
				"url": JSONConverter.ensure_str(style_data.get("url", "")),
				"name": JSONConverter.ensure_str(style_data.get("name", "")),
				"centerPoint": JSONConverter.ensure_dict(style_data.get("centerPoint", {"x": 0.0, "y": 0.0})),
				"adaption": JSONConverter.ensure_str(style_data.get("adaption", "none")),
				"styleType": JSONConverter.ensure_int(style_data.get("styleType", 1)),
			}
		# 解析变量
		variables_data = data.get("variables", {})
		variables_dict = JSONConverter.ensure_dict(variables_data.get("variablesDict", {}))
		for var_id, var_data in variables_dict.items():
			project.variables[var_id] = {
				"id": var_id,
				"name": JSONConverter.ensure_str(var_data.get("name", "")),
				"type": JSONConverter.ensure_str(var_data.get("type", "any")),
				"value": var_data.get("value", 0),
				"style": JSONConverter.ensure_str(var_data.get("style", "default")),
				"scale": JSONConverter.ensure_float(var_data.get("scale", 1.0)),
				"visible": JSONConverter.ensure_bool(var_data.get("visible", False)),
				"position": JSONConverter.ensure_dict(var_data.get("position", {"x": 20.0, "y": 20.0})),
				"isGlobal": JSONConverter.ensure_bool(var_data.get("isGlobal", True)),
				"currentEntityId": var_data.get("currentEntityId"),
			}
		# 解析场景
		scenes_data = JSONConverter.ensure_dict(data.get("scenes", {}))
		scenes_dict = JSONConverter.ensure_dict(scenes_data.get("scenesDict", {}))
		for scene_id, scene_data in scenes_dict.items():
			# 创建场景对象
			scene = Scene(
				id=scene_id,
				name=JSONConverter.ensure_str(scene_data.get("name")),
				screen_name=JSONConverter.ensure_str(scene_data.get("screenName", "屏幕")),
				styles=JSONConverter.ensure_list(scene_data.get("styles", [])),
				actor_ids=JSONConverter.ensure_list(scene_data.get("actorIds", [])),
				visible=JSONConverter.ensure_bool(scene_data.get("visible", True)),
				current_style_id=JSONConverter.ensure_str(scene_data.get("currentStyleId", "")),
				background_color=JSONConverter.ensure_str(scene_data.get("backgroundColor", "#FFFFFF")),
				background_image=scene_data.get("backgroundImage"),
			)
			# 解析场景积木 - 使用新的解析策略
			blocks_list = JSONConverter.ensure_list(scene_data.get("nekoBlockJsonList", []))
			for block_data in blocks_list:
				if isinstance(block_data, dict):
					# 使用新的Block.from_dict方法
					block = Block.from_dict(block_data)
					scene.blocks.append(block)
					project.workspace.add_block(block)
			project.scenes[scene_id] = scene
		project.current_scene_id = JSONConverter.ensure_str(
			scenes_data.get("currentSceneId", ""),
		)
		project.sort_list = JSONConverter.ensure_list(
			scenes_data.get("sortList", []),
		)
		# 解析角色
		actors_data = JSONConverter.ensure_dict(data.get("actors", {}))
		actors_dict = JSONConverter.ensure_dict(actors_data.get("actorsDict", {}))
		for actor_id, actor_data in actors_dict.items():
			actor = Actor(
				id=actor_id,
				name=JSONConverter.ensure_str(actor_data.get("name")),
				position=JSONConverter.ensure_dict(actor_data.get("position", {"x": 0.0, "y": 0.0})),
				scale=JSONConverter.ensure_float(actor_data.get("scale", 100.0)),
				rotation=JSONConverter.ensure_float(actor_data.get("rotation", 0.0)),
				visible=JSONConverter.ensure_bool(actor_data.get("visible", True)),
				locked=JSONConverter.ensure_bool(actor_data.get("locked", False)),
				draggable=JSONConverter.ensure_bool(actor_data.get("draggable", True)),
				rotation_type=JSONConverter.ensure_str(actor_data.get("rotationType", "all around")),
				styles=JSONConverter.ensure_list(actor_data.get("styles", [])),
				current_style_id=JSONConverter.ensure_str(actor_data.get("currentStyleId", "")),
			)
			# 解析角色积木
			blocks_list = JSONConverter.ensure_list(actor_data.get("nekoBlockJsonList", []))
			for block_data in blocks_list:
				if isinstance(block_data, dict):
					block = Block.from_dict(block_data)
					actor.blocks.append(block)
					project.workspace.add_block(block)
			project.actors[actor_id] = actor
		# 解析广播
		broadcasts_data = data.get("broadcasts", {})
		broadcasts_dict = JSONConverter.ensure_dict(broadcasts_data.get("broadcastsDict", {}))
		for scene_id, messages in broadcasts_dict.items():
			if isinstance(messages, list):
				project.broadcasts[scene_id] = {
					"scene_id": scene_id,
					"messages": messages,
				}
		# 解析过程
		procedures_data = data.get("procedures", {})
		procedures_dict = JSONConverter.ensure_dict(procedures_data.get("proceduresDict", {}))
		project.procedures = procedures_dict.copy()
		# 解析列表
		lists_data = data.get("lists", {})
		lists_dict = JSONConverter.ensure_dict(lists_data.get("listsDict", {}))
		project.lists = lists_dict.copy()
		# 解析音频
		audios_data = data.get("audios", {})
		audios_dict = JSONConverter.ensure_dict(audios_data.get("audiosDict", {}))
		project.audios = audios_dict.copy()
		return project

	@classmethod
	def from_xml(cls, xml_str: str) -> KNProject:
		"""从XML创建项目"""
		root = ET.fromstring(xml_str)  # noqa: S314
		project_name = root.get("name", "XML项目")
		project = cls(project_name)
		project.version = root.get("version", "0.20.0")
		project.tool_type = root.get("toolType", "KN")
		# 解析场景
		scenes_elem = root.find("scenes")
		if scenes_elem is not None:
			for scene_elem in scenes_elem.findall("scene"):
				scene_id = scene_elem.get("id", str(uuid.uuid4()))
				scene_name = scene_elem.get("name", "场景")
				scene = Scene(id=scene_id, name=scene_name)
				# 解析场景的积木
				blocks_elem = scene_elem.find("blocks")
				if blocks_elem is not None:
					for block_elem in blocks_elem.findall("block"):
						_block_xml = ET.tostring(block_elem, encoding="unicode")
						# 这里需要Block类的from_xml方法,新版中没有这个方法
						# 暂时跳过或简化处理
						try:
							# 创建简单块对象
							block = Block(
								id=block_elem.get("id", str(uuid.uuid4())),
								type=block_elem.get("type", ""),
								location=[0.0, 0.0],
							)
							scene.blocks.append(block)
						except Exception:  # noqa: S110
							pass
				project.scenes[scene_id] = scene
				project.sort_list.append(scene_id)
		# 解析角色
		actors_elem = root.find("actors")
		if actors_elem is not None:
			for actor_elem in actors_elem.findall("actor"):
				actor_id = actor_elem.get("id", str(uuid.uuid4()))
				actor_name = actor_elem.get("name", "角色")
				actor = Actor(id=actor_id, name=actor_name)
				# 解析角色的积木
				blocks_elem = actor_elem.find("blocks")
				if blocks_elem is not None:
					for block_elem in blocks_elem.findall("block"):
						_block_xml = ET.tostring(block_elem, encoding="unicode")
						# 这里需要Block类的from_xml方法,新版中没有这个方法
						# 暂时跳过或简化处理
						try:
							block = Block(
								id=block_elem.get("id", str(uuid.uuid4())),
								type=block_elem.get("type", ""),
								location=[0.0, 0.0],
							)
							actor.blocks.append(block)
						except Exception:  # noqa: S110
							pass
				project.actors[actor_id] = actor
		return project

	def to_dict(self) -> dict[str, Any]:
		"""转换为完整项目JSON"""
		project_dict: dict[str, Any] = {
			"projectName": self.project_name,
			"version": self.version,
			"toolType": self.tool_type,
			"stageSize": self.stage_size,
			"timerPosition": self.timer_position,
			"workspaceScrollXy": self.workspace_scroll_xy,
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
			"actors": {
				"actorsDict": {actor_id: actor.to_dict() for actor_id, actor in self.actors.items()},
			},
		}
		return project_dict

	@classmethod
	def load_from_file(cls, filepath: str | Path) -> KNProject:
		"""从文件加载项目"""
		filepath = Path(filepath)
		if not filepath.exists():
			msg = f"文件不存在: {filepath}"
			raise FileNotFoundError(msg)
		with filepath.open("r", encoding="utf-8") as f:
			data = json.load(f)
		project = cls.load_from_dict(data)
		project.filepath = filepath
		project.project_folder = filepath.parent
		return project

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
		# 确保文件扩展名为 .bcmkn
		if filepath.suffix != ".bcmkn":
			filepath = filepath.with_suffix(".bcmkn")
		data = self.to_dict()
		with filepath.open("w", encoding="utf-8") as f:
			json.dump(data, f, ensure_ascii=False, indent=2)
		print(f"项目已保存: {filepath}")

	def add_actor(
		self,
		name: str,
		position: dict[str, float] | None = None,
		**kwargs: Any,
	) -> str:
		"""添加角色"""
		actor_id = str(uuid.uuid4())
		if position is None:
			position = {"x": 0.0, "y": 0.0}
		actor = Actor(id=actor_id, name=name, position=position, **kwargs)
		self.actors[actor_id] = actor
		return actor_id

	def add_scene(
		self,
		name: str,
		screen_name: str = "屏幕",
		**kwargs: Any,
	) -> str:
		"""添加场景"""
		scene_id = str(uuid.uuid4())
		scene = Scene(id=scene_id, name=name, screen_name=screen_name, **kwargs)
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

	def add_audio(
		self,
		name: str,
		audio_url: str = "",
		volume: int = 100,
	) -> str:
		"""添加音频"""
		audio_id = str(uuid.uuid4())
		audio = {
			"id": audio_id,
			"name": name,
			"audioUrl": audio_url,
			"volume": volume,
		}
		self.audios[audio_id] = audio
		return audio_id

	def add_style(self, name: str) -> str:
		"""添加样式"""
		style_id = str(uuid.uuid4())
		style = {"id": style_id, "name": name}
		self.styles[style_id] = style
		return style_id

	def add_block_to_actor(self, actor_id: str, block: Block) -> bool:
		"""添加块到角色"""
		if actor_id not in self.actors:
			return False
		self.actors[actor_id].blocks.append(block)
		self.workspace.add_block(block)
		return True

	def add_block_to_scene(self, scene_id: str, block: Block) -> bool:
		"""添加块到场景"""
		if scene_id not in self.scenes:
			return False
		self.scenes[scene_id].blocks.append(block)
		self.workspace.add_block(block)
		return True

	def add_procedure(self, name: str, params: list[dict[str, Any]] | None = None) -> str:
		"""添加自定义函数"""
		proc_id = str(uuid.uuid4())
		if params is None:
			params = []
		proc = Procedure(id=proc_id, name=name, params=params)
		self.procedures[proc_id] = proc
		return proc_id

	def get_procedure(self, proc_id: str) -> Procedure | None:
		"""获取过程"""
		return self.procedures.get(proc_id)

	def get_procedure_by_name(self, name: str) -> Procedure | dict | None:
		"""按名称获取过程"""
		for proc in self.procedures.values():
			if isinstance(proc, dict):
				if proc.get("name") == name:
					return proc
			elif isinstance(proc, Procedure) and proc.name == name:
				return proc
		return None

	def create_simple_program(
		self,
		actor_name: str = "角色1",
		scene_name: str = "场景1",
	) -> None:
		"""创建简单程序示例"""
		# 添加角色和场景
		actor_id = self.add_actor(actor_name)
		scene_id = self.add_scene(scene_name)
		self.scenes[scene_id].actor_ids.append(actor_id)
		# 创建启动块
		start_block = Block(
			type=BlockType.ON_RUNNING_GROUP_ACTIVATED.value,
			location=[100.0, 100.0],
		)
		# 创建说话块
		say_block = Block(
			type=BlockType.SELF_DIALOG.value,
			location=[100.0, 150.0],
		)
		say_block.inputs["TEXT"] = {"type": BlockType.TEXT.value, "fields": {"TEXT": "你好,世界!"}}
		# 创建移动块
		move_block = Block(
			type=BlockType.SELF_MOVE_TO.value,
			location=[100.0, 200.0],
		)
		move_block.inputs["X"] = {"type": BlockType.MATH_NUMBER.value, "fields": {"NUM": "100"}}
		move_block.inputs["Y"] = {"type": BlockType.MATH_NUMBER.value, "fields": {"NUM": "100"}}
		# 创建等待块
		wait_block = Block(
			type=BlockType.WAIT.value,
			location=[100.0, 250.0],
		)
		wait_block.inputs["SECONDS"] = {"type": BlockType.MATH_NUMBER.value, "fields": {"NUM": "1"}}
		# 连接块
		start_block.next = say_block.to_dict()
		say_block.next = move_block.to_dict()
		move_block.next = wait_block.to_dict()
		# 添加到场景和角色
		self.add_block_to_scene(scene_id, start_block)
		self.add_block_to_actor(actor_id, start_block)
		print(f"创建了简单程序: {actor_name} 在 {scene_name}")

	def get_all_blocks(self) -> list[Block]:
		"""获取项目中所有块"""
		all_blocks: list[Block] = []
		# 收集场景的块
		for scene in self.scenes.values():
			all_blocks.extend(scene.blocks)
		# 收集角色的块
		for actor in self.actors.values():
			all_blocks.extend(actor.blocks)
		# 收集工作区的块
		all_blocks.extend(self.workspace.blocks.values())
		return all_blocks

	def find_block(self, block_id: str) -> Block | None:
		"""在项目中查找代码块"""
		for block in self.get_all_blocks():
			if block.id == block_id:
				return block
		return None

	def find_actor_by_name(self, name: str) -> Actor | None:
		"""按名称查找角色"""
		for actor in self.actors.values():
			if actor.name == name:
				return actor
		return None

	def find_scene_by_name(self, name: str) -> Scene | None:
		"""按名称查找场景"""
		for scene in self.scenes.values():
			if scene.name == name:
				return scene
		return None

	def analyze_project(self) -> dict[str, Any]:
		"""分析项目结构"""
		all_blocks = self.get_all_blocks()
		# 统计块类型
		block_type_counts: dict[str, int] = {}
		for block in all_blocks:
			block_type_counts[block.type] = block_type_counts.get(block.type, 0) + 1
		# 分类统计
		category_counts: dict[str, int] = {}
		for category in BlockCategory:
			category_counts[category.value] = 0
		for block_type, count in block_type_counts.items():
			# 简单的分类判断逻辑
			if "on_" in block_type or "when_" in block_type or "start_" in block_type:
				category_counts[BlockCategory.EVENT.value] += count
			elif "controls_" in block_type or "repeat_" in block_type or "wait_" in block_type:
				category_counts[BlockCategory.CONTROL.value] += count
			elif "self_move" in block_type or "self_go" in block_type:
				category_counts[BlockCategory.MOTION.value] += count
			elif "self_dialog" in block_type or "create_stage_dialog" in block_type:
				category_counts[BlockCategory.APPEARANCE.value] += count
			elif "play_audio" in block_type or "stop_audio" in block_type:
				category_counts[BlockCategory.AUDIO.value] += count
			elif "get_" in block_type or "check_" in block_type:
				category_counts[BlockCategory.SENSING.value] += count
			elif "math_" in block_type or "logic_" in block_type:
				category_counts[BlockCategory.OPERATOR.value] += count
			elif "variables_" in block_type:
				category_counts[BlockCategory.VARIABLE.value] += count
			elif block_type == "math_number":
				category_counts[BlockCategory.MATH.value] += count
			elif block_type == "text":
				category_counts[BlockCategory.TEXT.value] += count
		# 统计影子积木
		shadow_count = sum(len(block.shadows) for block in all_blocks)
		return {
			"project_name": self.project_name,
			"version": self.version,
			"tool_type": self.tool_type,
			"scenes_count": len(self.scenes),
			"actors_count": len(self.actors),
			"variables_count": len(self.variables),
			"audios_count": len(self.audios),
			"styles_count": len(self.styles),
			"total_blocks": len(all_blocks),
			"shadow_blocks": shadow_count,
			"block_type_counts": block_type_counts,
			"category_counts": category_counts,
		}

	def print_summary(self) -> None:
		"""打印项目摘要"""
		analysis = self.analyze_project()
		print("=" * 60)
		print(f"项目名称: {analysis['project_name']}")
		print(f"项目版本: {analysis['version']}")
		print(f"工具类型: {analysis['tool_type']}")
		print("-" * 60)
		print(f"场景数量: {analysis['scenes_count']}")
		print(f"角色数量: {analysis['actors_count']}")
		print(f"变量数量: {analysis['variables_count']}")
		print(f"音频数量: {analysis['audios_count']}")
		print(f"样式数量: {analysis['styles_count']}")
		print("-" * 60)
		print(f"总积木数: {analysis['total_blocks']}")
		print(f"影子积木数: {analysis['shadow_blocks']}")
		print("=" * 60)
		# 显示块类型统计(前10种)
		if analysis["block_type_counts"]:
			print("\n积木类型统计(前10种):")
			sorted_types = sorted(
				analysis["block_type_counts"].items(),
				key=operator.itemgetter(1),
				reverse=True,
			)[:10]
			for block_type, count in sorted_types:
				print(f"  {block_type}: {count}")

	def to_xml(self) -> str:
		"""将整个项目转换为XML格式"""
		root = ET.Element("project")
		root.set("name", self.project_name)
		root.set("version", self.version)
		root.set("toolType", self.tool_type)
		# 添加场景
		scenes_elem = ET.SubElement(root, "scenes")
		for scene_id, scene in self.scenes.items():
			scene_elem = ET.SubElement(scenes_elem, "scene")
			scene_elem.set("id", scene_id)
			scene_elem.set("name", scene.name)
			# 添加场景的积木
			blocks_elem = ET.SubElement(scene_elem, "blocks")
			for block in scene.blocks:
				block_xml = block.to_xml(
					include_shadows=True,
					include_location=True,
				)
				block_elem = ET.fromstring(block_xml)  # noqa: S314
				blocks_elem.append(block_elem)
		# 添加角色
		actors_elem = ET.SubElement(root, "actors")
		for actor_id, actor in self.actors.items():
			actor_elem = ET.SubElement(actors_elem, "actor")
			actor_elem.set("id", actor_id)
			actor_elem.set("name", actor.name)
			# 添加角色的积木
			blocks_elem = ET.SubElement(actor_elem, "blocks")
			for block in actor.blocks:
				block_xml = block.to_xml(
					include_shadows=True,
					include_location=True,
				)
				block_elem = ET.fromstring(block_xml)  # noqa: S314
				blocks_elem.append(block_elem)
		return ET.tostring(root, encoding="unicode", xml_declaration=True)


# ============================================================================
# Python操作接口类
# ============================================================================
class KNEditor:
	"""KN项目编辑器(Python操作接口)"""

	def __init__(self, project: KNProject | None = None) -> None:
		self.project = project or KNProject()
		self.current_actor_id: str | None = None
		self.current_scene_id: str | None = None

	def load_project(self, filepath: str | Path) -> None:
		"""加载项目文件"""
		self.project = KNProject.load_from_file(filepath)
		print(f"已加载项目: {self.project.project_name}")

	def import_from_xml_file(self, filepath: str | Path) -> None:
		"""从XML文件导入项目"""
		with Path(filepath).open(encoding="utf-8") as f:
			xml_content = f.read()
		self.project = KNProject.from_xml(xml_content)
		print(f"已从XML导入项目: {self.project.project_name}")

	def save_project(self, filepath: str | Path | None = None) -> None:
		"""保存项目文件"""
		self.project.save_to_file(filepath)

	def select_actor(self, actor_id: str) -> bool:
		"""选择角色"""
		if actor_id in self.project.actors:
			self.current_actor_id = actor_id
			self.current_scene_id = None
			return True
		return False

	def select_actor_by_name(self, name: str) -> bool:
		"""按名称选择角色"""
		actor = self.project.find_actor_by_name(name)
		if actor is not None:
			self.current_actor_id = actor.id
			self.current_scene_id = None
			return True
		return False

	def select_scene(self, scene_id: str) -> bool:
		"""选择场景"""
		if scene_id in self.project.scenes:
			self.current_scene_id = scene_id
			self.current_actor_id = None
			return True
		return False

	def select_scene_by_name(self, name: str) -> bool:
		"""按名称选择场景"""
		scene = self.project.find_scene_by_name(name)
		if scene is not None:
			self.current_scene_id = scene.id
			self.current_actor_id = None
			return True
		return False

	def get_current_entity(self) -> tuple[str, Actor | Scene | None]:
		"""获取当前选择的实体"""
		if self.current_actor_id is not None:
			actor = self.project.actors.get(self.current_actor_id)
			return ("actor", actor)
		if self.current_scene_id is not None:
			scene = self.project.scenes.get(self.current_scene_id)
			return ("scene", scene)
		return ("none", None)

	def add_block(self, block_type: str, **kwargs: Any) -> Block | None:
		"""添加代码块到当前选择的实体"""
		entity_type, entity = self.get_current_entity()
		if entity is None:
			print("错误: 没有选择任何实体")
			return None
		block = Block(type=block_type, **kwargs)
		if entity_type == "actor":
			actor = cast("Actor", entity)
			actor.blocks.append(block)
			self.project.workspace.add_block(block)
		elif entity_type == "scene":
			scene = cast("Scene", entity)
			scene.blocks.append(block)
			self.project.workspace.add_block(block)
		return block

	def export_to_xml_file(self, filepath: str | Path) -> None:
		"""导出项目为XML文件"""
		xml_content = self.project.to_xml()
		with Path(filepath).open("w", encoding="utf-8") as f:
			f.write(xml_content)
		print(f"项目已导出为XML: {filepath}")

	def print_project_info(self) -> None:
		"""打印项目信息"""
		self.project.print_summary()


def main() -> None:  # noqa: PLR0915
	"""主函数 - 交互式KN项目编辑器"""
	print("=" * 60)
	print("KN项目编辑器")
	print("=" * 60)
	editor = KNEditor()

	def handle_menu_choice(choice: str) -> bool:  # noqa: PLR0912, PLR0915
		"""处理菜单选择"""
		if choice == "1":
			project_name = input("请输入项目名称: ").strip()
			editor.project = KNProject(project_name)
			print(f"已创建新项目: {project_name}")
		elif choice == "2":
			filepath = input("请输入项目文件路径 (.bcmkn): ").strip()
			try:
				editor.load_project(filepath)
			except Exception as e:
				print(f"加载失败: {e}")
		elif choice == "3":
			if editor.project.filepath:
				save_path = input(f"保存路径 [{editor.project.filepath}]: ").strip()
				if not save_path:
					save_path = editor.project.filepath
			else:
				save_path = input("请输入保存路径: ").strip()
			try:
				editor.save_project(save_path)
			except Exception as e:
				print(f"保存失败: {e}")
		elif choice == "4":
			if editor.project:
				editor.print_project_info()
			else:
				print("请先加载或创建项目")
		elif choice == "5":
			if editor.project:
				analysis = editor.project.analyze_project()
				print("\n" + "=" * 60)
				print("项目详细分析:")
				print("=" * 60)
				for key, value in analysis.items():
					if key in {"block_type_counts", "category_counts"}:
						print(f"\n{key}:")
						for sub_key, sub_value in value.items():
							print(f"  {sub_key}: {sub_value}")
					else:
						print(f"{key}: {value}")
			else:
				print("请先加载或创建项目")
		elif choice == "6":
			handle_scene_management()
		elif choice == "7":
			handle_actor_management()
		elif choice == "8":
			handle_block_management()
		elif choice == "9":
			handle_resource_management()
		elif choice == "10":
			handle_export_xml()
		elif choice == "11":
			handle_create_example()
		elif choice == "12":
			handle_search()
		elif choice == "13":
			print("感谢使用,再见!")
			return False
		else:
			print("无效选项,请重新选择")
		return True

	def handle_scene_management() -> None:
		"""处理场景管理"""
		if not editor.project:
			print("请先加载或创建项目")
			return
		print("\n场景管理:")
		print(" 1. 添加场景")
		print(" 2. 查看所有场景")
		print(" 3. 选择当前场景")
		print(" 4. 添加积木到场景")
		sub_choice = input("请选择: ").strip()
		if sub_choice == "1":
			name = input("场景名称: ").strip()
			screen_name = input("屏幕名称 [默认: 屏幕]: ").strip()
			if not screen_name:
				screen_name = "屏幕"
			scene_id = editor.project.add_scene(name, screen_name)
			print(f"已添加场景: {name} (ID: {scene_id})")
		elif sub_choice == "2":
			print("\n所有场景:")
			for scene_id, scene in editor.project.scenes.items():
				print(f"  ID: {scene_id}, 名称: {scene.name}, 角色数: {len(scene.actor_ids)}")
		elif sub_choice == "3":
			scene_name = input("请输入场景名称: ").strip()
			if editor.select_scene_by_name(scene_name):
				print(f"已选择场景: {scene_name}")
			else:
				print("场景未找到")
		elif sub_choice == "4":
			if not editor.current_scene_id:
				print("请先选择场景")
				return
			block_type = input("积木类型: ").strip()
			try:
				block = editor.add_block(block_type)
				if block:
					print(f"已添加积木: {block_type} (ID: {block.id})")
			except Exception as e:
				print(f"添加失败: {e}")

	def handle_actor_management() -> None:
		"""处理角色管理"""
		if not editor.project:
			print("请先加载或创建项目")
			return
		print("\n角色管理:")
		print(" 1. 添加角色")
		print(" 2. 查看所有角色")
		print(" 3. 选择当前角色")
		print(" 4. 添加积木到角色")
		sub_choice = input("请选择: ").strip()
		if sub_choice == "1":
			name = input("角色名称: ").strip()
			x = input("X坐标 [默认: 0]: ").strip()
			y = input("Y坐标 [默认: 0]: ").strip()
			position = {"x": 0.0, "y": 0.0}
			if x:
				with contextlib.suppress(ValueError):
					position["x"] = float(x)
			if y:
				with contextlib.suppress(ValueError):
					position["y"] = float(y)
			actor_id = editor.project.add_actor(name, position)
			print(f"已添加角色: {name} (ID: {actor_id})")
		elif sub_choice == "2":
			print("\n所有角色:")
			for actor_id, actor in editor.project.actors.items():
				print(f"  ID: {actor_id}, 名称: {actor.name}, 位置: ({actor.position['x']}, {actor.position['y']})")
		elif sub_choice == "3":
			actor_name = input("请输入角色名称: ").strip()
			if editor.select_actor_by_name(actor_name):
				print(f"已选择角色: {actor_name}")
			else:
				print("角色未找到")
		elif sub_choice == "4":
			if not editor.current_actor_id:
				print("请先选择角色")
				return
			block_type = input("积木类型: ").strip()
			try:
				block = editor.add_block(block_type)
				if block:
					print(f"已添加积木: {block_type} (ID: {block.id})")
			except Exception as e:
				print(f"添加失败: {e}")

	def handle_block_management() -> None:
		"""处理积木管理"""
		if not editor.project:
			print("请先加载或创建项目")
			return
		print("\n积木管理:")
		print(" 1. 查看所有积木")
		print(" 2. 查找积木")
		sub_choice = input("请选择: ").strip()
		if sub_choice == "1":
			all_blocks = editor.project.get_all_blocks()
			print(f"\n总积木数: {len(all_blocks)}")
			print("前10个积木:")
			for i, block in enumerate(all_blocks[:10]):
				print(f"  {i + 1}. ID: {block.id}, 类型: {block.type}")
		elif sub_choice == "2":
			block_id = input("请输入积木ID: ").strip()
			block = editor.project.find_block(block_id)
			if block:
				print(f"找到积木: ID={block.id}, 类型={block.type}")
				print(f"字段: {block.fields}")
			else:
				print("积木未找到")

	def handle_resource_management() -> None:
		"""处理资源管理"""
		if not editor.project:
			print("请先加载或创建项目")
			return
		print("\n资源管理:")
		print(" 1. 添加变量")
		print(" 2. 添加音频")
		print(" 3. 查看所有资源")
		sub_choice = input("请选择: ").strip()
		if sub_choice == "1":
			name = input("变量名称: ").strip()
			value = input("初始值 [默认: 0]: ").strip()
			if not value:
				value = 0
			var_id = editor.project.add_variable(name, value)
			print(f"已添加变量: {name} (ID: {var_id})")
		elif sub_choice == "2":
			name = input("音频名称: ").strip()
			url = input("音频URL [可选]: ").strip()
			audio_id = editor.project.add_audio(name, url)
			print(f"已添加音频: {name} (ID: {audio_id})")
		elif sub_choice == "3":
			print("\n变量:")
			for var in editor.project.variables.values():
				print(f"  {var.get('name', 'Unknown')}: {var.get('value', 'N/A')}")

	def handle_export_xml() -> None:
		"""处理XML导出"""
		if not editor.project:
			print("请先加载或创建项目")
			return
		filepath = input("请输入XML导出路径: ").strip()
		try:
			editor.export_to_xml_file(filepath)
		except Exception as e:
			print(f"导出失败: {e}")

	def handle_create_example() -> None:
		"""处理创建示例程序"""
		if not editor.project:
			print("请先创建或加载项目")
			return
		actor_name = input("角色名称 [默认: 角色1]: ").strip()
		if not actor_name:
			actor_name = "角色1"
		scene_name = input("场景名称 [默认: 场景1]: ").strip()
		if not scene_name:
			scene_name = "场景1"
		try:
			editor.project.create_simple_program(actor_name, scene_name)
			print("示例程序已创建")
		except Exception as e:
			print(f"创建失败: {e}")

	def handle_search() -> None:
		"""处理查找功能"""
		if not editor.project:
			print("请先加载或创建项目")
			return
		search_type = input("查找类型 (block/actor/scene): ").strip().lower()
		if search_type == "block":
			search_term = input("请输入积木ID或类型关键词: ").strip()
			all_blocks = editor.project.get_all_blocks()
			found = [b for b in all_blocks if search_term in b.id or search_term in b.type]
			print(f"找到 {len(found)} 个积木")
			for block in found[:5]:
				print(f"  ID: {block.id}, 类型: {block.type}")
		elif search_type == "actor":
			search_term = input("请输入角色名称: ").strip()
			actor = editor.project.find_actor_by_name(search_term)
			if actor:
				print(f"找到角色: {actor.name} (ID: {actor.id})")
			else:
				print("角色未找到")
		elif search_type == "scene":
			search_term = input("请输入场景名称: ").strip()
			scene = editor.project.find_scene_by_name(search_term)
			if scene:
				print(f"找到场景: {scene.name} (ID: {scene.id})")
			else:
				print("场景未找到")

	# 主循环
	while True:
		print("\n请选择操作:")
		print(" 1. 创建新项目")
		print(" 2. 加载项目文件")
		print(" 3. 保存项目")
		print(" 4. 显示项目摘要")
		print(" 5. 分析项目结构")
		print(" 6. 管理场景")
		print(" 7. 管理角色")
		print(" 8. 管理积木")
		print(" 9. 管理变量/函数/音频")
		print("10. 导出为XML格式")
		print("11. 创建示例程序")
		print("12. 查找积木/角色/场景")
		print("13. 退出")
		choice = input("请输入选项 (1-13): ").strip()
		if not handle_menu_choice(choice):
			break


if __name__ == "__main__":
	main()
