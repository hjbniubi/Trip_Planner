# 智能旅行助手 (AI Travel Planner)

基于多智能体协作的全栈 AI Agent 应用。用户输入目的地、日期、偏好和预算，系统自动生成包含景点、餐饮、酒店、地图路线和预算明细的完整旅行计划。

## 核心功能

| 功能 | 说明 |
|------|------|
| **智能行程规划** | 输入目的地、日期、偏好，自动生成完整行程 |
| **地图可视化** | 在地图上标注景点位置、展示游览路线 |
| **预算计算** | 自动计算门票、酒店、餐饮、交通费用明细 |
| **行程编辑** | 支持添加、删除、调整景点，实时更新地图 |
| **导出功能** | 支持导出为 PDF 或图片 |

## 技术架构

```
┌──────────────────────────────────────────┐
│  前端层  Vue3 + TypeScript + Ant Design  │
│         高德地图 JS API                   │
├──────────────────────────────────────────┤
│  后端层  FastAPI + Pydantic              │
│         API 路由 / 数据验证 / 业务编排     │
├──────────────────────────────────────────┤
│ 智能体层 自建 Agent 引擎（零框架依赖）      │
│         MCP Client / Agent Runner / LLM   │
├──────────────────────────────────────────┤
│ 外部服务 高德地图 MCP / Unsplash / LLM    │
└──────────────────────────────────────────┘
```

### 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.10+, FastAPI, Pydantic |
| 前端 | Vue 3, TypeScript, Vite, Ant Design Vue, Axios |
| AI Engine | 自建 Agent 引擎 + MCP 客户端 + LLM 封装（零框架依赖） |
| LLM | OpenAI / DeepSeek 兼容 API |
| 外部 API | 高德地图 Web 服务, Unsplash 图片 API |
| 协议 | MCP (Model Context Protocol) — 自建 JSON-RPC 实现 |

## 快速开始

### 前置条件

- Python 3.10+
- Node.js 18+
- 高德地图 API Key（Web服务 + JS API）
- LLM API Key（OpenAI / DeepSeek）
- Unsplash Access Key

### 后端启动

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # 编辑填入 API 密钥
uvicorn app.api.main:app --reload
```

访问 `http://localhost:8000/docs` 查看 Swagger API 文档。

### 前端启动

```bash
cd frontend
npm install
npm run dev
```

访问 `http://localhost:5173` 使用应用。

## 自建引擎（零框架依赖）

项目不依赖任何第三方 Agent 框架，从底层自建三个核心模块：

| 模块 | 文件 | 职责 | 代码量 |
|------|------|------|--------|
| **MCP Client** | `core/mcp_client.py` | JSON-RPC 通信、子进程管理、工具注册 | ~200 行 |
| **Agent Runner** | `core/agent_runner.py` | 提示词管理、工具调用循环、响应解析 | ~150 行 |
| **LLM Client** | `core/llm_client.py` | OpenAI 兼容 API 调用、重试、流式支持 | ~60 行 |

## 四个智能体

| Agent | 职责 | 工具 |
|-------|------|------|
| AttractionSearchAgent | 根据偏好搜索景点 | 高德 POI 文本搜索 |
| WeatherQueryAgent | 查询目的地天气 | 高德天气查询 |
| HotelAgent | 推荐酒店 | 高德 POI 搜索 |
| PlannerAgent | 整合信息生成行程 | LLM 信息整合 |

## 项目结构

```
ai-travel-planner/
├── backend/
│   ├── app/
│   │   ├── agents/          # Agent 提示词与编排
│   │   ├── core/            # 自建引擎（零框架依赖）
│   │   │   ├── mcp_client.py   # MCP JSON-RPC 客户端
│   │   │   ├── agent_runner.py # Agent 运行循环
│   │   │   └── llm_client.py   # LLM API 封装
│   │   ├── api/routes/      # API 路由
│   │   ├── models/          # Pydantic 数据模型
│   │   ├── services/        # 外部服务封装
│   │   └── config.py        # 配置管理
│   ├── requirements.txt
│   └── run.py
├── frontend/
│   ├── src/
│   │   ├── views/           # 页面组件
│   │   ├── services/        # API 封装
│   │   ├── types/           # TS 类型定义
│   │   └── router/          # 路由配置
│   ├── package.json
│   └── vite.config.ts
├── README.md
├── AGENTS.md
├── PRD.md
└── SPEC.md
```
