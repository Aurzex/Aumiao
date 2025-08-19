import importlib
import sys
import traceback
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from src.utils import data, tool

printer = tool.Printer()
T = TypeVar("T")

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
	def __init__(self, plugin_dir: Path) -> None:
		self.plugin_dir = plugin_dir
		# 不再需要 config_dir, 但保留参数以保持接口兼容
		self.plugin_info: dict[str, dict] = {}  # 插件元信息 {plugin_name: {meta}}
		self.loaded_plugins: dict[str, BasePlugin] = {}  # 已加载的插件 {plugin_name: plugin_instance}
		self.command_map: dict[str, tuple[str, str]] = {}  # 命令映射 {command_name: (plugin_name, method_name)}
		self.plugin_modules: dict[str, Any] = {}  # 已加载的模块 {plugin_name: module}
		# 扫描插件
		self.scan_plugins()

	def scan_plugins(self) -> None:
		"""扫描插件目录, 收集插件元信息"""
		sys.path.insert(0, str(self.plugin_dir))
		self.plugin_info = {}
		# 使用列表推导式提高效率
		plugin_files = [f for f in self.plugin_dir.iterdir() if f.suffix == ".py" and f.name != "__init__.py"]
		for file_path in plugin_files:
			module_name = file_path.stem
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
		keyword_lower = keyword.lower()
		# 使用生成器表达式提高效率
		return {
			name: info for name, info in plugins.items() if keyword_lower in name.lower() or (info["status"] == "loaded" and keyword_lower in info.get("description", "").lower())
		}

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
			# 更新全局配置
			self._update_global_config(plugin_name, config)
		except Exception as e:
			print(f"[错误] 加载插件 {plugin_name} 失败: {e!s}")
			traceback.print_exc()
			return False
		else:
			return True

	@staticmethod
	def _update_global_config(plugin_name: str, config: dict[str, Any]) -> None:
		"""更新全局配置"""
		try:
			# 使用插件名作为键, 配置作为值
			plugin_config = {plugin_name: config}
			data.SettingManager().data.PLUGIN.update(plugin_config)
			data.SettingManager().save()
			print(f"[系统] 已更新全局配置中的 {plugin_name} 插件配置")
		except Exception as e:
			print(f"[警告] 更新全局配置失败: {e!s}")

	def unload_plugin(self, plugin_name: str) -> bool:
		"""卸载插件, 释放内存"""
		if plugin_name not in self.loaded_plugins:
			return False
		plugin_instance = self.loaded_plugins[plugin_name]
		# 调用插件卸载回调
		if callable(getattr(plugin_instance, "on_unload", None)):
			plugin_instance.on_unload()
		# 移除命令映射
		commands_to_remove = [cmd for cmd, (p_name, _) in self.command_map.items() if p_name == plugin_name]
		for cmd in commands_to_remove:
			del self.command_map[cmd]
		# 移除插件信息
		del self.loaded_plugins[plugin_name]
		del self.plugin_modules[plugin_name]
		self.plugin_info[plugin_name]["status"] = "unloaded"
		self.plugin_info[plugin_name]["commands"] = {}
		# 清理模块引用
		module_name = self.plugin_info[plugin_name]["module_name"]
		if module_name in sys.modules:
			del sys.modules[module_name]
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
		"""从全局配置管理器加载插件配置"""
		default_config: dict[str, Any] = {}
		# 获取默认配置(需要先加载插件)
		if plugin_name in self.loaded_plugins:
			default_config = self.loaded_plugins[plugin_name].PLUGIN_DEFAULT_CONFIG
		try:
			# 从全局配置中获取插件配置
			global_config = data.SettingManager().data
			if hasattr(global_config, "PLUGIN") and plugin_name in global_config.PLUGIN:
				saved_config = global_config.PLUGIN[plugin_name]
				# 合并默认配置和保存的配置
				return {**default_config, **saved_config}
		except Exception as e:
			print(f"[警告] 从全局配置加载插件 {plugin_name} 配置失败: {e!s}")
			return default_config
		else:
			return default_config

	def save_config(self, plugin_name: str, config: dict[str, Any]) -> bool:
		"""保存插件配置到全局配置管理器"""
		if plugin_name not in self.plugin_info:
			return False
		try:
			# 直接更新全局配置
			plugin_config = {plugin_name: config}
			data.SettingManager().data.PLUGIN.update(plugin_config)
			data.SettingManager().save()
			print(f"[系统] 已保存 {plugin_name} 的配置到全局配置")
		except Exception as e:
			print(f"[错误] 保存插件 {plugin_name} 配置失败: {e!s}")
			return False
		else:
			return True

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
			if key in new_config and not isinstance(new_config[key], expected_type):
				print(f"[警告] 配置项 '{key}' 类型错误, 应为 {expected_type.__name__}")
				# 尝试转换类型
				try:
					new_config[key] = expected_type(new_config[key])
				except Exception:
					print(f"[错误] 无法转换配置项 '{key}' 到 {expected_type.__name__}")
					return False
		# 保存配置
		return self.save_config(plugin_name, new_config)


class PluginConsole:
	def __init__(self, plugin_manager: LazyPluginManager) -> None:
		self.manager = plugin_manager
		self.running = True

	@staticmethod
	def display_main_menu() -> None:
		"""显示主菜单"""
		menu_options = {"1": ("搜索插件", True), "2": ("使用插件", True), "3": ("查看配置", True), "4": ("更新配置", True), "0": ("退出系统", True)}
		for key, (name, visible) in menu_options.items():
			if not visible:
				continue
			print(printer.color_text(f"{key.rjust(2)}. {name}", "MENU_ITEM"))

	def run(self) -> None:
		"""运行控制台交互"""
		while self.running:
			self.display_main_menu()
			choice = printer.prompt_input("请选择操作")
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
				printer.prompt_input("无效选择, 请按回车键重新输入", "ERROR")

	def search_plugins(self) -> None:
		"""搜索插件"""
		keyword = printer.prompt_input("输入搜索关键词")
		results = self.manager.search_plugins(keyword)
		if not results:
			printer.prompt_input("未找到匹配的插件, 按回车键返回", "COMMENT")
			return
		printer.print_header("搜索结果")
		for name, info in results.items():
			status = "已加载" if info["status"] == "loaded" else "未加载"
			status_color = "SUCCESS" if info["status"] == "loaded" else "COMMENT"
			status_text = printer.color_text(f"({status})", status_color)
			print(f"- {name} {status_text}")
			print(f"  描述: {info['description']}")
			if "version" in info:
				print(f"  版本: {info['version']}")
			if info.get("commands"):
				commands_text = printer.color_text(", ".join(info["commands"]), "MENU_ITEM")
				print(f"  命令: {commands_text}")
		printer.prompt_input("按回车键返回", "COMMENT")

	def use_plugin(self) -> None:
		"""使用插件功能"""
		# 显示所有插件
		plugins = self.manager.get_plugin_list()
		printer.print_header("可用插件")
		plugin_names = list(plugins.keys())
		for idx, name in enumerate(plugin_names, 1):
			status = "已加载" if plugins[name]["status"] == "loaded" else "未加载"
			status_color = "SUCCESS" if plugins[name]["status"] == "loaded" else "COMMENT"
			status_text = printer.color_text(f"({status})", status_color)
			print(f"{idx:2d}. {name} {status_text}")
		choice = printer.get_valid_input("请选择插件编号", valid_options=range(1, len(plugin_names) + 1), cast_type=int)
		plugin_name = plugin_names[choice - 1]
		self.use_plugin_commands(plugin_name)

	def use_plugin_commands(self, plugin_name: str) -> None:
		"""使用插件的命令"""
		# 确保插件已加载
		if not self.manager.load_plugin(plugin_name):
			printer.prompt_input(f"无法加载插件 {plugin_name}, 按回车键返回", "ERROR")
			return
		# 获取插件命令
		commands = self.manager.get_plugin_commands(plugin_name)
		if not commands:
			printer.prompt_input(f"插件 {plugin_name} 没有可用命令, 按回车键返回", "COMMENT")
			return
		printer.print_header(f"{plugin_name} 的命令列表")
		command_names = list(commands.keys())
		for idx, cmd in enumerate(command_names, 1):
			info = commands[cmd]
			print(f"{idx:2d}. {printer.color_text(cmd, 'MENU_ITEM')} - {info['description']}")
		choice = printer.get_valid_input("请选择命令编号", valid_options=range(1, len(command_names) + 1), cast_type=int)
		command_name = command_names[choice - 1]
		self.execute_command(plugin_name, command_name)

	def execute_command(self, _plugin_name: str, command_name: str) -> None:
		"""执行插件命令"""
		# 获取参数
		args_input = printer.prompt_input("输入参数 (空格分隔)")
		args = args_input.split() if args_input else []
		# 执行命令
		try:
			result = self.manager.execute_command(command_name, *args)
			printer.print_header("执行结果")
			print(result)
			printer.prompt_input("按回车键返回", "COMMENT")
		except Exception as e:
			printer.prompt_input(f"执行命令失败: {e!s}, 按回车键返回", "ERROR")

	def view_config(self) -> None:
		"""查看插件配置"""
		plugins = self.manager.get_plugin_list()
		printer.print_header("插件列表")
		plugin_names = list(plugins.keys())
		for idx, name in enumerate(plugin_names, 1):
			print(f"{idx:2d}. {name}")
		choice = printer.get_valid_input("请选择插件查看配置", valid_options=range(1, len(plugin_names) + 1), cast_type=int)
		plugin_name = plugin_names[choice - 1]
		# 确保插件已加载
		if not self.manager.load_plugin(plugin_name):
			printer.prompt_input(f"无法加载插件 {plugin_name}, 按回车键返回", "ERROR")
			return
		config = self.manager.get_config(plugin_name)
		if config is None:
			printer.prompt_input("无可用配置, 按回车键返回", "COMMENT")
			return
		printer.print_header(f"{plugin_name} 的配置")
		for key, value in config.items():
			print(f"- {printer.color_text(key, 'MENU_ITEM')}: {value}")
		printer.prompt_input("按回车键返回", "COMMENT")

	def update_config(self) -> None:
		"""更新插件配置"""
		plugins = self.manager.get_plugin_list()
		printer.print_header("插件列表")
		plugin_names = list(plugins.keys())
		for idx, name in enumerate(plugin_names, 1):
			print(f"{idx:2d}. {name}")
		choice = printer.get_valid_input("请选择插件更新配置", valid_options=range(1, len(plugin_names) + 1), cast_type=int)
		plugin_name = plugin_names[choice - 1]
		# 确保插件已加载
		if not self.manager.load_plugin(plugin_name):
			printer.prompt_input(f"无法加载插件 {plugin_name}, 按回车键返回", "ERROR")
			return
		# 获取当前配置
		current_config = self.manager.get_config(plugin_name)
		if current_config is None:
			printer.prompt_input("无可用配置, 按回车键返回", "COMMENT")
			return
		printer.print_header(f"{plugin_name} 的当前配置")
		for key, value in current_config.items():
			print(f"- {printer.color_text(key, 'MENU_ITEM')}: {value}")
		# 获取新配置
		new_config: dict[str, Any] = {}
		printer.print_header("输入新配置")
		printer.prompt_input("输入新配置 (输入空行结束)", "PROMPT")
		for key in current_config:
			new_value = printer.prompt_input(f"{key} ({type(current_config[key]).__name__})")
			if new_value:
				# 尝试转换类型
				try:
					# 根据当前值的类型转换
					if isinstance(current_config[key], int):
						new_config[key] = int(new_value)
					elif isinstance(current_config[key], float):
						new_config[key] = float(new_value)
					elif isinstance(current_config[key], bool):
						# 使用集合提高查找效率
						new_config[key] = new_value.lower() in {"true", "1", "yes", "y"}
					else:
						new_config[key] = new_value
				except ValueError:
					printer.prompt_input(f"无法转换 {key} 的值, 使用字符串", "WARNING")
					new_config[key] = new_value
		# 更新配置
		if new_config:
			if self.manager.update_config(plugin_name, new_config):
				printer.prompt_input("配置更新成功, 按回车键返回", "SUCCESS")
			printer.prompt_input("配置更新失败, 按回车键返回", "ERROR")
		printer.prompt_input("未提供新配置, 按回车键返回", "COMMENT")
