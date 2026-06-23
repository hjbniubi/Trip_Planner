# 智能旅行助手 (AI Travel Planner)

基于多智能体协作的全栈 AI Agent 应用。用户输入目的地、日期、偏好、预算、交通方式和住宿类型后，后端会通过自建 Agent 引擎整合 LLM、高德 MCP 工具和图片服务，生成包含景点、天气、餐饮、酒店、地图位置和预算明细的旅行计划。

## 当前功能

| 功能 | 状态 | 说明 |
|------|------|------|
| 智能行程生成 | 已实现 | 调用 `/api/trip/plan`，返回结构化 `TripPlan` JSON |
| 多智能体编排 | 已实现 | 景点、天气、酒店、总规划四类 Agent 分工协作 |
| 高德 MCP 工具调用 | 已实现 | 自建 JSON-RPC MCP Client，延迟初始化外部 MCP 服务 |
| LLM 兼容封装 | 已实现 | 默认优先使用 DeepSeek，兼容 OpenAI Chat Completions 接口 |
| Unsplash 图片增强 | 已实现 | 为缺少图片的景点补充图片 URL，未配置 Key 时自动跳过 |
| 前端表单 | 已实现 | Vue 3 + Ant Design Vue，含日期校验、进度提示、错误提示 |
| 结果页展示 | 已实现 | 展示每日行程、天气、预算、景点坐标和地图容器 |
| 行程编辑 / 导出 | 规划中 | 代码中尚未实现，不作为当前版本能力 |

## 技术架构

```text
┌──────────────────────────────────────────┐
│  前端层  Vue 3 + TypeScript + Ant Design │
│         Axios / Vue Router / 高德 JS API │
├──────────────────────────────────────────┤
│  后端层  FastAPI + Pydantic              │
│         API 路由 / 数据验证 / 业务编排     │
├──────────────────────────────────────────┤
│ 智能体层 自建 Agent 引擎（零框架依赖）      │
│         MCP Client / Agent Runner / LLM  │
├──────────────────────────────────────────┤
│ 外部服务 高德地图 MCP / Unsplash / LLM   │
└──────────────────────────────────────────┘
```

## 前置条件

- Python 3.10+
- Node.js 18+，并确保 `npx` 可用
- 高德地图 Web 服务 API Key：用于 MCP Server 查询景点、天气、酒店
- 高德地图 JS API Key：用于前端地图展示，可选
- LLM API Key：默认使用 DeepSeek，也可切换到其它 OpenAI 兼容接口
- Unsplash Access Key：用于景点图片增强，可选

## 环境变量

后端配置文件：`backend/.env`

```bash
cd backend
copy .env.example .env
```

主要变量：

| 变量 | 必填 | 说明 |
|------|------|------|
| `LLM_API_KEY` | 是 | DeepSeek 或其它 OpenAI 兼容接口密钥 |
| `LLM_MODEL` | 是 | 默认 `deepseek-chat` |
| `LLM_BASE_URL` | 是 | 默认 `https://api.deepseek.com/v1` |
| `LLM_TIMEOUT` | 否 | 单次 LLM 请求超时时间，默认 90 秒 |
| `AMAP_API_KEY` | 是 | 高德 Web 服务 Key，传给 MCP Server |
| `UNSPLASH_ACCESS_KEY` | 否 | 未配置时图片增强会自动跳过 |
| `CORS_ORIGINS` | 否 | 默认允许 `localhost:5173` 和 `127.0.0.1:5173` |

前端配置文件：`frontend/.env`

```bash
cd frontend
copy .env.example .env
```

主要变量：

| 变量 | 必填 | 说明 |
|------|------|------|
| `VITE_API_BASE_URL` | 是 | 默认 `http://localhost:8000/api` |
| `VITE_AMAP_WEB_KEY` | 否 | 高德 JS API Key；未配置时结果页显示坐标兜底 |

## 本地启动

后端：

```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --reload
```

访问：

- Swagger 文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/api/health

前端：

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

访问：http://127.0.0.1:5173/

## API

### `GET /api/health`

返回：

```json
{ "status": "ok" }
```

### `POST /api/trip/plan`

请求示例：

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

说明：

- `days` 必须等于 `end_date - start_date + 1`，否则返回 `422`。
- 未配置外部 Key、LLM 超时或 MCP 启动失败时，会返回明确的错误 `detail`，前端会展示该文案。
- 规划器采用延迟初始化，无效请求不会提前启动 MCP/LLM 外部依赖。

## 测试与验证

后端测试：

```bash
python -m pytest backend/tests -v
python -m compileall backend/app backend/tests
```

前端验证：

```bash
cd frontend
npm run typecheck
npm run build
```

当前已覆盖：

- Pydantic schema 校验
- LLMClient 请求、重试、超时和工具调用封装
- MCPClient JSON-RPC 初始化、工具列表、工具调用、错误处理
- AgentRunner 工具调用循环
- TripPlannerAgent 编排与 JSON 解析
- Trip API 路由、错误映射、Unsplash 图片增强
- 前端表单工具、结果页解析工具、API 错误文案解析

## 自建引擎（零框架依赖）

项目不依赖第三方 Agent 框架，核心模块如下：

| 模块 | 文件 | 职责 |
|------|------|------|
| MCP Client | `backend/app/core/mcp_client.py` | JSON-RPC 通信、子进程管理、工具发现和调用 |
| Agent Runner | `backend/app/core/agent_runner.py` | 提示词管理、工具调用循环、响应解析 |
| LLM Client | `backend/app/core/llm_client.py` | OpenAI 兼容 API 调用、重试、超时处理 |
| Trip Planner | `backend/app/agents/planner.py` | 创建四类 Agent 并编排完整规划流程 |

## 智能体职责

| Agent | 职责 | 工具 |
|-------|------|------|
| AttractionSearchAgent | 根据城市和偏好搜索景点 | 高德文本搜索 |
| WeatherQueryAgent | 查询目的地天气 | 高德天气查询 |
| HotelAgent | 根据住宿类型推荐酒店 | 高德文本搜索 |
| PlannerAgent | 整合用户需求和前三类 Agent 输出，生成最终行程 JSON | 无工具，纯 LLM 整合 |

## 项目结构

```text
Trip_Planner/
├── backend/
│   ├── app/
│   │   ├── agents/          # Agent 提示词与编排
│   │   ├── api/routes/      # FastAPI 路由
│   │   ├── core/            # MCP / AgentRunner / LLM 核心模块
│   │   ├── models/          # Pydantic 数据模型
│   │   ├── services/        # Unsplash 等外部服务封装
│   │   └── config.py        # 环境变量配置
│   ├── tests/               # 后端测试
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── router/          # Vue Router
│   │   ├── services/        # Axios API 封装
│   │   ├── types/           # TypeScript 类型
│   │   ├── utils/           # 表单、结果页工具函数
│   │   └── views/           # Home / Result 页面
│   ├── .env.example
│   └── package.json
├── AGENTS.md                # 多智能体设计说明
├── PRD.md                   # 产品需求
├── SPEC.md                  # 技术规格
└── README.md
```

## 常见问题

### 无效请求为什么返回 422？

`TripPlanRequest` 会校验日期和天数一致性。例如 `2026-07-01` 到 `2026-07-03` 必须传 `days: 3`。

### 没有配置 Key 时能运行吗？

前端页面和后端健康检查可以运行。真实生成行程需要 `LLM_API_KEY` 和 `AMAP_API_KEY`。`UNSPLASH_ACCESS_KEY` 和 `VITE_AMAP_WEB_KEY` 是可选增强。

### Windows 下 `npm` 被执行策略拦截怎么办？

使用 `npm.cmd`：

```bash
npm.cmd run dev -- --host 127.0.0.1
npm.cmd run build
```

### 为什么 build 有 chunk size 警告？

Ant Design Vue 和高德地图相关依赖会让首包偏大。当前是 Vite 的性能提示，不影响构建产物生成；后续可以通过路由级懒加载和手动 chunk 拆分优化。
