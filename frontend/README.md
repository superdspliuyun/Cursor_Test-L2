# 智能数据分析助理 - 前端

基于 React + Vite + Ant Design 的智能数据分析前端。

## 技术栈

- **框架**: React 18
- **构建工具**: Vite 5
- **类型系统**: TypeScript 5
- **UI 组件**: Ant Design 5
- **状态管理**: Zustand
- **HTTP 客户端**: Axios
- **图表**: Chart.js (待集成)

## 项目结构

```
frontend/
├── src/
│   ├── App.tsx              # 主应用（三栏布局）
│   ├── main.tsx             # 入口
│   ├── index.css            # 全局样式
│   ├── components/
│   │   ├── ChatManagement/  # 左侧 - 聊天管理
│   │   ├── ChatArea/        # 中间 - 问答区域
│   │   └── Visualization/   # 右侧 - 可视化
│   ├── services/
│   │   └── api.ts           # axios API 封装
│   ├── store/               # 状态管理
│   └── types/               # TypeScript 类型
├── public/
├── package.json
├── tsconfig.json
├── vite.config.ts
└── index.html
```

## 快速开始

### 1. 安装依赖

```bash
cd frontend
npm install
```

### 2. 启动开发服务器

```bash
npm run dev
```

打开浏览器：http://localhost:5173

### 3. 构建生产版本

```bash
npm run build
```

## API 代理

开发环境下，Vite 会将 `/api` 请求代理到后端 `http://localhost:8000`。

确保后端服务先启动，否则前端请求会失败。
