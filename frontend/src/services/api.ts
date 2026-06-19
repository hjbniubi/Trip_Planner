import axios from "axios";

import type { TripPlan, TripPlanRequest } from "@/types";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api",
  timeout: 120000,
});

export async function generateTripPlan(request: TripPlanRequest): Promise<TripPlan> {
  const response = await api.post<TripPlan>("/trip/plan", request);
  return response.data;
}

export default api;
