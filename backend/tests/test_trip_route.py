from fastapi.testclient import TestClient

from app.agents.planner import TripPlannerAgentError
from app.api.main import app
from app.api.routes.trip import get_trip_planner, get_unsplash_service
from app.core.llm_client import LLMTimeoutError
from app.core.mcp_client import MCPClientError
from app.models.schemas import TripPlan


class FakePlanner:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def plan_trip(self, request):
        self.calls.append(request)
        if self.error:
            raise self.error
        return self.response


class FakeUnsplash:
    def __init__(self, urls):
        self.urls = dict(urls)
        self.calls = []

    def get_photo_url(self, query):
        self.calls.append(query)
        return self.urls.get(query)


def trip_plan_without_images():
    return TripPlan(
        city="北京",
        start_date="2026-07-01",
        end_date="2026-07-01",
        days=[
            {
                "date": "2026-07-01",
                "day_index": 0,
                "description": "历史文化一日游",
                "transportation": "公共交通",
                "accommodation": "经济型酒店",
                "attractions": [
                    {
                        "name": "故宫博物院",
                        "address": "北京市东城区景山前街4号",
                        "location": {"longitude": 116.397, "latitude": 39.916},
                        "visit_duration": 180,
                        "description": "明清皇家宫殿",
                        "category": "历史文化",
                        "rating": 4.8,
                        "ticket_price": 60,
                    },
                    {
                        "name": "天安门广场",
                        "address": "北京市东城区长安街",
                        "location": {"longitude": 116.397, "latitude": 39.908},
                        "visit_duration": 60,
                        "description": "城市广场",
                        "category": "历史文化",
                        "rating": 4.7,
                        "image_url": "https://existing.example/photo.jpg",
                        "ticket_price": 0,
                    },
                ],
                "meals": [{"type": "lunch", "name": "北京菜馆", "estimated_cost": 80}],
            }
        ],
        weather_info=[
            {
                "date": "2026-07-01",
                "day_weather": "晴",
                "night_weather": "多云",
                "day_temp": 32,
                "night_temp": 22,
                "wind_direction": "南",
                "wind_power": "≤3级",
            }
        ],
        overall_suggestions="注意防晒。",
        budget={
            "total_attractions": 60,
            "total_hotels": 0,
            "total_meals": 80,
            "total_transportation": 30,
            "total": 170,
        },
    )


def valid_request_payload():
    return {
        "city": "北京",
        "start_date": "2026-07-01",
        "end_date": "2026-07-01",
        "days": 1,
        "preferences": "历史文化",
        "budget": "中等",
        "transportation": "公共交通",
        "accommodation": "经济型酒店",
    }


def override_dependencies(planner, unsplash):
    app.dependency_overrides[get_trip_planner] = lambda: planner
    app.dependency_overrides[get_unsplash_service] = lambda: unsplash


def clear_overrides():
    app.dependency_overrides.clear()


def test_plan_trip_endpoint_returns_plan_and_enriches_missing_images():
    planner = FakePlanner(response=trip_plan_without_images())
    unsplash = FakeUnsplash({"故宫博物院": "https://images.unsplash.com/gugong.jpg"})
    override_dependencies(planner, unsplash)
    client = TestClient(app)

    try:
        response = client.post("/api/trip/plan", json=valid_request_payload())
    finally:
        clear_overrides()

    assert response.status_code == 200
    data = response.json()
    assert data["city"] == "北京"
    assert data["days"][0]["attractions"][0]["image_url"] == (
        "https://images.unsplash.com/gugong.jpg"
    )
    assert data["days"][0]["attractions"][1]["image_url"] == (
        "https://existing.example/photo.jpg"
    )
    assert [request.city for request in planner.calls] == ["北京"]
    assert unsplash.calls == ["故宫博物院"]


def test_plan_trip_endpoint_returns_422_for_invalid_request_payload():
    planner = FakePlanner(response=trip_plan_without_images())
    unsplash = FakeUnsplash({})
    override_dependencies(planner, unsplash)
    client = TestClient(app)
    payload = valid_request_payload()
    payload["days"] = 2

    try:
        response = client.post("/api/trip/plan", json=payload)
    finally:
        clear_overrides()

    assert response.status_code == 422
    assert planner.calls == []


def test_invalid_payload_is_rejected_before_real_planner_initialization():
    clear_overrides()
    get_trip_planner.cache_clear()
    client = TestClient(app)
    payload = valid_request_payload()
    payload["days"] = 2

    try:
        response = client.post("/api/trip/plan", json=payload)
    finally:
        clear_overrides()
        get_trip_planner.cache_clear()

    assert response.status_code == 422


def test_plan_trip_endpoint_maps_timeout_to_504():
    planner = FakePlanner(error=LLMTimeoutError("LLM request timed out"))
    override_dependencies(planner, FakeUnsplash({}))
    client = TestClient(app)

    try:
        response = client.post("/api/trip/plan", json=valid_request_payload())
    finally:
        clear_overrides()

    assert response.status_code == 504
    assert response.json()["detail"] == "规划生成超时，请稍后重试"


def test_plan_trip_endpoint_maps_planning_errors_to_500():
    planner = FakePlanner(error=TripPlannerAgentError("bad json"))
    override_dependencies(planner, FakeUnsplash({}))
    client = TestClient(app)

    try:
        response = client.post("/api/trip/plan", json=valid_request_payload())
    finally:
        clear_overrides()

    assert response.status_code == 500
    assert response.json()["detail"] == "规划生成失败，请稍后重试"


def test_plan_trip_endpoint_maps_mcp_errors_to_500():
    planner = FakePlanner(error=MCPClientError("MCP failed"))
    override_dependencies(planner, FakeUnsplash({}))
    client = TestClient(app)

    try:
        response = client.post("/api/trip/plan", json=valid_request_payload())
    finally:
        clear_overrides()

    assert response.status_code == 500
    assert response.json()["detail"] == "规划生成失败，请稍后重试"
