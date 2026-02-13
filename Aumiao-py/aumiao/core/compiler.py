from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from json import JSONDecodeError, dump, dumps, loads
from pathlib import Path
from random import choice
from typing import Any, ClassVar
from xml.etree import ElementTree as ET

from aumiao.api import auth
from aumiao.utils import acquire
from aumiao.utils.data import PathConfig
from aumiao.utils.tool import Crypto


# ============ 配置管理 ============
class DecompilerConfig:
	"""反编译器配置 - 不可变"""
	# API配置
	BASE_URL: str = "https://api.codemao.cn"
	CREATION_BASE_URL: str = "https://api-creation.codemao.cn"
	CLIENT_SECRET: str = "pBlYqXbJDu"
	CRYPTO_SALT: bytes = bytes(range(31))
	# 输出配置
	DEFAULT_OUTPUT_DIR: Path = PathConfig().COMPILE_FILE_PATH  # 直接赋值, 不要用field
	# 工具箱分类顺序
	TOOLBOX_CATEGORIES: tuple = (
		"action", "advanced", "ai", "ai_game", "ai_lab", "appearance",
		"arduino", "audio", "camera", "cloud_list", "cloud_variable",
		"cognitive", "control", "data", "event", "micro_bit", "midi_music",
		"mobile_control", "operator", "pen", "physic", "physics2", "procedure",
		"sensing", "video", "wee_make", "wood"
	)

	# 阴影积木类型
	SHADOW_TYPES: frozenset = frozenset({
		"broadcast_input", "controller_shadow", "default_value", "get_audios",
		"get_current_costume", "get_current_scene", "get_sensing_current_scene",
		"get_whole_audios", "lists_get", "logic_empty", "math_number", "text"
	})

	# 阴影积木字段配置
	SHADOW_FIELDS: dict[str, dict[str, str]] = {  # 直接赋值, 不要用field  # noqa: RUF012
		"math_number": {"name": "NUM", "text": "0", "constraints": "-Infinity,Infinity,0,", "allow_text": "true"},
		"controller_shadow": {"name": "NUM", "text": "0", "constraints": "-Infinity,Infinity,0,false"},
		"text": {"name": "TEXT", "text": ""},
		"lists_get": {"name": "VAR", "text": "?"},
		"broadcast_input": {"name": "MESSAGE", "text": "Hi"},
		"get_audios": {"name": "sound_id", "text": "?"},
		"get_whole_audios": {"name": "sound_id", "text": "all"},
		"get_current_costume": {"name": "style_id", "text": ""},
		"default_value": {"name": "TEXT", "text": "0", "has_been_edited": "false"},
		"get_current_scene": {"name": "scene", "text": ""},
		"get_sensing_current_scene": {"name": "scene", "text": ""}
	}

	# 作品类型映射
	FILE_EXTENSIONS: dict[str, str] = {  # 直接赋值, 不要用field  # noqa: RUF012
		"KITTEN2": ".bcm", "KITTEN3": ".bcm", "KITTEN4": ".bcm4",
		"COCO": ".json", "NEKO": ".json", "NEMO": ""
	}


# ============ 作品信息 ============

@dataclass
class WorkInfo:
	"""作品信息 - 值对象"""
	id: int
	name: str
	type: str
	version: str = "0.16.2"
	user_id: int = 0
	preview_url: str = ""
	source_urls: list[str] = field(default_factory=list)

	@classmethod
	def from_api_response(cls, data: dict[str, Any]) -> "WorkInfo":
		"""从API响应创建作品信息"""
		return cls(
			id=data["id"],
			name=data.get("work_name", data.get("name", "未知作品")),
			type=data.get("type", "NEMO"),
			version=data.get("bcm_version", "0.16.2"),
			user_id=data.get("user_id", 0),
			preview_url=data.get("preview", ""),
			source_urls=data.get("source_urls", data.get("work_urls", []))
		)

	@property
	def file_extension(self) -> str:
		"""获取文件扩展名"""
		return DecompilerConfig.FILE_EXTENSIONS.get(self.type, ".json")

	@property
	def is_nemo(self) -> bool:
		return self.type == "NEMO"

	@property
	def is_neko(self) -> bool:
		return self.type == "NEKO"

	@property
	def is_kitten(self) -> bool:
		return self.type in {"KITTEN2", "KITTEN3", "KITTEN4"}

	@property
	def is_coco(self) -> bool:
		return self.type == "COCO"


# ============ 工具类 ============

class FileHelper:
	"""文件操作工具类 - 静态方法"""

	@staticmethod
	def safe_filename(name: str, work_id: int, extension: str = "") -> str:
		"""生成安全文件名"""
		safe_name = "".join(c for c in name if c.isalnum() or c in {" ", "-", "_"}).strip()
		if not safe_name:
			safe_name = f"work_{work_id}"
		if extension and not extension.startswith("."):
			extension = f".{extension}"
		return f"{safe_name}_{work_id}{extension}"

	@staticmethod
	def ensure_dir(path: str | Path) -> Path:
		"""确保目录存在"""
		path = Path(path)
		path.mkdir(parents=True, exist_ok=True)
		return path

	@staticmethod
	def write_json(path: str | Path, data: Any) -> None:
		"""写入JSON文件"""
		with Path(path).open("w", encoding="utf-8") as f:
			dump(data, f, ensure_ascii=False, indent=2)

	@staticmethod
	def write_binary(path: str | Path, data: bytes) -> None:
		"""写入二进制文件"""
		Path(path).write_bytes(data)


class IdGenerator:
	"""ID生成器"""

	CHARS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

	@classmethod
	def generate(cls, length: int = 20) -> str:
		"""生成随机ID"""
		return "".join(choice(cls.CHARS) for _ in range(length))


class BCMKNDecryptor:
	"""BCMKN文件解密器 - 用于NEKO类型作品"""

	def __init__(self, salt: bytes = DecompilerConfig.CRYPTO_SALT) -> None:
		self.crypto = Crypto(salt)

	def decrypt(self, encrypted_content: str) -> dict[str, Any]:
		"""解密BCMKN数据"""
		# 步骤1: 字符串反转
		reversed_data = self.crypto.reverse_string(encrypted_content)
		# 步骤2: Base64解码
		decoded_data = self.crypto.base64_to_bytes(reversed_data)
		# 步骤3: 分离IV和密文(IV为前12字节)
		if len(decoded_data) < 13:
			msg = "数据太短,无法分离IV和密文"
			raise ValueError(msg)
		iv = decoded_data[:12]
		ciphertext = decoded_data[12:]
		# 步骤4: 生成AES密钥
		key = self.crypto.generate_aes_key()
		# 步骤5: AES-GCM解密
		decrypted_bytes = self.crypto.decrypt_aes_gcm(ciphertext, key, iv)
		# 步骤6: 解析JSON
		return self._parse_json(decrypted_bytes)

	def _parse_json(self, data: bytes) -> dict[str, Any]:
		"""解析并修复JSON数据"""
		text = data.decode("utf-8", errors="ignore")

		# 查找有效的JSON结束位置
		valid_end = self._find_valid_json_end(text)
		if valid_end < len(text):
			text = text[:valid_end]

		try:
			return loads(text)
		except JSONDecodeError:
			# 尝试修复
			repaired = self._repair_json(text)
			try:
				return loads(repaired)
			except JSONDecodeError as e:
				msg = "JSON解析失败,数据可能已损坏"
				raise ValueError(msg) from e

	@staticmethod
	def _find_valid_json_end(text: str) -> int:
		"""找到有效的JSON结束位置"""
		stack = []
		in_string = False
		escape = False

		for i, char in enumerate(text):
			if escape:
				escape = False
				continue
			if char == "\\":
				escape = True
				continue
			if char == '"':
				in_string = not in_string
				continue
			if in_string:
				continue
			if char in "{[":
				stack.append(char)
			elif char in "}]":
				if not stack:
					return i
				opening = stack.pop()
				if (opening == "{" and char != "}") or (opening == "[" and char != "]"):
					return i
				if not stack:
					return i + 1

		# 尝试从后往前找
		if stack:
			for i in range(len(text) - 1, -1, -1):
				if text[i] in "}]":
					try:
						loads(text[:i + 1])
						return i + 1
					except JSONDecodeError:
						continue
		return len(text)

	@staticmethod
	def _repair_json(text: str) -> str:
		"""尝试修复JSON"""
		text = text.rstrip()
		while text and text[-1] in ", \t\n\r":
			text = text[:-1]
		if not text.endswith("}") and not text.endswith("]"):
			last_brace = text.rfind("}")
			last_bracket = text.rfind("]")
			last_valid = max(last_brace, last_bracket)
			if last_valid > 0:
				text = text[:last_valid + 1]
		return text


class ShadowBuilder:
	"""阴影积木构建器"""

	def __init__(self) -> None:
		self.config = DecompilerConfig()

	def create(self, shadow_type: str, block_id: str | None = None, text: str | None = None) -> str:
		"""创建阴影积木"""
		if shadow_type == "logic_empty":
			block_id = block_id or IdGenerator.generate()
			return f'<empty type="logic_empty" id="{block_id}" visible="visible" editable="false"></empty>'

		config = self.config.SHADOW_FIELDS.get(shadow_type, {})
		block_id = block_id or IdGenerator.generate()
		display_text = text or config.get("text", "")

		shadow = ET.Element("shadow")
		shadow.set("type", shadow_type)
		shadow.set("id", block_id)
		shadow.set("visible", "visible")
		shadow.set("editable", "true")

		field = ET.SubElement(shadow, "field")
		field.set("name", config["name"])
		field.text = str(display_text)

		for attr in ["constraints", "allow_text", "has_been_edited"]:
			if attr in config:
				field.set(attr, config[attr])

		return ET.tostring(shadow, encoding="unicode")


# ============ 反编译器基类 ============

class BaseDecompiler(ABC):
	"""反编译器抽象基类"""

	def __init__(self, work_info: WorkInfo, client: acquire.CodeMaoClient) -> None:
		self.work_info = work_info
		self.client = client
		self.file_helper = FileHelper()
		self.id_generator = IdGenerator()

	@abstractmethod
	def decompile(self) -> dict[str, Any] | str:
		"""执行反编译"""

	def _fetch_json(self, url: str, **kwargs: Any) -> dict[str, Any]:
		"""获取JSON数据"""
		return self.client.send_request(endpoint=url, method="GET", **kwargs).json()

	def _fetch_binary(self, url: str) -> bytes:
		"""获取二进制数据"""
		return self.client.send_request(endpoint=url, method="GET").content

	def _fetch_text(self, url: str) -> str:
		"""获取文本数据"""
		return self.client.send_request(endpoint=url, method="GET").text


# ============ NEKO反编译器 ============

class NekoDecompiler(BaseDecompiler):
	"""NEKO作品反编译器"""

	def decompile(self) -> dict[str, Any]:
		"""反编译NEKO作品"""
		# 获取作品详情
		detail_url = f"{DecompilerConfig.CREATION_BASE_URL}/neko/community/player/published-work-detail/{self.work_info.id}"
		device_auth = dumps(auth.CloudAuthenticator().generate_x_device_auth())
		headers = {"x-creation-tools-device-auth": device_auth}

		detail = self._fetch_json(detail_url, headers=headers)
		encrypted_url = detail["source_urls"][0]

		# 下载并解密
		encrypted_content = self._fetch_text(encrypted_url)
		decryptor = BCMKNDecryptor()
		return decryptor.decrypt(encrypted_content)


# ============ NEMO反编译器 ============

class NemoDecompiler(BaseDecompiler):
	"""NEMO作品反编译器"""

	def decompile(self) -> str:
		"""反编译NEMO作品为文件夹结构"""
		work_id = self.work_info.id
		work_dir = Path(f"nemo_work_{work_id}")
		self.file_helper.ensure_dir(work_dir)

		# 获取作品源信息
		source_info = self._fetch_json(
			f"{DecompilerConfig.BASE_URL}/creation-tools/v1/works/{work_id}/source/public"
		)

		# 下载BCM数据
		bcm_data = self._fetch_json(source_info["work_urls"][0])

		# 创建目录结构
		dirs = self._create_directories(work_dir, work_id)

		# 保存核心文件
		self._save_core_files(dirs, work_id, bcm_data, source_info)

		# 下载资源
		self._download_resources(dirs, bcm_data)

		print("NEMO作品解密成功!")
		print("将反编译的文件复制到: /data/data/com.codemao.nemo/files/nemo_users_db")

		return str(work_dir)

	def _create_directories(self, base_dir: Path, work_id: int) -> dict[str, Path]:
		"""创建目录结构"""
		return {
			"material": self.file_helper.ensure_dir(base_dir / "user_material"),
			"works": self.file_helper.ensure_dir(base_dir / "user_works" / str(work_id)),
			"record": self.file_helper.ensure_dir(base_dir / "user_works" / str(work_id) / "record")
		}

	def _save_core_files(self, dirs: dict[str, Path], work_id: int, bcm_data: dict[str, Any], source_info: dict[str, Any]) -> None:
		"""保存核心文件"""
		# 保存BCM文件
		self.file_helper.write_json(dirs["works"] / f"{work_id}.bcm", bcm_data)

		# 保存用户图片配置
		user_images = self._build_user_images(bcm_data)
		self.file_helper.write_json(dirs["works"] / f"{work_id}.userimg", user_images)

		# 保存元数据
		meta_data = self._build_metadata(work_id, source_info)
		self.file_helper.write_json(dirs["works"] / f"{work_id}.meta", meta_data)

		# 下载封面
		if source_info.get("preview"):
			try:
				cover_data = self._fetch_binary(source_info["preview"])
				self.file_helper.write_binary(dirs["works"] / f"{work_id}.cover", cover_data)
			except Exception as e:
				print(f"封面下载失败: {e}")

	@staticmethod
	def _build_user_images(bcm_data: dict[str, Any]) -> dict[str, Any]:
		"""构建用户图片配置"""
		user_images = {"user_img_dict": {}}
		styles = bcm_data.get("styles", {}).get("styles_dict", {})
		for style_id, style_data in styles.items():
			if image_url := style_data.get("url"):
				user_images["user_img_dict"][style_id] = {
					"id": style_id,
					"path": f"user_material/{Crypto.sha256(image_url)}.webp"
				}
		return user_images

	@staticmethod
	def _build_metadata(work_id: int, source_info: dict[str, Any]) -> dict[str, Any]:
		"""构建元数据"""
		return {
			"bcm_count": {"block_cnt_without_invisible": 0.0, "block_cnt": 0.0, "entity_cnt": 1.0},
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
			"upload_status": {"work_id": work_id, "have_uploaded": 2}
		}

	def _download_resources(self, dirs: dict[str, Path], bcm_data: dict[str, Any]) -> None:
		"""下载资源文件"""
		styles = bcm_data.get("styles", {}).get("styles_dict", {})
		for style_data in styles.values():
			if image_url := style_data.get("url"):
				try:
					image_data = self._fetch_binary(image_url)
					filename = f"{Crypto.sha256(image_url)}.webp"
					self.file_helper.write_binary(dirs["material"] / filename, image_data)
				except Exception as e:
					print(f"资源下载失败 {image_url}: {e}")


# ============ 积木反编译器核心 ============

class BlockContext:
	"""积木反编译上下文"""

	def __init__(self, actor_data: dict[str, Any], functions: dict[str, Any], shadow_builder: ShadowBuilder) -> None:
		self.actor_data = actor_data
		self.blocks: dict[str, dict[str, Any]] = {}
		self.connections: dict[str, dict[str, Any]] = {}
		self.functions = functions
		self.shadow_builder = shadow_builder


class BlockDecompiler:
	"""积木反编译器基类"""

	# 输出类型积木
	OUTPUT_BLOCK_TYPES = frozenset({"logic_boolean", "procedures_2_stable_parameter"})

	def __init__(self, compiled: dict[str, Any], context: BlockContext) -> None:
		self.compiled = compiled
		self.context = context
		self.block: dict[str, Any] = {}
		self.connection: dict[str, Any] = {}
		self.shadows: dict[str, str] = {}
		self.fields: dict[str, Any] = {}
		self.id = compiled["id"]
		self.type = compiled["type"]

	def decompile(self) -> dict[str, Any]:
		"""反编译积木"""
		self._setup_basic_info()
		self._process_next()
		self._process_children()
		self._process_conditions()
		self._process_params()
		return self.block

	def _setup_basic_info(self) -> None:
		"""设置基础信息"""
		is_shadow = self.type in DecompilerConfig.SHADOW_TYPES
		is_output = is_shadow or self.type in self.OUTPUT_BLOCK_TYPES

		self.block.update({
			"id": self.id,
			"type": self.type,
			"location": [0, 0],
			"is_shadow": is_shadow,
			"is_output": is_output,
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
			"parent_id": None
		})

		self.context.blocks[self.id] = self.block
		self.context.connections[self.id] = self.connection

	def _process_next(self) -> None:
		"""处理下一个积木"""
		if "next_block" in self.compiled:
			next_block = self._decompile_block(self.compiled["next_block"])
			next_block["parent_id"] = self.id
			self.connection[next_block["id"]] = {"type": "next"}

	def _process_children(self) -> None:
		"""处理子积木(C型积木)"""
		if "child_block" in self.compiled:
			for i, child in enumerate(self.compiled["child_block"]):
				if child is not None:
					child_block = self._decompile_block(child)
					child_block["parent_id"] = self.id
					input_name = self._get_child_input_name(i)
					self.connection[child_block["id"]] = {
						"type": "input",
						"input_type": "statement",
						"input_name": input_name
					}
					self.shadows[input_name] = ""

	def _get_child_input_name(self, index: int) -> str:  # noqa: ARG002, PLR6301
		"""获取子积木输入名称"""
		return "DO"

	def _process_conditions(self) -> None:
		"""处理条件积木"""
		if "conditions" in self.compiled:
			for i, condition in enumerate(self.compiled["conditions"]):
				condition_block = self._decompile_block(condition)
				condition_block["parent_id"] = self.id
				input_name = f"IF{i}"

				if condition_block["type"] != "logic_empty":
					self.connection[condition_block["id"]] = {
						"type": "input",
						"input_type": "value",
						"input_name": input_name
					}

				self.shadows[input_name] = self.context.shadow_builder.create(
					"logic_empty", condition_block["id"]
				)

	def _process_params(self) -> None:
		"""处理参数"""
		for name, value in self.compiled.get("params", {}).items():
			if isinstance(value, dict):
				self._process_param_block(name, value)
			else:
				self.fields[name] = value

	def _process_param_block(self, name: str, param_data: dict[str, Any]) -> None:
		"""处理参数积木"""
		param_block = self._decompile_block(param_data)
		param_block["parent_id"] = self.id

		if param_block["type"] in DecompilerConfig.SHADOW_TYPES:
			# 纯阴影积木
			field_value = next(iter(param_block["fields"].values()), "")
			self.shadows[name] = self.context.shadow_builder.create(
				param_block["type"], param_block["id"], field_value
			)
		else:
			# 嵌入其他积木
			shadow_type = "logic_empty" if name in {"condition", "BOOL"} else "math_number"
			self.shadows[name] = self.context.shadow_builder.create(shadow_type)

		self.connection[param_block["id"]] = {
			"type": "input",
			"input_type": "value",
			"input_name": name
		}

	def _decompile_block(self, compiled: dict[str, Any]) -> dict[str, Any]:
		"""反编译子积木"""
		return get_block_decompiler(compiled, self.context).decompile()


class IfBlockDecompiler(BlockDecompiler):
	"""条件积木反编译器"""

	def decompile(self) -> dict[str, Any]:
		result = super().decompile()
		children = self.compiled["child_block"]

		if len(children) == 2 and children[-1] is None:
			self.shadows["EXTRA_ADD_ELSE"] = ""
		else:
			condition_count = len(self.compiled["conditions"])
			self.block["mutation"] = f'<mutation elseif="{condition_count - 1}" else="1"></mutation>'
			self.shadows["ELSE_TEXT"] = ""

		return result

	def _get_child_input_name(self, index: int) -> str:
		"""获取子积木输入名称"""
		conditions_count = len(self.compiled["conditions"])
		return f"DO {index}" if index < conditions_count else "ELSE"


class TextJoinDecompiler(BlockDecompiler):
	"""文本连接积木反编译器"""

	def decompile(self) -> dict[str, Any]:
		result = super().decompile()
		param_count = len(self.compiled["params"])
		self.block["mutation"] = f'<mutation items="{param_count}"></mutation>'
		return result


class FunctionDefDecompiler(BlockDecompiler):
	"""函数定义积木反编译器"""

	def decompile(self) -> dict[str, Any]:
		self._setup_basic_info()
		self._process_children()

		self.shadows["PROCEDURES_2_DEFNORETURN_DEFINE"] = ""
		self.shadows["PROCEDURES_2_DEFNORETURN_MUTATOR"] = ""
		self.fields["NAME"] = self.compiled["procedure_name"]

		mutation = ET.Element("mutation")

		for i, (param_name, _) in enumerate(self.compiled["params"].items()):
			input_name = f"PARAMS {i}"

			arg = ET.SubElement(mutation, "arg")
			arg.set("name", input_name)

			# 参数默认值积木
			self.shadows[input_name] = self.context.shadow_builder.create("math_number")

			param_block = self._decompile_block({
				"id": IdGenerator.generate(),
				"kind": "domain_block",
				"type": "procedures_2_stable_parameter",
				"params": {
					"param_name": param_name,
					"param_default_value": ""
				}
			})
			param_block["parent_id"] = self.block["id"]

			self.connection[param_block["id"]] = {
				"type": "input",
				"input_type": "value",
				"input_name": input_name
			}

		self.block["mutation"] = ET.tostring(mutation, encoding="unicode")
		return self.block

	def _get_child_input_name(self, index: int) -> str:  # noqa: ARG002, PLR6301
		"""获取子积木输入名称"""
		return "STACK"


class FunctionCallDecompiler(BlockDecompiler):
	"""函数调用积木反编译器"""

	def decompile(self) -> dict[str, Any]:
		self._setup_basic_info()
		self._process_next()

		name = self.compiled["procedure_name"]
		func_id = self.context.functions.get(name, {}).get("id", IdGenerator.generate())

		if name not in self.context.functions:
			self.block["disabled"] = True

		self.shadows["NAME"] = ""
		self.fields["NAME"] = name

		mutation = ET.Element("mutation")
		mutation.set("name", name)
		mutation.set("def_id", func_id)

		for i, (param_name, param_value) in enumerate(self.compiled["params"].items()):
			param_block = self._decompile_block(param_value)

			self.shadows[f"ARG {i}"] = self.context.shadow_builder.create(
				"default_value", param_block["id"]
			)

			param_elem = ET.SubElement(mutation, "procedures_2_parameter_shadow")
			param_elem.set("name", param_name)
			param_elem.set("value", "0")

			self.connection[param_block["id"]] = {
				"type": "input",
				"input_type": "value",
				"input_name": f"ARG {i}"
			}

		self.block["mutation"] = ET.tostring(mutation, encoding="unicode")
		return self.block


# 积木反编译器映射
BLOCK_DECOMPILER_MAP = {
	"controls_if": IfBlockDecompiler,
	"controls_if_no_else": IfBlockDecompiler,
	"text_join": TextJoinDecompiler,
	"procedures_2_defnoreturn": FunctionDefDecompiler,
	"procedures_2_callnoreturn": FunctionCallDecompiler,
	"procedures_2_callreturn": FunctionCallDecompiler
}


def get_block_decompiler(compiled: dict[str, Any], context: BlockContext) -> BlockDecompiler:
	"""获取积木反编译器实例"""
	block_type = compiled["type"]
	decompiler_class = BLOCK_DECOMPILER_MAP.get(block_type, BlockDecompiler)
	return decompiler_class(compiled, context)


# ============ KITTEN反编译器 ============

class KittenDecompiler(BaseDecompiler):
	"""KITTEN作品反编译器"""

	def decompile(self) -> dict[str, Any]:
		"""反编译KITTEN作品"""
		# 获取编译数据
		compiled_data = self._fetch_compiled_data()
		work = compiled_data.copy()

		# 创建阴影构建器
		shadow_builder = ShadowBuilder()

		# 存储函数定义
		functions: dict[str, Any] = {}

		# 反编译所有角色
		actors = []
		for actor_compiled in work["compile_result"]:
			actor_info = self._get_actor_info(work, actor_compiled["id"])
			context = BlockContext(actor_info, functions, shadow_builder)
			actors.append((actor_compiled, context))

		# 第一遍: 收集函数定义
		for actor_compiled, _context in actors:
			functions.update(dict(actor_compiled["procedures"].items()))

		# 第二遍: 反编译函数定义
		for name, func_data in functions.items():
			context = BlockContext({}, functions, shadow_builder)  # 临时上下文
			functions[name] = FunctionDefDecompiler(func_data, context).decompile()

		# 第三遍: 反编译角色积木
		for actor_compiled, context in actors:
			self._decompile_actor_blocks(actor_compiled, context)

		# 更新作品信息
		self._update_work_info(work)

		# 清理数据
		self._clean_work_data(work)

		return work

	def _fetch_compiled_data(self) -> dict[str, Any]:
		"""获取编译数据"""
		work_id = self.work_info.id

		if self.work_info.is_kitten:
			url = f"{DecompilerConfig.CREATION_BASE_URL}/kitten/r2/work/player/load/{work_id}"
			compiled_url = self._fetch_json(url)["source_urls"][0]
		else:
			compiled_url = self.work_info.source_urls[0]

		return self._fetch_json(compiled_url)

	@staticmethod
	def _get_actor_info(work: dict[str, Any], actor_id: str) -> dict[str, Any]:
		"""获取角色信息"""
		theatre = work["theatre"]
		if actor_id in theatre.get("actors", {}):
			return theatre["actors"][actor_id]
		if actor_id in theatre.get("scenes", {}):
			return theatre["scenes"][actor_id]

		return {
			"direction": 90,
			"draggable": False,
			"id": actor_id,
			"name": f"未知角色_{actor_id[:8]}",
			"rotation_style": "all around",
			"size": 100,
			"type": "sprite",
			"visible": True,
			"x": 0,
			"y": 0
		}

	def _decompile_actor_blocks(self, actor_compiled: dict[str, Any], context: BlockContext) -> None:  # noqa: PLR6301
		"""反编译角色积木"""
		# 初始化角色积木数据
		context.actor_data["block_data_json"] = {
			"blocks": context.blocks,
			"connections": context.connections,
			"comments": {}
		}

		# 反编译所有积木
		for block_data in actor_compiled["compiled_block_map"].values():
			get_block_decompiler(block_data, context).decompile()

	def _update_work_info(self, work: dict[str, Any]) -> None:
		"""更新作品信息"""
		work.update({
			"hidden_toolbox": {"toolbox": [], "blocks": []},
			"work_source_label": 0,
			"sample_id": "",
			"project_name": self.work_info.name,
			"toolbox_order": list(DecompilerConfig.TOOLBOX_CATEGORIES),
			"last_toolbox_order": list(DecompilerConfig.TOOLBOX_CATEGORIES)
		})

	@staticmethod
	def _clean_work_data(work: dict[str, Any]) -> None:
		"""清理作品数据"""
		for key in ["compile_result", "preview", "author_nickname"]:
			work.pop(key, None)


# ============ COCO反编译器 ============

class CocoDecompiler(BaseDecompiler):
	"""COCO作品反编译器"""

	def decompile(self) -> dict[str, Any]:
		"""反编译COCO作品"""
		# 获取编译数据
		compiled_data = self._fetch_compiled_data()
		work = compiled_data.copy()

		# 重组数据
		self._reorganize_data(work)

		# 清理数据
		self._clean_data(work)

		return work

	def _fetch_compiled_data(self) -> dict[str, Any]:
		"""获取编译数据"""
		url = f"{DecompilerConfig.CREATION_BASE_URL}/coconut/web/work/{self.work_info.id}/load"
		compiled_url = self._fetch_json(url)["data"]["bcmc_url"]
		return self._fetch_json(compiled_url)

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
			screen.update({
				"primitiveVariables": [],
				"arrayVariables": [],
				"objectVariables": [],
				"broadcasts": ["Hi"],
				"widgets": {}
			})

			work["screens"][screen_id] = screen
			work["screenIds"].append(screen_id)

			# 移动部件到屏幕
			for widget_id in screen["widgetIds"] + screen["invisibleWidgetIds"]:
				screen["widgets"][widget_id] = work["widgetMap"][widget_id]
				del work["widgetMap"][widget_id]

		# 处理积木
		work["blockly"] = {}
		for screen_id, blocks in work["blockJsonMap"].items():
			work["blockly"][screen_id] = {
				"screenId": screen_id,
				"workspaceJson": blocks,
				"workspaceOffset": {"x": 0, "y": 0}
			}

		# 处理资源
		self._process_resources(work)

		# 处理变量
		self._process_variables(work)

		# 处理全局部件
		work["globalWidgets"] = work["widgetMap"]
		work["globalWidgetIds"] = list(work["widgetMap"].keys())
		work["sourceId"] = ""
		work["sourceTag"] = 1

	@staticmethod
	def _process_resources(work: dict[str, Any]) -> None:
		"""处理资源文件"""
		resource_maps = [
			("imageFileMap", "imageFileList"),
			("soundFileMap", "soundFileList"),
			("iconFileMap", "iconFileList"),
			("fontFileMap", "fontFileList")
		]

		for map_name, list_name in resource_maps:
			if map_name in work:
				work[list_name] = list(work[map_name].values())

	@staticmethod
	def _process_variables(work: dict[str, Any]) -> None:
		"""处理变量"""
		counters = {"var": 0, "list": 0, "dict": 0}
		variable_lists = {
			"globalVariableList": [],
			"globalArrayList": [],
			"globalObjectList": []
		}

		for var_id, value in work["variableMap"].items():
			if isinstance(value, list):
				counters["list"] += 1
				variable_lists["globalArrayList"].append({
					"id": var_id,
					"name": f"列表{counters['list']}",
					"defaultValue": value,
					"value": value
				})
			elif isinstance(value, dict):
				counters["dict"] += 1
				variable_lists["globalObjectList"].append({
					"id": var_id,
					"name": f"字典{counters['dict']}",
					"defaultValue": value,
					"value": value
				})
			else:
				counters["var"] += 1
				variable_lists["globalVariableList"].append({
					"id": var_id,
					"name": f"变量{counters['var']}",
					"defaultValue": value,
					"value": value
				})

		work.update(variable_lists)

	@staticmethod
	def _clean_data(work: dict[str, Any]) -> None:
		"""清理数据"""
		remove_keys = [
			"apiToken", "blockCode", "blockJsonMap", "fontFileMap",
			"gridMap", "iconFileMap", "id", "imageFileMap",
			"initialScreenId", "screenList", "soundFileMap",
			"variableMap", "widgetMap"
		]

		for key in remove_keys:
			work.pop(key, None)


# ============ 反编译器工厂 ============

class DecompilerFactory:
	"""反编译器工厂"""

	_decompilers: ClassVar[dict[str, type[BaseDecompiler]]] = {
		"NEKO": NekoDecompiler,
		"NEMO": NemoDecompiler,
		"KITTEN2": KittenDecompiler,
		"KITTEN3": KittenDecompiler,
		"KITTEN4": KittenDecompiler,
		"COCO": CocoDecompiler
	}

	@classmethod
	def create(cls, work_info: WorkInfo, client: acquire.CodeMaoClient) -> BaseDecompiler:
		"""创建反编译器实例"""
		decompiler_class = cls._decompilers.get(work_info.type)
		if not decompiler_class:
			msg = f"不支持的作品类型: {work_info.type}"
			raise ValueError(msg)
		return decompiler_class(work_info, client)

	@classmethod
	def register(cls, work_type: str, decompiler_class: type[BaseDecompiler]) -> None:
		"""注册反编译器"""
		cls._decompilers[work_type] = decompiler_class


# ============ 主接口 ============

class CodemaoDecompiler:
	"""编程猫作品反编译器主接口"""

	def __init__(self) -> None:
		"""初始化反编译器"""
		self.client_factory = acquire.ClientFactory()
		self.client = self.client_factory.create_codemao_client()

	def decompile(self, work_id: int, output_dir: str | Path | None = None) -> str:
		"""
		反编译作品

		Args:
			work_id: 作品ID
			output_dir: 输出目录, 为None时使用默认目录

		Returns:
			保存的文件路径
		"""
		# 获取作品信息
		work_info = self._fetch_work_info(work_id)

		# 创建反编译器
		decompiler = DecompilerFactory.create(work_info, self.client)

		# 执行反编译
		result = decompiler.decompile()

		# 保存结果
		return self._save_result(result, work_info, output_dir)

	def _fetch_work_info(self, work_id: int) -> WorkInfo:
		"""获取作品信息"""
		url = f"{DecompilerConfig.BASE_URL}/creation-tools/v1/works/{work_id}"
		data = self.client.send_request(endpoint=url, method="GET").json()
		return WorkInfo.from_api_response(data)

	@staticmethod
	def _save_result(result: dict[str, Any] | str,
					work_info: WorkInfo,
					output_dir: str | Path | None = None) -> str:
		"""保存反编译结果"""
		output_path = Path(output_dir) if output_dir else DecompilerConfig.DEFAULT_OUTPUT_DIR
		FileHelper.ensure_dir(output_path)

		if work_info.is_nemo:
			if isinstance(result, str):
				return result
			msg = "Nemo作品应该返回字符串路径"
			raise TypeError(msg)

		filename = FileHelper.safe_filename(
			work_info.name,
			work_info.id,
			work_info.file_extension.lstrip(".")
		)
		filepath = output_path / filename

		if isinstance(result, dict):
			FileHelper.write_json(filepath, result)
		else:
			msg = "非Nemo作品应该返回字典"
			raise TypeError(msg)

		return str(filepath)


# ============ 向后兼容接口 ============

def decompile_work(work_id: int, output_dir: str | Path | None = None) -> str:
	"""
	反编译作品 (向后兼容)

	Args:
		work_id: 作品ID
		output_dir: 输出目录

	Returns:
		保存的文件路径
	"""
	decompiler = CodemaoDecompiler()
	return decompiler.decompile(work_id, output_dir)
