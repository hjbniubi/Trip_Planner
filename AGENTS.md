# 多智能体设计文档 (AGENTS.md)

## 设计理念

本系统采用**多智能体协作**而非单智能体方案，原因如下：

1. **工具调用限制**：单 Agent 需要同时管理景点搜索、天气查询、酒店推荐等多个工具，复杂度高
2. **时间成本**：串行 LLM 调用无法并行，但任务分解后子 Agent 可独立优化
3. **提示词复杂度**：单 Agent 需要超长提示词覆盖所有场景，不稳定
4. **职责分离**：不同专业 Agent 各司其职，便于调试和迭代

## 智能体协作架构

```
用户请求 (TripPlanRequest)
         │
         ▼
┌─ TripPlannerAgent (编排者) ─────────────────────┐
│                                                    │
│  Step 1: AttractionSearchAgent.run()               │
│           └─► 景点列表                              │
│                                                    │
│  Step 2: WeatherQueryAgent.run()                   │
│           └─► 天气预报                              │
│                                                    │
│  Step 3: HotelAgent.run()                          │
│           └─► 酒店推荐                              │
│                                                    │
│  Step 4: _build_planner_query()                    │
│           └─► 整合所有信息为结构化提示词              │
│                                                    │
│  Step 5: PlannerAgent.run()                        │
│           └─► TripPlan JSON                        │
│                                                    │
│  Step 6: _parse_trip_plan()                        │
│           └─► Pydantic TripPlan 对象               │
└────────────────────────────────────────────────────┘
```

### 共享 MCP 实例设计

三个搜索类 Agent 共享同一个 `MCPClient` 实例：

- 只启动一台 MCP 服务器子进程，避免多进程资源开销
- 由 `TripPlannerAgent` 初始化时创建，注入所有子 Agent
- 通过 `MCPClient.call_tool()` 统一管理所有高德 API 调用

## Agent 详细设计

### 1. AttractionSearchAgent（景点搜索专家）

| 属性 | 内容 |
|------|------|
| **角色** | 景点搜索专家 |
| **输入** | `city: str`, `preferences: str` |
| **工具** | `amap_maps_text_search` |
| **输出** | 景点列表（名称、地址、评分、坐标） |
| **提示词要点** | 必须使用工具搜索，禁止编造信息；根据偏好针对性搜索 |

**工具调用格式**：
```
[TOOL_CALL:amap_maps_text_search:keywords=博物馆,city=北京]
```

**偏好-关键词映射**：

| 偏好 | 搜索关键词 |
|------|-----------|
| 历史文化 | 博物馆、古迹、历史 |
| 自然风光 | 公园、山水、自然 |
| 美食购物 | 商圈、美食街、特产 |
| 亲子游玩 | 游乐园、动物园、亲子 |
| 文艺打卡 | 美术馆、创意园、网红 |

### 2. WeatherQueryAgent（天气查询专家）

| 属性 | 内容 |
|------|------|
| **角色** | 天气查询专家 |
| **输入** | `city: str` |
| **工具** | `amap_maps_weather` |
| **输出** | 每日天气（天气状况、温度、风力风向） |

**工具调用格式**：
```
[TOOL_CALL:amap_maps_weather:city=北京]
```

**输出格式要求**：温度必须为纯数字（不含 °C），通过 Pydantic validator 自动解析 `"16°C"` → `16`。

### 3. HotelAgent（酒店推荐专家）

| 属性 | 内容 |
|------|------|
| **角色** | 酒店推荐专家 |
| **输入** | `city: str`, `accommodation: str` |
| **工具** | `amap_maps_text_search` |
| **输出** | 酒店列表（名称、地址、价格、评分、距离） |

**工具调用格式**：
```
[TOOL_CALL:amap_maps_text_search:keywords=经济型酒店,city=上海]
```

**住宿类型-关键词映射**：

| 用户选择 | 搜索关键词 |
|----------|-----------|
| 经济型酒店 | 经济型酒店、快捷酒店 |
| 舒适型酒店 | 三星酒店、舒适型酒店 |
| 豪华型酒店 | 五星级酒店、度假酒店 |
| 民宿 | 民宿、客栈 |

### 4. PlannerAgent（行程规划专家）

| 属性 | 内容 |
|------|------|
| **角色** | 行程规划总策划 |
| **输入** | 用户需求 + 前三个 Agent 的所有输出 |
| **工具** | 无（纯 LLM 信息整合） |
| **输出** | JSON 格式的 `TripPlan` |

**规划约束**（写入提示词）：
1. weather_info 必须包含每天的天气
2. 温度为纯数字
3. 每天安排 2-3 个景点
4. 考虑景点距离和游览时间
5. 包含早中晚三餐
6. 提供实用旅行建议
7. 包含预算信息（门票/酒店/餐饮/交通）

**输出 JSON 模板**：
```json
{
  "city": "城市名称",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "days": [
    {
      "date": "YYYY-MM-DD",
      "day_index": 0,
      "description": "当日行程描述",
      "transportation": "交通方式",
      "accommodation": "住宿安排",
      "hotel": { ... },
      "attractions": [
        {
          "name": "景点名称",
          "address": "地址",
          "location": { "longitude": 116.4, "latitude": 39.9 },
          "visit_duration": 120,
          "description": "简短描述",
          "category": "景点类别",
          "rating": 4.5,
          "ticket_price": 60
        }
      ],
      "meals": [
        {
          "type": "lunch",
          "name": "推荐餐厅名称",
          "address": "地址",
          "estimated_cost": 50
        }
      ]
    }
  ],
  "weather_info": [
    {
      "date": "YYYY-MM-DD",
      "day_weather": "晴",
      "night_weather": "多云",
      "day_temp": 25,
      "night_temp": 15,
      "wind_direction": "南",
      "wind_power": "≤3级"
    }
  ],
  "overall_suggestions": "实用旅行建议...",
  "budget": {
    "total_attractions": 180,
    "total_hotels": 1200,
    "total_meals": 480,
    "total_transportation": 200,
    "total": 2060
  }
}
```

## 自建核心引擎（零框架依赖）

项目从底层自建三个核心模块，不依赖任何第三方 Agent 框架。三个模块之间的关系：

```
AgentRunner ──调用──► LLMClient ──HTTP──► OpenAI/DeepSeek API
     │
     └──调用──► MCPClient ──JSON-RPC──► 高德 MCP Server
                    │                 (子进程 stdin/stdout)
                    └── auto_discover() → 16 个工具
```

### 模块一：MCPClient (`core/mcp_client.py`)

**职责**：通过 JSON-RPC 协议与高德 MCP Server 通信

```
MCPClient 配置:
  server_command: "npx"
  server_args: ["-y", "@sugarforever/amap-mcp-server"]
  env: { AMAP_API_KEY: settings.amap_api_key }
```

**核心方法**：

| 方法 | 功能 |
|------|------|
| `start()` | 启动 MCP Server 子进程 |
| `initialize()` | 发送 `initialize` 请求，建立会话 |
| `list_tools()` | 发送 `tools/list` 请求，获取全部工具列表 |
| `call_tool(name, arguments)` | 发送 `tools/call` 请求，调用指定工具 |
| `close()` | 终止子进程 |

**JSON-RPC 协议要点**（MCP 标准，每行一个 JSON）：

```python
# 请求格式（写入 stdin）
{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}

# 响应格式（从 stdout 读取）
{"jsonrpc":"2.0","id":1,"result":{"tools":[...]}}
```

**工具自动发现**：初始化时调用 `list_tools()`，得到 16 个工具的名称、描述、参数 schema，存入 `self.tools` 字典。

### 模块二：AgentRunner (`core/agent_runner.py`)

**职责**：管理 Agent 的提示词模板、工具注册和 LLM 调用循环

```
AgentRunner 工作流:
  1. 填充提示词模板（注入 city, preferences 等变量）
  2. 调用 LLMClient.chat(messages)
  3. 检查响应中是否包含 [TOOL_CALL:...]
  4. 如有 → 解析工具调用 → 调用 MCPClient.call_tool() → 结果追加到 messages → 回到步骤 2
  5. 如无 → 返回最终文本响应
```

**核心方法**：

| 方法 | 功能 |
|------|------|
| `__init__(name, system_prompt, tools, llm)` | 注册 Agent 名称、提示词、可用工具列表 |
| `run(**kwargs)` | 执行 Agent：填充模板 → LLM 循环 → 返回结果 |
| `_parse_tool_call(text)` | 从 LLM 响应中提取 `[TOOL_CALL:...]` 标记 |
| `_execute_tool(name, args)` | 调用 MCPClient 执行工具并返回结果 |

**工具调用标记格式**（约定优于框架）：
```
[TOOL_CALL:tool_name:param1=value1,param2=value2]
```

示例：
```
[TOOL_CALL:amap_maps_text_search:keywords=博物馆,city=北京]
[TOOL_CALL:amap_maps_weather:city=北京]
```

### 模块三：LLMClient (`core/llm_client.py`)

**职责**：统一的 LLM API 调用封装，支持 OpenAI / DeepSeek 兼容接口

**核心方法**：

| 方法 | 功能 |
|------|------|
| `chat(messages, temperature, max_tokens)` | 发送 chat completion 请求 |
| `chat_with_tools(messages, tool_schemas)` | 发送带工具定义的请求（备用） |

**配置**：
```python
LLMClient(
    api_key=settings.llm_api_key,
    base_url=settings.llm_base_url,   # 兼容 OpenAI / DeepSeek
    model=settings.llm_model,          # gpt-4o / deepseek-chat
    timeout=90                          # 单次 LLM 调用超时
)
```

### 高德 MCP Server 工具列表

| 类别 | 工具名 | 使用者 |
|------|--------|--------|
| 地图 | `maps_staticmap` | 前端备用 |
| 搜索 | `maps_text_search` | AttractionAgent, HotelAgent |
| 天气 | `maps_weather` | WeatherAgent |
| 路线 | 多项路线规划工具 | 前端地图 |
| 地理编码 | `maps_geo`, `maps_regeo` | 坐标转换 |
| IP 定位 | `maps_ip_location` | 定位辅助 |

### 完整调用链路（以景点搜索为例）

```
AttractionAgent.run(city="北京", preferences="历史文化")
    │
    ▼
AgentRunner 填充提示词模板
    │
    ▼
LLMClient.chat([system_prompt, user_message])
    │
    ▼ LLM 返回
    "我需要搜索北京的景点。[TOOL_CALL:amap_maps_text_search:keywords=博物馆,city=北京]"
    │
    ▼ AgentRunner._parse_tool_call()
    │  提取: tool="amap_maps_text_search", args={keywords:"博物馆", city:"北京"}
    │
    ▼ MCPClient.call_tool("amap_maps_text_search", {keywords:"博物馆", city:"北京"})
    │  写入 stdin → {"jsonrpc":"2.0","id":2,"method":"tools/call",...}
    │  读取 stdout → {"jsonrpc":"2.0","id":2,"result":{...}}
    │
    ▼ 结果追加到 messages，再次调用 LLM
    │
    ▼ LLM 返回最终景点列表（无 [TOOL_CALL:...]）
    │
    ▼ AgentRunner 返回文本结果
```

## 外部服务集成

### Unsplash 图片服务

**设计决策**：Unsplash 不封装为 Agent 工具，而是作为 Service 直接调用。原因：图片搜索不需要 Agent 智能决策，属于简单数据增强。

```
API 路由层 (trip.py)
       │
       ├─► TripPlannerAgent.plan_trip()
       │       └─► 生成 TripPlan
       │
       └─► 遍历每个景点
               └─► UnsplashService.search_photos(景点名称)
                       └─► 补充 image_url 字段
```

### LLM 配置

通过环境变量切换不同 LLM 提供商，`LLMClient` 统一封装兼容 OpenAI 接口的 API：

```
LLM_API_KEY=sk-xxx
LLM_MODEL=gpt-4o            # 或 deepseek-chat
LLM_BASE_URL=https://api.openai.com/v1   # 或 https://api.deepseek.com/v1
```

## TripPlannerAgent 初始化代码结构

```python
class TripPlannerAgent:
    def __init__(self):
        # 1. 创建 LLM 客户端
        self.llm = LLMClient(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model
        )
        
        # 2. 启动 MCP Server 并发现工具
        self.mcp = MCPClient(
            command="npx",
            args=["-y", "@sugarforever/amap-mcp-server"],
            env={"AMAP_API_KEY": settings.amap_api_key}
        )
        self.mcp.start()
        self.mcp.initialize()
        tools = self.mcp.list_tools()  # 获取 16 个工具
        
        # 3. 创建子 Agent（共享同一个 mcp 和 llm）
        self.attraction_agent = AgentRunner(
            name="AttractionSearchAgent",
            system_prompt=ATTRACTION_AGENT_PROMPT,
            tools=[tools["amap_maps_text_search"]],
            llm=self.llm,
            mcp=self.mcp
        )
        self.weather_agent = AgentRunner(...)
        self.hotel_agent = AgentRunner(...)
        self.planner_agent = AgentRunner(
            name="PlannerAgent",
            system_prompt=PLANNER_AGENT_PROMPT,
            tools=[],           # 不需要工具
            llm=self.llm,
            mcp=None
        )
    
    def plan_trip(self, request: TripPlanRequest) -> TripPlan:
        attraction_response = self.attraction_agent.run(
            city=request.city, preferences=request.preferences
        )
        weather_response = self.weather_agent.run(city=request.city)
        hotel_response = self.hotel_agent.run(
            city=request.city, accommodation=request.accommodation
        )
        planner_query = self._build_planner_query(
            request, attraction_response, weather_response, hotel_response
        )
        planner_response = self.planner_agent.run(query=planner_query)
        return self._parse_trip_plan(planner_response)
```
