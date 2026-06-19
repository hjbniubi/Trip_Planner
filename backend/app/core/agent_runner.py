from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


class AgentRunnerError(RuntimeError):
    """Raised when an agent cannot complete its run loop."""


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, str]


class AgentRunner:
    def __init__(
        self,
        name: str,
        system_prompt: str,
        tools: list[dict[str, Any]],
        llm: Any,
        mcp: Any | None = None,
        max_tool_rounds: int = 5,
    ) -> None:
        self.name = name
        self.system_prompt = system_prompt
        self.tools = tools
        self.llm = llm
        self.mcp = mcp
        self.max_tool_rounds = max_tool_rounds
        self._tool_names = {
            tool["name"]
            for tool in tools
            if isinstance(tool, dict) and isinstance(tool.get("name"), str)
        }

    def run(self, **kwargs: Any) -> str:
        system_prompt = self._fill_prompt(
            self.system_prompt,
            tools_description=self._build_tools_prompt(),
            **kwargs,
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "请根据系统提示完成任务。"},
        ]

        for _ in range(self.max_tool_rounds):
            response = self.llm.chat(messages)
            tool_call = self._parse_tool_call(response)
            if tool_call is None:
                return response

            result = self._execute_tool(tool_call)
            messages.append({"role": "assistant", "content": response})
            messages.append(
                {
                    "role": "user",
                    "content": "工具调用结果:\n"
                    + json.dumps(result, ensure_ascii=False),
                }
            )

        raise AgentRunnerError(f"Agent {self.name} exceeded max tool rounds")

    def _fill_prompt(self, template: str, **kwargs: Any) -> str:
        return template.format(**kwargs)

    def _parse_tool_call(self, text: str) -> ToolCall | None:
        match = re.search(r"\[TOOL_CALL:([A-Za-z0-9_]+):([^\]]*)\]", text)
        if not match:
            return None

        tool_name = match.group(1)
        args_text = match.group(2).strip()
        arguments: dict[str, str] = {}
        if args_text:
            for pair in args_text.split(","):
                if "=" not in pair:
                    raise AgentRunnerError(f"invalid tool argument format: {pair}")
                key, value = pair.split("=", 1)
                arguments[key.strip()] = value.strip()

        return ToolCall(name=tool_name, arguments=arguments)

    def _build_tools_prompt(self) -> str:
        if not self.tools:
            return "无可用工具"

        descriptions = []
        for tool in self.tools:
            name = tool.get("name", "")
            description = tool.get("description", "")
            input_schema = tool.get("inputSchema", {})
            properties = input_schema.get("properties", {})
            params = ", ".join(properties.keys()) if isinstance(properties, dict) else ""
            descriptions.append(f"- {name}: {description}. 参数: {params}")
        return "\n".join(descriptions)

    def _execute_tool(self, tool_call: ToolCall) -> dict[str, Any]:
        if self.mcp is None:
            raise AgentRunnerError(f"Agent {self.name} requires an MCP client")
        if tool_call.name not in self._tool_names:
            raise AgentRunnerError(
                f"tool {tool_call.name} is not registered for agent {self.name}"
            )
        return self.mcp.call_tool(tool_call.name, tool_call.arguments)
