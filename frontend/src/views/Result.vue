<script setup lang="ts">
import AMapLoader from "@amap/amap-jsapi-loader";
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import type { Attraction, TripPlan } from "@/types";
import {
  collectAttractions,
  formatCurrency,
  formatTemperatureRange,
  parseTripPlanState,
} from "@/utils/resultPlan";

type MenuItem = {
  key: string;
  label: string;
};

type AMapNamespace = {
  Map: new (container: string | HTMLElement, options: Record<string, unknown>) => AMapMap;
  Marker: new (options: Record<string, unknown>) => unknown;
  Polyline: new (options: Record<string, unknown>) => unknown;
};

type AMapMap = {
  add: (overlay: unknown | unknown[]) => void;
  setFitView: () => void;
  destroy: () => void;
};

const route = useRoute();
const router = useRouter();
const mapContainerRef = ref<HTMLElement>();
const mapStatus = ref("地图待加载");
const mapInstance = ref<AMapMap | null>(null);

const tripPlan = computed<TripPlan | null>(() =>
  parseTripPlanState(window.history.state?.tripPlan ?? route.query.tripPlan),
);
const attractions = computed<Attraction[]>(() => collectAttractions(tripPlan.value));
const selectedMenuKeys = ref<string[]>(["overview"]);

const menuItems: MenuItem[] = [
  { key: "overview", label: "行程概览" },
  { key: "budget", label: "预算明细" },
  { key: "map", label: "地图" },
  { key: "daily", label: "每日行程" },
  { key: "weather", label: "天气" },
];

const totalDays = computed(() => tripPlan.value?.days.length ?? 0);

function scrollToSection(key: string): void {
  selectedMenuKeys.value = [key];
  document.getElementById(key)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function handleMenuClick(event: { key: string | number }): void {
  scrollToSection(String(event.key));
}

function goHome(): void {
  router.push({ name: "home" });
}

async function initMap(): Promise<void> {
  const key = import.meta.env.VITE_AMAP_WEB_KEY;
  if (!tripPlan.value || attractions.value.length === 0) {
    mapStatus.value = "暂无景点坐标";
    return;
  }
  if (!key) {
    mapStatus.value = "未配置高德地图 Key，已显示景点列表";
    return;
  }

  await nextTick();
  if (!mapContainerRef.value) {
    return;
  }

  try {
    const amap = (await AMapLoader.load({
      key,
      version: "2.0",
    })) as AMapNamespace;
    const first = attractions.value[0].location;
    const map = new amap.Map(mapContainerRef.value, {
      zoom: 12,
      center: [first.longitude, first.latitude],
    });
    const markers = attractions.value.map(
      (attraction) =>
        new amap.Marker({
          position: [attraction.location.longitude, attraction.location.latitude],
          title: attraction.name,
        }),
    );
    map.add(markers);
    if (attractions.value.length > 1) {
      map.add(
        new amap.Polyline({
          path: attractions.value.map((attraction) => [
            attraction.location.longitude,
            attraction.location.latitude,
          ]),
          strokeColor: "#c65d3a",
          strokeWeight: 4,
        }),
      );
    }
    map.setFitView();
    mapInstance.value = map;
    mapStatus.value = "地图已加载";
  } catch {
    mapStatus.value = "地图加载失败，已保留景点坐标列表";
  }
}

onMounted(() => {
  initMap();
});

onBeforeUnmount(() => {
  mapInstance.value?.destroy();
});
</script>

<template>
  <main class="result-page">
    <a-empty v-if="!tripPlan" description="暂无行程结果">
      <a-button type="primary" @click="goHome">返回生成行程</a-button>
    </a-empty>

    <div v-else class="result-shell">
      <aside class="side-nav">
        <a-menu
          v-model:selectedKeys="selectedMenuKeys"
          mode="inline"
          :items="menuItems"
          @click="handleMenuClick"
        />
      </aside>

      <section class="content">
        <section id="overview" class="section-panel overview">
          <div>
            <p class="eyebrow">Trip Plan</p>
            <h1>{{ tripPlan.city }}</h1>
            <p class="date-range">
              {{ tripPlan.start_date }} 至 {{ tripPlan.end_date }} · {{ totalDays }} 天
            </p>
          </div>
          <p class="suggestions">{{ tripPlan.overall_suggestions }}</p>
        </section>

        <section id="budget" class="section-panel">
          <div class="section-heading">
            <h2>预算明细</h2>
          </div>
          <a-row :gutter="[16, 16]">
            <a-col :xs="12" :md="6">
              <a-statistic title="门票" :value="formatCurrency(tripPlan.budget?.total_attractions)" />
            </a-col>
            <a-col :xs="12" :md="6">
              <a-statistic title="酒店" :value="formatCurrency(tripPlan.budget?.total_hotels)" />
            </a-col>
            <a-col :xs="12" :md="6">
              <a-statistic title="餐饮" :value="formatCurrency(tripPlan.budget?.total_meals)" />
            </a-col>
            <a-col :xs="12" :md="6">
              <a-statistic
                title="交通"
                :value="formatCurrency(tripPlan.budget?.total_transportation)"
              />
            </a-col>
          </a-row>
          <div class="total-budget">
            <span>总计</span>
            <strong>{{ formatCurrency(tripPlan.budget?.total) }}</strong>
          </div>
        </section>

        <section id="map" class="section-panel">
          <div class="section-heading">
            <h2>地图</h2>
            <span>{{ mapStatus }}</span>
          </div>
          <div ref="mapContainerRef" class="map-box">
            <div class="map-fallback">
              <span v-for="attraction in attractions" :key="attraction.name">
                {{ attraction.name }} · {{ attraction.location.longitude }},
                {{ attraction.location.latitude }}
              </span>
            </div>
          </div>
        </section>

        <section id="daily" class="section-panel">
          <div class="section-heading">
            <h2>每日行程</h2>
          </div>
          <a-collapse accordion>
            <a-collapse-panel
              v-for="day in tripPlan.days"
              :key="day.date"
              :header="`${day.date} · ${day.description}`"
            >
              <div class="day-meta">
                <a-tag color="green">{{ day.transportation }}</a-tag>
                <a-tag color="orange">{{ day.accommodation }}</a-tag>
              </div>

              <a-card v-if="day.hotel" class="sub-card" title="住宿" size="small">
                <strong>{{ day.hotel.name }}</strong>
                <p>{{ day.hotel.address }}</p>
                <span>{{ formatCurrency(day.hotel.estimated_cost) }}</span>
              </a-card>

              <div class="attraction-list">
                <article
                  v-for="attraction in day.attractions"
                  :key="`${day.date}-${attraction.name}`"
                  class="attraction-item"
                >
                  <img
                    v-if="attraction.image_url"
                    :src="attraction.image_url"
                    :alt="attraction.name"
                  />
                  <div class="attraction-copy">
                    <h3>{{ attraction.name }}</h3>
                    <p>{{ attraction.description }}</p>
                    <span>
                      {{ attraction.visit_duration }} 分钟 ·
                      {{ formatCurrency(attraction.ticket_price) }}
                    </span>
                  </div>
                </article>
              </div>

              <a-list size="small" :data-source="day.meals">
                <template #renderItem="{ item }">
                  <a-list-item>
                    <a-list-item-meta
                      :title="`${item.type} · ${item.name}`"
                      :description="`${item.address ?? '地址待补充'} · ${formatCurrency(item.estimated_cost)}`"
                    />
                  </a-list-item>
                </template>
              </a-list>
            </a-collapse-panel>
          </a-collapse>
        </section>

        <section id="weather" class="section-panel">
          <div class="section-heading">
            <h2>天气</h2>
          </div>
          <a-table
            :data-source="tripPlan.weather_info"
            :pagination="false"
            row-key="date"
            size="middle"
          >
            <a-table-column title="日期" data-index="date" />
            <a-table-column title="白天" data-index="day_weather" />
            <a-table-column title="夜间" data-index="night_weather" />
            <a-table-column title="温度">
              <template #default="{ record }">
                {{ formatTemperatureRange(record) }}
              </template>
            </a-table-column>
            <a-table-column title="风力风向">
              <template #default="{ record }">
                {{ record.wind_direction }} · {{ record.wind_power }}
              </template>
            </a-table-column>
          </a-table>
        </section>
      </section>
    </div>
  </main>
</template>

<style scoped>
.result-page {
  min-height: 100vh;
  background: #f7f3ec;
  color: #17231f;
  padding: 28px 24px 56px;
}

.result-shell {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 24px;
  max-width: 1240px;
  margin: 0 auto;
}

.side-nav {
  position: sticky;
  top: 24px;
  height: fit-content;
  overflow: hidden;
  border: 1px solid rgba(23, 35, 31, 0.1);
  border-radius: 8px;
  background: #fffdf8;
}

.content {
  display: grid;
  gap: 18px;
}

.section-panel {
  scroll-margin-top: 20px;
  border: 1px solid rgba(23, 35, 31, 0.1);
  border-radius: 8px;
  background: #fffdf8;
  padding: 24px;
  box-shadow: 0 18px 60px rgba(32, 39, 35, 0.08);
}

.overview {
  display: grid;
  grid-template-columns: minmax(240px, 0.7fr) 1fr;
  gap: 24px;
}

.eyebrow {
  margin: 0 0 8px;
  color: #b65337;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

h1,
h2,
h3,
p {
  margin-top: 0;
}

h1 {
  margin-bottom: 12px;
  font-family: Georgia, "Times New Roman", serif;
  font-size: 48px;
  line-height: 1;
  letter-spacing: 0;
}

h2 {
  margin-bottom: 0;
  font-size: 22px;
  letter-spacing: 0;
}

h3 {
  margin-bottom: 8px;
  font-size: 18px;
  letter-spacing: 0;
}

.date-range,
.suggestions {
  color: #53615d;
  line-height: 1.8;
}

.section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.section-heading span {
  color: #6a746f;
  font-size: 13px;
}

.total-budget {
  display: flex;
  align-items: baseline;
  justify-content: flex-end;
  gap: 14px;
  margin-top: 18px;
  padding-top: 18px;
  border-top: 1px solid rgba(23, 35, 31, 0.1);
}

.total-budget strong {
  color: #c65d3a;
  font-size: 30px;
}

.map-box {
  position: relative;
  min-height: 340px;
  overflow: hidden;
  border-radius: 8px;
  background:
    linear-gradient(90deg, rgba(23, 35, 31, 0.08) 1px, transparent 1px),
    linear-gradient(rgba(23, 35, 31, 0.08) 1px, transparent 1px),
    #edf0e7;
  background-size: 28px 28px;
}

.map-fallback {
  position: absolute;
  inset: auto 18px 18px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.map-fallback span {
  border: 1px solid rgba(23, 35, 31, 0.14);
  border-radius: 999px;
  background: rgba(255, 253, 248, 0.9);
  padding: 6px 10px;
  color: #394641;
  font-size: 12px;
}

.day-meta {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}

.sub-card {
  margin-bottom: 16px;
  border-radius: 8px;
}

.attraction-list {
  display: grid;
  gap: 14px;
  margin-bottom: 18px;
}

.attraction-item {
  display: grid;
  grid-template-columns: 156px 1fr;
  gap: 16px;
  align-items: stretch;
  border: 1px solid rgba(23, 35, 31, 0.1);
  border-radius: 8px;
  overflow: hidden;
  background: #ffffff;
}

.attraction-item img {
  width: 100%;
  height: 100%;
  min-height: 132px;
  object-fit: cover;
}

.attraction-copy {
  padding: 16px 16px 16px 0;
}

.attraction-copy p {
  color: #53615d;
  line-height: 1.7;
}

.attraction-copy span {
  color: #b65337;
  font-weight: 700;
}

:deep(.ant-statistic-content) {
  font-size: 22px;
}

@media (max-width: 900px) {
  .result-page {
    padding: 18px 14px 42px;
  }

  .result-shell {
    grid-template-columns: 1fr;
  }

  .side-nav {
    position: static;
  }

  .overview {
    grid-template-columns: 1fr;
  }

  h1 {
    font-size: 38px;
  }

  .attraction-item {
    grid-template-columns: 1fr;
  }

  .attraction-copy {
    padding: 16px;
  }
}
</style>
