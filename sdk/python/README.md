# 大模型配置中心 Python SDK

## 安装

```bash
pip install -e sdk/python
```

## 使用

```python
from llm_config_sdk import LLMConfigClient

client = LLMConfigClient(
    server_url="http://localhost:8000",
    access_key="<access_key>",
    env="prod",
)

config = client.get_config("chat-default")
print(config.model, config.base_url)
```

## 创建 OpenAI-compatible Client

```python
openai_client, model = client.create_openai_client("chat-default")
```

