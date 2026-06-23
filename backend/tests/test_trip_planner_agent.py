import json

import pytest

from app.agents.planner import (
    ATTRACTION_AGENT_PROMPT,
    HOTEL_AGENT_PROMPT,
    PLANNER_AGENT_PROMPT,
    WEATHER_AGENT_PROMPT,
    TripPlannerAgent,
    TripPlannerAgentError,
)
from app.config import get_settings
from app.models.schemas import TripPlan, TripPlanRequest


class FakeMCP:
    def __init__(self):
        self.started = False
        self.initialized = False
        self.closed = False
        self.tools = [
            {"name": "maps_text_search", "description": "POI 搜索", "inputSchema": {}},
            {"name": "maps_weather", "description": "天气查询", "inputSchema": {}},
        ]

    def start(self):
        self.started = True

    def initialize(self):
        self.initialized = True
        return {"serverInfo": {"name": "fake-mcp"}}

    def list_tools(self):
        return self.tools

    def close(self):
        self.closed = True


class FakeAgent:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class RecordingAgentFactory:
    def __init__(self):
        self.created = []

    def __call__(self, **kwargs):
        self.created.append(kwargs)
        return FakeAgent(kwargs["name"])


class RecordingMCPClient(FakeMCP):
    created = []

    def __init__(self, command, args, env):
        super().__init__()
        self.command = command
        self.args = args
        self.env = env
        self.created.append(self)


def valid_trip_json():
    return json.dumps(
        {
            "city": "北京",
            "start_date": "2026-07-01",
            "end_date": "2026-07-01",
            "days": [
                {
                    "date": "2026-07-01",
                    "day_index": 0,
                    "description": "历史文化一日游",
                    "transportation": "公共交通",
                    "accommodation": "经济型酒店",
                    "hotel": {
                        "name": "如家酒店",
                        "address": "东城区",
                        "estimated_cost": 300,
                    },
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
                        }
                    ],
                    "meals": [
                        {"type": "lunch", "name": "北京菜馆", "estimated_cost": 80}
                    ],
                }
            ],
            "weather_info": [
                {
                    "date": "2026-07-01",
                    "day_weather": "晴",
                    "night_weather": "多云",
                    "day_temp": "32°C",
                    "night_temp": "22℃",
                    "wind_direction": "南",
                    "wind_power": "≤3级",
                }
            ],
            "overall_suggestions": "注意防晒，提前预约门票。",
            "budget": {
                "total_attractions": 60,
                "total_hotels": 300,
                "total_meals": 80,
                "total_transportation": 30,
                "total": 470,
            },
        },
        ensure_ascii=False,
    )


def make_request():
    return TripPlanRequest(
        city="北京",
        start_date="2026-07-01",
        end_date="2026-07-01",
        days=1,
        preferences="历史文化",
        budget="中等",
        transportation="公共交通",
        accommodation="经济型酒店",
    )


def test_prompts_contain_required_roles_and_tool_placeholders():
    assert "景点搜索专家" in ATTRACTION_AGENT_PROMPT
    assert "{tools_description}" in ATTRACTION_AGENT_PROMPT
    assert "{city}" in ATTRACTION_AGENT_PROMPT
    assert "{preferences}" in ATTRACTION_AGENT_PROMPT

    assert "天气查询专家" in WEATHER_AGENT_PROMPT
    assert "{tools_description}" in WEATHER_AGENT_PROMPT
    assert "{city}" in WEATHER_AGENT_PROMPT

    assert "酒店推荐专家" in HOTEL_AGENT_PROMPT
    assert "{tools_description}" in HOTEL_AGENT_PROMPT
    assert "{accommodation}" in HOTEL_AGENT_PROMPT

    assert "行程规划专家" in PLANNER_AGENT_PROMPT
    assert "weather_info" in PLANNER_AGENT_PROMPT
    assert "预算" in PLANNER_AGENT_PROMPT


def test_initialization_starts_shared_mcp_and_creates_four_agents():
    mcp = FakeMCP()
    factory = RecordingAgentFactory()

    agent = TripPlannerAgent(llm=object(), mcp=mcp, agent_factory=factory)

    assert mcp.started is True
    assert mcp.initialized is True
    assert len(factory.created) == 4
    assert factory.created[0]["name"] == "AttractionSearch"
    assert factory.created[0]["mcp"] is mcp
    assert factory.created[0]["tools"] == [mcp.tools[0]]
    assert factory.created[1]["name"] == "WeatherQuery"
    assert factory.created[1]["tools"] == [mcp.tools[1]]
    assert factory.created[2]["name"] == "HotelSearch"
    assert factory.created[2]["mcp"] is mcp
    assert factory.created[3]["name"] == "Planner"
    assert factory.created[3]["tools"] == []
    assert factory.created[3]["mcp"] is None
    assert agent.mcp is mcp


def test_initialization_passes_official_amap_mcp_api_key_env(monkeypatch):
    RecordingMCPClient.created = []
    get_settings.cache_clear()
    monkeypatch.setenv("AMAP_API_KEY", "amap-test-key")
    monkeypatch.setattr("app.agents.planner.MCPClient", RecordingMCPClient)

    try:
        TripPlannerAgent(llm=object(), agent_factory=RecordingAgentFactory())
    finally:
        get_settings.cache_clear()

    mcp = RecordingMCPClient.created[0]
    assert mcp.args == ["-y", "@amap/amap-maps-mcp-server"]
    assert mcp.env["AMAP_API_KEY"] == "amap-test-key"
    assert mcp.env["AMAP_MAPS_API_KEY"] == "amap-test-key"


def test_build_planner_query_serializes_user_request_and_agent_outputs():
    planner = TripPlannerAgent(
        attraction_agent=FakeAgent("景点"),
        weather_agent=FakeAgent("天气"),
        hotel_agent=FakeAgent("酒店"),
        planner_agent=FakeAgent(valid_trip_json()),
    )

    query = planner._build_planner_query(make_request(), "景点", "天气", "酒店")
    data = json.loads(query)

    assert data["user_request"]["city"] == "北京"
    assert data["user_request"]["preferences"] == "历史文化"
    assert data["attractions_info"] == "景点"
    assert data["weather_info"] == "天气"
    assert data["hotels_info"] == "酒店"


def test_parse_trip_plan_accepts_plain_json_and_markdown_json_block():
    planner = TripPlannerAgent(
        attraction_agent=FakeAgent("景点"),
        weather_agent=FakeAgent("天气"),
        hotel_agent=FakeAgent("酒店"),
        planner_agent=FakeAgent(valid_trip_json()),
    )

    plain = planner._parse_trip_plan(valid_trip_json())
    fenced = planner._parse_trip_plan(f"```json\n{valid_trip_json()}\n```")

    assert isinstance(plain, TripPlan)
    assert plain.weather_info[0].day_temp == 32
    assert fenced.city == "北京"


def test_parse_trip_plan_raises_clear_error_for_invalid_json():
    planner = TripPlannerAgent(
        attraction_agent=FakeAgent("景点"),
        weather_agent=FakeAgent("天气"),
        hotel_agent=FakeAgent("酒店"),
        planner_agent=FakeAgent(valid_trip_json()),
    )

    with pytest.raises(TripPlannerAgentError) as exc_info:
        planner._parse_trip_plan("不是 JSON")

    assert "failed to parse trip plan JSON" in str(exc_info.value)


def test_plan_trip_runs_child_agents_and_returns_trip_plan():
    attraction_agent = FakeAgent("景点搜索结果")
    weather_agent = FakeAgent("天气查询结果")
    hotel_agent = FakeAgent("酒店推荐结果")
    planner_agent = FakeAgent(valid_trip_json())
    planner = TripPlannerAgent(
        attraction_agent=attraction_agent,
        weather_agent=weather_agent,
        hotel_agent=hotel_agent,
        planner_agent=planner_agent,
    )

    trip_plan = planner.plan_trip(make_request())

    assert trip_plan.city == "北京"
    assert attraction_agent.calls == [{"city": "北京", "preferences": "历史文化"}]
    assert weather_agent.calls == [{"city": "北京"}]
    assert hotel_agent.calls == [{"city": "北京", "accommodation": "经济型酒店"}]
    planner_query = json.loads(planner_agent.calls[0]["query"])
    assert planner_query["attractions_info"] == "景点搜索结果"
    assert planner_query["weather_info"] == "天气查询结果"
    assert planner_query["hotels_info"] == "酒店推荐结果"


def test_close_delegates_to_shared_mcp():
    mcp = FakeMCP()
    planner = TripPlannerAgent(
        attraction_agent=FakeAgent("景点"),
        weather_agent=FakeAgent("天气"),
        hotel_agent=FakeAgent("酒店"),
        planner_agent=FakeAgent(valid_trip_json()),
        mcp=mcp,
    )

    planner.close()

    assert mcp.closed is True
