import pytest
from pydantic import ValidationError

from app.models.schemas import (
    Budget,
    DayPlan,
    Location,
    TripPlanRequest,
    WeatherInfo,
)


def test_trip_plan_request_accepts_valid_dates_and_matching_days():
    request = TripPlanRequest(
        city="北京",
        start_date="2026-07-01",
        end_date="2026-07-03",
        days=3,
    )

    assert request.city == "北京"
    assert request.days == 3
    assert request.preferences == "历史文化"


def test_trip_plan_request_rejects_days_that_do_not_match_date_range():
    with pytest.raises(ValidationError) as exc_info:
        TripPlanRequest(
            city="北京",
            start_date="2026-07-01",
            end_date="2026-07-03",
            days=2,
        )

    assert "days must equal end_date - start_date + 1" in str(exc_info.value)


def test_trip_plan_request_rejects_end_date_before_start_date():
    with pytest.raises(ValidationError) as exc_info:
        TripPlanRequest(
            city="北京",
            start_date="2026-07-03",
            end_date="2026-07-01",
            days=1,
        )

    assert "end_date must be greater than or equal to start_date" in str(exc_info.value)


def test_location_rejects_out_of_range_coordinates():
    with pytest.raises(ValidationError):
        Location(longitude=181, latitude=39.9)

    with pytest.raises(ValidationError):
        Location(longitude=116.4, latitude=91)


def test_day_plan_lists_are_not_shared_between_instances():
    first = DayPlan(
        date="2026-07-01",
        day_index=0,
        description="第一天",
        transportation="公共交通",
        accommodation="经济型酒店",
    )
    second = DayPlan(
        date="2026-07-02",
        day_index=1,
        description="第二天",
        transportation="公共交通",
        accommodation="经济型酒店",
    )

    first.meals.append({"type": "lunch", "name": "面馆", "estimated_cost": 40})

    assert second.meals == []


def test_weather_temperature_strings_are_parsed_to_ints():
    weather = WeatherInfo(
        date="2026-07-01",
        day_weather="晴",
        night_weather="多云",
        day_temp="32°C",
        night_temp="22℃",
        wind_direction="南",
        wind_power="≤3级",
    )

    assert weather.day_temp == 32
    assert weather.night_temp == 22


def test_budget_total_must_equal_component_sum():
    budget = Budget(
        total_attractions=100,
        total_hotels=300,
        total_meals=120,
        total_transportation=60,
        total=580,
    )

    assert budget.total == 580

    with pytest.raises(ValidationError) as exc_info:
        Budget(
            total_attractions=100,
            total_hotels=300,
            total_meals=120,
            total_transportation=60,
            total=999,
        )

    assert "total must equal the sum of budget components" in str(exc_info.value)
