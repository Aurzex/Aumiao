# 插件开发文档

## 概述

本插件系统允许开发者扩展应用程序功能，而无需修改主程序代码。插件可以：

1. 提供新的命令和功能
2. **动态修改现有模块的代码**（通过行号插入、模式匹配插入、函数重写）
3. 响应插件加载和卸载事件
4. 管理配置和持久化数据

## 插件结构

每个插件必须是一个独立的 Python 模块（.py 文件），并包含一个名为`Plugin`的类，该类继承自`BasePlugin`。

### 必需部分

```python
from collections.abc import Callable
from typing import Any
from src.utils.plugin import BasePlugin

class Plugin(BasePlugin):
    @property
    def PLUGIN_NAME(self) -> str:
        return "示例插件"

    @property
    def PLUGIN_DESCRIPTION(self) -> str:
        return "这是一个示例插件"

    @property
    def PLUGIN_VERSION(self) -> str:
        return "1.0.0"

    @property
    def PLUGIN_CONFIG_SCHEMA(self) -> dict[str, Any]:
        return {
            "enabled": bool,
            "max_retries": int,
            "timeout": float,
            "api_key": str
        }

    @property
    def PLUGIN_DEFAULT_CONFIG(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "max_retries": 3,
            "timeout": 30.0,
            "api_key": ""
        }

    def register(self) -> dict[str, tuple[Callable, str]]:
        return {
            "example_command": (self.example_method, "示例命令描述"),
            "another_command": (self.another_method, "另一个命令")
        }

    def on_load(self, config: dict[str, Any]) -> None:
        self.config = config
        print(f"插件 {self.PLUGIN_NAME} 已加载")

    def on_unload(self) -> None:
        print(f"插件 {self.PLUGIN_NAME} 已卸载")
```

## 代码修改功能 - 重要更新

插件可以**动态修改其他模块的代码**，但需要注意加载时机和可靠性。

### 三种修改方式

#### 1. **行号注入**（不推荐 - 易受代码变动影响）

```python
self.inject_at_line("target_module", 42, "print('注入的代码')", position='before')
```

#### 2. **模式匹配注入**（中等可靠性）

```python
self.inject_at_pattern(
    "target_module",
    r"def target_function.*:",
    "    print('在函数开始前执行')",
    position='after'
)
```

#### 3. **函数重写**（推荐 - 最可靠）

```python
def new_function(self, *args, **kwargs):
    print("这是重写的函数")
    # 可选：调用原始函数
    if hasattr(self, '_original_function'):
        return self._original_function(*args, **kwargs)
    return None

self.rewrite_function("target_module", "target_function", new_function)
```

### 🚨 重要注意事项

#### 加载时机问题

代码修改必须在目标模块**被导入之前**应用。如果目标模块已经加载，修改可能不会生效。

**解决方案：**

```python
def on_load(self, config: dict[str, Any]) -> None:
    super().on_load(config)
    self.config = config

    # 备份原始函数引用
    self._backup_original_functions()

    if config.get("enabled", True):
        self.apply_code_modifications()

def _backup_original_functions(self):
    """备份需要修改的函数"""
    try:
        import target_module
        if hasattr(target_module, 'function_to_modify'):
            self._original_function = target_module.function_to_modify
    except ImportError:
        print("目标模块未找到")

def apply_code_modifications(self):
    """应用代码修改"""
    try:
        # 方法1: 直接函数替换（最可靠）
        import target_module
        target_module.function_to_modify = self.new_implementation

        # 方法2: 使用系统的代码修改功能
        self.rewrite_function("target_module", "function_to_modify", self.new_implementation)
        self.code_modifier.apply_modifications("target_module")

    except Exception as e:
        print(f"代码修改失败: {e}")

def on_unload(self):
    """恢复原始函数"""
    if hasattr(self, '_original_function'):
        try:
            import target_module
            target_module.function_to_modify = self._original_function
        except Exception:
            pass
    super().on_unload()
```

## 配置管理

### 配置模式支持的类型

- `bool`: 布尔值（true/false, 1/0, yes/no）
- `int`: 整数
- `float`: 浮点数
- `str`: 字符串
- `list`: 列表
- `dict`: 字典

### 配置访问方法

```python
def example_method(self):
    # 访问配置
    if self.config.get("enabled", False):
        retries = self.config.get("max_retries", 3)
        # 使用配置...
```

## 开发指南

### 1. 创建插件文件结构

```
plugins/
├── my_plugin.py
└── __init__.py
```

### 2. 完整的插件示例

```python
from collections.abc import Callable
from typing import Any
from src.utils.plugin import BasePlugin

class Plugin(BasePlugin):
    @property
    def PLUGIN_NAME(self) -> str:
        return "高级修改插件"

    @property
    def PLUGIN_DESCRIPTION(self) -> str:
        return "演示可靠的代码修改技术"

    @property
    def PLUGIN_VERSION(self) -> str:
        return "2.5.0"

    @property
    def PLUGIN_CONFIG_SCHEMA(self) -> dict[str, Any]:
        return {
            "enable_modification": bool,
            "log_level": str,
            "modification_mode": str
        }

    @property
    def PLUGIN_DEFAULT_CONFIG(self) -> dict[str, Any]:
        return {
            "enable_modification": True,
            "log_level": "INFO",
            "modification_mode": "direct"
        }

    def __init__(self):
        super().__init__()
        self.original_functions = {}

    def register(self) -> dict[str, tuple[Callable, str]]:
        return {
            "test_modification": (self.test_modification, "测试代码修改"),
            "get_status": (self.get_status, "获取插件状态")
        }

    def on_load(self, config: dict[str, Any]) -> None:
        super().on_load(config)
        self.config = config

        # 备份原始函数
        self._backup_functions()

        if config.get("enable_modification", True):
            result = self.apply_code_modifications()
            print(f"代码修改结果: {result}")

    def on_unload(self) -> None:
        # 恢复原始函数
        self._restore_functions()
        super().on_unload()
        print("所有修改已恢复")

    def _backup_functions(self):
        """备份所有要修改的函数"""
        try:
            import src.community as community
            if hasattr(community, 'authenticate_with_token'):
                self.original_functions['authenticate_with_token'] = community.authenticate_with_token
        except Exception as e:
            print(f"备份函数失败: {e}")

    def _restore_functions(self):
        """恢复所有修改的函数"""
        try:
            import src.community as community
            for func_name, original_func in self.original_functions.items():
                if hasattr(community, func_name):
                    setattr(community, func_name, original_func)
        except Exception as e:
            print(f"恢复函数失败: {e}")

    def apply_code_modifications(self) -> str:
        """应用代码修改 - 使用最可靠的方法"""
        try:
            import src.community as community

            # 方法1: 直接替换（最可靠）
            community.authenticate_with_token = self.new_authenticate_function

            # 方法2: 使用系统的重写功能
            self.rewrite_function("src.community", "authenticate_with_token", self.new_authenticate_function)

            return "代码修改成功应用"
        except Exception as e:
            return f"代码修改失败: {e}"

    def new_authenticate_function(self, token):
        """新的认证函数实现"""
        print(f"[插件] 认证请求: {token}")
        # 调用原始函数
        if 'authenticate_with_token' in self.original_functions:
            return self.original_functions['authenticate_with_token'](token)
        return None

    def test_modification(self) -> str:
        """测试修改是否生效"""
        try:
            import src.community as community
            # 模拟调用
            result = community.authenticate_with_token("test_token")
            return f"测试成功，函数已修改"
        except Exception as e:
            return f"测试失败: {e}"

    def get_status(self) -> dict:
        """获取插件状态"""
        return {
            "plugin_name": self.PLUGIN_NAME,
            "version": self.PLUGIN_VERSION,
            "config": self.config,
            "backup_functions": list(self.original_functions.keys())
        }
```

## 最佳实践

### ✅ 推荐做法

1. **备份原始函数**：在修改前保存原始函数的引用
2. **错误处理**：使用 try/except 包装所有可能失败的操作
3. **资源清理**：在 on_unload 中恢复所有修改
4. **配置验证**：在 on_load 中验证配置有效性
5. **日志记录**：使用 print 或日志系统记录重要操作

### ❌ 避免的做法

1. **直接修改已加载模块**：不备份就修改
2. **忽略异常**：不使用错误处理
3. **硬编码路径**：使用相对导入或动态检测
4. **假设加载顺序**：不要假设目标模块的加载状态

## 调试和故障排除

### 常见问题解决方案

#### Q: 代码修改没有生效？

**A:** 检查目标模块是否已加载，使用重新加载：

```python
import importlib
if "target_module" in sys.modules:
    importlib.reload(sys.modules["target_module"])
```

#### Q: 插件加载失败？

**A:** 检查：

- 所有必需属性是否正确定义
- register() 返回正确的格式
- 没有语法错误

#### Q: 配置不保存？

**A:** 确保使用正确的配置键名，并在修改后调用保存：

```python
self.manager.update_config(plugin_name, new_config)
```

### 调试工具

```python
def debug_module_status(self):
    """调试模块状态"""
    import sys
    modules = [m for m in sys.modules if 'community' in m]
    print(f"已加载的相关模块: {modules}")

    if 'src.community' in sys.modules:
        module = sys.modules['src.community']
        print(f"模块函数: {[f for f in dir(module) if not f.startswith('_')]}")
```

## 性能建议

1. **延迟加载**：只在需要时加载重型模块
2. **缓存结果**：对昂贵操作使用缓存
3. **避免循环导入**：小心处理模块依赖关系
4. **及时清理**：在 on_unload 中释放所有资源

## 支持资源

- 查看现有插件示例
- 使用调试方法检查模块状态
- 在 on_load/on_unload 中添加详细的日志记录
- 测试各种加载场景下的行为

这个更新后的文档强调了代码修改的可靠性和最佳实践，帮助开发者避免常见的陷阱。
