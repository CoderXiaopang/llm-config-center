from dataclasses import dataclass
from typing import Any

import httpx

from llm_config_sdk.cache import ConfigCache
from llm_config_sdk.openai_factory import create_openai_client as default_openai_factory


@dataclass
class ModelConfig:
    alias: str
    env: str
    provider: dict[str, Any]
    base_url: str
    model: str
    api_key: str
    params: dict[str, Any]
    version: int
    updated_at: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ModelConfig":
        return cls(**payload)


class LLMConfigClient:
    def __init__(
        self,
        server_url: str,
        access_key: str,
        env: str = "prod",
        refresh_interval: int = 60,
        timeout: float = 10.0,
        http_client: httpx.Client | None = None,
        openai_factory=default_openai_factory,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.access_key = access_key
        self.env = env
        self.refresh_interval = refresh_interval
        self.http = http_client or httpx.Client(timeout=timeout)
        self.openai_factory = openai_factory
        self.cache = ConfigCache()

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_key}"}

    def get_version(self) -> int:
        response = self.http.get(f"{self.server_url}/api/v1/runtime/config-version", params={"env": self.env}, headers=self.headers)
        response.raise_for_status()
        return int(response.json()["version"])

    def refresh_if_needed(self) -> bool:
        if not self.cache.should_check(self.refresh_interval):
            return False
        version = self.get_version()
        self.cache.mark_checked()
        if self.cache.version is None:
            self.cache.version = version
            return False
        if version != self.cache.version:
            self.cache.version = version
            self.cache.clear()
            return True
        return False

    def force_refresh(self) -> None:
        self.cache.clear()
        self.cache.version = self.get_version()
        self.cache.mark_checked()

    def get_config(self, alias: str) -> ModelConfig:
        self.refresh_if_needed()
        if alias in self.cache.items:
            return self.cache.items[alias]
        response = self.http.get(f"{self.server_url}/api/v1/runtime/configs/{alias}", params={"env": self.env}, headers=self.headers)
        response.raise_for_status()
        config = ModelConfig.from_payload(response.json())
        self.cache.items[alias] = config
        self.cache.version = config.version if self.cache.version is None else self.cache.version
        return config

    def get_all_configs(self) -> list[ModelConfig]:
        self.refresh_if_needed()
        response = self.http.get(f"{self.server_url}/api/v1/runtime/configs", params={"env": self.env}, headers=self.headers)
        response.raise_for_status()
        payload = response.json()
        configs = [ModelConfig.from_payload(item) for item in payload["configs"]]
        self.cache.version = int(payload["version"])
        self.cache.items = {item.alias: item for item in configs}
        self.cache.mark_checked()
        return configs

    def create_openai_client(self, alias: str):
        config = self.get_config(alias)
        return self.openai_factory(base_url=config.base_url, api_key=config.api_key), config.model

