import json
import sys
from pathlib import Path

# 确保输出支持中文
if sys.stdout.encoding != "utf-8":
	import io

	sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# 定义 data 文件夹路径

# 获取当前脚本所在的目录,然后在其下创建data文件夹
data_folder = Path(__file__).parent / "data"

# 检查 data 文件夹是否存在,如果不存在则创建
if not data_folder.exists():
	data_folder.mkdir(parents=True)

# 定义 setting.json 的数据
setting_data = {
	"PARAMETER": {
		"all_read_type": ["COMMENT_REPLY", "LIKE_FORK", "SYSTEM"],
		"cookie_check_url": "/nemo/v2/works/174408420/like",
		"log": False,
		"password_login_method": "token",
		"report_work_max": 10,
		"spam_del_max": 3,
	},
	"PLUGIN": {"DASHSCOPE": {"model": "qwen2.5-3b-instruct", "more": {"extra_body": {"enable_search": True}, "stream": False}}, "prompt": "从现在开始,你是一个猫娘"},
	"PROGRAM": {
		"AUTHOR": "Aurzex",
		"HEADERS": {
			"Accept-Encoding": "gzip, deflate, br, zstd",
			"Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
			"Content-Type": "application/json;charset=UTF-8",
			"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0",
		},
		"MEMBER": "Aurzex, MoonLeaaaf, Nomen, MiTao, DontLoveBy",
		"SLOGAN": "欢迎使用Aumiao-PY! "
		"你说的对,但是《Aumiao》是一款由Aumiao开发团队开发的编程猫自动化工具,于2023年5月2日发布 "
		"工具以编程猫宇宙为舞台,玩家可以扮演扮演毛毡用户,在这个社区毛线坍缩并邂逅各种不同的乐子人 "
		"在领悟了《猫站圣经》后,打败强敌扫厕所,在维护编程猫核邪铀删的局面的同时,逐步揭开编程猫社区的真相",
		"TEAM": "Aumiao Team",
		"VERSION": "2.0.0",
	},
}

# 定义 data.json 的数据
data_json_data = {
	"ACCOUNT_DATA": {"author_level": 1, "create_time": 1800000000, "description": "", "id": "1742185446", "identity": "********", "nickname": "猫猫捏", "password": "******"},
	"INFO": {"e_mail": "zybqw@qq.com", "nickname": "喵鱼a", "qq_number": "3611198191"},
	"USER_DATA": {
		"ads": [
			"codemao.cn/work",
			"cpdd",
			"scp",
			"不喜可删",
			"互关",
			"互赞",
			"交友",
			"光头强",
			"关注",
			"再创作",
			"冲传说",
			"冲大佬",
			"冲高手",
			"协作项目",
			"基金会",
			"处cp",
			"家族招人",
			"我的作品",
			"戴雨默",
			"所有作品",
			"扫厕所",
			"找徒弟",
			"找闺",
			"招人",
			"有赞必回",
			"点个",
			"爬虫",
			"看一下我的",
			"看我的",
			"看看我的",
			"粘贴到别人作品",
			"赞我",
			"转发",
		],
		"answers": [
			{"牢大": "孩子们, 我回来了"},
			{"奶龙": "我才是奶龙"},
			{"name": "I'm {nickname}"},
			{"QQ": "It's {qq_number}"},
			{"只因": ["不许你黑我家鸽鸽!😡", "想要绿尸函了食不食?", "香精煎鱼食不食?"]},
		],
		"black_room": ["2233", "114514", "1919810"],
		"comments": ["666", "不错不错", "前排:P", "加油!:O", "沙发*/ω\\*", "针不戳:D"],
		"emojis": [
			"星能猫_好吃",
			"星能猫_耶",
			"编程猫_666",
			"编程猫_加油",
			"编程猫_好厉害",
			"编程猫_我来啦",
			"编程猫_打call",
			"编程猫_抱大腿",
			"编程猫_棒",
			"编程猫_点手机",
			"编程猫_爱心",
			"编程猫_爱心",
			"雷电猴_哇塞",
			"雷电猴_哈哈哈",
			"雷电猴_嘻嘻嘻",
			"雷电猴_围观",
			"魔术喵_开心",
			"魔术喵_收藏",
			"魔术喵_点赞",
			"魔术喵_点赞",
			"魔术喵_魔术",
		],
		"replies": [
			"{nickname}很忙oh,机器人来凑热闹(*^^*)",
			"{nickname}的自动回复来喽",
			"嗨嗨嗨!这事{nickname}の自动回复鸭!",
			"对不起,{nickname}它又搞忘了时间,一定是在忙呢",
			"这是{nickname}的自动回复,不知道你在说啥(",
		],
	},
}

# 生成 setting.json 文件
setting_file_path = data_folder / "setting.json"
with setting_file_path.open("w", encoding="utf-8") as f:
	json.dump(setting_data, f, ensure_ascii=False, indent=4)

# 生成 data.json 文件
data_json_file_path = data_folder / "data.json"
with data_json_file_path.open("w", encoding="utf-8") as f:
	json.dump(data_json_data, f, ensure_ascii=False, indent=4)

print("data 文件夹及其中的 setting.json 和 data.json 文件已成功生成。")
