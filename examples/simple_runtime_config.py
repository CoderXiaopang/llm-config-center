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


def main() -> None:
    access_key = os.environ["LLM_CONFIG_ACCESS_KEY"]
    alias = os.getenv("LLM_CONFIG_ALIAS", "seed5")
    env = os.getenv("LLM_CONFIG_ENV", "prod")
    server_url = os.getenv("LLM_CONFIG_SERVER_URL", "http://localhost:8001")

    config = get_llm_config(alias=alias, access_key=access_key, server_url=server_url, env=env)
    print("base_url:", config["base_url"])
    print("model:", config["model"])
    print("params:", json.dumps(config.get("params", {}), ensure_ascii=False))

    # 如果项目里安装了 openai，可以这样初始化：
    # from openai import OpenAI
    # client = OpenAI(base_url=config["base_url"], api_key=config["api_key"])
    # model = config["model"]


if __name__ == "__main__":
    main()
