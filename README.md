# Aumiao

[![Moe Counter](https://count.getloli.com/@aurzex?name=aurzex&theme=capoo-1&padding=7&offset=0&align=top&scale=1&pixelated=1&darkmode=auto)](https://count.getloli.com/)

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.13+](https://img.shields.io/badge/Python-3.13+-green.svg)](https://www.python.org/downloads/)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/Aurzex/Aumiao)

一个为编程猫社区开发的 API 收集项目和工具集合，旨在赋能脚本开发并提升社区管理效率。

A powerful API collection project and toolset for CodeMao community development, empowering script development and enhancing community management efficiency.

## 主要功能 | Main Features

### 社区管理 | Community Management

- **评论管理**：支持关键词过滤、黑名单批量清理作品和帖子评论  
  **Comment Management**: Keyword filtering, batch cleanup of work and post comments via blacklist
- **智能回复**：基于关键词的自动化回复系统  
  **Auto Reply**: Keyword-based automated reply system
- **消息处理**：一键清空邮箱红点、批量邮件处理  
  **Message Processing**: Clear inbox notifications with one click, batch email processing

### 内容审核 | Content Moderation

- **批量举报**：支持批量提交和审核举报  
  **Batch Reporting**: Batch submission and review of reports
- **违规检测**：自动识别广告内容、黑名单用户和重复发布  
  **Violation Detection**: Automatically identify ads, blacklisted users, and duplicate posts
- **实时监控**：动态监测社区违规行为  
  **Real-time Monitoring**: Dynamically monitor community violations

### 开发工具 | Development Tools

- **多格式反编译**：支持 KITTEN N、KITTEN、NEMO、COCO 等作品格式  
  **Multi-format Decompilation**: Support for KITTEN N, KITTEN, NEMO, COCO and other work formats
- **AI 助手集成**：KN AI 对话接口和智能交互功能  
  **AI Assistant Integration**: KN AI dialogue interface and intelligent interaction features
- **跨平台上传**：多平台文件上传支持，便捷资源管理  
  **Cross-platform Upload**: Multi-platform file upload support for convenient resource management

### 实用工具 | Utility Tools

- **喵口令生成器**：快速生成作品分享口令  
  **Miao Code Generator**: Quickly generate work sharing codes
- **小说下载器**：批量下载编程猫社区小说  
  **Novel Downloader**: Batch download CodeMao community novels
- **插件系统**：支持第三方插件扩展功能  
  **Plugin System**: Support for third-party plugin extensions

## 快速开始 | Quick Start

### 环境要求 | Requirements

- Python 3.13 或更高版本 | Python 3.13 or higher

### 安装步骤 | Installation Steps

```bash
# 克隆项目 | Clone the repository
git clone https://github.com/aurzex/Aumiao.git
cd Aumiao/Aumiao-py

# 使用uv包管理器（推荐）| Using uv package manager (recommended)
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

从[Release 页面](https://github.com/aurzex/Aumiao/releases)下载预编译版本，无需配置即可直接运行。  
Download precompiled versions from the [Release page](https://github.com/aurzex/Aumiao/releases), ready to run without configuration.

## 贡献指南 | Contribution Guidelines

我们欢迎所有形式的贡献。请遵循以下流程： | We welcome all forms of contributions. Please follow the process below:

1. **Fork 仓库**：点击右上角的 Fork 按钮 | **Fork Repository**: Click the Fork button in the upper right corner
2. **创建分支**：基于`main`分支创建功能分支 | **Create Branch**: Create a feature branch based on the `main` branch
3. **开发功能**：在分支上实现您的改进 | **Develop Feature**: Implement your improvements on the branch
4. **提交测试**：确保代码通过现有测试 | **Run Tests**: Ensure code passes existing tests
5. **发起 PR**：向主仓库提交 Pull Request | **Submit PR**: Submit a Pull Request to the main repository

请确保： | Please ensure:

- 代码风格与现有代码保持一致 | Code style is consistent with existing code
- 添加必要的文档和注释 | Add necessary documentation and comments
- 更新相关的测试用例 | Update relevant test cases

[![Star History Chart](https://api.star-history.com/svg?repos=aurzex/Aumiao&type=Date)](https://star-history.com/#aurzex/Aumiao&Date)

## 相关项目 | Related Projects

### API 与文档 | API & Documentation

- [codemao-api](https://github.com/lambdark/codemao-api) - 编程猫社区官方 API 文档 | Official CodeMao community API documentation
- [CoCo-Source-Code-Plan](https://github.com/glacier-studio/CoCo-Source-Code-Plan) - CoCo 编辑器源代码还原计划 | CoCo editor source code restoration project

### 开发工具 | Development Tools

- [Kitten-4-Decompiler](https://github.com/S-LIGHTNING/Kitten-4-Decompiler) - Kitten4 作品反编译器 | Kitten4 work decompiler
- [Kitten-Cloud-Function](https://github.com/S-LIGHTNING/Kitten-Cloud-Function) - 云变量客户端工具 | Cloud variable client tool
- [JsToKn](https://github.com/PiicatXstate/JsToKn) - JavaScript 转 KittenN 积木工具 | JavaScript to KittenN block tool
- [CodemaoNemoMultiDecompiler](https://github.com/MoonBcmTools/CodemaoNemoMultiDecompiler) - Nemo 作品源代码还原 | Nemo work source code restoration
- [CodemaoNemoOneKeyBuildShareCode](https://github.com/MoonBcmTools/CodemaoNemoOneKeyBuildShareCode) - 一键生成 Nemo 作品分享口令 | One-click Nemo work share code generation
- [coco-packager](https://github.com/cocotais-lab/coco-packager) - CoCo 作品打包工具 | CoCo work packaging tool
- [widget-template](https://github.com/liulyxandy-codemao/widget-template) - CoCo 自定义控件模板 | CoCo custom widget template

### 社区增强与优化 | Community Enhancement & Optimization

- [Better-Codemao](https://github.com/LuYingYiLong/Better-Codemao) - 编程猫社区增强脚本 | CodeMao community enhancement script
- [codemaoOptimization](https://github.com/sf-yuzifu/codemaoOptimization) - 社区使用问题优化 | Community usage optimization
- [pickcat](https://github.com/sf-yuzifu/pickcat) - 编程猫社区重新设计与功能扩展 | CodeMao community redesign and feature extension

### 实用工具 | Utility Tools

- [CodemaoEDUTools](https://github.com/Wangs-official/CodemaoEDUTools) - 学生账号管理工具 | Student account management tool
- [Codemao-Storage](https://github.com/ornwind/Codemao-Storage) - 编程猫 CDN 文件上传工具 | CodeMao CDN file upload tool
- [bcm_convertor](https://github.com/sf-yuzifu/bcm_convertor) - 作品转桌面应用工具 | Work to desktop application converter
- [codemaonoveldownloader](https://github.com/rumunius/codemaonoveldownloader) - 小说下载爬虫 | Novel download crawler
- [CodemaoDrive](https://github.com/CrackerCat/CodemaoDrive) - 编程猫云盘，支持任意文件上传与下载 | CodeMao cloud drive supporting any file upload/download
- [PostCodemao](https://github.com/stonehfzs/PostCodemao) - 编程猫的时光邮箱/明信片生成 DEMO | CodeMao time email/postcard generation demo
- [Codemao-Studio-Ranking](https://github.com/Hatmic/Codemao-Studio-Ranking) - 编程猫工作室评论数排行榜 | CodeMao studio comment ranking
- [codemao-diger-rebuild](https://github.com/Rov-Waff/codemao-diger-rebuild) - 编程猫社区挖坟工具 | CodeMao community necromancy tool

### 数据采集与分析 | Data Collection & Analysis

- [CodemaoSpider](https://github.com/wbteve/CodemaoSpider) - 作品素材采集工具 | Work material collection tool
- [-Codemao-](https://github.com/Liu-YuC/-Codemao-) - 评论数据爬取与分析 | Comment data crawling and analysis

### CoCo 生态 | CoCo Ecosystem

- [CoCo-Community](https://github.com/zitzhen/CoCo-Community) - CoCo 第三方社区 | CoCo third-party community

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

本项目采用 AGPL-3.0 开源协议。详细条款请参阅[LICENSE](LICENSE)文件。  
This project is licensed under the AGPL-3.0 license. See the [LICENSE](LICENSE) file for details.

---

感谢使用 Aumiao。如果本项目对您有帮助，请考虑在 GitHub 上为我们点亮星标。  
Thank you for using Aumiao. If this project helps you, please consider giving it a star on GitHub.
