# 大模型配置中心

LLM Config Center 是一个内部使用的大模型配置中心，用于统一管理供应商、模型、上游 API Key、模型别名、应用访问密钥和 Alias 读取权限。业务服务通过 Runtime API 拉取有权限的配置，再在本地初始化 OpenAI-compatible 客户端。

## 功能范围

- 中文 Web 管理后台：登录、供应商、上游 API Key、模型、Alias、应用、访问密钥、权限、审计日志。
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
2. 在「供应商管理」创建 Provider，例如 `volcengine`。
3. 在「上游 API Key」创建真实模型服务 API Key，列表只显示脱敏值。
4. 在「模型管理」创建模型，例如 `doubao-seed-1.6`。
5. 在「模型别名」创建 `prod / chat-default`，绑定模型和上游 API Key。
6. 在「应用管理」创建业务应用，例如 `requirement-api`。
7. 在「访问密钥」输入应用 ID，创建 App Access Key，并立即保存弹窗里的完整密钥。
8. 在「权限管理」给应用授权 `prod / chat-default`。

Runtime API 调用：

```bash
curl -X GET "http://localhost:8000/api/v1/runtime/configs/chat-default?env=prod" \
  -H "Authorization: Bearer <access_key>"
```

返回示例：

```json
{
  "alias": "chat-default",
  "env": "prod",
  "provider": {
    "code": "volcengine",
    "name": "火山引擎",
    "protocol": "openai_compatible"
  },
  "base_url": "https://ark.cn-beijing.volces.com/api/v3",
  "model": "doubao-seed-1.6",
  "api_key": "sk-xxxx",
  "params": {
    "temperature": 0.7,
    "max_tokens": 4096
  },
  "version": 1
}
```

## Python SDK

```bash
pip install -e sdk/python
```

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

