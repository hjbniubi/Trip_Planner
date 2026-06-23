from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException

from app.agents.planner import TripPlannerAgent, TripPlannerAgentError
from app.config import get_settings
from app.core.llm_client import LLMAuthenticationError, LLMClientError, LLMTimeoutError
from app.core.mcp_client import MCPClientError
from app.models.schemas import TripPlan, TripPlanRequest
from app.services.unsplash import UnsplashService

router = APIRouter(prefix="/trip", tags=["trip"])


class LazyTripPlanner:
    def __init__(self) -> None:
        self._planner: TripPlannerAgent | None = None

    def plan_trip(self, request: TripPlanRequest) -> TripPlan:
        if self._planner is None:
            try:
                self._planner = TripPlannerAgent()
            except Exception as exc:
                raise TripPlannerAgentError("failed to initialize trip planner") from exc
        return self._planner.plan_trip(request)


@lru_cache
def get_trip_planner() -> LazyTripPlanner:
    return LazyTripPlanner()


@lru_cache
def get_unsplash_service() -> UnsplashService:
    settings = get_settings()
    return UnsplashService(access_key=settings.unsplash_access_key)


@router.post("/plan", response_model=TripPlan)
def plan_trip(
    request: TripPlanRequest,
    planner: TripPlannerAgent = Depends(get_trip_planner),
    unsplash: UnsplashService = Depends(get_unsplash_service),
) -> TripPlan:
    try:
        trip_plan = planner.plan_trip(request)
    except LLMAuthenticationError as exc:
        raise HTTPException(
            status_code=502,
            detail="LLM API Key 无效或无权限，请检查后端 .env 配置",
        ) from exc
    except LLMTimeoutError as exc:
        raise HTTPException(status_code=504, detail="规划生成超时，请稍后重试") from exc
    except (TripPlannerAgentError, MCPClientError, LLMClientError) as exc:
        raise HTTPException(status_code=500, detail="规划生成失败，请稍后重试") from exc

    _enrich_attraction_images(trip_plan, unsplash)
    return trip_plan


def _enrich_attraction_images(trip_plan: TripPlan, unsplash: UnsplashService) -> None:
    for day in trip_plan.days:
        for attraction in day.attractions:
            if attraction.image_url:
                continue
            image_url = unsplash.get_photo_url(attraction.name)
            if image_url:
                attraction.image_url = image_url
