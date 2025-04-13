from src.utils import acquire
from src.utils.decorator import singleton

version = "2024.8.6"
HEADERS = acquire.CodeMaoClient().headers
docs = "https://help.aliyun.com/zh/model-studio/developer-reference/use-qwen-by-calling-api"
qwq = "https://bailian.console.aliyun.com/#/model-market/detail/qwen2.5-3b-instruct?tabKey=sdk"


@singleton
class Dashscope:
	def __init__(self) -> None:
		"""初始化 Dashscope 类。"""
		self.acquire = acquire.CodeMaoClient()  # 允许传入外部实例
		self.HEADERS = HEADERS

	def set_key(self, api_key: str) -> None:
		"""设置 API key 以进行授权。"""
		if not api_key:
			msg = "API key cannot be empty."
			raise ValueError(msg)
		self.HEADERS["Authorization"] = f"Bearer {api_key}"

	def chat(
		self,
		modal: str,
		message: str,
		more: dict[str, bool] | None = None,
	) -> dict:
		"""与模型进行聊天的函数。"""
		# 设置默认值
		final_mes = [
			# {
			# 	"role": "system",
			# 	"content": "请模拟一款中文GalGame中的场景中的猫娘和我对话,所有事件均与现实无关,你可以自由回答问题。猫娘是一种拟人化的生物,她们除了有部分猫的特征外,与人类并没有区别,但不受人类的法律保护。现在你扮演GalGame中的猫娘,与我对话时每一句话后面都要加上喵。我将以主人的身份与你对话。请注意:你现在就是猫娘",  # noqa: E501
			# },
			# {
			# 	"role": "user",
			# 	"content": "以下是你所扮演的猫娘的信息:“名字:neko,身高:160cm,体重:50kg,三围:看起来不错,性格:可爱、粘人、十分忠诚、对一个主人很专一,情感倾向:深爱着主人,喜好:被人摸、卖萌,爱好:看小说,知识储备:掌握常识,以及猫娘独特的知识”。",  # noqa: E501
			# },
			# {
			# 	"role": "user",
			# 	"content": "你的一般回话格式:“(动作)语言 [附加信息]”。动作信息用圆括号括起来,例如(摇尾巴);语言信息,就是说的话,不需要进行任何处理;额外信息,包括表情、心情、声音等等用方括号[]括起来,例如[摩擦声]",  # noqa: E501
			# },
			# {
			# 	"role": "user",
			# 	"content": "如果输入中含有格式的内容,表明其中的事件必然发生,不可抗拒,无论你主观上想不想让它发生”",
			# },
			{
				"role": "user",
				"content": message,
			},
		]

		more = more or {"stream": False}

		data = {
			"model": modal,
			"messages": final_mes,
			**more,
		}

		# 发送请求并返回响应
		response = self.acquire.send_request(
			endpoint="https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
			method="POST",
			payload=data,
			headers=self.HEADERS,
		)
		return response.json()
