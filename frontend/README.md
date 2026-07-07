# 前端说明

管理台使用 React + Vite + Ant Design，界面文案为中文。

## 本地启动

默认会把 `/api` 代理到 `http://localhost:8001`，对应非 Docker 方式启动的后端。

```bash
cd frontend
npm install
npm run dev
```

如果后端不是 `8001` 端口，可以这样指定：

```bash
VITE_API_PROXY_TARGET=http://localhost:8000 npm run dev
```

访问：

```text
http://localhost:3000
```
