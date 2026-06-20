<script setup lang="ts">
import { message } from "ant-design-vue";
import type { FormInstance } from "ant-design-vue";
import { computed, onBeforeUnmount, reactive, ref } from "vue";
import { useRouter } from "vue-router";

import { generateTripPlan } from "@/services/api";
import type { TripPlanRequest } from "@/types";
import {
  calculateInclusiveDays,
  formatDateValue,
  getProgressStatus,
  isChineseCityName,
} from "@/utils/tripForm";

type SelectOption = {
  label: string;
  value: string;
};

type FormState = TripPlanRequest;

const router = useRouter();
const formRef = ref<FormInstance>();
const loading = ref(false);
const progress = ref(0);
let progressTimer: number | undefined;

const formState = reactive<FormState>({
  city: "",
  start_date: "",
  end_date: "",
  days: 1,
  preferences: "历史文化",
  budget: "中等",
  transportation: "公共交通",
  accommodation: "经济型酒店",
});

const preferenceOptions: SelectOption[] = [
  { label: "历史文化", value: "历史文化" },
  { label: "自然风光", value: "自然风光" },
  { label: "美食购物", value: "美食购物" },
  { label: "亲子游玩", value: "亲子游玩" },
  { label: "文艺打卡", value: "文艺打卡" },
];

const budgetOptions: SelectOption[] = [
  { label: "经济", value: "经济" },
  { label: "中等", value: "中等" },
  { label: "豪华", value: "豪华" },
];

const transportationOptions: SelectOption[] = [
  { label: "公共交通", value: "公共交通" },
  { label: "自驾", value: "自驾" },
  { label: "打车", value: "打车" },
  { label: "混合", value: "混合" },
];

const accommodationOptions: SelectOption[] = [
  { label: "经济型酒店", value: "经济型酒店" },
  { label: "舒适型酒店", value: "舒适型酒店" },
  { label: "豪华型酒店", value: "豪华型酒店" },
  { label: "民宿", value: "民宿" },
];

const progressText = computed(() => getProgressStatus(progress.value));

const rules = {
  city: [
    { required: true, message: "请输入城市名称", trigger: "blur" },
    {
      validator: async (_rule: unknown, value: string) => {
        if (!isChineseCityName(value)) {
          throw new Error("请输入 2-12 个中文字符");
        }
      },
      trigger: "blur",
    },
  ],
  start_date: [{ required: true, message: "请选择开始日期", trigger: "change" }],
  end_date: [
    { required: true, message: "请选择结束日期", trigger: "change" },
    {
      validator: async () => {
        if (calculateInclusiveDays(formState.start_date, formState.end_date) === null) {
          throw new Error("结束日期需不早于开始日期");
        }
      },
      trigger: "change",
    },
  ],
};

function updateDays(): void {
  const days = calculateInclusiveDays(formState.start_date, formState.end_date);
  formState.days = days ?? 1;
}

function handleStartDateChange(value: unknown): void {
  formState.start_date = formatDateValue(value as Parameters<typeof formatDateValue>[0]);
  updateDays();
}

function handleEndDateChange(value: unknown): void {
  formState.end_date = formatDateValue(value as Parameters<typeof formatDateValue>[0]);
  updateDays();
}

function startProgress(): void {
  progress.value = 8;
  progressTimer = window.setInterval(() => {
    if (progress.value < 88) {
      progress.value += progress.value < 50 ? 8 : 4;
    }
  }, 500);
}

function stopProgress(finalValue = 0): void {
  if (progressTimer) {
    window.clearInterval(progressTimer);
    progressTimer = undefined;
  }
  progress.value = finalValue;
}

async function handleSubmit(): Promise<void> {
  await formRef.value?.validate();
  loading.value = true;
  startProgress();

  try {
    const tripPlan = await generateTripPlan({ ...formState });
    stopProgress(100);
    message.success("行程已生成");
    await router.push({
      name: "result",
      state: { tripPlan: JSON.stringify(tripPlan) },
    });
  } catch {
    stopProgress(0);
    message.error("生成失败，请稍后重试");
  } finally {
    loading.value = false;
  }
}

onBeforeUnmount(() => stopProgress(progress.value));
</script>

<template>
  <main class="planner-page">
    <section class="planner-shell">
      <div class="planner-copy">
        <p class="eyebrow">AI Travel Planner</p>
        <h1>智能旅行助手</h1>
      </div>

      <a-card class="planner-card" :bordered="false">
        <a-form
          ref="formRef"
          :model="formState"
          :rules="rules"
          layout="vertical"
          @finish="handleSubmit"
        >
          <div class="form-grid">
            <a-form-item label="目的地城市" name="city">
              <a-input
                v-model:value="formState.city"
                size="large"
                placeholder="北京"
                :disabled="loading"
              />
            </a-form-item>

            <a-form-item label="偏好" name="preferences">
              <a-select
                v-model:value="formState.preferences"
                size="large"
                :options="preferenceOptions"
                :disabled="loading"
              />
            </a-form-item>

            <a-form-item label="开始日期" name="start_date">
              <a-date-picker
                size="large"
                class="full-width"
                :disabled="loading"
                @change="handleStartDateChange"
              />
            </a-form-item>

            <a-form-item label="结束日期" name="end_date">
              <a-date-picker
                size="large"
                class="full-width"
                :disabled="loading"
                @change="handleEndDateChange"
              />
            </a-form-item>

            <a-form-item label="天数" name="days">
              <a-input-number
                v-model:value="formState.days"
                size="large"
                class="full-width"
                :min="1"
                disabled
              />
            </a-form-item>

            <a-form-item label="预算" name="budget">
              <a-select
                v-model:value="formState.budget"
                size="large"
                :options="budgetOptions"
                :disabled="loading"
              />
            </a-form-item>

            <a-form-item label="交通方式" name="transportation">
              <a-select
                v-model:value="formState.transportation"
                size="large"
                :options="transportationOptions"
                :disabled="loading"
              />
            </a-form-item>

            <a-form-item label="住宿类型" name="accommodation">
              <a-select
                v-model:value="formState.accommodation"
                size="large"
                :options="accommodationOptions"
                :disabled="loading"
              />
            </a-form-item>
          </div>

          <div v-if="loading || progress > 0" class="progress-panel">
            <a-progress :percent="progress" :show-info="false" />
            <span>{{ progressText }}</span>
          </div>

          <a-button
            type="primary"
            html-type="submit"
            size="large"
            block
            :loading="loading"
          >
            生成行程
          </a-button>
        </a-form>
      </a-card>
    </section>
  </main>
</template>

<style scoped>
.planner-page {
  min-height: 100vh;
  background:
    linear-gradient(135deg, rgba(242, 94, 64, 0.08), transparent 32%),
    linear-gradient(215deg, rgba(28, 121, 104, 0.12), transparent 36%),
    #f7f3ec;
  color: #17231f;
  padding: 40px 24px;
}

.planner-shell {
  display: grid;
  grid-template-columns: minmax(220px, 0.72fr) minmax(420px, 1fr);
  gap: 36px;
  align-items: start;
  max-width: 1080px;
  margin: 0 auto;
}

.planner-copy {
  padding-top: 28px;
}

.eyebrow {
  margin: 0 0 12px;
  color: #b65337;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

h1 {
  margin: 0;
  color: #10231f;
  font-family: Georgia, "Times New Roman", serif;
  font-size: 54px;
  line-height: 1.02;
  letter-spacing: 0;
}

.planner-card {
  border: 1px solid rgba(23, 35, 31, 0.12);
  border-radius: 8px;
  box-shadow: 0 24px 80px rgba(32, 39, 35, 0.12);
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 2px 18px;
}

.full-width {
  width: 100%;
}

.progress-panel {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 14px;
  align-items: center;
  min-height: 42px;
  margin: 2px 0 18px;
  color: #42524d;
  font-size: 14px;
}

:deep(.ant-btn-primary) {
  background: #c65d3a;
  box-shadow: none;
}

:deep(.ant-btn-primary:not(:disabled):hover) {
  background: #a9492d;
}

:deep(.ant-input),
:deep(.ant-select-selector),
:deep(.ant-picker),
:deep(.ant-input-number) {
  border-radius: 6px;
}

@media (max-width: 820px) {
  .planner-page {
    padding: 24px 16px;
  }

  .planner-shell {
    grid-template-columns: 1fr;
    gap: 22px;
  }

  .planner-copy {
    padding-top: 0;
  }

  h1 {
    font-size: 38px;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }

  .progress-panel {
    grid-template-columns: 1fr;
    gap: 8px;
  }
}
</style>
