"""
ToxMCP Server Manager

Manages the lifecycle of ToxMCP server processes. Each server is a Python
package that runs as a local HTTP service. This manager handles:
  - Checking which servers are already running (via HTTP health check)
  - Launching servers as subprocesses if not already running
  - Graceful shutdown on app exit
  - Status reporting for the UI status bar

Default ports (configurable via config.py):
    ADMETlab MCP  : 8082
    CompTox MCP   : 8083
    AOP MCP       : 8084
    PBPK MCP      : 8085

Usage:
    manager = ToxServerManager()
    manager.start_server("admet")
    status = manager.get_status()   # dict: server_name -> bool (alive)
    manager.stop_all()
"""

import subprocess
import logging
import sys
from dataclasses import dataclass, field
from typing import Optional
from .mcp_client import MCPClient

logger = logging.getLogger(__name__)


@dataclass
class ServerConfig:
    name: str               # short key used internally
    display_name: str       # shown in UI
    package: str            # pip package / uvx package name
    launch_cmd: list        # subprocess argv
    port: int
    requires_key: bool = False
    key_env_var: str = ""
    _process: Optional[subprocess.Popen] = field(default=None, repr=False)


# Default server configurations
_DEFAULT_SERVERS: dict[str, ServerConfig] = {
    "admet": ServerConfig(
        name="admet",
        display_name="ADMETlab MCP",
        package="admetlab-mcp",
        launch_cmd=[sys.executable, "-m", "admetlab_mcp", "--port", "8082"],
        port=8082,
        requires_key=False,
    ),
    "comptox": ServerConfig(
        name="comptox",
        display_name="CompTox MCP",
        package="comptox-mcp",
        launch_cmd=[sys.executable, "-m", "comptox_mcp", "--port", "8083"],
        port=8083,
        requires_key=True,
        key_env_var="EPA_COMPTOX_API_KEY",
    ),
    "aop": ServerConfig(
        name="aop",
        display_name="AOP MCP",
        package="aop-mcp",
        launch_cmd=[sys.executable, "-m", "aop_mcp", "--port", "8084"],
        port=8084,
        requires_key=False,
    ),
    "pbpk": ServerConfig(
        name="pbpk",
        display_name="PBPK MCP",
        package="pbpk-mcp",
        launch_cmd=[sys.executable, "-m", "pbpk_mcp", "--port", "8085"],
        port=8085,
        requires_key=False,
    ),
}


class ToxServerManager:
    """
    Manages ToxMCP server subprocesses and provides MCPClient instances.

    Typical usage in app startup:
        manager = ToxServerManager()
        manager.start_server("admet")          # start ADMETlab (no key needed)
        admet_client = manager.get_client("admet")

    The manager is tolerant -- if a server fails to start, it logs a warning
    and marks it unavailable rather than crashing the app.
    """

    def __init__(self, port_overrides: Optional[dict] = None):
        self._servers = {k: v for k, v in _DEFAULT_SERVERS.items()}
        if port_overrides:
            for name, port in port_overrides.items():
                if name in self._servers:
                    self._servers[name].port = port
                    # Rebuild launch_cmd with new port
                    cmd = self._servers[name].launch_cmd
                    if "--port" in cmd:
                        idx = cmd.index("--port")
                        cmd[idx + 1] = str(port)

        self._clients: dict[str, MCPClient] = {}

    def get_client(self, server_name: str) -> Optional[MCPClient]:
        """
        Return an MCPClient for the named server.
        Creates one on first call. Returns None if server config unknown.
        """
        if server_name not in self._servers:
            return None
        if server_name not in self._clients:
            cfg = self._servers[server_name]
            self._clients[server_name] = MCPClient(
                base_url=f"http://localhost:{cfg.port}",
                server_name=cfg.display_name,
            )
        return self._clients[server_name]

    def is_alive(self, server_name: str) -> bool:
        """Return True if the named server is reachable right now."""
        client = self.get_client(server_name)
        if client is None:
            return False
        return client.is_alive()

    def start_server(self, server_name: str) -> bool:
        """
        Start a ToxMCP server as a subprocess if not already running.

        Returns True if the server is alive after the attempt.
        Does NOT block -- server startup is async; caller should poll is_alive().
        """
        if server_name not in self._servers:
            logger.error("Unknown ToxMCP server: %s", server_name)
            return False

        cfg = self._servers[server_name]

        # Already alive?
        if self.is_alive(server_name):
            logger.debug("%s already running on port %d", cfg.display_name, cfg.port)
            return True

        # Launch subprocess
        try:
            proc = subprocess.Popen(
                cfg.launch_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            cfg._process = proc
            logger.info("Started %s (PID %d) on port %d", cfg.display_name, proc.pid, cfg.port)
            return True
        except FileNotFoundError:
            logger.warning(
                "%s not installed. Install with: pip install %s",
                cfg.display_name, cfg.package,
            )
            return False
        except Exception as e:
            logger.error("Failed to start %s: %s", cfg.display_name, e)
            return False

    def start_all_available(self) -> dict[str, bool]:
        """
        Attempt to start all servers that don't require an API key.
        Servers requiring keys are skipped unless the key env var is set.
        Returns dict of server_name -> started_ok.
        """
        import os
        results = {}
        for name, cfg in self._servers.items():
            if cfg.requires_key and not os.getenv(cfg.key_env_var):
                logger.debug(
                    "Skipping %s -- %s not set", cfg.display_name, cfg.key_env_var
                )
                results[name] = False
                continue
            results[name] = self.start_server(name)
        return results

    def get_status(self) -> dict[str, bool]:
        """Return alive status for all known servers."""
        return {name: self.is_alive(name) for name in self._servers}

    def stop_all(self) -> None:
        """Terminate all server subprocesses started by this manager."""
        for cfg in self._servers.values():
            if cfg._process is not None:
                try:
                    cfg._process.terminate()
                    cfg._process.wait(timeout=5)
                    logger.info("Stopped %s", cfg.display_name)
                except Exception as e:
                    logger.warning("Error stopping %s: %s", cfg.display_name, e)
                finally:
                    cfg._process = None

    @property
    def available_servers(self) -> list[str]:
        """Names of all known server configurations."""
        return list(self._servers.keys())
