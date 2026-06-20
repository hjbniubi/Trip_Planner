import type { Attraction, TripPlan, WeatherInfo } from "@/types";

export function parseTripPlanState(value: unknown): TripPlan | null {
  if (!value) {
    return null;
  }
  if (typeof value === "object") {
    return value as TripPlan;
  }
  if (typeof value !== "string") {
    return null;
  }

  try {
    return JSON.parse(value) as TripPlan;
  } catch {
    return null;
  }
}

export function collectAttractions(plan: TripPlan | null): Attraction[] {
  if (!plan) {
    return [];
  }
  return plan.days.flatMap((day) => day.attractions);
}

export function formatCurrency(value: number | null | undefined): string {
  return `¥${Math.round(value ?? 0).toLocaleString("zh-CN")}`;
}

export function formatTemperatureRange(weather: WeatherInfo): string {
  return `${weather.night_temp}-${weather.day_temp}°C`;
}
