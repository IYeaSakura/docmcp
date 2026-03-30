"""
Security module tests.

This module tests:
- Authentication (AuthManager, TokenManager, PasswordManager)
- Authorization (Permission, Role, User, Resource)
- Sandbox execution
- Security utilities
"""

import pytest
import time
from datetime import datetime, timedelta

from docmcp.security.auth import (
    AuthManager,
    User,
    Role,
    Permission,
    Resource,
    PasswordManager,
    TokenManager,
    PermissionChecker,
    DEFAULT_ROLE_PERMISSIONS,
)
from docmcp.security.sandbox import (
    SandboxExecutor,
    SandboxResult,
    SandboxStatus,
    ResourceLimits,
    sandbox_context,
    safe_execute,
    create_restricted_environment,
)


# ============================================================================
# Permission Tests
# ============================================================================

class TestPermission:
    """Test Permission enum."""

    def test_permission_values(self):
        """Test permission values."""
        assert Permission.READ.value == "read"
        assert Permission.READ_OWN.value == "read:own"
        assert Permission.READ_ALL.value == "read:all"
        assert Permission.CREATE.value == "create"
        assert Permission.UPDATE.value == "update"
        assert Permission.DELETE.value == "delete"
        assert Permission.EXECUTE.value == "execute"
        assert Permission.ADMIN.value == "admin"
        assert Permission.UPLOAD.value == "upload"
        assert Permission.DOWNLOAD.value == "download"
        assert Permission.SHARE.value == "share"


# ============================================================================
# Role Tests
# ============================================================================

class TestRole:
    """Test Role enum."""

    def test_role_values(self):
        """Test role values."""
        assert Role.GUEST.value == "guest"
        assert Role.USER.value == "user"
        assert Role.MODERATOR.value == "moderator"
        assert Role.ADMIN.value == "admin"
        assert Role.SUPERADMIN.value == "superadmin"


# ============================================================================
# Default Role Permissions Tests
# ============================================================================

class TestDefaultRolePermissions:
    """Test default role permissions mapping."""

    def test_guest_permissions(self):
        """Test guest role permissions."""
        perms = DEFAULT_ROLE_PERMISSIONS[Role.GUEST]
        assert Permission.READ in perms
        assert Permission.CREATE not in perms
        assert Permission.DELETE not in perms

    def test_user_permissions(self):
        """Test user role permissions."""
        perms = DEFAULT_ROLE_PERMISSIONS[Role.USER]
        assert Permission.READ in perms
        assert Permission.READ_OWN in perms
        assert Permission.CREATE in perms
        assert Permission.UPDATE_OWN in perms
        assert Permission.DELETE_OWN in perms
        assert Permission.EXECUTE in perms
        assert Permission.UPLOAD in perms
        assert Permission.DOWNLOAD in perms
        assert Permission.ADMIN not in perms

    def test_admin_permissions(self):
        """Test admin role permissions."""
        perms = DEFAULT_ROLE_PERMISSIONS[Role.ADMIN]
        assert Permission.READ in perms
        assert Permission.READ_ALL in perms
        assert Permission.CREATE in perms
        assert Permission.UPDATE in perms
        assert Permission.DELETE in perms
        assert Permission.MANAGE_USERS in perms
        assert Permission.MANAGE_ROLES in perms

    def test_superadmin_permissions(self):
        """Test superadmin role permissions."""
        perms = DEFAULT_ROLE_PERMISSIONS[Role.SUPERADMIN]
        # Superadmin has all permissions
        assert len(perms) == len(Permission)
        for perm in Permission:
            assert perm in perms


# ============================================================================
# User Tests
# ============================================================================

class TestUser:
    """Test User class."""

    def test_user_creation(self):
        """Test user creation."""
        user = User(
            id="user-123",
            username="testuser",
            email="test@example.com",
            role=Role.USER,
        )
        assert user.id == "user-123"
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.role == Role.USER
        assert user.is_active is True
        assert user.is_locked is False

    def test_has_permission_direct(self):
        """Test direct permission check."""
        user = User(
            id="user-123",
            username="testuser",
            email="test@example.com",
            permissions={Permission.ADMIN},
        )
        assert user.has_permission(Permission.ADMIN) is True
        assert user.has_permission(Permission.READ) is False

    def test_has_permission_via_role(self):
        """Test permission check via role."""
        user = User(
            id="user-123",
            username="testuser",
            email="test@example.com",
            role=Role.USER,
        )
        # User role has READ permission
        assert user.has_permission(Permission.READ) is True
        assert user.has_permission(Permission.ADMIN) is False

    def test_has_permission_inactive_user(self):
        """Test permission check for inactive user."""
        user = User(
            id="user-123",
            username="testuser",
            email="test@example.com",
            role=Role.USER,
            is_active=False,
        )
        assert user.has_permission(Permission.READ) is False

    def test_has_permission_locked_user(self):
        """Test permission check for locked user."""
        user = User(
            id="user-123",
            username="testuser",
            email="test@example.com",
            role=Role.USER,
            is_locked=True,
        )
        assert user.has_permission(Permission.READ) is False

    def test_has_any_permission(self):
        """Test has_any_permission method."""
        user = User(
            id="user-123",
            username="testuser",
            email="test@example.com",
            role=Role.USER,
        )
        assert user.has_any_permission([Permission.READ, Permission.ADMIN]) is True
        assert user.has_any_permission([Permission.ADMIN, Permission.MANAGE_SYSTEM]) is False

    def test_has_all_permissions(self):
        """Test has_all_permissions method."""
        user = User(
            id="user-123",
            username="testuser",
            email="test@example.com",
            role=Role.USER,
        )
        assert user.has_all_permissions([Permission.READ, Permission.CREATE]) is True
        assert user.has_all_permissions([Permission.READ, Permission.ADMIN]) is False


# ============================================================================
# Resource Tests
# ============================================================================

class TestResource:
    """Test Resource class."""

    def test_resource_creation(self):
        """Test resource creation."""
        resource = Resource(
            id="res-123",
            type="document",
            owner_id="user-123",
        )
        assert resource.id == "res-123"
        assert resource.type == "document"
        assert resource.owner_id == "user-123"
        assert resource.is_public is False

    def test_can_access_public_resource(self):
        """Test access to public resource."""
        resource = Resource(
            id="res-123",
            type="document",
            owner_id="user-123",
            is_public=True,
        )
        user = User(id="user-456", username="other", email="other@example.com")

        # Anyone can read public resource
        assert resource.can_access(user, Permission.READ) is True
        # But not modify it
        assert resource.can_access(user, Permission.UPDATE) is False

    def test_can_access_owner(self):
        """Test owner access to resource."""
        resource = Resource(
            id="res-123",
            type="document",
            owner_id="user-123",
        )
        owner = User(id="user-123", username="owner", email="owner@example.com")

        # Owner has full access
        assert resource.can_access(owner, Permission.READ) is True
        assert resource.can_access(owner, Permission.UPDATE) is True
        assert resource.can_access(owner, Permission.DELETE) is True

    def test_can_access_via_permissions(self):
        """Test access via resource permissions."""
        resource = Resource(
            id="res-123",
            type="document",
            owner_id="user-123",
            permissions={
                "user": {Permission.READ},
            },
        )
        user = User(
            id="user-456",
            username="reader",
            email="reader@example.com",
            role=Role.USER,
        )

        # User role has READ permission on this resource
        assert resource.can_access(user, Permission.READ) is True
        assert resource.can_access(user, Permission.UPDATE) is False


# ============================================================================
# PasswordManager Tests
# ============================================================================

class TestPasswordManager:
    """Test PasswordManager class."""

    def test_password_validation_valid(self):
        """Test valid password validation."""
        manager = PasswordManager()
        valid, errors = manager.validate_password("ValidP@ss123")
        assert valid is True
        assert errors == []

    def test_password_validation_too_short(self):
        """Test password too short."""
        manager = PasswordManager(min_length=8)
        valid, errors = manager.validate_password("Short1!")
        assert valid is False
        assert any("8 characters" in e for e in errors)

    def test_password_validation_no_uppercase(self):
        """Test password without uppercase."""
        manager = PasswordManager()
        valid, errors = manager.validate_password("lowercase1!")
        assert valid is False
        assert any("uppercase" in e for e in errors)

    def test_password_validation_no_lowercase(self):
        """Test password without lowercase."""
        manager = PasswordManager()
        valid, errors = manager.validate_password("UPPERCASE1!")
        assert valid is False
        assert any("lowercase" in e for e in errors)

    def test_password_validation_no_digit(self):
        """Test password without digit."""
        manager = PasswordManager()
        valid, errors = manager.validate_password("NoDigits!!")
        assert valid is False
        assert any("digit" in e for e in errors)

    def test_password_validation_no_special(self):
        """Test password without special character."""
        manager = PasswordManager()
        valid, errors = manager.validate_password("NoSpecial123")
        assert valid is False
        assert any("special" in e for e in errors)

    def test_password_hashing(self):
        """Test password hashing."""
        manager = PasswordManager()
        password = "TestP@ss123"
        hashed = manager.hash_password(password)

        assert hashed != password
        assert len(hashed) > len(password)

    def test_password_verification_valid(self):
        """Test valid password verification."""
        manager = PasswordManager()
        password = "TestP@ss123"
        hashed = manager.hash_password(password)

        assert manager.verify_password(password, hashed) is True

    def test_password_verification_invalid(self):
        """Test invalid password verification."""
        manager = PasswordManager()
        password = "TestP@ss123"
        hashed = manager.hash_password(password)

        assert manager.verify_password("WrongP@ss123", hashed) is False

    def test_password_hash_uniqueness(self):
        """Test that same password produces different hashes."""
        manager = PasswordManager()
        password = "TestP@ss123"

        hash1 = manager.hash_password(password)
        hash2 = manager.hash_password(password)

        # Hashes should be different due to salt
        assert hash1 != hash2
        # But both should verify correctly
        assert manager.verify_password(password, hash1) is True
        assert manager.verify_password(password, hash2) is True


# ============================================================================
# TokenManager Tests
# ============================================================================

class TestTokenManager:
    """Test TokenManager class."""

    def test_access_token_creation(self):
        """Test access token creation."""
        manager = TokenManager(secret_key="test-secret")
        token = manager.create_access_token(
            user_id="user-123",
            role=Role.USER,
        )

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_access_token_with_permissions(self):
        """Test access token with permissions."""
        manager = TokenManager(secret_key="test-secret")
        token = manager.create_access_token(
            user_id="user-123",
            role=Role.USER,
            permissions=[Permission.READ, Permission.CREATE],
        )

        payload = manager.decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["role"] == "user"
        assert "read" in payload["permissions"]
        assert "create" in payload["permissions"]

    def test_refresh_token_creation(self):
        """Test refresh token creation."""
        manager = TokenManager(secret_key="test-secret")
        token = manager.create_refresh_token(user_id="user-123")

        assert token is not None

        payload = manager.decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["type"] == "refresh"

    def test_token_decoding(self):
        """Test token decoding."""
        manager = TokenManager(secret_key="test-secret")
        token = manager.create_access_token("user-123", Role.USER)

        payload = manager.decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user-123"

    def test_token_decoding_invalid(self):
        """Test decoding invalid token."""
        manager = TokenManager(secret_key="test-secret")

        payload = manager.decode_token("invalid-token")
        assert payload is None

    def test_token_verification(self):
        """Test token verification."""
        manager = TokenManager(secret_key="test-secret")
        token = manager.create_access_token("user-123", Role.USER)

        payload = manager.verify_token(token, token_type="access")
        assert payload is not None
        assert payload["type"] == "access"

    def test_token_verification_wrong_type(self):
        """Test token verification with wrong type."""
        manager = TokenManager(secret_key="test-secret")
        token = manager.create_access_token("user-123", Role.USER)

        # Try to verify access token as refresh token
        payload = manager.verify_token(token, token_type="refresh")
        assert payload is None

    def test_token_expiration(self):
        """Test token expiration."""
        # Create manager with very short expiration
        manager = TokenManager(
            secret_key="test-secret",
            access_token_expire=0,  # Expires immediately
        )
        token = manager.create_access_token("user-123", Role.USER)

        # Token should be expired
        payload = manager.decode_token(token)
        assert payload is None  # decode_token returns None for expired tokens


# ============================================================================
# AuthManager Tests
# ============================================================================

class TestAuthManager:
    """Test AuthManager class."""

    def test_user_registration_success(self):
        """Test successful user registration."""
        auth = AuthManager(secret_key="test-secret")
        success, user, errors = auth.register_user(
            username="testuser",
            email="test@example.com",
            password="ValidP@ss123",
        )

        assert success is True
        assert user is not None
        assert user.username == "testuser"
        assert errors == []

    def test_user_registration_duplicate_username(self):
        """Test registration with duplicate username."""
        auth = AuthManager(secret_key="test-secret")
        auth.register_user("testuser", "test1@example.com", "ValidP@ss123")

        success, user, errors = auth.register_user(
            username="testuser",
            email="test2@example.com",
            password="ValidP@ss123",
        )

        assert success is False
        assert user is None
        assert any("Username already exists" in e for e in errors)

    def test_user_registration_duplicate_email(self):
        """Test registration with duplicate email."""
        auth = AuthManager(secret_key="test-secret")
        auth.register_user("user1", "test@example.com", "ValidP@ss123")

        success, user, errors = auth.register_user(
            username="user2",
            email="test@example.com",
            password="ValidP@ss123",
        )

        assert success is False
        assert any("Email already exists" in e for e in errors)

    def test_user_registration_weak_password(self):
        """Test registration with weak password."""
        auth = AuthManager(secret_key="test-secret")

        success, user, errors = auth.register_user(
            username="testuser",
            email="test@example.com",
            password="weak",
        )

        assert success is False
        assert len(errors) > 0

    def test_authentication_success(self):
        """Test successful authentication."""
        auth = AuthManager(secret_key="test-secret")
        auth.register_user("testuser", "test@example.com", "ValidP@ss123")

        success, tokens, error = auth.authenticate("testuser", "ValidP@ss123")

        assert success is True
        assert tokens is not None
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert error == ""

    def test_authentication_invalid_username(self):
        """Test authentication with invalid username."""
        auth = AuthManager(secret_key="test-secret")

        success, tokens, error = auth.authenticate("nonexistent", "password")

        assert success is False
        assert tokens is None
        assert "Invalid" in error

    def test_authentication_invalid_password(self):
        """Test authentication with invalid password."""
        auth = AuthManager(secret_key="test-secret")
        auth.register_user("testuser", "test@example.com", "ValidP@ss123")

        success, tokens, error = auth.authenticate("testuser", "WrongP@ss123")

        assert success is False
        assert "Invalid" in error

    def test_authentication_account_lockout(self):
        """Test account lockout after failed attempts."""
        auth = AuthManager(
            secret_key="test-secret",
            max_login_attempts=3,
        )
        auth.register_user("testuser", "test@example.com", "ValidP@ss123")

        # Fail authentication 3 times
        for _ in range(3):
            auth.authenticate("testuser", "WrongP@ss123")

        # Account should be locked
        success, tokens, error = auth.authenticate("testuser", "ValidP@ss123")
        assert success is False
        assert "locked" in error.lower()

    def test_get_user(self):
        """Test getting user by ID."""
        auth = AuthManager(secret_key="test-secret")
        _, user, _ = auth.register_user("testuser", "test@example.com", "ValidP@ss123")

        retrieved = auth.get_user(user.id)
        assert retrieved is not None
        assert retrieved.username == "testuser"

    def test_get_user_by_token(self):
        """Test getting user by token."""
        auth = AuthManager(secret_key="test-secret")
        _, user, _ = auth.register_user("testuser", "test@example.com", "ValidP@ss123")
        success, tokens, _ = auth.authenticate("testuser", "ValidP@ss123")

        retrieved = auth.get_user_by_token(tokens["access_token"])
        assert retrieved is not None
        assert retrieved.id == user.id

    def test_change_password_success(self):
        """Test successful password change."""
        auth = AuthManager(secret_key="test-secret")
        _, user, _ = auth.register_user("testuser", "test@example.com", "ValidP@ss123")

        success, errors = auth.change_password(
            user.id,
            "ValidP@ss123",
            "NewP@ss123!",
        )

        assert success is True
        assert errors == []

        # Should be able to authenticate with new password
        success, _, _ = auth.authenticate("testuser", "NewP@ss123!")
        assert success is True

    def test_change_password_invalid_old(self):
        """Test password change with invalid old password."""
        auth = AuthManager(secret_key="test-secret")
        _, user, _ = auth.register_user("testuser", "test@example.com", "ValidP@ss123")

        success, errors = auth.change_password(
            user.id,
            "WrongP@ss123",
            "NewP@ss123!",
        )

        assert success is False
        assert any("Invalid old password" in e for e in errors)

    def test_unlock_user(self):
        """Test unlocking a user."""
        auth = AuthManager(secret_key="test-secret", max_login_attempts=1)
        _, user, _ = auth.register_user("testuser", "test@example.com", "ValidP@ss123")

        # Lock the account
        auth.authenticate("testuser", "wrong")
        assert user.is_locked is True

        # Unlock
        success = auth.unlock_user(user.id)
        assert success is True
        assert user.is_locked is False
        assert user.failed_login_attempts == 0


# ============================================================================
# PermissionChecker Tests
# ============================================================================

class TestPermissionChecker:
    """Test PermissionChecker class."""

    def test_check_permission_success(self):
        """Test successful permission check."""
        auth = AuthManager(secret_key="test-secret")
        _, user, _ = auth.register_user("testuser", "test@example.com", "ValidP@ss123")
        success, tokens, _ = auth.authenticate("testuser", "ValidP@ss123")

        checker = PermissionChecker(auth)
        result = checker.check_permission(tokens["access_token"], Permission.READ)

        assert result is True

    def test_check_permission_invalid_token(self):
        """Test permission check with invalid token."""
        auth = AuthManager(secret_key="test-secret")
        checker = PermissionChecker(auth)

        result = checker.check_permission("invalid-token", Permission.READ)
        assert result is False

    def test_check_permission_insufficient(self):
        """Test permission check with insufficient permissions."""
        auth = AuthManager(secret_key="test-secret")
        _, user, _ = auth.register_user("testuser", "test@example.com", "ValidP@ss123")
        success, tokens, _ = auth.authenticate("testuser", "ValidP@ss123")

        checker = PermissionChecker(auth)
        # User role doesn't have ADMIN permission
        result = checker.check_permission(tokens["access_token"], Permission.ADMIN)

        assert result is False

    def test_check_permission_with_resource(self):
        """Test permission check with resource."""
        auth = AuthManager(secret_key="test-secret")
        _, user, _ = auth.register_user("testuser", "test@example.com", "ValidP@ss123")
        success, tokens, _ = auth.authenticate("testuser", "ValidP@ss123")

        resource = Resource(
            id="res-123",
            type="document",
            owner_id=user.id,  # User owns the resource
        )

        checker = PermissionChecker(auth)
        result = checker.check_permission(
            tokens["access_token"],
            Permission.READ,
            resource,
        )

        assert result is True


# ============================================================================
# SandboxExecutor Tests
# ============================================================================

class TestSandboxExecutor:
    """Test SandboxExecutor class."""

    def test_sandbox_creation(self):
        """Test sandbox creation."""
        executor = SandboxExecutor()
        assert executor.temp_dir is not None
        assert executor.network_enabled is False

    def test_sandbox_with_limits(self):
        """Test sandbox with resource limits."""
        limits = ResourceLimits(
            max_memory_mb=256,
            max_execution_time=10.0,
        )
        executor = SandboxExecutor(resource_limits=limits)

        assert executor.resource_limits.max_memory_mb == 256
        assert executor.resource_limits.max_execution_time == 10.0

    def test_execute_code_success(self):
        """Test successful code execution."""
        executor = SandboxExecutor()
        result = executor.execute_code('print("Hello, World!")')

        assert result.status == SandboxStatus.COMPLETED
        assert "Hello, World!" in result.stdout
        assert result.return_code == 0

    def test_execute_code_with_error(self):
        """Test code execution with error."""
        executor = SandboxExecutor()
        result = executor.execute_code('raise ValueError("Test error")')

        assert result.status == SandboxStatus.COMPLETED  # Process completed
        assert result.return_code != 0  # But with error
        assert "ValueError" in result.stderr

    def test_execute_code_timeout(self):
        """Test code execution timeout."""
        executor = SandboxExecutor(
            resource_limits=ResourceLimits(max_execution_time=0.1)
        )
        result = executor.execute_code('import time; time.sleep(10)')

        assert result.status == SandboxStatus.TIMEOUT
        assert "timeout" in result.error_message.lower()

    def test_execute_command(self):
        """Test command execution."""
        executor = SandboxExecutor()
        result = executor.execute_command(["echo", "Hello"])

        assert result.status == SandboxStatus.COMPLETED
        assert "Hello" in result.stdout

    def test_execute_command_with_input(self):
        """Test command execution with input."""
        executor = SandboxExecutor()
        result = executor.execute_command(
            ["cat"],
            input_data="Hello, World!",
        )

        assert result.status == SandboxStatus.COMPLETED
        assert "Hello, World!" in result.stdout

    def test_kill_all(self):
        """Test killing all processes."""
        executor = SandboxExecutor()
        # Just test that it doesn't raise
        count = executor.kill_all()
        assert isinstance(count, int)

    def test_cleanup(self):
        """Test sandbox cleanup."""
        executor = SandboxExecutor()
        temp_dir = executor.temp_dir

        executor.cleanup()

        # Temp directory should be removed
        import os
        assert not os.path.exists(temp_dir)


# ============================================================================
# Sandbox Context Tests
# ============================================================================

class TestSandboxContext:
    """Test sandbox_context context manager."""

    def test_context_manager(self):
        """Test context manager usage."""
        with sandbox_context(max_memory_mb=128, max_execution_time=5.0) as sandbox:
            result = sandbox.execute_code('print("Test")')
            assert result.status == SandboxStatus.COMPLETED

    def test_context_manager_cleanup(self):
        """Test automatic cleanup."""
        temp_dir = None
        with sandbox_context() as sandbox:
            temp_dir = sandbox.temp_dir
            import os
            assert os.path.exists(temp_dir)

        # Should be cleaned up after exit
        import os
        assert not os.path.exists(temp_dir)


# ============================================================================
# Safe Execute Tests
# ============================================================================

class TestSafeExecute:
    """Test safe_execute function."""

    def test_safe_execute_success(self):
        """Test successful safe execution."""
        result = safe_execute('print("Hello")', timeout=5.0)

        assert result.status == SandboxStatus.COMPLETED
        assert "Hello" in result.stdout

    def test_safe_execute_timeout(self):
        """Test safe execution timeout."""
        result = safe_execute(
            'import time; time.sleep(10)',
            timeout=0.1,
        )

        assert result.status == SandboxStatus.TIMEOUT


# ============================================================================
# Restricted Environment Tests
# ============================================================================

class TestRestrictedEnvironment:
    """Test create_restricted_environment function."""

    def test_restricted_environment_creation(self):
        """Test restricted environment creation."""
        env = create_restricted_environment()

        assert "__builtins__" in env
        assert "math" in env

    def test_restricted_environment_blocked_builtins(self):
        """Test blocked builtins in restricted environment."""
        env = create_restricted_environment()
        builtins = env["__builtins__"]

        # These should be blocked
        assert "__import__" not in builtins
        assert "open" not in builtins
        assert "exec" not in builtins
        assert "eval" not in builtins


# ============================================================================
# Integration Tests
# ============================================================================

class TestSecurityIntegration:
    """Integration tests for security module."""

    def test_full_authentication_flow(self):
        """Test complete authentication flow."""
        auth = AuthManager(secret_key="test-secret")

        # Register
        success, user, errors = auth.register_user(
            "testuser",
            "test@example.com",
            "ValidP@ss123",
        )
        assert success is True

        # Authenticate
        success, tokens, error = auth.authenticate("testuser", "ValidP@ss123")
        assert success is True

        # Verify token
        retrieved_user = auth.get_user_by_token(tokens["access_token"])
        assert retrieved_user.id == user.id

        # Check permission
        checker = PermissionChecker(auth)
        has_perm = checker.check_permission(
            tokens["access_token"],
            Permission.READ,
        )
        assert has_perm is True

    def test_role_based_access_control(self):
        """Test role-based access control."""
        auth = AuthManager(secret_key="test-secret")

        # Create admin user
        _, admin, _ = auth.register_user(
            "admin",
            "admin@example.com",
            "AdminP@ss123",
            role=Role.ADMIN,
        )

        # Create regular user
        _, user, _ = auth.register_user(
            "user",
            "user@example.com",
            "UserP@ss123",
            role=Role.USER,
        )

        # Admin should have more permissions
        assert admin.has_permission(Permission.MANAGE_USERS) is True
        assert user.has_permission(Permission.MANAGE_USERS) is False

    def test_resource_protection(self):
        """Test resource protection."""
        # Create owner and resource
        owner = User(id="owner-123", username="owner", email="owner@example.com")
        resource = Resource(
            id="doc-123",
            type="document",
            owner_id="owner-123",
        )

        # Owner should have access
        assert resource.can_access(owner, Permission.READ) is True
        assert resource.can_access(owner, Permission.UPDATE) is True

        # Other user should not
        other = User(id="other-123", username="other", email="other@example.com")
        assert resource.can_access(other, Permission.READ) is False
        assert resource.can_access(other, Permission.UPDATE) is False
