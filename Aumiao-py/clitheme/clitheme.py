# Copyright (c) 2025 Aurzex (github.com/aurzex)  # noqa: INP001
# --使用条款--
# 【请仔细阅读该使用条款】
# 根据以下条款,你可以使用、分发、和修改该文件,以及对文件内容进行二次创作:
# - 所有副本必须保留上方的【作者版权说明】和【该使用须知】
# - 如果对文件中的文字内容有任何修改(除细微问题修复外),必须在现有作者版权说明后添加相关作者/你的修改署名
# - 不得以任何商业或盈利通途传播该文件(非商业用途)
# - 不得以侵犯他人及本作者合法权益、违反法律法规或相关平台规定、或严重违背价值观常识的方式传播和修改该文件
# - 除原文件中包含的内容外,本作者不对任何他人额外修改或添加的内容部分承担任何责任
#
# * 原作者有权追究任何违反以上使用须知的使用

import argparse
import json
import re
import subprocess  # noqa: S404
import sys
import threading
from pathlib import Path
from typing import Any, TextIO


def load_config(file_path: Path) -> dict:
	"""加载JSON配置文件"""
	try:
		with file_path.open(encoding="utf-8") as f:
			config = json.load(f)

		# 验证配置文件结构
		if not isinstance(config, dict):
			msg = "配置文件格式错误: 根元素必须是字典"
			raise TypeError(msg)  # noqa: TRY301
		if "replacements" not in config:
			msg = "配置文件中缺少 'replacements' 部分"
			raise ValueError(msg)  # noqa: TRY301

	except Exception as e:
		print(f"加载配置文件时出错: {e}", file=sys.stderr)
		sys.exit(1)
	return config


def compile_replacements(replacements: list[dict[str, Any]]) -> list[dict[str, Any]]:
	"""编译正则表达式替换规则"""
	compiled = []
	for rule in replacements:
		try:
			pattern = rule.get("pattern")
			replacement = rule.get("replacement")
			locale = rule.get("locale", "default")
			commands = rule.get("filter_commands", [])

			if not pattern or not replacement:
				print("警告: 规则缺少必要字段 'pattern' 或 'replacement'", file=sys.stderr)
				continue

			# 尝试编译正则表达式,失败则跳过
			try:
				regex = re.compile(pattern)
			except re.error as e:
				print(f"无效的正则表达式 '{pattern}': {e}", file=sys.stderr)
				continue

			compiled.append(
				{
					"pattern": regex,
					"replacement": replacement,
					"locale": locale,
					"commands": [cmd.lower() for cmd in commands],  # 统一转换为小写
				},
			)
		except Exception as e:
			print(f"处理规则时出错: {e}", file=sys.stderr)
	return compiled


def apply_replacements(text: str, command_name: str, replacements: list[dict[str, Any]], locale: str = "default") -> str:
	"""应用所有匹配的替换规则到文本"""
	command_name = command_name.lower()  # 统一为小写以便匹配
	for rule in replacements:
		# 检查命令过滤和locale匹配
		cmd_list = rule["commands"]
		if cmd_list and command_name not in cmd_list:
			continue
		if rule["locale"] != locale:
			continue
		text = rule["pattern"].sub(rule["replacement"], text)
	return text


def process_stream(stream: TextIO, command_name: str, replacements: list[dict[str, Any]], output_stream: TextIO, locale: str = "default") -> None:
	"""处理流数据并应用替换规则"""
	while True:
		line = stream.readline()
		if not line:
			break
		try:
			processed = apply_replacements(line, command_name, replacements, locale)
			output_stream.write(processed)
			output_stream.flush()
		except Exception as e:
			print(f"处理输出时出错: {e}", file=sys.stderr)
			output_stream.write(line)  # 出错时回退到原始输出
			output_stream.flush()


def execute_command(command: list[str], replacements: list[dict[str, Any]], locale: str = "default") -> int:
	"""执行命令并处理输出"""
	try:
		# 获取命令名称用于过滤规则
		command_name = Path(command[0]).name

		# 启动子进程 - 安全地执行命令
		proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, text=True, bufsize=1, encoding="utf-8", errors="replace")  # noqa: S603

		# 创建处理输出的线程
		stdout_thread = threading.Thread(target=process_stream, args=(proc.stdout, command_name, replacements, sys.stdout, locale))
		stderr_thread = threading.Thread(target=process_stream, args=(proc.stderr, command_name, replacements, sys.stderr, locale))

		stdout_thread.daemon = True
		stderr_thread.daemon = True

		stdout_thread.start()
		stderr_thread.start()

		# 处理标准输入
		try:
			while True:
				if proc.stdin is None:
					break
				input_line = sys.stdin.readline()
				if not input_line:  # EOF
					break
				proc.stdin.write(input_line)
				proc.stdin.flush()
		except (KeyboardInterrupt, BrokenPipeError):
			# 用户中断或管道关闭
			pass
		finally:
			if proc.stdin:
				proc.stdin.close()

		# 等待进程结束
		return_code = proc.wait()

		# 等待输出线程结束
		stdout_thread.join(5)
		stderr_thread.join(5)

	except FileNotFoundError:
		print(f"错误: 找不到命令 '{command[0]}'", file=sys.stderr)
		return 127  # 标准命令未找到退出码
	except Exception as e:
		print(f"执行命令时出错: {e}", file=sys.stderr)
		return 1
	return return_code


def main() -> None:
	parser = argparse.ArgumentParser(
		description="命令行输出文本替换工具",
		epilog="示例: clitheme.py -apply config.json -- python3 script.py\n        clitheme.py -apply config.json python3 script.py",
		formatter_class=argparse.RawTextHelpFormatter,
	)
	parser.add_argument("-apply", dest="config_file", required=True, help="包含替换规则的JSON配置文件")
	parser.add_argument("--locale", default="default", help="指定使用的语言环境(默认为 'default')")
	parser.add_argument("command", nargs=argparse.REMAINDER, help="要执行的命令及其参数")

	args = parser.parse_args()

	# 更灵活的命令参数处理
	command = args.command
	if command and command[0] == "--":
		command = command[1:]
	if not command:
		print("错误: 必须指定要执行的命令", file=sys.stderr)
		print("请提供要执行的命令及其参数。例如:", file=sys.stderr)
		print("  clitheme.py -apply config.json -- python3 your_script.py", file=sys.stderr)
		print("  clitheme.py -apply config.json python3 your_script.py", file=sys.stderr)
		sys.exit(1)

	# 加载和编译替换规则
	config_path = Path(args.config_file)
	if not config_path.exists():
		print(f"错误: 配置文件不存在 '{args.config_file}'", file=sys.stderr)
		sys.exit(1)

	config = load_config(config_path)
	replacements = compile_replacements(config["replacements"])

	# 执行命令
	return_code = execute_command(command, replacements, args.locale)
	sys.exit(return_code)


if __name__ == "__main__":
	main()
# python Aumiao-py/clitheme/clitheme.py -apply Aumiao-py/clitheme/theme.json -- python3 Aumiao-py/main.py
