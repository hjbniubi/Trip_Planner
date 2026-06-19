import json

import pytest

from app.core.agent_runner import AgentRunner, AgentRunnerError, ToolCall


class RecordingLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat(self, messages):
        self.calls.append(messages)
        return self.responses.pop(0)


class RecordingMCP:
    def __init__(self):
        self.calls = []

    def call_tool(self, name, arguments):
        self.calls.append({"name": name, "arguments": arguments})
        return {"content": [{"type": "text", "text": f"{name} result"}]}


TOOLS = [
    {
        "name": "maps_text_search",
        "description": "高德 POI 文本搜索",
        "inputSchema": {
            "type": "object",
            "properties": {"keywords": {"type": "string"}, "city": {"type": "string"}},
            "required": ["keywords", "city"],
        },
    },
    {
        "name": "maps_weather",
        "description": "高德天气查询",
        "inputSchema": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    },
]


def make_runner(llm, mcp=None, tools=None, max_tool_rounds=5):
    return AgentRunner(
        name="AttractionSearch",
        system_prompt="可用工具:\n{tools_description}\n任务: 搜索 {city}，偏好 {preferences}",
        tools=TOOLS if tools is None else tools,
        llm=llm,
        mcp=mcp,
        max_tool_rounds=max_tool_rounds,
    )


def test_parse_tool_call_extracts_name_and_arguments():
    runner = make_runner(RecordingLLM([]), mcp=RecordingMCP())

    tool_call = runner._parse_tool_call(
        "我需要搜索。[TOOL_CALL:maps_text_search:keywords=博物馆,city=北京]"
    )

    assert tool_call == ToolCall(
        name="maps_text_search",
        arguments={"keywords": "博物馆", "city": "北京"},
    )


def test_parse_tool_call_returns_none_when_marker_absent():
    runner = make_runner(RecordingLLM([]), mcp=RecordingMCP())

    assert runner._parse_tool_call("最终景点列表") is None


def test_run_returns_final_text_when_no_tool_call_is_needed():
    llm = RecordingLLM(["完整行程 JSON"])
    runner = AgentRunner(
        name="Planner",
        system_prompt="任务: {query}",
        tools=[],
        llm=llm,
        mcp=None,
    )

    result = runner.run(query="整合信息")

    assert result == "完整行程 JSON"
    assert llm.calls[0] == [
        {"role": "system", "content": "任务: 整合信息"},
        {"role": "user", "content": "请根据系统提示完成任务。"},
    ]


def test_run_executes_tool_and_adds_result_before_final_answer():
    llm = RecordingLLM(
        [
            "需要查工具。[TOOL_CALL:maps_text_search:keywords=博物馆,city=北京]",
            "景点列表: 故宫博物院",
        ]
    )
    mcp = RecordingMCP()
    runner = make_runner(llm, mcp=mcp)

    result = runner.run(city="北京", preferences="历史文化")

    assert result == "景点列表: 故宫博物院"
    assert mcp.calls == [
        {
            "name": "maps_text_search",
            "arguments": {"keywords": "博物馆", "city": "北京"},
        }
    ]
    second_call_messages = llm.calls[1]
    assert second_call_messages[-2] == {
        "role": "assistant",
        "content": "需要查工具。[TOOL_CALL:maps_text_search:keywords=博物馆,city=北京]",
    }
    assert second_call_messages[-1]["role"] == "user"
    assert second_call_messages[-1]["content"].startswith("工具调用结果:\n")
    assert json.loads(second_call_messages[-1]["content"].split("\n", 1)[1]) == {
        "content": [{"type": "text", "text": "maps_text_search result"}]
    }


def test_run_supports_multiple_tool_rounds():
    llm = RecordingLLM(
        [
            "[TOOL_CALL:maps_text_search:keywords=博物馆,city=北京]",
            "[TOOL_CALL:maps_weather:city=北京]",
            "全部信息整理完成",
        ]
    )
    mcp = RecordingMCP()
    runner = make_runner(llm, mcp=mcp)

    assert runner.run(city="北京", preferences="历史文化") == "全部信息整理完成"
    assert mcp.calls == [
        {
            "name": "maps_text_search",
            "arguments": {"keywords": "博物馆", "city": "北京"},
        },
        {"name": "maps_weather", "arguments": {"city": "北京"}},
    ]


def test_run_rejects_tool_call_when_mcp_is_missing():
    llm = RecordingLLM(["[TOOL_CALL:maps_weather:city=北京]"])
    runner = AgentRunner(
        name="Planner",
        system_prompt="任务: {query}",
        tools=[],
        llm=llm,
        mcp=None,
    )

    with pytest.raises(AgentRunnerError) as exc_info:
        runner.run(query="天气")

    assert "requires an MCP client" in str(exc_info.value)


def test_run_rejects_tool_call_not_registered_for_agent():
    llm = RecordingLLM(["[TOOL_CALL:maps_weather:city=北京]"])
    runner = make_runner(llm, mcp=RecordingMCP(), tools=[TOOLS[0]])

    with pytest.raises(AgentRunnerError) as exc_info:
        runner.run(city="北京", preferences="历史文化")

    assert "tool maps_weather is not registered" in str(exc_info.value)


def test_run_raises_when_max_tool_rounds_is_exceeded():
    llm = RecordingLLM(
        [
            "[TOOL_CALL:maps_weather:city=北京]",
            "[TOOL_CALL:maps_weather:city=北京]",
        ]
    )
    runner = make_runner(llm, mcp=RecordingMCP(), max_tool_rounds=2)

    with pytest.raises(AgentRunnerError) as exc_info:
        runner.run(city="北京", preferences="历史文化")

    assert "exceeded max tool rounds" in str(exc_info.value)


def test_build_tools_prompt_includes_tool_schema_summary():
    runner = make_runner(RecordingLLM([]), mcp=RecordingMCP())

    tools_prompt = runner._build_tools_prompt()

    assert "maps_text_search" in tools_prompt
    assert "高德 POI 文本搜索" in tools_prompt
    assert "keywords" in tools_prompt
    assert "maps_weather" in tools_prompt
