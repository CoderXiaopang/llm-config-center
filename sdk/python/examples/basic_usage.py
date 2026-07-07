import os

from llm_config_sdk import LLMConfigClient


def main() -> None:
    client = LLMConfigClient(
        server_url=os.getenv("LLM_CONFIG_SERVER_URL", "http://localhost:8000"),
        access_key=os.environ["LLM_CONFIG_ACCESS_KEY"],
        env=os.getenv("LLM_CONFIG_ENV", "prod"),
        refresh_interval=60,
    )

    config = client.get_config(os.getenv("LLM_CONFIG_ALIAS", "seed5"))
    print("Alias:", config.alias)
    print("环境:", config.env)
    print("供应商:", config.provider)
    print("真实模型:", config.model)
    print("Base URL:", config.base_url)
    print("默认参数:", config.params)
    print("版本:", config.version)

    # 如果已安装 openai，可以直接创建 OpenAI-compatible Client。
    # openai_client, model = client.create_openai_client("chat-default")
    # response = openai_client.chat.completions.create(
    #     model=model,
    #     messages=[{"role": "user", "content": "你好"}],
    #     **config.params,
    # )
    # print(response.choices[0].message.content)


if __name__ == "__main__":
    main()
