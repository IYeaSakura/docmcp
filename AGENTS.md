# DocMCP 项目指南

本文档为 AI 编程助手提供项目背景、架构和开发规范，帮助快速理解和贡献代码。

---

## 项目概述

**DocMCP** 是一个基于 MCP（Model Context Protocol）协议和 Skills 系统构建的企业级文档处理平台。

### 核心特性

- **多格式支持**: doc/docx/pdf/xlsx/xls/ppt/pptx/txt/md/html/json
- **MCP 协议**: 标准化通信协议，支持 AI 模型与文档处理能力对接
- **Skills 插件系统**: 可动态加载的模块化处理单元
- **安全沙箱**: 隔离执行环境，防止恶意代码
- **高性能**: 异步处理、连接池、缓存机制
- **监控告警**: 内置性能监控和健康检查

### 项目元数据

| 属性 | 值 |
|------|-----|
| 名称 | docmcp |
| 版本 | 0.1.0 |
| 许可证 | MIT |
| Python 版本 | >= 3.9 |
| 构建工具 | hatchling |

---

## 项目结构

```
docmcp/
├── docmcp/                    # 主代码目录
│   ├── __init__.py           # 包入口，导出核心类
│   ├── config.py             # 系统配置管理（中文注释）
│   ├── core/                 # 核心引擎
│   │   ├── document.py       # 文档抽象基类
│   │   ├── engine.py         # 异步处理引擎
│   │   ├── pipeline.py       # 处理管道
│   │   ├── handlers/         # 格式处理器
│   │   │   ├── base.py       # 处理器基类
│   │   │   ├── word_handler.py
│   │   │   ├── pdf_handler.py
│   │   │   ├── excel_handler.py
│   │   │   └── ppt_handler.py
│   │   └── utils.py          # 核心工具函数
│   ├── mcp/                  # MCP 协议实现
│   │   ├── protocol.py       # 协议消息定义
│   │   ├── server.py         # MCP 服务器
│   │   ├── client.py         # MCP 客户端
│   │   └── doc_server.py     # 文档专用服务器
│   ├── skills/               # Skills 插件系统
│   │   ├── base.py           # Skill 基类、上下文、结果
│   │   ├── registry.py       # 技能注册表
│   │   ├── loader.py         # 动态加载器
│   │   ├── scheduler.py      # 调度器
│   │   ├── sandbox.py        # 安全沙箱执行
│   │   └── builtins/         # 内置技能
│   │       ├── extract_text.py
│   │       ├── analyze_document.py
│   │       ├── convert_format.py
│   │       └── merge_documents.py
│   ├── security/             # 安全模块（中文注释）
│   │   ├── sandbox.py        # 沙箱执行器
│   │   ├── auth.py           # 认证授权
│   │   ├── scanner.py        # 内容扫描
│   │   └── audit.py          # 审计日志
│   ├── performance/          # 性能模块（中文注释）
│   │   ├── cache.py          # 多级缓存
│   │   ├── pool.py           # 连接池
│   │   ├── monitor.py        # 监控指标
│   │   └── limiter.py        # 限流器
│   └── utils/                # 工具函数
│       ├── async_utils.py
│       ├── validation.py
│       ├── security.py
│       └── logging_utils.py
├── tests/                    # 测试目录
│   ├── conftest.py           # pytest 配置和 fixtures
│   ├── test_*.py             # 各模块测试
│   └── data/                 # 测试数据生成
├── examples/                 # 使用示例（中文注释）
│   ├── basic_usage.py
│   ├── basic_server.py
│   ├── client_example.py
│   └── demo_skills.py
├── skills/                   # 额外的技能目录
├── scripts/                  # 脚本工具
│   ├── run_tests.sh          # 测试运行脚本
│   └── verify_all.py         # 功能验证
├── pyproject.toml            # 项目配置和依赖
├── requirements.txt          # 基础依赖
├── API.md                    # API 参考文档（中文）
└── README.md                 # 项目说明（中文）
```

---

## 技术栈

### 核心依赖

```
# 异步支持
aiofiles>=23.0.0
aiohttp>=3.8.0

# 文档处理
python-docx>=0.8.11      # Word 文档
PyPDF2>=3.0.0            # PDF 基础处理
pdfplumber>=0.9.0        # PDF 高级提取
openpyxl>=3.1.0          # Excel 处理
python-pptx>=0.6.21      # PPT 处理

# 数据验证
pydantic>=2.0.0
PyYAML>=6.0

# 安全
cryptography>=41.0.0
PyJWT>=2.8.0

# 工具
watchdog>=3.0.0          # 文件监控
tenacity>=8.2.0          # 重试机制
```

### 可选依赖组

- `dev`: pytest, black, isort, mypy, flake8, pre-commit
- `docs`: mkdocs, mkdocs-material, mkdocstrings
- `server`: fastapi, uvicorn, gunicorn
- `redis`: redis, aioredis
- `database`: asyncpg, sqlalchemy, alembic

---

## 构建和测试命令

### 安装开发环境

```bash
# 基础安装
pip install -e .

# 完整开发环境
pip install -e ".[all]"

# 或使用 requirements.txt
pip install -r requirements.txt
```

### 运行测试

```bash
# 使用脚本运行完整测试套件
bash scripts/run_tests.sh

# 使用 pytest 运行测试
pytest tests/ -v

# 运行特定标记的测试
pytest tests/ -m "not slow"          # 排除慢测试
pytest tests/ -m integration         # 仅集成测试
pytest tests/ -m security            # 仅安全测试
pytest tests/ -m performance         # 仅性能测试

# 生成覆盖率报告
pytest tests/ --cov=docmcp --cov-report=html
```

### 代码检查

```bash
# 格式化代码
black docmcp/ tests/

# 排序导入
isort docmcp/ tests/

# 类型检查
mypy docmcp/

# 代码风格检查
flake8 docmcp/
```

### 启动 MCP 服务器

```bash
# 使用 CLI 启动
docmcp-server

# 或使用 Python
python -m docmcp.mcp.server
```

---

## 代码风格指南

### 格式规范

- **行长度**: 100 字符（Black 配置）
- **引号**: 双引号优先
- **导入排序**: isort 的 black profile

### 类型注解

- **强制类型注解**: mypy 配置要求完整类型标注
- **Python 版本**: 目标 Python 3.9+
- **严格模式**: 启用 `disallow_untyped_defs`, `no_implicit_optional`

### 注释规范

- **模块/类/函数**: 使用 Google 风格的 docstring
- **语言**: 项目主要使用**中文**注释和文档
- **类型**: 使用类型注解替代类型注释

示例：

```python
@dataclass
class SkillContext:
    """
    Skills 的执行上下文。
    
    提供执行期间访问资源、配置和状态的能力。
    
    Attributes:
        document: 正在处理的文档（如适用）
        config: Skill 配置
        variables: 运行时变量
        user_id: 执行用户 ID
        request_id: 唯一请求标识
    """
    document: Optional[BaseDocument] = None
    config: Dict[str, Any] = field(default_factory=dict)
```

### 命名规范

- **类名**: PascalCase (如 `ProcessingEngine`, `SkillRegistry`)
- **函数/方法**: snake_case (如 `extract_text`, `validate_document`)
- **常量**: UPPER_SNAKE_CASE
- **私有成员**: 单下划线前缀 (如 `_config`, `_initialized`)
- **抽象基类**: 避免 ABC/Abstract 前缀，直接描述概念

---

## 架构设计

### 核心概念

#### 1. 文档抽象 (`core/document.py`)

```python
BaseDocument          # 文档基类
├── format            # 文档格式 (PDF, DOCX, etc.)
├── content           # 内容数据
├── metadata          # 元数据（标题、作者等）
└── methods           # extract_text(), save(), etc.
```

#### 2. 处理引擎 (`core/engine.py`)

```python
ProcessingEngine      # 异步处理引擎
├── 任务队列          # 优先级队列
├── 工作线程池        # 并发执行
├── 管道处理          # Pipeline stages
└── 监控指标          # 性能追踪
```

#### 3. Skills 系统 (`skills/`)

```python
BaseSkill             # Skill 抽象基类
├── name              # 唯一名称
├── version           # 语义化版本
├── metadata          # 支持格式、依赖等
├── execute()         # 主执行方法
└── validate()        # 前置验证

SkillRegistry         # 技能注册表
├── register()        # 注册技能
├── execute()         # 执行指定技能
└── load_from_dir()   # 动态加载

SkillContext          # 执行上下文
├── document          # 输入文档
├── config            # 配置参数
└── variables         # 运行时变量
```

#### 4. MCP 协议 (`mcp/`)

```python
MCPServer             # MCP 服务器
├── protocol          # JSON-RPC 2.0
├── handlers          # 方法处理器
└── connections       # 连接管理

MCPMessage            # 协议消息
├── method            # 方法名
├── params            # 参数
└── id                # 请求 ID
```

#### 5. 安全模块 (`security/`)

```python
SandboxExecutor       # 沙箱执行器
├── resource_limits   # 资源限制
├── network_policy    # 网络策略
└── isolation         # 进程隔离

ContentScanner        # 内容扫描
├── virus_scan        # 恶意代码检测
├── pattern_match     # 危险模式匹配
└── file_validation   # 文件类型验证
```

### 异步架构

- **引擎级别**: `ProcessingEngine` 使用 `asyncio` 和线程池
- **Skill 级别**: `BaseSkill.execute()` 是 `async` 方法
- **MCP 级别**: 服务器和客户端全异步实现

---

## 测试策略

### 测试结构

```
tests/
├── conftest.py              # 共享 fixtures
├── test_document.py         # 文档模型测试
├── test_engine.py           # 处理引擎测试
├── test_handlers.py         # 格式处理器测试
├── test_skills.py           # Skills 系统测试
├── test_security.py         # 安全模块测试
├── test_performance.py      # 性能测试
├── test_mcp_integration.py  # MCP 集成测试
└── data/                    # 测试数据生成脚本
```

### Fixtures 分类

- **文档 Fixtures**: `sample_document`, `sample_document_content`, `sample_documents`
- **引擎 Fixtures**: `processing_engine`, `processing_context`
- **MCP Fixtures**: `mcp_server`, `sample_mcp_request`
- **Skill Fixtures**: `mock_skill`, `skill_registry`, `skill_context`
- **安全 Fixtures**: `auth_manager`, `sandbox_executor`
- **性能 Fixtures**: `metrics_collector`, `health_checker`

### 测试标记

```python
@pytest.mark.slow           # 慢测试，可跳过
@pytest.mark.integration    # 集成测试
@pytest.mark.security       # 安全测试
@pytest.mark.performance    # 性能测试
```

### 运行策略

```bash
# 快速反馈（排除慢测试）
pytest -m "not slow"

# 完整测试
pytest

# 持续集成
pytest --cov=docmcp --cov-report=xml
```

---

## 配置系统

### 配置分层

1. **默认配置** (`config.py` 中的 dataclass 默认值)
2. **配置文件** (JSON 文件加载)
3. **环境变量** (`DOCMCP_*` 前缀)

### 环境变量

```bash
# 基础配置
DOCMCP_DEBUG=true                    # 调试模式
DOCMCP_ENV=development               # 环境类型

# 沙箱配置
DOCMCP_SANDBOX_MAX_MEMORY=512        # 最大内存(MB)
DOCMCP_SANDBOX_MAX_TIME=30           # 最大执行时间(秒)
DOCMCP_SANDBOX_NETWORK_ENABLED=false # 网络访问

# 缓存配置
DOCMCP_CACHE_MEMORY_SIZE=10000       # 内存缓存条目数
DOCMCP_CACHE_DISK_SIZE=1024          # 磁盘缓存大小(MB)

# 限流配置
DOCMCP_LIMITER_ENABLED=true
DOCMCP_LIMITER_RATE=100              # 每秒请求数
```

### 配置文件示例

```json
{
  "app_name": "DocMCP",
  "debug": false,
  "env": "production",
  "sandbox": {
    "max_memory_mb": 512,
    "max_execution_time": 30,
    "network_enabled": false
  },
  "cache": {
    "memory_cache_enabled": true,
    "memory_cache_size": 10000
  }
}
```

---

## 开发工作流

### 添加新 Skill

1. 创建继承 `BaseSkill` 的类
2. 定义 `name`, `version`, `supported_formats`
3. 实现 `execute()` 方法
4. 注册到 `SkillRegistry`

示例：

```python
from docmcp.skills import BaseSkill, SkillContext, SkillResult

class MySkill(BaseSkill):
    name = "my_skill"
    version = "1.0.0"
    description = "我的自定义技能"
    supported_formats = [DocumentFormat.PDF, DocumentFormat.DOCX]
    
    async def execute(self, input_data, context: SkillContext) -> SkillResult:
        # 实现处理逻辑
        result = await process(context.document)
        return SkillResult.success(data=result)
```

### 添加新格式处理器

1. 继承 `BaseHandler`
2. 定义 `supported_formats`
3. 实现 `load()`, `convert()`, `validate()`
4. 注册到引擎

### 扩展配置

1. 在 `config.py` 添加新的 dataclass
2. 添加到 `SystemConfig` 字段
3. 添加环境变量解析
4. 添加序列化/反序列化

---

## 安全注意事项

### 沙箱执行

- 所有用户提供的代码在 `SandboxExecutor` 中运行
- 默认禁用网络访问
- 限制内存、CPU、执行时间
- 使用 seccomp 和命名空间隔离（Linux）

### 内容扫描

- 文件上传前进行 magic bytes 验证
- 扫描恶意代码模式
- 检测敏感信息泄露

### 审计日志

- 记录所有操作（登录、处理、删除）
- 支持异步日志写入
- 可配置的保留策略

---

## 部署建议

### 生产环境

```bash
# 安装生产依赖
pip install ".[server,redis,database]"

# 使用 Gunicorn + Uvicorn
gunicorn docmcp.mcp.server:app -k uvicorn.workers.UvicornWorker -w 4
```

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install -e ".[all]"

EXPOSE 8080
CMD ["docmcp-server"]
```

---

## 常用导入路径

```python
# 核心类
from docmcp import ProcessingEngine, BaseDocument, DocumentFormat

# Skills
from docmcp.skills import BaseSkill, SkillRegistry, SkillContext, SkillResult

# MCP
from docmcp.mcp import MCPServer, MCPMessage, MCPResponse

# 安全
from docmcp.security import SandboxExecutor, AuthManager

# 性能
from docmcp.performance import Cache, ConnectionPool, MetricsCollector

# 配置
from docmcp.config import get_config, SystemConfig
```

---

## 调试技巧

### 启用详细日志

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 测试单个 Skill

```python
async def test_skill():
    registry = SkillRegistry()
    skill = MySkill()
    registry.register(skill)
    
    context = SkillContext(document=doc)
    result = await registry.execute("my_skill", input_data, context)
    print(result)
```

### 验证配置

```python
from docmcp.config import get_config, init_config

# 从环境变量加载
config = init_config()
print(config.to_dict())
```

---

## 相关文档

- `README.md` - 项目概览和快速开始
- `API.md` - 详细 API 参考
- 代码中的 docstring - 实现细节

---

*本文档由 AI 助手根据项目实际内容生成，如有更新请同步修改。*
