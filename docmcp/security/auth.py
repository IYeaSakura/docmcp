"""
DocMCP 权限控制模块

提供基于角色的访问控制(RBAC)、细粒度权限管理和资源访问控制。
"""

import re
import hashlib
import secrets
import hmac
import time
import jwt
from typing import Dict, List, Optional, Set, Any, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from functools import wraps
from datetime import datetime, timedelta
import threading
import logging

logger = logging.getLogger(__name__)


class Permission(Enum):
    """权限枚举"""
    # 读取权限
    READ = "read"
    READ_OWN = "read:own"
    READ_ALL = "read:all"

    # 写入权限
    CREATE = "create"
    UPDATE = "update"
    UPDATE_OWN = "update:own"
    DELETE = "delete"
    DELETE_OWN = "delete:own"

    # 执行权限
    EXECUTE = "execute"
    EXECUTE_SANDBOX = "execute:sandbox"

    # 管理权限
    ADMIN = "admin"
    MANAGE_USERS = "manage:users"
    MANAGE_ROLES = "manage:roles"
    MANAGE_SYSTEM = "manage:system"

    # 特殊权限
    UPLOAD = "upload"
    DOWNLOAD = "download"
    SHARE = "share"


class Role(Enum):
    """角色枚举"""
    GUEST = "guest"
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"


# 角色权限映射
DEFAULT_ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.GUEST: {
        Permission.READ,
    },
    Role.USER: {
        Permission.READ,
        Permission.READ_OWN,
        Permission.CREATE,
        Permission.UPDATE_OWN,
        Permission.DELETE_OWN,
        Permission.EXECUTE,
        Permission.UPLOAD,
        Permission.DOWNLOAD,
        Permission.SHARE,
    },
    Role.MODERATOR: {
        Permission.READ,
        Permission.READ_OWN,
        Permission.READ_ALL,
        Permission.CREATE,
        Permission.UPDATE,
        Permission.UPDATE_OWN,
        Permission.DELETE_OWN,
        Permission.EXECUTE,
        Permission.EXECUTE_SANDBOX,
        Permission.UPLOAD,
        Permission.DOWNLOAD,
        Permission.SHARE,
    },
    Role.ADMIN: {
        Permission.READ,
        Permission.READ_OWN,
        Permission.READ_ALL,
        Permission.CREATE,
        Permission.UPDATE,
        Permission.UPDATE_OWN,
        Permission.DELETE,
        Permission.DELETE_OWN,
        Permission.EXECUTE,
        Permission.EXECUTE_SANDBOX,
        Permission.UPLOAD,
        Permission.DOWNLOAD,
        Permission.SHARE,
        Permission.MANAGE_USERS,
        Permission.MANAGE_ROLES,
    },
    Role.SUPERADMIN: set(Permission),  # 所有权限
}


@dataclass
class User:
    """用户对象"""
    id: str
    username: str
    email: str
    role: Role = Role.USER
    permissions: Set[Permission] = field(default_factory=set)
    is_active: bool = True
    is_locked: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    failed_login_attempts: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def has_permission(self, permission: Permission) -> bool:
        """检查用户是否有指定权限"""
        if not self.is_active or self.is_locked:
            return False

        # 检查直接权限
        if permission in self.permissions:
            return True

        # 检查角色权限
        role_perms = DEFAULT_ROLE_PERMISSIONS.get(self.role, set())
        return permission in role_perms

    def has_any_permission(self, permissions: List[Permission]) -> bool:
        """检查用户是否有任意一个指定权限"""
        return any(self.has_permission(p) for p in permissions)

    def has_all_permissions(self, permissions: List[Permission]) -> bool:
        """检查用户是否有所有指定权限"""
        return all(self.has_permission(p) for p in permissions)


@dataclass
class Resource:
    """资源对象"""
    id: str
    type: str
    owner_id: str
    permissions: Dict[str, Set[Permission]] = field(default_factory=dict)
    is_public: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def can_access(self, user: User, permission: Permission) -> bool:
        """检查用户是否可以访问资源"""
        # 公开资源允许读取
        if self.is_public and permission == Permission.READ:
            return True

        # 资源所有者检查
        if user.id == self.owner_id:
            if permission in [Permission.READ, Permission.UPDATE, Permission.DELETE]:
                return True

        # 检查用户角色权限
        user_perms = self.permissions.get(user.role.value, set())
        if permission in user_perms:
            return True

        # 检查用户特定权限
        user_perms = self.permissions.get(user.id, set())
        return permission in user_perms


class PasswordManager:
    """密码管理器"""

    def __init__(
        self,
        min_length: int = 8,
        require_uppercase: bool = True,
        require_lowercase: bool = True,
        require_digits: bool = True,
        require_special: bool = True
    ):
        """初始化密码管理器

        Args:
            min_length: 最小长度
            require_uppercase: 需要大写字母
            require_lowercase: 需要小写字母
            require_digits: 需要数字
            require_special: 需要特殊字符
        """
        self.min_length = min_length
        self.require_uppercase = require_uppercase
        self.require_lowercase = require_lowercase
        self.require_digits = require_digits
        self.require_special = require_special

    def validate_password(self, password: str) -> tuple[bool, List[str]]:
        """验证密码强度

        Args:
            password: 密码

        Returns:
            tuple: (是否有效, 错误信息列表)
        """
        errors = []

        if len(password) < self.min_length:
            errors.append(f"Password must be at least {self.min_length} characters long")

        if self.require_uppercase and not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")

        if self.require_lowercase and not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")

        if self.require_digits and not re.search(r'\d', password):
            errors.append("Password must contain at least one digit")

        if self.require_special and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("Password must contain at least one special character")

        return len(errors) == 0, errors

    def hash_password(self, password: str) -> str:
        """哈希密码

        Args:
            password: 明文密码

        Returns:
            str: 哈希后的密码
        """
        salt = secrets.token_hex(32)
        pwdhash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return salt + pwdhash.hex()

    def verify_password(self, password: str, hashed: str) -> bool:
        """验证密码

        Args:
            password: 明文密码
            hashed: 哈希后的密码

        Returns:
            bool: 是否匹配
        """
        salt = hashed[:64]
        pwdhash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return hmac.compare_digest(hashed[64:], pwdhash.hex())


class TokenManager:
    """令牌管理器"""

    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        access_token_expire: int = 24,  # 小时
        refresh_token_expire: int = 7   # 天
    ):
        """初始化令牌管理器

        Args:
            secret_key: JWT密钥
            algorithm: 加密算法
            access_token_expire: 访问令牌过期时间(小时)
            refresh_token_expire: 刷新令牌过期时间(天)
        """
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire = access_token_expire
        self.refresh_token_expire = refresh_token_expire

    def create_access_token(
        self,
        user_id: str,
        role: Role,
        permissions: Optional[List[Permission]] = None,
        extra_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """创建访问令牌

        Args:
            user_id: 用户ID
            role: 用户角色
            permissions: 额外权限
            extra_claims: 额外声明

        Returns:
            str: JWT令牌
        """
        now = datetime.utcnow()
        expire = now + timedelta(hours=self.access_token_expire)

        payload = {
            'sub': user_id,
            'role': role.value,
            'permissions': [p.value for p in (permissions or [])],
            'iat': now,
            'exp': expire,
            'type': 'access'
        }

        if extra_claims:
            payload.update(extra_claims)

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(self, user_id: str) -> str:
        """创建刷新令牌

        Args:
            user_id: 用户ID

        Returns:
            str: JWT刷新令牌
        """
        now = datetime.utcnow()
        expire = now + timedelta(days=self.refresh_token_expire)

        payload = {
            'sub': user_id,
            'iat': now,
            'exp': expire,
            'type': 'refresh'
        }

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        """解码令牌

        Args:
            token: JWT令牌

        Returns:
            Optional[Dict]: 解码后的载荷
        """
        try:
            return jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None

    def verify_token(self, token: str, token_type: str = 'access') -> Optional[Dict[str, Any]]:
        """验证令牌

        Args:
            token: JWT令牌
            token_type: 期望的令牌类型

        Returns:
            Optional[Dict]: 验证通过的载荷
        """
        payload = self.decode_token(token)

        if payload is None:
            return None

        if payload.get('type') != token_type:
            logger.warning(f"Invalid token type: expected {token_type}")
            return None

        return payload


class AuthManager:
    """认证管理器"""

    def __init__(
        self,
        secret_key: str,
        password_manager: Optional[PasswordManager] = None,
        token_manager: Optional[TokenManager] = None,
        max_login_attempts: int = 5,
        lockout_duration: int = 30  # 分钟
    ):
        """初始化认证管理器

        Args:
            secret_key: 密钥
            password_manager: 密码管理器
            token_manager: 令牌管理器
            max_login_attempts: 最大登录尝试次数
            lockout_duration: 锁定持续时间(分钟)
        """
        self.password_manager = password_manager or PasswordManager()
        self.token_manager = token_manager or TokenManager(secret_key)
        self.max_login_attempts = max_login_attempts
        self.lockout_duration = lockout_duration

        # 用户存储
        self._users: Dict[str, User] = {}
        self._passwords: Dict[str, str] = {}
        self._lock = threading.RLock()

    def register_user(
        self,
        username: str,
        email: str,
        password: str,
        role: Role = Role.USER
    ) -> tuple[bool, Optional[User], List[str]]:
        """注册用户

        Args:
            username: 用户名
            email: 邮箱
            password: 密码
            role: 角色

        Returns:
            tuple: (是否成功, 用户对象, 错误信息)
        """
        errors = []

        # 验证密码
        valid, pwd_errors = self.password_manager.validate_password(password)
        if not valid:
            errors.extend(pwd_errors)

        with self._lock:
            # 检查用户名
            if any(u.username == username for u in self._users.values()):
                errors.append("Username already exists")

            # 检查邮箱
            if any(u.email == email for u in self._users.values()):
                errors.append("Email already exists")

            if errors:
                return False, None, errors

            # 创建用户
            user_id = secrets.token_hex(16)
            user = User(
                id=user_id,
                username=username,
                email=email,
                role=role
            )

            # 存储用户
            self._users[user_id] = user
            self._passwords[user_id] = self.password_manager.hash_password(password)

            logger.info(f"User registered: {username} ({user_id})")

            return True, user, []

    def authenticate(
        self,
        username: str,
        password: str
    ) -> tuple[bool, Optional[Dict[str, str]], str]:
        """用户认证

        Args:
            username: 用户名
            password: 密码

        Returns:
            tuple: (是否成功, 令牌字典, 错误信息)
        """
        with self._lock:
            # 查找用户
            user = None
            for u in self._users.values():
                if u.username == username:
                    user = u
                    break

            if user is None:
                return False, None, "Invalid username or password"

            # 检查锁定
            if user.is_locked:
                return False, None, "Account is locked"

            # 验证密码
            stored_hash = self._passwords.get(user.id)
            if not stored_hash or not self.password_manager.verify_password(password, stored_hash):
                user.failed_login_attempts += 1

                # 锁定账户
                if user.failed_login_attempts >= self.max_login_attempts:
                    user.is_locked = True
                    logger.warning(f"User locked due to too many failed attempts: {username}")
                    return False, None, "Account locked due to too many failed attempts"

                return False, None, "Invalid username or password"

            # 重置失败计数
            user.failed_login_attempts = 0
            user.last_login = datetime.now()

            # 创建令牌
            tokens = {
                'access_token': self.token_manager.create_access_token(user.id, user.role),
                'refresh_token': self.token_manager.create_refresh_token(user.id),
                'token_type': 'Bearer'
            }

            logger.info(f"User authenticated: {username}")

            return True, tokens, ""

    def get_user(self, user_id: str) -> Optional[User]:
        """获取用户"""
        with self._lock:
            return self._users.get(user_id)

    def get_user_by_token(self, token: str) -> Optional[User]:
        """通过令牌获取用户"""
        payload = self.token_manager.verify_token(token)
        if payload is None:
            return None

        user_id = payload.get('sub')
        return self.get_user(user_id) if user_id else None

    def change_password(
        self,
        user_id: str,
        old_password: str,
        new_password: str
    ) -> tuple[bool, List[str]]:
        """修改密码"""
        with self._lock:
            user = self._users.get(user_id)
            if user is None:
                return False, ["User not found"]

            stored_hash = self._passwords.get(user_id)
            if not stored_hash or not self.password_manager.verify_password(old_password, stored_hash):
                return False, ["Invalid old password"]

            # 验证新密码
            valid, errors = self.password_manager.validate_password(new_password)
            if not valid:
                return False, errors

            # 更新密码
            self._passwords[user_id] = self.password_manager.hash_password(new_password)

            logger.info(f"Password changed for user: {user_id}")

            return True, []

    def unlock_user(self, user_id: str) -> bool:
        """解锁用户"""
        with self._lock:
            user = self._users.get(user_id)
            if user is None:
                return False

            user.is_locked = False
            user.failed_login_attempts = 0

            logger.info(f"User unlocked: {user_id}")

            return True


class PermissionChecker:
    """权限检查器"""

    def __init__(self, auth_manager: AuthManager):
        """初始化权限检查器

        Args:
            auth_manager: 认证管理器
        """
        self.auth_manager = auth_manager

    def check_permission(
        self,
        token: str,
        permission: Permission,
        resource: Optional[Resource] = None
    ) -> bool:
        """检查权限

        Args:
            token: 访问令牌
            permission: 需要权限
            resource: 资源对象

        Returns:
            bool: 是否有权限
        """
        user = self.auth_manager.get_user_by_token(token)
        if user is None:
            return False

        # 检查用户权限
        if not user.has_permission(permission):
            return False

        # 检查资源权限
        if resource is not None:
            return resource.can_access(user, permission)

        return True

    def require_permission(self, permission: Permission):
        """权限要求装饰器

        Args:
            permission: 需要的权限

        Returns:
            Callable: 装饰器函数
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # 从上下文中获取token
                token = kwargs.get('token') or (args[0] if args else None)

                if not isinstance(token, str):
                    raise PermissionError("Authentication required")

                if not self.check_permission(token, permission):
                    raise PermissionError(f"Permission denied: {permission.value}")

                return func(*args, **kwargs)

            return wrapper
        return decorator


# 便捷函数
def create_auth_manager(secret_key: str) -> AuthManager:
    """创建认证管理器的便捷函数"""
    return AuthManager(secret_key=secret_key)


def require_auth(permission: Permission):
    """认证要求装饰器的便捷函数"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 这里假设有一个全局的auth_manager
            # 实际使用时应该注入
            raise PermissionError("Global auth manager not configured")
        return wrapper
    return decorator
