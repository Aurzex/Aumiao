from json import JSONDecodeError, dump, dumps, loads
from pathlib import Path
from random import choice
from typing import Any, ClassVar
from xml.etree import ElementTree as ET

from aumiao.api import auth
from aumiao.utils import acquire
from aumiao.utils.data import PathConfig
from aumiao.utils.tool import Crypto


class Configuration:
	"""配置管理器"""

	CLIENT_FACTORY = acquire.ClientFactory()
	AUTHENTICATOR = auth.AuthManager
	CRYPTO_SALT = bytes(range(31))
	CLIENT_SECRET = "pBlYqXbJDu"
	BASE_URL = "https://api.codemao.cn"
	CREATION_BASE_URL = "https://api-creation.codemao.cn"
	DEFAULT_OUTPUT_DIR = PathConfig().COMPILE_FILE_PATH
	TOOLBOX_CATEGORIES: ClassVar = [
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
	]


class InternalImplementations:
	"""内部实现模块"""

	class BCMKNDecryptor:
		"""BCMKN 文件解密器 - 用于 NEKO 类型作品"""

		def __init__(self) -> None:
			self.crypto = Crypto(Configuration.CRYPTO_SALT)

		def decrypt_data(self, encrypted_content: str) -> dict[str, Any]:
			"""解密 BCMKN 数据"""
			# 步骤 1: 字符串反转
			reversed_data = self.crypto.reverse_string(encrypted_content)
			# 步骤 2: Base64 解码
			decoded_data = self.crypto.base64_to_bytes(reversed_data)
			# 步骤 3: 分离 IV 和密文 (IV 为前 12 字节)
			MIN_DATA_LENGTH = 13  # noqa: N806
			if len(decoded_data) < MIN_DATA_LENGTH:
				msg = "数据太短, 无法分离 IV 和密文"
				raise ValueError(msg)
			iv = decoded_data[:12]
			ciphertext = decoded_data[12:]
			# 步骤 4: 生成 AES 密钥
			key = self.crypto.generate_aes_key()
			# 步骤 5: AES-GCM 解密
			decrypted_bytes = self.crypto.decrypt_aes_gcm(ciphertext, key, iv)
			# 清理和修复 JSON 数据
			return self._clean_and_repair_json(decrypted_bytes)

		@staticmethod
		def _find_valid_json_end(text: str) -> int:
			"""找到有效的 JSON 结束位置"""
			stack: list[str] = []
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
			if stack:
				for i in range(len(text) - 1, -1, -1):
					if text[i] in "}]":
						try:
							loads(text[: i + 1])
							return i + 1
						except JSONDecodeError:
							continue
			return len(text)

		def _clean_and_repair_json(self, raw_bytes: bytes) -> dict[str, Any]:
			"""清理和修复 JSON 数据"""
			text_content = raw_bytes.decode("utf-8", errors="ignore")
			# 查找有效的 JSON 结束位置
			valid_end = self._find_valid_json_end(text_content)
			if valid_end < len(text_content):
				text_content = text_content[:valid_end]
			# 尝试解析 JSON
			try:
				return loads(text_content)
			except JSONDecodeError:
				# 尝试修复常见的 JSON 问题
				repaired_content = self._repair_json(text_content)
				try:
					return loads(repaired_content)
				except JSONDecodeError as decode_error:
					error_msg = "JSON 解析失败, 数据可能已损坏"
					raise ValueError(error_msg) from decode_error

		@staticmethod
		def _repair_json(text: str) -> str:
			"""尝试修复 JSON 数据"""
			# 移除末尾的逗号
			text = text.rstrip()
			while text and text[-1] in ", \t\n\r":
				text = text[:-1]
			# 确保以 } 或 ] 结束
			if not text.endswith("}") and not text.endswith("]"):
				last_brace = text.rfind("}")
				last_bracket = text.rfind("]")
				last_valid = max(last_brace, last_bracket)
				if last_valid > 0:
					text = text[: last_valid + 1]
			return text

	class WorkInfo:
		"""作品信息容器"""

		def __init__(self, data: dict[str, Any]) -> None:
			self.id = data["id"]
			self.name = data.get("work_name", data.get("name", "未知作品"))
			self.type = data.get("type", "NEMO")
			self.version = data.get("bcm_version", "0.16.2")
			self.user_id = data.get("user_id", 0)
			self.preview_url = data.get("preview", "")
			self.source_urls = data.get("source_urls", data.get("work_urls", []))

		@property
		def file_extension(self) -> str:
			"""根据作品类型返回文件扩展名"""
			extensions = {
				"KITTEN2": ".bcm",
				"KITTEN3": ".bcm",
				"KITTEN4": ".bcm4",
				"COCO": ".json",
				"NEMO": "",
				"NEKO": ".json",
			}
			return extensions.get(self.type, ".json")

		@property
		def is_nemo(self) -> bool:
			"""是否为 Nemo 作品"""
			return self.type == "NEMO"

		@property
		def is_neko(self) -> bool:
			"""是否为 NEKO 作品"""
			return self.type == "NEKO"

	class FileHelper:
		"""文件操作工具类"""

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
		def ensure_dir(path: str | Path) -> None:
			"""确保目录存在"""
			Path(path).mkdir(parents=True, exist_ok=True)

		@staticmethod
		def write_json(path: str | Path, data: Any) -> None:
			"""写入 JSON 文件"""
			with Path(path).open("w", encoding="utf-8") as f:
				dump(data, f, ensure_ascii=False, indent=2)

		@staticmethod
		def write_binary(path: str | Path, data: bytes) -> None:
			"""写入二进制文件"""
			Path(path).write_bytes(data)

	class ShadowBuilder:
		"""阴影积木构建器"""

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
			"""生成随机 ID"""
			chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
			return "".join(choice(chars) for _ in range(length))

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
			for attr in ["constraints", "allow_text", "has_been_edited"]:
				if attr in config:
					field.set(attr, config[attr])
			return ET.tostring(shadow, encoding="unicode")

	class BaseDecompiler:
		"""反编译器基类"""

		def __init__(self, work_info: "InternalImplementations.WorkInfo", client: Any) -> None:
			self.work_info = work_info
			self.client = client
			self.shadow_builder = InternalImplementations.ShadowBuilder()

		def decompile(self) -> dict[str, Any] | str:
			"""反编译作品 - 子类必须实现"""
			raise NotImplementedError

	class NekoDecompiler(BaseDecompiler):
		"""NEKO 作品反编译器"""

		def decompile(self) -> dict[str, Any]:
			"""反编译 NEKO 作品"""
			print(f"开始解密 NEKO 作品: {self.work_info.id}")
			# 获取作品详情以获取加密文件 URL
			detail_url = f"{Configuration.CREATION_BASE_URL}/neko/community/player/published-work-detail/{self.work_info.id}"
			device_auth_dict = auth.CloudAuthenticator().generate_x_device_auth()
			device_auth_json = dumps(device_auth_dict)
			headers = {"x-creation-tools-device-auth": device_auth_json}
			try:
				detail_data = self.client.send_request(endpoint=detail_url, method="GET", headers=headers).json()
				encrypted_url = detail_data["source_urls"][0]
				print(f"获取加密文件 URL: {encrypted_url}")
			except Exception as e:
				error_msg = "获取作品详情失败"
				raise ValueError(error_msg) from e
			# 下载加密文件
			try:
				encrypted_content = self.client.send_request(endpoint=encrypted_url, method="GET").text
				print(f"下载加密数据完成, 长度: {len(encrypted_content)} 字符")
			except Exception as e:
				error_msg = "下载加密文件失败"
				raise ValueError(error_msg) from e
			# 解密文件
			decryptor = InternalImplementations.BCMKNDecryptor()
			try:
				decrypted_data = decryptor.decrypt_data(encrypted_content)
			except Exception as e:
				error_msg = "解密失败"
				raise ValueError(error_msg) from e
			else:
				return decrypted_data

	class NemoDecompiler(BaseDecompiler):
		"""Nemo 作品反编译器"""

		def decompile(self) -> str:
			"""反编译 Nemo 作品为文件夹结构"""
			work_id = self.work_info.id
			work_dir = Path(f"nemo_work_{work_id}")
			InternalImplementations.FileHelper.ensure_dir(work_dir)
			source_info = self.client.send_request(
				endpoint=f"{Configuration.BASE_URL}/creation-tools/v1/works/{work_id}/source/public",
				method="GET",
			).json()
			bcm_data = self.client.send_request(endpoint=source_info["work_urls"][0], method="GET").json()
			dirs = self._create_directories(work_dir, work_id)
			self._save_core_files(dirs, work_id, bcm_data, source_info)
			self._download_resources(dirs, bcm_data)
			print("NEMO 作品解密成功!")
			print("食用教程:")
			print("首先确保你有 ROOT 权限或者 MT 管理器")
			print("将反编译的文件复制到 NEMO 客户端数据目录")
			print("一般为 /data/data/com.codemao.nemo/files/nemo_users_db")
			print("重启客户端, 打开并保存一次")
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
				InternalImplementations.FileHelper.ensure_dir(path)
			return dirs

		def _save_core_files(self, dirs: dict[str, Path], work_id: int, bcm_data: dict[str, Any], source_info: dict[str, Any]) -> None:
			"""保存核心文件"""
			bcm_path = dirs["works"] / f"{work_id}.bcm"
			InternalImplementations.FileHelper.write_json(bcm_path, bcm_data)
			user_images = self._build_user_images(bcm_data)
			user_img_path = dirs["works"] / f"{work_id}.userimg"
			InternalImplementations.FileHelper.write_json(user_img_path, user_images)
			meta_data = self._build_metadata(work_id, source_info)
			meta_path = dirs["works"] / f"{work_id}.meta"
			InternalImplementations.FileHelper.write_json(meta_path, meta_data)
			if source_info.get("preview"):
				try:
					cover_data = self.client.send_request(endpoint=source_info["preview"], method="GET").content
					cover_path = dirs["works"] / f"{work_id}.cover"
					InternalImplementations.FileHelper.write_binary(cover_path, cover_data)
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
					user_images["user_img_dict"][style_id] = {
						"id": style_id,
						"path": f"user_material/{Crypto.sha256(image_url)}.webp",
					}
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

		def _download_resources(self, dirs: dict[str, Path], bcm_data: dict[str, Any]) -> None:
			"""下载资源文件"""
			styles = bcm_data.get("styles", {}).get("styles_dict", {})
			for style_data in styles.values():
				image_url = style_data.get("url")
				if image_url:
					try:
						image_data = self.client.send_request(endpoint=image_url, method="GET").content
						file_name = f"{Crypto.sha256(image_url)}.webp"
						file_path = dirs["material"] / file_name
						InternalImplementations.FileHelper.write_binary(file_path, image_data)
					except Exception as e:
						print(f"资源下载失败 {image_url}: {e}")

	class KittenDecompiler(BaseDecompiler):
		"""Kitten 作品反编译器"""

		def __init__(self, work_info: "InternalImplementations.WorkInfo", client: Any) -> None:
			super().__init__(work_info, client)
			self.functions: dict[str, Any] = {}

		def decompile(self) -> dict[str, Any]:
			"""反编译 Kitten 作品"""
			compiled_data = self._fetch_compiled_data()
			work = compiled_data.copy()
			self._decompile_actors(work)
			self._update_work_info(work)
			self._clean_work_data(work)
			return work

		def _fetch_compiled_data(self) -> dict[str, Any]:
			"""获取编译数据"""
			work_id = self.work_info.id
			if self.work_info.type in {"KITTEN2", "KITTEN3", "KITTEN4"}:
				url = f"{Configuration.CREATION_BASE_URL}/kitten/r2/work/player/load/{work_id}"
				compiled_url = self.client.send_request(endpoint=url, method="GET").json()["source_urls"][0]
			else:
				compiled_url = self.work_info.source_urls[0]
			return self.client.send_request(endpoint=compiled_url, method="GET").json()

		def _decompile_actors(self, work: dict[str, Any]) -> None:
			"""反编译所有角色"""
			actors = []
			for actor_data in work["compile_result"]:
				actor_info = self._get_actor_info(work, actor_data["id"])
				actor = self.ActorProcessor(self, actor_info, actor_data)
				actors.append(actor)
			for actor in actors:
				actor.prepare()
			for actor in actors:
				actor.process()

		@staticmethod
		def _get_actor_info(work: dict[str, Any], actor_id: str) -> dict[str, Any]:
			"""获取角色信息"""
			theatre = work["theatre"]
			if actor_id in theatre["actors"]:
				return theatre["actors"][actor_id]
			if actor_id in theatre["scenes"]:
				return theatre["scenes"][actor_id]
			print(f"警告: 角色 ID {actor_id} 在 actors 和 scenes 中均未找到, 使用空角色信息")
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

		def _update_work_info(self, work: dict[str, Any]) -> None:
			"""更新作品信息"""
			work.update(
				{
					"hidden_toolbox": {"toolbox": [], "blocks": []},
					"work_source_label": 0,
					"sample_id": "",
					"project_name": self.work_info.name,
					"toolbox_order": Configuration.TOOLBOX_CATEGORIES,
					"last_toolbox_order": Configuration.TOOLBOX_CATEGORIES,
				},
			)

		@staticmethod
		def _clean_work_data(work: dict[str, Any]) -> None:
			"""清理作品数据"""
			for key in ["compile_result", "preview", "author_nickname"]:
				work.pop(key, None)

		class ActorProcessor:
			"""角色处理器"""

			def __init__(
				self,
				decompiler: "InternalImplementations.KittenDecompiler",
				actor_info: dict[str, Any],
				compiled_data: dict[str, Any],
			) -> None:
				self.decompiler = decompiler
				self.actor_info = actor_info
				self.compiled_data = compiled_data
				self.blocks: dict[str, Any] = {}
				self.connections: dict[str, Any] = {}

			def prepare(self) -> None:
				"""准备阶段"""
				self.actor_info["block_data_json"] = {
					"blocks": self.blocks,
					"connections": self.connections,
					"comments": {},
				}

			def process(self) -> None:
				"""处理角色"""
				for func_name, func_data in self.compiled_data["procedures"].items():
					processor = self.decompiler.FunctionProcessor(func_data, self)
					self.decompiler.functions[func_name] = processor.process()
				for block_data in self.compiled_data["compiled_block_map"].values():
					self.process_block(block_data)

			def process_block(self, compiled: dict[str, Any]) -> dict[str, Any]:
				"""处理单个积木"""
				block_type = compiled["type"]
				if block_type == "controls_if":
					processor = self.decompiler.IfBlockProcessor(compiled, self)
				elif block_type == "text_join":
					processor = self.decompiler.TextJoinProcessor(compiled, self)
				elif block_type.startswith("procedures_2_def"):
					processor = self.decompiler.FunctionProcessor(compiled, self)
				elif block_type.startswith("procedures_2_call"):
					processor = self.decompiler.FunctionCallProcessor(compiled, self)
				else:
					processor = self.decompiler.BlockProcessor(compiled, self)
				return processor.process()

		class BlockProcessor:
			"""积木处理器基类"""

			def __init__(self, compiled: dict[str, Any], actor: "InternalImplementations.KittenDecompiler.ActorProcessor") -> None:
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
						"collapsed": False,
						"comment": None,
						"deletable": True,
						"disabled": False,
						"editable": True,
						"field_constraints": {},
						"field_extra_attr": {},
						"fields": self.fields,
						"id": block_id,
						"is_output": (block_type in shadow_types or block_type in {"logic_boolean", "procedures_2_stable_parameter"}),
						"is_shadow": block_type in shadow_types,
						"location": [0, 0],
						"movable": True,
						"mutation": "",
						"parent_id": None,
						"shadows": self.shadows,
						"type": block_type,
						"visible": "visible",
					},
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
							self.connection[child_block["id"]] = {
								"type": "input",
								"input_type": "statement",
								"input_name": input_name,
							}
							self.shadows[input_name] = ""

			def _process_conditions(self) -> None:
				"""处理条件积木"""
				if "conditions" in self.compiled:
					for i, condition in enumerate(self.compiled["conditions"]):
						condition_block = self.actor.process_block(condition)
						condition_block["parent_id"] = self.block["id"]
						input_name = f"IF {i}"
						if condition_block["type"] != "logic_empty":
							self.connection[condition_block["id"]] = {
								"type": "input",
								"input_type": "value",
								"input_name": input_name,
							}
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
							shadow = self.actor.decompiler.shadow_builder.create(
								param_type,
								param_block["id"],
								field_value,
							)
						else:
							shadow_type = "logic_empty" if name in {"condition", "BOOL"} else "math_number"
							shadow = self.actor.decompiler.shadow_builder.create(shadow_type)
						self.shadows[name] = shadow
						self.connection[param_block["id"]] = {
							"type": "input",
							"input_type": "value",
							"input_name": name,
						}
					else:
						self.fields[name] = value

			@staticmethod
			def _get_child_input_name(_index: int) -> str:
				return "DO"

		class IfBlockProcessor(BlockProcessor):
			"""条件积木处理器"""

			MIN_CONDITIONS_FOR_ELSE = 2

			def process(self) -> dict[str, Any]:
				block = super().process()
				children = self.compiled["child_block"]
				if len(children) == self.MIN_CONDITIONS_FOR_ELSE and children[-1] is None:
					self.shadows["EXTRA_ADD_ELSE"] = ""
				else:
					condition_count = len(self.compiled["conditions"])
					self.block["mutation"] = f'<mutation elseif="{condition_count - 1}" else="1"></mutation>'
					self.shadows["ELSE_TEXT"] = ""
				return block

			def _get_child_input_name(self, index: int) -> str:  # pyright: ignore [reportIncompatibleMethodOverride]  # ty:ignore [invalid-method-override]
				conditions_count = len(self.compiled["conditions"])
				return f"DO {index}" if index < conditions_count else "ELSE"

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
					input_name = f"PARAMS {i}"
					arg = ET.SubElement(mutation, "arg")
					arg.set("name", input_name)
					shadow = self.actor.decompiler.shadow_builder.create("math_number")
					self.shadows[input_name] = shadow
					param_block = self.actor.process_block(
						{
							"id": InternalImplementations.ShadowBuilder.generate_id(),
							"kind": "domain_block",
							"params": {"param_name": param_name, "param_default_value": ""},
							"type": "procedures_2_stable_parameter",
						},
					)
					param_block["parent_id"] = self.block["id"]
					self.connection[param_block["id"]] = {
						"type": "input",
						"input_type": "value",
						"input_name": input_name,
					}
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
					func_id = InternalImplementations.ShadowBuilder.generate_id()
					self.block["disabled"] = True
				self.shadows["NAME"] = ""
				self.fields["NAME"] = func_name
				mutation = ET.Element("mutation")
				mutation.set("name", func_name)
				mutation.set("def_id", func_id)
				for i, (param_name, param_value) in enumerate(self.compiled["params"].items()):
					param_block = self.actor.process_block(param_value)
					shadow = self.actor.decompiler.shadow_builder.create("default_value", param_block["id"])
					self.shadows[f"ARG {i}"] = shadow
					param_elem = ET.SubElement(mutation, "procedures_2_parameter_shadow")
					param_elem.set("name", param_name)
					param_elem.set("value", "0")
					self.connection[param_block["id"]] = {
						"type": "input",
						"input_type": "value",
						"input_name": f"ARG {i}",
					}
				self.block["mutation"] = ET.tostring(mutation, encoding="unicode")
				return self.block

	class CocoDecompiler(BaseDecompiler):
		"""CoCo 作品反编译器"""

		def decompile(self) -> dict[str, Any]:
			"""反编译 CoCo 作品"""
			compiled_data = self._fetch_compiled_data()
			work = compiled_data.copy()
			self._reorganize_data(work)
			self._clean_data(work)
			return work

		def _fetch_compiled_data(self) -> dict[str, Any]:
			"""获取编译数据"""
			work_id = self.work_info.id
			url = f"{Configuration.CREATION_BASE_URL}/coconut/web/work/{work_id}/load"
			compiled_url = self.client.send_request(endpoint=url, method="GET").json()["data"]["bcmc_url"]
			return self.client.send_request(endpoint=compiled_url, method="GET").json()

		def _reorganize_data(self, work: dict[str, Any]) -> None:
			"""重组数据"""
			work["authorId"] = self.work_info.user_id
			work["title"] = self.work_info.name
			work["screens"] = {}
			work["screenIds"] = []
			for screen in work["screenList"]:
				screen_id = screen["id"]
				screen["snapshot"] = ""
				work["screens"][screen_id] = screen
				work["screenIds"].append(screen_id)
				screen.update(
					{
						"arrayVariables": [],
						"broadcasts": ["Hi"],
						"objectVariables": [],
						"primitiveVariables": [],
						"widgets": {},
					},
				)
				for widget_id in screen["widgetIds"] + screen["invisibleWidgetIds"]:
					screen["widgets"][widget_id] = work["widgetMap"][widget_id]
					del work["widgetMap"][widget_id]
			work["blockly"] = {}
			for screen_id, blocks in work["blockJsonMap"].items():
				work["blockly"][screen_id] = {
					"screenId": screen_id,
					"workspaceJson": blocks,
					"workspaceOffset": {"x": 0, "y": 0},
				}
			self._process_resources(work)
			self._process_variables(work)
			work.update(
				{
					"globalWidgetIds": list(work["widgetMap"].keys()),
					"globalWidgets": work["widgetMap"],
					"sourceId": "",
					"sourceTag": 1,
				},
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
				"globalArrayList": [],
				"globalObjectList": [],
				"globalVariableList": [],
			}
			for var_id, value in work["variableMap"].items():
				if isinstance(value, list):
					counters["list"] += 1
					variable_lists["globalArrayList"].append(
						{
							"id": var_id,
							"name": f"列表 {counters['list']}",
							"defaultValue": value,
							"value": value,
						},
					)
				elif isinstance(value, dict):
					counters["dict"] += 1
					variable_lists["globalObjectList"].append(
						{
							"id": var_id,
							"name": f"字典 {counters['dict']}",
							"defaultValue": value,
							"value": value,
						},
					)
				else:
					counters["var"] += 1
					variable_lists["globalVariableList"].append(
						{
							"id": var_id,
							"name": f"变量 {counters['var']}",
							"defaultValue": value,
							"value": value,
						},
					)
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


class CodemaoDecompiler:
	"""高级接口 - 外部主要使用这个类"""

	def __init__(self) -> None:
		"""
		初始化反编译器
		Args:
			client_config: 客户端配置, 如为 None 则使用默认配置
		"""
		self.client = Configuration.CLIENT_FACTORY.create_codemao_client()
		self._decompiler_map = {
			"COCO": InternalImplementations.CocoDecompiler,
			"KITTEN2": InternalImplementations.KittenDecompiler,
			"KITTEN3": InternalImplementations.KittenDecompiler,
			"KITTEN4": InternalImplementations.KittenDecompiler,
			"NEKO": InternalImplementations.NekoDecompiler,
			"NEMO": InternalImplementations.NemoDecompiler,
		}

	def decompile(self, work_id: int, output_dir: Path | None = None) -> str:
		"""
		反编译作品
		Args:
			work_id: 作品 ID
			output_dir: 输出目录, 如为 None 则使用默认目录
		Returns:
			保存的文件路径
		"""
		if output_dir is None:
			output_dir = Configuration.DEFAULT_OUTPUT_DIR
		print(f"开始反编译作品 {work_id}...")
		# 获取作品信息
		url = f"{Configuration.BASE_URL}/creation-tools/v1/works/{work_id}"
		raw_info = self.client.send_request(endpoint=url, method="GET").json()
		work_info = InternalImplementations.WorkInfo(raw_info)
		print(f"✓ 作品: {work_info.name}")
		print(f"✓ 类型: {work_info.type}")
		# 选择对应的反编译器
		decompiler_class = self._decompiler_map.get(work_info.type)
		if not decompiler_class:
			error_msg = f"不支持的作品类型: {work_info.type}"
			raise ValueError(error_msg)
		decompiler = decompiler_class(work_info, self.client)
		result = decompiler.decompile()
		return self._save_result(result, work_info, output_dir)

	@staticmethod
	def _save_result(result: dict[str, Any] | str, work_info: InternalImplementations.WorkInfo, output_dir: Path) -> str:
		"""保存反编译结果"""
		InternalImplementations.FileHelper.ensure_dir(output_dir)
		if work_info.is_nemo:
			if isinstance(result, str):
				return result
			msg = "Nemo 作品应该返回字符串路径"
			raise TypeError(msg)
		file_name = InternalImplementations.FileHelper.safe_filename(
			work_info.name,
			work_info.id,
			work_info.file_extension.lstrip("."),
		)
		file_path = output_dir / file_name
		if isinstance(result, dict):
			InternalImplementations.FileHelper.write_json(file_path, result)
		else:
			msg = "非 Nemo 作品应该返回字典"
			raise TypeError(msg)
		return str(file_path)


# 向后兼容的函数
def decompile_work(work_id: int, output_dir: Path | None = None) -> str:
	"""
	反编译作品 (向后兼容的函数)
	Args:
		work_id: 作品 ID
		output_dir: 输出目录, 如为 None 则使用默认目录
	Returns:
		保存的文件路径
	"""
	decompiler = CodemaoDecompiler()
	return decompiler.decompile(work_id, output_dir)
