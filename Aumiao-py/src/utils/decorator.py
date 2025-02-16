from collections.abc import Callable, Generator
from functools import wraps
from locale import Error
from time import sleep
from typing import Any


def singleton(cls):  # noqa: ANN001, ANN201
	_instance = {}

	def _singleton(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
		# 如果cls不在_instance中,则创建cls的实例,并将其添加到_instance中
		if cls not in _instance:
			_instance[cls] = cls(*args, **kwargs)
		# 返回_instance中cls的实例
		return _instance[cls]

	# 返回_singleton函数
	return _singleton


def retry(retries: int = 3, delay: float = 1) -> Callable:
	# 如果重试次数小于1或者延迟时间小于等于0,则抛出ValueError异常
	if retries < 1 or delay <= 0:
		msg = "Are you high, mate?"
		raise ValueError(msg)

	# 定义装饰器函数
	def decorator(func: Callable) -> Callable:
		# 使用wraps装饰器,保留原函数的元信息
		@wraps(func)
		def wrapper(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
			# 循环重试
			for i in range(1, retries + 1):
				try:
					# 调用原函数
					return func(*args, **kwargs)
				except Exception as e:
					# 如果重试次数达到上限,则抛出异常
					if i == retries:
						print(f"Error: {e!r}.")
						print(f'"{func.__name__}()" failed after {retries} retries.')
						break
					# 否则,打印错误信息并等待一段时间后重试
					print(f"Error: {e!r} -> Retrying...")
					sleep(delay)
			# 如果重试次数达到上限,则抛出Error异常
			raise Error

		return wrapper

	return decorator


def skip_on_error(func):  # noqa: ANN001, ANN201
	"""捕获异常并跳过当前循环"""

	@wraps(func)
	def wrapper(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
		try:
			return func(*args, **kwargs)
		except Exception as e:
			print(f"Error occurred: {e}. Skipping this iteration.")
			return None  # 继续执行下一个循环

	return wrapper


def generator(chunk_size: int = 1000) -> Callable:
	# 定义一个装饰器函数,用于将一个函数的返回值按指定大小分割成多个块
	def decorator(func: Callable) -> Callable:
		# 定义一个包装函数,用于调用被装饰的函数,并将返回值按指定大小分割成多个块
		def wrapper(*args, **kwargs) -> Generator:  # noqa: ANN002, ANN003
			# 调用被装饰的函数,并将返回值赋给result
			result = func(*args, **kwargs)
			# 遍历result,将result按指定大小分割成多个块,并逐个返回
			for i in range(0, len(result), chunk_size):
				yield result[i : i + chunk_size]

		return wrapper

	return decorator


def lazy_property(func: Callable) -> ...:
	# 定义一个属性名,用于存储函数的返回值
	attr_name = "_lazy_" + func.__name__

	# 定义一个装饰器,用于将函数转换为属性
	@property
	@wraps(func)
	def wrapper(self) -> object:  # noqa: ANN001
		# 如果属性不存在,则调用函数并将返回值存储为属性
		if not hasattr(self, attr_name):
			setattr(self, attr_name, func(self))
		# 返回属性值
		return getattr(self, attr_name)

	# 返回装饰后的函数
	return wrapper
