# 智能数据分析助理 - 后端

基于 FastAPI + LangChain + Qwen3 的自然语言数据分析后端服务。

## 技术栈

- **Web 框架**: FastAPI 0.110
- **LLM**: 阿里云百炼 Qwen3
- **LLM 框架**: LangChain
- **数据库**: SQLite3 (异步)
- **ORM**: SQLAlchemy 2.0

## 项目结构

```
backend/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 配置管理
│   ├── api/                 # API 路由
│   │   ├── chat.py
│   │   ├── session.py
│   │   └── visualization.py
│   ├── services/            # 业务服务
│   ├── chains/              # LangChain 链
│   ├── models/              # Pydantic 模型
│   └── db/                  # 数据库
│       └── database.py
├── data/                    # SQLite 数据库文件
├── requirements.txt
├── .env                     # 环境变量
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填入你的阿里云百炼 API Key：

```bash
cp .env.example .env       # macOS / Linux
# Windows (PowerShell):
Copy-Item .env.example .env
```

然后编辑 `.env`：

```bash
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

> ⚠️ **安全提示**：`backend/.env` 已被 `.gitignore` 排除，**禁止**把真实 key 提交到 git 或写入任何代码/文档/截图。
> 测试脚本（`test_qwen3.py` / `test_nl2sql.py`）会自动从 `.env` 读取，不再硬编码。

### 3. 启动服务

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. 访问 API 文档

打开浏览器：http://localhost:8000/docs

## 健康检查

```bash
curl http://localhost:8000/health
```

返回：

```json
{
  "status": "ok",
  "app": "智能数据分析助理",
  "version": "0.1.0"
}
```
