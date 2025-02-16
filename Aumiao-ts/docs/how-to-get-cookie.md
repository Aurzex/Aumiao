# 如何获取 Cookie

1. 登录至`shequ.codemao.cn`
2. 按下键盘上的`F12`或`FN + F12`或`CTRL + SHIFT + L`或`页面选项`打开网页开发者工具
3. 在网页开发者工具中找到应用程序标签页（默认名字为`Application`）
4. 在左侧的部分按顺序展开：存储 > Cookie > https://shequ.codemao.cn
5. 在右侧的储存列表中找到名称为 authorization 的一项
6. 确保其 domain 字段为`.codemao.cn`
7. 复制值，该值通常以 **ey**字母作为开头
8. 运行 login 命令，并且选择使用 cookie 登录
9. 输入 cookie，完成登录，如果输入正确，将会正确返回面板
