# Aumiao

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.13](https://img.shields.io/badge/Python-3.13-green.svg)](https://www.python.org/downloads/)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/Aurzex/Aumiao)

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
- `setting.json` - 程序设置配置文件 | Program settings configuration file

#### 编译版本 | Compiled Version：

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
- **联系邮箱**：Aumiao@aurzex.top
- **开发团队**：Aurzex, DontLoveby, Moonleeeaf, Nomen

## 许可证 | License

本项目采用 AGPL 协议。
This project is licensed under the AGPL license.

---

[![Star History Chart](https://api.star-history.com/svg?repos=aurzex/Aumiao&type=Date)](https://star-history.com/#aurzex/Aumiao&Date)

感谢您的阅读！ Thank you for reading!

## 相关项目 | Related Projects

以下是一些与编程猫开发相关的其他项目：

### API 和文档

- [lambdark / codemao-api](https://github.com/lambdark/codemao-api) - 编程猫社区 API 文档
- [Aurzex / codemao-api](https://github.com/Aurzex/codemao-api) - Forked from lambdark/codemao-api

### 开发工具

- [S-LIGHTNING / Kitten-4-Decompiler](https://github.com/S-LIGHTNING/Kitten-4-Decompiler) - 源码反编译器 4
- [S-LIGHTNING / Kitten-Cloud-Function](https://github.com/S-LIGHTNING/Kitten-Cloud-Function) - 用于编程猫源码云功能的客户端工具
- [MoonBcmTools / CodemaoNemoMultiDecompiler](https://github.com/MoonBcmTools/CodemaoNemoMultiDecompiler) - 还原 nEmo 作品源代码
- [MoonBcmTools / CodemaoNemoOneKeyBuildShareCode](https://github.com/MoonBcmTools/CodemaoNemoOneKeyBuildShareCode) - 一键生成菠菜面 Nemo 作品分享口令

### 社区优化

- [sf-yuzifu / codemaoOptimization](https://github.com/sf-yuzifu/codemaoOptimization) - 编程猫使用问题优化
- [LuYingYiLong / Better-Codemao](https://github.com/LuYingYiLong/Better-Codemao) - Better Codemao
- [sf-yuzifu / pickcat](https://github.com/sf-yuzifu/pickcat) - 重新设计编程猫社区并添加更多功能

### 实用工具

- [Wangs-official / CodemaoEDUTools](https://github.com/Wangs-official/CodemaoEDUTools) - 编程猫社区学生账号工具
- [glacier-studio / CoCo-Source-Code-Plan](https://github.com/glacier-studio/CoCo-Source-Code-Plan) - 编程猫 CoCo 源代码计划
- [sf-yuzifu / bcm_convertor](https://github.com/sf-yuzifu/bcm_convertor) - 将作品制作成独立应用程序
- [Hatmic / Codemao-Studio-Ranking](https://github.com/Hatmic/Codemao-Studio-Ranking) - 编程猫工作室评论数排行榜
- [Rov-Waff / codemao-diger-rebuild](https://github.com/Rov-Waff/codemao-diger-rebuild) - 编程猫社区挖坟工具
- [ornwind / Codemao-Storage](https://github.com/ornwind/Codemao-Storage) - 编程猫论坛 CDN 文件上传

### 数据采集

- [wbteve / CodemaoSpider](https://github.com/wbteve/CodemaoSpider) - 一键获取编程猫作品中的素材
- [Liu-YuC / -Codemao-](https://github.com/Liu-YuC/-Codemao-) - 爬取 Codemao 社区的评论并分析
- [rumunius / codemaonoveldownloader](https://github.com/rumunius/codemaonoveldownloader) - 下载编程猫小说的 Python 爬虫

### 其他工具

- [PiicatXstate / JsToKn](https://github.com/PiicatXstate/JsToKn) - 将特定 Js 代码转换为编程猫 KittenN 文本积木
- [CrackerCat / CodemaoDrive](https://github.com/CrackerCat/CodemaoDrive) - 编程猫云盘，支持任意文件上传与下载
- [stonehfzs / PostCodemao](https://github.com/stonehfzs/PostCodemao) - 编程猫的时光邮箱/明信片生成 DEMO
