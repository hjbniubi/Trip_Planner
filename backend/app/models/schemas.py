from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class Location(BaseModel):
    longitude: float = Field(..., ge=-180, le=180, description="经度")
    latitude: float = Field(..., ge=-90, le=90, description="纬度")


class Attraction(BaseModel):
    name: str
    address: str
    location: Location
    visit_duration: int = Field(..., gt=0, description="建议游览时间，单位分钟")
    description: str
    category: str | None = "景点"
    rating: float | None = Field(default=None, ge=0, le=5)
    image_url: str | None = None
    ticket_price: int = Field(default=0, ge=0)


class Meal(BaseModel):
    type: Literal["breakfast", "lunch", "dinner", "snack"]
    name: str
    address: str | None = None
    location: Location | None = None
    description: str | None = None
    estimated_cost: int = Field(default=0, ge=0)


class Hotel(BaseModel):
    name: str
    address: str = ""
    location: Location | None = None
    price_range: str = ""
    rating: str = ""
    distance: str = ""
    type: str = ""
    estimated_cost: int = Field(default=0, ge=0)


class Budget(BaseModel):
    total_attractions: int = Field(default=0, ge=0)
    total_hotels: int = Field(default=0, ge=0)
    total_meals: int = Field(default=0, ge=0)
    total_transportation: int = Field(default=0, ge=0)
    total: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_total(self) -> "Budget":
        expected_total = (
            self.total_attractions
            + self.total_hotels
            + self.total_meals
            + self.total_transportation
        )
        if self.total != expected_total:
            raise ValueError("total must equal the sum of budget components")
        return self


class WeatherInfo(BaseModel):
    date: str
    day_weather: str
    night_weather: str
    day_temp: int
    night_temp: int
    wind_direction: str
    wind_power: str

    @field_validator("day_temp", "night_temp", mode="before")
    @classmethod
    def parse_temperature(cls, value: object) -> int:
        if isinstance(value, str):
            cleaned = (
                value.replace("°C", "")
                .replace("℃", "")
                .replace("°", "")
                .strip()
            )
            return int(cleaned)
        if isinstance(value, (int, float)):
            return int(value)
        raise ValueError("temperature must be a number")


class DayPlan(BaseModel):
    date: str
    day_index: int = Field(..., ge=0)
    description: str
    transportation: str
    accommodation: str
    hotel: Hotel | None = None
    attractions: list[Attraction] = Field(default_factory=list)
    meals: list[Meal] = Field(default_factory=list)


class TripPlan(BaseModel):
    city: str
    start_date: str
    end_date: str
    days: list[DayPlan] = Field(default_factory=list)
    weather_info: list[WeatherInfo] = Field(default_factory=list)
    overall_suggestions: str
    budget: Budget | None = None


class TripPlanRequest(BaseModel):
    city: str = Field(..., min_length=1)
    start_date: str
    end_date: str
    days: int = Field(..., ge=1)
    preferences: str = "历史文化"
    budget: str = "中等"
    transportation: str = "公共交通"
    accommodation: str = "经济型酒店"

    @model_validator(mode="after")
    def validate_dates_and_days(self) -> "TripPlanRequest":
        try:
            start = date.fromisoformat(self.start_date)
            end = date.fromisoformat(self.end_date)
        except ValueError as exc:
            raise ValueError("start_date and end_date must use YYYY-MM-DD format") from exc

        if end < start:
            raise ValueError("end_date must be greater than or equal to start_date")

        expected_days = (end - start).days + 1
        if self.days != expected_days:
            raise ValueError("days must equal end_date - start_date + 1")

        return self
