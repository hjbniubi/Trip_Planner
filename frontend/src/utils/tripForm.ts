interface DateLike {
  format: (pattern: string) => string;
}

const DAY_IN_MS = 24 * 60 * 60 * 1000;

export function formatDateValue(value: DateLike | null): string {
  return value ? value.format("YYYY-MM-DD") : "";
}

export function calculateInclusiveDays(startDate: string, endDate: string): number | null {
  if (!startDate || !endDate) {
    return null;
  }

  const start = Date.parse(`${startDate}T00:00:00`);
  const end = Date.parse(`${endDate}T00:00:00`);
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) {
    return null;
  }

  return Math.floor((end - start) / DAY_IN_MS) + 1;
}

export function isChineseCityName(value: string): boolean {
  return /^[\u4e00-\u9fa5]{2,12}$/.test(value.trim());
}

export function getProgressStatus(progress: number): string {
  if (progress <= 30) {
    return "正在搜索景点...";
  }
  if (progress <= 50) {
    return "正在查询天气...";
  }
  if (progress <= 70) {
    return "正在推荐酒店...";
  }
  if (progress < 100) {
    return "正在生成行程计划...";
  }
  return "完成！";
}
