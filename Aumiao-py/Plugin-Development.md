# 插件开发文档

## 概述

本文档详细介绍了如何为基于 `LazyPluginManager` 的插件系统开发插件。该系统采用懒加载机制，支持动态加载、卸载和配置管理。

## 插件结构要求

每个插件必须是一个独立的 Python 模块（.py 文件或包），并包含一个名为 `Plugin` 的类，该类必须继承自 `BasePlugin` 抽象类或实现其所有抽象方法和属性。

### 必需组件

1. **类属性**：

   - `PLUGIN_NAME`: 插件名称（字符串）
   - `PLUGIN_DESCRIPTION`: 插件描述（字符串）
   - `PLUGIN_VERSION`: 插件版本（字符串）
   - `PLUGIN_CONFIG_SCHEMA`: 插件配置模式（字典），定义配置结构
   - `PLUGIN_DEFAULT_CONFIG`: 插件默认配置（字典）

2. **方法**：
   - `register() -> dict`: 返回要暴露的方法字典
   - `on_load(config: dict)`: 插件加载时调用，传入当前配置（可选重写）
   - `on_unload()`: 插件卸载时调用（可选重写）

## 详细规范

### 1. 插件元信息

```python
@property
def PLUGIN_NAME(self) -> str:
    return "示例插件"

@property
def PLUGIN_DESCRIPTION(self) -> str:
    return "这是一个示例插件，用于演示插件开发规范"

@property
def PLUGIN_VERSION(self) -> str:
    return "1.0.0"
```

### 2. 配置管理

```python
@property
def PLUGIN_CONFIG_SCHEMA(self) -> dict[str, Any]:
    return {
        "api_key": str,        # 字符串类型配置
        "max_retries": int,     # 整数类型配置
        "enable_feature": bool, # 布尔类型配置
        "timeout": float        # 浮点数类型配置
    }

@property
def PLUGIN_DEFAULT_CONFIG(self) -> dict[str, Any]:
    return {
        "api_key": "",
        "max_retries": 3,
        "enable_feature": True,
        "timeout": 30.0
    }
```

### 3. 方法注册

```python
def register(self) -> dict[str, tuple[Callable, str]]:
    return {
        "fetch_data": (self.fetch_data, "获取数据方法"),
        "process_item": (self.process_item, "处理单个项目"),
        "batch_process": (self.batch_process, "批量处理方法")
    }
```

### 4. 生命周期方法

```python
def on_load(self, config: dict[str, Any]) -> None:
    """插件加载时的回调"""
    # 初始化操作
    self.config = config
    self.initialize_client()
    print(f"[{self.PLUGIN_NAME}] 插件已加载，配置: {config}")

def on_unload(self) -> None:
    """插件卸载时的回调"""
    # 清理操作
    self.cleanup_resources()
    print(f"[{self.PLUGIN_NAME}] 插件已卸载")
```

## 完整示例插件

```python
# example_plugin.py
import time
from typing import Any
from collections.abc import Callable

class Plugin:
    """示例插件"""

    @property
    def PLUGIN_NAME(self) -> str:
        return "示例数据处理插件"

    @property
    def PLUGIN_DESCRIPTION(self) -> str:
        return "提供数据获取和处理功能"

    @property
    def PLUGIN_VERSION(self) -> str:
        return "1.0.0"

    @property
    def PLUGIN_CONFIG_SCHEMA(self) -> dict[str, Any]:
        return {
            "api_endpoint": str,
            "timeout_seconds": int,
            "enable_cache": bool
        }

    @property
    def PLUGIN_DEFAULT_CONFIG(self) -> dict[str, Any]:
        return {
            "api_endpoint": "https://api.example.com/data",
            "timeout_seconds": 10,
            "enable_cache": True
        }

    def on_load(self, config: dict[str, Any]) -> None:
        """插件加载回调"""
        self.config = config
        self.cache = {} if config["enable_cache"] else None
        print(f"[{self.PLUGIN_NAME}] 已加载，配置: {config}")

    def on_unload(self) -> None:
        """插件卸载回调"""
        print(f"[{self.PLUGIN_NAME}] 已卸载")

    def register(self) -> dict[str, tuple[Callable, str]]:
        """注册暴露的方法"""
        return {
            "fetch_user_data": (self.fetch_user_data, "获取用户数据"),
            "process_data": (self.process_data, "处理数据"),
            "get_stats": (self.get_stats, "获取统计信息")
        }

    # 以下是插件提供的功能方法
    def fetch_user_data(self, user_id: str) -> dict:
        """获取用户数据"""
        # 模拟API调用
        print(f"获取用户 {user_id} 的数据...")
        time.sleep(0.5)  # 模拟网络延迟
        return {"id": user_id, "name": "示例用户", "score": 85}

    def process_data(self, data: list) -> list:
        """处理数据"""
        print(f"处理 {len(data)} 条数据...")
        return [{"processed": True, **item} for item in data]

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {"total_processed": 100, "average_score": 78.5}
```

## 插件开发最佳实践

### 1. 命名规范

遵循项目统一的函数命名规范：

- `fetch_` - 远程数据获取
- `grab_` - 本地数据获取
- `create_` - 创建资源
- `delete_` - 删除资源
- `update_` - 更新资源
- `execute_` - 执行操作
- `validate_` - 数据验证
- `is_` - 布尔判断
- `has_` - 存在性检查
- `_gen` - 生成器
- `do_` - 其他操作

### 2. 错误处理

```python
def safe_method(self, *args):
    try:
        # 可能出错的操作
        return self._unsafe_method(*args)
    except Exception as e:
        print(f"方法执行失败: {e}")
        return None
```

### 3. 资源管理

```python
def on_load(self, config):
    # 初始化资源
    self.db_connection = create_connection(config["db_url"])

def on_unload(self):
    # 清理资源
    if hasattr(self, "db_connection"):
        self.db_connection.close()
```

### 4. 配置验证

```python
def validate_config(self, config: dict) -> bool:
    """验证配置有效性"""
    required_keys = ["api_key", "endpoint"]
    return all(key in config for key in required_keys)
```

## 插件部署

1. 将插件文件(.py)放置在插件管理器指定的目录中
2. 确保插件文件名与插件名称一致（或通过模块名识别）
3. 插件管理器会自动扫描并识别可用插件

## 调试与测试

1. 使用插件控制台交互式测试插件功能
2. 检查控制台输出以识别加载和运行问题
3. 验证配置是否正确保存和加载

## 注意事项

1. 避免在插件中使用全局状态，除非必要
2. 确保插件线程安全（如果系统是多线程的）
3. 遵循最小权限原则，只暴露必要的方法
4. 处理所有可能的异常，避免插件崩溃影响主系统

通过遵循本文档规范，您可以开发出符合标准的插件，并能与插件管理系统无缝集成。
