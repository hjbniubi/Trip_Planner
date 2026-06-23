import httpx
import pytest

from app.core.llm_client import (
    LLMAuthenticationError,
    LLMClient,
    LLMResponseError,
    LLMTimeoutError,
)


class FakeHttpClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def post(self, url, *, headers, json):
        self.requests.append({"url": url, "headers": headers, "json": json})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def completion_response(content="你好"):
    return httpx.Response(
        200,
        request=httpx.Request("POST", "https://api.example.com/v1/chat/completions"),
        json={
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
        },
    )


def json_response(status_code, body):
    return httpx.Response(
        status_code,
        request=httpx.Request("POST", "https://api.example.com/v1/chat/completions"),
        json=body,
    )


def test_chat_posts_openai_compatible_payload_and_returns_message_content():
    http_client = FakeHttpClient([completion_response("旅行计划已生成")])
    client = LLMClient(
        api_key="sk-test",
        base_url="https://api.example.com/v1",
        model="test-model",
        http_client=http_client,
    )

    result = client.chat(
        [{"role": "user", "content": "规划北京三日游"}],
        temperature=0.2,
        max_tokens=512,
    )

    assert result == "旅行计划已生成"
    assert http_client.requests == [
        {
            "url": "https://api.example.com/v1/chat/completions",
            "headers": {
                "Authorization": "Bearer sk-test",
                "Content-Type": "application/json",
            },
            "json": {
                "model": "test-model",
                "messages": [{"role": "user", "content": "规划北京三日游"}],
                "temperature": 0.2,
                "max_tokens": 512,
            },
        }
    ]


def test_chat_supports_base_url_with_trailing_slash():
    http_client = FakeHttpClient([completion_response("ok")])
    client = LLMClient(
        api_key="sk-test",
        base_url="https://api.deepseek.com/v1/",
        model="deepseek-chat",
        http_client=http_client,
    )

    assert client.chat([{"role": "user", "content": "hello"}]) == "ok"
    assert http_client.requests[0]["url"] == "https://api.deepseek.com/v1/chat/completions"


def test_chat_retries_transient_http_errors_before_returning_content():
    http_client = FakeHttpClient(
        [
            json_response(500, {"error": "temporary"}),
            json_response(502, {"error": "temporary"}),
            completion_response("重试成功"),
        ]
    )
    sleep_calls = []
    client = LLMClient(
        api_key="sk-test",
        base_url="https://api.example.com/v1",
        model="test-model",
        http_client=http_client,
        sleep=sleep_calls.append,
    )

    assert client.chat([{"role": "user", "content": "hello"}]) == "重试成功"
    assert len(http_client.requests) == 3
    assert sleep_calls == [1, 2]


def test_chat_maps_timeout_to_custom_error():
    http_client = FakeHttpClient([httpx.TimeoutException("timed out")])
    client = LLMClient(
        api_key="sk-test",
        base_url="https://api.example.com/v1",
        model="test-model",
        http_client=http_client,
        sleep=lambda _: None,
    )

    with pytest.raises(LLMTimeoutError) as exc_info:
        client.chat([{"role": "user", "content": "hello"}])

    assert "LLM request timed out" in str(exc_info.value)


def test_chat_maps_authentication_error_without_retrying():
    http_client = FakeHttpClient([json_response(401, {"error": "invalid api key"})])
    client = LLMClient(
        api_key="bad-key",
        base_url="https://api.example.com/v1",
        model="test-model",
        http_client=http_client,
        sleep=lambda _: None,
    )

    with pytest.raises(LLMAuthenticationError) as exc_info:
        client.chat([{"role": "user", "content": "hello"}])

    assert "LLM API key is invalid or unauthorized" in str(exc_info.value)
    assert len(http_client.requests) == 1


def test_chat_raises_response_error_when_content_is_missing():
    http_client = FakeHttpClient([json_response(200, {"choices": []})])
    client = LLMClient(
        api_key="sk-test",
        base_url="https://api.example.com/v1",
        model="test-model",
        http_client=http_client,
    )

    with pytest.raises(LLMResponseError) as exc_info:
        client.chat([{"role": "user", "content": "hello"}])

    assert "missing assistant message content" in str(exc_info.value)


def test_chat_with_tools_includes_tool_schemas():
    http_client = FakeHttpClient([completion_response("工具响应")])
    client = LLMClient(
        api_key="sk-test",
        base_url="https://api.example.com/v1",
        model="test-model",
        http_client=http_client,
    )
    tools = [{"type": "function", "function": {"name": "maps_weather"}}]

    assert client.chat_with_tools([{"role": "user", "content": "天气"}], tools) == "工具响应"
    assert http_client.requests[0]["json"]["tools"] == tools
