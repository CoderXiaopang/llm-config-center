import httpx

from llm_config_sdk import LLMConfigClient


def make_transport(state):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/config-version"):
            return httpx.Response(200, json={"env": "prod", "version": state["version"], "updated_at": None})
        if request.url.path.endswith("/configs/chat-default"):
            return httpx.Response(
                200,
                json={
                    "alias": "chat-default",
                    "env": "prod",
                    "provider": {"code": "volcengine", "name": "火山引擎", "protocol": "openai_compatible"},
                    "base_url": "https://example.com/v1",
                    "model": state["model"],
                    "api_key": "sk-test",
                    "params": {"temperature": 0.7},
                    "version": state["version"],
                    "updated_at": None,
                },
            )
        if request.url.path.endswith("/configs"):
            return httpx.Response(
                200,
                json={
                    "env": "prod",
                    "version": state["version"],
                    "configs": [
                        {
                            "alias": "chat-default",
                            "env": "prod",
                            "provider": {"code": "volcengine", "name": "火山引擎", "protocol": "openai_compatible"},
                            "base_url": "https://example.com/v1",
                            "model": state["model"],
                            "api_key": "sk-test",
                            "params": {},
                            "version": state["version"],
                            "updated_at": None,
                        }
                    ],
                },
            )
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_get_config_and_version():
    state = {"version": 1, "model": "doubao-seed-1.6"}
    client = LLMConfigClient("http://test", "lcg_ak_test.secret", http_client=httpx.Client(transport=make_transport(state)))
    config = client.get_config("chat-default")
    assert config.model == "doubao-seed-1.6"
    assert client.get_version() == 1


def test_version_change_refreshes_cache():
    state = {"version": 1, "model": "doubao-seed-1.6"}
    client = LLMConfigClient("http://test", "lcg_ak_test.secret", refresh_interval=0, http_client=httpx.Client(transport=make_transport(state)))
    assert client.get_config("chat-default").model == "doubao-seed-1.6"
    state["version"] = 2
    state["model"] = "qwen-plus"
    assert client.get_config("chat-default").model == "qwen-plus"


def test_create_openai_client_uses_config():
    state = {"version": 1, "model": "doubao-seed-1.6"}
    made = {}

    def factory(base_url: str, api_key: str):
        made["base_url"] = base_url
        made["api_key"] = api_key
        return {"client": "ok"}

    client = LLMConfigClient("http://test", "lcg_ak_test.secret", http_client=httpx.Client(transport=make_transport(state)), openai_factory=factory)
    openai_client, model = client.create_openai_client("chat-default")
    assert openai_client == {"client": "ok"}
    assert model == "doubao-seed-1.6"
    assert made == {"base_url": "https://example.com/v1", "api_key": "sk-test"}

