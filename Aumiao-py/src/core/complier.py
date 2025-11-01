import json
import pathlib
import random
import xml.etree.ElementTree as ET  # noqa: S405
from typing import Any, ClassVar

import requests


class SimpleDecompiler:
	"""简化版源码反编译器"""

	def __init__(self) -> None:
		self.shadow_creator = ShadowCreator()

	@staticmethod
	def http_get_json(url: str) -> ...:
		"""HTTP GET请求获取JSON"""
		response = requests.get(url, timeout=30)
		HTTP_SUCCESS_CODE = 200  # noqa: N806
		if response.status_code != HTTP_SUCCESS_CODE:
			error_msg = f"HTTP请求失败: {url}, 状态码: {response.status_code}"
			raise RequestError(error_msg)
		return response.json()

	def get_work_info(self, work_id: int) -> dict[str, Any]:
		"""获取作品信息"""
		info = self.http_get_json(f"https://api.codemao.cn/creation-tools/v1/works/{work_id}")
		return {"id": info["id"], "name": info["work_name"], "type": info["type"], "version": info["bcm_version"]}

	def get_compiled_work_url(self, work_info: dict[str, Any]) -> str:
		"""获取编译作品URL"""
		work_type = work_info["type"]
		work_id = work_info["id"]
		if work_type in {"KITTEN2", "KITTEN3", "KITTEN4"}:
			url = f"https://api-creation.codemao.cn/kitten/r2/work/player/load/{work_id}"
			return self.http_get_json(url)["source_urls"][0]
		if work_type == "COCO":
			url = f"https://api-creation.codemao.cn/coconut/web/work/{work_id}/load"
			return self.http_get_json(url)["data"]["bcmc_url"]
		error_msg = f"不支持的作品类型: {work_type}"
		raise ValueError(error_msg)

	def decompile_kitten_work(self, work_info: dict[str, Any], compiled_work: dict[str, Any]) -> dict[str, Any]:
		"""反编译Kitten作品"""
		decompiler = KittenWorkDecompiler(work_info, compiled_work, self)
		return decompiler.start()

	@staticmethod
	def decompile_coco_work(work_info: dict[str, Any], compiled_work: dict[str, Any]) -> dict[str, Any]:
		"""反编译CoCo作品"""
		decompiler = CoCoWorkDecompiler(work_info, compiled_work)
		return decompiler.start()

	@staticmethod
	def save_source_code(source_code: dict[str, Any], work_type: str, work_name: str, work_id: int) -> str:
		"""保存源码文件到当前目录"""
		# 确定文件扩展名
		extension_map = {"KITTEN4": ".bcm4", "KITTEN3": ".bcm", "KITTEN2": ".bcm", "COCO": ".json"}
		default_extension = extension_map.get(work_type, ".json")
		# 清理文件名中的非法字符
		clean_name = "".join(c for c in work_name if c.isalnum() or c in {" ", "-", "_"}).rstrip()
		if not clean_name:
			clean_name = f"work_{work_id}"
		# 生成文件名
		filename = f"{clean_name}_{work_id}{default_extension}"
		file_path = pathlib.Path(filename)
		# 保存文件
		with file_path.open("w", encoding="utf-8") as f:
			json.dump(source_code, f, ensure_ascii=False, indent=2)
		return str(file_path.absolute())

	def decompile_work(self, work_id: int) -> str:
		"""反编译作品的主函数"""
		try:
			print(f"开始反编译作品 {work_id}...")
			# 获取作品信息
			work_info = self.get_work_info(work_id)
			print(f"✓ 获取作品信息成功: {work_info['name']}")
			# 获取编译文件URL
			compiled_work_url = self.get_compiled_work_url(work_info)
			print("✓ 获取编译文件URL成功")
			# 获取编译文件
			compiled_work = self.http_get_json(compiled_work_url)
			print("✓ 获取编译文件成功")
			# 选择反编译器
			if work_info["type"] in {"KITTEN2", "KITTEN3", "KITTEN4"}:
				source_code = self.decompile_kitten_work(work_info, compiled_work)
			elif work_info["type"] == "COCO":
				source_code = self.decompile_coco_work(work_info, compiled_work)
			else:
				error_msg = f"不支持的作品类型: {work_info['type']}"
				raise ValueError(error_msg)  # noqa: TRY301
			print("✓ 反编译完成")
			# 保存源码
			file_path = self.save_source_code(source_code, work_info["type"], work_info["name"], work_id)
			print(f"✓ 源码已保存到: {file_path}")
			return file_path  # noqa: TRY300
		except Exception as e:
			print(f"✗ 反编译失败: {e}")
			raise


class ShadowCreator:
	"""积木阴影创建器"""

	SHADOW_ALL_TYPES: ClassVar[set[str]] = {
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
	SHADOW_FIELD_ATTRIBUTES_MAP: ClassVar[dict[str, dict[str, str]]] = {
		"broadcast_input": {"name": "MESSAGE"},
		"controller_shadow": {"name": "NUM", "constraints": "-Infinity,Infinity,0,false"},
		"default_value": {"name": "TEXT", "has_been_edited": "false"},
		"get_audios": {"name": "sound_id"},
		"get_current_costume": {"name": "style_id"},
		"get_current_scene": {"name": "scene"},
		"get_sensing_current_scene": {"name": "scene"},
		"get_whole_audios": {"name": "sound_id"},
		"lists_get": {"name": "VAR"},
		"math_number": {"name": "NUM", "constraints": "-Infinity,Infinity,0,", "allow_text": "true"},
		"text": {"name": "TEXT"},
	}
	SHADOW_FIELD_TEXT_MAP: ClassVar[dict[str, str]] = {
		"broadcast_input": "Hi",
		"controller_shadow": "0",
		"default_value": "0",
		"get_audios": "?",
		"get_current_costume": "",
		"get_current_scene": "",
		"get_sensing_current_scene": "",
		"get_whole_audios": "all",
		"lists_get": "?",
		"math_number": "0",
		"text": "",
	}

	def create_shadow(self, shadow_type: str, block_id: str | None = None, text: str | None = None) -> str:
		"""创建阴影积木"""
		if shadow_type == "logic_empty":
			actual_block_id = block_id or self.random_block_id()
			return f'<empty type="logic_empty" id="{actual_block_id}" visible="visible" editable="false"></empty>'
		actual_block_id = block_id or self.random_block_id()
		actual_text = text or self.SHADOW_FIELD_TEXT_MAP.get(shadow_type, "")
		attrs = self.SHADOW_FIELD_ATTRIBUTES_MAP.get(shadow_type, {})
		shadow = ET.Element("shadow")
		shadow.set("type", shadow_type)
		shadow.set("id", actual_block_id)
		shadow.set("visible", "visible")
		shadow.set("editable", "true")
		field = ET.SubElement(shadow, "field")
		for name, value in attrs.items():
			field.set(name, value)
		field.text = str(actual_text)
		return ET.tostring(shadow, encoding="unicode")

	@staticmethod
	def random_block_id() -> str:
		"""生成随机积木ID"""
		chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
		return "".join(random.choice(chars) for _ in range(20))


class RequestError(Exception):
	"""自定义请求异常"""


class KittenWorkDecompiler:
	"""Kitten作品反编译器"""

	def __init__(self, work_info: dict[str, Any], compiled_work: dict[str, Any], parent: SimpleDecompiler) -> None:
		self.work_info = work_info
		self.work = compiled_work
		self.functions: dict[str, Any] = {}
		self.parent = parent

	def start(self) -> dict[str, Any]:
		"""开始反编译"""
		# 创建角色反编译器
		decompilers = []
		for actor_compiled_blocks in self.work["compile_result"]:
			actor = ActorDecompiler(self, self.get_actor(actor_compiled_blocks["id"]), actor_compiled_blocks)
			decompilers.append(actor)
		# 准备所有的角色
		for decompiler in decompilers:
			decompiler.prepare()
		# 开始反编译所有的角色
		for decompiler in decompilers:
			decompiler.start()
		self.write_work_info()
		self.clean()
		return self.work

	def get_actor(self, actor_id: str) -> dict[str, Any]:
		"""获取角色信息"""
		theatre = self.work["theatre"]
		try:
			return theatre["actors"][actor_id]
		except KeyError:
			return theatre["scenes"][actor_id]

	def clean(self) -> None:
		"""清理无用数据"""
		keys_to_remove = ["compile_result", "preview", "author_nickname"]
		for key in keys_to_remove:
			if key in self.work:
				del self.work[key]

	def write_work_info(self) -> None:
		"""写入作品信息"""
		self.work["hidden_toolbox"] = {"toolbox": [], "blocks": []}
		self.work["work_source_label"] = 0
		self.work["sample_id"] = ""
		self.work["project_name"] = self.work_info["name"]
		self.work["toolbox_order"] = self.work["last_toolbox_order"] = [
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
			"microbit",
			"midimusic",
			"mobile_control",
			"operator",
			"pen",
			"physic",
			"physics2",
			"procedure",
			"sensing",
			"video",
			"weeemake",
			"wood",
		]


class ActorDecompiler:
	"""角色反编译器"""

	def __init__(self, work: KittenWorkDecompiler, actor: dict[str, Any], compiled_blocks: dict[str, Any]) -> None:
		self.work = work
		self.actor = actor
		self.compiled = compiled_blocks
		self.blocks: dict[str, Any] = {}
		self.connections: dict[str, Any] = {}

	def prepare(self) -> None:
		"""准备阶段"""
		# 把积木数据关联到角色
		self.actor["block_data_json"] = {"blocks": self.blocks, "connections": self.connections, "comments": {}}

	def start(self) -> None:
		"""开始反编译"""
		# 反编译角色所有的函数
		for name, compiled_function in self.compiled["procedures"].items():
			self.work.functions[name] = Procedures2DefnoreturnDecompiler(compiled_function, self).start()
		# 反编译角色其余的积木
		for compiled_blocks in self.compiled["compiled_block_map"].values():
			self.get_block_decompiler(compiled_blocks).start()

	def get_block_decompiler(self, compiled: dict[str, Any]) -> ...:
		"""获取积木反编译器"""
		block_type = compiled["type"]
		decompiler_map = {
			"ask_and_choose": AskAndChooseDecompiler,
			"controls_if": ControlsIfDecompiler,
			"controls_if_no_else": ControlsIfDecompiler,
			"procedures_2_callnoreturn": Procedures2CallDecompiler,
			"procedures_2_callreturn": Procedures2CallDecompiler,
			"procedures_2_defnoreturn": Procedures2DefnoreturnDecompiler,
			"procedures_2_return_value": Procedures2ReturnValueDecompiler,
			"text_join": TextJoinDecompiler,
			"text_select_changeable": TextSelectChangeableDecompiler,
		}
		decompiler_class = decompiler_map.get(block_type, BlockDecompiler)
		return decompiler_class(compiled, self)


class BlockDecompiler:
	"""基础积木反编译器"""

	def __init__(self, compiled: dict[str, Any], actor: ActorDecompiler) -> None:
		self.compiled = compiled
		self.actor = actor
		self.block: dict[str, Any] = {}
		self.connection: dict[str, Any] = {}
		self.shadows: dict[str, Any] = {}
		self.fields: dict[str, Any] = {}

	def start(self) -> dict[str, Any]:
		"""开始反编译积木"""
		self.info()
		self.process_next()
		self.process_children()
		self.process_conditions()
		self.process_params()
		return self.block

	def info(self) -> None:
		"""积木基本信息"""
		self.id = self.block["id"] = self.compiled["id"]
		self.type = self.block["type"] = self.compiled["type"]
		self.block["location"] = [0, 0]
		self.block["is_shadow"] = self.type in self.actor.work.parent.shadow_creator.SHADOW_ALL_TYPES
		self.block["collapsed"] = False
		self.block["disabled"] = False
		self.block["deletable"] = True
		self.block["movable"] = True
		self.block["editable"] = True
		self.block["visible"] = "visible"
		self.block["shadows"] = self.shadows
		self.block["fields"] = self.fields
		self.block["field_constraints"] = {}
		self.block["field_extra_attr"] = {}
		self.block["comment"] = None
		self.block["mutation"] = ""
		self.block["is_output"] = self.type in self.actor.work.parent.shadow_creator.SHADOW_ALL_TYPES or self.type in {"logic_boolean", "procedures_2_stable_parameter"}
		self.block["parent_id"] = None
		self.actor.connections[self.id] = self.connection
		self.actor.blocks[self.id] = self.block

	def process_next(self) -> None:
		"""处理下一个积木"""
		if "next_block" in self.compiled:
			next_block = self.actor.get_block_decompiler(self.compiled["next_block"]).start()
			next_block["parent_id"] = self.id
			self.connection[next_block["id"]] = {"type": "next"}

	def process_children(self) -> None:
		"""处理子积木"""
		if "child_block" in self.compiled:
			child_blocks = self.compiled["child_block"]
			for i, child_data in enumerate(child_blocks):
				if child_data is not None:
					child_block = self.actor.get_block_decompiler(child_data).start()
					child_block["parent_id"] = self.id
					input_name = self.get_child_input_name(i)
					self.connection[child_block["id"]] = {"type": "input", "input_type": "statement", "input_name": input_name}
					self.shadows[input_name] = ""

	@staticmethod
	def get_child_input_name(_count: int) -> str:
		"""获取子输入名称"""
		return "DO"

	def process_conditions(self) -> None:
		"""处理条件积木"""
		if "conditions" in self.compiled:
			conditions = self.compiled["conditions"]
			for i, condition_data in enumerate(conditions):
				condition_block = self.actor.get_block_decompiler(condition_data).start()
				condition_block["parent_id"] = self.id
				input_name = f"IF{i}"
				if condition_block["type"] != "logic_empty":
					self.connection[condition_block["id"]] = {"type": "input", "input_type": "value", "input_name": input_name}
				self.shadows[input_name] = self.actor.work.parent.shadow_creator.create_shadow("logic_empty", condition_block["id"])

	def process_params(self) -> None:
		"""处理参数"""
		for name, value in self.compiled["params"].items():
			if isinstance(value, dict):
				param_block = self.actor.get_block_decompiler(value).start()
				param_block["parent_id"] = self.id
				param_type = param_block["type"]
				if param_type in self.actor.work.parent.shadow_creator.SHADOW_ALL_TYPES:
					# 转换参数信息
					field_values = list(param_block["fields"].values())
					field_value = field_values[0] if field_values else ""
					self.shadows[name] = self.actor.work.parent.shadow_creator.create_shadow(param_type, param_block["id"], field_value)
				else:
					# 生成参数信息
					shadow_type = "logic_empty" if name in {"condition", "BOOL"} else "math_number"
					self.shadows[name] = self.actor.work.parent.shadow_creator.create_shadow(shadow_type)
				self.connection[param_block["id"]] = {"type": "input", "input_type": "value", "input_name": name}
			else:
				self.fields[name] = value


class ControlsIfDecompiler(BlockDecompiler):
	"""条件控制积木反编译器"""

	def start(self) -> dict[str, Any]:
		block = super().start()
		child_blocks = self.compiled["child_block"]
		# 检查是否有else分支
		MIN_CONDITIONS_FOR_ELSE = 2  # noqa: N806
		if len(child_blocks) == MIN_CONDITIONS_FOR_ELSE and child_blocks[-1] is None:
			self.shadows["EXTRA_ADD_ELSE"] = ""
		else:
			condition_count = len(self.compiled["conditions"])
			self.block["mutation"] = f'<mutation elseif="{condition_count - 1}" else="1"></mutation>'
			self.shadows["ELSE_TEXT"] = ""
		return block

	def get_child_input_name(self, count: int) -> str:  # pyright: ignore[reportIncompatibleMethodOverride]
		conditions_count = len(self.compiled["conditions"])
		if count < conditions_count:
			return f"DO{count}"
		return "ELSE"


class AskAndChooseDecompiler(BlockDecompiler):
	"""询问选择积木反编译器"""

	def start(self) -> dict[str, Any]:
		block = super().start()
		param_count = len(self.compiled["params"])
		self.block["mutation"] = f'<mutation items="{param_count - 1}"></mutation>'
		return block


class TextJoinDecompiler(BlockDecompiler):
	"""文本连接积木反编译器"""

	def start(self) -> dict[str, Any]:
		block = super().start()
		param_count = len(self.compiled["params"])
		self.block["mutation"] = f'<mutation items="{param_count}"></mutation>'
		return block


class TextSelectChangeableDecompiler(BlockDecompiler):
	"""文本选择积木反编译器"""

	def start(self) -> dict[str, Any]:
		block = super().start()
		param_count = len(self.compiled["params"])
		self.block["mutation"] = f'<mutation items="{param_count - 1}"></mutation>'
		return block


class Procedures2DefnoreturnDecompiler(BlockDecompiler):
	"""无返回值函数定义积木反编译器"""

	def start(self) -> dict[str, Any]:
		self.info()
		self.process_children()
		self.shadows["PROCEDURES_2_DEFNORETURN_DEFINE"] = ""
		self.shadows["PROCEDURES_2_DEFNORETURN_MUTATOR"] = ""
		self.fields["NAME"] = self.compiled["procedure_name"]
		mutation = ET.Element("mutation")
		for param_count, (param_name, _param_value) in enumerate(self.compiled["params"].items()):
			input_name = f"PARAMS{param_count}"
			arg = ET.SubElement(mutation, "arg")
			arg.set("name", input_name)
			self.shadows[input_name] = self.actor.work.parent.shadow_creator.create_shadow("math_number")
			param_block = self.actor.get_block_decompiler(
				{
					"id": self.actor.work.parent.shadow_creator.random_block_id(),
					"kind": "domain_block",
					"type": "procedures_2_stable_parameter",
					"params": {"param_name": param_name, "param_default_value": ""},
				}
			).start()
			param_block["parent_id"] = self.block["id"]
			self.connection[param_block["id"]] = {"type": "input", "input_type": "value", "input_name": input_name}
		self.block["mutation"] = ET.tostring(mutation, encoding="unicode")
		return self.block

	@staticmethod
	def get_child_input_name(_count: int) -> str:
		return "STACK"


class Procedures2ReturnValueDecompiler(BlockDecompiler):
	"""返回值函数定义积木反编译器"""

	def start(self) -> dict[str, Any]:
		block = super().start()
		self.shadows["PROCEDURES_2_DEFRETURN_RETURN"] = ""
		self.shadows["PROCEDURES_2_DEFRETURN_RETURN_MUTATOR"] = ""
		param_count = len(self.compiled["params"])
		self.block["mutation"] = f'<mutation items="{param_count}"></mutation>'
		return block


class Procedures2CallDecompiler(BlockDecompiler):
	"""函数调用积木反编译器"""

	def start(self) -> dict[str, Any]:
		self.info()
		self.process_next()
		name = self.compiled["procedure_name"]
		try:
			function_id = self.actor.work.functions[name]["id"]
		except KeyError:
			function_id = self.actor.work.parent.shadow_creator.random_block_id()
			self.block["disabled"] = True
		self.shadows["NAME"] = ""
		self.fields["NAME"] = name
		mutation = ET.Element("mutation")
		mutation.set("name", name)
		mutation.set("def_id", function_id)
		for param_count, (param_name, param_value) in enumerate(self.compiled["params"].items()):
			param_block = self.actor.get_block_decompiler(param_value).start()
			self.shadows[f"ARG{param_count}"] = self.actor.work.parent.shadow_creator.create_shadow("default_value", param_block["id"])
			param = ET.SubElement(mutation, "procedures_2_parameter_shadow")
			param.set("name", param_name)
			param.set("value", "0")
			self.connection[param_block["id"]] = {"type": "input", "input_type": "value", "input_name": f"ARG{param_count}"}
		self.block["mutation"] = ET.tostring(mutation, encoding="unicode")
		return self.block


class CoCoWorkDecompiler:
	"""CoCo作品反编译器"""

	def __init__(self, work_info: dict[str, Any], compiled_work: dict[str, Any]) -> None:
		self.work_info = work_info
		self.work = compiled_work

	def start(self) -> dict[str, Any]:
		"""开始反编译"""
		self.write_work_info()
		self.clean()
		return self.work

	def clean(self) -> None:
		"""清理无用数据"""
		keys_to_remove = [
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
		for key in keys_to_remove:
			if key in self.work:
				del self.work[key]

	def write_work_info(self) -> None:
		"""写入作品信息"""
		self.work["authorId"] = self.work_info.get("author", {}).get("id", "")
		self.work["title"] = self.work_info["name"]
		self.work["screens"] = {}
		self.work["screenIds"] = []
		for screen in self.work["screenList"]:
			screen_id = screen["id"]
			screen["snapshot"] = ""
			self.work["screens"][screen_id] = screen
			self.work["screenIds"].append(screen_id)
			screen["primitiveVariables"] = []
			screen["arrayVariables"] = []
			screen["objectVariables"] = []
			screen["broadcasts"] = ["Hi"]
			screen["widgets"] = {}
			for widget_id in screen["widgetIds"] + screen["invisibleWidgetIds"]:
				screen["widgets"][widget_id] = self.work["widgetMap"][widget_id]
				del self.work["widgetMap"][widget_id]
		self.work["blockly"] = {}
		for screen_id, blocks in self.work["blockJsonMap"].items():
			self.work["blockly"][screen_id] = {"screenId": screen_id, "workspaceJson": blocks, "workspaceOffset": {"x": 0, "y": 0}}
		self.work["imageFileList"] = list(self.work["imageFileMap"].values())
		self.work["soundFileList"] = list(self.work["soundFileMap"].values())
		self.work["iconFileList"] = list(self.work["iconFileMap"].values())
		self.work["fontFileList"] = list(self.work["fontFileMap"].values())
		# 处理变量
		var_count = 0
		list_count = 0
		dict_count = 0
		self.work["globalVariableList"] = []
		self.work["globalArrayList"] = []
		self.work["globalObjectList"] = []
		for var_id, value in self.work["variableMap"].items():
			if isinstance(value, list):
				list_count += 1
				self.work["globalArrayList"].append({"id": var_id, "name": f"列表{list_count}", "defaultValue": value, "value": value})
			elif isinstance(value, dict):
				dict_count += 1
				self.work["globalObjectList"].append({"id": var_id, "name": f"字典{dict_count}", "defaultValue": value, "value": value})
			else:
				var_count += 1
				self.work["globalVariableList"].append({"id": var_id, "name": f"变量{var_count}", "defaultValue": value, "value": value})
		self.work["globalWidgets"] = self.work["widgetMap"]
		self.work["globalWidgetIds"] = list(self.work["widgetMap"].keys())
		self.work["sourceTag"] = 1
		self.work["sourceId"] = ""


# 使用示例
def decompile_work(work_id: int) -> str:
	"""
	反编译作品
	Args:
		work_id: 作品ID
	Returns:
		保存的文件路径
	"""
	decompiler = SimpleDecompiler()
	return decompiler.decompile_work(work_id)


if __name__ == "__main__":
	try:
		work_id = int(input("输入作品ID"))
		file_path = decompile_work(work_id)
		print(f"反编译完成,文件已保存到: {file_path}")
	except ValueError:
		print("错误: 作品ID必须是数字")
	except Exception as e:
		print(f"反编译失败: {e}")
