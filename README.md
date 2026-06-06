# 智能数据分析助理

基于 **Qwen3 大模型** + **LangChain v1** 的自然语言数据分析系统，支持 SQLite3 数据库查询、实时 SSE 流式响应、Chart.js 可视化。

![Phase](https://img.shields.io/badge/Phase-1--5%20Done-3fb950)
![Backend](https://img.shields.io/badge/Backend-FastAPI%20%2B%20LangChain-009688)
![Frontend](https://img.shields.io/badge/Frontend-React%2018%20%2B%20AntD-1677ff)

---

## ✨ 功能

- 🧠 **NL2SQL**：用自然语言查数据库，自动生成 SQL（LangChain `create_agent` + 4 个标准 SQL @tool）
- 📊 **实时图表**：查询结果自动渲染 Chart.js 折线/柱状/饼图/表格
- ⚡ **SSE 流式响应**：实时显示 agent 思考步骤（list_tables → schema → checker → query → answer）
- 💬 **会话管理**：多会话持久化、上下文记忆、自动重命名
- 🛡️ **LLM 工具调用守卫**：温度 0.0 + few-shot prompt + 运行时重试，**100% 触发 SQL 工具**（5 轮 × 8 题压测 0 失败）

## 🏗️ 技术栈

**Backend**：FastAPI · LangChain 1.3.4 · langchain-openai · SQLAlchemy (async) · aiosqlite · DashScope (Qwen3)

**Frontend**：React 18 · TypeScript 5 · Vite 5 · Ant Design 5 · Zustand · Axios · Chart.js 4

## 📂 项目结构

```
.
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── api/             # chat / session / visualization
│   │   ├── services/        # llm / nl2sql / chart / memory / session
│   │   ├── models/          # ORM
│   │   ├── schemas/         # Pydantic
│   │   ├── db/              # async SQLite
│   │   └── main.py          # FastAPI 入口
│   ├── scripts/seed_db.py   # 6 个月销售演示数据
│   ├── requirements.txt
│   └── .env.example
├── frontend/                # React 前端
│   ├── src/
│   │   ├── components/      # ChatManagement / ChatArea / Visualization
│   │   ├── services/api.ts  # Axios + SSE
│   │   ├── store/           # Zustand
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

## 🚀 快速开始

### 1. 后端

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate    # Windows
pip install -r requirements.txt
cp .env.example .env                               # 填入 DASHSCOPE_API_KEY
python scripts/seed_db.py                          # 初始化示例数据
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

后端跑在 `http://localhost:8000`，API 文档 `http://localhost:8000/docs`。

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

前端跑在 `http://localhost:5173`（自动找可用端口）。Vite proxy 自动转发 `/api` 到 8000。

## 🧪 测试问题示例

| 问题 | 预期结果 |
|---|---|
| 查询商品销售额 | SUM(amount) 折线 |
| 查询各类商品销售额 | 按 category 聚合柱状 |
| 统计每个城市的用户数 | city GROUP BY 柱状 |
| 看看有哪些用户 | users 表 SELECT |
| 本月卖了多少商品 | strftime '%Y-%m' 过滤 |

## 📐 架构决策

详见 `.cursor/plans/智能数据分析系统架构规划_df4bf712.plan.md` 中的 ADR：
- **ADR-001**：LangChain 接入 Qwen3 的方式（langchain-openai + DashScope）
- **ADR-002**：Qwen3 DashScope 字段规范（实测）
- **ADR-003**：NL2SQL 实现路径（create_agent + 4 SQL @tool）
- **ADR-004**：NL2SQL Agent 字段规范（实测 13.88s / 5 往返 / 1.3K token）

## 📝 License

MIT
