"""
DocMCP 安全模块

提供安全相关的功能，包括沙箱执行、权限控制、内容扫描和审计日志。
"""

from .sandbox import (
    SandboxExecutor,
    AsyncSandboxExecutor,
    SandboxResult,
    SandboxStatus,
    ResourceLimits,
    sandbox_context,
    create_restricted_environment,
    safe_execute,
)

from .auth import (
    AuthManager,
    TokenManager,
    PasswordManager,
    PermissionChecker,
    User,
    Resource,
    Permission,
    Role,
    create_auth_manager,
)

from .scanner import (
    ContentScanner,
    RealtimeScanner,
    ScanResult,
    ScanResultStatus,
    Threat,
    ThreatType,
    FileTypeValidator,
    quick_scan,
    scan_text,
    is_safe,
)

from .audit import (
    AuditLogger,
    AuditEvent,
    AuditEventType,
    AuditLevel,
    AuditConfig,
    get_audit_logger,
    log_event,
    log_login,
    log_access_denied,
)

__all__ = [
    # 沙箱
    'SandboxExecutor',
    'AsyncSandboxExecutor',
    'SandboxResult',
    'SandboxStatus',
    'ResourceLimits',
    'sandbox_context',
    'create_restricted_environment',
    'safe_execute',
    
    # 认证
    'AuthManager',
    'TokenManager',
    'PasswordManager',
    'PermissionChecker',
    'User',
    'Resource',
    'Permission',
    'Role',
    'create_auth_manager',
    
    # 扫描
    'ContentScanner',
    'RealtimeScanner',
    'ScanResult',
    'ScanResultStatus',
    'Threat',
    'ThreatType',
    'FileTypeValidator',
    'quick_scan',
    'scan_text',
    'is_safe',
    
    # 审计
    'AuditLogger',
    'AuditEvent',
    'AuditEventType',
    'AuditLevel',
    'AuditConfig',
    'get_audit_logger',
    'log_event',
    'log_login',
    'log_access_denied',
]
