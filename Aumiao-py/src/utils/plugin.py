import importlib
import inspect
import operator
import re
import sys
import traceback
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar, get_type_hints

from src.utils import data, tool

printer = tool.Printer()
T = TypeVar("T")
"""
插件开发规范:
1. 每个插件必须是一个独立的 Python 模块 (.py 文件或包)
2. 每个插件必须包含一个名为 'Plugin' 的类
3. Plugin 类必须实现以下内容:
	- 类属性:
		PLUGIN_NAME: 插件名称 (字符串)
		PLUGIN_DESCRIPTION: 插件描述 (字符串)
		PLUGIN_VERSION: 插件版本 (字符串)
		PLUGIN_CONFIG_SCHEMA: 插件配置模式 (字典), 定义配置结构
		PLUGIN_DEFAULT_CONFIG: 插件默认配置 (字典)
	- 方法:
		register() -> dict: 返回要暴露的方法字典
			格式: {"方法名": (方法对象, "方法描述")}
		on_load (config: dict): 插件加载时调用, 传入当前配置
		on_unload(): 插件卸载时调用
4. 插件可以放置在任意目录, 但需要被插件管理器扫描到
新增功能:
5. 插件现在可以修改其他模块的代码:
	- 通过 inject_code_at_line() 在指定行号插入代码
	- 通过 inject_code_at_pattern() 基于代码模式插入代码
	- 通过 rewrite_function() 完全重写函数
6. 插件方法可以定义参数类型和默认值, 系统会自动提示用户输入
"""


class CodeModificationManager:
	"""管理代码修改的类"""

	def __init__(self) -> None:
		self.line_injections = {}  # {module_name: [(line_number, code, position)]}
		self.pattern_injections = {}  # {module_name: [(pattern, code, position)]}
		self.function_rewrites = {}  # {module_name: {function_name: new_function}}
		self.modified_modules = set()

	def inject_code_at_line(self, module_name, line_number, code, position="before") -> None:  # noqa: ANN001
		"""在指定模块的指定行号插入代码"""
		if module_name not in self.line_injections:
			self.line_injections[module_name] = []
		self.line_injections[module_name].append({"line": line_number, "code": code, "position": position})

	def inject_code_at_pattern(self, module_name, pattern, code, position="after") -> None:  # noqa: ANN001
		"""基于代码模式插入代码"""
		if module_name not in self.pattern_injections:
			self.pattern_injections[module_name] = []
		self.pattern_injections[module_name].append({"pattern": re.compile(pattern), "code": code, "position": position})

	def rewrite_function(self, module_name, function_name, new_function) -> None:  # noqa: ANN001
		"""完全重写函数"""
		if module_name not in self.function_rewrites:
			self.function_rewrites[module_name] = {}
		self.function_rewrites[module_name][function_name] = new_function

	def apply_modifications(self, module_name: str) -> None:
		"""应用所有修改到指定模块"""
		if module_name not in sys.modules or module_name in self.modified_modules:
			return
		module = sys.modules[module_name]
		try:
			# 获取模块源代码
			source = inspect.getsource(module)
			modified_source = self._apply_all_modifications(module_name, source)
			if modified_source != source:
				# 编译并执行修改后的代码
				code = compile(modified_source, module.__file__, "exec")  # pyright: ignore [reportArgumentType]
				exec(code, module.__dict__)  # noqa: S102
			# 应用函数重写
			self._apply_function_rewrites(module_name, module)
			self.modified_modules.add(module_name)
			print(f"代码修改已应用到模块: {module_name}")
		except Exception as e:
			print(f"应用代码修改到 {module_name} 失败: {e}")
			traceback.print_exc()

	def _apply_all_modifications(self, module_name, source) -> str:  # noqa: ANN001
		"""应用所有代码修改"""
		lines = source.split("\n")
		modifications = []
		# 收集行号注入
		for injection in self.line_injections.get(module_name, []):
			line_num = injection["line"]
			if 0 <= line_num - 1 < len(lines):
				modifications.append({"line": line_num - 1, "code": injection["code"], "position": injection["position"]})
		# 收集模式匹配注入
		for injection in self.pattern_injections.get(module_name, []):
			for i, line in enumerate(lines):
				if injection["pattern"].search(line):
					modifications.append({"line": i, "code": injection["code"], "position": injection["position"]})
		# 按行号倒序应用修改 (避免影响行号)
		modifications.sort(key=operator.itemgetter("line"), reverse=True)
		for mod in modifications:
			indent = self._get_indentation(lines[mod["line"]])
			injected_code = f"{indent}{mod['code']}"
			if mod["position"] == "before":
				lines.insert(mod["line"], injected_code)
			elif mod["position"] == "after":
				lines.insert(mod["line"] + 1, injected_code)
			elif mod["position"] == "replace":
				lines[mod["line"]] = injected_code
		return "\n".join(lines)

	def _apply_function_rewrites(self, module_name, module) -> None:  # noqa: ANN001
		"""应用函数重写"""
		if module_name in self.function_rewrites:
			for func_name, new_func in self.function_rewrites[module_name].items():
				if hasattr(module, func_name):
					setattr(module, func_name, new_func)

	@staticmethod
	def _get_indentation(line) -> Any:  # noqa: ANN001
		"""获取行的缩进"""
		return line[: len(line) - len(line.lstrip())]


class BasePlugin(ABC):
	# 新增代码修改管理器
	code_modifier = CodeModificationManager()

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
		print(f"[系统] 插件 {self.PLUGIN_NAME} v {self.PLUGIN_VERSION} 已加载")
		self.apply_code_modifications()

	def on_unload(self) -> None:
		"""插件卸载时的回调"""
		print(f"[系统] 插件 {self.PLUGIN_NAME} 已卸载")

	def apply_code_modifications(self) -> None:  # noqa: B027
		"""应用代码修改 - 子类可以重写此方法"""

	# 新增代码修改方法
	def inject_at_line(self, module_name, line_number, code, position="before") -> None:  # noqa: ANN001
		"""在指定行号插入代码"""
		self.code_modifier.inject_code_at_line(module_name, line_number, code, position)

	def inject_at_pattern(self, module_name, pattern, code, position="after") -> None:  # noqa: ANN001
		"""基于代码模式插入代码"""
		self.code_modifier.inject_code_at_pattern(module_name, pattern, code, position)

	def rewrite_function(self, module_name, function_name, new_function) -> None:  # noqa: ANN001
		"""完全重写函数"""
		self.code_modifier.rewrite_function(module_name, function_name, new_function)


# ======================
# 增强的插件管理器
# ======================
class LazyPluginManager:
	def __init__(self, plugin_dir: Path) -> None:
		self.plugin_dir = plugin_dir
		self.plugin_info: dict[str, dict] = {}  # 插件元信息 {plugin_name: {meta}}
		self.loaded_plugins: dict[str, BasePlugin] = {}  # 已加载的插件 {plugin_name: plugin_instance}
		self.command_map: dict[str, tuple[str, str]] = {}  # 命令映射 {command_name: (plugin_name, method_name)}
		self.plugin_modules: dict[str, Any] = {}  # 已加载的模块 {plugin_name: module}
		# 代码修改管理器
		self.code_modifier = CodeModificationManager()
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
		"""获取插件列表 (不加载插件)"""
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

	def load_plugin(self, plugin_name: str) -> bool:
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
				self.plugin_info[plugin_name]["commands"][method_name] = {"description": description, "method": method, "signature": self._get_method_signature(method)}
			# 保存插件实例
			self.loaded_plugins[plugin_name] = plugin_instance
			self.plugin_info[plugin_name]["status"] = "loaded"
			# 更新全局配置
			self._update_global_config(plugin_name, config)
			# 应用代码修改
			self.code_modifier.apply_modifications(plugin_name)
		except Exception as e:
			print(f"[错误] 加载插件 {plugin_name} 失败: {e!s}")
			traceback.print_exc()
			return False
		else:
			return True

	@staticmethod
	def _get_method_signature(method: Callable) -> dict:
		"""获取方法的签名信息"""
		signature = inspect.signature(method)
		type_hints = get_type_hints(method)
		params = {}
		for name, param in signature.parameters.items():
			if name == "self":
				continue
			param_info = {
				"name": name,
				"default": param.default if param.default is not param.empty else None,
				"has_default": param.default is not param.empty,
				"type": type_hints.get(name, str),
				"annotation": param.annotation if param.annotation is not param.empty else Any,
			}
			params[name] = param_info
		return {"params": params, "return_type": type_hints.get("return", Any)}

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
		# 获取默认配置 (需要先加载插件)
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
		if not keyword:
			return
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
			print(f"描述: {info['description']}")
			if "version" in info:
				print(f"版本: {info['version']}")
			if info.get("commands"):
				commands_text = printer.color_text(",".join(info["commands"]), "MENU_ITEM")
				print(f"命令: {commands_text}")
		printer.prompt_input("按回车键返回", "COMMENT")

	def use_plugin(self) -> None:
		"""使用插件功能"""
		# 显示所有插件
		plugins = self.manager.get_plugin_list()
		if not plugins:
			printer.prompt_input("没有可用插件, 按回车键返回", "COMMENT")
			return
		printer.print_header("可用插件")
		plugin_names = list(plugins.keys())
		for idx, name in enumerate(plugin_names, 1):
			status = "已加载" if plugins[name]["status"] == "loaded" else "未加载"
			status_color = "SUCCESS" if plugins[name]["status"] == "loaded" else "COMMENT"
			status_text = printer.color_text(f"({status})", status_color)
			print(f"{idx:2d}. {name} {status_text}")
		print("0. 返回")
		choice = printer.get_valid_input("请选择插件编号 (输入 0 返回)", valid_options=range(len(plugin_names) + 1), cast_type=int)
		if choice == 0:
			return
		plugin_name = plugin_names[choice - 1]
		self.use_plugin_commands(plugin_name)

	def use_plugin_commands(self, plugin_name: str) -> None:
		"""使用插件的命令 - 优化为循环显示命令列表"""
		# 确保插件已加载
		if not self.manager.load_plugin(plugin_name):
			printer.prompt_input(f"无法加载插件 {plugin_name}, 按回车键返回", "ERROR")
			return
		while True:
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
			print("0. 返回")
			choice = printer.get_valid_input("请选择命令编号", valid_options=range(len(command_names) + 1), cast_type=int)
			if choice == 0:
				break
			command_name = command_names[choice - 1]
			self.execute_command(plugin_name, command_name, commands[command_name])
			# 执行完命令后不立即返回, 而是继续显示命令列表

	@staticmethod
	def execute_command(_plugin_name: str, command_name: str, command_info: dict) -> None:
		"""执行插件命令"""
		method = command_info["method"]
		signature = command_info.get("signature", {})
		params = signature.get("params", {})
		# 收集参数
		args = []
		kwargs = {}
		printer.print_header(f"执行命令: {command_name}")
		if params:
			print("请提供参数:")
			for param_name, param_info in params.items():
				param_type = param_info["type"]
				has_default = param_info["has_default"]
				default_value = param_info["default"]
				# 构建提示信息
				prompt = f"{param_name} ({param_type.__name__})"
				if has_default:
					prompt += f"[默认: {default_value}]"
				prompt += ":"
				# 获取用户输入
				value_input = input(prompt).strip()
				if not value_input and has_default:
					# 使用默认值
					value = default_value
				elif not value_input and not has_default:
					# 必需参数但没有提供值
					printer.print_message("此参数为必需参数, 必须提供值", "ERROR")
					return
				else:
					# 转换类型
					try:
						if param_type is int:
							value = int(value_input)
						elif param_type is float:
							value = float(value_input)
						elif param_type is bool:
							value = value_input.lower() in {"true", "1", "yes", "y"}
						else:
							value = value_input
					except ValueError:
						printer.print_message(f"无法将 '{value_input}' 转换为 {param_type.__name__}", "ERROR")
						return
				kwargs[param_name] = value
		else:
			printer.print_message("此命令不需要参数", "COMMENT")
		# 执行命令
		try:
			result = method(*args, **kwargs)
			printer.print_header("执行结果")
			if result is not None:
				print(result)
			printer.prompt_input("按回车键继续...", "COMMENT")
		except Exception as e:
			printer.prompt_input(f"执行命令失败: {e!s}, 按回车键继续...", "ERROR")

	def view_config(self) -> None:
		"""查看插件配置"""
		plugins = self.manager.get_plugin_list()
		if not plugins:
			printer.prompt_input("没有可用插件, 按回车键返回", "COMMENT")
			return
		printer.print_header("插件列表")
		plugin_names = list(plugins.keys())
		for idx, name in enumerate(plugin_names, 1):
			print(f"{idx:2d}. {name}")
		print("0. 返回")
		choice = printer.get_valid_input("请选择插件查看配置", valid_options=range(len(plugin_names) + 1), cast_type=int)
		if choice == 0:
			return
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
		if not plugins:
			printer.prompt_input("没有可用插件, 按回车键返回", "COMMENT")
			return
		printer.print_header("插件列表")
		plugin_names = list(plugins.keys())
		for idx, name in enumerate(plugin_names, 1):
			print(f"{idx:2d}. {name}")
		print("0. 返回")
		choice = printer.get_valid_input("请选择插件更新配置", valid_options=range(len(plugin_names) + 1), cast_type=int)
		if choice == 0:
			return
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
		printer.print_header("输入新配置 (输入空值保持原配置)")
		for key, current_value in current_config.items():
			value_type = type(current_value)
			prompt = f"{key} ({value_type.__name__}) [当前: {current_value}]:"
			new_value = input(prompt).strip()
			if not new_value:
				new_config[key] = current_value
				continue
			# 尝试转换类型
			try:
				if value_type is int:
					new_config[key] = int(new_value)
				elif value_type is float:
					new_config[key] = float(new_value)
				elif value_type is bool:
					new_config[key] = new_value.lower() in {"true", "1", "yes", "y"}
				else:
					new_config[key] = new_value
			except ValueError:
				printer.print_message(f"无法转换 {key} 的值, 使用原值", "ERROR")
				new_config[key] = current_value
		# 更新配置
		if self.manager.update_config(plugin_name, new_config):
			printer.prompt_input("配置更新成功, 按回车键返回", "SUCCESS")
		else:
			printer.prompt_input("配置更新失败, 按回车键返回", "ERROR")
