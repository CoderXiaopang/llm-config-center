from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def get_llm_config(
    alias: str,
    access_key: str,
    server_url: str = "http://localhost:8001",
    env: str = "prod",
    timeout: float = 10.0,
) -> dict[str, Any]:
    query = urllib.parse.urlencode({"env": env})
    url = f"{server_url.rstrip('/')}/api/v1/runtime/configs/{urllib.parse.quote(alias)}?{query}"
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_key}"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"读取配置失败：HTTP {exc.code}，响应：{body}") from exc


class LLMConfigOpenAI:
    def __init__(
        self,
        access_key: str,
        alias: str,
        server_url: str = "http://localhost:8001",
        env: str = "prod",
        timeout: float = 10.0,
    ) -> None:
        self.access_key = access_key
        self.alias = alias
        self.server_url = server_url
        self.env = env
        self.config = get_llm_config(
            alias=alias,
            access_key=access_key,
            server_url=server_url,
            env=env,
            timeout=timeout,
        )
        self.model = self.config["model"]
        self.default_params = self.config.get("params", {})
        self.client = self._create_openai_client()

    def _create_openai_client(self):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("请先安装 openai：pip install openai") from exc
        return OpenAI(base_url=self.config["base_url"], api_key=self.config["api_key"])

    def openai(self):
        return self.client

    def __call__(self):
        return self.client

    def chat(self, messages: list[dict[str, Any]], **kwargs: Any):
        request_params = {**self.default_params, **kwargs}
        return self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            **request_params,
        )


def main() -> None:
    access_key = os.environ["LLM_CONFIG_ACCESS_KEY"]
    alias = os.getenv("LLM_CONFIG_ALIAS", "seed5")
    env = os.getenv("LLM_CONFIG_ENV", "prod")
    server_url = os.getenv("LLM_CONFIG_SERVER_URL", "http://localhost:8001")

    llm = LLMConfigOpenAI(access_key=access_key, alias=alias, server_url=server_url, env=env)
    client = llm.openai()
    print("client:", client.__class__.__name__)
    print("model:", llm.model)
    print("params:", json.dumps(llm.default_params, ensure_ascii=False))


if __name__ == "__main__":
    main()
