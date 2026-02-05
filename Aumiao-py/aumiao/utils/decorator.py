from collections.abc import Callable, Generator
from functools import lru_cache, wraps


def singleton(cls):  # noqa: ANN001, ANN201
	instances = {}

	@wraps(cls)
	def wrapper(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
		if cls not in instances:
			instances[cls] = cls(*args, **kwargs)
		return instances[cls]

	wrapper.__dict__.update(cls.__dict__)
	return wrapper


def skip_on_error(func):  # noqa: ANN001, ANN201
	@wraps(func)
	def wrapper(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
		try:
			return func(*args, **kwargs)
		except Exception as e:
			print(f"Error occurred: {e}. Skipping this iteration.")
			return None  # 继续执行下一个循环

	return wrapper


def generator(chunk_size: int = 1000) -> Callable:
	# 定义一个装饰器函数, 用于将一个函数的返回值按指定大小分割成多个块
	def decorator(func: Callable) -> Callable:
		# 定义一个包装函数, 用于调用被装饰的函数, 并将返回值按指定大小分割成多个块
		def wrapper(*args, **kwargs) -> Generator:  # noqa: ANN002, ANN003
			# 调用被装饰的函数, 并将返回值赋给 result
			result = func(*args, **kwargs)
			# 遍历 result, 将 result 按指定大小分割成多个块, 并逐个返回
			for i in range(0, len(result), chunk_size):
				yield result[i : i + chunk_size]

		return wrapper

	return decorator


def lru_cache_with_reset(maxsize: int = 128, max_calls: int = 3, *, typed: bool = False) -> Callable:
	def decorator(func: Callable) -> ...:
		# 使用 lru_cache 缓存结果
		cached_func = lru_cache(maxsize=maxsize, typed=typed)(func)
		# 使用字典记录调用次数,键为参数元组
		call_counts = {}

		@wraps(func)
		def wrapper(*args: ..., **kwargs: ...) -> ...:
			# 生成缓存键
			# 注意:functools.lru_cache 内部使用的方式更复杂
			# 我们简化处理,只基于 args 和排序后的 kwargs
			key = (
				args,
				tuple(sorted(kwargs.items())) if kwargs else (),
			)
			# 获取当前计数
			current_count = call_counts.get(key, 0) + 1
			call_counts[key] = current_count
			# 检查是否需要重置
			if current_count > max_calls:
				# 重置该键的计数
				call_counts[key] = 1
				# 清除整个缓存(简化处理)
				cached_func.cache_clear()
			# 调用缓存函数
			return cached_func(*args, **kwargs)

		return wrapper

	return decorator
