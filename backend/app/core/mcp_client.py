from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Callable
from typing import Any


class MCPClientError(RuntimeError):
    """Base error for MCP client failures."""


class MCPProtocolError(MCPClientError):
    """Raised when the MCP server returns malformed JSON-RPC data."""


class MCPClient:
    def __init__(
        self,
        command: str,
        args: list[str],
        env: dict[str, str] | None = None,
        process_factory: Callable[[str, list[str], dict[str, str]], Any] | None = None,
    ) -> None:
        self.command = command
        self.args = args
        self.env = env or {}
        self.process = None
        self.request_id = 0
        self.tools: dict[str, dict[str, Any]] = {}
        self._process_factory = process_factory or self._default_process_factory

    def start(self) -> None:
        if self.process is not None and self.process.poll() is None:
            return
        merged_env = os.environ.copy()
        merged_env.update(self.env)
        self.process = self._process_factory(self.command, self.args, merged_env)

    def initialize(self) -> dict[str, Any]:
        return self._send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "trip-planner", "version": "0.1.0"},
            },
        )

    def list_tools(self) -> list[dict[str, Any]]:
        result = self._send_request("tools/list", {})
        tools = result.get("tools")
        if not isinstance(tools, list):
            raise MCPProtocolError("tools/list response missing tools list")
        self.tools = {
            tool["name"]: tool
            for tool in tools
            if isinstance(tool, dict) and isinstance(tool.get("name"), str)
        }
        return tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._send_request(
            "tools/call",
            {
                "name": name,
                "arguments": arguments,
            },
        )

    def close(self) -> None:
        if self.process is None:
            return

        process = self.process
        self.process = None
        if process.poll() is not None:
            return

        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    def _send_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._ensure_process()
        self.request_id += 1
        request_id = self.request_id
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }

        assert self.process is not None
        if self.process.stdin is None or self.process.stdout is None:
            raise MCPClientError("MCP process was not started with stdin/stdout pipes")

        self.process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
        self.process.stdin.flush()

        raw_response = self.process.stdout.readline()
        if not raw_response:
            raise MCPProtocolError("MCP server returned no response")

        try:
            response = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            raise MCPProtocolError("MCP server returned invalid JSON") from exc

        response_id = response.get("id")
        if response_id != request_id:
            raise MCPProtocolError(
                f"response id {response_id} did not match request id {request_id}"
            )

        if "error" in response:
            error = response["error"]
            message = error.get("message") if isinstance(error, dict) else str(error)
            raise MCPClientError(f"MCP request failed: {message}")

        result = response.get("result")
        if not isinstance(result, dict):
            raise MCPProtocolError("MCP response missing result object")
        return result

    def _ensure_process(self) -> None:
        if self.process is None or self.process.poll() is not None:
            self.start()

    def _default_process_factory(
        self,
        command: str,
        args: list[str],
        env: dict[str, str],
    ) -> subprocess.Popen:
        resolved_command = self._resolve_command(command)
        return subprocess.Popen(
            [resolved_command, *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=env,
        )

    def _resolve_command(self, command: str) -> str:
        if os.name == "nt" and command.lower() == "npx":
            npx_cmd = shutil.which("npx.cmd")
            if npx_cmd:
                return npx_cmd
        return command
