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
from dataclasses import dataclass
from pathlib import Path
from re import Pattern
from typing import Any, TextIO


# 预编译规则结构
@dataclass
class ReplacementRule:
	__slots__ = ("commands", "locale", "pattern", "replacement")

	def __init__(
		self,
		pattern: Pattern[str],
		replacement: str,
		locale: str,
		commands: list[str],
	) -> None:
		self.pattern = pattern
		self.replacement = replacement
		self.locale = locale
		self.commands = commands


def load_config(file_path: Path) -> dict[str, Any]:
	"""加载并验证JSON配置文件"""
	try:
		with file_path.open(encoding="utf-8") as f:
			config = json.load(f)

		if not isinstance(config, dict):
			msg = "配置文件格式错误: 根元素必须是字典"
			raise ValueError(msg)  # noqa: TRY004, TRY301
		if "replacements" not in config:
			msg = "配置文件中缺少 'replacements' 部分"
			raise ValueError(msg)  # noqa: TRY301

	except Exception as e:
		print(f"加载配置文件时出错: {e}", file=sys.stderr)
		sys.exit(1)
	else:
		return config


def compile_replacements(replacements: list[dict[str, Any]]) -> list[ReplacementRule]:
	"""编译正则表达式替换规则,使用类代替字典提高性能"""
	compiled = []
	for rule in replacements:
		pattern_str = rule.get("pattern")
		replacement = rule.get("replacement")
		locale = rule.get("locale", "default")
		commands = rule.get("filter_commands", [])

		if not pattern_str or not replacement:
			print("警告: 规则缺少必要字段 'pattern' 或 'replacement'", file=sys.stderr)
			continue

		try:
			pattern = re.compile(pattern_str)
			# 统一命令名为小写
			norm_commands = [cmd.lower() for cmd in commands]
			compiled.append(ReplacementRule(pattern, replacement, locale, norm_commands))
		except re.error as e:
			print(f"无效的正则表达式 '{pattern_str}': {e}", file=sys.stderr)

	return compiled


def apply_replacements(
	text: str,
	command_name: str,
	replacements: list[ReplacementRule],
	locale: str = "default",
) -> str:
	"""应用所有匹配的替换规则到文本"""
	command_name = command_name.lower()
	for rule in replacements:
		# 快速跳过不匹配的规则
		if rule.commands and command_name not in rule.commands:
			continue
		if rule.locale != locale:
			continue
		text = rule.pattern.sub(rule.replacement, text)
	return text


def process_stream(
	stream: TextIO,
	command_name: str,
	replacements: list[ReplacementRule],
	output_stream: TextIO,
	locale: str = "default",
) -> None:
	"""处理流数据并应用替换规则,优化缓冲区处理"""
	while True:
		line = stream.readline()
		if not line:
			break

		try:
			processed = apply_replacements(line, command_name, replacements, locale)
			# 立即输出处理后的行,而不是使用缓冲区
			output_stream.write(processed)
			output_stream.flush()
		except Exception as e:
			print(f"处理输出时出错: {e}", file=sys.stderr)
			output_stream.write(line)
			output_stream.flush()


def execute_command(
	command: list[str],
	replacements: list[ReplacementRule],
	locale: str = "default",
) -> int:
	"""执行命令并处理输出,优化交互式命令处理"""
	try:
		command_name = Path(command[0]).name
		is_interactive = command_name.lower() in {"python", "python3", "ipython", "bash", "sh", "cmd", "zsh"}

		# 使用上下文管理器确保资源释放
		with subprocess.Popen(  # noqa: S603
			command if not is_interactive else [" ".join(command)],
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			stdin=subprocess.PIPE if is_interactive else None,
			text=True,
			bufsize=1,
			encoding="utf-8",
			errors="replace",
			shell=is_interactive,
		) as proc:
			# 创建处理输出的线程
			stdout_thread = threading.Thread(
				target=process_stream,
				args=(proc.stdout, command_name, replacements, sys.stdout, locale),
				daemon=True,
			)
			stderr_thread = threading.Thread(
				target=process_stream,
				args=(proc.stderr, command_name, replacements, sys.stderr, locale),
				daemon=True,
			)

			stdout_thread.start()
			stderr_thread.start()

			# 处理交互式输入
			if is_interactive and proc.stdin:
				try:
					while proc.poll() is None:
						try:
							input_line = sys.stdin.readline()
							if not input_line:
								break
							proc.stdin.write(input_line)
							proc.stdin.flush()
						except (KeyboardInterrupt, EOFError):
							break
				except Exception as e:
					print(f"处理输入时出错: {e}", file=sys.stderr)
				finally:
					proc.stdin.close()

			# 等待进程结束
			return_code = proc.wait()

			# 等待输出线程结束
			stdout_thread.join(2.0)
			stderr_thread.join(2.0)

			return return_code

	except FileNotFoundError:
		print(f"错误: 找不到命令 '{command[0]}'", file=sys.stderr)
		return 127
	except Exception as e:
		print(f"执行命令时出错: {e}", file=sys.stderr)
		return 1


def main() -> None:
	parser = argparse.ArgumentParser(
		description="命令行输出文本替换工具",
		epilog="示例:\n  clitheme.py -apply config.json -- python3 script.py\n  clitheme.py -apply config.json python3 script.py",
		formatter_class=argparse.RawTextHelpFormatter,
	)
	parser.add_argument("-apply", dest="config_file", required=True, help="包含替换规则的JSON配置文件")
	parser.add_argument("--locale", default="default", help="指定使用的语言环境(默认为 'default')")
	parser.add_argument("command", nargs=argparse.REMAINDER, help="要执行的命令及其参数")

	args = parser.parse_args()

	# 处理命令参数
	command = args.command
	if command and command[0] == "--":
		command = command[1:]
	if not command:
		print("错误: 必须指定要执行的命令", file=sys.stderr)
		print("使用示例:", file=sys.stderr)
		print("  clitheme.py -apply config.json -- python3 your_script.py", file=sys.stderr)
		print("  clitheme.py -apply config.json python3 your_script.py", file=sys.stderr)
		sys.exit(1)

	# 加载配置
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
# python Aumiao-py/clitheme/clitheme.py -apply Aumiao-py/clitheme/theme.json -- python3 -i
