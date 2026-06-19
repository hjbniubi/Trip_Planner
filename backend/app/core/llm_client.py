from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx


class LLMClientError(RuntimeError):
    """Base error for LLM client failures."""


class LLMTimeoutError(LLMClientError):
    """Raised when the upstream LLM request times out."""


class LLMResponseError(LLMClientError):
    """Raised when the upstream LLM response cannot be used."""


class LLMClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: int = 90,
        http_client: Any | None = None,
        sleep: Callable[[int], None] = time.sleep,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._http_client = http_client or httpx.Client(timeout=timeout)
        self._sleep = sleep

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        return self._post_chat_completion(payload)

    def chat_with_tools(
        self,
        messages: list[dict[str, str]],
        tool_schemas: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "tools": tool_schemas,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        return self._post_chat_completion(payload)

    def _post_chat_completion(self, payload: dict[str, Any]) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self._http_client.post(url, headers=headers, json=payload)
                if response.status_code >= 500 and attempt < 2:
                    self._sleep(2**attempt)
                    continue
                response.raise_for_status()
                return self._extract_content(response)
            except httpx.TimeoutException as exc:
                raise LLMTimeoutError("LLM request timed out") from exc
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < 2:
                    self._sleep(2**attempt)
                    continue
                raise LLMClientError(f"LLM request failed: {exc}") from exc

        raise LLMClientError(f"LLM request failed: {last_error}")

    def _extract_content(self, response: httpx.Response) -> str:
        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMResponseError("LLM response missing assistant message content") from exc

        if not isinstance(content, str) or not content.strip():
            raise LLMResponseError("LLM response missing assistant message content")
        return content
