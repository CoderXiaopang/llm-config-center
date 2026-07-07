# 后端说明

这是大模型配置中心的 FastAPI 后端，提供后台管理 API 和 Runtime 配置下发 API。

## 本地启动

```bash
cd backend
export PYTHONPATH=$PWD
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

默认管理员由环境变量控制：

```bash
INIT_ADMIN_USERNAME=admin
INIT_ADMIN_PASSWORD=admin123456
```

## 运行测试

```bash
cd backend
PYTHONPATH=$PWD pytest -q
```
