# 技术规格与开发文档 (SPEC.md)

## 文档元信息

| 项目 | 内容 |
|------|------|
| 版本 | v1.0 |
| 最后更新 | 2026-06-19 |
| 关联文档 | README.md, PRD.md, AGENTS.md |

---

## 第一部分：系统架构

### 1.1 架构分层

```
┌──────────────────────────────────────────────────────┐
│                    Frontend Layer                      │
│  Vue 3 + TypeScript + Vite + Ant Design Vue           │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │ Home.vue │  │Result.vue│  │ AMap JS API Loader│  │
│  └──────────┘  └──────────┘  └───────────────────┘  │
│         │              │                               │
│    ┌────┴──────────────┴─────┐                        │
│    │   Axios (api.ts)        │                        │
│    │   POST /api/trip/plan   │                        │
│    └────────────┬────────────┘                        │
└─────────────────┼────────────────────────────────────┘
                  │  HTTP (JSON)
┌─────────────────┼────────────────────────────────────┐
│                 ▼          Backend Layer               │
│  FastAPI + Uvicorn                                    │
│  ┌───────────────┐  ┌──────────────┐                 │
│  │ routes/trip.py│  │ models/      │                 │
│  │ POST /trip/   │  │ schemas.py   │                 │
│  │ plan          │  │ (Pydantic)   │                 │
│  └───────┬───────┘  └──────────────┘                 │
│          │                                             │
│  ┌───────┴──────────────────────────────────┐        │
│  │          Agent Layer (自建引擎)             │        │
│  │  ┌──────────────────────────────────┐    │        │
│  │  │      TripPlannerAgent             │    │        │
│  │  │  ┌───────────┐ ┌──────────────┐  │    │        │
│  │  │  │ Attraction│ │ WeatherAgent │  │    │        │
│  │  │  │ Agent     │ │              │  │    │        │
│  │  │  └───────────┘ └──────────────┘  │    │        │
│  │  │  ┌───────────┐ ┌──────────────┐  │    │        │
│  │  │  │ HotelAgent│ │ PlannerAgent │  │    │        │
│  │  │  └───────────┘ └──────────────┘  │    │        │
│  │  └───────────────┬──────────────────┘    │        │
│  │                  │                        │        │
│  │  ┌───────────────┴──────────────────┐    │        │
│  │  │     Core Engine (core/)           │    │        │
│  │  │  ┌──────────┐ ┌───────────────┐  │    │        │
│  │  │  │AgentRunner│ │  MCPClient    │  │    │        │
│  │  │  │(运行循环) │  │(JSON-RPC通信) │  │    │        │
│  │  │  └─────┬────┘ └───────┬───────┘  │    │        │
│  │  │  ┌─────┴──────────────┴───────┐  │    │        │
│  │  │  │       LLMClient            │  │    │        │
│  │  │  │  (OpenAI兼容API封装)       │  │    │        │
│  │  │  └────────────────────────────┘  │    │        │
│  │  └──────────────────────────────────┘    │        │
│  └──────────────────────────────────────────┘        │
└──────────────────────────────────────────────────────┘
┌────────────────────────┼─────────────────────────────┐
│                        ▼    External Services          │
│  ┌────────────────┐ ┌──────────┐ ┌────────────────┐  │
│  │ 高德地图 API   │ │ Unsplash │ │ LLM API        │  │
│  │ (POI/天气/地图)│ │ API      │ │ (OpenAI/       │  │
│  │                │ │          │ │  DeepSeek)     │  │
│  └────────────────┘ └──────────┘ └────────────────┘  │
└──────────────────────────────────────────────────────┘
```

### 1.2 数据流

```
User Input (表单)
    │
    ▼
TripPlanRequest (Pydantic 验证)
    │
    ▼
TripPlannerAgent.plan_trip()
    │
    ├──► AgentRunner(Attraction).run(city, preferences)
    │         └─► LLMClient.chat() ↔ MCPClient.call_tool("amap_maps_text_search")
    │
    ├──► AgentRunner(Weather).run(city)
    │         └─► LLMClient.chat() ↔ MCPClient.call_tool("amap_maps_weather")
    │
    ├──► AgentRunner(Hotel).run(city, accommodation)
    │         └─► LLMClient.chat() ↔ MCPClient.call_tool("amap_maps_text_search")
    │
    ├──► _build_planner_query(request, ...)
    │         └─► 结构化提示词字符串
    │
    └──► AgentRunner(Planner).run(planner_query)
              └─► LLMClient.chat() → JSON → Pydantic TripPlan
    │
    ▼
UnsplashService 补充景点图片
    │
    ▼
TripPlan (JSON Response)
    │
    ▼
Frontend 渲染（行程卡片 + 地图 + 预算）
```

---

## 第二部分：数据模型

### 2.1 模型层级

```
Location (经纬度)
    ├──► Attraction (景点)
    ├──► Meal (餐饮)
    ├──► Hotel (酒店)
    └──► 作为以上模型的嵌套字段

WeatherInfo (天气) ──独立

Budget (预算) ──独立

DayPlan (每日行程)
    ├──► Attraction[] (多)
    ├──► Meal[] (多)
    └──► Hotel? (可选)

TripPlan (顶层)
    ├──► DayPlan[] (多)
    ├──► WeatherInfo[] (多)
    └──► Budget? (可选)
```

### 2.2 Pydantic 模型定义

#### Location
```python
class Location(BaseModel):
    longitude: float = Field(..., ge=-180, le=180, description="经度")
    latitude: float  = Field(..., ge=-90,  le=90,  description="纬度")
```

#### Attraction
```python
class Attraction(BaseModel):
    name:           str           # 景点名称
    address:        str           # 地址
    location:       Location      # 坐标
    visit_duration: int           # 建议游览时间(分钟), >0
    description:    str           # 景点描述
    category:       Optional[str] = "景点"          # 类别
    rating:         Optional[float] = None          # 评分 0-5
    image_url:      Optional[str] = None            # 图片URL
    ticket_price:   int = 0                         # 门票(元), >=0
```

#### Meal
```python
class Meal(BaseModel):
    type:           str                  # breakfast/lunch/dinner/snack
    name:           str                  # 餐饮名称
    address:        Optional[str] = None # 地址
    location:       Optional[Location]   # 坐标
    description:    Optional[str] = None # 描述
    estimated_cost: int = 0              # 预估费用(元)
```

#### Hotel
```python
class Hotel(BaseModel):
    name:           str
    address:        str = ""
    location:       Optional[Location] = None
    price_range:    str = ""
    rating:         str = ""
    distance:       str = ""
    type:           str = ""
    estimated_cost: int = 0
```

#### Budget
```python
class Budget(BaseModel):
    total_attractions:    int = 0  # 门票总费用
    total_hotels:         int = 0  # 酒店总费用
    total_meals:          int = 0  # 餐饮总费用
    total_transportation: int = 0  # 交通总费用
    total:                int = 0  # 总费用 (= 前四项之和)
```

#### WeatherInfo
```python
class WeatherInfo(BaseModel):
    date:           str                   # YYYY-MM-DD
    day_weather:    str                   # 白天天气
    night_weather:  str                   # 夜间天气
    day_temp:       int                   # 白天温度(纯数字)
    night_temp:     int                   # 夜间温度(纯数字)
    wind_direction: str                   # 风向
    wind_power:     str                   # 风力

    @field_validator('day_temp', 'night_temp', mode='before')
    def parse_temperature(cls, v):
        if isinstance(v, str):
            v = v.replace('°C','').replace('℃','').replace('°','').strip()
            try: return int(v)
            except ValueError: return 0
        return v
```

#### DayPlan
```python
class DayPlan(BaseModel):
    date:            str
    day_index:       int                    # 从 0 开始
    description:     str                    # 当日概述
    transportation:  str                    # 交通方式
    accommodation:   str                    # 住宿安排
    hotel:           Optional[Hotel] = None
    attractions:     List[Attraction] = []
    meals:           List[Meal] = []
```

#### TripPlan（顶层）
```python
class TripPlan(BaseModel):
    city:                str
    start_date:          str                # YYYY-MM-DD
    end_date:            str                # YYYY-MM-DD
    days:                List[DayPlan] = []
    weather_info:        List[WeatherInfo] = []
    overall_suggestions: str
    budget:              Optional[Budget] = None
```

#### TripPlanRequest（请求体）
```python
class TripPlanRequest(BaseModel):
    city:           str            # 目的地城市
    start_date:     str            # YYYY-MM-DD
    end_date:       str            # YYYY-MM-DD
    days:           int            # 天数, >=1
    preferences:    str = "历史文化" # 用户偏好
    budget:         str = "中等"    # 预算水平
    transportation: str = "公共交通" # 交通方式
    accommodation:  str = "经济型酒店" # 住宿类型
```

### 2.3 TypeScript 类型（前端对应）

```typescript
// types/index.ts

export interface Location {
  longitude: number;
  latitude: number;
}

export interface Attraction {
  name: string;
  address: string;
  location: Location;
  visit_duration: number;
  description: string;
  category?: string;
  rating?: number;
  image_url?: string;
  ticket_price: number;
}

export interface Meal {
  type: 'breakfast' | 'lunch' | 'dinner' | 'snack';
  name: string;
  address?: string;
  location?: Location;
  description?: string;
  estimated_cost: number;
}

export interface Hotel {
  name: string;
  address: string;
  location?: Location;
  price_range: string;
  rating: string;
  distance: string;
  type: string;
  estimated_cost: number;
}

export interface Budget {
  total_attractions: number;
  total_hotels: number;
  total_meals: number;
  total_transportation: number;
  total: number;
}

export interface WeatherInfo {
  date: string;
  day_weather: string;
  night_weather: string;
  day_temp: number;
  night_temp: number;
  wind_direction: string;
  wind_power: string;
}

export interface DayPlan {
  date: string;
  day_index: number;
  description: string;
  transportation: string;
  accommodation: string;
  hotel?: Hotel;
  attractions: Attraction[];
  meals: Meal[];
}

export interface TripPlan {
  city: string;
  start_date: string;
  end_date: string;
  days: DayPlan[];
  weather_info: WeatherInfo[];
  overall_suggestions: string;
  budget?: Budget;
}

export interface TripPlanRequest {
  city: string;
  start_date: string;
  end_date: string;
  days: number;
  preferences: string;
  budget: string;
  transportation: string;
  accommodation: string;
}
```

---

## 第三部分：API 接口定义

### 3.1 核心接口

#### POST /api/trip/plan — 生成旅行计划

**请求**

```
POST /api/trip/plan
Content-Type: application/json
```

```json
{
  "city": "北京",
  "start_date": "2026-07-01",
  "end_date": "2026-07-03",
  "days": 3,
  "preferences": "历史文化",
  "budget": "中等",
  "transportation": "公共交通",
  "accommodation": "经济型酒店"
}
```

**成功响应** (200)

```json
{
  "city": "北京",
  "start_date": "2026-07-01",
  "end_date": "2026-07-03",
  "days": [
    {
      "date": "2026-07-01",
      "day_index": 0,
      "description": "抵达北京，游览天安门广场和故宫博物院...",
      "transportation": "公共交通",
      "accommodation": "经济型酒店",
      "hotel": {
        "name": "如家快捷酒店(天安门店)",
        "address": "东城区xxx",
        "location": { "longitude": 116.4, "latitude": 39.9 },
        "price_range": "200-400元",
        "rating": "4.3",
        "distance": "步行10分钟至天安门",
        "type": "经济型酒店",
        "estimated_cost": 300
      },
      "attractions": [
        {
          "name": "天安门广场",
          "address": "东城区长安街",
          "location": { "longitude": 116.397, "latitude": 39.908 },
          "visit_duration": 60,
          "description": "世界上最大的城市广场",
          "category": "历史文化",
          "rating": 4.8,
          "image_url": "https://images.unsplash.com/...",
          "ticket_price": 0
        }
      ],
      "meals": [
        {
          "type": "lunch",
          "name": "大碗居(东华门店)",
          "address": "东城区x号",
          "estimated_cost": 60
        }
      ]
    }
  ],
  "weather_info": [
    {
      "date": "2026-07-01",
      "day_weather": "晴",
      "night_weather": "多云",
      "day_temp": 32,
      "night_temp": 22,
      "wind_direction": "南",
      "wind_power": "≤3级"
    }
  ],
  "overall_suggestions": "7月北京较热，建议携带防晒用品...",
  "budget": {
    "total_attractions": 120,
    "total_hotels": 900,
    "total_meals": 450,
    "total_transportation": 90,
    "total": 1560
  }
}
```

**错误响应**

| HTTP 状态码 | 场景 |
|-------------|------|
| 400 | 参数验证失败（日期格式错误、必填项缺失） |
| 422 | 业务逻辑错误（结束日期早于开始日期） |
| 500 | 内部错误（LLM 调用失败、MCP 超时） |
| 504 | 上游超时（超过 120 秒） |

```json
{
  "detail": "规划生成失败，请稍后重试"
}
```

### 3.2 扩展接口（v1.1）

```
GET  /api/trip/history          # 获取历史行程列表
GET  /api/trip/history/{id}     # 获取指定历史行程
POST /api/trip/plan/alternatives # 生成多方案对比
```

---

## 第四部分：分步骤开发计划

---

### Phase 0: 项目初始化（预计 2-3 小时）

#### Step 0.1: 创建项目目录结构

```
ai-travel-planner/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   └── routes/
│   │   │       ├── __init__.py
│   │   │       └── trip.py
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   └── planner.py
│   │   ├── core/               # 自建引擎（零框架依赖）
│   │   │   ├── __init__.py
│   │   │   ├── llm_client.py   # LLM API 封装
│   │   │   ├── mcp_client.py   # MCP JSON-RPC 客户端
│   │   │   └── agent_runner.py # Agent 运行循环
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── schemas.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   └── unsplash.py
│   │   └── config.py
│   ├── requirements.txt
│   ├── .env.example
│   └── run.py
├── frontend/
│   ├── src/
│   │   ├── views/
│   │   │   ├── Home.vue
│   │   │   └── Result.vue
│   │   ├── services/
│   │   │   └── api.ts
│   │   ├── types/
│   │   │   └── index.ts
│   │   ├── router/
│   │   │   └── index.ts
│   │   ├── App.vue
│   │   └── main.ts
│   ├── public/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
└── docs/
    ├── README.md
    ├── AGENTS.md
    ├── PRD.md
    └── SPEC.md
```

**检查点**：
- [ ] 目录结构创建完毕
- [ ] 后端虚拟环境创建、依赖安装
- [ ] 前端项目脚手架搭建（Vite + Vue3 + TS）
- [ ] `.gitignore` 配置完成

---

### Phase 1: 数据模型层（预计 2-3 小时）

#### Step 1.1: 定义 Pydantic 模型

- 文件：`backend/app/models/schemas.py`
- 按层级自底向上实现：
  1. `Location` — 经纬度基础模型
  2. `Attraction` — 景点模型
  3. `Meal` — 餐饮模型
  4. `Hotel` — 酒店模型
  5. `WeatherInfo` — 天气模型（含 temperature validator）
  6. `Budget` — 预算模型
  7. `DayPlan` — 每日行程模型
  8. `TripPlan` — 完整行程模型（顶层）
  9. `TripPlanRequest` — 请求体模型

#### Step 1.2: 定义前端 TypeScript 类型

- 文件：`frontend/src/types/index.ts`
- 与后端 Pydantic 模型一一对应
- 确保字段名和类型一致

**检查点**：
- [ ] `from app.models.schemas import TripPlan, TripPlanRequest` 可正常导入
- [ ] Pydantic 模型含字段验证（ge/le/gt 约束）
- [ ] 前端 TS 类型编译无错误
- [ ] 创建测试用例验证模型序列化/反序列化

---

### Phase 2: 配置与基础设施（预计 1-2 小时）

#### Step 2.1: 配置管理

- 文件：`backend/app/config.py`
- 使用 Pydantic Settings 管理配置：

| 配置项 | 来源 | 说明 |
|--------|------|------|
| `LLM_API_KEY` | 环境变量 | LLM API 密钥 |
| `LLM_MODEL` | 环境变量 | 模型名称，默认 `gpt-4o` |
| `LLM_BASE_URL` | 环境变量 | API 地址 |
| `AMAP_API_KEY` | 环境变量 | 高德 Web 服务 Key |
| `AMAP_WEB_KEY` | 环境变量 | 高德 JS API Key（前端用） |
| `UNSPLASH_ACCESS_KEY` | 环境变量 | Unsplash API Key |

#### Step 2.2: FastAPI 应用入口

- 文件：`backend/app/api/main.py`
- 创建 FastAPI 实例
- 配置 CORS 中间件（允许前端 `localhost:5173`）
- 注册路由
- 添加异常处理器

#### Step 2.3: 前端路由与 API 封装

- 文件：`frontend/src/router/index.ts`
  - `GET /` → `Home.vue`
  - `GET /result` → `Result.vue`（通过 state 传递 tripPlan）
- 文件：`frontend/src/services/api.ts`
  - Axios 实例（baseURL、timeout=120000）
  - `generateTripPlan(request: TripPlanRequest): Promise<TripPlan>`

**检查点**：
- [ ] FastAPI 启动 `uvicorn app.api.main:app --reload` 无报错
- [ ] `http://localhost:8000/docs` 可访问
- [ ] 前端 `npm run dev` 启动正常
- [ ] 前端可访问 `http://localhost:5173`

---

### Phase 3A: LLM Client 封装（预计 1-2 小时）

> **目标**：实现统一的 LLM API 调用封装，支持 OpenAI / DeepSeek 兼容接口

#### Step 3A.1: 实现 LLMClient 类

- 文件：`backend/app/core/llm_client.py`

**类结构**：

```python
class LLMClient:
    def __init__(self, api_key, base_url, model, timeout=90):
        ...
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> str:
        """发送 chat completion 请求，返回文本响应"""
        ...
    
    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> Generator[str, None, None]:
        """流式版本（可选，用于进度推送）"""
        ...
```

**实现要点**：
- 使用 `httpx` 或 `requests` 调用 `/v1/chat/completions`
- 自动获取 `response.choices[0].message.content`
- 3 次重试（指数退避：1s, 2s, 4s）
- 异常映射：`httpx.TimeoutException` → 自定义 `LLMTimeoutError`

**检查点**：
- [ ] `LLMClient.chat()` 返回正确文本
- [ ] 支持 DeepSeek 兼容接口
- [ ] 重试机制工作正常
- [ ] 超时异常可被上层捕获

---

### Phase 3B: MCP Client 实现（预计 2-3 小时）

> **目标**：从零实现 MCP JSON-RPC 客户端，管理高德 MCP Server 子进程

#### Step 3B.1: 实现 MCPClient 子进程管理

- 文件：`backend/app/core/mcp_client.py`

**类结构**：

```python
class MCPClient:
    def __init__(self, command: str, args: list, env: dict = None):
        self.command = command     # "npx"
        self.args = args           # ["-y", "@sugarforever/amap-mcp-server"]
        self.env = env             # {"AMAP_API_KEY": "..."}
        self.process = None        # subprocess.Popen
        self.request_id = 0        # JSON-RPC 自增 ID
        self.tools = {}            # 已发现的工具 {name: ToolSchema}
    
    def start(self):
        """启动 MCP Server 子进程 (stdin=PIPE, stdout=PIPE)"""
        ...
    
    def initialize(self) -> dict:
        """发送 initialize 请求，获取服务器能力"""
        ...
    
    def list_tools(self) -> List[ToolSchema]:
        """发送 tools/list 请求，获取全部工具定义并存入 self.tools"""
        ...
    
    def call_tool(self, name: str, arguments: dict) -> dict:
        """发送 tools/call 请求，执行工具并返回结果"""
        ...
    
    def close(self):
        """终止子进程"""
        ...
    
    def _send_request(self, method: str, params: dict) -> dict:
        """核心：json.dumps 写入 stdin → json.loads 读取 stdout"""
        ...
```

**JSON-RPC 协议实现要点**：

```
每行一个完整的 JSON 对象（MCP 使用 \n 分隔）:

写入 stdin:
  {"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}

从 stdout 读取:
  {"jsonrpc":"2.0","id":1,"result":{"tools":[{"name":"maps_text_search",...}, ...]}}

工具调用:
  写入: {"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"maps_text_search","arguments":{"keywords":"博物馆","city":"北京"}}}
  读取: {"jsonrpc":"2.0","id":2,"result":{"content":[{"type":"text","text":"..."}]}}
```

**子进程管理要点**：
- 使用 `subprocess.Popen` 启动
- `stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE`
- 非阻塞读取 stdout（使用 `select` 或超时机制）
- `close()` 时调用 `process.terminate()` + `process.wait()`

**检查点**：
- [ ] MCP Server 成功启动（进程存在）
- [ ] `initialize()` 返回服务器能力信息
- [ ] `list_tools()` 返回 16 个工具定义
- [ ] `call_tool()` 可调用任意工具并返回正确结果
- [ ] `close()` 正常终止子进程
- [ ] 子进程崩溃时能自动重启

---

### Phase 3C: Agent Runner 实现（预计 2-3 小时）

> **目标**：实现 Agent 运行循环引擎，管理提示词、工具调用和 LLM 交互

#### Step 3C.1: 实现 AgentRunner 类

- 文件：`backend/app/core/agent_runner.py`

**类结构**：

```python
class AgentRunner:
    def __init__(
        self,
        name: str,
        system_prompt: str,
        tools: List[ToolSchema],   # 从 MCPClient.list_tools() 获取
        llm: LLMClient,
        mcp: Optional[MCPClient],  # PlannerAgent 不需要 MCP
        max_tool_rounds: int = 5   # 最多工具调用轮次（防止死循环）
    ):
        ...
    
    def run(self, **kwargs) -> str:
        """
        主运行循环:
        1. 填充提示词模板（用 kwargs 替换 {city}, {preferences} 等）
        2. LLM 调用 → 检查响应
        3. 如果包含 [TOOL_CALL:...] → 解析 → 调用 MCP → 结果追加 → 回到 2
        4. 如果不包含工具调用 → 返回最终文本
        """
        ...
    
    def _fill_prompt(self, template: str, **kwargs) -> str:
        """用参数填充提示词中的 {变量} 占位符"""
        ...
    
    def _parse_tool_call(self, text: str) -> Optional[Tuple[str, dict]]:
        """
        解析 [TOOL_CALL:tool_name:key1=val1,key2=val2] 格式
        返回 (tool_name, {key1: val1, key2: val2}) 或 None
        """
        ...
    
    def _build_tools_prompt(self) -> str:
        """将可用工具列表格式化为提示词中的工具说明段落"""
        ...
```

**工具调用标记解析**（核心正则）：

```python
import re

def _parse_tool_call(self, text: str):
    pattern = r'\[TOOL_CALL:(\w+):([^\]]+)\]'
    match = re.search(pattern, text)
    if not match:
        return None
    tool_name = match.group(1)
    args_str = match.group(2)
    args = {}
    for pair in args_str.split(','):
        k, v = pair.split('=', 1)
        args[k.strip()] = v.strip()
    return tool_name, args
```

**运行循环伪代码**：

```python
def run(self, **kwargs) -> str:
    messages = [
        {"role": "system", "content": self._fill_prompt(self.system_prompt, **kwargs)},
        {"role": "user", "content": f"请开始执行任务。"}
    ]
    
    for round in range(self.max_tool_rounds):
        response = self.llm.chat(messages)
        
        tool_call = self._parse_tool_call(response)
        if tool_call is None:
            return response  # 没有工具调用，返回最终结果
        
        tool_name, tool_args = tool_call
        result = self.mcp.call_tool(tool_name, tool_args)
        
        # 追加到消息历史，让 LLM 继续
        messages.append({"role": "assistant", "content": response})
        messages.append({"role": "user", "content": f"工具调用结果:\n{json.dumps(result, ensure_ascii=False)}"})
    
    raise RuntimeError(f"Agent {self.name} 超过最大工具调用轮次")
```

**检查点**：
- [ ] `_parse_tool_call()` 正确解析所有 16 种工具调用格式
- [ ] Agent 单次工具调用流程正常
- [ ] Agent 多轮工具调用流程正常
- [ ] 超过 max_tool_rounds 时正确抛出异常
- [ ] 不带工具的 Agent (PlannerAgent) 正常返回

---

### Phase 3D: 四个 Agent 实现（预计 2-3 小时）

> **目标**：使用 AgentRunner + 自定义提示词创建四个专业 Agent

- 文件：`backend/app/agents/planner.py`

#### Step 3D.1: AttractionSearchAgent 提示词

```python
ATTRACTION_AGENT_PROMPT = """你是景点搜索专家。

可用工具:
{tools_description}

任务: 搜索 {city} 的景点，偏好: {preferences}

根据偏好选择合适的搜索关键词:
- 历史文化: 博物馆、古迹、历史遗址
- 自然风光: 公园、山水、自然风景区
- 美食购物: 商圈、美食街、特色市场
- 亲子游玩: 游乐园、动物园、亲子活动
- 文艺打卡: 美术馆、创意园、网红景点

请使用工具搜索多个关键词，每种偏好搜索1-2个关键词。
搜索后整理为景点列表，包含每个景点的: 名称、地址、坐标(经度/纬度)、评分、类别。
"""
```

#### Step 3D.2: WeatherQueryAgent 提示词

```python
WEATHER_AGENT_PROMPT = """你是天气查询专家。

可用工具:
{tools_description}

任务: 查询 {city} 的天气预报。

请使用天气查询工具获取天气信息。
返回每日天气: 日期、白天天气、夜间天气、温度(纯数字)、风力风向。
"""
```

#### Step 3D.3: HotelAgent 提示词

```python
HOTEL_AGENT_PROMPT = """你是酒店推荐专家。

可用工具:
{tools_description}

任务: 搜索 {city} 的酒店，住宿偏好: {accommodation}

根据住宿类型选择合适的搜索关键词:
- 经济型酒店: 经济型酒店、快捷酒店
- 舒适型酒店: 三星酒店、舒适型酒店
- 豪华型酒店: 五星级酒店、豪华酒店、度假酒店
- 民宿: 民宿、客栈

请使用工具搜索，返回酒店列表，包含: 名称、地址、评分、价格范围、类型。
"""
```

#### Step 3D.4: PlannerAgent 提示词

```python
PLANNER_AGENT_PROMPT = """你是行程规划专家。你不需要使用任何工具，只需根据提供的信息整合生成行程计划。

请严格按照以下JSON格式输出旅行计划:
{... 完整的 JSON Schema ...}

规划要求:
1. weather_info 必须包含每天的天气
2. 温度必须为纯数字(不含°C)
3. 每天安排2-3个景点，考虑景点间的距离和游览时间
4. 包含早中晚三餐推荐
5. 提供实用的旅行建议
6. 包含预算估算

输入信息:
- 用户需求: {user_request}
- 景点搜索结果: {attractions_info}
- 天气预报: {weather_info}
- 酒店推荐: {hotels_info}
"""
```

#### Step 3D.5: TripPlannerAgent 编排类

```python
class TripPlannerAgent:
    def __init__(self):
        self.llm = LLMClient(...)
        self.mcp = MCPClient(
            command="npx",
            args=["-y", "@sugarforever/amap-mcp-server"],
            env={"AMAP_API_KEY": settings.amap_api_key}
        )
        self.mcp.start()
        self.mcp.initialize()
        tools = self.mcp.list_tools()
        
        # 三个搜索 Agent 共享 mcp 实例
        self.attraction_agent = AgentRunner(
            name="AttractionSearch",
            system_prompt=ATTRACTION_AGENT_PROMPT,
            tools=[t for t in tools if t["name"] == "maps_text_search"],
            llm=self.llm, mcp=self.mcp
        )
        self.weather_agent = AgentRunner(
            name="WeatherQuery",
            system_prompt=WEATHER_AGENT_PROMPT,
            tools=[t for t in tools if t["name"] == "maps_weather"],
            llm=self.llm, mcp=self.mcp
        )
        self.hotel_agent = AgentRunner(
            name="HotelSearch",
            system_prompt=HOTEL_AGENT_PROMPT,
            tools=[t for t in tools if t["name"] == "maps_text_search"],
            llm=self.llm, mcp=self.mcp
        )
        # PlannerAgent 不需要 MCP
        self.planner_agent = AgentRunner(
            name="Planner",
            system_prompt=PLANNER_AGENT_PROMPT,
            tools=[], llm=self.llm, mcp=None
        )
    
    def plan_trip(self, request: TripPlanRequest) -> TripPlan:
        attractions = self.attraction_agent.run(
            city=request.city, preferences=request.preferences
        )
        weather = self.weather_agent.run(city=request.city)
        hotels = self.hotel_agent.run(
            city=request.city, accommodation=request.accommodation
        )
        query = self._build_planner_query(request, attractions, weather, hotels)
        planner_response = self.planner_agent.run(query=query)
        return self._parse_trip_plan(planner_response)
    
    def _build_planner_query(self, request, attractions, weather, hotels) -> str:
        return json.dumps({
            "user_request": request.model_dump(),
            "attractions_info": attractions,
            "weather_info": weather,
            "hotels_info": hotels
        }, ensure_ascii=False)
    
    def _parse_trip_plan(self, response: str) -> TripPlan:
        # 从 LLM 响应中提取 JSON（处理 markdown 代码块包裹）
        json_str = response
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0]
        data = json.loads(json_str.strip())
        return TripPlan(**data)
```

**检查点**：
- [ ] 每个 Agent 可独立运行并返回正确格式的结果
- [ ] MCPClient 成功连接高德地图服务
- [ ] PlannerAgent JSON 输出格式正确
- [ ] `_parse_trip_plan()` 正确解析 LLM 响应（含 markdown 包裹场景）
- [ ] 完整编排流程可生成有效 TripPlan
- [ ] MCP 超时 / LLM 返回非法 JSON 时有异常处理
- [ ] TripPlannerAgent 销毁时调用 `self.mcp.close()` 清理子进程

---

### Phase 4: API 路由层（预计 2-3 小时）

#### Step 4.1: 实现行程规划路由

- 文件：`backend/app/api/routes/trip.py`
- 端点：`POST /api/trip/plan`
- 流程：
  1. 接收 `TripPlanRequest`（FastAPI 自动验证）
  2. 调用 `TripPlannerAgent.plan_trip()`
  3. 调用 `UnsplashService` 为景点补充图片
  4. 返回 `TripPlan`

#### Step 4.2: 实现 Unsplash 图片服务

- 文件：`backend/app/services/unsplash.py`
- `search_photos(query, per_page)` → 图片 URL 列表
- `get_photo_url(query)` → 单张图片 URL
- 在路由层遍历每个景点的 `attractions`，为空 `image_url` 的景点补充图片

#### Step 4.3: 错误处理

- LLM 调用超时 → 返回 504
- MCPClient.call_tool() 失败 → 返回 500
- LLM 返回非 JSON → 重试 1 次，仍失败则返回 500
- 高德 API Key 无效 → TripPlannerAgent 初始化时检测

**检查点**：
- [ ] `POST /api/trip/plan` 返回 200 + TripPlan
- [ ] 无效参数返回 422
- [ ] Swagger 文档可测试接口
- [ ] Unsplash 图片正确填充

---

### Phase 5: 前端首页（预计 2-3 小时）

#### Step 5.1: Home.vue — 表单设计

- 使用 Ant Design Vue 组件：
  | 组件 | 用途 |
  |------|------|
  | `a-form` / `a-form-item` | 表单容器 |
  | `a-input` | 城市名称输入 |
  | `a-date-picker` | 开始/结束日期选择 |
  | `a-input-number` | 天数输入 |
  | `a-select` | 偏好/预算/交通/住宿下拉选择 |
  | `a-button` | 提交按钮 |
  | `a-progress` | 生成进度条 |
  | `a-card` | 内容卡片容器 |
  | `a-message` | 错误/成功消息提示 |

#### Step 5.2: 表单验证规则

| 字段 | 规则 |
|------|------|
| city | 必填，中文城市名 |
| start_date | 必填，日期格式 |
| end_date | 必填，>= start_date |
| days | 自动计算 = end - start + 1 |
| preferences | 下拉选择（5 个选项） |
| budget | 下拉选择（3 个选项） |
| transportation | 下拉选择（4 个选项） |
| accommodation | 下拉选择（4 个选项） |

#### Step 5.3: 提交流程与进度模拟

1. 表单验证通过 → `loading = true`
2. 启动 `setInterval(500ms)` 模拟进度
3. 进度映射状态文字：
   - 0-30%: "正在搜索景点..."
   - 31-50%: "正在查询天气..."
   - 51-70%: "正在推荐酒店..."
   - 71-90%: "正在生成行程计划..."
   - 100%: "完成！"
4. 调用 `generateTripPlan(request)`
5. 成功 → 清除定时器，`router.push('/result', { state: { tripPlan } })`
6. 失败 → 停止定时器，`a-message.error()`

**检查点**：
- [ ] 表单所有字段渲染正确
- [ ] 日期联动计算天数
- [ ] 进度条和状态文字正确显示
- [ ] 提交成功跳转 Result 页
- [ ] 提交失败显示错误消息

---

### Phase 6: 前端结果页（预计 4-6 小时）

#### Step 6.1: Result.vue — 页面布局

使用 Ant Design Vue 栅格系统：

```
┌──────────────────────────────────────────────┐
│  [a-row]                                      │
│    [a-col :span="6"]    [a-col :span="18"]    │
│    ┌──────────────┐    ┌───────────────────┐  │
│    │ a-menu 侧边  │    │ 行程概览 (#overview)│  │
│    │ 导航          │    │ 预算明细 (#budget)  │  │
│    │              │    │ 地图   (#map)       │  │
│    │              │    │ 每日行程(#daily)     │  │
│    │              │    │ 天气   (#weather)    │  │
│    └──────────────┘    └───────────────────┘  │
└──────────────────────────────────────────────┘
```

#### Step 6.2: 行程概览区域

- 展示城市、日期范围、天数、总体建议
- 组件：`a-card` + 文字排版

#### Step 6.3: 预算明细区域

- 四项费用 + 总计
- 组件：`a-statistic` (Ant Design Vue)
- 总计使用突出样式（颜色/字号）

#### Step 6.4: 地图可视化

- 使用 `@amap/amap-jsapi-loader` 加载高德地图
- 初始化：
  ```typescript
  AMapLoader.load({ key: amapWebKey, version: '2.0' })
  map = new AMap.Map('map-container', { zoom: 12, center: [lng, lat] })
  ```
- 遍历所有景点的 `location`，为每个创建 `AMap.Marker`
- 可选：使用 `AMap.Polyline` 描绘路线连线

#### Step 6.5: 每日行程详情

- 按 `day_index` 分组渲染
- 每日包含：日期标题、交通/住宿信息、酒店卡片、景点列表（名称/图片/描述/时长/门票）、餐饮列表
- 支持展开/折叠

#### Step 6.6: 天气信息

- 表格或卡片形式展示每日天气
- 字段：日期、白天天气、夜间天气、温度范围、风力风向

#### Step 6.7: 侧边导航锚点

- 使用 `a-menu` 垂直模式
- 菜单项：行程概览、预算明细、地图、每日行程、天气
- 点击调用 `document.getElementById(id).scrollIntoView({ behavior: 'smooth' })`

**检查点**：
- [ ] 页面正确渲染所有区域
- [ ] 地图加载并显示景点 Marker
- [ ] 侧边导航平滑滚动
- [ ] 预算数字正确显示
- [ ] 无 TripPlan 数据时有空状态处理

---

### Phase 7: 行程编辑功能（预计 2-3 小时）

#### Step 7.1: 编辑模式切换

- 状态：`isEditing: ref(false)`
- 进入编辑：`originalPlan = JSON.parse(JSON.stringify(tripPlan))`
- 保存：更新 tripPlan，重新 initMap
- 取消：`tripPlan = originalPlan`

#### Step 7.2: 景点操作

**上移**：交换 `attractions[i]` 与 `attractions[i-1]`

**下移**：交换 `attractions[i]` 与 `attractions[i+1]`

**删除**：`attractions.splice(i, 1)`

**添加**（v1.1）：弹出搜索框，调用景点搜索添加

#### Step 7.3: 按钮显隐控制

- 编辑模式：显示上移/下移/删除按钮，显示保存/取消
- 只读模式：显示编辑按钮、导出按钮

**检查点**：
- [ ] 编辑操作正确修改 tripPlan
- [ ] 保存后地图更新
- [ ] 取消后完全恢复原始数据
- [ ] 边界情况：首项无上移、末项无下移

---

### Phase 8: 导出功能（预计 1-2 小时）

#### Step 8.1: 导出为图片

- 库：`html2canvas`
- 目标 DOM：行程内容区域（排除地图以避免 Canvas 兼容问题）
- 参数：`{ scale: 2, useCORS: true }`
- 下载：创建 `<a>` 标签触发

#### Step 8.2: 导出为 PDF

- 库：`jspdf`
- 流程：html2canvas → Canvas → toDataURL → jsPDF.addImage
- 格式：A4 纸张，保持宽高比
- 多页：计算高度，超出时换页

#### Step 8.3: 地图导出替代方案

- 当前：导出时隐藏地图区域
- 备选：高德静态地图 API 生成图片嵌入
- 备选：服务端 Puppeteer 截图

**检查点**：
- [ ] 导出图片文件正确
- [ ] 导出 PDF 文件正确
- [ ] 地图区域有降级处理

---

### Phase 9: 测试（预计 2-3 小时）

#### Step 9.1: 后端测试

| 测试类型 | 内容 | 工具 |
|----------|------|------|
| 单元测试 | Pydantic 模型验证 | pytest |
| 单元测试 | config 配置加载 | pytest |
| 单元测试 | UnsplashService | pytest + mock |
| 集成测试 | Agent 单个运行 | pytest |
| 集成测试 | API 端点 | pytest + httpx |

#### Step 9.2: 前端测试

| 测试类型 | 内容 |
|----------|------|
| 组件测试 | Home.vue 表单验证 |
| 组件测试 | Result.vue 渲染 |
| E2E | 完整流程（选填） |

#### Step 9.3: 手动测试 checklist

| 场景 | 步骤 |
|------|------|
| 正常流程 | 输入所有参数 → 生成 → 查看结果 |
| 边界值 | 1 天行程、30 天行程 |
| 异常输入 | 空城市、无效日期 |
| 编辑流程 | 编辑 → 上移/下移/删除 → 保存/取消 |
| 导出流程 | 导出 PDF / 导出图片 |
| 网络异常 | 后端未启动时的前端错误提示 |

---

### Phase 10: 部署准备（预计 1-2 小时）

#### Step 10.1: 构建配置

- 后端：Dockerfile 或直接部署
  ```
  FROM python:3.10-slim
  COPY . /app
  RUN pip install -r requirements.txt
  CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
  ```
- 前端：`npm run build` → 静态文件

#### Step 10.2: 环境变量

- 服务端通过 `.env` 或平台环境变量注入
- 前端通过构建时注入或运行时配置
- 高德 JS API Key 在前端配置中

#### Step 10.3: Nginx 反向代理（可选）

```
location /api/ {
    proxy_pass http://backend:8000;
}
location / {
    root /var/www/frontend/dist;
    try_files $uri /index.html;
}
```

---

## 第五部分：配置与环境变量

### 5.1 后端 .env 文件

```bash
# LLM 配置
LLM_API_KEY=sk-your-api-key-here
LLM_MODEL=gpt-4o
LLM_BASE_URL=https://api.openai.com/v1

# 高德地图 API（Web 服务端）
AMAP_API_KEY=your-amap-web-api-key

# Unsplash 图片
UNSPLASH_ACCESS_KEY=your-unsplash-access-key
```

### 5.2 前端环境变量

```bash
# .env.development / .env.production
VITE_API_BASE_URL=http://localhost:8000/api
VITE_AMAP_WEB_KEY=your-amap-js-api-key
```

---

## 第六部分：依赖清单

### 6.1 Python (requirements.txt)

```
# Web 框架
fastapi>=0.110.0
uvicorn[standard]>=0.27.0

# 数据验证与配置
pydantic>=2.6.0
pydantic-settings>=2.1.0
python-dotenv>=1.0.0

# HTTP 客户端（LLM API + Unsplash）
httpx>=0.27.0

# 无 Agent 框架依赖 —— MCP Client / Agent Runner / LLM Client 全部自建
```

### 6.2 Node.js (package.json)

```json
{
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.3.0",
    "ant-design-vue": "^4.1.0",
    "axios": "^1.6.0",
    "@amap/amap-jsapi-loader": "^1.0.1",
    "html2canvas": "^1.4.1",
    "jspdf": "^2.5.1"
  },
  "devDependencies": {
    "typescript": "^5.3.0",
    "vite": "^5.1.0",
    "@vitejs/plugin-vue": "^5.0.0",
    "vue-tsc": "^2.0.0"
  }
}
```

---

## 第七部分：关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| Agent 框架 | **自建，零依赖** | 仅约 400 行核心代码，完全可控，不受框架版本升级影响 |
| 多 Agent vs 单 Agent | 多 Agent | 职责分离，提示词更可控，便于调试 |
| MCP 通信方式 | 自建 JSON-RPC 客户端 | MCP 协议公开标准，不依赖任何框架实现 |
| LLM 调用 | 自建 LLMClient | OpenAI 接口已是事实标准，封装 60 行即可 |
| 工具调用约定 | `[TOOL_CALL:...]` 文本标记 | 简单可解析，不依赖 function calling API |
| 共享 MCP 实例 | 是 | 避免多进程资源开销，控制 API 调用频率 |
| Unsplash 封装方式 | Service 而非 Tool | 图片搜索不需要 Agent 智能决策 |
| 地图导出方案 | 导出时隐藏地图 | html2canvas 与 Canvas 地图存在兼容问题 |
| 温度数据格式 | validator 自动清洗 | 兼容高德返回的 "16°C" 格式 |
| 前端状态传递 | Vue Router state | 避免 URL 参数暴露大量数据 |
| API 超时设置 | 120 秒 | 考虑 4 个 Agent 串行 LLM 调用的总耗时 |

---

## 第八部分：附录

### A. 高德地图 API Key 申请

1. 访问 [高德开放平台](https://console.amap.com)
2. 创建应用 → 添加 Key
3. **Web 服务**类型 Key → 配置到后端 `AMAP_API_KEY`
4. **Web 端(JS API)** 类型 Key → 配置到前端 `VITE_AMAP_WEB_KEY`

### B. Unsplash API Key 申请

1. 访问 [Unsplash Developers](https://unsplash.com/developers)
2. 注册应用 → 获取 Access Key
3. 免费额度：50 次/小时

### C. 前端启动说明

高德 JS API 的安全密钥在页面 head 中设置：

```html
<script>
  window._AMapSecurityConfig = {
    securityJsCode: 'your-security-code'
  };
</script>
```

### D. MCP 启动方式说明

| 方式 | 适用场景 | 示例 |
|------|----------|------|
| `npx` | Node.js / npm 包 | `npx -y @sugarforever/amap-mcp-server` |
| `uvx` | Python / PyPI 包 | `uvx some-python-mcp-server` |

本项目使用 `npx` 方式，因为 `amap-mcp-server` 是 Node.js 实现。
