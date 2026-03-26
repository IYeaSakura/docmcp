# DocMCP - 文档处理MCP+Skills系统

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue.svg" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="MIT License">
  <img src="https://img.shields.io/badge/Version-1.0.0-orange.svg" alt="Version 1.0.0">
</p>

---

## 目录

- [项目介绍](#项目介绍)
- [核心特性](#核心特性)
- [支持格式](#支持格式)
- [快速开始](#快速开始)
- [安装说明](#安装说明)
- [基本使用](#基本使用)
- [项目结构](#项目结构)
- [文档导航](#文档导航)
- [贡献指南](#贡献指南)
- [许可证](#许可证)

---

## 项目介绍

DocMCP是一个基于MCP（Model Context Protocol）协议和Skills系统构建的企业级文档处理平台。它提供了统一的文档抽象层，支持多种文档格式的解析、转换、提取和处理，同时具备强大的安全沙箱机制和高性能处理能力。

### 设计理念

- **模块化设计**: 各组件独立，易于扩展和维护
- **插件化架构**: Skills系统支持动态加载和自定义扩展
- **安全第一**: 内置沙箱机制，确保文档处理安全
- **高性能**: 连接池、缓存、异步处理，最大化性能

---

## 核心特性

| 特性 | 描述 |
|------|------|
| **多格式支持** | 支持 doc/docx/pdf/xlsx/xls/ppt/pptx 等主流文档格式 |
| **MCP协议** | 基于Model Context Protocol的标准化通信协议 |
| **Skills系统** | 可插拔的技能系统，支持自定义文档处理逻辑 |
| **安全沙箱** | 内置沙箱环境，隔离文档处理，防止恶意代码执行 |
| **高性能** | 连接池、缓存机制、异步处理，支持高并发 |
| **监控告警** | 内置性能监控和告警系统 |
| **易于扩展** | 插件化架构，易于添加新格式和技能 |
| **完整审计** | 操作日志和审计追踪 |

---

## 支持格式

| 格式 | 扩展名 | 读取 | 写入 | 转换 |
|------|--------|------|------|------|
| Word文档 | .doc, .docx | ✅ | ✅ | ✅ |
| PDF文档 | .pdf | ✅ | ⚠️ | ✅ |
| Excel表格 | .xls, .xlsx | ✅ | ✅ | ✅ |
| PPT演示 | .ppt, .pptx | ✅ | ✅ | ✅ |
| 纯文本 | .txt | ✅ | ✅ | ✅ |
| Markdown | .md | ✅ | ✅ | ✅ |
| HTML | .html, .htm | ✅ | ✅ | ✅ |
| JSON | .json | ✅ | ✅ | ✅ |

> ⚠️ PDF写入需要额外配置（如wkhtmltopdf或pandoc）

---

## 快速开始

### 1. 安装

```bash
# 克隆仓库
git clone https://github.com/your-org/docmcp.git
cd docmcp

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 安装可选依赖（PDF处理）
pip install -r requirements-optional.txt
```

### 2. 快速启动

```python
from docmcp import DocumentProcessor

# 创建处理器实例
processor = DocumentProcessor()

# 处理文档
result = processor.process("example.docx")
print(result.content)

# 转换格式
processor.convert("example.docx", "output.pdf")
```

### 3. 使用MCP服务器

```python
from docmcp.mcp import MCPServer

# 启动MCP服务器
server = MCPServer(host="0.0.0.0", port=8080)
server.start()
```

---

## 安装说明

### 环境要求

- Python 3.9+
- 内存: 最低 2GB，推荐 4GB+
- 磁盘: 最低 1GB 可用空间

### 依赖安装

```bash
# 基础依赖
pip install docmcp

# 完整安装（包含所有可选依赖）
pip install docmcp[all]

# 特定格式支持
pip install docmcp[pdf]      # PDF处理
pip install docmcp[office]   # Office文档
pip install docmcp[excel]    # Excel处理
```

### Docker部署

```bash
# 构建镜像
docker build -t docmcp:latest .

# 运行容器
docker run -d -p 8080:8080 docmcp:latest
```

---

## 基本使用

### 文档处理

```python
from docmcp import DocumentProcessor

processor = DocumentProcessor()

# 读取文档
with open("document.docx", "rb") as f:
    doc = processor.load(f, format="docx")

# 提取文本
text = doc.extract_text()
print(text)

# 提取元数据
metadata = doc.get_metadata()
print(metadata)
```

### 格式转换

```python
# 转换为不同格式
processor.convert("input.docx", "output.pdf")
processor.convert("input.pdf", "output.txt")
processor.convert("input.xlsx", "output.csv")
```

### 使用Skills

```python
from docmcp.skills import SkillRegistry

# 注册自定义Skill
registry = SkillRegistry()
registry.register("summarize", SummarizeSkill())

# 执行Skill
result = registry.execute("summarize", document=doc)
```

### MCP客户端

```python
from docmcp.mcp import MCPClient

client = MCPClient(server_url="http://localhost:8080")

# 发送处理请求
response = client.process_document(
    file_path="document.pdf",
    operations=["extract_text", "extract_metadata"]
)
```

---

## 项目结构

```
docmcp/
├── docmcp/                    # 主代码目录
│   ├── __init__.py           # 包入口
│   ├── core/                 # 核心引擎
│   │   ├── __init__.py
│   │   ├── document.py       # 文档抽象基类
│   │   ├── processor.py      # 处理引擎
│   │   ├── handlers/         # 格式处理器
│   │   │   ├── __init__.py
│   │   │   ├── docx.py       # Word处理器
│   │   │   ├── pdf.py        # PDF处理器
│   │   │   ├── excel.py      # Excel处理器
│   │   │   ├── ppt.py        # PPT处理器
│   │   │   └── base.py       # 处理器基类
│   │   └── utils/            # 工具函数
│   │       ├── __init__.py
│   │       ├── validators.py # 验证工具
│   │       └── converters.py # 转换工具
│   ├── mcp/                  # MCP协议实现
│   │   ├── __init__.py
│   │   ├── server.py         # MCP服务器
│   │   ├── client.py         # MCP客户端
│   │   ├── protocol.py       # 协议定义
│   │   └── handlers/         # 请求处理器
│   ├── skills/               # Skills系统
│   │   ├── __init__.py
│   │   ├── registry.py       # 技能注册表
│   │   ├── loader.py         # 技能加载器
│   │   ├── scheduler.py      # 调度器
│   │   └── base.py           # 技能基类
│   ├── security/             # 安全模块
│   │   ├── __init__.py
│   │   ├── sandbox.py        # 沙箱环境
│   │   ├── permissions.py    # 权限管理
│   │   └── audit.py          # 审计日志
│   └── performance/          # 性能模块
│       ├── __init__.py
│       ├── cache.py          # 缓存管理
│       ├── pool.py           # 连接池
│       └── monitor.py        # 性能监控
├── tests/                    # 测试目录
│   ├── unit/                 # 单元测试
│   ├── integration/          # 集成测试
│   └── fixtures/             # 测试数据
├── docs/                     # 文档目录
├── examples/                 # 示例代码
├── scripts/                  # 脚本工具
├── requirements.txt          # 依赖文件
├── pyproject.toml            # 项目配置
└── README.md                 # 本文件
```

---

## 许可证

本项目采用 [MIT License](./LICENSE) 开源协议。
