import httpx

from app.services.unsplash import UnsplashService


class FakeHttpClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def get(self, url, *, headers, params):
        self.requests.append({"url": url, "headers": headers, "params": params})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def json_response(status_code, body):
    return httpx.Response(
        status_code,
        request=httpx.Request("GET", "https://api.unsplash.com/search/photos"),
        json=body,
    )


def test_search_photos_returns_regular_photo_urls_and_sends_access_key():
    http_client = FakeHttpClient(
        [
            json_response(
                200,
                {
                    "total": 2,
                    "results": [
                        {
                            "id": "photo-1",
                            "urls": {
                                "regular": "https://images.unsplash.com/photo-1",
                                "small": "https://images.unsplash.com/photo-1-small",
                            },
                        },
                        {
                            "id": "photo-2",
                            "urls": {"small": "https://images.unsplash.com/photo-2-small"},
                        },
                    ],
                },
            )
        ]
    )
    service = UnsplashService(access_key="unsplash-key", http_client=http_client)

    urls = service.search_photos("故宫博物院", per_page=2)

    assert urls == [
        "https://images.unsplash.com/photo-1",
        "https://images.unsplash.com/photo-2-small",
    ]
    assert http_client.requests == [
        {
            "url": "https://api.unsplash.com/search/photos",
            "headers": {"Authorization": "Client-ID unsplash-key"},
            "params": {"query": "故宫博物院", "per_page": 2, "orientation": "landscape"},
        }
    ]


def test_get_photo_url_returns_first_photo_url():
    http_client = FakeHttpClient(
        [
            json_response(
                200,
                {
                    "results": [
                        {"id": "photo-1", "urls": {"regular": "https://images.unsplash.com/1"}}
                    ]
                },
            )
        ]
    )
    service = UnsplashService(access_key="unsplash-key", http_client=http_client)

    assert service.get_photo_url("天安门广场") == "https://images.unsplash.com/1"


def test_search_photos_gracefully_returns_empty_list_without_access_key():
    service = UnsplashService(access_key="")

    assert service.search_photos("故宫博物院") == []
    assert service.get_photo_url("故宫博物院") is None


def test_search_photos_gracefully_returns_empty_list_on_http_failure():
    http_client = FakeHttpClient([httpx.TimeoutException("timeout")])
    service = UnsplashService(access_key="unsplash-key", http_client=http_client)

    assert service.search_photos("故宫博物院") == []
