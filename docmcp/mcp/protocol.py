"""
MCP (Model Context Protocol) protocol implementation.

This module defines the core protocol structures for MCP communication,
including message formats, error codes, and capability definitions.

The Model Context Protocol enables standardized communication between:
    - AI models (clients)
    - Document processing services (servers)

Protocol Features:
    - JSON-RPC 2.0 inspired message format
    - Request/Response correlation via IDs
    - Batch request support
    - Error handling with structured codes
    - Capability negotiation
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Union


class MCPErrorCode(Enum):
    """
    MCP protocol error codes.

    These error codes follow JSON-RPC 2.0 conventions with MCP-specific
    extensions for document processing scenarios.
    """

    # Standard JSON-RPC errors
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    # MCP-specific errors
    DOCUMENT_NOT_FOUND = -32001
    DOCUMENT_INVALID = -32002
    PROCESSING_FAILED = -32003
    TIMEOUT = -32004
    UNAUTHORIZED = -32005
    RATE_LIMITED = -32006
    UNSUPPORTED_FORMAT = -32007
    SANDBOX_ERROR = -32008
    SKILL_NOT_FOUND = -32009
    SKILL_EXECUTION_FAILED = -32010


class MCPMethod(Enum):
    """
    Standard MCP protocol methods.

    These methods define the core operations supported by MCP servers.
    """

    # Document operations
    PROCESS_DOCUMENT = "process_document"
    EXTRACT_CONTENT = "extract_content"
    CONVERT_FORMAT = "convert_format"
    VALIDATE_DOCUMENT = "validate_document"
    GET_DOCUMENT_INFO = "get_document_info"

    # Skill operations
    LIST_SKILLS = "list_skills"
    EXECUTE_SKILL = "execute_skill"
    GET_SKILL_INFO = "get_skill_info"

    # Context operations
    GET_CONTEXT = "get_context"
    SET_CONTEXT = "set_context"
    CLEAR_CONTEXT = "clear_context"

    # Server operations
    GET_CAPABILITIES = "get_capabilities"
    HEALTH_CHECK = "health_check"
    GET_METRICS = "get_metrics"


@dataclass
class MCPCapability:
    """
    MCP server capability descriptor.

    Describes a capability that an MCP server provides, including
    its name, version, and configuration options.

    Attributes:
        name: Capability name
        version: Capability version (semver)
        description: Human-readable description
        options: Capability-specific options
    """

    name: str
    version: str = "1.0.0"
    description: str = ""
    options: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "options": self.options,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MCPCapability:
        """Create from dictionary."""
        return cls(
            name=data["name"],
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            options=data.get("options", {}),
        )


@dataclass
class MCPError:
    """
    MCP protocol error.

    Represents an error that occurred during MCP communication.

    Attributes:
        code: Error code
        message: Human-readable error message
        data: Additional error data
    """

    code: int
    message: str
    data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        error = {
            "code": self.code,
            "message": self.message,
        }
        if self.data:
            error["data"] = self.data
        return error

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MCPError:
        """Create from dictionary."""
        return cls(
            code=data["code"],
            message=data["message"],
            data=data.get("data"),
        )

    @classmethod
    def parse_error(cls, message: str = "Parse error") -> MCPError:
        """Create a parse error."""
        return cls(code=MCPErrorCode.PARSE_ERROR.value, message=message)

    @classmethod
    def invalid_request(cls, message: str = "Invalid request") -> MCPError:
        """Create an invalid request error."""
        return cls(code=MCPErrorCode.INVALID_REQUEST.value, message=message)

    @classmethod
    def method_not_found(cls, method: str) -> MCPError:
        """Create a method not found error."""
        return cls(
            code=MCPErrorCode.METHOD_NOT_FOUND.value,
            message=f"Method not found: {method}"
        )

    @classmethod
    def invalid_params(cls, message: str = "Invalid params") -> MCPError:
        """Create an invalid params error."""
        return cls(code=MCPErrorCode.INVALID_PARAMS.value, message=message)

    @classmethod
    def internal_error(cls, message: str = "Internal error") -> MCPError:
        """Create an internal error."""
        return cls(code=MCPErrorCode.INTERNAL_ERROR.value, message=message)

    @classmethod
    def document_not_found(cls, document_id: str) -> MCPError:
        """Create a document not found error."""
        return cls(
            code=MCPErrorCode.DOCUMENT_NOT_FOUND.value,
            message=f"Document not found: {document_id}",
            data={"document_id": document_id}
        )

    @classmethod
    def processing_failed(cls, message: str, details: Optional[Dict] = None) -> MCPError:
        """Create a processing failed error."""
        return cls(
            code=MCPErrorCode.PROCESSING_FAILED.value,
            message=message,
            data=details
        )

    @classmethod
    def timeout(cls, operation: str, timeout_seconds: float) -> MCPError:
        """Create a timeout error."""
        return cls(
            code=MCPErrorCode.TIMEOUT.value,
            message=f"Operation '{operation}' timed out after {timeout_seconds}s",
            data={"operation": operation, "timeout_seconds": timeout_seconds}
        )


@dataclass
class MCPMessage:
    """
    MCP protocol message.

    Represents a message in the MCP protocol. Messages can be requests,
    responses, or notifications.

    Attributes:
        jsonrpc: Protocol version (always "2.0")
        id: Message ID for request/response correlation
        method: Method name (for requests)
        params: Method parameters (for requests)
        result: Result data (for responses)
        error: Error data (for error responses)

    Example:
        >>> # Request message
        >>> request = MCPMessage(
        ...     id="req-123",
        ...     method="process_document",
        ...     params={"document_id": "doc-456"}
        ... )
        >>>
        >>> # Response message
        >>> response = MCPMessage(
        ...     id="req-123",
        ...     result={"status": "completed"}
        ... )
    """

    jsonrpc: str = "2.0"
    id: Optional[str] = None
    method: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        """Generate ID if not provided for requests."""
        # Only auto-generate ID for regular requests, not notifications
        # Notifications should explicitly have id=None
        pass

    def is_request(self) -> bool:
        """Check if this is a request message."""
        return self.method is not None

    def is_notification(self) -> bool:
        """Check if this is a notification (request without id)."""
        return self.method is not None and self.id is None

    def is_response(self) -> bool:
        """Check if this is a response message."""
        return self.id is not None and self.method is None

    def is_success(self) -> bool:
        """Check if this is a successful response."""
        return self.is_response() and self.error is None

    def is_error(self) -> bool:
        """Check if this is an error response."""
        return self.is_response() and self.error is not None

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        data: Dict[str, Any] = {"jsonrpc": self.jsonrpc}

        if self.id is not None:
            data["id"] = self.id
        if self.method is not None:
            data["method"] = self.method
        if self.params is not None:
            data["params"] = self.params
        if self.result is not None:
            data["result"] = self.result
        if self.error is not None:
            data["error"] = self.error

        return data

    def to_json(self) -> str:
        """Convert message to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MCPMessage:
        """Create message from dictionary."""
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data.get("id"),
            method=data.get("method"),
            params=data.get("params"),
            result=data.get("result"),
            error=data.get("error"),
        )

    @classmethod
    def from_json(cls, json_str: str) -> MCPMessage:
        """Create message from JSON string."""
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def request(
        cls,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        id: Optional[str] = None,
    ) -> MCPMessage:
        """Create a request message."""
        return cls(
            id=id or str(uuid.uuid4()),
            method=method,
            params=params or {},
        )

    @classmethod
    def notification(
        cls,
        method: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> MCPMessage:
        """Create a notification message (no id)."""
        # Create without calling __post_init__ by using object.__new__
        msg = cls.__new__(cls)
        msg.jsonrpc = "2.0"
        msg.id = None
        msg.method = method
        msg.params = params or {}
        msg.result = None
        msg.error = None
        return msg

    @classmethod
    def success_response(
        cls,
        id: str,
        result: Any,
    ) -> MCPMessage:
        """Create a success response message."""
        return cls(
            id=id,
            result=result,
        )

    @classmethod
    def error_response(
        cls,
        id: Optional[str],
        error: MCPError,
    ) -> MCPMessage:
        """Create an error response message."""
        return cls(
            id=id,
            error=error.to_dict(),
        )


@dataclass
class MCPRequest:
    """
    High-level MCP request wrapper.

    Provides a more convenient interface for creating and handling
    MCP requests with type-safe parameters.

    Attributes:
        method: Request method
        params: Request parameters
        id: Request ID
        context: Additional context data
    """

    method: str
    params: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    context: Dict[str, Any] = field(default_factory=dict)

    def to_message(self) -> MCPMessage:
        """Convert to MCP message."""
        return MCPMessage.request(
            method=self.method,
            params=self.params,
            id=self.id,
        )

    @classmethod
    def from_message(cls, message: MCPMessage) -> MCPRequest:
        """Create from MCP message."""
        return cls(
            method=message.method or "",
            params=message.params or {},
            id=message.id or str(uuid.uuid4()),
        )


@dataclass
class MCPResponse:
    """
    High-level MCP response wrapper.

    Provides a more convenient interface for handling MCP responses
    with type-safe result access.

    Attributes:
        id: Response ID (matches request ID)
        result: Response result data
        error: Response error (if failed)
        metadata: Response metadata
    """

    id: str
    result: Optional[Any] = None
    error: Optional[MCPError] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        """Check if response is successful."""
        return self.error is None

    @property
    def is_error(self) -> bool:
        """Check if response is an error."""
        return self.error is not None

    def get_result(self, key: Optional[str] = None) -> Any:
        """
        Get result data.

        Args:
            key: Optional key to access nested result

        Returns:
            Result data or nested value

        Raises:
            MCPError: If response is an error
        """
        if self.error:
            raise RuntimeError(f"MCP error: {self.error.message}")

        if key is None:
            return self.result

        if isinstance(self.result, dict):
            return self.result.get(key)

        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary."""
        data: Dict[str, Any] = {
            "id": self.id,
            "jsonrpc": "2.0",
        }
        if self.error:
            data["error"] = self.error.to_dict()
        else:
            data["result"] = self.result
        return data

    def to_message(self) -> MCPMessage:
        """Convert to MCP message."""
        if self.error:
            return MCPMessage.error_response(self.id, self.error)
        return MCPMessage.success_response(self.id, self.result)

    @classmethod
    def from_message(cls, message: MCPMessage) -> MCPResponse:
        """Create from MCP message."""
        error = None
        if message.error:
            error = MCPError.from_dict(message.error)

        return cls(
            id=message.id or "",
            result=message.result,
            error=error,
        )

    @classmethod
    def success(
        cls,
        id: str,
        result: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MCPResponse:
        """Create a success response."""
        return cls(
            id=id,
            result=result,
            metadata=metadata or {},
        )

    @classmethod
    def error_response(
        cls,
        id: str,
        error: MCPError,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MCPResponse:
        """Create an error response."""
        return cls(
            id=id,
            error=error,
            metadata=metadata or {},
        )


# Batch message handling

@dataclass
class MCPBatch:
    """
    Batch of MCP messages.

    Supports batching multiple requests/responses in a single message.
    """

    messages: List[MCPMessage] = field(default_factory=list)

    def add(self, message: MCPMessage) -> None:
        """Add a message to the batch."""
        self.messages.append(message)

    def to_json(self) -> str:
        """Convert batch to JSON."""
        return json.dumps([m.to_dict() for m in self.messages])

    @classmethod
    def from_json(cls, json_str: str) -> MCPBatch:
        """Create batch from JSON."""
        data = json.loads(json_str)
        messages = [MCPMessage.from_dict(m) for m in data]
        return cls(messages=messages)

    def get_responses(self) -> List[MCPMessage]:
        """Get all response messages."""
        return [m for m in self.messages if m.is_response()]

    def get_requests(self) -> List[MCPMessage]:
        """Get all request messages."""
        return [m for m in self.messages if m.is_request()]
