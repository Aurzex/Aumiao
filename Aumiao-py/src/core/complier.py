import hashlib
import json
import random
import xml.etree.ElementTree as ET  # noqa: S405
from pathlib import Path
from typing import Any, ClassVar

import requests


class Network:
	"""网络请求工具类"""

	@staticmethod
	def fetch_json(url: str) -> ...:
		"""获取JSON数据"""
		response = requests.get(url, timeout=30)
		response.raise_for_status()
		return response.json()

	@staticmethod
	def fetch_binary(url: str) -> bytes:
		"""获取二进制数据"""
		response = requests.get(url, timeout=30)
		response.raise_for_status()
		return response.content

	@staticmethod
	def fetch_text(url: str) -> str:
		"""获取文本数据"""
		response = requests.get(url, timeout=30)
		response.raise_for_status()
		return response.text


class Crypto:
	"""加密哈希工具类"""

	@staticmethod
	def sha256(data: str | bytes) -> str:
		"""计算SHA256哈希"""
		if isinstance(data, str):
			data = data.encode()
		return hashlib.sha256(data).hexdigest()


class WorkInfo:
	"""作品信息容器"""

	def __init__(self, data: dict[str, Any]) -> None:
		self.id = data["id"]
		self.name = data.get("work_name", data.get("name", "未知作品"))
		self.type = data.get("type", "NEMO")
		self.version = data.get("bcm_version", "0.16.2")
		self.user_id = data.get("user_id", 0)
		self.preview_url = data.get("preview", "")
		self.source_urls = data.get("work_urls", [])

	@property
	def file_extension(self) -> str:
		"""根据作品类型返回文件扩展名"""
		extensions = {
			"KITTEN2": ".bcm",
			"KITTEN3": ".bcm",
			"KITTEN4": ".bcm4",
			"COCO": ".json",
			"NEMO": "",  # Nemo使用文件夹
		}
		return extensions.get(self.type, ".json")

	@property
	def is_nemo(self) -> bool:
		"""是否为Nemo作品"""
		return self.type == "NEMO"


class FileHelper:
	"""文件操作工具类"""

	@staticmethod
	def safe_filename(name: str, work_id: int, extension: str = "") -> str:
		"""生成安全文件名"""
		# 移除非法字符
		safe_name = "".join(c for c in name if c.isalnum() or c in {" ", "-", "_"}).strip()
		if not safe_name:
			safe_name = f"work_{work_id}"
		# 添加扩展名
		if extension and not extension.startswith("."):
			extension = f".{extension}"
		return f"{safe_name}_{work_id}{extension}"

	@staticmethod
	def ensure_dir(path: str | Path) -> None:
		"""确保目录存在"""
		Path(path).mkdir(parents=True, exist_ok=True)

	@staticmethod
	def write_json(path: str | Path, data: ...) -> None:
		"""写入JSON文件"""
		with Path(path).open("w", encoding="utf-8") as f:
			json.dump(data, f, ensure_ascii=False, indent=2)

	@staticmethod
	def write_binary(path: str | Path, data: bytes) -> None:
		"""写入二进制文件"""
		with Path(path).open("wb") as f:
			f.write(data)


class ShadowBuilder:
	"""阴影积木构建器"""

	# 阴影类型定义
	SHADOW_TYPES: ClassVar[set[str]] = {
		"broadcast_input",
		"controller_shadow",
		"default_value",
		"get_audios",
		"get_current_costume",
		"get_current_scene",
		"get_sensing_current_scene",
		"get_whole_audios",
		"lists_get",
		"logic_empty",
		"math_number",
		"text",
	}
	# 字段属性配置
	FIELD_CONFIG: ClassVar[dict[str, dict[str, str]]] = {
		"broadcast_input": {"name": "MESSAGE", "text": "Hi"},
		"controller_shadow": {"name": "NUM", "text": "0", "constraints": "-Infinity,Infinity,0,false"},
		"default_value": {"name": "TEXT", "text": "0", "has_been_edited": "false"},
		"get_audios": {"name": "sound_id", "text": "?"},
		"get_current_costume": {"name": "style_id", "text": ""},
		"get_current_scene": {"name": "scene", "text": ""},
		"get_sensing_current_scene": {"name": "scene", "text": ""},
		"get_whole_audios": {"name": "sound_id", "text": "all"},
		"lists_get": {"name": "VAR", "text": "?"},
		"math_number": {"name": "NUM", "text": "0", "constraints": "-Infinity,Infinity,0,", "allow_text": "true"},
		"text": {"name": "TEXT", "text": ""},
	}

	@staticmethod
	def generate_id(length: int = 20) -> str:
		"""生成随机ID"""
		chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
		return "".join(random.choice(chars) for _ in range(length))

	def create(self, shadow_type: str, block_id: str | None = None, text: str | None = None) -> str:
		"""创建阴影积木"""
		if shadow_type == "logic_empty":
			block_id = block_id or self.generate_id()
			return f'<empty type="logic_empty" id="{block_id}" visible="visible" editable="false"></empty>'
		config = self.FIELD_CONFIG.get(shadow_type, {})
		block_id = block_id or self.generate_id()
		display_text = text or config.get("text", "")
		shadow = ET.Element("shadow")
		shadow.set("type", shadow_type)
		shadow.set("id", block_id)
		shadow.set("visible", "visible")
		shadow.set("editable", "true")
		field = ET.SubElement(shadow, "field")
		field.set("name", config["name"])
		field.text = str(display_text)
		# 添加额外属性
		for attr in ["constraints", "allow_text", "has_been_edited"]:
			if attr in config:
				field.set(attr, config[attr])
		return ET.tostring(shadow, encoding="unicode")


class BaseDecompiler:
	"""反编译器基类"""

	def __init__(self, work_info: WorkInfo) -> None:
		self.work_info = work_info
		self.shadow_builder = ShadowBuilder()

	def decompile(self) -> dict[str, Any] | str:
		"""反编译作品 - 子类必须实现"""
		raise NotImplementedError


class NemoDecompiler(BaseDecompiler):
	"""Nemo作品反编译器"""

	def decompile(self) -> str:
		"""反编译Nemo作品为文件夹结构"""
		work_id = self.work_info.id
		# 创建主目录
		work_dir = Path(f"nemo_work_{work_id}")
		FileHelper.ensure_dir(work_dir)
		# 获取作品源数据
		source_info = Network.fetch_json(f"https://api.codemao.cn/creation-tools/v1/works/{work_id}/source/public")
		bcm_data = Network.fetch_json(source_info["work_urls"][0])
		# 创建目录结构
		dirs = self._create_directories(work_dir, work_id)
		# 保存核心文件
		self._save_core_files(dirs, work_id, bcm_data, source_info)
		# 下载资源文件
		self._download_resources(dirs, bcm_data)
		return str(work_dir)

	@staticmethod
	def _create_directories(base_dir: Path, work_id: int) -> dict[str, Path]:
		"""创建目录结构"""
		dirs = {
			"material": base_dir / "user_material",
			"works": base_dir / "user_works" / str(work_id),
			"record": base_dir / "user_works" / str(work_id) / "record",
		}
		for path in dirs.values():
			FileHelper.ensure_dir(path)
		return dirs

	def _save_core_files(self, dirs: dict[str, Path], work_id: int, bcm_data: dict[str, Any], source_info: dict[str, Any]) -> None:
		"""保存核心文件"""
		# 保存BCM文件
		bcm_path = dirs["works"] / f"{work_id}.bcm"
		FileHelper.write_json(bcm_path, bcm_data)
		# 创建用户图片配置
		user_images = self._build_user_images(bcm_data)
		userimg_path = dirs["works"] / f"{work_id}.userimg"
		FileHelper.write_json(userimg_path, user_images)
		# 创建元数据
		meta_data = self._build_metadata(work_id, source_info)
		meta_path = dirs["works"] / f"{work_id}.meta"
		FileHelper.write_json(meta_path, meta_data)
		# 下载封面
		if source_info.get("preview"):
			try:
				cover_data = Network.fetch_binary(source_info["preview"])
				cover_path = dirs["works"] / f"{work_id}.cover"
				FileHelper.write_binary(cover_path, cover_data)
			except Exception as e:
				print(f"封面下载失败: {e}")

	@staticmethod
	def _build_user_images(bcm_data: dict[str, Any]) -> dict[str, Any]:
		"""构建用户图片配置"""
		user_images = {"user_img_dict": {}}
		styles = bcm_data.get("styles", {}).get("styles_dict", {})
		for style_id, style_data in styles.items():
			image_url = style_data.get("url")
			if image_url:
				user_images["user_img_dict"][style_id] = {"id": style_id, "path": f"user_material/{Crypto.sha256(image_url)}.webp"}
		return user_images

	@staticmethod
	def _build_metadata(work_id: int, source_info: dict[str, Any]) -> dict[str, Any]:
		"""构建元数据"""
		return {
			"bcm_count": {
				"block_cnt_without_invisible": 0.0,
				"block_cnt": 0.0,
				"entity_cnt": 1.0,
			},
			"bcm_name": source_info["name"],
			"bcm_url": source_info["work_urls"][0],
			"bcm_version": source_info["bcm_version"],
			"download_fail": False,
			"extra_data": {},
			"have_published_status": False,
			"have_remote_resources": False,
			"is_landscape": False,
			"is_micro_bit": False,
			"is_valid": False,
			"mcloud_variable": [],
			"publish_preview": source_info["preview"],
			"publish_status": 0,
			"review_state": 0,
			"template_id": 0,
			"term_id": 0,
			"type": 0,
			"upload_status": {
				"work_id": work_id,
				"have_uploaded": 2,
			},
		}

	@staticmethod
	def _download_resources(dirs: dict[str, Path], bcm_data: dict[str, Any]) -> None:
		"""下载资源文件"""
		styles = bcm_data.get("styles", {}).get("styles_dict", {})
		for style_data in styles.values():
			image_url = style_data.get("url")
			if image_url:
				try:
					image_data = Network.fetch_binary(image_url)
					file_name = f"{Crypto.sha256(image_url)}.webp"
					file_path = dirs["material"] / file_name
					FileHelper.write_binary(file_path, image_data)
				except Exception as e:
					print(f"资源下载失败 {image_url}: {e}")


class KittenDecompiler(BaseDecompiler):
	"""Kitten作品反编译器"""

	def __init__(self, work_info: WorkInfo) -> None:
		super().__init__(work_info)
		self.functions: dict[str, Any] = {}

	def decompile(self) -> dict[str, Any]:
		"""反编译Kitten作品"""
		# 获取编译数据
		compiled_data = self._fetch_compiled_data()
		# 反编译作品
		work = compiled_data.copy()
		self._decompile_actors(work)
		self._update_work_info(work)
		self._clean_work_data(work)
		return work

	def _fetch_compiled_data(self) -> dict[str, Any]:
		"""获取编译数据"""
		work_id = self.work_info.id
		if self.work_info.type in {"KITTEN2", "KITTEN3", "KITTEN4"}:
			url = f"https://api-creation.codemao.cn/kitten/r2/work/player/load/{work_id}"
			compiled_url = Network.fetch_json(url)["source_urls"][0]
		else:
			compiled_url = self.work_info.source_urls[0]
		return Network.fetch_json(compiled_url)

	def _decompile_actors(self, work: dict[str, Any]) -> None:
		"""反编译所有角色"""
		actors = []
		for actor_data in work["compile_result"]:
			actor_info = self._get_actor_info(work, actor_data["id"])
			actor = ActorProcessor(self, actor_info, actor_data)
			actors.append(actor)
		# 准备并执行反编译
		for actor in actors:
			actor.prepare()
		for actor in actors:
			actor.process()

	@staticmethod
	def _get_actor_info(work: dict[str, Any], actor_id: str) -> dict[str, Any]:
		"""获取角色信息"""
		theatre = work["theatre"]
		return theatre["actors"].get(actor_id, theatre["scenes"][actor_id])

	def _update_work_info(self, work: dict[str, Any]) -> None:
		"""更新作品信息"""
		toolbox_categories = [
			"action",
			"advanced",
			"ai",
			"ai_game",
			"ai_lab",
			"appearance",
			"arduino",
			"audio",
			"camera",
			"cloud_list",
			"cloud_variable",
			"cognitive",
			"control",
			"data",
			"data",
			"event",
			"micro_bit",
			"midi_music",
			"mobile_control",
			"operator",
			"pen",
			"physic",
			"physics2",
			"procedure",
			"sensing",
			"video",
			"wee_make",
			"wood",
		]
		work.update(
			{
				"hidden_toolbox": {"toolbox": [], "blocks": []},
				"work_source_label": 0,
				"sample_id": "",
				"project_name": self.work_info.name,
				"toolbox_order": toolbox_categories,
				"last_toolbox_order": toolbox_categories,
			}
		)

	@staticmethod
	def _clean_work_data(work: dict[str, Any]) -> None:
		"""清理作品数据"""
		for key in ["compile_result", "preview", "author_nickname"]:
			work.pop(key, None)


class ActorProcessor:
	"""角色处理器"""

	def __init__(self, decompiler: KittenDecompiler, actor_info: dict[str, Any], compiled_data: dict[str, Any]) -> None:
		self.decompiler = decompiler
		self.actor_info = actor_info
		self.compiled_data = compiled_data
		self.blocks: dict[str, Any] = {}
		self.connections: dict[str, Any] = {}

	def prepare(self) -> None:
		"""准备阶段"""
		self.actor_info["block_data_json"] = {"blocks": self.blocks, "connections": self.connections, "comments": {}}

	def process(self) -> None:
		"""处理角色"""
		# 处理函数
		for func_name, func_data in self.compiled_data["procedures"].items():
			processor = FunctionProcessor(func_data, self)
			self.decompiler.functions[func_name] = processor.process()
		# 处理积木
		for block_data in self.compiled_data["compiled_block_map"].values():
			self.process_block(block_data)

	def process_block(self, compiled: dict[str, Any]) -> dict[str, Any]:
		"""处理单个积木"""
		block_type = compiled["type"]
		# 选择处理器
		if block_type == "controls_if":
			processor = IfBlockProcessor(compiled, self)
		elif block_type == "text_join":
			processor = TextJoinProcessor(compiled, self)
		elif block_type.startswith("procedures_2_def"):
			processor = FunctionProcessor(compiled, self)
		elif block_type.startswith("procedures_2_call"):
			processor = FunctionCallProcessor(compiled, self)
		else:
			processor = BlockProcessor(compiled, self)
		return processor.process()


class BlockProcessor:
	"""积木处理器基类"""

	def __init__(self, compiled: dict[str, Any], actor: ActorProcessor) -> None:
		self.compiled = compiled
		self.actor = actor
		self.block: dict[str, Any] = {}
		self.connection: dict[str, Any] = {}
		self.shadows: dict[str, Any] = {}
		self.fields: dict[str, Any] = {}

	def process(self) -> dict[str, Any]:
		"""处理积木"""
		self._setup_basic_info()
		self._process_next()
		self._process_children()
		self._process_conditions()
		self._process_params()
		return self.block

	def _setup_basic_info(self) -> None:
		"""设置基础信息"""
		block_id = self.compiled["id"]
		block_type = self.compiled["type"]
		shadow_types = self.actor.decompiler.shadow_builder.SHADOW_TYPES
		self.block.update(
			{
				"id": block_id,
				"type": block_type,
				"location": [0, 0],
				"is_shadow": block_type in shadow_types,
				"collapsed": False,
				"disabled": False,
				"deletable": True,
				"movable": True,
				"editable": True,
				"visible": "visible",
				"shadows": self.shadows,
				"fields": self.fields,
				"field_constraints": {},
				"field_extra_attr": {},
				"comment": None,
				"mutation": "",
				"is_output": (block_type in shadow_types or block_type in {"logic_boolean", "procedures_2_stable_parameter"}),
				"parent_id": None,
			}
		)
		self.actor.connections[block_id] = self.connection
		self.actor.blocks[block_id] = self.block

	def _process_next(self) -> None:
		"""处理下一个积木"""
		if "next_block" in self.compiled:
			next_block = self.actor.process_block(self.compiled["next_block"])
			next_block["parent_id"] = self.block["id"]
			self.connection[next_block["id"]] = {"type": "next"}

	def _process_children(self) -> None:
		"""处理子积木"""
		if "child_block" in self.compiled:
			for i, child in enumerate(self.compiled["child_block"]):
				if child is not None:
					child_block = self.actor.process_block(child)
					child_block["parent_id"] = self.block["id"]
					input_name = self._get_child_input_name(i)
					self.connection[child_block["id"]] = {"type": "input", "input_type": "statement", "input_name": input_name}
					self.shadows[input_name] = ""

	def _process_conditions(self) -> None:
		"""处理条件积木"""
		if "conditions" in self.compiled:
			for i, condition in enumerate(self.compiled["conditions"]):
				condition_block = self.actor.process_block(condition)
				condition_block["parent_id"] = self.block["id"]
				input_name = f"IF{i}"
				if condition_block["type"] != "logic_empty":
					self.connection[condition_block["id"]] = {"type": "input", "input_type": "value", "input_name": input_name}
				shadow = self.actor.decompiler.shadow_builder.create("logic_empty", condition_block["id"])
				self.shadows[input_name] = shadow

	def _process_params(self) -> None:
		"""处理参数"""
		for name, value in self.compiled["params"].items():
			if isinstance(value, dict):
				param_block = self.actor.process_block(value)
				param_block["parent_id"] = self.block["id"]
				param_type = param_block["type"]
				if param_type in self.actor.decompiler.shadow_builder.SHADOW_TYPES:
					field_values = list(param_block["fields"].values())
					field_value = field_values[0] if field_values else ""
					shadow = self.actor.decompiler.shadow_builder.create(param_type, param_block["id"], field_value)
				else:
					shadow_type = "logic_empty" if name in {"condition", "BOOL"} else "math_number"
					shadow = self.actor.decompiler.shadow_builder.create(shadow_type)
				self.shadows[name] = shadow
				self.connection[param_block["id"]] = {"type": "input", "input_type": "value", "input_name": name}
			else:
				self.fields[name] = value

	@staticmethod
	def _get_child_input_name(_index: int) -> str:
		"""获取子输入名称"""
		return "DO"


class IfBlockProcessor(BlockProcessor):
	"""条件积木处理器"""

	MIN_CONDITIONS_FOR_ELSE = 2

	def process(self) -> dict[str, Any]:
		block = super().process()
		children = self.compiled["child_block"]
		# 检查else分支
		if len(children) == self.MIN_CONDITIONS_FOR_ELSE and children[-1] is None:
			self.shadows["EXTRA_ADD_ELSE"] = ""
		else:
			condition_count = len(self.compiled["conditions"])
			self.block["mutation"] = f'<mutation elseif="{condition_count - 1}" else="1"></mutation>'
			self.shadows["ELSE_TEXT"] = ""
		return block

	def _get_child_input_name(self, index: int) -> str:  # type: ignore  # noqa: PGH003
		conditions_count = len(self.compiled["conditions"])
		return f"DO{index}" if index < conditions_count else "ELSE"


class TextJoinProcessor(BlockProcessor):
	"""文本连接积木处理器"""

	def process(self) -> dict[str, Any]:
		block = super().process()
		param_count = len(self.compiled["params"])
		self.block["mutation"] = f'<mutation items="{param_count}"></mutation>'
		return block


class FunctionProcessor(BlockProcessor):
	"""函数定义处理器"""

	def process(self) -> dict[str, Any]:
		self._setup_basic_info()
		self._process_children()
		self.shadows["PROCEDURES_2_DEFNORETURN_DEFINE"] = ""
		self.shadows["PROCEDURES_2_DEFNORETURN_MUTATOR"] = ""
		self.fields["NAME"] = self.compiled["procedure_name"]
		mutation = ET.Element("mutation")
		for i, (param_name, _) in enumerate(self.compiled["params"].items()):
			input_name = f"PARAMS{i}"
			arg = ET.SubElement(mutation, "arg")
			arg.set("name", input_name)
			shadow = self.actor.decompiler.shadow_builder.create("math_number")
			self.shadows[input_name] = shadow
			param_block = self.actor.process_block(
				{
					"id": ShadowBuilder.generate_id(),
					"kind": "domain_block",
					"type": "procedures_2_stable_parameter",
					"params": {"param_name": param_name, "param_default_value": ""},
				}
			)
			param_block["parent_id"] = self.block["id"]
			self.connection[param_block["id"]] = {"type": "input", "input_type": "value", "input_name": input_name}
		self.block["mutation"] = ET.tostring(mutation, encoding="unicode")
		return self.block

	@staticmethod
	def _get_child_input_name(_index: int) -> str:
		return "STACK"


class FunctionCallProcessor(BlockProcessor):
	"""函数调用处理器"""

	def process(self) -> dict[str, Any]:
		self._setup_basic_info()
		self._process_next()
		func_name = self.compiled["procedure_name"]
		functions = self.actor.decompiler.functions
		try:
			func_id = functions[func_name]["id"]
		except KeyError:
			func_id = ShadowBuilder.generate_id()
			self.block["disabled"] = True
		self.shadows["NAME"] = ""
		self.fields["NAME"] = func_name
		mutation = ET.Element("mutation")
		mutation.set("name", func_name)
		mutation.set("def_id", func_id)
		for i, (param_name, param_value) in enumerate(self.compiled["params"].items()):
			param_block = self.actor.process_block(param_value)
			shadow = self.actor.decompiler.shadow_builder.create("default_value", param_block["id"])
			self.shadows[f"ARG{i}"] = shadow
			param_elem = ET.SubElement(mutation, "procedures_2_parameter_shadow")
			param_elem.set("name", param_name)
			param_elem.set("value", "0")
			self.connection[param_block["id"]] = {"type": "input", "input_type": "value", "input_name": f"ARG{i}"}
		self.block["mutation"] = ET.tostring(mutation, encoding="unicode")
		return self.block


class CocoDecompiler(BaseDecompiler):
	"""CoCo作品反编译器"""

	def decompile(self) -> dict[str, Any]:
		"""反编译CoCo作品"""
		compiled_data = self._fetch_compiled_data()
		work = compiled_data.copy()
		self._reorganize_data(work)
		self._clean_data(work)
		return work

	def _fetch_compiled_data(self) -> dict[str, Any]:
		"""获取编译数据"""
		work_id = self.work_info.id
		url = f"https://api-creation.codemao.cn/coconut/web/work/{work_id}/load"
		compiled_url = Network.fetch_json(url)["data"]["bcmc_url"]
		return Network.fetch_json(compiled_url)

	def _reorganize_data(self, work: dict[str, Any]) -> None:
		"""重组数据"""
		work["authorId"] = self.work_info.user_id
		work["title"] = self.work_info.name
		work["screens"] = {}
		work["screenIds"] = []
		# 处理屏幕
		for screen in work["screenList"]:
			screen_id = screen["id"]
			screen["snapshot"] = ""
			work["screens"][screen_id] = screen
			work["screenIds"].append(screen_id)
			# 初始化屏幕数据
			screen.update(
				{
					"primitiveVariables": [],
					"arrayVariables": [],
					"objectVariables": [],
					"broadcasts": ["Hi"],
					"widgets": {},
				}
			)
			# 处理组件
			for widget_id in screen["widgetIds"] + screen["invisibleWidgetIds"]:
				screen["widgets"][widget_id] = work["widgetMap"][widget_id]
				del work["widgetMap"][widget_id]
		# 处理积木数据
		work["blockly"] = {}
		for screen_id, blocks in work["blockJsonMap"].items():
			work["blockly"][screen_id] = {"screenId": screen_id, "workspaceJson": blocks, "workspaceOffset": {"x": 0, "y": 0}}
		# 处理资源文件
		self._process_resources(work)
		# 处理变量
		self._process_variables(work)
		# 设置全局属性
		work.update(
			{
				"globalWidgets": work["widgetMap"],
				"globalWidgetIds": list(work["widgetMap"].keys()),
				"sourceTag": 1,
				"sourceId": "",
			}
		)

	@staticmethod
	def _process_resources(work: dict[str, Any]) -> None:
		"""处理资源文件"""
		resource_maps = ["imageFileMap", "soundFileMap", "iconFileMap", "fontFileMap"]
		for map_name in resource_maps:
			if map_name in work:
				list_name = map_name.replace("Map", "List")
				work[list_name] = list(work[map_name].values())

	@staticmethod
	def _process_variables(work: dict[str, Any]) -> None:
		"""处理变量"""
		counters = {"var": 0, "list": 0, "dict": 0}
		variable_lists = {
			"globalVariableList": [],
			"globalArrayList": [],
			"globalObjectList": [],
		}
		for var_id, value in work["variableMap"].items():
			if isinstance(value, list):
				counters["list"] += 1
				variable_lists["globalArrayList"].append({"id": var_id, "name": f"列表{counters['list']}", "defaultValue": value, "value": value})
			elif isinstance(value, dict):
				counters["dict"] += 1
				variable_lists["globalObjectList"].append({"id": var_id, "name": f"字典{counters['dict']}", "defaultValue": value, "value": value})
			else:
				counters["var"] += 1
				variable_lists["globalVariableList"].append({"id": var_id, "name": f"变量{counters['var']}", "defaultValue": value, "value": value})
		work.update(variable_lists)

	@staticmethod
	def _clean_data(work: dict[str, Any]) -> None:
		"""清理数据"""
		remove_keys = [
			"apiToken",
			"blockCode",
			"blockJsonMap",
			"fontFileMap",
			"gridMap",
			"iconFileMap",
			"id",
			"imageFileMap",
			"initialScreenId",
			"screenList",
			"soundFileMap",
			"variableMap",
			"widgetMap",
		]
		for key in remove_keys:
			work.pop(key, None)


class Decompiler:
	"""反编译器主类"""

	def __init__(self) -> None:
		self.decompilers = {
			"NEMO": NemoDecompiler,
			"KITTEN2": KittenDecompiler,
			"KITTEN3": KittenDecompiler,
			"KITTEN4": KittenDecompiler,
			"COCO": CocoDecompiler,
		}

	def decompile(self, work_id: int, output_dir: str = "decompiled") -> str:
		"""
		反编译作品
		Args:
			work_id: 作品ID
			output_dir: 输出目录
		Returns:
			保存的文件路径
		"""
		print(f"开始反编译作品 {work_id}...")
		# 获取作品信息
		raw_info = Network.fetch_json(f"https://api.codemao.cn/creation-tools/v1/works/{work_id}")
		work_info = WorkInfo(raw_info)
		print(f"✓ 作品: {work_info.name}")
		print(f"✓ 类型: {work_info.type}")
		# 选择反编译器
		decompiler_class = self.decompilers.get(work_info.type)
		if not decompiler_class:
			error_msg = f"不支持的作品类型: {work_info.type}"
			raise ValueError(error_msg)
		decompiler = decompiler_class(work_info)
		result = decompiler.decompile()
		# 保存结果
		return self._save_result(result, work_info, output_dir)

	@staticmethod
	def _save_result(result: dict[str, Any] | str, work_info: WorkInfo, output_dir: str) -> str:
		"""保存反编译结果"""
		FileHelper.ensure_dir(output_dir)
		if work_info.is_nemo:
			# Nemo作品已经是文件夹,直接返回路径
			if isinstance(result, str):
				return result
			msg = "Nemo作品应该返回字符串路径"
			raise TypeError(msg)
		# 其他作品保存为文件
		file_name = FileHelper.safe_filename(work_info.name, work_info.id, work_info.file_extension.lstrip("."))
		file_path = Path(output_dir) / file_name
		if isinstance(result, dict):
			FileHelper.write_json(file_path, result)
		else:
			# 对于非Nemo作品,result应该是dict,所以这里不应该发生
			msg = "非Nemo作品应该返回字典"
			raise TypeError(msg)
		return str(file_path)


def decompile_work(work_id: int, output_dir: str = "decompiled") -> str:
	"""
	反编译作品
	Args:
		work_id: 作品ID
		output_dir: 输出目录
	Returns:
		保存的文件路径
	"""
	decompiler = Decompiler()
	return decompiler.decompile(work_id, output_dir)


if __name__ == "__main__":
	try:
		work_id = int(input("请输入作品ID: "))
		output_path = decompile_work(work_id)
		print(f"✓ 反编译完成: {output_path}")
	except ValueError:
		print("错误: 作品ID必须是数字")
	except Exception as e:
		print(f"反编译失败: {e}")
