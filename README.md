# 大模型配置中心

LLM Config Center 是一个内部使用的大模型配置中心。后台只需要维护「配置项」：一次填完 `Alias`、`Base URL`、模型名、上游 API Key、默认参数和访问密钥，业务服务通过 SDK 拉取配置后初始化 OpenAI-compatible 客户端。

## 功能范围

- 中文 Web 管理后台：登录、配置项新增、配置项编辑、访问密钥复制、用户管理。
- 后端 Runtime API：Access Key 鉴权、App 权限校验、禁用/过期状态校验、真实上游 API Key 解密下发。
- 安全处理：密码哈希、Access Key 哈希、上游 API Key Fernet 加密、审计日志脱敏。
- 配置版本：影响 Runtime 下发结果的 Alias/权限等变更会递增版本。
- Python SDK：本地缓存、版本刷新、OpenAI-compatible Client 创建。

## 启动

1. 准备环境变量：

```bash
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

把生成的值写入 `.env` 的 `LLM_CONFIG_MASTER_KEY`。

2. 启动服务：

```bash
docker compose up -d
```

3. 打开后台：

```text
http://localhost:3000
```

默认账号来自 `.env`：

```text
INIT_ADMIN_USERNAME=admin
INIT_ADMIN_PASSWORD=admin123456
```

## 最小演示流程

1. 登录后台。
2. 进入「配置项」页面。
3. 点击「新增配置项」。
4. 一次填完 `Alias`、环境、供应商、`Base URL`、真实模型名、上游 `API Key`、默认参数、客户端名称。
5. 保存后系统会自动创建底层供应商、模型、模型别名、客户端权限和访问密钥。
6. 弹窗和列表里都可以复制客户端要用的 `access_key`。
7. 后续要改模型、Key、参数或 Base URL，直接点配置项右侧「编辑」。

## 用户管理

后台左侧进入「用户管理」：

1. 点击「新增用户」。
2. 填写用户名、显示名称、角色、状态和初始密码。
3. 后续可编辑用户信息、重置密码、启用或禁用用户。

密码只保存 hash，不会在列表和接口响应里展示。

Runtime API 调用：

```bash
curl -X GET "http://localhost:8000/api/v1/runtime/configs/seed5?env=prod" \
  -H "Authorization: Bearer <access_key>"
```

返回示例：

```json
{
  "alias": "seed5",
  "env": "prod",
  "provider": {
    "code": "volcengine",
    "name": "火山引擎",
    "protocol": "openai_compatible"
  },
  "base_url": "https://ark.cn-beijing.volces.com/api/v3",
  "model": "doubao-seed-evolving",
  "api_key": "sk-xxxx",
  "params": {
    "temperature": 0.7,
    "max_tokens": 4096
  },
  "version": 1
}
```

## Python SDK

Python SDK 目录：

```text
sdk/python
```

详细说明见：[sdk/python/README.md](/Users/quxiaopang/Documents/LLMCOMFIG/sdk/python/README.md)

安装：

```bash
pip install -e sdk/python
```

基础用法：

```python
from llm_config_sdk import LLMConfigClient

client = LLMConfigClient(
    server_url="http://localhost:8000",
    access_key="<access_key>",
    env="prod",
)

config = client.get_config("chat-default")
print(config.model, config.base_url)

openai_client, model = client.create_openai_client("chat-default")
```

可运行示例见：[basic_usage.py](/Users/quxiaopang/Documents/LLMCOMFIG/sdk/python/examples/basic_usage.py)

## 本地测试

后端：

```bash
cd backend
PYTHONPATH=$PWD pytest -q
```

SDK：

```bash
cd sdk/python
PYTHONPATH=$PWD pytest -q
```

前端：

```bash
cd frontend
npm install
npm run build
```
