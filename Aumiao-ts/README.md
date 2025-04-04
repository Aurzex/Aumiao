# Aumiao-ts

## 这是什么

Aumiao-ts 是由**Nomen**开发的 Aumiao 子项目，用于支持 Node.js 并且使用更强大的界面控制

## 这和 Aumiao-py 有什么区别

Aumiao-ts 与 Aumiao-py 实现的功能不同

## 这和 Aumiao-js 有什么区别

Aumiao-ts 使用 TypeScript 进行编写，并且使用了更加现代化的统一命令框架和界面

## 常用指令

见 [commands.md](./docs/commands.md)

## FAQ

见 [faq.md](./docs/faq.md)

---

## 功能列表

- [x] 身份验证
  - [x] 单账号登录
    - [x] 本地凭据储存
    - [x] Auth
      - [x] 凭据登录
      - [x] Cookie 登录
      - [x] 环境登录
- [x] 信息获取
  - [x] 获取个人资料
- [x] 爬虫
  - [x] 论坛
    - [x] 爬取帖子
    - [x] 索引帖子
    - [x] 搜索帖子
    - [x] 归档帖子

## 如何使用

### 手动安装

1. 安装 Node.js 18 或以上从 [Nodejs.org](https://nodejs.org/)
2. 安装 Git
3. 确保 nodejs 安装成功: `node --version`
4. 克隆仓库: `git clone https://github.com/zybqw/Aumiao.git && cd ./Aumiao/Aumiao-ts`
5. 启动`node aumiao`

### 一句话指令

**需先安装 Node.js 和 Git**

CMD (Windows >= 10)

```bash
git clone https://github.com/zybqw/Aumiao.git && cd ./Aumiao/Aumiao-ts && node ./scripts/install.js && node aumiao.js
```

Windows PowerShell

```bash
git clone https://github.com/zybqw/Aumiao.git; cd .\Aumiao\Aumiao-ts; node .\scripts\install.js; node .\aumiao.js
```

## 如何更新

### 通常

使用以下指令进行更新

```bash
node aumiao update
```

### 出错了

如果尝试更新出错，可以删除整个本地仓库并且重新安装

## 文档

- [如何获得 Cookie](./docs/how-to-get-cookie.md)
- [如何使用环境登录](./docs/how-to-use-env-login.md)
- [常见问题一览](./docs/faq.md)

## TODO

1. 用户行为
