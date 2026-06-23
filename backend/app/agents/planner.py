from __future__ import annotations

import json
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from app.config import get_settings
from app.core.agent_runner import AgentRunner
from app.core.llm_client import LLMClient
from app.core.mcp_client import MCPClient
from app.models.schemas import TripPlan, TripPlanRequest


AMAP_MCP_SERVER_PACKAGE = "@amap/amap-maps-mcp-server"
BACKEND_DIR = Path(__file__).resolve().parents[2]


ATTRACTION_AGENT_PROMPT = """你是景点搜索专家。

可用工具:
{tools_description}

任务: 搜索 {city} 的景点，偏好: {preferences}

根据偏好选择合适的搜索关键词:
- 历史文化: 博物馆、古迹、历史遗址
- 自然风光: 公园、山水、自然风景区
- 美食购物: 商圈、美食街、特色市场
- 亲子游玩: 游乐园、动物园、亲子活动
- 文艺打卡: 美术馆、创意园、网红景点

必须使用工具搜索，禁止编造信息。返回景点列表，包含名称、地址、评分、坐标。"""


WEATHER_AGENT_PROMPT = """你是天气查询专家。

可用工具:
{tools_description}

任务: 查询 {city} 的天气预报。

请使用天气查询工具获取天气信息。
返回每日天气: 日期、白天天气、夜间天气、温度(纯数字)、风力风向。"""


HOTEL_AGENT_PROMPT = """你是酒店推荐专家。

可用工具:
{tools_description}

任务: 搜索 {city} 的酒店，住宿偏好: {accommodation}

根据住宿类型选择合适的搜索关键词:
- 经济型酒店: 经济型酒店、快捷酒店
- 舒适型酒店: 三星酒店、舒适型酒店
- 豪华型酒店: 五星级酒店、豪华酒店、度假酒店
- 民宿: 民宿、客栈

请使用工具搜索，返回酒店列表，包含: 名称、地址、评分、价格范围、类型。"""


PLANNER_AGENT_PROMPT = """你是行程规划专家。你不需要使用任何工具，只需根据提供的信息整合生成行程计划。

请严格输出 JSON，不要输出解释文字。JSON 结构必须包含:
- city, start_date, end_date
- days: 每日行程，包含 date, day_index, description, transportation, accommodation, hotel, attractions, meals
- weather_info: 每天的天气
- overall_suggestions: 实用旅行建议
- budget: 门票、酒店、餐饮、交通和总预算

规划要求:
1. weather_info 必须包含每天的天气
2. 温度必须为纯数字(不含°C)
3. 每天安排2-3个景点，考虑景点间的距离和游览时间
4. 包含早中晚三餐推荐
5. 提供实用的旅行建议
6. 包含预算估算

输入信息:
{query}"""


class TripPlannerAgentError(RuntimeError):
    """Raised when trip planning orchestration cannot produce a valid plan."""


class TripPlannerAgent:
    def __init__(
        self,
        llm: Any | None = None,
        mcp: Any | None = None,
        agent_factory: Callable[..., Any] = AgentRunner,
        attraction_agent: Any | None = None,
        weather_agent: Any | None = None,
        hotel_agent: Any | None = None,
        planner_agent: Any | None = None,
    ) -> None:
        self.llm = llm
        self.mcp = mcp

        if all(
            agent is not None
            for agent in [attraction_agent, weather_agent, hotel_agent, planner_agent]
        ):
            self.attraction_agent = attraction_agent
            self.weather_agent = weather_agent
            self.hotel_agent = hotel_agent
            self.planner_agent = planner_agent
            return

        settings = get_settings()
        if self.llm is None:
            self.llm = LLMClient(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                model=settings.llm_model,
                timeout=settings.llm_timeout,
            )
        if self.mcp is None:
            self.mcp = MCPClient(
                command="npx",
                args=["-y", AMAP_MCP_SERVER_PACKAGE],
                env={
                    "AMAP_API_KEY": settings.amap_api_key,
                    "AMAP_MAPS_API_KEY": settings.amap_api_key,
                    "npm_config_cache": str(BACKEND_DIR / ".npm-cache"),
                },
            )

        self.mcp.start()
        self.mcp.initialize()
        tools = self.mcp.list_tools()

        text_search_tools = [tool for tool in tools if tool.get("name") == "maps_text_search"]
        weather_tools = [tool for tool in tools if tool.get("name") == "maps_weather"]

        self.attraction_agent = attraction_agent or agent_factory(
            name="AttractionSearch",
            system_prompt=ATTRACTION_AGENT_PROMPT,
            tools=text_search_tools,
            llm=self.llm,
            mcp=self.mcp,
        )
        self.weather_agent = weather_agent or agent_factory(
            name="WeatherQuery",
            system_prompt=WEATHER_AGENT_PROMPT,
            tools=weather_tools,
            llm=self.llm,
            mcp=self.mcp,
        )
        self.hotel_agent = hotel_agent or agent_factory(
            name="HotelSearch",
            system_prompt=HOTEL_AGENT_PROMPT,
            tools=text_search_tools,
            llm=self.llm,
            mcp=self.mcp,
        )
        self.planner_agent = planner_agent or agent_factory(
            name="Planner",
            system_prompt=PLANNER_AGENT_PROMPT,
            tools=[],
            llm=self.llm,
            mcp=None,
        )

    def plan_trip(self, request: TripPlanRequest) -> TripPlan:
        attractions = self.attraction_agent.run(
            city=request.city,
            preferences=request.preferences,
        )
        weather = self.weather_agent.run(city=request.city)
        hotels = self.hotel_agent.run(
            city=request.city,
            accommodation=request.accommodation,
        )
        query = self._build_planner_query(request, attractions, weather, hotels)
        planner_response = self.planner_agent.run(query=query)
        try:
            return self._parse_trip_plan(planner_response)
        except TripPlannerAgentError as exc:
            correction_query = self._build_correction_query(
                request=request,
                invalid_response=planner_response,
                validation_error=str(exc.__cause__ or exc),
            )
            corrected_response = self.planner_agent.run(query=correction_query)
            return self._parse_trip_plan(corrected_response)

    def _build_planner_query(
        self,
        request: TripPlanRequest,
        attractions: str,
        weather: str,
        hotels: str,
    ) -> str:
        return json.dumps(
            {
                "user_request": request.model_dump(),
                "attractions_info": attractions,
                "weather_info": weather,
                "hotels_info": hotels,
            },
            ensure_ascii=False,
        )

    def _build_correction_query(
        self,
        request: TripPlanRequest,
        invalid_response: str,
        validation_error: str,
    ) -> str:
        return json.dumps(
            {
                "task": "Fix the previous trip plan response so it matches the backend schema exactly. Return only valid JSON.",
                "user_request": request.model_dump(),
                "invalid_response": invalid_response,
                "validation_error": validation_error,
                "required_schema": {
                    "city": "string",
                    "start_date": "YYYY-MM-DD string",
                    "end_date": "YYYY-MM-DD string",
                    "days": [
                        {
                            "date": "YYYY-MM-DD string",
                            "day_index": "integer starting at 0",
                            "description": "string",
                            "transportation": "string",
                            "accommodation": "string",
                            "hotel": {
                                "name": "string",
                                "address": "string",
                                "location": {
                                    "longitude": "number between -180 and 180",
                                    "latitude": "number between -90 and 90",
                                },
                                "price_range": "string",
                                "rating": "string",
                                "distance": "string",
                                "type": "string",
                                "estimated_cost": "non-negative integer",
                            },
                            "attractions": [
                                {
                                    "name": "string",
                                    "address": "string",
                                    "location": {
                                        "longitude": "number between -180 and 180",
                                        "latitude": "number between -90 and 90",
                                    },
                                    "visit_duration": "positive integer minutes",
                                    "description": "string",
                                    "category": "string",
                                    "rating": "number between 0 and 5",
                                    "ticket_price": "non-negative integer",
                                }
                            ],
                            "meals": [
                                {
                                    "type": "breakfast|lunch|dinner|snack",
                                    "name": "string",
                                    "address": "string",
                                    "estimated_cost": "non-negative integer",
                                }
                            ],
                        }
                    ],
                    "weather_info": [
                        {
                            "date": "YYYY-MM-DD string",
                            "day_weather": "string",
                            "night_weather": "string",
                            "day_temp": "integer, no unit",
                            "night_temp": "integer, no unit",
                            "wind_direction": "string",
                            "wind_power": "string",
                        }
                    ],
                    "overall_suggestions": "string, not an array",
                    "budget": {
                        "total_attractions": "non-negative integer",
                        "total_hotels": "non-negative integer",
                        "total_meals": "non-negative integer",
                        "total_transportation": "non-negative integer",
                        "total": "sum of the four total_* fields",
                    },
                },
                "rules": [
                    "Do not return markdown fences or explanatory text.",
                    "Do not use arrays where the schema requires an object or string.",
                    "Do not rename weather_info or budget fields.",
                    "Keep budget.total equal to total_attractions + total_hotels + total_meals + total_transportation.",
                ],
            },
            ensure_ascii=False,
        )

    def _parse_trip_plan(self, response: str) -> TripPlan:
        json_str = self._extract_json_text(response)
        try:
            data = json.loads(json_str)
            return TripPlan(**data)
        except (JSONDecodeError, ValidationError, TypeError) as exc:
            raise TripPlannerAgentError("failed to parse trip plan JSON") from exc

    def close(self) -> None:
        if self.mcp is not None:
            self.mcp.close()

    def _extract_json_text(self, response: str) -> str:
        stripped = response.strip()
        if "```json" in stripped:
            return stripped.split("```json", 1)[1].split("```", 1)[0].strip()
        if "```" in stripped:
            return stripped.split("```", 1)[1].split("```", 1)[0].strip()
        return stripped
