import {
  calculateInclusiveDays,
  formatDateValue,
  getProgressStatus,
  isChineseCityName,
} from "./tripForm";

const days: number | null = calculateInclusiveDays("2026-07-01", "2026-07-03");
const sameDay: number | null = calculateInclusiveDays("2026-07-01", "2026-07-01");
const invalidRange: number | null = calculateInclusiveDays("2026-07-03", "2026-07-01");
const formatted: string = formatDateValue({ format: () => "2026-07-01" });
const emptyFormatted: string = formatDateValue(null);
const cityValid: boolean = isChineseCityName("北京");
const cityInvalid: boolean = isChineseCityName("Beijing");
const progressText: string = getProgressStatus(72);

void [
  days,
  sameDay,
  invalidRange,
  formatted,
  emptyFormatted,
  cityValid,
  cityInvalid,
  progressText,
];
