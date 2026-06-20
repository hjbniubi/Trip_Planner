import type { Attraction, TripPlan } from "@/types";

import {
  collectAttractions,
  formatCurrency,
  formatTemperatureRange,
  parseTripPlanState,
} from "./resultPlan";

const samplePlan: TripPlan = {
  city: "北京",
  start_date: "2026-07-01",
  end_date: "2026-07-01",
  days: [
    {
      date: "2026-07-01",
      day_index: 0,
      description: "历史文化一日游",
      transportation: "公共交通",
      accommodation: "经济型酒店",
      attractions: [
        {
          name: "故宫博物院",
          address: "北京市东城区景山前街4号",
          location: { longitude: 116.397, latitude: 39.916 },
          visit_duration: 180,
          description: "明清皇家宫殿",
          ticket_price: 60,
        },
      ],
      meals: [],
    },
  ],
  weather_info: [
    {
      date: "2026-07-01",
      day_weather: "晴",
      night_weather: "多云",
      day_temp: 32,
      night_temp: 22,
      wind_direction: "南",
      wind_power: "≤3级",
    },
  ],
  overall_suggestions: "注意防晒。",
};

const parsedFromObject: TripPlan | null = parseTripPlanState(samplePlan);
const parsedFromString: TripPlan | null = parseTripPlanState(JSON.stringify(samplePlan));
const parsedFromBadString: TripPlan | null = parseTripPlanState("{bad json");
const attractions: Attraction[] = collectAttractions(samplePlan);
const money: string = formatCurrency(1200);
const temp: string = formatTemperatureRange(samplePlan.weather_info[0]);

void [
  parsedFromObject,
  parsedFromString,
  parsedFromBadString,
  attractions,
  money,
  temp,
];
