"""
Base MCP HTTP JSON-RPC 2.0 Client

All ToxMCP servers expose a standard HTTP endpoint at /mcp using JSON-RPC 2.0.
This module provides the base client used by all individual server wrappers.

Protocol:
    POST {server_url}/mcp
    Content-Type: application/json
    Body: {"jsonrpc": "2.0", "id": <int>, "method": <str>, "params": <dict>}

Key MCP methods:
    tools/list  -- discover available tools on a server
    tools/call  -- call a named tool with arguments
"""

import json
import time
import logging
from dataclasses import dataclass, field
from typing import Any, Optional
import requests

logger = logging.getLogger(__name__)


class MCPError(Exception):
    """Raised when an MCP server returns an error or is unreachable."""
    def __init__(self, message: str, code: Optional[int] = None, server: str = ""):
        super().__init__(message)
        self.code = code
        self.server = server


@dataclass
class MCPToolResult:
    """Structured result from a single MCP tool call."""
    tool: str
    server: str
    content: Any
    raw_text: str = ""
    success: bool = True
    error: Optional[str] = None
    duration_ms: float = 0.0
    metadata: dict = field(default_factory=dict)


class MCPClient:
    """
    Synchronous HTTP JSON-RPC 2.0 client for MCP servers.

    Each ToxMCP server has its own MCPClient instance. The individual
    wrappers (ADMETClient, CompToxClient, etc.) compose this class.

    Args:
        base_url:    Full URL to server root, e.g. "http://localhost:8082"
        server_name: Human-readable label used in logging and error messages
        timeout:     Request timeout in seconds (default 60)
    """

    def __init__(self, base_url: str, server_name: str, timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.mcp_url = f"{self.base_url}/mcp"
        self.server_name = server_name
        self.timeout = timeout
        self._request_id = 0
        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _post(self, method: str, params: dict) -> dict:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params,
        }
        try:
            response = self._session.post(self.mcp_url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.ConnectionError:
            raise MCPError(
                f"{self.server_name} is not running at {self.mcp_url}. "
                "Start it with the server_manager or manually.",
                server=self.server_name,
            )
        except requests.exceptions.Timeout:
            raise MCPError(f"{self.server_name} timed out after {self.timeout}s.", server=self.server_name)
        except requests.exceptions.HTTPError as e:
            raise MCPError(str(e), server=self.server_name)

        if "error" in data:
            err = data["error"]
            raise MCPError(err.get("message", "Unknown MCP error"), code=err.get("code"), server=self.server_name)
        return data.get("result", {})

    def is_alive(self) -> bool:
        """Return True if the server responds. Never raises."""
        try:
            self._post("tools/list", {})
            return True
        except Exception:
            return False

    def list_tools(self) -> list:
        """Return tools advertised by this server."""
        result = self._post("tools/list", {})
        return result.get("tools", [])

    def call_tool(self, tool_name: str, arguments: dict) -> MCPToolResult:
        """
        Call a named tool and return a structured result.
        Always returns MCPToolResult -- never raises.
        Check .success and .error for failure cases.
        """
        t0 = time.monotonic()
        try:
            result = self._post("tools/call", {"name": tool_name, "arguments": arguments})
            duration_ms = (time.monotonic() - t0) * 1000

            content_blocks = result.get("content", [])
            raw_text = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")

            try:
                parsed = json.loads(raw_text)
            except (json.JSONDecodeError, TypeError):
                parsed = raw_text

            logger.debug("%s :: %s completed in %.0f ms", self.server_name, tool_name, duration_ms)
            return MCPToolResult(tool=tool_name, server=self.server_name, content=parsed,
                                 raw_text=raw_text, success=True, duration_ms=duration_ms)

        except MCPError as e:
            duration_ms = (time.monotonic() - t0) * 1000
            logger.warning("%s :: %s failed: %s", self.server_name, tool_name, e)
            return MCPToolResult(tool=tool_name, server=self.server_name, content=None,
                                 success=False, error=str(e), duration_ms=duration_ms)
