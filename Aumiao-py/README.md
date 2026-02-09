# Aumiao

一个为编程猫社区开发的 API 收集项目和工具集合，旨在赋能脚本开发并提升社区管理效率。

A powerful API collection project and toolset for CodeMao community development, empowering script development and enhancing community management efficiency.

## 主要功能 | Main Features

### 账户与认证 | Account & Authentication

- **多方式登录**：支持 password（三种方法）与 cookie 登录  
  **Multiple Login Methods**: Support for password (both old and new formats) and cookie login
- **状态查询**：检查禁言状态和社区公约签署情况  
  **Status Query**: Check mute status and community convention signing status
- **身份切换**：支持 average、edu、judgement 三种身份模式切换  
  **Identity Switching**: Support switching between average, edu, and judgement identity modes
- **教育账号登录**：专用教育账号登录接口，支持密码重置  
  **Edu Account Login**: Dedicated educational account login interface with password reset support

### 消息管理 | Message Management

- **一键清理**：支持一键清除邮箱未读消息  
  **One-click Cleanup**: Clear all unread messages in mailbox with one click
- **多端清理**：支持 web 端和 nemo 客户端消息清理  
  **Multi-platform Cleanup**: Support message cleanup for both web and nemo client
- **分页处理**：智能分页处理大量未读消息，避免请求超时  
  **Pagination**: Smart pagination for large volumes of unread messages to prevent request timeout
- **类型过滤**：按消息类型（点赞、评论、系统通知）分别处理  
  **Type Filtering**: Process messages by type (likes, comments, system notifications)
- **状态验证**：实时验证消息清理状态，确保彻底清除  
  **Status Verification**: Real-time verification of message cleanup status to ensure complete removal

### 内容管理 | Content Management

- **评论管理**：基于关键词和用户 ID 删除作品/帖子评论，自动监测并删除刷屏评论  
  **Comment Management**: Delete work/post comments based on keywords and user IDs, automatically monitor and remove spam comments
    - **策略模式检测**：使用策略模式检测广告、黑名单、重复评论  
      **Strategy Pattern Detection**: Use strategy pattern to detect ads, blacklisted users, and duplicate comments
    - **批量删除确认**：删除前显示检测结果，支持选择性批量删除  
      **Batch Deletion Confirmation**: Show detection results before deletion, support selective batch deletion
    - **多维分析**：评论内容、用户行为、时间频率多维度分析  
      **Multi-dimensional Analysis**: Analyze comment content, user behavior, and time frequency
- **智能回复**：支持关键词回复和随机回复双模式，支持表情包和多样化回复内容  
  **Smart Reply**: Support keyword-based reply and random reply modes, includes emoji support and diverse reply content, built-in work analysis commands for Bot usage
    - **动态格式化**：回复内容支持动态变量替换（用户名、作品名等）  
      **Dynamic Formatting**: Reply content supports dynamic variable replacement (username, work name, etc.)
    - **CDN链接保护**：自动保护回复中的CDN链接，防止被平台过滤  
      **CDN Link Protection**: Automatically protect CDN links in replies to prevent platform filtering
    - **多类型通知处理**：支持作品评论、帖子回复、工作室讨论等多种通知类型  
      **Multi-type Notification**: Support multiple notification types including work comments, post replies, studio discussions
- **内容置顶**：通过修改工作室和小说信息实现内容常驻首页  
  **Content Pinning**: Keep content on homepage by modifying studio and novel information
    - **定时更新**：支持定时更新工作室详情，保持新鲜度  
      **Scheduled Updates**: Support scheduled updates of studio details to maintain freshness
    - **自动发布**：定时自动发布小说章节，保持内容活跃  
      **Auto Publishing**: Automatically publish novel chapters on schedule to keep content active

### 作品处理 | Work Processing

- **作品反编译**：支持 KITTEN N、KITTEN、NEMO、COCO 格式，自动识别文件类型并下载资源文件，生成可编辑的源码文件  
  **Work Decompilation**: Support for KITTEN N, KITTEN, NEMO, COCO formats, automatically identify file types and download resource files, generate editable source code files
- **作品解析与编辑**：解析 Kitten N 和 Kitten4 作品文件，支持添加角色、变量等编辑操作，统计作品积木使用情况  
  **Work Analysis & Editing**: Parse Kitten N and Kitten4 work files, support editing operations like adding characters and variables, count work block usage

### 数据与文件操作 | Data & File Operations

- **云数据管理**：支持云列表和云变量的调取、修改和创建，提供交互式界面  
  **Cloud Data Management**: Support for querying, modifying, and creating cloud lists and cloud variables with interactive interface
- **文件上传**：支持 codemao、codegame、pgaot 平台的文件上传，支持批量操作和历史查看  
  **File Upload**: Support file upload to codemao, codegame, pgaot platforms, supports batch operations and history viewing
    - **智能文件检测**：自动检测文件类型和大小，跳过超限文件  
      **Smart File Detection**: Automatically detect file type and size, skip oversized files
    - **目录递归上传**：支持整个目录递归上传，保持目录结构  
      **Directory Recursive Upload**: Support recursive upload of entire directories while preserving structure
    - **上传历史管理**：记录上传历史，支持链接有效性验证  
      **Upload History**: Record upload history with link validity verification
    - **统一上传接口**：抽象上传器协议，支持多种上传方法切换  
      **Unified Upload Interface**: Abstract uploader protocol supporting multiple upload methods
- **分享功能**：生成 NEMO 作品分享喵口令  
  **Sharing Function**: Generate sharing codes for NEMO works
    - **作品类型检测**：自动检测作品类型，仅NEMO作品可生成喵口令  
      **Work Type Detection**: Automatically detect work type, only NEMO works can generate sharing codes
    - **URL解析**：解析作品BCM链接，生成带token的喵口令  
      **URL Parsing**: Parse work BCM links to generate sharing codes with tokens

### 内容获取 | Content Retrieval

- **小说下载**：下载图书馆小说并自动转换 HTML 为 TXT 格式  
  **Novel Download**: Download library novels and automatically convert HTML to TXT format
    - **章节批量下载**：自动下载小说所有章节，保持章节顺序  
      **Chapter Batch Download**: Automatically download all novel chapters while maintaining order
    - **元数据保存**：保存小说作者、简介、字数等元数据  
      **Metadata Preservation**: Save novel metadata including author, introduction, word count
    - **格式转换**：HTML到TXT智能转换，合并空行优化阅读体验  
      **Format Conversion**: Smart HTML to TXT conversion with empty line merging for better reading
- **数据分析**：分析社区发言活跃用户，作品在线人数排行榜，获取最热作品  
  **Data Analysis**: Analyze active community users, filter posts by time, obtain follower statistics
    - **多源数据聚合**：从多个数据源聚合作品信息  
      **Multi-source Aggregation**: Aggregate work information from multiple data sources
    - **在线人数监测**：实时监测作品在线用户数  
      **Online User Monitoring**: Real-time monitoring of online users for works
    - **用户评论统计**：分析用户评论行为，按阈值筛选活跃用户  
      **User Comment Statistics**: Analyze user comment behavior, filter active users by threshold
    - **粉丝数据分析**：获取粉丝获赞数、作品数等统计数据  
      **Follower Data Analysis**: Get follower statistics including likes received, work count, etc.

### AI 功能 | AI Features

- **AI 调用**：支持 KN 编辑器 AI 调用，包含流式调用和交互式界面  
  **AI Calling**: Support KN editor AI calling, includes streaming calls and interactive interface
- **多 Token 轮询**：优化 AI 服务使用体验  
  **Multi-Token Polling**: Optimize AI service usage experience

### EDU 用户功能 | EDU User Features

#### 账户管理 | Account Management

- **批量账户操作**：支持 EDU 账户的批量生成和删除  
  **Batch Account Operations**: Support batch generation and deletion of EDU accounts
    - **班级管理**：自动创建班级，按班级容量分配学生  
      **Class Management**: Automatically create classes and allocate students by class capacity
    - **名称生成器**：智能生成班级和学生名称  
      **Name Generator**: Intelligently generate class and student names
    - **容量优化**：智能计算班级数量，最大化利用容量  
      **Capacity Optimization**: Intelligently calculate number of classes to maximize capacity usage
- **凭证管理**：生成 token 或 password 配置文件  
  **Credential Management**: Generate token or password configuration files
    - **格式适配**：自动适配不同格式（仅token或账号:密码）  
      **Format Adaptation**: Automatically adapt to different formats (token only or account:password)
    - **登录验证**：生成token时自动登录验证有效性  
      **Login Verification**: Automatically login to verify token validity during generation

#### 批量操作 | Batch Operations

- **批量举报**：针对作品进行批量举报操作  
  **Batch Reporting**: Perform batch reporting operations for works
    - **账号轮换**：自动切换账号避免单账号举报次数过多  
      **Account Rotation**: Automatically rotate accounts to avoid excessive reports per account
    - **频率控制**：智能延迟控制举报频率  
      **Frequency Control**: Intelligent delay control for report frequency
    - **失败处理**：自动处理失效账号，继续使用可用账号  
      **Failure Handling**: Automatically handle failed accounts and continue with available ones
- **批量评论**：支持回帖、工作室讨论区和作品评论的批量创建  
  **Batch Commenting**: Support batch creation of replies, studio discussions, and work comments
    - **多类型支持**：支持作品、工作室、帖子三种来源类型  
      **Multi-type Support**: Support three source types: work, studio, post
    - **重复次数控制**：支持单个账号多次评论  
      **Repeat Control**: Support multiple comments from single account
    - **内容统一管理**：统一管理评论内容格式  
      **Content Management**: Unified management of comment content format
- **批量点赞收藏**：批量点赞作品和收藏小说  
  **Batch Like & Collect**: Batch like works and collect novels
    - **用户作品遍历**：自动获取用户所有作品进行批量操作  
      **User Works Traversal**: Automatically get all user works for batch operations
    - **关注联动**：点赞时自动关注作者  
      **Follow Linkage**: Automatically follow author when liking works

### 风纪委员功能 | Moderator Features

#### 举报处理 | Report Handling

- **全类型支持**：处理 work、discussion、post、comment 所有举报类型  
  **Full Type Support**: Handle all report types including work, discussion, post, comment
    - **类型注册表**：统一管理所有举报类型配置  
      **Type Registry**: Unified management of all report type configurations
    - **字段映射**：每种类型有独立的字段映射关系  
      **Field Mapping**: Each type has independent field mapping relationships
    - **处理动作自定义**：不同类型支持不同的处理动作  
      **Action Customization**: Different types support different processing actions
- **批量处理**：一键处理全部待处理项  
  **Batch Processing**: Process all pending items with one click
    - **一键全部通过**：一键通过所有待处理举报  
      **One-click Pass All**: Pass all pending reports with one click
    - **智能分组**：自动识别相同内容或相同ID的批量举报  
      **Smart Grouping**: Automatically identify batch reports with same content or same ID
    - **历史动作复用**：对相同违规项自动复用历史处理动作  
      **History Action Reuse**: Automatically reuse historical processing actions for same violations
- **智能分块**：支持分块处理和详情查看  
  **Smart Chunking**: Support chunked processing and detail viewing
    - **管道处理模式**：使用管道模式组织处理流程  
      **Pipeline Processing**: Use pipeline pattern to organize processing flow
    - **官方账号识别**：自动识别官方账号内容并特殊处理  
      **Official Account Recognition**: Automatically recognize official account content for special handling
    - **详情格式化显示**：按举报类型格式化显示详情信息  
      **Formatted Detail Display**: Format display details according to report type

#### 违规检测 | Violation Detection

- **自动检测**：识别评论和帖子刷屏行为  
  **Auto Detection**: Identify comment and post spamming behaviors
    - **阈值配置**：可配置刷屏检测阈值  
      **Threshold Configuration**: Configurable spamming detection threshold
    - **内容相似度分析**：分析评论内容相似度  
      **Content Similarity Analysis**: Analyze comment content similarity
    - **用户行为分析**：分析用户评论频率和模式  
      **User Behavior Analysis**: Analyze user comment frequency and patterns
- **关键词侦测**：自动检测预设违规关键词  
  **Keyword Detection**: Automatically detect preset violation keywords
    - **多关键词支持**：支持广告词、敏感词等多类关键词  
      **Multi-keyword Support**: Support multiple keyword categories including ads and sensitive words
    - **内容忽略**：自动忽略置顶评论  
      **Content Ignoring**: Automatically ignore pinned comments
    - **层级检测**：同时检测主评论和回复评论  
      **Hierarchical Detection**: Detect both main comments and reply comments
- **一键举报**：自动举报所有检测到的违规内容  
  **One-click Reporting**: Automatically report all detected violation content
    - **多账号自动切换**：使用学生账号自动切换进行举报  
      **Multi-account Auto-switch**: Use student accounts with automatic switching for reporting
    - **账号使用计数**：跟踪每个账号的使用次数，自动切换  
      **Account Usage Counting**: Track usage count per account, auto-switch when limit reached
    - **失败重试**：失败时自动使用备用账号重试  
      **Failure Retry**: Automatically retry with backup accounts on failure

#### 历史应用 | History Application

- **批量应用**：支持对同一违规项批量应用历史操作  
  **Batch Application**: Support batch application of historical operations for same violation
    - **分组键识别**：基于内容和类型识别分组键  
      **Group Key Identification**: Identify group keys based on content and type
    - **动作持久化**：保存批量处理动作供后续块使用  
      **Action Persistence**: Save batch processing actions for subsequent chunks
    - **跨会话保持**：处理动作在同一会话中保持有效  
      **Cross-session Persistence**: Processing actions remain valid within same session
- **操作复用**：自动参考之前的处理决策  
  **Operation Reuse**: Automatically reference previous processing decisions
    - **决策缓存**：缓存处理决策提高效率  
      **Decision Caching**: Cache processing decisions to improve efficiency
    - **上下文感知**：根据上下文智能选择处理动作  
      **Context Awareness**: Intelligently select processing actions based on context

## 快速开始 | Quick Start

### 环境要求 | Requirements

- Python 3.13 或更高版本 | Python 3.13 or higher

### 安装方式 | Installation Methods

#### 通过 PyPI 安装（推荐）| Via PyPI (Recommended)

```bash
# 安装最新版本
pip install aumiao

# 或安装特定版本
pip install aumiao==2.7.0
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

# 初始化基础设施协调器和服务管理器
coordinator = base.InfrastructureCoordinator()
manager = services.ServiceManager()

# 登录认证
coordinator.auth_manager.login(
    identity="identity",  # 用户身份标识(用户名/邮箱/手机号)
    password="password",  # 登录密码
    prefer_method="password_v2"  # 推荐认证方式: password_v2 或 password_v1
)

# 获取社区消息(Nemo 消息系统)
coordinator.community_obtain.fetch_nemo_messages()

# 取消点赞操作(可用于帖子、回复等)
coordinator.forum_motion.execute_toggle_like(
    action="unlike",  # 操作类型: 'like' 点赞 / 'unlike' 取消点赞
    item_id=123456,  # 目标项目ID(帖子ID、回复ID等)
    item_type="REPLY"  # 项目类型: 'REPLY' 回复 / 'COMMENT' 评论
)

# 处理工作室加入申请
coordinator.shop_motion.execute_review_join_application(
    workshop_id=123456,  # 工作室ID
    status="UNACCEPTED",  # 审核状态: 'ACCEPTED' 通过 / 'UNACCEPTED' 拒绝
    user_id=123456  # 申请用户ID
)

# 生成喵码(用于社区分享)
manager.community.generate_miao_code(
    work_id=123456  # 作品ID
)

# 标记通知为已读
manager.community.mark_notifications_as_read(
    method="nemo"  # 通知系统类型: 'nemo' Nemo系统通知
)

# 处理回复(可筛选有效回复类型)
manager.reply.process_replies(
    valid_reply_types=None  # 有效回复类型列表, None表示处理所有类型
)

# 文件上传功能
manager.file_upload.upload_file(
    file_path="path",  # 本地文件路径
    save_path="aumiao",  # 云端保存路径
    method="codemao"  # 上传方式: 'codemao' 编程猫云存储
)

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
