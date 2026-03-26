# DocMCP API 参考文档

本文档详细介绍 DocMCP 系统的所有 API 接口，包括核心引擎 API、MCP 协议 API、Skills API 和配置选项。

---

## 目录

- [核心引擎 API](#核心引擎-api)
- [MCP 协议 API](#mcp-协议-api)
- [Skills API](#skills-api)
- [REST API](#rest-api)
- [配置选项](#配置选项)

---

## 核心引擎 API

### DocumentProcessor

文档处理器是 DocMCP 的核心类，提供文档加载、处理和转换功能。

#### 类定义

```python
class DocumentProcessor:
    """文档处理器"""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        handlers: Optional[List[BaseHandler]] = None
    ):
        """
        初始化文档处理器

        Args:
            config: 处理器配置
            handlers: 自定义处理器列表
        """
```

#### 方法

##### load

```python
def load(
    self,
    content: Union[bytes, BinaryIO],
    format: str,
    options: Optional[Dict[str, Any]] = None
) -> Document:
    """
    加载文档

    Args:
        content: 文档内容（字节或流）
        format: 文档格式（如 'pdf', 'docx'）
        options: 加载选项

    Returns:
        Document: 文档对象

    Raises:
        UnsupportedFormatError: 不支持的格式
        InvalidDocumentError: 文档无效

    Example:
        >>> processor = DocumentProcessor()
        >>> with open('doc.pdf', 'rb') as f:
        ...     doc = processor.load(f.read(), format='pdf')
    """
```

##### load_file

```python
def load_file(
    self,
    file_path: Union[str, Path],
    options: Optional[Dict[str, Any]] = None
) -> Document:
    """
    从文件加载文档

    Args:
        file_path: 文件路径
        options: 加载选项

    Returns:
        Document: 文档对象

    Example:
        >>> doc = processor.load_file('document.docx')
    """
```

##### convert

```python
def convert(
    self,
    source: Union[str, Path, Document],
    target_path: Union[str, Path],
    target_format: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None
) -> ConversionResult:
    """
    转换文档格式

    Args:
        source: 源文档（路径或Document对象）
        target_path: 目标文件路径
        target_format: 目标格式（从路径推断）
        options: 转换选项

    Returns:
        ConversionResult: 转换结果

    Example:
        >>> result = processor.convert('input.docx', 'output.pdf')
        >>> print(result.success, result.output_path)
    """
```

##### process

```python
def process(
    self,
    source: Union[str, Path, Document],
    operations: List[Dict[str, Any]],
    options: Optional[Dict[str, Any]] = None
) -> ProcessingResult:
    """
    执行文档处理操作

    Args:
        source: 源文档
        operations: 操作列表
        options: 处理选项

    Returns:
        ProcessingResult: 处理结果

    Example:
        >>> result = processor.process('doc.pdf', [
        ...     {'type': 'extract_text'},
        ...     {'type': 'extract_metadata'}
        ... ])
    """
```

### Document

文档抽象基类，所有格式文档的基类。

```python
class Document(ABC):
    """文档抽象基类"""

    @property
    @abstractmethod
    def format(self) -> str:
        """文档格式"""
        pass

    @abstractmethod
    def extract_text(
        self,
        pages: Optional[List[int]] = None,
        bbox: Optional[Tuple[float, float, float, float]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """提取文本"""
        pass

    @abstractmethod
    def extract_metadata(self) -> DocumentMetadata:
        """提取元数据"""
        pass

    @abstractmethod
    def extract_tables(
        self,
        pages: Optional[List[int]] = None
    ) -> List[Table]:
        """提取表格"""
        pass

    @abstractmethod
    def extract_images(
        self,
        pages: Optional[List[int]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> List[Image]:
        """提取图片"""
        pass

    @abstractmethod
    def get_metadata(self) -> DocumentMetadata:
        """获取文档元数据"""
        pass

    @abstractmethod
    def save(self, path: Union[str, Path], **options) -> None:
        """保存文档"""
        pass
```

### BaseHandler

处理器基类，用于实现特定格式的文档处理。

```python
class BaseHandler(ABC):
    """文档处理器基类"""

    # 处理器支持的格式
    supported_formats: List[str] = []

    # 处理器版本
    version: str = "1.0.0"

    @abstractmethod
    def can_handle(self, format: str) -> bool:
        """检查是否支持指定格式"""
        pass

    @abstractmethod
    def load(
        self,
        content: Union[bytes, BinaryIO],
        options: Optional[Dict[str, Any]] = None
    ) -> Document:
        """加载文档"""
        pass

    @abstractmethod
    def convert(
        self,
        document: Document,
        target_format: str,
        options: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """转换文档"""
        pass

    @abstractmethod
    def validate(self, content: bytes) -> Tuple[bool, Optional[str]]:
        """验证文档"""
        pass
```

---

## MCP 协议 API

### MCPServer

MCP 服务器实现，提供标准化的文档处理服务接口。

```python
class MCPServer:
    """MCP服务器"""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        config: Optional[Dict[str, Any]] = None,
        processor: Optional[DocumentProcessor] = None
    ):
        """
        初始化MCP服务器

        Args:
            host: 监听主机
            port: 监听端口
            config: 服务器配置
            processor: 文档处理器实例
        """

    def start(self) -> None:
        """启动服务器"""

    def stop(self) -> None:
        """停止服务器"""

    def register_handler(
        self,
        method: str,
        handler: Callable
    ) -> None:
        """
        注册请求处理器

        Args:
            method: 方法名
            handler: 处理函数
        """
```

### MCPClient

MCP 客户端，用于连接 MCP 服务器。

```python
class MCPClient:
    """MCP客户端"""

    def __init__(
        self,
        server_url: str,
        api_key: Optional[str] = None,
        timeout: int = 30
    ):
        """
        初始化MCP客户端

        Args:
            server_url: 服务器URL
            api_key: API密钥
            timeout: 请求超时时间
        """

    def connect(self) -> bool:
        """连接服务器"""

    def disconnect(self) -> None:
        """断开连接"""

    def send_request(
        self,
        method: str,
        params: Dict[str, Any],
        request_id: Optional[str] = None
    ) -> MCPResponse:
        """
        发送请求

        Args:
            method: 方法名
            params: 请求参数
            request_id: 请求ID

        Returns:
            MCPResponse: 响应对象
        """

    def process_document(
        self,
        document_id: str,
        operations: List[Dict[str, Any]]
    ) -> ProcessingResult:
        """处理文档"""

    def upload_document(
        self,
        file_path: Union[str, Path],
        options: Optional[Dict[str, Any]] = None
    ) -> UploadResult:
        """上传文档"""

    def convert_document(
        self,
        document_id: str,
        target_format: str,
        options: Optional[Dict[str, Any]] = None
    ) -> ConversionResult:
        """转换文档"""
```

### MCP 协议消息格式

#### 请求消息

```json
{
  "jsonrpc": "2.0",
  "method": "document.process",
  "params": {
    "document_id": "doc_123456",
    "operations": [
      {
        "type": "extract_text",
        "options": {
          "pages": [0, 1]
        }
      }
    ]
  },
  "id": 1
}
```

#### 响应消息

```json
{
  "jsonrpc": "2.0",
  "result": {
    "success": true,
    "data": {
      "text": "提取的文本内容...",
      "metadata": {
        "page_count": 10,
        "word_count": 5000
      }
    }
  },
  "id": 1
}
```

#### 错误响应

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32600,
    "message": "Invalid Request",
    "data": {
      "details": "Document not found"
    }
  },
  "id": 1
}
```

### MCP 方法列表

| 方法名 | 描述 | 参数 |
|--------|------|------|
| `document.upload` | 上传文档 | `file`, `options` |
| `document.process` | 处理文档 | `document_id`, `operations` |
| `document.convert` | 转换文档 | `document_id`, `target_format` |
| `document.delete` | 删除文档 | `document_id` |
| `document.get_metadata` | 获取元数据 | `document_id` |
| `document.download` | 下载文档 | `document_id` |
| `batch.process` | 批量处理 | `documents`, `operations` |
| `skills.list` | 列出Skills | - |
| `skills.execute` | 执行Skill | `document_id`, `skill_name` |
| `system.health` | 健康检查 | - |
| `system.metrics` | 获取指标 | - |

---

## Skills API

### BaseSkill

Skill 基类，所有自定义 Skill 的基类。

```python
class BaseSkill(ABC):
    """Skill基类"""

    # Skill元数据
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    author: str = ""

    # 输入输出Schema
    input_schema: Dict[str, Any] = {}
    output_schema: Dict[str, Any] = {}

    @abstractmethod
    def execute(
        self,
        document: Document,
        **kwargs
    ) -> SkillResult:
        """
        执行Skill

        Args:
            document: 输入文档
            **kwargs: 额外参数

        Returns:
            SkillResult: 执行结果
        """
        pass

    def validate(
        self,
        document: Document,
        **kwargs
    ) -> bool:
        """
        验证输入

        Args:
            document: 输入文档
            **kwargs: 额外参数

        Returns:
            bool: 验证是否通过
        """
        return True

    def initialize(self, config: Dict[str, Any]) -> None:
        """
        初始化Skill

        Args:
            config: 配置字典
        """
        pass

    def cleanup(self) -> None:
        """清理资源"""
        pass
```

### SkillRegistry

Skill 注册表，管理所有可用的 Skills。

```python
class SkillRegistry:
    """Skill注册表"""

    def __init__(self):
        """初始化注册表"""

    def register(self, skill: BaseSkill) -> None:
        """
        注册Skill

        Args:
            skill: Skill实例
        """

    def unregister(self, skill_name: str) -> None:
        """
        注销Skill

        Args:
            skill_name: Skill名称
        """

    def get(self, skill_name: str) -> Optional[BaseSkill]:
        """
        获取Skill

        Args:
            skill_name: Skill名称

        Returns:
            BaseSkill: Skill实例
        """

    def list_skills(self) -> List[SkillInfo]:
        """
        列出所有Skills

        Returns:
            List[SkillInfo]: Skill信息列表
        """

    def execute(
        self,
        skill_name: str,
        document: Document,
        **kwargs
    ) -> SkillResult:
        """
        执行指定Skill

        Args:
            skill_name: Skill名称
            document: 输入文档
            **kwargs: 额外参数

        Returns:
            SkillResult: 执行结果
        """

    async def execute_async(
        self,
        skill_name: str,
        document: Document,
        **kwargs
    ) -> SkillResult:
        """异步执行Skill"""

    def load_from_directory(self, directory: str) -> None:
        """
        从目录加载Skills

        Args:
            directory: Skills目录路径
        """
```

### SkillResult

Skill 执行结果。

```python
@dataclass
class SkillResult:
    """Skill执行结果"""

    success: bool
    data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    execution_time: float = 0.0
```

---

## REST API

### 基础信息

- **Base URL**: `http://localhost:8080/api/v1`
- **认证方式**: API Key 或 JWT

### 认证

#### API Key 认证

```bash
curl -H "X-API-Key: your-api-key" \
  http://localhost:8080/api/v1/documents
```

#### JWT 认证

```bash
curl -H "Authorization: Bearer your-jwt-token" \
  http://localhost:8080/api/v1/documents
```

### 端点列表

#### 1. 文档上传

```http
POST /api/v1/documents/upload
Content-Type: multipart/form-data
```

**请求参数**:

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| `file` | File | 是 | 上传的文件 |
| `options` | JSON | 否 | 处理选项 |

**响应**:

```json
{
  "id": "doc_123456",
  "filename": "document.pdf",
  "format": "pdf",
  "size": 1024567,
  "status": "processed",
  "created_at": "2024-01-15T10:30:00Z",
  "expires_at": "2024-01-16T10:30:00Z"
}
```

#### 2. 获取文档信息

```http
GET /api/v1/documents/{document_id}
```

**响应**:

```json
{
  "id": "doc_123456",
  "filename": "document.pdf",
  "format": "pdf",
  "size": 1024567,
  "status": "processed",
  "metadata": {
    "title": "文档标题",
    "author": "作者",
    "page_count": 10,
    "word_count": 5000,
    "created_at": "2024-01-01T00:00:00Z"
  },
  "created_at": "2024-01-15T10:30:00Z"
}
```

#### 3. 提取文本

```http
POST /api/v1/documents/{document_id}/extract/text
Content-Type: application/json
```

**请求体**:

```json
{
  "pages": [0, 1, 2],
  "include_formatting": true
}
```

**响应**:

```json
{
  "text": "完整文本内容...",
  "pages": [
    {"page": 0, "text": "第一页内容..."},
    {"page": 1, "text": "第二页内容..."}
  ],
  "word_count": 5000,
  "char_count": 25000
}
```

#### 4. 提取元数据

```http
POST /api/v1/documents/{document_id}/extract/metadata
```

**响应**:

```json
{
  "title": "文档标题",
  "author": "作者名称",
  "subject": "主题",
  "keywords": ["关键词1", "关键词2"],
  "page_count": 10,
  "word_count": 5000,
  "created_at": "2024-01-01T00:00:00Z",
  "modified_at": "2024-01-10T00:00:00Z"
}
```

#### 5. 格式转换

```http
POST /api/v1/documents/{document_id}/convert
Content-Type: application/json
```

**请求体**:

```json
{
  "target_format": "docx",
  "options": {
    "preserve_formatting": true,
    "quality": "high"
  }
}
```

**响应**:

```json
{
  "id": "doc_789012",
  "source_id": "doc_123456",
  "target_format": "docx",
  "status": "completed",
  "download_url": "/api/v1/documents/doc_789012/download",
  "created_at": "2024-01-15T10:31:00Z",
  "completed_at": "2024-01-15T10:31:05Z"
}
```

#### 6. 下载文档

```http
GET /api/v1/documents/{document_id}/download
```

**响应**: 文件流

#### 7. 删除文档

```http
DELETE /api/v1/documents/{document_id}
```

**响应**:

```json
{
  "success": true,
  "message": "Document deleted successfully"
}
```

#### 8. 批量处理

```http
POST /api/v1/batch/process
Content-Type: application/json
```

**请求体**:

```json
{
  "documents": ["doc_1", "doc_2", "doc_3"],
  "operations": [
    {"type": "extract_text"},
    {"type": "extract_metadata"}
  ],
  "options": {
    "parallel": true,
    "max_workers": 3
  }
}
```

**响应**:

```json
{
  "batch_id": "batch_456",
  "status": "processing",
  "total": 3,
  "completed": 0,
  "failed": 0,
  "results_url": "/api/v1/batch/batch_456/results",
  "created_at": "2024-01-15T10:30:00Z"
}
```

#### 9. 列出 Skills

```http
GET /api/v1/skills
```

**响应**:

```json
{
  "skills": [
    {
      "name": "extract_text",
      "description": "提取文档文本",
      "version": "1.0.0",
      "input_schema": {...},
      "output_schema": {...}
    },
    {
      "name": "summarize",
      "description": "生成文档摘要",
      "version": "1.0.0",
      "input_schema": {...},
      "output_schema": {...}
    }
  ],
  "total": 10
}
```

#### 10. 执行 Skill

```http
POST /api/v1/documents/{document_id}/skills/{skill_name}
Content-Type: application/json
```

**请求体**:

```json
{
  "options": {
    "max_length": 500,
    "language": "zh"
  }
}
```

**响应**:

```json
{
  "success": true,
  "data": {
    "summary": "文档摘要内容..."
  },
  "metadata": {
    "execution_time": 1.5,
    "original_length": 5000,
    "summary_length": 500
  }
}
```

#### 11. 健康检查

```http
GET /health
```

**响应**:

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime": 3600,
  "components": {
    "processor": "healthy",
    "cache": "healthy",
    "database": "healthy"
  }
}
```

#### 12. 就绪检查

```http
GET /ready
```

**响应**:

```json
{
  "ready": true,
  "checks": {
    "processor": true,
    "cache": true,
    "database": true
  }
}
```

### 错误码

| 状态码 | 错误码 | 描述 |
|--------|--------|------|
| 400 | `INVALID_REQUEST` | 请求无效 |
| 400 | `UNSUPPORTED_FORMAT` | 不支持的格式 |
| 400 | `INVALID_DOCUMENT` | 文档无效 |
| 401 | `UNAUTHORIZED` | 未授权 |
| 403 | `FORBIDDEN` | 禁止访问 |
| 404 | `DOCUMENT_NOT_FOUND` | 文档不存在 |
| 413 | `FILE_TOO_LARGE` | 文件过大 |
| 422 | `PROCESSING_ERROR` | 处理错误 |
| 429 | `RATE_LIMITED` | 请求过于频繁 |
| 500 | `INTERNAL_ERROR` | 内部错误 |
| 503 | `SERVICE_UNAVAILABLE` | 服务不可用 |

---

## 配置选项

### 完整配置参考

```yaml
# ==================== 服务器配置 ====================
server:
  # 监听主机
  host: "0.0.0.0"

  # 监听端口
  port: 8080

  # 工作进程数
  workers: 4

  # 热重载（仅开发）
  reload: false

  # 日志级别: debug, info, warning, error, critical
  log_level: "info"

  # SSL配置
  ssl:
    enabled: false
    cert_file: "/path/to/cert.pem"
    key_file: "/path/to/key.pem"
    ca_file: "/path/to/ca.pem"

# ==================== 核心引擎配置 ====================
core:
  # 临时文件目录
  temp_dir: "/tmp/docmcp"

  # 最大文件大小 (MB)
  max_file_size: 100

  # 支持的格式
  supported_formats:
    - "docx"
    - "doc"
    - "pdf"
    - "xlsx"
    - "xls"
    - "pptx"
    - "ppt"
    - "txt"
    - "md"
    - "html"
    - "json"

  # 处理器配置
  handlers:
    pdf:
      # 启用OCR
      ocr_enabled: true
      # OCR语言
      ocr_language: ["chi_sim", "eng"]
      # 提取图片
      extract_images: true
      # DPI设置
      dpi: 300

    docx:
      # 保留格式
      preserve_formatting: true
      # 提取批注
      extract_comments: false
      # 提取修订
      extract_revisions: false

    excel:
      # 最大工作表数
      max_sheets: 100
      # 每页最大行数
      max_rows_per_sheet: 100000
      # 日期格式
      date_format: "%Y-%m-%d"

    pptx:
      # 提取备注
      extract_notes: false
      # 提取母版
      extract_master: false

# ==================== MCP协议配置 ====================
mcp:
  enabled: true

  # 协议版本
  protocol_version: "1.0"

  # 超时设置 (秒)
  timeout: 30

  # 最大并发连接
  max_connections: 100

  # 认证配置
  auth:
    enabled: true
    # 认证类型: jwt, api_key, oauth
    type: "jwt"
    # JWT密钥
    secret: "your-secret-key"
    # Token过期时间 (秒)
    token_expire: 3600
    # API密钥列表
    api_keys:
      - "key-1"
      - "key-2"

# ==================== Skills配置 ====================
skills:
  # Skills目录
  directory: "./skills"

  # 自动加载
  auto_load: true

  # 允许自定义Skills
  allow_custom: true

  # 执行超时 (秒)
  execution_timeout: 60

  # 最大并发执行数
  max_concurrent: 10

  # 预定义Skills
  builtin_skills:
    - "extract_text"
    - "extract_metadata"
    - "extract_tables"
    - "extract_images"
    - "convert_format"
    - "summarize"
    - "translate"
    - "classify"
    - "ocr"
    - "redact"

# ==================== 安全配置 ====================
security:
  # 沙箱配置
  sandbox:
    enabled: true
    # 沙箱类型: subprocess, docker, none
    type: "subprocess"
    # 执行超时 (秒)
    timeout: 300
    # 内存限制
    memory_limit: "512m"
    # CPU限制
    cpu_limit: "1.0"
    # 网络访问
    network_access: false

  # 权限配置
  permissions:
    file_read: true
    file_write: true
    network_access: false
    subprocess: false
    code_execution: false

  # 审计日志
  audit:
    enabled: true
    # 日志级别: debug, info, warning, error
    level: "info"
    # 存储类型: file, database, elasticsearch
    storage: "file"
    # 文件路径
    file_path: "/var/log/docmcp/audit.log"
    # 保留天数
    retention_days: 90
    # 敏感字段
    sensitive_fields:
      - "password"
      - "token"
      - "api_key"

# ==================== 性能配置 ====================
performance:
  # 缓存配置
  cache:
    enabled: true
    # 缓存类型: memory, redis, memcached
    type: "memory"
    # 缓存TTL (秒)
    ttl: 3600
    # 最大缓存项数
    max_size: 1000

    # Redis配置
    redis:
      host: "localhost"
      port: 6379
      db: 0
      password: ""
      ssl: false

    # Memcached配置
    memcached:
      servers:
        - "localhost:11211"
      timeout: 5

  # 连接池配置
  pool:
    enabled: true
    # 最小连接数
    min_size: 5
    # 最大连接数
    max_size: 20
    # 最大空闲时间 (秒)
    max_idle_time: 300
    # 连接超时 (秒)
    connection_timeout: 10

  # 监控配置
  monitoring:
    enabled: true
    # 指标端口
    metrics_port: 9090
    # 启用Prometheus
    prometheus_enabled: true
    # 采样率
    sample_rate: 1.0

# ==================== 存储配置 ====================
storage:
  # 存储类型: local, s3, azure, gcs
  type: "local"

  # 本地存储配置
  local:
    path: "/var/lib/docmcp/storage"

  # S3配置
  s3:
    bucket: "docmcp-bucket"
    region: "us-east-1"
    access_key: ""
    secret_key: ""
    endpoint: ""
    use_ssl: true

  # Azure Blob配置
  azure:
    account_name: ""
    account_key: ""
    container: "docmcp"

  # GCS配置
  gcs:
    project_id: ""
    bucket: "docmcp-bucket"
    credentials_path: ""

  # 数据库配置
  database:
    # 数据库类型: sqlite, postgresql, mysql
    type: "sqlite"

    # SQLite配置
    sqlite:
      path: "/var/lib/docmcp/docmcp.db"

    # PostgreSQL配置
    postgresql:
      host: "localhost"
      port: 5432
      database: "docmcp"
      username: "docmcp"
      password: "password"
      pool_size: 10
      max_overflow: 20

    # MySQL配置
    mysql:
      host: "localhost"
      port: 3306
      database: "docmcp"
      username: "docmcp"
      password: "password"
      pool_size: 10

# ==================== 日志配置 ====================
logging:
  # 日志级别
  level: "info"
  # 日志格式
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  # 日期格式
  date_format: "%Y-%m-%d %H:%M:%S"

  # 文件日志
  file:
    enabled: true
    path: "/var/log/docmcp/docmcp.log"
    max_size: "100MB"
    backup_count: 10
    encoding: "utf-8"

  # 控制台日志
  console:
    enabled: true
    color: true

  # 第三方日志级别
  loggers:
    uvicorn: "warning"
    sqlalchemy: "warning"
    asyncio: "warning"
```

---

## 更多资源

- [使用手册](./USAGE.md)
- [部署文档](./DEPLOYMENT.md)
- [架构设计](./ARCHITECTURE.md)
- [贡献指南](./CONTRIBUTING.md)
