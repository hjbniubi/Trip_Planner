import json

import pytest

from app.core import mcp_client as mcp_client_module
from app.core.mcp_client import MCPClient, MCPClientError, MCPProtocolError


class RecordingStdin:
    def __init__(self):
        self.lines = []
        self.flushed = False

    def write(self, text):
        self.lines.append(text)

    def flush(self):
        self.flushed = True


class QueuedStdout:
    def __init__(self, responses):
        self.responses = list(responses)

    def readline(self):
        if not self.responses:
            return ""
        return json.dumps(self.responses.pop(0), ensure_ascii=False) + "\n"


class FakeProcess:
    def __init__(self, responses, poll_result=None):
        self.stdin = RecordingStdin()
        self.stdout = QueuedStdout(responses)
        self.stderr = QueuedStdout([])
        self.poll_result = poll_result
        self.terminated = False
        self.killed = False
        self.wait_timeout = None

    def poll(self):
        return self.poll_result

    def terminate(self):
        self.terminated = True
        self.poll_result = 0

    def kill(self):
        self.killed = True
        self.poll_result = -9

    def wait(self, timeout=None):
        self.wait_timeout = timeout
        return self.poll_result


class ProcessFactory:
    def __init__(self, processes):
        self.processes = list(processes)
        self.calls = []

    def __call__(self, command, args, env):
        self.calls.append({"command": command, "args": args, "env": env})
        return self.processes.pop(0)


def parse_written_requests(process):
    return [json.loads(line) for line in process.stdin.lines]


def test_start_uses_command_args_and_merged_environment():
    process = FakeProcess([])
    factory = ProcessFactory([process])
    client = MCPClient(
        command="npx",
        args=["-y", "@amap/amap-maps-mcp-server"],
        env={"AMAP_API_KEY": "amap-test-key"},
        process_factory=factory,
    )

    client.start()

    assert client.process is process
    assert factory.calls[0]["command"] == "npx"
    assert factory.calls[0]["args"] == ["-y", "@amap/amap-maps-mcp-server"]
    assert factory.calls[0]["env"]["AMAP_API_KEY"] == "amap-test-key"
    assert "PATH" in factory.calls[0]["env"]


def test_initialize_sends_json_rpc_initialize_request_and_returns_result():
    process = FakeProcess(
        [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"serverInfo": {"name": "amap-mcp"}},
            }
        ]
    )
    client = MCPClient("npx", [], process_factory=ProcessFactory([process]))
    client.start()

    result = client.initialize()

    assert result == {"serverInfo": {"name": "amap-mcp"}}
    assert parse_written_requests(process) == [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "trip-planner", "version": "0.1.0"},
            },
        }
    ]
    assert process.stdin.flushed is True


def test_list_tools_stores_tools_by_name():
    process = FakeProcess(
        [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "tools": [
                        {
                            "name": "maps_text_search",
                            "description": "POI 搜索",
                            "inputSchema": {"type": "object"},
                        },
                        {
                            "name": "maps_weather",
                            "description": "天气",
                            "inputSchema": {"type": "object"},
                        },
                    ]
                },
            }
        ]
    )
    client = MCPClient("npx", [], process_factory=ProcessFactory([process]))
    client.start()

    tools = client.list_tools()

    assert [tool["name"] for tool in tools] == ["maps_text_search", "maps_weather"]
    assert client.tools["maps_weather"]["description"] == "天气"
    assert parse_written_requests(process)[0]["method"] == "tools/list"


def test_call_tool_sends_tool_name_and_arguments():
    process = FakeProcess(
        [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"content": [{"type": "text", "text": "故宫博物院"}]},
            }
        ]
    )
    client = MCPClient("npx", [], process_factory=ProcessFactory([process]))
    client.start()

    result = client.call_tool(
        "maps_text_search",
        {"keywords": "博物馆", "city": "北京"},
    )

    assert result == {"content": [{"type": "text", "text": "故宫博物院"}]}
    assert parse_written_requests(process) == [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "maps_text_search",
                "arguments": {"keywords": "博物馆", "city": "北京"},
            },
        }
    ]


def test_json_rpc_error_response_raises_client_error():
    process = FakeProcess(
        [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "error": {"code": -32602, "message": "Invalid params"},
            }
        ]
    )
    client = MCPClient("npx", [], process_factory=ProcessFactory([process]))
    client.start()

    with pytest.raises(MCPClientError) as exc_info:
        client.call_tool("maps_weather", {"city": ""})

    assert "Invalid params" in str(exc_info.value)


def test_mismatched_response_id_raises_protocol_error():
    process = FakeProcess(
        [{"jsonrpc": "2.0", "id": 99, "result": {"tools": []}}]
    )
    client = MCPClient("npx", [], process_factory=ProcessFactory([process]))
    client.start()

    with pytest.raises(MCPProtocolError) as exc_info:
        client.list_tools()

    assert "response id 99 did not match request id 1" in str(exc_info.value)


def test_close_terminates_running_process():
    process = FakeProcess([])
    client = MCPClient("npx", [], process_factory=ProcessFactory([process]))
    client.start()

    client.close()

    assert process.terminated is True
    assert process.wait_timeout == 5
    assert client.process is None


def test_request_restarts_process_when_previous_process_exited():
    exited_process = FakeProcess([], poll_result=1)
    running_process = FakeProcess(
        [{"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}]
    )
    factory = ProcessFactory([exited_process, running_process])
    client = MCPClient("npx", [], process_factory=factory)
    client.start()

    assert client.list_tools() == []

    assert client.process is running_process
    assert len(factory.calls) == 2


def test_resolve_command_uses_cmd_shim_for_npx_on_windows(monkeypatch):
    monkeypatch.setattr(mcp_client_module.os, "name", "nt")
    monkeypatch.setattr(
        mcp_client_module.shutil,
        "which",
        lambda command: "D:\\webziliao\\NodeJS\\npx.cmd" if command == "npx.cmd" else None,
    )
    client = MCPClient("npx", [])

    assert client._resolve_command("npx") == "D:\\webziliao\\NodeJS\\npx.cmd"
