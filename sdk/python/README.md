# 大模型配置中心 Python SDK

这个 SDK 给内部 Python 后端服务使用。业务服务只需要保存配置中心发放的 App Access Key，然后通过 Alias 拉取真实模型配置，不再把 `model`、`base_url`、上游 `api_key` 写死在自己的配置文件里。

## 适用场景

- 服务启动时读取 `chat-default`、`vision-default`、`embedding-default` 等模型配置。
- 配置中心切换上游 API Key、模型名或 `base_url` 后，业务服务无需改代码。
- 本地初始化 OpenAI-compatible Client，业务服务仍然直连真实模型供应商。

## 后台如何创建 SDK 所需配置

推荐走后台的简单入口：

1. 打开「配置项」。
2. 点击「新增配置项」。
3. 一次填完 `Alias`、`Base URL`、真实模型名、上游 `API Key`、默认参数、客户端编码。
4. 保存后弹窗会展示 SDK 需要的 `access_key`、`alias` 和示例代码。

客户端初始化只需要：

```text
server_url：配置中心后端地址
access_key：弹窗里展示的一次性访问密钥
env：环境，默认 prod
alias：配置项里的 Alias
```

## 安装

开发期从仓库本地安装：

```bash
pip install -e sdk/python
```

如果要使用 `create_openai_client()`，还需要安装 OpenAI Python 包：

```bash
pip install "sdk/python[openai]"
```

或者：

```bash
pip install openai
```

## 初始化

```python
from llm_config_sdk import LLMConfigClient

client = LLMConfigClient(
    server_url="http://localhost:8000",
    access_key="lcg_ak_xxxxxxxx.yyyyyyyyyyyyyyyyyyyy",
    env="prod",
    refresh_interval=60,
)
```

参数说明：

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `server_url` | 是 | 配置中心后端地址，例如 `http://localhost:8000` |
| `access_key` | 是 | 后台「访问密钥」页面创建的 App Access Key，不是上游模型 API Key |
| `env` | 否 | 配置环境，默认 `prod` |
| `refresh_interval` | 否 | SDK 检查配置版本的最小间隔，单位秒，默认 `60` |
| `timeout` | 否 | HTTP 请求超时时间，单位秒，默认 `10.0` |

## 获取单个 Alias 配置

```python
config = client.get_config("chat-default")

print(config.alias)
print(config.env)
print(config.provider)
print(config.base_url)
print(config.model)
print(config.api_key)
print(config.params)
print(config.version)
```

`get_config()` 会请求：

```text
GET /api/v1/runtime/configs/{alias}?env=prod
Authorization: Bearer <access_key>
```

返回对象字段：

| 字段 | 说明 |
| --- | --- |
| `alias` | 业务使用的模型别名，例如 `chat-default` |
| `env` | 环境，例如 `prod` |
| `provider` | 供应商信息，包含 `code`、`name`、`protocol` |
| `base_url` | OpenAI-compatible 接口地址 |
| `model` | 真实模型名 |
| `api_key` | 解密后的上游模型 API Key |
| `params` | Alias 默认参数，例如 `temperature`、`max_tokens`、`timeout`、`stream` |
| `version` | Alias 当前版本 |
| `updated_at` | 更新时间，可能为空 |

## 获取当前 App 可用的全部配置

```python
configs = client.get_all_configs()

for item in configs:
    print(item.alias, item.model, item.base_url)
```

只会返回当前 Access Key 所属 App 有权限读取的 Alias。无权限、禁用、过期或上游组件禁用的配置不会返回。

## 获取配置版本

```python
version = client.get_version()
print(version)
```

`get_version()` 会请求：

```text
GET /api/v1/runtime/config-version?env=prod
Authorization: Bearer <access_key>
```

业务服务可以用版本号判断是否需要刷新本地配置。

## 缓存与刷新机制

SDK 内部维护内存缓存：

```text
alias_config_cache
last_version
last_refresh_at
```

行为说明：

1. 第一次 `get_config("chat-default")` 会请求 Runtime API，并缓存结果。
2. `refresh_interval` 时间内再次读取同一个 Alias，会直接走本地内存缓存。
3. 超过 `refresh_interval` 后，SDK 会先请求配置版本。
4. 如果版本没有变化，继续使用缓存。
5. 如果版本变化，SDK 会清空缓存并重新请求 Alias 配置。
6. 可以调用 `force_refresh()` 主动清空缓存并同步最新版本。

示例：

```python
client.refresh_if_needed()
client.force_refresh()
```

## 创建 OpenAI-compatible Client

```python
openai_client, model = client.create_openai_client("chat-default")

response = openai_client.chat.completions.create(
    model=model,
    messages=[
        {"role": "user", "content": "你好"}
    ],
)

print(response.choices[0].message.content)
```

这个方法内部会：

1. 调用 `get_config(alias)`。
2. 用返回的 `base_url` 和 `api_key` 初始化 `openai.OpenAI`。
3. 返回 `(openai_client, model)`。

注意：配置中心只负责配置下发，不代理模型请求。真正的模型调用仍由业务服务直连上游供应商。

## 异常处理

SDK 使用 `httpx` 请求 Runtime API。接口错误会抛出 `httpx.HTTPStatusError`：

```python
import httpx

try:
    config = client.get_config("chat-default")
except httpx.HTTPStatusError as exc:
    if exc.response.status_code == 401:
        print("Access Key 无效或已禁用")
    elif exc.response.status_code == 403:
        print("当前 App 没有读取该 Alias 的权限")
    elif exc.response.status_code == 404:
        print("Alias 不存在")
    elif exc.response.status_code == 409:
        print("Alias、Provider、Model、API Key 或 Access Key 状态不可用")
    else:
        raise
```

常见状态码：

| 状态码 | 含义 |
| --- | --- |
| `401` | Access Key 缺失、格式错误、密钥错误、已禁用或所属 App 禁用 |
| `403` | App 没有读取目标 Alias 的权限 |
| `404` | Alias 不存在 |
| `409` | Alias / Provider / Model / API Key 禁用，或 Key 已过期 |

## 完整示例

```python
from llm_config_sdk import LLMConfigClient


def main():
    client = LLMConfigClient(
        server_url="http://localhost:8000",
        access_key="请替换为后台创建的完整 access_key",
        env="prod",
        refresh_interval=60,
    )

    config = client.get_config("chat-default")
    print("Alias:", config.alias)
    print("模型:", config.model)
    print("Base URL:", config.base_url)
    print("默认参数:", config.params)

    openai_client, model = client.create_openai_client("chat-default")
    response = openai_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "用一句话介绍你自己"}],
        **config.params,
    )
    print(response.choices[0].message.content)


if __name__ == "__main__":
    main()
```

## 本地测试

```bash
cd sdk/python
PYTHONPATH=$PWD pytest -q
```
