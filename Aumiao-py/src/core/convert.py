import json
import math
import operator
import struct
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Color:
	r: int
	g: int
	b: int
	a: int = 255


@dataclass
class Voxel:
	x: int
	y: int
	z: int
	color_index: int


@dataclass
class VoxModel:
	size_x: int
	size_y: int
	size_z: int
	voxels: list[Voxel]
	palette: list[Color]


class VoxReader:
	"""Vox文件读取器"""

	VOX_VERSION = 150
	CHUNK_HEADER_SIZE = 12

	@staticmethod
	def read_vox(filename: str) -> VoxModel:  # noqa: PLR0914
		"""读取vox文件"""
		with Path(filename).open("rb") as f:
			data = f.read()
		# 检查文件头
		magic = data[0:4]
		if magic != b"VOX ":
			error_msg = "无效的 VOX 文件"
			raise ValueError(error_msg)
		version = struct.unpack("<I", data[4:8])[0]
		if version != VoxReader.VOX_VERSION:
			print(f"警告: VOX 版本 {version}, 期望 {VoxReader.VOX_VERSION}")
		# 查找MAIN块
		main_chunk = VoxReader._find_chunk(data[8:], b"MAIN")
		if not main_chunk:
			error_msg = "未找到 MAIN 块"
			raise ValueError(error_msg)
		# 在MAIN块中查找SIZE和XYZI
		size_chunk = VoxReader._find_chunk(main_chunk, b"SIZE")
		xyzi_chunk = VoxReader._find_chunk(main_chunk, b"XYZI")
		rgba_chunk = VoxReader._find_chunk(main_chunk, b"RGBA")
		if not size_chunk or not xyzi_chunk:
			error_msg = "未找到 SIZE 或 XYZI 块"
			raise ValueError(error_msg)
		# 读取尺寸
		size_data = size_chunk[8:20]  # 跳过chunk id和内容大小
		size_x, size_y, size_z = struct.unpack("<III", size_data[:12])
		# 读取体素数据
		xyzi_data = xyzi_chunk[8:]
		num_voxels = struct.unpack("<I", xyzi_data[:4])[0]
		voxels = []
		for i in range(num_voxels):
			offset = 4 + i * 4
			x, y, z, color_index = struct.unpack("<BBBB", xyzi_data[offset : offset + 4])
			voxels.append(Voxel(x, y, z, color_index))
		# 读取调色板
		palette = VoxReader._get_default_palette()
		if rgba_chunk:
			rgba_data = rgba_chunk[8:]
			for i in range(256):
				offset = i * 4
				if offset + 4 <= len(rgba_data):
					r, g, b, a = struct.unpack("<BBBB", rgba_data[offset : offset + 4])
					palette[i] = Color(r, g, b, a)
		return VoxModel(size_x, size_y, size_z, voxels, palette)

	@staticmethod
	def _find_chunk(data: bytes, chunk_id: bytes) -> bytes | None:
		"""在数据中查找指定chunk"""
		pos = 0
		while pos < len(data):
			if len(data) - pos < VoxReader.CHUNK_HEADER_SIZE:
				break
			current_id = data[pos : pos + 4]
			content_size = struct.unpack("<I", data[pos + 4 : pos + 8])[0]
			# children_size变量未使用,但为了完整性保留
			_ = struct.unpack("<I", data[pos + 8 : pos + 12])[0]
			if current_id == chunk_id:
				return data[pos : pos + VoxReader.CHUNK_HEADER_SIZE + content_size]
			pos += VoxReader.CHUNK_HEADER_SIZE + content_size
		return None

	@staticmethod
	def _get_default_palette() -> list[Color]:
		"""获取默认调色板"""
		palette = []
		for i in range(256):
			r = (i * 67) % 256
			g = (i * 101) % 256
			b = (i * 37) % 256
			palette.append(Color(r, g, b))
		return palette


class VoxWriter:
	"""Vox文件写入器"""

	@staticmethod
	def write_vox(model: VoxModel, filename: str) -> None:
		"""写入vox文件"""
		chunks = []
		# SIZE chunk
		size_data = struct.pack("<III", model.size_x, model.size_y, model.size_z)
		size_chunk = VoxWriter._create_chunk(b"SIZE", size_data)
		chunks.append(size_chunk)
		# XYZI chunk
		num_voxels = len(model.voxels)
		xyzi_data = struct.pack("<I", num_voxels)
		for voxel in model.voxels:
			xyzi_data += struct.pack("<BBBB", voxel.x, voxel.y, voxel.z, voxel.color_index)
		xyzi_chunk = VoxWriter._create_chunk(b"XYZI", xyzi_data)
		chunks.append(xyzi_chunk)
		# RGBA chunk (palette)
		rgba_data = b""
		for color in model.palette:
			rgba_data += struct.pack("<BBBB", color.r, color.g, color.b, color.a)
		rgba_chunk = VoxWriter._create_chunk(b"RGBA", rgba_data)
		chunks.append(rgba_chunk)
		# MAIN chunk
		main_content = b"".join(chunks)
		main_chunk = VoxWriter._create_chunk(b"MAIN", main_content, 0)
		# 文件头
		header = b"VOX " + struct.pack("<I", VoxReader.VOX_VERSION)
		# 写入文件
		with Path(filename).open("wb") as f:
			f.write(header)
			f.write(main_chunk)

	@staticmethod
	def _create_chunk(chunk_id: bytes, content: bytes, children_size: int = 0) -> bytes:
		"""创建chunk"""
		content_size = len(content)
		return chunk_id + struct.pack("<III", content_size, children_size, 0) + content


class Box3Converter:
	"""Box3转换器"""

	MAX_PALETTE_SIZE = 256

	def __init__(self, blocks_data_file: str = "blocks.json") -> None:
		"""初始化转换器"""
		self.blocks_data = self._load_blocks_data(blocks_data_file)
		self.color_blocks = self._create_color_mapping()

	@staticmethod
	def _load_blocks_data(filename: str) -> dict:
		"""加载方块数据"""
		if Path(filename).exists():
			with Path(filename).open(encoding="utf-8") as f:
				return json.load(f)
		else:
			# 创建默认方块数据
			blocks_data = {
				"id2name": {
					"0": "air",
					"1": "stone",
					"2": "grass",
					"3": "dirt",
					"4": "cobblestone",
					"5": "planks",
					"6": "sapling",
					"7": "bedrock",
					"8": "water",
					"9": "lava",
					"10": "sand",
					"11": "gravel",
					"12": "gold_ore",
					"13": "iron_ore",
					"14": "coal_ore",
					"15": "wood",
					"16": "leaves",
					"17": "sponge",
					"18": "glass",
					"19": "red_wool",
					"20": "orange_wool",
					"21": "yellow_wool",
					"22": "lime_wool",
					"23": "green_wool",
					"24": "cyan_wool",
					"25": "blue_wool",
					"26": "purple_wool",
					"27": "magenta_wool",
					"28": "pink_wool",
					"29": "brown_wool",
					"30": "white_wool",
					"31": "black_wool",
				},
				"name2id": {
					"air": 0,
					"stone": 1,
					"grass": 2,
					"dirt": 3,
					"cobblestone": 4,
					"planks": 5,
					"sapling": 6,
					"bedrock": 7,
					"water": 8,
					"lava": 9,
					"sand": 10,
					"gravel": 11,
					"gold_ore": 12,
					"iron_ore": 13,
					"coal_ore": 14,
					"wood": 15,
					"leaves": 16,
					"sponge": 17,
					"glass": 18,
					"red_wool": 19,
					"orange_wool": 20,
					"yellow_wool": 21,
					"lime_wool": 22,
					"green_wool": 23,
					"cyan_wool": 24,
					"blue_wool": 25,
					"purple_wool": 26,
					"magenta_wool": 27,
					"pink_wool": 28,
					"brown_wool": 29,
					"white_wool": 30,
					"black_wool": 31,
				},
			}
			# 保存默认数据
			with Path(filename).open("w", encoding="utf-8") as f:
				json.dump(blocks_data, f, indent=2)
			print(f"已创建默认方块数据文件: {filename}")
			return blocks_data

	@staticmethod
	def _create_color_mapping() -> dict[str, Color]:
		"""创建颜色映射"""
		return {
			"stone": Color(128, 128, 128),
			"grass": Color(0, 128, 0),
			"dirt": Color(139, 69, 19),
			"cobblestone": Color(112, 112, 112),
			"planks": Color(205, 133, 63),
			"bedrock": Color(64, 64, 64),
			"water": Color(64, 64, 255),
			"lava": Color(255, 64, 0),
			"sand": Color(237, 201, 175),
			"gravel": Color(136, 126, 125),
			"gold_ore": Color(255, 215, 0),
			"iron_ore": Color(210, 180, 140),
			"coal_ore": Color(64, 64, 64),
			"wood": Color(160, 120, 80),
			"leaves": Color(0, 100, 0),
			"sponge": Color(200, 200, 0),
			"glass": Color(200, 200, 255, 128),
			"red_wool": Color(255, 0, 0),
			"orange_wool": Color(255, 165, 0),
			"yellow_wool": Color(255, 255, 0),
			"lime_wool": Color(0, 255, 0),
			"green_wool": Color(0, 128, 0),
			"cyan_wool": Color(0, 255, 255),
			"blue_wool": Color(0, 0, 255),
			"purple_wool": Color(128, 0, 128),
			"magenta_wool": Color(255, 0, 255),
			"pink_wool": Color(255, 192, 203),
			"brown_wool": Color(165, 42, 42),
			"white_wool": Color(255, 255, 255),
			"black_wool": Color(0, 0, 0),
			"air": Color(0, 0, 0, 0),  # 透明
		}

	@staticmethod
	def _nearest_color(target: Color, colors: dict[str, Color]) -> str:
		"""找到最接近的颜色对应的方块"""
		min_distance = float("inf")
		nearest_block = "air"
		for block_name, color in colors.items():
			# 跳过透明方块
			if block_name == "air":
				continue
			distance = math.sqrt((target.r - color.r) ** 2 + (target.g - color.g) ** 2 + (target.b - color.b) ** 2)
			if distance < min_distance:
				min_distance = distance
				nearest_block = block_name
		return nearest_block

	@staticmethod
	def _axis_permute(x: int, y: int, z: int, size: tuple[int, int, int], axis: str) -> tuple[int, int, int]:
		"""轴排列转换"""
		coords = [x, y, z]
		size_coords = list(size)
		result = []
		for char in axis:
			if char in "xyz":
				idx = "xyz".index(char)
				result.append(coords[idx])
			elif char in "XYZ":
				idx = "xyz".index(char.lower())
				result.append(size_coords[idx] - coords[idx] - 1)
			else:
				msg = f"无效的轴字符: {char}"
				raise ValueError(msg)
		return tuple(result)

	def vox2blocks(self, vox_file: str, scale: float = 0.25, axis: str = "xzy") -> dict[str, int]:
		"""Vox模型转方块建筑"""
		try:
			print(f"正在读取 VOX 文件: {vox_file}")
			vox_model = VoxReader.read_vox(vox_file)
			print(f"模型尺寸: {vox_model.size_x} x {vox_model.size_y} x {vox_model.size_z}")
			print(f"体素数量: {len(vox_model.voxels)}")
			# 计算缩放后的尺寸
			scaled_size = (int(vox_model.size_x * scale) + 1, int(vox_model.size_y * scale) + 1, int(vox_model.size_z * scale) + 1)
			print(f"缩放后尺寸: {scaled_size[0]} x {scaled_size[1]} x {scaled_size[2]}")
			blocks: dict[str, int] = {}
			block_count: dict[str, int] = {}
			# 转换每个体素
			for i, voxel in enumerate(vox_model.voxels):
				# 应用缩放
				x = int(voxel.x * scale)
				y = int(voxel.y * scale)
				z = int(voxel.z * scale)
				# 轴排列
				x, y, z = self._axis_permute(x, y, z, scaled_size, axis)
				# 获取颜色并找到最接近的方块
				color = vox_model.palette[voxel.color_index - 1]  # 颜色索引从1开始
				block_name = self._nearest_color(color, self.color_blocks)
				block_id = self.blocks_data["name2id"].get(block_name, 0)  # 默认为空气
				# 存储方块
				pos_key = f"{x},{y},{z}"
				blocks[pos_key] = block_id
				block_count[block_name] = block_count.get(block_name, 0) + 1
				# 显示进度
				if (i + 1) % 1000 == 0 or (i + 1) == len(vox_model.voxels):
					print(f"进度: {i + 1}/{len(vox_model.voxels)} 体素")
			print("\n方块统计:")
			for block_name, count in sorted(block_count.items(), key=operator.itemgetter(1), reverse=True):
				print(f"  {block_name}: {count}")
		except Exception as e:
			error_msg = f"Vox 转方块转换失败: {e!s}"
			raise Exception(error_msg) from e  # noqa: TRY002
		else:
			return blocks

	def blocks2vox(self, blocks_data: dict[str, int], axis: str = "xzy", custom_colors: dict[str, Color] | None = None) -> VoxModel:
		"""方块建筑转Vox模型"""
		try:
			print("正在处理方块数据...")
			# 合并自定义颜色
			color_map = self.color_blocks.copy()
			if custom_colors is not None:
				color_map.update(custom_colors)
			# 计算模型尺寸
			max_x = max_y = max_z = 0
			positions = []
			for pos_key in blocks_data:
				x, y, z = map(int, pos_key.split(","))
				positions.append((x, y, z))
				max_x = max(max_x, x)
				max_y = max(max_y, y)
				max_z = max(max_z, z)
			size = (max_x + 1, max_y + 1, max_z + 1)
			print(f"模型尺寸: {size[0]} x {size[1]} x {size[2]}")
			print(f"方块数量: {len(blocks_data)}")
			# 创建调色板
			palette = [Color(0, 0, 0, 0)]  # 索引0为透明
			block_to_color_index: dict[int, int] = {}
			# 为每个方块类型分配颜色索引
			unique_blocks = set(blocks_data.values())
			print(f"唯一方块类型: {len(unique_blocks)}")
			for block_id in unique_blocks:
				block_name = self.blocks_data["id2name"].get(str(block_id), "air")
				color = color_map.get(block_name, Color(0, 0, 0, 0))
				# 查找或添加颜色到调色板
				color_index = None
				for i, pal_color in enumerate(palette):
					if (pal_color.r, pal_color.g, pal_color.b, pal_color.a) == (color.r, color.g, color.b, color.a):
						color_index = i
						break
				if color_index is None:
					if len(palette) < self.MAX_PALETTE_SIZE:
						color_index = len(palette)
						palette.append(color)
					else:
						# 调色板已满,使用最接近的颜色
						color_index = 1  # 默认使用索引1
				block_to_color_index[block_id] = color_index
			# 填充调色板到256色
			while len(palette) < self.MAX_PALETTE_SIZE:
				palette.append(Color(0, 0, 0, 0))
			print(f"调色板颜色数量: {len([c for c in palette if c.a > 0])}")
			# 创建体素数据
			voxels = []
			for i, (x, y, z) in enumerate(positions):
				block_id = blocks_data[f"{x},{y},{z}"]
				color_index = block_to_color_index.get(block_id, 0)
				if color_index > 0:  # 只添加非透明体素
					# 反向轴排列
					orig_x, orig_y, orig_z = self._axis_permute(x, y, z, size, self._reverse_axis(axis))
					voxels.append(Voxel(orig_x, orig_y, orig_z, color_index))
				# 显示进度
				if (i + 1) % 1000 == 0 or (i + 1) == len(positions):
					print(f"进度: {i + 1}/{len(positions)} 方块")
			print(f"有效体素数量: {len(voxels)}")
			return VoxModel(size[0], size[1], size[2], voxels, palette)
		except Exception as e:
			error_msg = f"方块转 Vox 转换失败: {e!s}"
			raise Exception(error_msg) from e  # noqa: TRY002

	@staticmethod
	def _reverse_axis(axis: str) -> str:
		"""反转轴排列顺序"""
		reverse_map = {"x": "X", "X": "x", "y": "Y", "Y": "y", "z": "Z", "Z": "z"}
		return "".join(reverse_map.get(c, c) for c in axis)


def save_blocks_data(blocks: dict[str, int], output_file: str) -> None:
	"""保存方块数据到文件"""
	with Path(output_file).open("w", encoding="utf-8") as f:
		json.dump(blocks, f, indent=2)
	print(f"方块数据已保存到: {output_file}")


def load_blocks_data(input_file: str) -> dict[str, int]:
	"""从文件加载方块数据"""
	with Path(input_file).open(encoding="utf-8") as f:
		data = json.load(f)
	print(f"已加载方块数据: {len(data)} 个方块")
	return data


def get_file_path(prompt: str, extension: str = "") -> str:
	"""获取文件路径,支持相对路径和绝对路径"""
	while True:
		path = input(prompt).strip()
		if not path:
			print("路径不能为空,请重新输入")
			continue
		# 如果指定了扩展名,检查文件扩展名
		if extension and not path.lower().endswith(extension.lower()):
			path += extension
		if Path(path).exists():
			return path
		print(f"文件不存在: {path}")
		retry = input("是否重新输入? (y/n): ").lower()
		if retry != "y":
			return path


def get_float_input(prompt: str, default: float = 0.25) -> float:
	"""获取浮点数输入"""
	while True:
		try:
			value = input(f"{prompt} (默认: {default}): ").strip()
			if not value:
				return default
			return float(value)
		except ValueError:
			print("请输入有效的数字")


def get_axis_input(prompt: str, default: str = "xzy") -> str:
	"""获取轴排列输入"""
	AXIS_LENGTH = 3  # noqa: N806
	while True:
		value = input(f"{prompt} (默认: {default}): ").strip()
		if not value:
			return default
		if len(value) != AXIS_LENGTH:
			print("轴排列必须是3个字符")
			continue
		valid_chars = set("xyzXYZ")
		if all(c in valid_chars for c in value):
			return value
		print("轴排列只能包含 x, y, z 字符 (大小写均可)")


def show_menu() -> None:
	"""显示主菜单"""
	print("\n" + "=" * 50)
	print("          Box3 Voxel 转换工具")
	print("=" * 50)
	print("1. Vox 模型转方块建筑")
	print("2. 方块建筑转 Vox 模型")
	print("3. 查看方块颜色映射")
	print("4. 退出")
	print("=" * 50)


def show_color_mapping(converter: Box3Converter) -> None:
	"""显示颜色映射"""
	print("\n方块颜色映射:")
	print("-" * 40)
	for block_name, color in converter.color_blocks.items():
		if block_name != "air":  # 跳过空气方块
			print(f"{block_name:15} -> RGB({color.r:3}, {color.g:3}, {color.b:3})")


def vox_to_blocks_interactive(converter: Box3Converter) -> None:
	"""交互式 Vox 转方块转换"""
	print("\n[Vox 转方块建筑]")
	# 获取输入文件
	vox_file = get_file_path("请输入 VOX 文件路径: ", ".vox")
	# 获取参数
	scale = get_float_input("请输入缩放比例", 0.25)
	axis = get_axis_input("请输入轴排列", "xzy")
	# 获取输出文件
	output_file = input("请输入输出 JSON 文件路径 (默认: output.json): ").strip()
	if not output_file:
		output_file = "output.json"
	if not output_file.endswith(".json"):
		output_file += ".json"
	try:
		# 执行转换
		blocks = converter.vox2blocks(vox_file, scale, axis)
		# 保存结果
		save_blocks_data(blocks, output_file)
		print("\n✅ 转换完成!")
		print(f"   输入: {vox_file}")
		print(f"   输出: {output_file}")
		print(f"   生成方块: {len(blocks)} 个")
	except Exception as e:
		print(f"\n❌ 转换失败: {e!s}")


def blocks_to_vox_interactive(converter: Box3Converter) -> None:
	"""交互式方块转 Vox 转换"""
	print("\n[方块建筑转 Vox 模型]")
	# 获取输入文件
	json_file = get_file_path("请输入 JSON 文件路径: ", ".json")
	# 获取参数
	axis = get_axis_input("请输入轴排列", "xzy")
	# 获取输出文件
	output_file = input("请输入输出 VOX 文件路径 (默认: output.vox): ").strip()
	if not output_file:
		output_file = "output.vox"
	if not output_file.endswith(".vox"):
		output_file += ".vox"
	try:
		# 加载方块数据
		blocks_data = load_blocks_data(json_file)
		# 执行转换
		vox_model = converter.blocks2vox(blocks_data, axis)
		# 保存结果
		VoxWriter.write_vox(vox_model, output_file)
		print("\n✅ 转换完成!")
		print(f"   输入: {json_file}")
		print(f"   输出: {output_file}")
		print(f"   生成体素: {len(vox_model.voxels)} 个")
	except Exception as e:
		print(f"\n❌ 转换失败: {e!s}")


def main() -> None:
	"""主函数 - 交互式界面"""
	print("正在初始化 Box3 转换器...")
	try:
		converter = Box3Converter()
		print("✅ 转换器初始化完成")
		while True:
			show_menu()
			choice = input("请选择操作 (1-4): ").strip()
			if choice == "1":
				vox_to_blocks_interactive(converter)
			elif choice == "2":
				blocks_to_vox_interactive(converter)
			elif choice == "3":
				show_color_mapping(converter)
			elif choice == "4":
				print("感谢使用 Box3 Voxel 转换工具!")
				break
			else:
				print("无效选择,请重新输入")
			input("\n按回车键继续...")
	except Exception as e:
		print(f"初始化失败: {e!s}")
		input("按回车键退出...")


if __name__ == "__main__":
	main()
