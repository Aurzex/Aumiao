# 插件开发文档

## 概述

本插件系统允许开发者扩展应用程序功能，而无需修改主程序代码。插件可以：

1. 提供新的命令和功能
2. 修改现有模块的代码（通过行号插入、模式匹配插入、函数重写）
3. 响应插件加载和卸载事件

## 插件结构

每个插件必须是一个独立的 Python 模块（.py 文件），并包含一个名为`Plugin`的类，该类继承自`BasePlugin`。

### 必需部分

1. **类属性**：

   - `PLUGIN_NAME`: 插件名称（字符串）
   - `PLUGIN_DESCRIPTION`: 插件描述（字符串）
   - `PLUGIN_VERSION`: 插件版本（字符串）
   - `PLUGIN_CONFIG_SCHEMA`: 配置模式（字典），定义配置项的类型
   - `PLUGIN_DEFAULT_CONFIG`: 默认配置（字典）

2. **方法**：
   - `register()`: 返回一个字典，键为命令名，值为一个元组（可调用对象，描述字符串）
   - `on_load(config)`: 插件加载时调用，传入当前配置
   - `on_unload()`: 插件卸载时调用

### 可选部分

- `apply_code_modifications()`: 如果你需要修改其他模块的代码，可以重写此方法，并在其中使用注入方法。

## 代码修改功能

插件可以修改其他模块的代码，支持三种方式：

1. **行号注入**：在指定模块的指定行号前后插入代码

   ```python
   self.inject_at_line(module_name, line_number, code, position='before')
   ```

2. **模式匹配注入**：在匹配到指定正则表达式模式的代码行前后插入代码

   ```python
   self.inject_at_pattern(module_name, pattern, code, position='after')
   ```

3. **函数重写**：完全替换指定模块中的函数
   ```python
   self.rewrite_function(module_name, function_name, new_function)
   ```

## 配置说明

插件配置通过全局配置管理器管理。配置模式定义了每个配置项的类型，系统会自动进行类型验证和转换。

### 配置模式支持的类型

- `bool`: 布尔值（true/false, 1/0, yes/no）
- `int`: 整数
- `float`: 浮点数
- `str`: 字符串
- `list`: 列表
- `dict`: 字典

## 开发指南

### 1. 创建插件文件

在插件目录中创建新的.py 文件，例如`my_plugin.py`。

### 2. 实现插件类

按照上述结构实现`Plugin`类，确保包含所有必需的属性和方法。

### 3. 测试插件

使用插件控制台加载和测试插件功能：

```python
# 初始化插件管理器
manager = LazyPluginManager(Path("plugins"))

# 加载插件
manager.load_plugin("example_plugin")

# 执行插件命令
result = manager.execute_command("example_info")
print(result)
```

### 4. 调试技巧

- 使用`print`语句输出调试信息
- 检查控制台错误消息
- 使用`try/except`捕获和处理异常

## 最佳实践

1. **错误处理**：妥善处理可能出现的异常
2. **资源管理**：在`on_unload`中释放资源
3. **配置验证**：确保配置值在合理范围内
4. **性能考虑**：避免在代码修改中引入性能问题
5. **兼容性**：确保插件与不同版本的主程序兼容

## 常见问题

### Q: 插件加载失败怎么办？

A: 检查控制台错误信息，常见问题包括：

- 缺少必需的类属性
- register()返回格式不正确
- 语法错误

### Q: 代码修改没有生效怎么办？

A: 检查：

- 模块名称是否正确
- 行号是否准确
- 正则表达式模式是否匹配

### Q: 如何调试代码修改？

A: 在`apply_code_modifications`方法中添加打印语句，确认修改已应用。

## 支持

如有问题，请参考示例插件或联系开发团队。
