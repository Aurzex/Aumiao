from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from json import JSONDecodeError, dump, dumps, loads
from pathlib import Path
from random import choice
from typing import Any, ClassVar, Protocol, Self
from xml.etree import ElementTree as ET

from aumiao.api import auth
from aumiao.utils import acquire
from aumiao.utils.data import PathConfig
from aumiao.utils.tool import Crypto


# ============ 配置管理 ============
@dataclass(frozen=True)
class DecompilerConfig:
	"""反编译器配置 - 不可变值对象"""

	# API配置
	base_url: str = "https://api.codemao.cn"
	creation_base_url: str = "https://api-creation.codemao.cn"
	client_secret: str = "pBlYqXbJDu"
	crypto_salt: bytes = bytes(range(31))

	# 输出配置
	default_output_dir: Path = field(default_factory=lambda: PathConfig().COMPILE_FILE_PATH)

	# 工具箱分类顺序
	toolbox_categories: tuple[str, ...] = (
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
	)

	# 阴影积木类型
	shadow_types: frozenset[str] = field(
		default_factory=lambda: frozenset(
			{
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
		)
	)

	# 阴影积木字段配置
	shadow_fields: dict[str, dict[str, str]] = field(
		default_factory=lambda: {
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
			"get_sensing_current_scene": {"name": "scene", "text": ""},
		}
	)

	# 作品类型映射
	file_extensions: dict[str, str] = field(
		default_factory=lambda: {
			"KITTEN2": ".bcm",
			"KITTEN3": ".bcm",
			"KITTEN4": ".bcm4",
			"COCO": ".json",
			"NEKO": ".bcmkn",
			"NEMO": "",
			"WOOD": "",
		}
	)


# ============ 作品类型枚举 ============
class WorkType(Enum):
	"""作品类型枚举"""

	KITTEN2 = "KITTEN2"
	KITTEN3 = "KITTEN3"
	KITTEN4 = "KITTEN4"
	COCO = "COCO"
	NEKO = "NEKO"
	NEMO = "NEMO"
	WOOD = "WOOD"

	@property
	def is_kitten(self) -> bool:
		return self in {WorkType.KITTEN2, WorkType.KITTEN3, WorkType.KITTEN4}

	@property
	def is_nemo(self) -> bool:
		return self == WorkType.NEMO

	@property
	def is_neko(self) -> bool:
		return self == WorkType.NEKO

	@property
	def is_coco(self) -> bool:
		return self == WorkType.COCO

	@property
	def is_wood(self) -> bool:
		return self == WorkType.WOOD


# ============ 作品信息值对象 ============
@dataclass(frozen=True)
class WorkInfo:
	"""作品信息 - 不可变值对象"""

	id: int
	name: str
	type: WorkType
	version: str = ""
	user_id: int = 0
	preview_url: str = ""

	@classmethod
	def from_api_response(cls, data: dict[str, Any], _config: DecompilerConfig) -> "WorkInfo":
		"""从API响应创建作品信息"""
		work_type_str = data.get("type", "NEMO")
		try:
			work_type = WorkType(work_type_str)
		except ValueError:
			work_type = WorkType.NEMO

		return cls(
			id=data["id"],
			name=data.get("work_name", data.get("name", "未知作品")),
			type=work_type,
			version=data.get("bcm_version", "0.16.2"),
			user_id=data.get("user_id", 0),
			preview_url=data.get("preview", ""),
		)

	@property
	def file_extension(self) -> str:
		"""获取文件扩展名"""
		return DecompilerConfig().file_extensions.get(self.type.value, ".json")


# ============ 文件操作服务 ============
class FileService:
	"""文件操作服务"""

	def __init__(self, config: DecompilerConfig) -> None:
		self.config = config

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


# ============ ID生成器 ============
class IdGenerator:
	"""ID生成器 - 单例模式"""

	_instance = None
	CHARS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

	def __new__(cls) -> Self:
		if cls._instance is None:
			cls._instance = super().__new__(cls)
		return cls._instance

	def generate(self, length: int = 20) -> str:
		"""生成随机ID"""
		return "".join(choice(self.CHARS) for _ in range(length))


# ============ 加密解密服务 ============
class CryptoService:
	"""加密解密服务"""

	def __init__(self, salt: bytes) -> None:
		self.crypto = Crypto(salt)

	@staticmethod
	def sha256(data: str) -> str:
		"""计算SHA256哈希"""
		return Crypto.sha256(data)


class BCMKNDecryptor:
	"""BCMKN文件解密器 - 策略模式"""

	def __init__(self, crypto_service: CryptoService) -> None:
		self.crypto = crypto_service

	def decrypt(self, encrypted_content: str) -> dict[str, Any]:
		"""解密BCMKN数据"""
		# 步骤1: 字符串反转
		reversed_data = self.crypto.crypto.reverse_string(encrypted_content)
		# 步骤2: Base64解码
		decoded_data = self.crypto.crypto.base64_to_bytes(reversed_data)
		# 步骤3: 分离IV和密文(IV为前12字节)
		if len(decoded_data) < 13:
			msg = "数据太短,无法分离IV和密文"
			raise ValueError(msg)
		iv = decoded_data[:12]
		ciphertext = decoded_data[12:]
		# 步骤4: 生成AES密钥
		key = self.crypto.crypto.generate_aes_key()
		# 步骤5: AES-GCM解密
		decrypted_bytes = self.crypto.crypto.decrypt_aes_gcm(ciphertext, key, iv)
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
						loads(text[: i + 1])
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
				text = text[: last_valid + 1]
		return text


# ============ 阴影积木构建器 ============
class ShadowBuilder:
	"""阴影积木构建器 - 建造者模式"""

	def __init__(self, config: DecompilerConfig, id_generator: IdGenerator) -> None:
		self.config = config
		self.id_generator = id_generator

	def create(self, shadow_type: str, block_id: str | None = None, text: str | None = None) -> str:
		"""创建阴影积木"""
		if shadow_type == "logic_empty":
			block_id = block_id or self.id_generator.generate()
			return f'<empty type="logic_empty" id="{block_id}" visible="visible" editable="false"></empty>'

		config = self.config.shadow_fields.get(shadow_type, {})
		block_id = block_id or self.id_generator.generate()
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


# ============ HTTP客户端协议 ============


class HttpClient(Protocol):
	"""HTTP客户端协议"""

	def get_json(self, url: str, **kwargs: Any) -> dict[str, Any]:
		"""获取JSON数据"""
		...

	def get_binary(self, url: str) -> bytes:
		"""获取二进制数据"""
		...

	def get_text(self, url: str) -> str:
		"""获取文本数据"""
		...


class CodeMaoHttpClient:
	"""编程猫HTTP客户端适配器"""

	def __init__(self, client: acquire.CodeMaoClient) -> None:
		self._client = client

	def get_json(self, url: str, **kwargs: Any) -> dict[str, Any]:
		"""获取JSON数据"""
		return self._client.send_request(endpoint=url, method="GET", **kwargs).json()

	def get_binary(self, url: str) -> bytes:
		"""获取二进制数据"""
		return self._client.send_request(endpoint=url, method="GET").content

	def get_text(self, url: str) -> str:
		"""获取文本数据"""
		return self._client.send_request(endpoint=url, method="GET").text


# ============ 反编译器上下文 ============
@dataclass
class DecompilerContext:
	"""反编译器上下文"""

	work_info: WorkInfo
	http_client: HttpClient
	file_service: FileService
	id_generator: IdGenerator
	config: DecompilerConfig
	crypto_service: CryptoService | None


# ============ 反编译器基类 ============
class BaseDecompiler(ABC):
	"""反编译器抽象基类 - 模板方法模式"""

	def __init__(self, context: DecompilerContext) -> None:
		self.context = context

	@abstractmethod
	def decompile(self) -> dict[str, Any] | str:
		"""执行反编译 - 模板方法"""

	def save_result(self, result: dict[str, Any] | str, output_dir: str | Path | None = None) -> str:
		"""保存反编译结果"""
		if self.context.work_info.type.is_nemo or self.context.work_info.type.is_wood:
			if isinstance(result, str):
				return result
			msg = "Nemo与Wood作品应该返回字符串路径"
			raise TypeError(msg)

		output_path = Path(output_dir) if output_dir else self.context.config.default_output_dir
		self.context.file_service.ensure_dir(output_path)
		filename = self.context.file_service.safe_filename(self.context.work_info.name, self.context.work_info.id, self.context.work_info.file_extension.lstrip("."))
		filepath = output_path / filename
		if isinstance(result, dict):
			self.context.file_service.write_json(filepath, result)
		else:
			msg = "非Nemo作品应该返回字典"
			raise TypeError(msg)

		return str(filepath)


# ============ NEKO反编译器 ============
class NekoDecompiler(BaseDecompiler):
	"""NEKO作品反编译器"""

	def decompile(self) -> dict[str, Any]:
		"""反编译NEKO作品"""
		# 获取作品详情
		detail_url = f"{self.context.config.creation_base_url}/neko/community/player/published-work-detail/{self.context.work_info.id}"
		device_auth = dumps(auth.CloudAuthenticator().generate_x_device_auth())
		headers = {"x-creation-tools-device-auth": device_auth}

		detail = self.context.http_client.get_json(detail_url, headers=headers)
		encrypted_url = detail["source_urls"][0]
		# 下载并解密
		encrypted_content = self.context.http_client.get_text(encrypted_url)
		if not isinstance(self.context.crypto_service, CryptoService):
			msg = "NEKO作品需要有效的加密服务"
			raise TypeError(msg)
		decryptor = BCMKNDecryptor(self.context.crypto_service)
		return decryptor.decrypt(encrypted_content)


# ============ NEMO作品资源管理器 ============
class NemoResourceManager:
	"""NEMO作品资源管理器"""

	def __init__(self, context: DecompilerContext, work_dir: Path) -> None:
		self.context = context
		self.work_dir = work_dir
		self.dirs: dict[str, Path] = {}

	def create_directories(self, work_id: int) -> dict[str, Path]:
		"""创建目录结构"""
		self.dirs = {
			"material": self.context.file_service.ensure_dir(self.work_dir / "user_material"),
			"works": self.context.file_service.ensure_dir(self.work_dir / "user_works" / str(work_id)),
			"record": self.context.file_service.ensure_dir(self.work_dir / "user_works" / str(work_id) / "record"),
		}
		return self.dirs

	def save_core_files(self, work_id: int, bcm_data: dict[str, Any], source_info: dict[str, Any]) -> None:
		"""保存核心文件"""
		# 保存BCM文件
		self.context.file_service.write_json(self.dirs["works"] / f"{work_id}.bcm", bcm_data)
		# 保存用户图片配置
		user_images = self._build_user_images(bcm_data)
		self.context.file_service.write_json(self.dirs["works"] / f"{work_id}.userimg", user_images)
		# 保存元数据
		meta_data = self._build_metadata(work_id, source_info)
		self.context.file_service.write_json(self.dirs["works"] / f"{work_id}.meta", meta_data)
		# 下载封面
		if source_info.get("preview"):
			try:
				cover_data = self.context.http_client.get_binary(source_info["preview"])
				self.context.file_service.write_binary(self.dirs["works"] / f"{work_id}.cover", cover_data)
			except Exception as e:
				print(f"封面下载失败: {e}")

	@staticmethod
	def _build_user_images(bcm_data: dict[str, Any]) -> dict[str, Any]:
		"""构建用户图片配置"""
		user_images = {"user_img_dict": {}}
		styles = bcm_data.get("styles", {}).get("styles_dict", {})
		for style_id, style_data in styles.items():
			if image_url := style_data.get("url"):
				user_images["user_img_dict"][style_id] = {"id": style_id, "path": f"user_material/{Crypto.sha256(image_url)}.webp"}
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
			"upload_status": {"work_id": work_id, "have_uploaded": 2},
		}

	def download_resources(self, bcm_data: dict[str, Any]) -> None:
		"""下载资源文件"""
		styles = bcm_data.get("styles", {}).get("styles_dict", {})
		for style_data in styles.values():
			if image_url := style_data.get("url"):
				try:
					image_data = self.context.http_client.get_binary(image_url)
					filename = f"{Crypto.sha256(image_url)}.webp"
					self.context.file_service.write_binary(self.dirs["material"] / filename, image_data)
				except Exception as e:
					print(f"资源下载失败 {image_url}: {e}")


# ============ NEMO反编译器 ============
class NemoDecompiler(BaseDecompiler):
	"""NEMO作品反编译器"""

	def decompile(self) -> str:
		"""反编译NEMO作品为文件夹结构"""
		work_id = self.context.work_info.id
		folder_name = self.context.file_service.safe_filename(self.context.work_info.name, work_id, "")
		base_dir = self.context.config.default_output_dir
		work_dir = base_dir / folder_name
		resource_manager = NemoResourceManager(self.context, work_dir)
		source_info = self.context.http_client.get_json(f"{self.context.config.base_url}/creation-tools/v1/works/{work_id}/source/public")
		bcm_data = self.context.http_client.get_json(source_info["work_urls"][0])
		resource_manager.create_directories(work_id)
		resource_manager.save_core_files(work_id, bcm_data, source_info)
		resource_manager.download_resources(bcm_data)
		print("NEMO作品解密成功!")
		print("将反编译的文件复制到: /data/data/com.codemao.nemo/files/nemo_users_db")
		return str(work_dir)


# ============ 积木反编译上下文 ============
@dataclass
class BlockContext:
	"""积木反编译上下文"""

	actor_data: dict[str, Any]
	functions: dict[str, Any]
	shadow_builder: ShadowBuilder
	blocks: dict[str, dict[str, Any]] = field(default_factory=dict)
	connections: dict[str, dict[str, Any]] = field(default_factory=dict)


# ============ 积木反编译器基类 ============
class BlockDecompiler(ABC):
	"""积木反编译器基类 - 策略模式"""

	# 输出类型积木
	OUTPUT_BLOCK_TYPES = frozenset({"logic_boolean", "procedures_2_stable_parameter"})

	def __init__(self, compiled: dict[str, Any], context: BlockContext, config: DecompilerConfig) -> None:
		self.compiled = compiled
		self.context = context
		self.config = config
		self.block: dict[str, Any] = {}
		self.connection: dict[str, Any] = {}
		self.shadows: dict[str, str] = {}
		self.fields: dict[str, Any] = {}
		self.id = compiled["id"]
		self.type = compiled["type"]

	@abstractmethod
	def decompile(self) -> dict[str, Any]:
		"""反编译积木 - 模板方法"""
		self._setup_basic_info()
		self._process_next()
		self._process_children()
		self._process_conditions()
		self._process_params()
		return self.block

	def _setup_basic_info(self) -> None:
		"""设置基础信息"""
		is_shadow = self.type in self.config.shadow_types
		is_output = is_shadow or self.type in self.OUTPUT_BLOCK_TYPES

		self.block.update(
			{
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
				"parent_id": None,
			}
		)

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
					self.connection[child_block["id"]] = {"type": "input", "input_type": "statement", "input_name": input_name}
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
					self.connection[condition_block["id"]] = {"type": "input", "input_type": "value", "input_name": input_name}

				self.shadows[input_name] = self.context.shadow_builder.create("logic_empty", condition_block["id"])

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

		if param_block["type"] in self.config.shadow_types:
			# 纯阴影积木
			field_value = next(iter(param_block["fields"].values()), "")
			self.shadows[name] = self.context.shadow_builder.create(param_block["type"], param_block["id"], field_value)
		else:
			# 嵌入其他积木
			shadow_type = "logic_empty" if name in {"condition", "BOOL"} else "math_number"
			self.shadows[name] = self.context.shadow_builder.create(shadow_type)

		self.connection[param_block["id"]] = {"type": "input", "input_type": "value", "input_name": name}

	def _decompile_block(self, compiled: dict[str, Any]) -> dict[str, Any]:
		"""反编译子积木"""
		factory = BlockDecompilerFactory(self.config)
		decompiler = factory.create(compiled, self.context)
		return decompiler.decompile()


# ============ 具体积木反编译器 ============
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

			param_block = self._decompile_block(
				{
					"id": self.context.shadow_builder.id_generator.generate(),
					"kind": "domain_block",
					"type": "procedures_2_stable_parameter",
					"params": {"param_name": param_name, "param_default_value": ""},
				}
			)
			param_block["parent_id"] = self.block["id"]

			self.connection[param_block["id"]] = {"type": "input", "input_type": "value", "input_name": input_name}

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
		func_id = self.context.functions.get(name, {}).get("id", self.context.shadow_builder.id_generator.generate())

		if name not in self.context.functions:
			self.block["disabled"] = True

		self.shadows["NAME"] = ""
		self.fields["NAME"] = name

		mutation = ET.Element("mutation")
		mutation.set("name", name)
		mutation.set("def_id", func_id)

		for i, (param_name, param_value) in enumerate(self.compiled["params"].items()):
			param_block = self._decompile_block(param_value)

			self.shadows[f"ARG {i}"] = self.context.shadow_builder.create("default_value", param_block["id"])

			param_elem = ET.SubElement(mutation, "procedures_2_parameter_shadow")
			param_elem.set("name", param_name)
			param_elem.set("value", "0")

			self.connection[param_block["id"]] = {"type": "input", "input_type": "value", "input_name": f"ARG {i}"}

		self.block["mutation"] = ET.tostring(mutation, encoding="unicode")
		return self.block


# ============ 积木反编译器工厂 ============
class BlockDecompilerFactory:
	"""积木反编译器工厂"""

	_decompilers: ClassVar[dict[str, type[BlockDecompiler]]] = {
		"controls_if": IfBlockDecompiler,
		"controls_if_no_else": IfBlockDecompiler,
		"text_join": TextJoinDecompiler,
		"procedures_2_defnoreturn": FunctionDefDecompiler,
		"procedures_2_callnoreturn": FunctionCallDecompiler,
		"procedures_2_callreturn": FunctionCallDecompiler,
	}

	def __init__(self, config: DecompilerConfig) -> None:
		self.config = config

	def create(self, compiled: dict[str, Any], context: BlockContext) -> BlockDecompiler:
		"""创建积木反编译器实例"""
		block_type = compiled["type"]
		decompiler_class = self._decompilers.get(block_type)

		if decompiler_class is None:
			# 为未知类型的积木创建一个具体的默认实现
			return DefaultBlockDecompiler(compiled, context, self.config)

		return decompiler_class(compiled, context, self.config)


# 添加一个默认的积木反编译器实现
class DefaultBlockDecompiler(BlockDecompiler):
	"""默认积木反编译器 - 处理未知类型的积木"""

	def decompile(self) -> dict[str, Any]:
		"""使用基类的默认实现"""
		return super().decompile()


# ============ KITTEN作品反编译器 ============
class KittenDecompiler(BaseDecompiler):
	"""KITTEN作品反编译器"""

	def decompile(self) -> dict[str, Any]:
		"""反编译KITTEN作品"""
		# 获取编译数据
		compiled_data = self._fetch_compiled_data()
		work = compiled_data.copy()
		# 创建阴影构建器
		shadow_builder = ShadowBuilder(self.context.config, self.context.id_generator)
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
		block_factory = BlockDecompilerFactory(self.context.config)
		for name, func_data in functions.items():
			context = BlockContext({}, functions, shadow_builder)
			functions[name] = block_factory.create(func_data, context).decompile()
		# 第三遍: 反编译角色积木
		for actor_compiled, context in actors:
			self._decompile_actor_blocks(actor_compiled, context, block_factory)
		# 更新作品信息
		self._update_work_info(work)
		# 清理数据
		self._clean_work_data(work)
		return work

	def _fetch_compiled_data(self) -> dict[str, Any]:
		"""获取编译数据"""
		work_id = self.context.work_info.id
		url = f"{self.context.config.creation_base_url}/kitten/r2/work/player/load/{work_id}"
		compiled_url = self.context.http_client.get_json(url)["source_urls"][0]
		return self.context.http_client.get_json(compiled_url)

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
			"y": 0,
		}

	@staticmethod
	def _decompile_actor_blocks(actor_compiled: dict[str, Any], context: BlockContext, block_factory: BlockDecompilerFactory) -> None:
		"""反编译角色积木"""
		# 初始化角色积木数据
		context.actor_data["block_data_json"] = {"blocks": context.blocks, "connections": context.connections, "comments": {}}

		# 反编译所有积木
		for block_data in actor_compiled["compiled_block_map"].values():
			block_factory.create(block_data, context).decompile()

	def _update_work_info(self, work: dict[str, Any]) -> None:
		"""更新作品信息"""
		work.update(
			{
				"hidden_toolbox": {"toolbox": [], "blocks": []},
				"work_source_label": 0,
				"sample_id": "",
				"project_name": self.context.work_info.name,
				"toolbox_order": list(self.context.config.toolbox_categories),
				"last_toolbox_order": list(self.context.config.toolbox_categories),
			}
		)

	@staticmethod
	def _clean_work_data(work: dict[str, Any]) -> None:
		"""清理作品数据"""
		for key in ["compile_result", "preview", "author_nickname"]:
			work.pop(key, None)


# ============ COCO作品反编译器 ============
class CocoDecompiler(BaseDecompiler):
	"""COCO作品反编译器"""

	def decompile(self) -> dict[str, Any]:
		"""反编译COCO作品"""
		# 获取编译数据
		compiled_data = self._fetch_compiled_data()
		work = compiled_data.copy()

		# 重组数据
		reorganizer = CocoDataReorganizer(self.context)
		reorganizer.reorganize(work)

		return work

	def _fetch_compiled_data(self) -> dict[str, Any]:
		"""获取编译数据"""
		url = f"{self.context.config.creation_base_url}/coconut/web/work/{self.context.work_info.id}/load"
		compiled_url = self.context.http_client.get_json(url)["data"]["bcmc_url"]
		return self.context.http_client.get_json(compiled_url)


class CocoDataReorganizer:
	"""COCO数据重组器"""

	def __init__(self, context: DecompilerContext) -> None:
		self.context = context

	def reorganize(self, work: dict[str, Any]) -> None:
		"""重组数据"""
		work["authorId"] = self.context.work_info.user_id
		work["title"] = self.context.work_info.name
		work["screens"] = {}
		work["screenIds"] = []
		# 处理屏幕
		self._process_screens(work)
		# 处理积木
		self._process_blocks(work)
		# 处理资源
		self._process_resources(work)
		# 处理变量
		self._process_variables(work)
		# 处理全局部件
		work["globalWidgets"] = work["widgetMap"]
		work["globalWidgetIds"] = list(work["widgetMap"].keys())
		work["sourceId"] = ""
		work["sourceTag"] = 1
		# 清理数据
		self._clean_data(work)

	@staticmethod
	def _process_screens(work: dict[str, Any]) -> None:
		"""处理屏幕"""
		for screen in work["screenList"]:
			screen_id = screen["id"]
			screen["snapshot"] = ""
			screen.update({"primitiveVariables": [], "arrayVariables": [], "objectVariables": [], "broadcasts": ["Hi"], "widgets": {}})

			work["screens"][screen_id] = screen
			work["screenIds"].append(screen_id)

			# 移动部件到屏幕
			for widget_id in screen["widgetIds"] + screen["invisibleWidgetIds"]:
				screen["widgets"][widget_id] = work["widgetMap"][widget_id]
				del work["widgetMap"][widget_id]

	@staticmethod
	def _process_blocks(work: dict[str, Any]) -> None:
		"""处理积木"""
		work["blockly"] = {}
		for screen_id, blocks in work["blockJsonMap"].items():
			work["blockly"][screen_id] = {"screenId": screen_id, "workspaceJson": blocks, "workspaceOffset": {"x": 0, "y": 0}}

	@staticmethod
	def _process_resources(work: dict[str, Any]) -> None:
		"""处理资源文件"""
		resource_maps = [("imageFileMap", "imageFileList"), ("soundFileMap", "soundFileList"), ("iconFileMap", "iconFileList"), ("fontFileMap", "fontFileList")]

		for map_name, list_name in resource_maps:
			if map_name in work:
				work[list_name] = list(work[map_name].values())

	@staticmethod
	def _process_variables(work: dict[str, Any]) -> None:
		"""处理变量"""
		counters = {"var": 0, "list": 0, "dict": 0}
		variable_lists = {"globalVariableList": [], "globalArrayList": [], "globalObjectList": []}

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


# ============ WOOD作品资源管理器 ============
class WoodResourceManager:
	"""WOOD作品资源管理器"""

	def __init__(self, context: DecompilerContext, work_dir: Path) -> None:
		self.context = context
		self.work_dir = work_dir
		self.dirs: dict[str, Path] = {}

	def create_directories(self) -> dict[str, Path]:
		"""创建目录结构"""
		self.dirs = {"root": self.context.file_service.ensure_dir(self.work_dir), "images": self.context.file_service.ensure_dir(self.work_dir / "images")}
		return self.dirs

	def save_work_files(self, work_data: dict[str, Any]) -> None:
		"""保存作品文件"""
		# 保存作品信息元数据
		self._save_work_info(work_data)
		# 保存代码文件
		self._save_code_files(work_data)
		# 下载并保存图片资源
		self._download_images(work_data)

	def _save_work_info(self, work_data: dict[str, Any]) -> None:
		"""保存作品信息"""
		work_info = {
			"id": work_data["work_id"],
			"name": work_data["work_name"],
			"type": "WOOD",
			"language_type": work_data.get("language_type", 3),  # 3 表示Python
			"run_mode": work_data.get("run_mode", 0),
			"code_visible": work_data.get("code_visible", True),
			"addition": work_data.get("addition", {}),
		}
		self.context.file_service.write_json(self.dirs["root"] / "work_info.json", work_info)

	def _save_code_files(self, work_data: dict[str, Any]) -> None:
		"""保存代码文件"""
		for file_info in work_data.get("content", []):
			if file_info["file_type"] == 2 and file_info["file_name"].endswith(".py"):
				code_content = file_info.get("source", "")
				file_path = self.dirs["root"] / file_info["file_name"]
				file_path.write_text(code_content, encoding="utf-8")

	@staticmethod
	def _extract_filename_from_url(url: str) -> str:
		"""
		从URL中提取文件名
		"""
		# 查找最后一个 '/' 之后的部分
		last_slash = url.rfind("/")
		filename_part = url[last_slash + 1 :] if last_slash != -1 else url
		# 移除URL参数(?后面的部分)
		question_mark = filename_part.find("?")
		if question_mark != -1:
			filename_part = filename_part[:question_mark]
		# 移除锚点(#后面的部分)
		hash_mark = filename_part.find("#")
		if hash_mark != -1:
			filename_part = filename_part[:hash_mark]
		# 如果提取到的部分为空,使用默认名称
		if not filename_part:
			return ""

		return filename_part

	def _get_file_extension(self, url: str) -> str:
		"""
		从URL中获取文件扩展名
		"""
		filename = self._extract_filename_from_url(url)
		last_dot = filename.rfind(".")
		if last_dot != -1:
			return filename[last_dot:]
		return ""

	def _download_images(self, work_data: dict[str, Any]) -> None:
		"""下载图片资源"""
		for file_info in work_data.get("content", []):
			if file_info["file_type"] == 3 and file_info.get("url"):  # 图片文件
				image_url = file_info["url"]
				try:
					image_data = self.context.http_client.get_binary(image_url)
					file_name = file_info.get("file_name", "")
					if not file_name:
						file_name = self._extract_filename_from_url(image_url)
					if not file_name:
						file_name = "image.png"
					file_path = self.dirs["images"] / file_name
					self.context.file_service.write_binary(file_path, image_data)

				except Exception as e:
					print(f"图片下载失败 {image_url}: {e}")


# ============ WOOD反编译器 ============
class WoodDecompiler(BaseDecompiler):
	"""WOOD作品反编译器"""

	def decompile(self) -> str:
		"""
		反编译WOOD作品为文件夹结构
		"""
		work_id = self.context.work_info.id
		folder_name = self.context.file_service.safe_filename(self.context.work_info.name, work_id, "")
		base_dir = self.context.config.default_output_dir
		work_dir = base_dir / folder_name
		try:
			# 获取作品发布数据
			publish_url = f"{self.context.config.creation_base_url}/wood/work/{work_id}/publish?channel_type=0"
			work_data = self.context.http_client.get_json(publish_url)
			# 创建资源管理器
			resource_manager = WoodResourceManager(self.context, work_dir)
			# 创建目录结构并保存文件
			resource_manager.create_directories()
			resource_manager.save_work_files(work_data)
			return str(work_dir)
		except Exception as e:
			print(f"反编译失败: {e}")
			raise


# ============ 反编译器工厂 ============
class DecompilerFactory:
	"""反编译器工厂"""

	_decompilers: ClassVar[dict[WorkType, type[BaseDecompiler]]] = {
		WorkType.NEKO: NekoDecompiler,
		WorkType.NEMO: NemoDecompiler,
		WorkType.WOOD: WoodDecompiler,
		WorkType.KITTEN2: KittenDecompiler,
		WorkType.KITTEN3: KittenDecompiler,
		WorkType.KITTEN4: KittenDecompiler,
		WorkType.COCO: CocoDecompiler,
	}

	@classmethod
	def create(cls, work_info: WorkInfo, context: DecompilerContext) -> BaseDecompiler:
		"""创建反编译器实例"""
		decompiler_class = cls._decompilers.get(work_info.type)
		if not decompiler_class:
			msg = f"不支持的作品类型: {work_info.type.value}"
			raise ValueError(msg)
		return decompiler_class(context)

	@classmethod
	def register(cls, work_type: WorkType, decompiler_class: type[BaseDecompiler]) -> None:
		"""注册反编译器"""
		cls._decompilers[work_type] = decompiler_class


# ============ 主接口 ============
class CodemaoDecompiler:
	"""编程猫作品反编译器主接口"""

	def __init__(self, config: DecompilerConfig | None = None) -> None:
		"""初始化反编译器"""
		self.config = config or DecompilerConfig()
		self.client_factory = acquire.ClientFactory()
		self.id_generator = IdGenerator()

	def decompile(self, work_id: int, output_dir: str | Path | None = None) -> str:
		"""
		反编译作品

		Args:
			work_id: 作品ID
			output_dir: 输出目录, 为None时使用默认目录

		Returns:
			保存的文件路径
		"""
		context = self._create_context(work_id)
		decompiler = DecompilerFactory.create(context.work_info, context)
		result = decompiler.decompile()
		return decompiler.save_result(result, output_dir)

	def _create_context(self, work_id: int) -> DecompilerContext:
		"""创建反编译器上下文"""
		client = self.client_factory.create_codemao_client()
		http_client = CodeMaoHttpClient(client)
		work_info = self._fetch_work_info(http_client, work_id)
		file_service = FileService(self.config)
		crypto_service = CryptoService(self.config.crypto_salt) if work_info.type.is_neko else None
		return DecompilerContext(
			work_info=work_info, http_client=http_client, file_service=file_service, id_generator=self.id_generator, config=self.config, crypto_service=crypto_service
		)

	def _fetch_work_info(self, http_client: HttpClient, work_id: int) -> WorkInfo:
		"""获取作品信息"""
		url = f"{self.config.base_url}/creation-tools/v1/works/{work_id}"
		data = http_client.get_json(url)
		return WorkInfo.from_api_response(data, self.config)


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
