import json
import operator
import pathlib
import random
import sys
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, cast


class EntityType(Enum):
	"""实体类型枚举"""

	SCENE = "scene"
	ACTOR = "actor"
	GROUP = "group"
	STYLE = "style"
	VARIABLE = "variable"


@dataclass
class Entity:
	"""实体基类"""

	id: str
	name: str
	entity_type: EntityType
	data: dict[str, Any] = field(default_factory=dict)

	def to_dict(self) -> dict[str, Any]:
		"""转换为字典"""
		return {"id": self.id, "name": self.name, "type": self.entity_type.value, **self.data}


class IDGenerator:
	"""ID生成器"""

	@staticmethod
	def generate_uuid() -> str:
		"""生成UUID"""
		return str(uuid.uuid4())

	@staticmethod
	def generate_id(length: int = 20) -> str:
		"""生成随机ID(兼容旧格式)"""
		chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
		return "".join(random.choice(chars) for _ in range(length))

	@staticmethod
	def generate_short_id() -> str:
		"""生成短ID"""
		return IDGenerator.generate_id(8)


class WorkParser:
	"""作品解析器"""

	def __init__(self, work_data: dict[str, Any]) -> None:
		self.work_data = work_data
		self.entities: dict[str, Entity] = {}
		self.id_maps: dict[str, dict[str, str]] = {
			"scenes": {},
			"actors": {},
			"groups": {},
			"styles": {},
			"variables": {},
		}

	def parse(self) -> None:
		"""解析作品数据"""
		print("开始解析作品数据...")
		# 检查是否有theatre字段
		if "theatre" not in self.work_data:
			print("错误: 作品文件中缺少'theatre'字段")
			return
		# 解析场景
		self._parse_scenes()
		# 解析演员
		self._parse_actors()
		# 解析组
		self._parse_groups()
		# 解析样式
		self._parse_styles()
		# 解析变量
		self._parse_variables()
		print(f"解析完成: {len(self.entities)} 个实体")

	def _parse_scenes(self) -> None:
		"""解析场景 - 修复: 场景在theatre.scenes字典中"""
		theatre = self.work_data.get("theatre", {})
		scenes = theatre.get("scenes", {})
		if not isinstance(scenes, dict):
			print(f"  警告: 场景数据格式无效: {type(scenes)}")
			return
		for scene_id, scene_data in scenes.items():
			if isinstance(scene_data, dict):
				scene = Entity(
					id=str(scene_id),
					name=str(scene_data.get("name", "未命名场景")),
					entity_type=EntityType.SCENE,
					data=scene_data,
				)
				self.entities[scene.id] = scene
				self.id_maps["scenes"][scene.id] = scene.id
				print(f"  场景: {scene.name} ({scene.id})")
			else:
				print(f"  警告: 跳过无效的场景数据: {scene_id}")

	def _parse_actors(self) -> None:
		"""解析演员 - 修复: 演员在theatre.actors字典中"""
		theatre = self.work_data.get("theatre", {})
		actors = theatre.get("actors", {})
		if not isinstance(actors, dict):
			print(f"  警告: 演员数据格式无效: {type(actors)}")
			return
		for actor_id, actor_data in actors.items():
			if isinstance(actor_data, dict):
				actor = Entity(
					id=str(actor_id),
					name=str(actor_data.get("name", "未命名角色")),
					entity_type=EntityType.ACTOR,
					data=actor_data,
				)
				self.entities[actor.id] = actor
				self.id_maps["actors"][actor.id] = actor.id
				print(f"  演员: {actor.name} ({actor.id})")
			else:
				print(f"  警告: 跳过无效的演员数据: {actor_id}")

	def _parse_groups(self) -> None:
		"""解析组 - 修复: 组在theatre.groups字典中"""
		theatre = self.work_data.get("theatre", {})
		groups = theatre.get("groups", {})
		if not isinstance(groups, dict):
			print(f"  警告: 组数据格式无效: {type(groups)}")
			return
		for group_id, group_data in groups.items():
			if isinstance(group_data, dict):
				group = Entity(
					id=str(group_id),
					name=str(group_data.get("name", "未命名组")),
					entity_type=EntityType.GROUP,
					data=group_data,
				)
				self.entities[group.id] = group
				self.id_maps["groups"][group.id] = group.id
				print(f"  组: {group.name} ({group.id})")
			else:
				print(f"  警告: 跳过无效的组数据: {group_id}")

	def _parse_styles(self) -> None:
		"""解析样式 - 修复: 样式在theatre.styles字典中"""
		theatre = self.work_data.get("theatre", {})
		styles = theatre.get("styles", {})
		if not isinstance(styles, dict):
			print(f"  警告: 样式数据格式无效: {type(styles)}")
			return
		for style_id, style_data in styles.items():
			if isinstance(style_data, dict):
				style = Entity(
					id=str(style_id),
					name=str(style_data.get("name", "未命名样式")),
					entity_type=EntityType.STYLE,
					data=style_data,
				)
				self.entities[style.id] = style
				self.id_maps["styles"][style.id] = style.id
				print(f"  样式: {style.name} ({style.id})")
			else:
				print(f"  警告: 跳过无效的样式数据: {style_id}")

	def _parse_variables(self) -> None:
		"""解析变量 - 修复: 变量在cloud_variables字典中"""
		variables_dict = self.work_data.get("cloud_variables", {})
		if not isinstance(variables_dict, dict):
			print(f"  警告: 变量数据格式无效: {type(variables_dict)}")
			return
		for var_name, var_value in variables_dict.items():
			variable = Entity(
				id=str(var_name),
				name=str(var_name),
				entity_type=EntityType.VARIABLE,
				data={"value": var_value},
			)
			self.entities[variable.id] = variable
			self.id_maps["variables"][variable.id] = variable.id
			print(f"  变量: {variable.name} = {var_value}")


class WorkEditor:
	"""作品编辑器"""

	def __init__(self, work_parser: WorkParser) -> None:
		self.parser = work_parser
		self.work_data = work_parser.work_data.copy()

	def remap_ids(self) -> None:
		"""重新映射所有ID"""
		print("\n开始重新映射ID...")
		# 生成新的ID映射
		self._generate_id_maps()
		# 更新所有实体的ID
		self._update_entity_ids()
		# 更新所有引用关系
		self._update_references()
		print("ID重新映射完成!")

	def _generate_id_maps(self) -> None:
		"""生成ID映射表"""
		print("  生成新的ID映射表...")
		# 为每种实体类型生成新ID
		for entity_id, entity in self.parser.entities.items():
			entity_type = entity.entity_type
			new_id = IDGenerator.generate_uuid()
			# 添加到映射表
			if entity_type == EntityType.SCENE:
				self.parser.id_maps["scenes"][entity_id] = new_id
			elif entity_type == EntityType.ACTOR:
				self.parser.id_maps["actors"][entity_id] = new_id
			elif entity_type == EntityType.GROUP:
				self.parser.id_maps["groups"][entity_id] = new_id
			elif entity_type == EntityType.STYLE:
				self.parser.id_maps["styles"][entity_id] = new_id
			elif entity_type == EntityType.VARIABLE:
				self.parser.id_maps["variables"][entity_id] = new_id

	def _update_entity_ids(self) -> None:
		"""更新实体ID"""
		print("  更新实体ID...")
		# 更新场景ID
		self._update_scene_ids()
		# 更新演员ID
		self._update_actor_ids()
		# 更新组ID
		self._update_group_ids()
		# 更新样式ID
		self._update_style_ids()
		# 更新变量ID
		self._update_variable_ids()

	def _update_scene_ids(self) -> None:
		"""更新场景ID"""
		theatre = self.work_data.get("theatre", {})
		scenes = theatre.get("scenes", {})
		new_scenes = {}
		for old_id, scene_data in scenes.items():
			old_id_str = str(old_id)
			if old_id_str in self.parser.id_maps["scenes"]:
				new_id = self.parser.id_maps["scenes"][old_id_str]
				# 更新场景自身ID
				if isinstance(scene_data, dict):
					scene_data["id"] = new_id
					new_scenes[new_id] = scene_data
			else:
				new_scenes[old_id_str] = scene_data
		theatre["scenes"] = new_scenes
		# 更新scenes_order中的ID
		if "scenes_order" in theatre:
			new_order = []
			for old_id in theatre["scenes_order"]:
				old_id_str = str(old_id)
				if old_id_str in self.parser.id_maps["scenes"]:
					new_order.append(self.parser.id_maps["scenes"][old_id_str])
				else:
					new_order.append(old_id_str)
			theatre["scenes_order"] = new_order

	def _update_actor_ids(self) -> None:
		"""更新演员ID"""
		theatre = self.work_data.get("theatre", {})
		actors = theatre.get("actors", {})
		new_actors = {}
		name_list = []
		for old_id, actor_data in actors.items():
			old_id_str = str(old_id)
			if isinstance(actor_data, dict):
				# 更新ID
				if old_id_str in self.parser.id_maps["actors"]:
					new_id = self.parser.id_maps["actors"][old_id_str]
					actor_data["id"] = new_id
					new_actors[new_id] = actor_data
				else:
					new_actors[old_id_str] = actor_data
				# 处理名称重复
				actor_name = str(actor_data.get("name", ""))
				actor_data["name"] = self._deduplicate_name(actor_name, name_list)
				name_list.append(actor_data["name"])
		theatre["actors"] = new_actors

	def _update_group_ids(self) -> None:
		"""更新组ID"""
		theatre = self.work_data.get("theatre", {})
		groups = theatre.get("groups", {})
		new_groups = {}
		for old_id, group_data in groups.items():
			old_id_str = str(old_id)
			if isinstance(group_data, dict):
				# 更新ID
				if old_id_str in self.parser.id_maps["groups"]:
					new_id = self.parser.id_maps["groups"][old_id_str]
					group_data["id"] = new_id
					new_groups[new_id] = group_data
				else:
					new_groups[old_id_str] = group_data
				# 更新组内演员引用
				if "actors" in group_data:
					new_actors = []
					for actor_id in group_data["actors"]:
						actor_id_str = str(actor_id)
						if actor_id_str in self.parser.id_maps["actors"]:
							new_actors.append(self.parser.id_maps["actors"][actor_id_str])
						else:
							new_actors.append(actor_id_str)
					group_data["actors"] = new_actors
		theatre["groups"] = new_groups

	def _update_style_ids(self) -> None:
		"""更新样式ID"""
		theatre = self.work_data.get("theatre", {})
		styles = theatre.get("styles", {})
		new_styles = {}
		for old_id, style_data in styles.items():
			old_id_str = str(old_id)
			if isinstance(style_data, dict):
				if old_id_str in self.parser.id_maps["styles"]:
					new_id = self.parser.id_maps["styles"][old_id_str]
					style_data["id"] = new_id
					new_styles[new_id] = style_data
				else:
					new_styles[old_id_str] = style_data
		theatre["styles"] = new_styles

	def _update_variable_ids(self) -> None:
		"""更新变量ID - 修复: 变量名不变,只更新值"""
		# 变量名通常保持不变,只更新值
		# 如果有需要可以在这里添加变量名映射逻辑

	def _update_references(self) -> None:
		"""更新所有引用关系"""
		print("  更新引用关系...")
		# 更新场景引用
		self._update_scene_references()
		# 更新演员引用
		self._update_actor_references()
		# 更新组引用
		self._update_group_references()
		# 更新积木数据中的引用
		self._update_block_references()

	def _update_scene_references(self) -> None:
		"""更新场景引用"""
		theatre = self.work_data.get("theatre", {})
		# 更新演员的场景引用
		actors = theatre.get("actors", {})
		for actor_data in actors.values():
			if isinstance(actor_data, dict):
				old_scene_id = actor_data.get("scene", "")
				old_scene_id_str = str(old_scene_id)
				if old_scene_id_str in self.parser.id_maps["scenes"]:
					actor_data["scene"] = self.parser.id_maps["scenes"][old_scene_id_str]
		# 更新组的场景引用
		groups = theatre.get("groups", {})
		for group_data in groups.values():
			if isinstance(group_data, dict):
				old_scene_id = group_data.get("scene", "")
				old_scene_id_str = str(old_scene_id)
				if old_scene_id_str in self.parser.id_maps["scenes"]:
					group_data["scene"] = self.parser.id_maps["scenes"][old_scene_id_str]

	def _update_actor_references(self) -> None:
		"""更新演员引用"""
		theatre = self.work_data.get("theatre", {})
		actors = theatre.get("actors", {})
		for actor_data in actors.values():
			if isinstance(actor_data, dict):
				# 更新样式引用
				if "styles" in actor_data:
					new_styles = []
					for style_id in actor_data["styles"]:
						style_id_str = str(style_id)
						if style_id_str in self.parser.id_maps["styles"]:
							new_styles.append(self.parser.id_maps["styles"][style_id_str])
						else:
							new_styles.append(style_id_str)
					actor_data["styles"] = new_styles
				# 更新当前样式
				current_style = actor_data.get("current_style_id", "")
				current_style_str = str(current_style)
				if current_style_str in self.parser.id_maps["styles"]:
					actor_data["current_style_id"] = self.parser.id_maps["styles"][current_style_str]

	def _update_group_references(self) -> None:
		"""更新组引用"""
		theatre = self.work_data.get("theatre", {})
		groups = theatre.get("groups", {})
		for group_data in groups.values():
			if isinstance(group_data, dict):
				# 更新组内演员引用(已在_update_group_ids中处理)
				pass

	def _update_block_references(self) -> None:
		"""更新积木数据中的引用"""
		print("  更新积木数据中的引用...")
		# 更新场景积木数据
		self._update_entity_block_data("scenes")
		# 更新演员积木数据
		self._update_entity_block_data("actors")
		# 更新组积木数据
		self._update_entity_block_data("groups")

	def _update_entity_block_data(self, entity_type: str) -> None:
		"""更新实体积木数据"""
		theatre = self.work_data.get("theatre", {})
		if entity_type == "scenes":
			scenes = theatre.get("scenes", {})
			for scene_data in scenes.values():
				if isinstance(scene_data, dict) and "block_data_json" in scene_data:
					self._replace_ids_in_block_data(scene_data["block_data_json"])
		elif entity_type == "actors":
			actors = theatre.get("actors", {})
			for actor_data in actors.values():
				if isinstance(actor_data, dict) and "block_data_json" in actor_data:
					self._replace_ids_in_block_data(actor_data["block_data_json"])
		elif entity_type == "groups":
			groups = theatre.get("groups", {})
			for group_data in groups.values():
				if isinstance(group_data, dict) and "block_data_json" in group_data:
					self._replace_ids_in_block_data(group_data["block_data_json"])

	def _replace_ids_in_block_data(self, block_data: dict[str, Any]) -> None:
		"""在积木数据中替换ID"""
		if not block_data:
			return
		# 替换blocks中的ID引用
		if "blocks" in block_data:
			blocks = block_data["blocks"]
			new_blocks = {}
			for block_id, block_info in blocks.items():
				if isinstance(block_info, dict):
					# 更新block自身的ID
					new_block_id = block_id
					for id_map in self.parser.id_maps.values():
						for old_id, new_id in id_map.items():
							if old_id == block_id:
								new_block_id = new_id
								break
					# 替换block内容中的ID
					self._replace_ids_in_dict(block_info)
					new_blocks[new_block_id] = block_info
			block_data["blocks"] = new_blocks
		# 替换connections中的ID引用
		if "connections" in block_data:
			connections = block_data["connections"]
			new_connections = {}
			for block_id, conn_info in connections.items():
				if isinstance(conn_info, dict):
					# 更新block ID
					new_block_id = block_id
					for id_map in self.parser.id_maps.values():
						for old_id, new_id in id_map.items():
							if old_id == block_id:
								new_block_id = new_id
								break
					# 替换连接中的ID
					self._replace_ids_in_dict(conn_info)
					new_connections[new_block_id] = conn_info
			block_data["connections"] = new_connections

	def _replace_ids_in_dict(self, data: dict[str, Any]) -> None:
		"""递归替换字典中的ID"""
		if not isinstance(data, dict):
			return
		for key, value in data.items():
			if isinstance(value, str):
				# 替换字符串中的ID
				for id_map in self.parser.id_maps.values():
					for old_id, new_id in id_map.items():
						if old_id in value:
							data[key] = value.replace(old_id, new_id)
			elif isinstance(value, dict):
				# 递归处理嵌套字典
				self._replace_ids_in_dict(value)
			elif isinstance(value, list):
				# 处理列表
				for i, item in enumerate(value):
					if isinstance(item, str):
						for id_map in self.parser.id_maps.values():
							for old_id, new_id in id_map.items():
								if old_id == item:
									value[i] = new_id
									break

	@staticmethod
	def _deduplicate_name(name: str, name_list: list[str]) -> str:
		"""名称去重"""
		if name not in name_list:
			return name
		# 添加数字后缀
		counter = 1
		while f"{name}({counter})" in name_list:
			counter += 1
		return f"{name}({counter})"

	def save_work(self, filepath: str) -> None:
		"""保存作品文件"""
		with pathlib.Path(filepath).open("w", encoding="utf-8") as f:
			json.dump(self.work_data, f, ensure_ascii=False, indent=2)
		print(f"作品已保存到: {filepath}")


class BlockAnalyzer:
	"""积木分析器"""

	@staticmethod
	def analyze_block_structure(block_data: dict[str, Any]) -> dict[str, Any]:
		"""分析积木结构"""
		if not block_data or "blocks" not in block_data:
			return {}
		analysis: dict[str, Any] = {
			"total_blocks": 0,
			"block_types": {},
			"shadows": 0,
			"events": 0,
			"controls": 0,
			"operators": 0,
			"motions": 0,
			"looks": 0,
		}
		blocks = block_data["blocks"]
		analysis["total_blocks"] = len(blocks)
		for block in blocks.values():
			if not isinstance(block, dict):
				continue
			block_type = block.get("type", "")
			# 统计积木类型
			if block_type in analysis["block_types"]:
				analysis["block_types"][block_type] += 1
			else:
				analysis["block_types"][block_type] = 1
			# 统计阴影积木
			if block.get("is_shadow", False):
				analysis["shadows"] += 1
			# 分类统计
			block_type_str = str(block_type).lower()
			if "start" in block_type_str or "event" in block_type_str:
				analysis["events"] += 1
			elif "control" in block_type_str or "repeat" in block_type_str:
				analysis["controls"] += 1
			elif "operator" in block_type_str or "math" in block_type_str:
				analysis["operators"] += 1
			elif "motion" in block_type_str or "go" in block_type_str or "turn" in block_type_str:
				analysis["motions"] += 1
			elif "looks" in block_type_str or "say" in block_type_str:
				analysis["looks"] += 1
		return analysis


class InteractiveEditor:
	"""交互式编辑器"""

	def __init__(self) -> None:
		self.work_data: dict[str, Any] | None = None
		self.work_parser: WorkParser | None = None
		self.work_editor: WorkEditor | None = None

	def run(self) -> None:
		"""运行交互式编辑器"""
		print("=" * 60)
		print("Kitten/Codemao 作品文件解析编辑工具 - 修复版")
		print("=" * 60)
		while True:
			print("\n主菜单:")
			print("  1. 加载作品文件")
			print("  2. 查看作品信息")
			print("  3. 重新映射ID")
			print("  4. 分析积木结构")
			print("  5. 编辑实体")
			print("  6. 保存作品")
			print("  7. 退出")
			choice = input("请选择操作 (1-7): ").strip()
			if choice == "1":
				self.load_work()
			elif choice == "2":
				self.show_work_info()
			elif choice == "3":
				self.remap_ids()
			elif choice == "4":
				self.analyze_blocks()
			elif choice == "5":
				self.edit_entities()
			elif choice == "6":
				self.save_work()
			elif choice == "7":
				print("退出程序")
				break
			else:
				print("无效选择,请重新输入")

	def load_work(self) -> None:
		"""加载作品文件"""
		filepath = input("请输入作品文件路径: ").strip()
		path = pathlib.Path(filepath)
		if not path.exists():
			print(f"错误: 文件不存在 - {filepath}")
			return
		try:
			with path.open(encoding="utf-8") as f:
				self.work_data = json.load(f)
			if self.work_data:
				self.work_parser = WorkParser(self.work_data)
				self.work_parser.parse()
				self.work_editor = WorkEditor(self.work_parser)
				print(f"作品文件加载成功: {filepath}")
				print(f"项目名称: {self.work_data.get('project_name', '未知')}")
				print(f"应用版本: {self.work_data.get('application_version', '未知')}")
		except json.JSONDecodeError as e:
			print(f"JSON解析失败: {e}")
		except Exception as e:
			print(f"加载失败: {e}")

	def show_work_info(self) -> None:
		"""显示作品信息"""
		if not self.work_data or not self.work_parser:
			print("请先加载作品文件")
			return

		print("\n作品信息:")
		work_data = self.work_data  # 确保不是None
		print(f"  项目名称: {work_data.get('project_name', '未知')}")
		print(f"  应用版本: {work_data.get('application_version', '未知')}")
		# 获取theatre信息
		theatre = work_data.get("theatre", {})
		print(f"  场景数量: {len(theatre.get('scenes', {}))}")
		print(f"  演员数量: {len(theatre.get('actors', {}))}")
		print(f"  组数量: {len(theatre.get('groups', {}))}")
		print(f"  样式数量: {len(theatre.get('styles', {}))}")
		print(f"  变量数量: {len(work_data.get('cloud_variables', {}))}")
		# 显示场景顺序
		scenes_order = theatre.get("scenes_order", [])
		if scenes_order:
			print(f"  场景顺序: {', '.join(map(str, scenes_order))}")
		# 显示实体列表
		print("\n实体列表:")
		for entity in self.work_parser.entities.values():
			print(f"  {entity.entity_type.value}: {entity.name} ({entity.id[:8]}...)")

	def remap_ids(self) -> None:
		"""重新映射ID"""
		if not self.work_editor:
			print("请先加载作品文件")
			return
		confirm = input("确定要重新映射所有ID吗? (y/n): ").strip().lower()
		if confirm == "y":
			self.work_editor.remap_ids()

	def analyze_blocks(self) -> None:
		"""分析积木结构"""
		if not self.work_data:
			print("请先加载作品文件")
			return

		theatre = self.work_data.get("theatre", {})
		# 分析场景积木
		scenes = theatre.get("scenes", {})
		for scene_id, scene_data in scenes.items():
			if isinstance(scene_data, dict) and "block_data_json" in scene_data:
				analysis = BlockAnalyzer.analyze_block_structure(scene_data["block_data_json"])
				print(f"\n场景 '{scene_data.get('name', scene_id)}' 积木分析:")
				self._print_block_analysis(analysis)
		# 分析演员积木
		actors = theatre.get("actors", {})
		for actor_id, actor_data in actors.items():
			if isinstance(actor_data, dict) and "block_data_json" in actor_data:
				analysis = BlockAnalyzer.analyze_block_structure(actor_data["block_data_json"])
				print(f"\n演员 '{actor_data.get('name', actor_id)}' 积木分析:")
				self._print_block_analysis(analysis)

	@staticmethod
	def _print_block_analysis(analysis: dict[str, Any]) -> None:
		"""打印积木分析结果"""
		if not analysis or analysis["total_blocks"] == 0:
			print("  无积木数据")
			return
		print(f"  总积木数: {analysis['total_blocks']}")
		print(f"  阴影积木: {analysis['shadows']}")
		print(f"  事件积木: {analysis.get('events', 0)}")
		print(f"  控制积木: {analysis.get('controls', 0)}")
		print(f"  运算积木: {analysis.get('operators', 0)}")
		print(f"  运动积木: {analysis.get('motions', 0)}")
		print(f"  外观积木: {analysis.get('looks', 0)}")
		if analysis.get("block_types"):
			print("\n  积木类型分布 (前10):")
			for block_type, count in sorted(
				analysis["block_types"].items(),
				key=operator.itemgetter(1),
				reverse=True,
			)[:10]:
				print(f"    {block_type}: {count}")

	def edit_entities(self) -> None:
		"""编辑实体"""
		if not self.work_parser:
			print("请先加载作品文件")
			return
		print("\n编辑实体:")
		print("  1. 重命名实体")
		print("  2. 删除实体")
		print("  3. 添加新实体")
		choice = input("请选择操作 (1-3): ").strip()
		if choice == "1":
			self.rename_entity()
		elif choice == "2":
			self.delete_entity()
		elif choice == "3":
			self.add_entity()
		else:
			print("无效选择")

	def rename_entity(self) -> None:
		"""重命名实体"""
		if not self.work_parser or not self.work_data:
			print("请先加载作品文件")
			return
		entity_id = input("请输入实体ID: ").strip()
		if entity_id not in self.work_parser.entities:
			print(f"错误: 实体ID不存在 - {entity_id}")
			return
		entity = self.work_parser.entities[entity_id]
		new_name = input(f"请输入新名称 (当前: {entity.name}): ").strip()
		if new_name:
			entity.name = new_name
			# 更新work_data中的名称
			entity_type = entity.entity_type
			theatre = self.work_data.get("theatre", {})
			if entity_type == EntityType.SCENE:
				scenes = theatre.get("scenes", {})
				if entity_id in scenes:
					scenes[entity_id]["name"] = new_name
			elif entity_type == EntityType.ACTOR:
				actors = theatre.get("actors", {})
				if entity_id in actors:
					actors[entity_id]["name"] = new_name
			elif entity_type == EntityType.GROUP:
				groups = theatre.get("groups", {})
				if entity_id in groups:
					groups[entity_id]["name"] = new_name
			elif entity_type == EntityType.STYLE:
				styles = theatre.get("styles", {})
				if entity_id in styles:
					styles[entity_id]["name"] = new_name
			print(f"实体重命名为: {new_name}")

	def delete_entity(self) -> None:
		"""删除实体"""
		if not self.work_parser or not self.work_data:
			print("请先加载作品文件")
			return
		entity_id = input("请输入要删除的实体ID: ").strip()
		if entity_id not in self.work_parser.entities:
			print(f"错误: 实体ID不存在 - {entity_id}")
			return
		entity = self.work_parser.entities[entity_id]
		confirm = input(f"确定要删除 {entity.name} ({entity_id}) 吗? (y/n): ").strip().lower()
		if confirm == "y":
			# 从work_data中删除实体
			entity_type = entity.entity_type
			theatre = self.work_data.get("theatre", {})
			if entity_type == EntityType.SCENE:
				scenes = theatre.get("scenes", {})
				if entity_id in scenes:
					del scenes[entity_id]
					# 从scenes_order中移除
					if "scenes_order" in theatre:
						theatre["scenes_order"] = [sid for sid in theatre["scenes_order"] if str(sid) != entity_id]
			elif entity_type == EntityType.ACTOR:
				actors = theatre.get("actors", {})
				if entity_id in actors:
					del actors[entity_id]
					# 从所有组中移除该演员
					groups = theatre.get("groups", {})
					for group_data in groups.values():
						if "actors" in group_data and entity_id in group_data["actors"]:
							group_data["actors"].remove(entity_id)
			elif entity_type == EntityType.GROUP:
				groups = theatre.get("groups", {})
				if entity_id in groups:
					del groups[entity_id]
			elif entity_type == EntityType.STYLE:
				styles = theatre.get("styles", {})
				if entity_id in styles:
					del styles[entity_id]
					# 从所有使用该样式的演员中移除引用
					actors = theatre.get("actors", {})
					for actor_data in actors.values():
						if "styles" in actor_data and entity_id in actor_data["styles"]:
							actor_data["styles"].remove(entity_id)
						if actor_data.get("current_style_id") == entity_id:
							actor_data["current_style_id"] = ""
			# 从解析器中移除
			del self.work_parser.entities[entity_id]
			print(f"实体 {entity.name} 已删除")

	def add_entity(self) -> None:
		"""添加新实体"""
		if not self.work_parser or not self.work_data:
			print("请先加载作品文件")
			return
		print("\n添加新实体:")
		print("  1. 添加演员")
		print("  2. 添加变量")
		print("  3. 添加场景")
		choice = input("请选择实体类型 (1-3): ").strip()
		if choice == "1":
			self.add_actor()
		elif choice == "2":
			self.add_variable()
		elif choice == "3":
			self.add_scene()
		else:
			print("无效选择")

	def add_actor(self) -> None:
		"""添加演员"""
		if not self.work_parser or not self.work_data:
			print("请先加载作品文件")
			return
		name = input("请输入演员名称: ").strip()
		if not name:
			print("名称不能为空")
			return
		# 选择场景
		theatre = self.work_data.get("theatre", {})
		scenes = theatre.get("scenes", {})
		if not scenes:
			print("错误: 没有可用的场景")
			return
		print("可用场景:")
		for scene_id, scene_data in scenes.items():
			print(f"  {scene_id}: {scene_data.get('name', '未命名')}")
		scene_id = input("请输入场景ID: ").strip()
		if scene_id not in scenes:
			print(f"错误: 场景ID不存在 - {scene_id}")
			return
		new_actor = {
			"id": IDGenerator.generate_uuid(),
			"name": name,
			"draggable": True,
			"editable_in_tuition_mode": True,
			"lock": False,
			"rotation": 0,
			"rotation_type": 0,
			"scale": 100.0,
			"scene": scene_id,
			"styles": [],
			"current_style_id": "",
			"user_change_r_c": False,
			"visible": True,
			"workspace_offset": {"x": 0, "y": 0},
			"x": 0,
			"y": 0,
			"block_data_json": {"blocks": {}, "connections": {}, "comments": {}},
		}
		# 添加到work_data
		if "actors" not in theatre:
			theatre["actors"] = {}
		theatre["actors"][new_actor["id"]] = new_actor
		# 添加到解析器
		actor_entity = Entity(
			id=cast("str", new_actor["id"]),
			name=name,
			entity_type=EntityType.ACTOR,
			data=new_actor,
		)
		self.work_parser.entities[new_actor["id"]] = actor_entity  # pyright: ignore[reportArgumentType]
		self.work_parser.id_maps["actors"][new_actor["id"]] = new_actor["id"]  # pyright: ignore[reportArgumentType]
		print(f"演员 {name} 添加成功")

	def add_variable(self) -> None:
		"""添加变量"""
		if not self.work_parser or not self.work_data:
			print("请先加载作品文件")
			return
		name = input("请输入变量名称: ").strip()
		if not name:
			print("名称不能为空")
			return
		value = input("请输入变量值: ").strip()
		if not value:
			value = "0"
		# 添加到work_data
		if "cloud_variables" not in self.work_data:
			self.work_data["cloud_variables"] = {}
		self.work_data["cloud_variables"][name] = value
		# 添加到解析器
		var_entity = Entity(
			id=name,
			name=name,
			entity_type=EntityType.VARIABLE,
			data={"value": value},
		)
		self.work_parser.entities[name] = var_entity
		self.work_parser.id_maps["variables"][name] = name
		print(f"变量 {name} = {value} 添加成功")

	def add_scene(self) -> None:
		"""添加场景"""
		if not self.work_parser or not self.work_data:
			print("请先加载作品文件")
			return
		name = input("请输入场景名称: ").strip()
		if not name:
			print("名称不能为空")
			return
		new_scene: dict = {
			"id": IDGenerator.generate_uuid(),
			"name": name,
			"actors": [],
			"block_data_json": {"blocks": {}, "connections": {}, "comments": {}},
			"current_style_id": "",
			"draggable": False,
			"group_order": [],
			"rotation": 0,
			"rotation_type": 0,
			"scale": 100,
			"screen_name": name,
			"styles": [],
			"visible": True,
			"workspace_offset": {"x": 0, "y": 0},
			"x": 0,
			"y": 0,
		}
		# 添加到work_data
		theatre = self.work_data.get("theatre", {})
		if "scenes" not in theatre:
			theatre["scenes"] = {}
		theatre["scenes"][new_scene["id"]] = new_scene
		# 添加到scenes_order
		if "scenes_order" not in theatre:
			theatre["scenes_order"] = []
		theatre["scenes_order"].append(new_scene["id"])
		# 添加到解析器
		scene_entity = Entity(
			id=new_scene["id"],
			name=name,
			entity_type=EntityType.SCENE,
			data=new_scene,
		)
		self.work_parser.entities[new_scene["id"]] = scene_entity
		self.work_parser.id_maps["scenes"][new_scene["id"]] = new_scene["id"]
		print(f"场景 {name} 添加成功")

	def save_work(self) -> None:
		"""保存作品"""
		if not self.work_editor:
			print("请先加载作品文件")
			return
		filepath = input("请输入保存路径 (直接回车使用默认路径): ").strip()
		if not filepath:
			timestamp = time.strftime("%Y%m%d_%H%M%S")
			filepath = f"work_modified_{timestamp}.json"
		self.work_editor.save_work(filepath)


def main() -> None:
	"""主函数"""
	editor = InteractiveEditor()
	# 检查是否有命令行参数
	if len(sys.argv) > 1:
		# 直接加载文件
		filepath = sys.argv[1]
		path = pathlib.Path(filepath)
		if not path.exists():
			print(f"错误: 文件不存在 - {filepath}")
			return
		try:
			with path.open(encoding="utf-8") as f:
				work_data = json.load(f)
			editor.work_data = work_data
			editor.work_parser = WorkParser(work_data)
			editor.work_parser.parse()
			editor.work_editor = WorkEditor(editor.work_parser)
			print(f"已加载作品文件: {filepath}")
			print(f"项目名称: {work_data.get('project_name', '未知')}")
		except json.JSONDecodeError as e:
			print(f"JSON解析失败: {e}")
			return
		except Exception as e:
			print(f"加载失败: {e}")
			return
		editor.run()
	else:
		# 运行交互式编辑器
		editor.run()


if __name__ == "__main__":
	main()
