"""服务类:认证管理、文件上传、高级服务"""

from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from src.core.base import MAX_SIZE_BYTES, ClassUnion, acquire, data, decorator, tool
from src.core.manage import Motion
from src.core.retrieve import Obtain
from src.utils.acquire import HTTPSTATUS


@decorator.singleton
class FileUploader(ClassUnion):
	def __init__(self) -> None:
		super().__init__()

	def upload_file(
		self,
		method: Literal["pgaot", "codemao", "codegame"],
		file_path: Path,
		save_path: str = "aumiao",
		*,
		recursive: bool = True,
	) -> dict[str, str | None] | str | None:
		"""
		上传文件或文件夹
		Args:
			method: 上传方法 ("pgaot", "codemao" 或 "codegame")
			file_path: 要上传的文件或文件夹路径
			save_path: 保存路径 (默认为 "aumiao")
			recursive: 是否递归上传子文件夹中的文件 (默认为 True)
		Returns:
			- 如果是单个文件: 返回上传后的URL或None
			- 如果是文件夹: 返回字典 {文件路径: 上传URL或None}
		"""
		uploader = acquire.FileUploader()
		if file_path.is_file():
			return self._handle_file_upload(file_path=file_path, save_path=save_path, method=method, uploader=uploader)
		if file_path.is_dir():
			return self._handle_directory_upload(dir_path=file_path, save_path=save_path, method=method, uploader=uploader, recursive=recursive)
		return None

	def _handle_file_upload(self, file_path: Path, save_path: str, method: Literal["pgaot", "codemao", "codegame"], uploader: acquire.FileUploader) -> str | None:
		"""处理单个文件的上传流程"""
		file_size = file_path.stat().st_size
		if file_size > MAX_SIZE_BYTES:
			size_mb = file_size / 1024 / 1024
			print(f"警告: 文件 {file_path.name} 大小 {size_mb:.2f}MB 超过 15MB 限制,跳过上传")
			return None
		# 使用重构后的统一上传接口
		url = uploader.upload(file_path=file_path, method=method, save_path=save_path)
		file_size_human = self._tool.DataConverter().bytes_to_human(file_size)
		history = data.UploadHistory(file_name=file_path.name, file_size=file_size_human, method=method, save_url=url, upload_time=self._tool.TimeUtils().current_timestamp())
		self._upload_history.data.history.append(history)
		self._upload_history.save()
		return url

	def _handle_directory_upload(
		self, dir_path: Path, save_path: str, method: Literal["pgaot", "codemao", "codegame"], uploader: acquire.FileUploader, *, recursive: bool
	) -> dict[str, str | None]:
		"""处理整个文件夹的上传流程"""
		results = {}
		pattern = "**/*" if recursive else "*"
		for child_file in dir_path.rglob(pattern):
			if child_file.is_file():
				try:
					# 检查文件大小
					file_size = child_file.stat().st_size
					if file_size > MAX_SIZE_BYTES:
						size_mb = file_size / 1024 / 1024
						print(f"警告: 文件 {child_file.name} 大小 {size_mb:.2f}MB 超过 15MB 限制,跳过上传")
						results[str(child_file)] = None
						continue
					# 计算保存路径
					relative_path = child_file.relative_to(dir_path)
					child_save_path = str(Path(save_path) / relative_path.parent)
					# 使用重构后的统一上传接口
					url = uploader.upload(file_path=child_file, method=method, save_path=child_save_path)
					# 记录上传历史
					file_size_human = self._tool.DataConverter().bytes_to_human(file_size)
					history = data.UploadHistory(
						file_name=str(relative_path), file_size=file_size_human, method=method, save_url=url, upload_time=self._tool.TimeUtils().current_timestamp()
					)
					self._upload_history.data.history.append(history)
					results[str(child_file)] = url
				except Exception as e:
					results[str(child_file)] = None
					print(f"上传 {child_file} 失败: {e}")
		# 保存历史记录
		self._upload_history.save()
		return results

	def print_upload_history(self, limit: int = 10, *, reverse: bool = True) -> None:
		"""
		打印上传历史记录(支持分页、详细查看和链接验证)
		Args:
			limit: 每页显示记录数(默认10条)
			reverse: 是否按时间倒序显示(最新的在前)
		"""
		history_list = self._upload_history.data.history
		if not history_list:
			print("暂无上传历史记录")
			return
		# 排序历史记录
		sorted_history = sorted(
			history_list,
			key=lambda x: x.upload_time,
			reverse=reverse,
		)
		total_records = len(sorted_history)
		max_page = (total_records + limit - 1) // limit
		page = 1
		while True:
			# 获取当前页数据
			start = (page - 1) * limit
			end = min(start + limit, total_records)
			page_data = sorted_history[start:end]
			# 打印当前页
			self._print_current_page(page, max_page, total_records, start, end, page_data)
			# 处理用户操作
			action = input("请输入操作: ").strip().lower()
			if action == "q":
				break
			if action == "n" and page < max_page:
				page += 1
			elif action == "p" and page > 1:
				page -= 1
			elif action.startswith("d"):
				try:
					record_id = int(action[1:])
					if 1 <= record_id <= total_records:
						self._show_record_detail(sorted_history[record_id - 1])
					else:
						print(f"错误:ID超出范围(1-{total_records})")
				except ValueError:
					print("错误:无效的ID格式(正确格式:d1,d2等)")
			else:
				print("错误:无效操作或超出页码范围")

	def _print_current_page(self, page: int, max_page: int, total_records: int, start: int, end: int, page_data: list) -> None:
		"""打印当前分页的所有内容"""
		print(f"\n上传历史记录(第{page}/{max_page}页):")
		print(f"{'ID':<3} | {'文件名':<25} | {'时间':<19} | {'URL(类型)'}")
		print("-" * 85)
		for i, record in enumerate(page_data, start + 1):
			upload_time = record.upload_time
			if isinstance(upload_time, (int, float)):
				upload_time = self._tool.TimeUtils().format_timestamp(upload_time)
			formatted_time = str(upload_time)[:19]
			file_name = record.file_name.replace("\\", "/")[:25]
			url = record.save_url.replace("\\", "/")
			url_type = "[other]"
			simplified_url = url[:30] + "..." if len(url) > 30 else url  # noqa: PLR2004
			parsed_url = urlparse(url)
			host = parsed_url.hostname
			if host == "static.codemao.cn":
				cn_index = url.find(".cn")
				simplified_url = url[cn_index + 3 :].split("?")[0] if cn_index != -1 else url.split("/")[-1].split("?")[0]
				url_type = "[static]"
			elif host and (host == "cdn-community.bcmcdn.com" or host.endswith(".cdn-community.bcmcdn.com")):  # cSpell: ignore bcmcdn
				com_index = url.find(".com")
				simplified_url = url[com_index + 4 :].split("?")[0] if com_index != -1 else url.split("/")[-1].split("?")[0]
				url_type = "[cdn]"
			print(f"{i:<3} | {file_name:<25} | {formatted_time:<19} | {url_type}{simplified_url}")
		print(f"共 {total_records} 条记录 | 当前显示: {start + 1}-{end}")
		print("\n操作选项:")
		print("n:下一页 p:上一页 d[ID]:查看详情(含链接验证) q:退出")

	def _show_record_detail(self, record: data.UploadHistory) -> None:
		"""显示单条记录的详细信息并验证链接"""
		# 格式化上传时间
		upload_time = record.upload_time
		if isinstance(upload_time, (int, float)):
			upload_time = self._tool.TimeUtils().format_timestamp(upload_time)
		print("\n文件上传详情:")
		print("-" * 60)
		print(f"文件名: {record.file_name}")
		print(f"文件大小: {record.file_size}")
		print(f"上传方式: {record.method}")
		print(f"上传时间: {upload_time}")
		print(f"完整URL: {record.save_url}")
		# 验证链接有效性
		is_valid = self._validate_url(record.save_url)
		status = "有效" if is_valid else "无效"
		print(f"链接状态: {status}")
		if record.save_url.startswith("http"):
			print("\n提示:复制上方URL到浏览器可直接访问或下载")
		print("-" * 60)
		input("按Enter键返回...")

	def _validate_url(self, url: str) -> bool:
		"""
		验证URL链接是否有效
		先使用HEAD请求检查,若返回无效状态则尝试GET请求验证内容
		"""
		response = self._client.send_request(endpoint=url, method="HEAD", timeout=5)
		if response.status_code == HTTPSTATUS.OK.value:
			content_length = response.headers.get("Content-Length")
			if content_length and int(content_length) > 0:
				return True
		response = self._client.send_request(endpoint=url, method="GET", stream=True, timeout=5)
		if response.status_code != HTTPSTATUS.OK.value:
			return False
		return bool(next(response.iter_content(chunk_size=1)))


@decorator.singleton
class MillenniumEntanglement(ClassUnion):
	def __init__(self) -> None:
		super().__init__()

	def batch_like_content(self, user_id: int | None, content_type: Literal["work", "novel"], custom_list: list | None = None) -> None:
		"""批量点赞用户作品或小说"""
		if custom_list:
			target_list = custom_list
		elif content_type == "work":
			target_list = list(self._user_obtain.fetch_user_works_web_gen(str(user_id), limit=None))
		elif content_type == "novel":
			target_list = self._novel_obtain.fetch_my_novels()
		else:
			msg = f"不支持的内容类型 {content_type}"
			raise TypeError(msg)

		def action() -> None:
			if content_type == "work":
				Motion().like_all_work(user_id=str(user_id), works_list=target_list)
			else:
				Motion().like_my_novel(novel_list=target_list)

		Obtain().process_edu_accounts(limit=None, action=action())

	def upgrade_to_teacher(self, real_name: str) -> None:
		"""升级账号为教师身份"""
		generator = tool.EduDataGenerator()
		self._edu_motion.execute_upgrade_to_teacher(
			user_id=int(self._data.ACCOUNT_DATA.id),
			real_name=real_name,
			grade=["2", "3", "4"],
			school_id=11000161,
			school_name="北京景山学校",
			school_type=1,
			country_id="156",
			province_id=1,
			city_id=1,
			district_id=1,
			teacher_card_number=generator.generate_teacher_certificate_number(),
		)

	def manage_edu_accounts(self, action_type: Literal["create", "delete", "token"], limit: int | None = 100) -> None:
		"""批量管理教育账号"""

		def _create_students(student_limit: int) -> None:
			"""创建学生账号"""
			class_capacity = 95
			class_count = (student_limit + class_capacity - 1) // class_capacity
			generator = tool.EduDataGenerator()
			class_names = generator.generate_class_names(num_classes=class_count, add_specialty=True)
			student_names = generator.generate_student_names(num_students=student_limit)
			for class_idx in range(class_count):
				class_id = self._edu_motion.create_class(name=class_names[class_idx])["id"]
				print(f"创建班级 {class_id}")
				start = class_idx * class_capacity
				end = start + class_capacity
				batch_names = student_names[start:end]
				self._edu_motion.add_students_to_class(name=batch_names, class_id=class_id)
				print("添加学生ing")

		def _delete_students(delete_limit: int | None) -> None:
			"""删除学生账号"""
			students = self._edu_obtain.fetch_class_students_gen(limit=delete_limit)
			for student in students:
				self._edu_motion.delete_student_from_class(stu_id=student["id"])

		def _create_token(token_limit: int | None) -> list[str]:
			"""生成账号token"""
			accounts = Obtain().switch_edu_account(limit=token_limit, return_method="list")
			token_list = []
			for identity, pass_key in accounts:
				response = self._community_login.authenticate_with_password(identity=identity, password=pass_key, status="edu")
				token = response["auth"]["token"]
				token_list.append(token)
				self._file.file_write(path=data.TOKEN_DIR, content=f"{token}\n", method="a")
			return token_list

		if action_type == "delete":
			_delete_students(limit)
		elif action_type == "create":
			actual_limit = limit or 100
			_create_students(actual_limit)
		elif action_type == "token":
			_create_token(token_limit=limit)

	def batch_report_work(self, work_id: int) -> None:
		"""批量举报作品"""
		hidden_border = 10
		Obtain().process_edu_accounts(limit=hidden_border, action=lambda: self._work_motion.execute_report_work(describe="", reason="违法违规", work_id=work_id))

	def create_comment(self, target_id: int, content: str, source_type: Literal["work", "shop", "post"]) -> None:
		"""创建评论/回复"""
		if source_type == "post":
			self._forum_motion.create_post_reply(post_id=target_id, content=content)
		elif source_type == "shop":
			self._shop_motion.create_comment(workshop_id=target_id, content=content, rich_content=content)
		elif source_type == "work":
			self._work_motion.create_work_comment(work_id=target_id, comment=content)
		else:
			msg = f"不支持的来源类型 {source_type}"
			raise TypeError(msg)
