import importlib
import json
import sys
import traceback
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any

"""
插件开发规范:
1. 每个插件必须是一个独立的Python模块(.py文件或包)
2. 每个插件必须包含一个名为 'Plugin' 的类
3. Plugin类必须实现以下内容:
    - 类属性:
        PLUGIN_NAME: 插件名称(字符串)
        PLUGIN_DESCRIPTION: 插件描述(字符串)
        PLUGIN_VERSION: 插件版本(字符串)
        PLUGIN_CONFIG_SCHEMA: 插件配置模式(字典), 定义配置结构
        PLUGIN_DEFAULT_CONFIG: 插件默认配置(字典)
    - 方法:
        register() -> dict: 返回要暴露的方法字典
            格式: {"方法名": (方法对象, "方法描述")}
        on_load(config: dict): 插件加载时调用, 传入当前配置
        on_unload(): 插件卸载时调用
4. 插件可以放置在任意目录, 但需要被插件管理器扫描到
"""


# ======================
# 插件接口抽象类
# ======================
class BasePlugin(ABC):
	@property
	@abstractmethod
	def PLUGIN_NAME(self) -> str:  # noqa: N802
		pass

	@property
	@abstractmethod
	def PLUGIN_DESCRIPTION(self) -> str:  # noqa: N802
		pass

	@property
	@abstractmethod
	def PLUGIN_VERSION(self) -> str:  # noqa: N802
		pass

	@property
	@abstractmethod
	def PLUGIN_CONFIG_SCHEMA(self) -> dict[str, Any]:  # noqa: N802
		"""配置模式, 定义配置项的类型和默认值"""

	@property
	@abstractmethod
	def PLUGIN_DEFAULT_CONFIG(self) -> dict[str, Any]:  # noqa: N802
		"""默认配置值"""

	@abstractmethod
	def register(self) -> dict[str, tuple[Callable, str]]:
		"""返回要暴露的方法字典"""

	def on_load(self, _config: dict[str, Any]) -> None:
		"""插件加载时的回调, 传入当前配置"""
		print(f"[系统] 插件 {self.PLUGIN_NAME} v{self.PLUGIN_VERSION} 已加载")

	def on_unload(self) -> None:
		"""插件卸载时的回调"""
		print(f"[系统] 插件 {self.PLUGIN_NAME} 已卸载")


class LazyPluginManager:
	def __init__(self, plugin_dir: Path, config_dir: Path) -> None:
		self.plugin_dir = plugin_dir
		self.config_dir = config_dir
		self.plugin_info: dict[str, dict] = {}  # 插件元信息 {plugin_name: {meta}}
		self.loaded_plugins: dict[str, BasePlugin] = {}  # 已加载的插件 {plugin_name: plugin_instance}
		self.command_map: dict[str, tuple[str, str]] = {}  # 命令映射 {command_name: (plugin_name, method_name)}
		self.plugin_modules: dict[str, Any] = {}  # 已加载的模块 {plugin_name: module}
		# 确保配置目录存在
		Path.mkdir(config_dir, exist_ok=True)
		# 扫描插件
		self.scan_plugins()

	def scan_plugins(self) -> None:
		"""扫描插件目录, 收集插件元信息"""
		sys.path.insert(0, str(self.plugin_dir))  # 转换Path为字符串
		self.plugin_info = {}
		for filename in Path.iterdir(self.plugin_dir):
			# 使用suffix检查文件后缀, 更准确的Path用法
			if filename.suffix == ".py" and filename.name != "__init__.py":
				module_name = filename.stem  # 使用stem获取不带后缀的文件名
				plugin_name = module_name
				# 只收集元信息, 不加载模块
				self.plugin_info[plugin_name] = {"module_name": module_name, "status": "scanned", "commands": {}}

	def get_plugin_list(self) -> dict[str, dict]:
		"""获取插件列表(不加载插件)"""
		result: dict[str, dict] = {}
		for name, info in self.plugin_info.items():
			# 如果插件已加载过, 则包含更多信息
			if name in self.loaded_plugins:
				plugin = self.loaded_plugins[name]
				result[name] = {
					"name": plugin.PLUGIN_NAME,
					"description": plugin.PLUGIN_DESCRIPTION,
					"version": plugin.PLUGIN_VERSION,
					"status": "loaded",
					"commands": list(info["commands"].keys()),
				}
			else:
				result[name] = {"name": name, "status": "unloaded", "description": "未加载, 无法获取详细信息"}
		return result

	def search_plugins(self, keyword: str) -> dict[str, dict]:
		"""搜索插件"""
		plugins = self.get_plugin_list()
		# 简单搜索:名称或描述中包含关键词
		return {name: info for name, info in plugins.items() if keyword.lower() in name.lower() or (info["status"] == "loaded" and keyword.lower() in info["description"].lower())}

	def load_plugin(self, plugin_name: str) -> bool:  # noqa: PLR0911
		"""按需加载插件"""
		if plugin_name in self.loaded_plugins:
			return True  # 已加载
		if plugin_name not in self.plugin_info:
			print(f"[错误] 插件 {plugin_name} 未找到")
			return False
		try:
			# 动态导入模块
			module = importlib.import_module(self.plugin_info[plugin_name]["module_name"])
			self.plugin_modules[plugin_name] = module
			# 获取插件类
			if not hasattr(module, "Plugin"):
				print(f"[错误] 插件 {plugin_name} 缺少 Plugin 类")
				return False
			plugin_class = module.Plugin
			plugin_instance = plugin_class()
			# 验证必要属性
			required_attrs = ["PLUGIN_NAME", "PLUGIN_DESCRIPTION", "PLUGIN_VERSION", "PLUGIN_CONFIG_SCHEMA", "PLUGIN_DEFAULT_CONFIG"]
			for attr in required_attrs:
				if not hasattr(plugin_class, attr):
					print(f"[错误] 插件 {plugin_name} 缺少必要属性 {attr}")
					return False
			# 加载配置
			config = self.load_config(plugin_name)
			# 调用插件加载回调
			plugin_instance.on_load(config)
			# 注册暴露的方法
			exposed_methods = plugin_instance.register()
			if not isinstance(exposed_methods, dict):
				print(f"[错误] 插件 {plugin_name} 的 register() 必须返回字典")
				return False
			# 保存命令映射
			for method_name, (method, description) in exposed_methods.items():
				if not callable(method):
					print(f"[错误] 插件 {plugin_name} 的方法 {method_name} 不可调用")
					continue
				self.command_map[method_name] = (plugin_name, method_name)
				self.plugin_info[plugin_name]["commands"][method_name] = {"description": description, "method": method}
			# 保存插件实例
			self.loaded_plugins[plugin_name] = plugin_instance
			self.plugin_info[plugin_name]["status"] = "loaded"
		except Exception as e:  # 替换bare except
			print(f"[错误] 加载插件 {plugin_name} 失败: {e!s}")
			traceback.print_exc()
			return False
		else:
			return True  # 将成功返回移到else块

	def unload_plugin(self, plugin_name: str) -> bool:
		"""卸载插件, 释放内存"""
		if plugin_name not in self.loaded_plugins:
			return False
		plugin_instance = self.loaded_plugins[plugin_name]
		# 调用插件卸载回调
		if callable(getattr(plugin_instance, "on_unload", None)):
			plugin_instance.on_unload()
		# 移除命令映射
		for cmd in list(self.command_map.keys()):
			if self.command_map[cmd][0] == plugin_name:
				del self.command_map[cmd]
		# 移除插件信息
		del self.loaded_plugins[plugin_name]
		del self.plugin_modules[plugin_name]
		self.plugin_info[plugin_name]["status"] = "unloaded"
		self.plugin_info[plugin_name]["commands"] = {}
		# 清理模块引用
		if self.plugin_info[plugin_name]["module_name"] in sys.modules:
			del sys.modules[self.plugin_info[plugin_name]["module_name"]]
		return True

	def get_plugin_commands(self, plugin_name: str) -> dict[str, dict]:
		"""获取插件的命令列表"""
		if plugin_name not in self.plugin_info:
			return {}
		# 如果插件未加载, 先加载
		if self.plugin_info[plugin_name]["status"] != "loaded":
			self.load_plugin(plugin_name)
		return self.plugin_info[plugin_name]["commands"]

	def execute_command(self, command_name: str, *args: ..., **kwargs: ...) -> ...:
		"""执行插件命令"""
		if command_name not in self.command_map:
			# 尝试在未加载的插件中查找
			for plugin_name, info in self.plugin_info.items():
				if command_name in info.get("commands", {}):
					self.load_plugin(plugin_name)
					break
			if command_name not in self.command_map:
				print(f"[错误] 命令 '{command_name}' 不存在")
				return None
		plugin_name, method_name = self.command_map[command_name]
		# 确保插件已加载
		if plugin_name not in self.loaded_plugins:
			self.load_plugin(plugin_name)
		# 获取方法并执行
		method = self.plugin_info[plugin_name]["commands"][method_name]["method"]
		return method(*args, **kwargs)

	def load_config(self, plugin_name: str) -> dict[str, Any]:
		"""加载插件配置"""
		config_path = self.config_dir / f"{plugin_name}.json"  # 使用Path的/运算符
		default_config: dict[str, Any] = {}
		# 获取默认配置(需要先加载插件)
		if plugin_name in self.loaded_plugins:
			default_config = self.loaded_plugins[plugin_name].PLUGIN_DEFAULT_CONFIG
		# 如果配置文件存在, 加载它
		if config_path.exists():  # 使用Path的exists方法
			try:
				with config_path.open("r", encoding="utf-8") as f:  # 使用Path.open并指定编码
					saved_config = json.load(f)
				# 合并默认配置和保存的配置

			except Exception as e:
				print(f"[警告] 加载插件 {plugin_name} 配置失败: {e!s}")
				return default_config
			else:
				return {**default_config, **saved_config}
		return default_config

	def save_config(self, plugin_name: str, config: dict[str, Any]) -> bool:
		"""保存插件配置"""
		if plugin_name not in self.plugin_info:
			return False
		config_path = self.config_dir / f"{plugin_name}.json"  # 使用Path的/运算符
		try:
			with config_path.open("w", encoding="utf-8") as f:  # 使用Path.open并指定编码
				json.dump(config, f, indent=2, ensure_ascii=False)
		except Exception as e:
			print(f"[错误] 保存插件 {plugin_name} 配置失败: {e!s}")
			return False
		else:
			return True  # 将成功返回移到else块

	def get_config(self, plugin_name: str) -> dict[str, Any] | None:
		"""获取当前插件配置"""
		if plugin_name not in self.plugin_info:
			return None
		# 确保插件已加载
		if plugin_name not in self.loaded_plugins:
			self.load_plugin(plugin_name)
		return self.load_config(plugin_name)

	def update_config(self, plugin_name: str, new_config: dict[str, Any]) -> bool:
		"""更新插件配置并保存"""
		if plugin_name not in self.plugin_info:
			return False
		# 确保插件已加载
		if plugin_name not in self.loaded_plugins:
			self.load_plugin(plugin_name)
		# 验证配置结构
		plugin = self.loaded_plugins[plugin_name]
		config_schema = plugin.PLUGIN_CONFIG_SCHEMA
		# 简单的配置验证
		for key, expected_type in config_schema.items():
			if key in new_config and not isinstance(new_config[key], expected_type):  # 使用in代替in.keys()
				print(f"[警告] 配置项 '{key}' 类型错误, 应为 {expected_type.__name__}")
				# 尝试转换类型
				try:
					new_config[key] = expected_type(new_config[key])
				except Exception:
					print(f"[错误] 无法转换配置项 '{key}' 到 {expected_type.__name__}")
					return False
		# 保存配置
		return self.save_config(plugin_name, new_config)


# ======================
# 控制台交互界面 (简化版)
# ======================
class PluginConsole:
	def __init__(self, plugin_manager: LazyPluginManager) -> None:
		self.manager = plugin_manager
		self.running = True

	@staticmethod  # 改为静态方法, 因为未使用self
	def display_main_menu() -> None:
		"""显示主菜单"""
		print("\n===== 插件管理系统 =====")
		print("1. 搜索插件")
		print("2. 使用插件")
		print("3. 查看插件配置")
		print("4. 更新插件配置")
		print("0. 退出系统")

	def run(self) -> None:
		"""运行控制台交互"""
		while self.running:
			self.display_main_menu()
			choice = input("请选择操作: ")
			if choice == "1":
				self.search_plugins()
			elif choice == "2":
				self.use_plugin()
			elif choice == "3":
				self.view_config()
			elif choice == "4":
				self.update_config()
			elif choice == "0":
				self.running = False
			else:
				print("无效选择, 请重新输入")

	def search_plugins(self) -> None:
		"""搜索插件"""
		keyword = input("输入搜索关键词: ").strip()
		results = self.manager.search_plugins(keyword)
		if not results:
			print("未找到匹配的插件")
			return
		print("\n搜索结果:")
		for name, info in results.items():
			status = "已加载" if info["status"] == "loaded" else "未加载"
			print(f"- {name} ({status})")
			print(f"  描述: {info['description']}")
			if "version" in info:
				print(f"  版本: {info['version']}")
			if info.get("commands"):
				print(f"  命令: {', '.join(info['commands'])}")

	def use_plugin(self) -> None:
		"""使用插件功能"""
		# 显示所有插件
		plugins = self.manager.get_plugin_list()
		print("\n可用插件:")
		for idx, (name, _) in enumerate(plugins.items(), 1):  # 未使用的变量用_代替
			status = "已加载" if plugins[name]["status"] == "loaded" else "未加载"
			print(f"{idx}. {name} ({status})")
		try:
			choice = int(input("请选择插件编号: "))
			plugin_names = list(plugins.keys())
			if 1 <= choice <= len(plugin_names):
				plugin_name = plugin_names[choice - 1]
				self.use_plugin_commands(plugin_name)
			else:
				print("无效选择")
		except ValueError:
			print("请输入有效数字")

	def use_plugin_commands(self, plugin_name: str) -> None:
		"""使用插件的命令"""
		# 确保插件已加载
		if not self.manager.load_plugin(plugin_name):
			print(f"无法加载插件 {plugin_name}")
			return
		# 获取插件命令
		commands = self.manager.get_plugin_commands(plugin_name)
		if not commands:
			print(f"插件 {plugin_name} 没有可用命令")
			return
		print(f"\n{plugin_name} 的命令列表:")
		for idx, (cmd, info) in enumerate(commands.items(), 1):
			print(f"{idx}. {cmd} - {info['description']}")
		try:
			choice = int(input("请选择命令编号: "))
			command_names = list(commands.keys())
			if 1 <= choice <= len(command_names):
				command_name = command_names[choice - 1]
				self.execute_command(plugin_name, command_name)
			else:
				print("无效选择")
		except ValueError:
			print("请输入有效数字")

	def execute_command(self, _plugin_name: str, command_name: str) -> None:  # 未使用参数重命名为_plugins_name
		"""执行插件命令"""
		# 获取参数
		args_input = input("输入参数 (空格分隔): ").strip()
		args = args_input.split() if args_input else []
		# 执行命令
		try:
			result = self.manager.execute_command(command_name, *args)
			print(f"执行结果: {result}")
		except Exception as e:
			print(f"执行命令失败: {e!s}")

	def view_config(self) -> None:
		"""查看插件配置"""
		plugins = self.manager.get_plugin_list()
		print("\n插件列表:")
		for idx, (name, _) in enumerate(plugins.items(), 1):  # 未使用的变量用_代替
			print(f"{idx}. {name}")
		try:
			choice = int(input("请选择插件查看配置: "))
			plugin_names = list(plugins.keys())
			if 1 <= choice <= len(plugin_names):
				plugin_name = plugin_names[choice - 1]
				# 确保插件已加载
				if not self.manager.load_plugin(plugin_name):
					print(f"无法加载插件 {plugin_name}")
					return
				config = self.manager.get_config(plugin_name)
				if config is None:
					print("无可用配置")
					return
				print(f"\n{plugin_name} 的配置:")
				for key, value in config.items():
					print(f"- {key}: {value}")
			else:
				print("无效选择")
		except ValueError:
			print("请输入有效数字")

	def update_config(self) -> None:  # noqa: PLR0912
		"""更新插件配置"""
		plugins = self.manager.get_plugin_list()
		print("\n插件列表:")
		for idx, (name, _) in enumerate(plugins.items(), 1):  # 未使用的变量用_代替
			print(f"{idx}. {name}")
		try:
			choice = int(input("请选择插件更新配置: "))
			plugin_names = list(plugins.keys())
			if 1 <= choice <= len(plugin_names):
				plugin_name = plugin_names[choice - 1]
				# 确保插件已加载
				if not self.manager.load_plugin(plugin_name):
					print(f"无法加载插件 {plugin_name}")
					return
				# 获取当前配置
				current_config = self.manager.get_config(plugin_name)
				if current_config is None:
					print("无可用配置")
					return
				print("\n当前配置:")
				for key, value in current_config.items():
					print(f"- {key}: {value}")
				# 获取新配置
				new_config: dict[str, Any] = {}
				print("\n输入新配置 (输入空行结束):")
				for key in current_config:
					new_value = input(f"{key} ({type(current_config[key]).__name__}): ").strip()
					if new_value:
						# 尝试转换类型
						try:
							# 根据当前值的类型转换
							if isinstance(current_config[key], int):
								new_config[key] = int(new_value)
							elif isinstance(current_config[key], float):
								new_config[key] = float(new_value)
							elif isinstance(current_config[key], bool):
								# 使用集合字面量代替列表
								new_config[key] = new_value.lower() in {"true", "1", "yes"}
							else:
								new_config[key] = new_value
						except ValueError:
							print(f"无法转换 {key} 的值, 使用字符串")
							new_config[key] = new_value
				# 更新配置
				if new_config:
					if self.manager.update_config(plugin_name, new_config):
						print("配置更新成功")
					else:
						print("配置更新失败")
				else:
					print("未提供新配置")
			else:
				print("无效选择")
		except ValueError:
			print("请输入有效数字")
