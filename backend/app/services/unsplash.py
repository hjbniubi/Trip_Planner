from __future__ import annotations

from typing import Any

import httpx


class UnsplashService:
    def __init__(
        self,
        access_key: str,
        http_client: Any | None = None,
        base_url: str = "https://api.unsplash.com",
    ) -> None:
        self.access_key = access_key
        self.base_url = base_url.rstrip("/")
        self._http_client = http_client or httpx.Client(timeout=10)

    def search_photos(self, query: str, per_page: int = 1) -> list[str]:
        if not self.access_key:
            return []

        try:
            response = self._http_client.get(
                f"{self.base_url}/search/photos",
                headers={"Authorization": f"Client-ID {self.access_key}"},
                params={
                    "query": query,
                    "per_page": per_page,
                    "orientation": "landscape",
                },
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError):
            return []

        results = data.get("results", [])
        if not isinstance(results, list):
            return []

        urls: list[str] = []
        for result in results:
            if not isinstance(result, dict):
                continue
            image_urls = result.get("urls", {})
            if not isinstance(image_urls, dict):
                continue
            url = image_urls.get("regular") or image_urls.get("small")
            if isinstance(url, str) and url:
                urls.append(url)
        return urls

    def get_photo_url(self, query: str) -> str | None:
        urls = self.search_photos(query, per_page=1)
        return urls[0] if urls else None
