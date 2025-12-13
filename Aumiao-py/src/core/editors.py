from __future__ import annotations

import json
import operator
import re
import uuid
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from dataclasses import dataclass, field
from html import unescape
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar, cast

from src.core.base import BLOCK_CONFIG, DEFAULT_PROJECT_CONFIG, BlockCategory, BlockType, ColorFormat, ConnectionType, ShadowCategory, ShadowType

if TYPE_CHECKING:
	from collections.abc import Callable
T = TypeVar("T")
U = TypeVar("U")


class TypeChecker:
	"""类型检查工具"""

	@staticmethod
	def is_valid_color(color_str: str) -> bool:
		"""检查是否为有效颜色字符串"""
		if not color_str:
			return False
		if color_str.startswith("#"):
			hex_part = color_str[1:]
			return len(hex_part) in {3, 4, 6, 8} and all(c in "0123456789ABCDEFabcdef" for c in hex_part)
		if color_str.startswith("rgba("):
			match = re.match(r"rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)", color_str)
			if match:
				try:
					r, g, b, a = match.groups()
					return all([0 <= int(r) <= 255, 0 <= int(g) <= 255, 0 <= int(b) <= 255, 0 <= float(a) <= 1])
				except (ValueError, TypeError):
					return False
		if color_str.startswith("rgb("):
			match = re.match(r"rgb\((\d+),\s*(\d+),\s*(\d+)\)", color_str)
			if match:
				try:
					r, g, b = match.groups()
					return all([0 <= int(r) <= 255, 0 <= int(g) <= 255, 0 <= int(b) <= 255])
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

	@staticmethod
	def is_valid_uuid(value: str) -> bool:
		"""检查是否为有效UUID"""
		try:
			uuid.UUID(value)
		except (ValueError, TypeError, AttributeError):
			return False
		else:
			return True


class JSONConverter:
	"""JSON转换工具(类型安全)"""

	@staticmethod
	def ensure_dict(obj: Any, default: dict[str, Any] | None = None) -> dict[str, Any]:
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

	@staticmethod
	def ensure_uuid(obj: Any, default: str = "") -> str:
		"""确保对象是有效UUID"""
		if isinstance(obj, str) and TypeChecker.is_valid_uuid(obj):
			return obj
		return default or str(uuid.uuid4())


# ============================================================================
# Repository模式实现 - 增强版
# ============================================================================
class BlockRepository:
	"""
	增强版积木仓库
	支持高效的按类型、父级、位置、分类查找,减少重复遍历
	"""

	def __init__(self) -> None:
		self._blocks_by_id: dict[str, Block] = {}
		self._blocks_by_type: dict[str, list[Block]] = defaultdict(list)
		self._blocks_by_parent: dict[str, list[Block]] = defaultdict(list)
		self._blocks_by_category: dict[BlockCategory, list[Block]] = defaultdict(list)
		self._blocks_by_location_index: dict[tuple[int, int], list[Block]] = defaultdict(list)
		self._location_grid_size: int = 50  # 位置网格大小

	def _get_grid_key(self, x: float, y: float) -> tuple[int, int]:
		"""获取位置网格键"""
		grid_x = int(x // self._location_grid_size)
		grid_y = int(y // self._location_grid_size)
		return (grid_x, grid_y)

	def add(self, block: Block) -> None:
		"""添加积木到仓库"""
		if block.id in self._blocks_by_id:
			self.remove(block.id)
		self._blocks_by_id[block.id] = block
		self._blocks_by_type[block.type].append(block)
		if block.parent_id:
			self._blocks_by_parent[block.parent_id].append(block)
		# 按分类索引
		config = BLOCK_CONFIG.get(BlockType(block.type), {})
		category = config.get("category")
		if category:
			self._blocks_by_category[category].append(block)
		# 按位置索引
		if block.location and len(block.location) >= 2:
			grid_key = self._get_grid_key(block.location[0], block.location[1])
			self._blocks_by_location_index[grid_key].append(block)

	def remove(self, block_id: str) -> bool:
		"""从仓库移除积木"""
		if block_id not in self._blocks_by_id:
			return False
		block = self._blocks_by_id[block_id]
		# 从所有索引中移除
		if block.type in self._blocks_by_type:
			type_list = self._blocks_by_type[block.type]
			for i, b in enumerate(type_list):
				if b.id == block_id:
					type_list.pop(i)
					break
		if block.parent_id and block.parent_id in self._blocks_by_parent:
			parent_list = self._blocks_by_parent[block.parent_id]
			for i, b in enumerate(parent_list):
				if b.id == block_id:
					parent_list.pop(i)
					break
		config = BLOCK_CONFIG.get(BlockType(block.type), {})
		category = config.get("category")
		if category and category in self._blocks_by_category:
			category_list = self._blocks_by_category[category]
			for i, b in enumerate(category_list):
				if b.id == block_id:
					category_list.pop(i)
					break
		if block.location and len(block.location) >= 2:
			grid_key = self._get_grid_key(block.location[0], block.location[1])
			if grid_key in self._blocks_by_location_index:
				location_list = self._blocks_by_location_index[grid_key]
				for i, b in enumerate(location_list):
					if b.id == block_id:
						location_list.pop(i)
						break
		del self._blocks_by_id[block_id]
		return True

	def get_by_id(self, block_id: str) -> Block | None:
		"""根据ID获取积木"""
		return self._blocks_by_id.get(block_id)

	def get_by_type(self, block_type: str) -> list[Block]:
		"""根据类型获取积木"""
		return self._blocks_by_type.get(block_type, []).copy()

	def get_by_parent(self, parent_id: str) -> list[Block]:
		"""根据父级ID获取积木"""
		return self._blocks_by_parent.get(parent_id, []).copy()

	def get_by_category(self, category: BlockCategory) -> list[Block]:
		"""根据分类获取积木"""
		return self._blocks_by_category.get(category, []).copy()

	def find_by_location(self, x: float, y: float, radius: float = 10.0) -> list[Block]:
		"""根据位置查找附近的积木(使用空间索引优化)"""
		result = []
		# 计算搜索的网格范围
		min_grid_x = int((x - radius) // self._location_grid_size)
		max_grid_x = int((x + radius) // self._location_grid_size)
		min_grid_y = int((y - radius) // self._location_grid_size)
		max_grid_y = int((y + radius) // self._location_grid_size)
		for grid_x in range(min_grid_x, max_grid_x + 1):
			for grid_y in range(min_grid_y, max_grid_y + 1):
				grid_key = (grid_x, grid_y)
				if grid_key in self._blocks_by_location_index:
					for block in self._blocks_by_location_index[grid_key]:
						if block.location and len(block.location) >= 2:
							block_x, block_y = block.location[:2]
							distance = ((block_x - x) ** 2 + (block_y - y) ** 2) ** 0.5
							if distance <= radius:
								result.append(block)
		return result

	def find_by_criteria(self, criteria_func: Callable[[Block], bool]) -> list[Block]:
		"""根据自定义条件查找积木"""
		return [block for block in self._blocks_by_id.values() if criteria_func(block)]

	def find_connected_blocks(self, start_block_id: str) -> list[Block]:
		"""查找与指定积木相连的所有积木(BFS搜索)"""
		result = []
		visited = set()
		queue = deque([start_block_id])
		while queue:
			current_id = queue.popleft()
			if current_id in visited:
				continue
			visited.add(current_id)
			block = self.get_by_id(current_id)
			if block:
				result.append(block)
				# 查找通过inputs连接的积木
				for input_data in block.inputs.values():
					if isinstance(input_data, dict) and "id" in input_data:
						queue.append(input_data["id"])
				# 查找通过statements连接的积木
				for stmt_data in block.statements.values():
					if isinstance(stmt_data, dict) and "id" in stmt_data:
						queue.append(stmt_data["id"])
				# 查找通过next连接的积木
				if block.next and isinstance(block.next, dict) and "id" in block.next:
					queue.append(block.next["id"])
		return result

	def clear(self) -> None:
		"""清空仓库"""
		self._blocks_by_id.clear()
		self._blocks_by_type.clear()
		self._blocks_by_parent.clear()
		self._blocks_by_category.clear()
		self._blocks_by_location_index.clear()

	def get_all(self) -> list[Block]:
		"""获取所有积木"""
		return list(self._blocks_by_id.values())

	def count(self) -> int:
		"""获取积木总数"""
		return len(self._blocks_by_id)

	def get_statistics(self) -> dict[str, Any]:
		"""获取仓库统计信息"""
		return {
			"total_blocks": self.count(),
			"blocks_by_type": {k: len(v) for k, v in self._blocks_by_type.items()},
			"blocks_by_category": {k.value: len(v) for k, v in self._blocks_by_category.items()},
			"blocks_with_parent": sum(1 for b in self._blocks_by_id.values() if b.parent_id),
			"blocks_with_location": sum(1 for b in self._blocks_by_id.values() if b.location),
		}


# ============================================================================
# Builder模式实现 - 增强版
# ============================================================================
class BlockBuilder:
	"""
	增强版积木构建器
	提供完整的链式API,支持复杂积木创建
	"""

	def __init__(self, block_type: str) -> None:
		self._block = Block(type=block_type)
		self._config = BLOCK_CONFIG.get(BlockType(block_type), {})

	def with_id(self, block_id: str) -> BlockBuilder:
		"""设置积木ID"""
		self._block.id = JSONConverter.ensure_uuid(block_id)
		return self

	def with_location(self, x: float, y: float) -> BlockBuilder:
		"""设置位置"""
		self._block.location = [float(x), float(y)]
		return self

	def with_field(self, name: str, value: Any) -> BlockBuilder:
		"""添加字段"""
		self._block.fields[name] = value
		return self

	def with_fields(self, **fields: Any) -> BlockBuilder:
		"""批量添加字段"""
		self._block.fields.update(fields)
		return self

	def with_input(self, name: str, input_type: str, input_value: Any = None, **kwargs: Any) -> BlockBuilder:
		"""添加输入"""
		if isinstance(input_value, Block):
			input_dict = input_value.to_dict()
		elif isinstance(input_value, BlockBuilder):
			input_dict = input_value.build().to_dict()
		elif input_value is not None:
			input_dict = {"type": input_type, "fields": kwargs.get("fields", {"TEXT": input_value} if input_value is not None else {})}
			if "id" in kwargs:
				input_dict["id"] = kwargs["id"]
		else:
			input_dict = {"type": input_type, "fields": kwargs.get("fields", {})}
			if "id" in kwargs:
				input_dict["id"] = kwargs["id"]
		self._block.inputs[name] = input_dict
		return self

	def with_input_builder(self, name: str, builder: BlockBuilder) -> BlockBuilder:
		"""使用Builder添加输入"""
		block = builder.build()
		self._block.inputs[name] = block.to_dict()
		return self

	def with_shadow(self, name: str, _shadow_type: str, shadow_value: Any = None, **kwargs: Any) -> BlockBuilder:
		"""添加影子积木"""
		if shadow_value is None and "xml_string" in kwargs:
			shadow_xml = kwargs["xml_string"]
		elif shadow_value is not None:
			shadow_xml = shadow_value.xml_string if isinstance(shadow_value, ShadowXML) else str(shadow_value)
		else:
			shadow_xml = ""
		self._block.shadows[name] = shadow_xml
		return self

	def with_parent(self, parent_id: str) -> BlockBuilder:
		"""设置父级ID"""
		self._block.parent_id = parent_id
		return self

	def with_mutation(self, mutation: str) -> BlockBuilder:
		"""设置mutation"""
		self._block.mutation = mutation
		return self

	def with_next(self, next_block: Block | BlockBuilder | dict) -> BlockBuilder:
		"""设置下一个积木"""
		if isinstance(next_block, Block):
			self._block.next = next_block.to_dict()
		elif isinstance(next_block, BlockBuilder):
			self._block.next = next_block.build().to_dict()
		elif isinstance(next_block, dict):
			self._block.next = next_block
		return self

	def with_statement(self, name: str, statement: Block | BlockBuilder | dict) -> BlockBuilder:
		"""添加语句块"""
		if isinstance(statement, Block):
			self._block.statements[name] = statement.to_dict()
		elif isinstance(statement, BlockBuilder):
			self._block.statements[name] = statement.build().to_dict()
		elif isinstance(statement, dict):
			self._block.statements[name] = statement
		return self

	def with_property(self, property_name: str, value: Any) -> BlockBuilder:
		"""设置属性"""
		if property_name == "shield":
			self._block.shield = bool(value)
		elif property_name == "is_output":
			self._block.is_output = bool(value)
		elif property_name == "is_shadow":
			self._block.is_shadow = bool(value)
		elif property_name == "collapsed":
			self._block.collapsed = bool(value)
		elif property_name == "disabled":
			self._block.disabled = bool(value)
		elif property_name == "deletable":
			self._block.deletable = bool(value)
		elif property_name == "movable":
			self._block.movable = bool(value)
		elif property_name == "editable":
			self._block.editable = bool(value)
		elif property_name == "visible":
			self._block.visible = str(value)
		return self

	def build(self) -> Block:
		"""构建积木"""
		# 应用默认配置
		config = self._config
		if config and "color" in config and "color" not in self._block.field_extra_attr:
			self._block.field_extra_attr["color"] = config["color"]
		return self._block

	# 工厂方法 - 常用积木
	@classmethod
	def create_move_to_block(cls, x: float, y: float, **kwargs: Any) -> Block:
		"""创建移动到指定位置的积木"""
		builder = cls(BlockType.SELF_MOVE_TO.value)
		builder.with_input("X", BlockType.MATH_NUMBER.value, str(x))
		builder.with_input("Y", BlockType.MATH_NUMBER.value, str(y))
		for key, value in kwargs.items():
			if key == "location":
				builder.with_location(value[0], value[1])
			elif key.startswith("field_"):
				field_name = key[6:]
				builder.with_field(field_name, value)
			elif key == "id":
				builder.with_id(value)
		return builder.build()

	@classmethod
	def create_say_block(cls, text: str, **kwargs: Any) -> Block:
		"""创建说话积木"""
		builder = cls(BlockType.SELF_DIALOG.value)
		builder.with_input("TEXT", BlockType.TEXT.value, text)
		for key, value in kwargs.items():
			if key == "location":
				builder.with_location(value[0], value[1])
			elif key.startswith("field_"):
				field_name = key[6:]
				builder.with_field(field_name, value)
			elif key == "id":
				builder.with_id(value)
		return builder.build()

	@classmethod
	def create_wait_block(cls, seconds: float, **kwargs: Any) -> Block:
		"""创建等待积木"""
		builder = cls(BlockType.WAIT.value)
		builder.with_input("SECONDS", BlockType.MATH_NUMBER.value, str(seconds))
		for key, value in kwargs.items():
			if key == "location":
				builder.with_location(value[0], value[1])
			elif key.startswith("field_"):
				field_name = key[6:]
				builder.with_field(field_name, value)
			elif key == "id":
				builder.with_id(value)
		return builder.build()

	@classmethod
	def create_if_block(cls, condition: Block, then_block: Block, else_block: Block | None = None, **kwargs: Any) -> Block:
		"""创建条件判断积木"""
		builder = cls(BlockType.CONTROLS_IF_ELSE.value)
		# 直接使用Block对象,而不是尝试转换为BlockBuilder
		if isinstance(condition, Block):
			builder.with_input("IF0", condition.type, condition.fields.get("TEXT", ""))
		if isinstance(then_block, Block):
			builder.with_input("DO0", then_block.type, then_block.fields.get("TEXT", ""))
		if else_block and isinstance(else_block, Block):
			builder.with_input("ELSE", else_block.type, else_block.fields.get("TEXT", ""))
		for key, value in kwargs.items():
			if key == "location":
				builder.with_location(value[0], value[1])
			elif key.startswith("field_"):
				field_name = key[6:]
				builder.with_field(field_name, value)
			elif key == "id":
				builder.with_id(value)
		return builder.build()

	@classmethod
	def create_compare_block(cls, left_value: Any, right_value: Any, operator: str = "EQ", **kwargs: Any) -> Block:
		"""创建比较积木"""
		builder = cls(BlockType.LOGIC_COMPARE.value)
		builder.with_field("OP", operator)
		# 根据值类型创建输入
		if isinstance(left_value, (int, float, str)):
			builder.with_input("A", BlockType.MATH_NUMBER.value, str(left_value))
		elif isinstance(left_value, Block):
			# 将Block对象转换为BlockBuilder
			builder.with_input_builder("A", cls.from_block(left_value))
		if isinstance(right_value, (int, float, str)):
			builder.with_input("B", BlockType.MATH_NUMBER.value, str(right_value))
		elif isinstance(right_value, Block):
			# 将Block对象转换为BlockBuilder
			builder.with_input_builder("B", cls.from_block(right_value))
		for key, value in kwargs.items():
			if key == "location":
				builder.with_location(value[0], value[1])
			elif key.startswith("field_"):
				field_name = key[6:]
				builder.with_field(field_name, value)
			elif key == "id":
				builder.with_id(value)
		return builder.build()

	@classmethod
	def create_number_block(cls, value: float, **kwargs: Any) -> Block:
		"""创建数字积木"""
		builder = cls(BlockType.MATH_NUMBER.value)
		builder.with_field("NUM", str(value))
		for key, val in kwargs.items():
			if key == "location":
				builder.with_location(val[0], val[1])
			elif key == "id":
				builder.with_id(val)
		return builder.build()

	@classmethod
	def create_text_block(cls, text: str, **kwargs: Any) -> Block:
		"""创建文本积木"""
		builder = cls(BlockType.TEXT.value)
		builder.with_field("TEXT", text)
		for key, val in kwargs.items():
			if key == "location":
				builder.with_location(val[0], val[1])
			elif key == "id":
				builder.with_id(val)
		return builder.build()

	@classmethod
	def from_block(cls, block: Block) -> BlockBuilder:
		"""从现有积木创建Builder"""
		builder = cls(block.type)
		builder._block = block
		return builder


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
			self.r = 0
			self.g = 0
			self.b = 0
			self.a = 1.0

	def set(self, color_str: str) -> bool:
		"""设置颜色值"""
		if not color_str:
			return False
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
		elif color_str.startswith("rgba("):
			match = re.match(r"rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)", color_str)
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
		elif color_str.startswith("rgb("):
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
			cleaned = unescape(xml_str)
			root = ET.fromstring(cleaned)
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

	def add_shadow_block(self, shadow_block: ShadowBlock, parent_id: str | None = None) -> str:
		"""添加影子积木"""
		self.shadow_blocks[shadow_block.id] = shadow_block
		if parent_id is not None:
			shadow_block.parent_id = parent_id
			if parent_id not in self.parent_child_map:
				self.parent_child_map[parent_id] = []
			self.parent_child_map[parent_id].append(shadow_block.id)
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
		if parent_id is not None and parent_id in self.parent_child_map:
			if shadow_id in self.parent_child_map[parent_id]:
				self.parent_child_map[parent_id].remove(shadow_id)
			if not self.parent_child_map[parent_id]:
				del self.parent_child_map[parent_id]
		if parent_id is not None and parent_id in self.input_shadow_map:
			if shadow_block.input_name is not None and shadow_block.input_name in self.input_shadow_map[parent_id]:
				del self.input_shadow_map[parent_id][shadow_block.input_name]
			if not self.input_shadow_map[parent_id]:
				del self.input_shadow_map[parent_id]
		del self.shadow_blocks[shadow_id]
		return True

	def get_shadows_by_parent(self, parent_id: str) -> list[ShadowBlock]:
		"""获取父积木的所有影子积木"""
		if parent_id not in self.parent_child_map:
			return []
		shadows: list[ShadowBlock] = [self.shadow_blocks[shadow_id] for shadow_id in self.parent_child_map[parent_id] if shadow_id in self.shadow_blocks]
		return shadows

	def get_input_shadow(self, parent_id: str, input_name: str) -> ShadowBlock | None:
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
		for shadow_id, shadow_data in JSONConverter.ensure_dict(data.get("shadow_blocks")).items():
			shadow_block = ShadowBlock.from_dict(shadow_data)
			manager.shadow_blocks[shadow_id] = shadow_block
		manager.parent_child_map = JSONConverter.ensure_dict(data.get("parent_child_map")).copy()
		manager.input_shadow_map = JSONConverter.ensure_dict(data.get("input_shadow_map")).copy()
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
	shadow_manager: ShadowManager | None = field(default_factory=lambda: None)
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
		if self.inputs:
			result["inputs"] = self.inputs.copy()
		if self.statements:
			result["statements"] = self.statements.copy()
		if self.next is not None:
			result["next"] = self.next
		return result

	@classmethod
	def from_dict(cls, data: dict[str, Any]) -> Block:
		"""从字典创建块 - 匹配KN实际JSON结构"""
		block_type = JSONConverter.ensure_str(data.get("type"))
		fields = JSONConverter.ensure_dict(data.get("fields"))
		if block_type in {"procedures_2_callnoreturn", "procedures_2_callreturn"}:
			return cls._create_procedure_call_block(data, block_type)
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
		inputs_data = data.get("inputs", {})
		if isinstance(inputs_data, dict):
			block.inputs.update(inputs_data)
		statements_data = data.get("statements", {})
		if isinstance(statements_data, dict):
			block.statements.update(statements_data)
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
		block.fields["procedure_id"] = procedure_id
		block.fields["params_info"] = params_info
		if "inputs" in data:
			inputs_dict = JSONConverter.ensure_dict(data.get("inputs"))
			block.inputs.update(inputs_dict)
		if data.get("next"):
			block.next = data["next"]
		return block

	@classmethod
	def _parse_procedure_mutation(cls, mutation_xml: str) -> dict[str, Any]:
		"""解析过程调用的mutation XML"""
		if not mutation_xml:
			return {}
		try:
			root = ET.fromstring(mutation_xml)
			result: dict[str, Any] = {
				"def_id": root.get("def_id", ""),
				"name": root.get("name", ""),
				"type": root.get("type", "NORMAL"),
				"args": [],
			}
			for arg_elem in root.findall("arg"):
				arg_info = {
					"id": arg_elem.get("id", ""),
					"content": arg_elem.get("content", ""),
					"type": arg_elem.get("type", ""),
				}
				result["args"].append(arg_info)
		except ET.ParseError:
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
			block = Block.from_dict(block_data)
			visited.add(block.id)
			blocks.append(block)
			for input_data in block.inputs.values():
				if isinstance(input_data, dict):
					collect_blocks(input_data)
			for stmt_data in block.statements.values():
				if isinstance(stmt_data, dict):
					collect_blocks(stmt_data)
			if block.next is not None and isinstance(block.next, dict):
				collect_blocks(block.next)

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

	def to_xml(self, *, include_shadows: bool = True, include_location: bool = True) -> str:
		"""转换为XML字符串"""
		root = ET.Element("shadow" if self.is_shadow else "block")
		root.set("type", self.type)
		root.set("id", self.id)
		if include_location and self.location is not None and len(self.location) >= 2:
			root.set("x", str(self.location[0]))
			root.set("y", str(self.location[1]))
		if self.mutation:
			try:
				mutation_elem = ET.fromstring(self.mutation)
				root.append(mutation_elem)
			except ET.ParseError:
				mutation_elem = ET.Element("mutation")
				root.append(mutation_elem)
		for field_name, field_value in self.fields.items():
			if field_value is not None:
				field_elem = ET.Element("field")
				field_elem.set("name", field_name)
				field_elem.text = str(field_value)
				root.append(field_elem)
		if include_shadows and self.shadows:
			for shadow_name, shadow_xml in self.shadows.items():
				if shadow_xml:
					try:
						shadow_elem = ET.fromstring(shadow_xml)
						shadow_elem.set("name", shadow_name)
						root.append(shadow_elem)
					except ET.ParseError:
						pass
		return ET.tostring(root, encoding="unicode", xml_declaration=False)

	@classmethod
	def from_xml(cls, xml_str: str) -> Block:
		"""从XML字符串创建积木块"""
		try:
			root = ET.fromstring(xml_str)
		except ET.ParseError as e:
			error_msg = f"XML解析错误: {e}"
			raise ValueError(error_msg) from e
		block_type = root.get("type", "")
		block_id = root.get("id", str(uuid.uuid4()))
		is_shadow = root.tag in {"shadow", "empty"}
		block = cls(
			id=block_id,
			type=block_type,
			is_shadow=is_shadow,
			editable=root.tag != "empty",
		)
		x = root.get("x")
		y = root.get("y")
		if x is not None and y is not None:
			try:
				block.location = [float(x), float(y)]
			except ValueError:
				block.location = [0.0, 0.0]
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
		mutation_elem = root.find("mutation")
		if mutation_elem is not None:
			block.mutation = ET.tostring(mutation_elem, encoding="unicode")
		for field_elem in root.findall("field"):
			field_name = field_elem.get("name")
			if field_name is not None and field_elem.text is not None:
				block.fields[field_name] = field_elem.text
		return block

	def add_shadow(self, shadow_block: ShadowBlock, input_name: str | None = None) -> str:
		"""添加影子积木"""
		shadow_block.parent_id = self.id
		shadow_block.input_name = input_name
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
			is_detachable=JSONConverter.ensure_bool(data.get("is_detachable", True)),
			is_replaceable=JSONConverter.ensure_bool(data.get("is_replaceable", True)),
			can_have_inputs=JSONConverter.ensure_bool(data.get("can_have_inputs", True)),
			can_be_replaced=JSONConverter.ensure_bool(data.get("can_be_replaced", True)),
			keeps_value=JSONConverter.ensure_bool(data.get("keeps_value", False)),
			default_value=data.get("default_value"),
			value_type=data.get("value_type"),
			field_constraints=JSONConverter.ensure_dict(data.get("field_constraints")),
			connection_constraints=JSONConverter.ensure_dict(data.get("connection_constraints")),
		)


# ============================================================================
# KN项目解析器(恢复旧版功能)
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
				KNProjectParser.parse_nested_structure(input_data, all_blocks_flat, block_id)
		# 递归处理statements
		statements = data.get("statements", {})
		for stmt_data in statements.values():
			if isinstance(stmt_data, dict):
				KNProjectParser.parse_nested_structure(stmt_data, all_blocks_flat, block_id)
		# 递归处理next
		next_data = data.get("next")
		if isinstance(next_data, dict):
			KNProjectParser.parse_nested_structure(next_data, all_blocks_flat, block_id)

	@staticmethod
	def build_blocks_from_flat(all_blocks_flat: dict[str, dict]) -> dict[str, Block]:
		"""从平面数据构建Block对象"""
		blocks = {}
		for block_id, block_data in all_blocks_flat.items():
			blocks[block_id] = Block.from_dict(block_data)
		return blocks

	@staticmethod
	def parse_project_structure(data: dict) -> dict[str, Any]:
		"""解析项目结构,提取所有积木"""
		all_blocks_flat: dict[str, dict] = {}
		# 解析场景积木
		scenes_data = JSONConverter.ensure_dict(data.get("scenes", {}))
		scenes_dict = JSONConverter.ensure_dict(scenes_data.get("scenesDict", {}))
		for scene_data in scenes_dict.values():
			blocks_list = JSONConverter.ensure_list(scene_data.get("nekoBlockJsonList", []))
			for block_data in blocks_list:
				if isinstance(block_data, dict):
					KNProjectParser.parse_nested_structure(block_data, all_blocks_flat)
		# 解析角色积木
		actors_data = JSONConverter.ensure_dict(data.get("actors", {}))
		actors_dict = JSONConverter.ensure_dict(actors_data.get("actorsDict", {}))
		for actor_data in actors_dict.values():
			blocks_list = JSONConverter.ensure_list(actor_data.get("nekoBlockJsonList", []))
			for block_data in blocks_list:
				if isinstance(block_data, dict):
					KNProjectParser.parse_nested_structure(block_data, all_blocks_flat)
		return all_blocks_flat


# ============================================================================
# 角色和场景类
# ============================================================================
@dataclass
class Actor:
	"""角色(增强版)"""

	id: str
	name: str
	position: dict[str, float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0})
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
			position=JSONConverter.ensure_dict(data.get("position", {"x": 0.0, "y": 0.0})),
			scale=JSONConverter.ensure_float(data.get("scale", 100.0)),
			rotation=JSONConverter.ensure_float(data.get("rotation", 0.0)),
			visible=JSONConverter.ensure_bool(data.get("visible", True)),
			locked=JSONConverter.ensure_bool(data.get("locked", False)),
			draggable=JSONConverter.ensure_bool(data.get("draggable", True)),
			rotation_type=JSONConverter.ensure_str(data.get("rotationType", "all around")),
			styles=JSONConverter.ensure_list(data.get("styles")),
			current_style_id=JSONConverter.ensure_str(data.get("currentStyleId")),
		)
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

	@staticmethod
	def add_move_block(x: float, y: float) -> Block:
		"""添加移动块"""
		return BlockBuilder.create_move_to_block(x, y)

	@staticmethod
	def add_say_block(text: str) -> Block:
		"""添加说话块"""
		return BlockBuilder.create_say_block(text)

	@staticmethod
	def add_wait_block(seconds: float) -> Block:
		"""添加等待块"""
		return BlockBuilder.create_wait_block(seconds)


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
			screen_name=JSONConverter.ensure_str(data.get("screenName", "屏幕")),
			styles=JSONConverter.ensure_list(data.get("styles")),
			actor_ids=JSONConverter.ensure_list(data.get("actorIds")),
			visible=JSONConverter.ensure_bool(data.get("visible", True)),
			current_style_id=JSONConverter.ensure_str(data.get("currentStyleId")),
			background_color=JSONConverter.ensure_str(data.get("backgroundColor", "#FFFFFF")),
			background_image=data.get("backgroundImage"),
		)
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
	connections: dict[str, dict[str, ConnectionJson]] = field(default_factory=dict)
	repository: BlockRepository = field(default_factory=BlockRepository)

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
		for block_id, block_data in JSONConverter.ensure_dict(data.get("blocks")).items():
			block = Block.from_dict(block_data)
			ws.blocks[block_id] = block
			ws.repository.add(block)
		for comment_id, comment_data in JSONConverter.ensure_dict(data.get("comments")).items():
			ws.comments[comment_id] = CommentJson.from_dict(comment_data)
		for block_id, target_conns in JSONConverter.ensure_dict(data.get("connections")).items():
			ws.connections[block_id] = {}
			for target_id, conn_data in JSONConverter.ensure_dict(target_conns).items():
				ws.connections[block_id][target_id] = ConnectionJson.from_dict(conn_data)
		return ws

	def add_block(self, block: Block) -> None:
		"""添加块"""
		self.blocks[block.id] = block
		self.repository.add(block)

	def remove_block(self, block_id: str) -> bool:
		"""移除块"""
		if block_id in self.blocks:
			del self.blocks[block_id]
			self.repository.remove(block_id)
			# 清理连接
			if block_id in self.connections:
				del self.connections[block_id]
			for source_id, target_conns in list(self.connections.items()):
				if block_id in target_conns:
					del target_conns[block_id]
				if not target_conns:
					del self.connections[source_id]
			return True
		return False

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

	def get_connected_blocks(self, block_id: str) -> list[Block]:
		"""获取与指定积木相连的所有积木"""
		return self.repository.find_connected_blocks(block_id)

	def get_statistics(self) -> dict[str, Any]:
		"""获取工作区统计信息"""
		repo_stats = self.repository.get_statistics()
		return {
			**repo_stats,
			"comments_count": len(self.comments),
			"connections_count": sum(len(conns) for conns in self.connections.values()),
		}


# ============================================================================
# KN项目主类 - 完整版
# ============================================================================
class KNProject:
	"""KN项目(完整重构版)"""

	def __init__(self, project_name: str = "未命名项目") -> None:
		self.project_name: str = project_name
		self.version: str = DEFAULT_PROJECT_CONFIG["version"]
		self.tool_type: str = DEFAULT_PROJECT_CONFIG["tool_type"]
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
		self.procedures: dict[str, Procedure | dict] = {}
		# 工作区数据
		self.workspace: WorkspaceData = WorkspaceData()
		# 其他设置
		self.stage_size: dict[str, float] = DEFAULT_PROJECT_CONFIG["stage_size"].copy()
		self.timer_position: dict[str, float] = DEFAULT_PROJECT_CONFIG["timer_position"].copy()
		self.workspace_scroll_xy: dict[str, float] = DEFAULT_PROJECT_CONFIG["workspace_scroll_xy"].copy()
		self.filepath: Path | None = None
		self.resources: dict[str, Any] = {}
		self.project_folder: Path | None = None

	@classmethod
	def load_from_dict(cls, data: dict[str, Any]) -> KNProject:
		"""从JSON字典加载项目 - 完整版"""
		project = cls(JSONConverter.ensure_str(data.get("projectName", "未命名项目")))
		# 基础信息
		project.version = JSONConverter.ensure_str(data.get("version", DEFAULT_PROJECT_CONFIG["version"]))
		project.tool_type = JSONConverter.ensure_str(data.get("toolType", DEFAULT_PROJECT_CONFIG["tool_type"]))
		project.stage_size = JSONConverter.ensure_dict(data.get("stageSize", DEFAULT_PROJECT_CONFIG["stage_size"]))
		project.timer_position = JSONConverter.ensure_dict(data.get("timerPosition", DEFAULT_PROJECT_CONFIG["timer_position"]))
		project.workspace_scroll_xy = JSONConverter.ensure_dict(data.get("workspaceScrollXy", DEFAULT_PROJECT_CONFIG["workspace_scroll_xy"]))
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
			blocks_list = JSONConverter.ensure_list(scene_data.get("nekoBlockJsonList", []))
			for block_data in blocks_list:
				if isinstance(block_data, dict):
					block = Block.from_dict(block_data)
					scene.blocks.append(block)
					project.workspace.add_block(block)
			project.scenes[scene_id] = scene
		project.current_scene_id = JSONConverter.ensure_str(scenes_data.get("currentSceneId", ""))
		project.sort_list = JSONConverter.ensure_list(scenes_data.get("sortList", []))
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
		for proc_id, proc_data in procedures_dict.items():
			if isinstance(proc_data, dict):
				# 尝试创建 Procedure 对象,如果数据有效
				try:
					if "name" in proc_data and "params" in proc_data:
						# 创建 Procedure 对象
						procedure = Procedure.from_dict(proc_data)
						project.procedures[proc_id] = procedure
					else:
						# 如果数据不符合 Procedure 结构,则存储为字典
						project.procedures[proc_id] = proc_data
				except Exception:
					# 如果创建失败,存储为原始字典
					project.procedures[proc_id] = proc_data
			else:
				# 如果数据类型不是字典,直接存储
				project.procedures[proc_id] = proc_data
		return project

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
		if filepath.suffix != ".bcmkn":
			filepath = filepath.with_suffix(".bcmkn")
		data = self.to_dict()
		with filepath.open("w", encoding="utf-8") as f:
			json.dump(data, f, ensure_ascii=False, indent=2)
		print(f"项目已保存: {filepath}")

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
			"procedures": {"proceduresDict": {proc_id: (proc.to_dict() if isinstance(proc, Procedure) else proc) for proc_id, proc in self.procedures.items()}},
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
	def from_xml(cls, xml_str: str) -> KNProject:
		"""从XML创建项目"""
		root = ET.fromstring(xml_str)
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
						try:
							block_xml = ET.tostring(block_elem, encoding="unicode")
							block = Block.from_xml(block_xml)
							scene.blocks.append(block)
							project.workspace.add_block(block)
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
						try:
							block_xml = ET.tostring(block_elem, encoding="unicode")
							block = Block.from_xml(block_xml)
							actor.blocks.append(block)
							project.workspace.add_block(block)
						except Exception:  # noqa: S110
							pass
				project.actors[actor_id] = actor
		return project

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
				block_xml = block.to_xml(include_shadows=True, include_location=True)
				block_elem = ET.fromstring(block_xml)
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
				block_xml = block.to_xml(include_shadows=True, include_location=True)
				block_elem = ET.fromstring(block_xml)
				blocks_elem.append(block_elem)
		return ET.tostring(root, encoding="unicode", xml_declaration=True)

	def add_actor(self, name: str, position: dict[str, float] | None = None, **kwargs: Any) -> str:
		"""添加角色"""
		actor_id = str(uuid.uuid4())
		if position is None:
			position = {"x": 0.0, "y": 0.0}
		actor = Actor(id=actor_id, name=name, position=position, **kwargs)
		self.actors[actor_id] = actor
		return actor_id

	def add_scene(self, name: str, screen_name: str = "屏幕", **kwargs: Any) -> str:
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

	def add_audio(self, name: str, audio_url: str = "", volume: int = 100) -> str:
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

	def add_procedure(self, name: str, params: list[dict[str, Any]] | None = None) -> str:
		"""添加自定义函数"""
		proc_id = str(uuid.uuid4())
		if params is None:
			params = []
		proc = Procedure(id=proc_id, name=name, params=params)
		self.procedures[proc_id] = proc
		return proc_id

	def get_procedure(self, proc_id: str) -> Procedure | dict | None:
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

	def get_all_blocks(self) -> list[Block]:
		"""获取项目中所有块"""
		return self.workspace.repository.get_all()

	def find_block(self, block_id: str) -> Block | None:
		"""在项目中查找代码块"""
		return self.workspace.repository.get_by_id(block_id)

	def find_blocks_by_type(self, block_type: str) -> list[Block]:
		"""按类型查找积木"""
		return self.workspace.repository.get_by_type(block_type)

	def find_blocks_by_category(self, category: BlockCategory) -> list[Block]:
		"""按分类查找积木"""
		return self.workspace.repository.get_by_category(category)

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
		for block in all_blocks:
			config = BLOCK_CONFIG.get(BlockType(block.type), {})
			category = config.get("category")
			if category:
				category_counts[category.value] = category_counts.get(category.value, 0) + 1
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
			"procedures_count": len(self.procedures),
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
		print(f"过程数量: {analysis['procedures_count']}")
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
		builder = BlockBuilder(block_type)
		for key, value in kwargs.items():
			if key == "location":
				builder.with_location(value[0], value[1])
			elif key.startswith("field_"):
				field_name = key[6:]
				builder.with_field(field_name, value)
			elif key == "id":
				builder.with_id(value)
			elif key == "parent_id":
				builder.with_parent(value)
		block = builder.build()
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

	def analyze_project(self) -> dict[str, Any]:
		"""分析项目结构"""
		return self.project.analyze_project()

	def get_statistics(self) -> dict[str, Any]:
		"""获取项目统计信息"""
		project_stats = self.project.analyze_project()
		workspace_stats = self.project.workspace.get_statistics()
		return {**project_stats, **workspace_stats}
