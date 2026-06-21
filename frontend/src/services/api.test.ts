import { getApiErrorMessage } from "./api";

const backendMessage: string = getApiErrorMessage({
  response: { data: { detail: "规划生成超时，请稍后重试" } },
});
const fallbackMessage: string = getApiErrorMessage(new Error("network down"));

if (backendMessage !== "规划生成超时，请稍后重试") {
  throw new Error("Expected backend detail to be shown to the user.");
}

if (fallbackMessage !== "生成失败，请稍后重试") {
  throw new Error("Expected fallback message when backend detail is unavailable.");
}
