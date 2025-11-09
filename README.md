# Aumiao

## 项目简介 | Project Introduction

Aumiao 是一个编程猫 API 收集项目和工具集合，为编程猫脚本的开发提供便利的支持。

Aumiao is a CodeMao API collection project and toolset that provides convenient support for the development of CodeMao scripts.

## 主要功能 | Main Features

### 社区管理 | Community Management

- **评论管理**：支持按关键词或黑名单清除作品和帖子评论  
  **Comment Management**: Clear work and post comments based on keywords or blacklist
- **自动回复**：基于关键词的智能回复系统  
  **Auto Reply**: Keyword-based intelligent reply system
- **消息处理**：清除邮箱红点和批量邮件处理  
  **Message Processing**: Clear inbox notifications and batch email processing

### 内容审核 | Content Moderation

- **举报处理**：支持批量举报审核和处理  
  **Report Handling**: Batch report review and processing
- **违规检测**：自动识别广告、黑名单用户和重复内容  
  **Violation Detection**: Automatically detect ads, blacklisted users, and duplicate content

### 开发工具 | Development Tools

- **作品反编译**：支持 KITTEN N、KITTEN、NEMO、COCO 等多种格式  
  **Work Decompilation**: Support for KITTEN N, KITTEN, NEMO, COCO and other formats
- **AI 助手集成**：KN AI 对话和智能交互功能  
  **AI Assistant Integration**: KN AI dialogue and intelligent interaction features
- **文件上传**：多平台文件上传支持  
  **File Upload**: Multi-platform file upload support

### 实用工具 | Utility Tools

- **喵口令生成** | **Miao Command Generation**
- **小说下载** | **Novel Download**
- **外置插件支持** | **External Plugin Support**

## 快速开始 | Quick Start

### 环境要求 | Environment Requirements

- Python 3.13

```bash
# 克隆项目 | Clone the project
git clone https://github.com/aurzex/Aumiao.git
cd Aumiao/Aumiao-py

pip install uv
uv sync
```

### 首次运行说明 | First Run Instructions

**Python 源码版本 | Python Source Version：**  
首次运行需要执行 `Aumiao-py` 目录下的 `recover.py` 来生成必要的数据文件。  
First run requires executing `recover.py` in the `Aumiao-py` directory to generate necessary data files.

- `data.json` - 用户数据配置文件 | User data configuration file
- `setting.py` - 程序设置配置文件 | Program settings configuration file

**编译版本 | Compiled Version：**  
可以直接使用 Release 页面或 GitHub Actions 自动构建的版本，无需额外配置。  
Can directly use versions from Release page or GitHub Actions auto-builds, no additional configuration needed.

## 贡献指南 | Contribution Guide

我们欢迎社区贡献！请参考以下步骤：  
We welcome community contributions! Please follow these steps:

1. Fork 本仓库 | Fork this repository
2. 创建功能分支 | Create a feature branch
3. 提交更改 | Commit your changes
4. 推送到分支 | Push to the branch
5. 开启 Pull Request | Open a Pull Request

## 联系我们 | Contact Us

- **官方网站**：https://aumiao.aurzex.top  
  **Official Website**: https://aumiao.aurzex.top
- **联系邮箱**：Aumiao@aurzex.top  
  **Contact Email**: Aumiao@aurzex.top
- **开发团队**：Aurzex, DontLoveby, Moonleeeaf, Nomen  
  **Development Team**: Aurzex, DontLoveby, Moonleeeaf, Nomen

## 许可证 | License

本项目采用 AGPL 协议。  
This project is licensed under the AGPL license.

---

感谢您的阅读！
Thank you for reading!
