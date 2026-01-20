# Aumiao

一个为编程猫社区开发的 API 收集项目和工具集合，旨在赋能脚本开发并提升社区管理效率。

A powerful API collection project and toolset for CodeMao community development, empowering script development and enhancing community management efficiency.

## 主要功能 | Main Features

### 用户功能 | User Features

#### 账户与认证 | Account & Authentication
- **多方式登录**：支持 password（新旧格式）与 cookie 登录  
  **Multiple Login Methods**: Support for password (both old and new formats) and cookie login
- **状态查询**：检查禁言状态和社区公约签署情况  
  **Status Query**: Check mute status and community convention signing status

#### 消息管理 | Message Management
- **一键清理**：支持一键清除邮箱未读消息  
  **One-click Cleanup**: Clear all unread messages in mailbox with one click

#### 内容管理 | Content Management
- **评论管理**：基于关键词和用户 ID 删除作品/帖子评论，自动监测并删除刷屏评论  
  **Comment Management**: Delete work/post comments based on keywords and user IDs, automatically monitor and remove spam comments
- **智能回复**：支持关键词回复和随机回复双模式，支持表情包和多样化回复内容，内置作品解析命令，可作为 Bot 使用  
  **Smart Reply**: Support keyword-based reply and random reply modes, includes emoji support and diverse reply content, built-in work analysis commands for Bot usage
- **内容置顶**：通过修改工作室和小说信息实现内容常驻首页  
  **Content Pinning**: Keep content on homepage by modifying studio and novel information

#### 作品处理 | Work Processing
- **作品反编译**：支持 KITTEN N、KITTEN、NEMO、COCO 格式，自动识别文件类型并下载资源文件，生成可编辑的源码文件  
  **Work Decompilation**: Support for KITTEN N, KITTEN, NEMO, COCO formats, automatically identify file types and download resource files, generate editable source code files
- **作品解析与编辑**：解析 Kitten N 和 Kitten4 作品文件，支持添加角色、变量等编辑操作，统计作品积木使用情况  
  **Work Analysis & Editing**: Parse Kitten N and Kitten4 work files, support editing operations like adding characters and variables, count work block usage

#### 数据与文件操作 | Data & File Operations
- **云数据管理**：支持云列表和云变量的调取、修改和创建，提供交互式界面  
  **Cloud Data Management**: Support for querying, modifying, and creating cloud lists and cloud variables with interactive interface
- **文件上传**：支持 codemao、codegame、pgaot 平台的文件上传，支持批量操作和历史查看  
  **File Upload**: Support file upload to codemao, codegame, pgaot platforms, supports batch operations and history viewing
- **分享功能**：生成 NEMO 作品分享喵口令  
  **Sharing Function**: Generate sharing codes for NEMO works

#### 内容获取 | Content Retrieval
- **小说下载**：下载图书馆小说并自动转换 HTML 为 TXT 格式  
  **Novel Download**: Download library novels and automatically convert HTML to TXT format
- **数据分析**：分析社区发言活跃用户，按时间筛选帖子，获取粉丝统计信息  
  **Data Analysis**: Analyze active community users, filter posts by time, obtain follower statistics

#### AI 功能 | AI Features
- **AI 调用**：支持 KN 编辑器 AI 调用，包含流式调用和交互式界面  
  **AI Calling**: Support KN editor AI calling, includes streaming calls and interactive interface
- **多 Token 轮询**：优化 AI 服务使用体验  
  **Multi-Token Polling**: Optimize AI service usage experience

### EDU 用户功能 | EDU User Features

#### 账户管理 | Account Management
- **批量账户操作**：支持 EDU 账户的批量生成和删除  
  **Batch Account Operations**: Support batch generation and deletion of EDU accounts
- **凭证管理**：生成 token 或 password 配置文件  
  **Credential Management**: Generate token or password configuration files

#### 批量操作 | Batch Operations
- **批量举报**：针对作品进行批量举报操作  
  **Batch Reporting**: Perform batch reporting operations for works
- **批量评论**：支持回帖、工作室讨论区和作品评论的批量创建  
  **Batch Commenting**: Support batch creation of replies, studio discussions, and work comments

### 风纪委员功能 | Moderator Features

#### 举报处理 | Report Handling
- **全类型支持**：处理 work、discussion、post、comment 所有举报类型  
  **Full Type Support**: Handle all report types including work, discussion, post, comment
- **批量处理**：一键处理全部待处理项  
  **Batch Processing**: Process all pending items with one click
- **智能分块**：支持分块处理和详情查看  
  **Smart Chunking**: Support chunked processing and detail viewing

#### 违规检测 | Violation Detection
- **自动检测**：识别评论和帖子刷屏行为  
  **Auto Detection**: Identify comment and post spamming behaviors
- **关键词侦测**：自动检测预设违规关键词  
  **Keyword Detection**: Automatically detect preset violation keywords
- **一键举报**：自动举报所有检测到的违规内容  
  **One-click Reporting**: Automatically report all detected violation content

#### 历史应用 | History Application
- **批量应用**：支持对同一违规项批量应用历史操作  
  **Batch Application**: Support batch application of historical operations for same violation
- **操作复用**：自动参考之前的处理决策  
  **Operation Reuse**: Automatically reference previous processing decisions

## 快速开始 | Quick Start

### 环境要求 | Requirements

- Python 3.13 或更高版本 | Python 3.13 or higher

### 安装方式 | Installation Methods

#### 通过 PyPI 安装（推荐）| Via PyPI (Recommended)

```bash
# 安装最新版本
pip install aumiao

# 或安装特定版本
pip install aumiao==2.6.0
```

#### 从源代码安装 | From Source

```bash
# 克隆项目 | Clone the repository
git clone https://github.com/aurzex/Aumiao.git
cd Aumiao/Aumiao-py

# 使用 uv 包管理器（推荐）| Using uv package manager (recommended)
pip install uv
uv sync

# 或使用传统方式 | Or using traditional method
pip install -r requirements.txt
```

### 配置文件 | Configuration Files

项目使用以下配置文件： | The project uses the following configuration files:

- `data.json` - 用户认证和数据配置文件 | User authentication and data configuration
- `setting.json` - 程序运行设置和选项 | Program runtime settings and options

### 二进制版本 | Binary Versions

从 [Release 页面](https://github.com/aurzex/Aumiao/releases) 下载预编译版本，无需配置即可直接运行。  
Download precompiled versions from the [Release page](https://github.com/aurzex/Aumiao/releases), ready to run without configuration.

## 开发者指南 | Developer Guide

### 核心模块结构
- **api/** - 编程猫社区 API 接口封装，涵盖社区大部分可用 API
- **core/** - 核心功能模块
  - **base/** - 基础 API 协调器，提供编程猫基础 API 调用
  - **retrieve/** - 数据获取功能
  - **process/** - 数据处理功能
  - **service/** - 高级服务封装，提供封装好的功能调用
- **utils/** - 实用工具和辅助函数

### 基本用法示例
```python
from aumiao import base, services

# 初始化基础协调器和服务管理器
coordinator = base.InfraCoordinator()
service = services.ServiceManager()

# 用户登录（支持多种账户类型）
coordinator.auth.login(
    identity="your_username",
    password="your_password",
    status="average"  # 账户类型: average/edu/judgement
)

# 使用基础功能
coordinator.community_obtain.fetch_random_nickname()
coordinator.user_motion.update_profile_cover(cover_url="Your_URL")

# 使用高级服务
service.reply.process_replies()  # 处理自动回复
service.community.download_novel(
    novel_id="Novel_ID",
    output_dir="PATH"
)  # 下载小说
```

### 设计特性
- **单例模式**：核心功能采用单例设计，优化资源使用
- **动态导入**：模块按需加载，提升启动速度
- **配置管理**：自动同步配置文件，无需手动保存
- **多账户支持**：支持普通用户、教育账户、风纪委员等多种账户类型
- **请求功能**：内置丰富的请求功能，支持分页信息获取、WebSockets、HTTP 和文件上传客户端
- **数据转换**：数据文件自动从 JSON 字典转换为 dataclass
- **错误处理**：完善的异常处理机制和日志记录

## 贡献指南 | Contribution Guidelines

我们欢迎所有形式的贡献。请遵循以下流程： | We welcome all forms of contributions. Please follow the process below:

1. **Fork 仓库**：点击右上角的 Fork 按钮 | **Fork Repository**: Click the Fork button in the upper right corner
2. **创建分支**：基于 `main` 分支创建功能分支 | **Create Branch**: Create a feature branch based on the `main` branch
3. **开发功能**：在分支上实现您的改进 | **Develop Feature**: Implement your improvements on the branch
4. **提交测试**：确保代码通过现有测试 | **Run Tests**: Ensure code passes existing tests
5. **发起 PR**：向主仓库提交 Pull Request | **Submit PR**: Submit a Pull Request to the main repository

请确保： | Please ensure:

- 代码风格与现有代码保持一致 | Code style is consistent with existing code
- 添加必要的文档和注释 | Add necessary documentation and comments
- 更新相关的测试用例 | Update relevant test cases


## 联系我们 | Contact Us

- **官方网站**：[https://aumiao.aurzex.top](https://aumiao.aurzex.top)  
  **Official Website**: [https://aumiao.aurzex.top](https://aumiao.aurzex.top)
- **问题反馈**：[GitHub Issues](https://github.com/aurzex/Aumiao/issues)  
  **Issue Reporting**: [GitHub Issues](https://github.com/aurzex/Aumiao/issues)
- **联系邮箱**：Aumiao@aurzex.top  
  **Contact Email**: Aumiao@aurzex.top
- **开发团队**：Aurzex, DontLoveby, Moonleeeaf, Nomen  
  **Development Team**: Aurzex, DontLoveby, Moonleeeaf, Nomen

## 许可证 | License

本项目采用 AGPL-3.0 开源协议。详细条款请参阅 [LICENSE](LICENSE) 文件。  
This project is licensed under the AGPL-3.0 license. See the [LICENSE](LICENSE) file for details.

---

感谢使用 Aumiao。如果本项目对您有帮助，请考虑在 GitHub 上为我们点亮星标。  
Thank you for using Aumiao. If this project helps you, please consider giving it a star on GitHub.
