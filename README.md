# 大模型配置中心

LLM Config Center 是一个内部使用的大模型配置中心。后台只需要维护「配置项」：一次填完 `Alias`、`Base URL`、模型名、上游 API Key、默认参数和访问密钥，业务服务用一个 Python 函数拉取配置后初始化 OpenAI-compatible 客户端。

## 功能范围

- 中文 Web 管理后台：登录、配置项新增、配置项编辑、访问密钥复制、用户管理。
- 后端 Runtime API：Access Key 鉴权、App 权限校验、禁用/过期状态校验、真实上游 API Key 解密下发。
- 安全处理：密码哈希、Access Key 哈希、上游 API Key Fernet 加密、审计日志脱敏。
- 配置版本：影响 Runtime 下发结果的 Alias/权限等变更会递增版本。
- 简单接入：业务项目不需要 SDK，复制一个 Python 函数即可读取配置。

## 启动

1. 准备环境变量：

```bash
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

把生成的值写入 `.env` 的 `LLM_CONFIG_MASTER_KEY`。

2. 用 Docker Compose 启动服务：

```bash
docker compose up -d --build
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

数据会持久化到 Docker volume `postgres_data`，正常执行 `docker compose restart`、`docker compose up -d --build`、重启服务器都不会丢数据。

不要执行下面这种带 `-v` 的命令，除非你就是想清空数据库：

```bash
docker compose down -v
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
curl -X GET "http://localhost:8001/api/v1/runtime/configs/seed5?env=prod" \
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

## Python 类接入

业务项目不需要安装 SDK，直接复制 [examples/simple_runtime_config.py](examples/simple_runtime_config.py) 里的 `LLMConfigOpenAI` 类即可。

最小用法：

```python
from simple_runtime_config import LLMConfigOpenAI

llm = LLMConfigOpenAI(
    access_key="<access_key>",
    alias="seed5",
    server_url="http://localhost:8001",
)

client = llm.openai()
print(llm.model)
```

配置项里直接选择「调用类型」。Runtime API 会返回顶层字段 `call_type`：

```json
{
  "call_type": "chat",
  "params": {
    "temperature": 0.7,
    "max_tokens": 4096
  }
}
```

`call_type` 按真实接口分：

| call_type | 调用方式 |
| --- | --- |
| `chat` | `client.chat.completions.create` |
| `responses` | `client.responses.create`，适合火山 seed 多模态 |
| `image` | `client.images.generate`，适合火山 seedream 文生图、图生图、图像编辑 |

云雾、百炼文本、普通 OpenAI-compatible 文本：

```python
response = llm.create_chat_completion(
    [{"role": "user", "content": "你好"}],
    stream=False,
)
print(response.choices[0].message.content)
```

火山 seed 多模态/VLM：

```python
response = llm.create_vision_response(
    prompt="你看见了什么？",
    image_urls="https://ark-project.tos-cn-beijing.volces.com/doc_image/ark_demo_img_1.png",
)
print(response)
```

火山 seedream 文生图：

```python
response = llm.text_to_image(
    "星际穿越，黑洞里冲出一辆快支离破碎的复古列车",
    size="2K",
    response_format="url",
    extra_body={"watermark": True},
)
print(llm.image_urls(response))
```

火山 seedream 图生图/换装/编辑：

```python
response = llm.image_to_image(
    prompt="将图1的服装换为图2的服装",
    images=[
        "https://ark-project.tos-cn-beijing.volces.com/doc_image/seedream4_imagesToimage_1.png",
        "https://ark-project.tos-cn-beijing.volces.com/doc_image/seedream4_imagesToimage_2.png",
    ],
    size="2K",
    response_format="url",
    extra_body={
        "watermark": True,
        "sequential_image_generation": "disabled",
    },
)
print(llm.image_urls(response))
```

百炼 qwen-vl：

```python
response = llm.create_vision_chat_completion(
    prompt="这是什么？",
    image_urls="https://dashscope.oss-cn-beijing.aliyuncs.com/images/dog_and_girl.jpeg",
)
print(response.model_dump_json())
```

百炼 qwen-long 文件理解：

```python
response = llm.create_file_chat_completion(
    file="百炼系列手机产品介绍.docx",
    prompt="这篇文章讲了什么？",
)
print(response.model_dump_json())
```

火山 seedream 配置项默认参数示例：

```json
{
  "size": "2K",
  "watermark": false
}
```

百炼 qwen-plus/qwen-vl/qwen-long 配置项默认参数示例：

```json
{}
```

直接运行测试函数：

```bash
export LLM_CONFIG_SERVER_URL=http://localhost:8001
export LLM_CONFIG_ACCESS_KEY='<access_key>'
export LLM_CONFIG_ALIAS=seed5
python examples/simple_runtime_config.py
```

## 本地测试

后端：

```bash
cd backend
PYTHONPATH=$PWD pytest -q
```

类示例：

```bash
python -m py_compile examples/simple_runtime_config.py
```

前端：

```bash
cd frontend
npm install
npm run build
```
