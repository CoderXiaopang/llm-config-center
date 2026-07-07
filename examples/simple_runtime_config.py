from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Literal


TaskType = Literal["chat", "responses", "text_to_image", "image_to_image", "image_edit", "raw"]
INTERNAL_PARAM_KEYS = {"provider", "task_type"}
SUPPORTED_PROVIDERS = {"yunwu", "volcengine", "bailian", "openai_compatible"}
IMAGE_EXTRA_BODY_KEYS = {"image", "watermark", "sequential_image_generation"}


def normalize_server_url(server_url: str) -> str:
    cleaned = server_url.strip()
    if cleaned.startswith("http://http://"):
        cleaned = cleaned.removeprefix("http://")
    if cleaned.startswith("https://https://"):
        cleaned = cleaned.removeprefix("https://")
    if not cleaned.startswith(("http://", "https://")):
        raise ValueError("server_url 必须以 http:// 或 https:// 开头")
    return cleaned.rstrip("/")


def get_llm_config(
    alias: str,
    access_key: str,
    server_url: str = "http://localhost:8001",
    env: str = "prod",
    timeout: float = 10.0,
) -> dict[str, Any]:
    query = urllib.parse.urlencode({"env": env})
    url = f"{normalize_server_url(server_url)}/api/v1/runtime/configs/{urllib.parse.quote(alias)}?{query}"
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_key}"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"读取配置失败：HTTP {exc.code}，响应：{body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"读取配置失败：无法连接 {url}，原因：{exc.reason}") from exc


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
        self.provider = self._detect_provider()
        self.task_type = self._detect_task_type()

    def _create_openai_client(self):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("请先安装 openai：pip install openai") from exc
        return OpenAI(base_url=self.config["base_url"], api_key=self.config["api_key"])

    def _detect_provider(self) -> str:
        configured = str(self.default_params.get("provider") or "").lower()
        if configured in SUPPORTED_PROVIDERS:
            return configured

        provider = self.config.get("provider") or {}
        raw = " ".join(
            [
                str(provider.get("code") or ""),
                str(provider.get("name") or ""),
                str(self.config.get("base_url") or ""),
            ]
        ).lower()
        if "yunwu" in raw or "yunwu" in raw or "云雾" in raw:
            return "yunwu"
        if "volc" in raw or "ark" in raw or "volces" in raw or "火山" in raw:
            return "volcengine"
        if "bailian" in raw or "dashscope" in raw or "aliyun" in raw or "百炼" in raw:
            return "bailian"
        return "openai_compatible"

    def _detect_task_type(self) -> TaskType:
        configured = self.default_params.get("task_type")
        if configured in {"chat", "responses", "text_to_image", "image_to_image", "image_edit", "raw"}:
            return configured
        model_name = self.model.lower()
        if "seed-" in model_name or "seed_" in model_name or "vl" in model_name:
            return "responses" if self.provider == "volcengine" else "chat"
        if "seededit" in model_name:
            return "image_edit"
        if "seedream" in model_name or "qwen-image" in model_name or "wanx" in model_name:
            return "text_to_image"
        return "chat"

    def _request_params(self, overrides: dict[str, Any]) -> dict[str, Any]:
        params = {key: value for key, value in self.default_params.items() if key not in INTERNAL_PARAM_KEYS}
        params.update(overrides)
        return params

    def _image_params(self, images: str | list[str] | None, overrides: dict[str, Any]) -> dict[str, Any]:
        params = self._request_params(overrides)
        extra_body = dict(params.pop("extra_body", {}) or {})
        for key in list(params.keys()):
            if key in IMAGE_EXTRA_BODY_KEYS:
                extra_body[key] = params.pop(key)
        if images:
            extra_body["image"] = [images] if isinstance(images, str) else images
        if extra_body:
            params["extra_body"] = extra_body
        return params

    def openai(self):
        return self.client

    def __call__(self):
        return self.client

    def create_chat_completion(self, messages: list[dict[str, Any]], **kwargs: Any):
        request_params = self._request_params(kwargs)
        return self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            **request_params,
        )

    def create_response(self, input: str | list[dict[str, Any]], **kwargs: Any):
        request_params = self._request_params(kwargs)
        return self.client.responses.create(
            model=self.model,
            input=input,
            **request_params,
        )

    def create_vision_response(self, prompt: str, image_urls: str | list[str], **kwargs: Any):
        urls = [image_urls] if isinstance(image_urls, str) else image_urls
        content = [{"type": "input_image", "image_url": url} for url in urls]
        content.append({"type": "input_text", "text": prompt})
        return self.create_response([{"role": "user", "content": content}], **kwargs)

    def create_vision_chat_completion(self, prompt: str, image_urls: str | list[str], **kwargs: Any):
        urls = [image_urls] if isinstance(image_urls, str) else image_urls
        content = [{"type": "image_url", "image_url": {"url": url}} for url in urls]
        content.append({"type": "text", "text": prompt})
        return self.create_chat_completion([{"role": "user", "content": content}], **kwargs)

    def create_image(self, prompt: str, images: str | list[str] | None = None, **kwargs: Any):
        request_params = self._image_params(images, kwargs)
        return self.client.images.generate(
            model=self.model,
            prompt=prompt,
            **request_params,
        )

    def text_to_image(self, prompt: str, **kwargs: Any):
        return self.create_image(prompt=prompt, **kwargs)

    def image_to_image(self, prompt: str, images: str | list[str], **kwargs: Any):
        return self.create_image(prompt=prompt, images=images, **kwargs)

    def edit_image(self, prompt: str, images: str | list[str], **kwargs: Any):
        return self.create_image(prompt=prompt, images=images, **kwargs)

    def upload_file(self, file: str | Path, purpose: str = "file-extract"):
        return self.client.files.create(file=Path(file), purpose=purpose)

    def create_file_chat_completion(self, file: str | Path, prompt: str, **kwargs: Any):
        file_object = self.upload_file(file)
        return self.create_chat_completion(
            [
                {"role": "system", "content": f"fileid://{file_object.id}"},
                {"role": "user", "content": prompt},
            ],
            **kwargs,
        )

    def run(self, prompt: str | None = None, messages: list[dict[str, Any]] | None = None, images: str | list[str] | None = None, **kwargs: Any):
        if self.task_type == "chat":
            chat_messages = messages or [{"role": "user", "content": prompt or ""}]
            return self.create_chat_completion(chat_messages, **kwargs)
        if self.task_type == "responses":
            return self.create_vision_response(prompt or "", images, **kwargs) if images else self.create_response(prompt or "", **kwargs)
        if self.task_type in {"text_to_image", "image_to_image", "image_edit"}:
            if not prompt:
                raise ValueError("图片任务必须传 prompt")
            return self.create_image(prompt=prompt, images=images, **kwargs)
        raise ValueError("task_type=raw 时请使用 openai() 原生客户端自行调用")

    @staticmethod
    def image_urls(response: Any) -> list[str]:
        if hasattr(response, "model_dump"):
            response = response.model_dump()
        urls: list[str] = []

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in {"url", "image", "image_url"} and isinstance(item, str) and item.startswith(("http://", "https://", "data:")):
                        urls.append(item)
                    else:
                        walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(response)
        return urls


def main() -> None:
    access_key = os.environ["LLM_CONFIG_ACCESS_KEY"]
    alias = os.getenv("LLM_CONFIG_ALIAS", "seed5")
    env = os.getenv("LLM_CONFIG_ENV", "prod")
    server_url = os.getenv("LLM_CONFIG_SERVER_URL", "http://localhost:8001")

    llm = LLMConfigOpenAI(access_key=access_key, alias=alias, server_url=server_url, env=env)
    client = llm.openai()
    print("client:", client.__class__.__name__)
    print("model:", llm.model)
    print("provider:", llm.provider)
    print("task_type:", llm.task_type)
    print("params:", json.dumps(llm.default_params, ensure_ascii=False))

    if llm.task_type == "chat":
        response = llm.run(prompt="你好", stream=False)
        print("answer:", response.choices[0].message.content)
    else:
        response = llm.run(prompt="一只橘猫坐在白色桌面上，商业摄影风格")
        print("image_urls:", llm.image_urls(response))


if __name__ == "__main__":
    main()
