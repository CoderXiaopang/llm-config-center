from sqlalchemy import select

from app.core.crypto import decrypt_api_key
from app.db.session import get_db
from app.models import AppAccessKey, ConfigVersion, ProviderApiKey


def unwrap(response):
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    return body["data"]


def create_full_config(client, admin_headers):
    provider = unwrap(
        client.post(
            "/api/v1/admin/providers",
            headers=admin_headers,
            json={
                "code": "volcengine",
                "name": "火山引擎",
                "protocol": "openai_compatible",
                "base_url": "https://ark.cn-beijing.volces.com/api/v3",
                "status": "enabled",
            },
        )
    )
    provider_key = unwrap(
        client.post(
            "/api/v1/admin/provider-api-keys",
            headers=admin_headers,
            json={"provider_id": provider["id"], "name": "火山生产 Key", "api_key": "sk-real-secret", "status": "enabled"},
        )
    )
    model = unwrap(
        client.post(
            "/api/v1/admin/models",
            headers=admin_headers,
            json={
                "provider_id": provider["id"],
                "model_name": "doubao-seed-1.6",
                "display_name": "豆包 Seed 1.6",
                "model_type": "chat",
                "support_stream": True,
                "support_vision": False,
                "context_window": 128000,
                "max_output_tokens": 8192,
                "status": "enabled",
            },
        )
    )
    alias = unwrap(
        client.post(
            "/api/v1/admin/aliases",
            headers=admin_headers,
            json={
                "alias": "chat-default",
                "env": "prod",
                "model_id": model["id"],
                "provider_api_key_id": provider_key["id"],
                "default_params": {"temperature": 0.7, "max_tokens": 4096, "timeout": 60, "stream": True},
                "status": "enabled",
            },
        )
    )
    app = unwrap(
        client.post(
            "/api/v1/admin/apps",
            headers=admin_headers,
            json={"app_code": "requirement-api", "app_name": "需求提取服务", "owner": "算法组", "status": "enabled"},
        )
    )
    access_key = unwrap(
        client.post(
            f"/api/v1/admin/apps/{app['id']}/access-keys",
            headers=admin_headers,
            json={"name": "requirement-api-prod-key"},
        )
    )
    permission = unwrap(
        client.post(
            f"/api/v1/admin/apps/{app['id']}/permissions",
            headers=admin_headers,
            json={"alias": "chat-default", "env": "prod", "can_read_config": True},
        )
    )
    return {
        "provider": provider,
        "provider_key": provider_key,
        "model": model,
        "alias": alias,
        "app": app,
        "access_key": access_key,
        "permission": permission,
    }


def test_login_success_and_failure(client):
    ok = client.post("/api/v1/admin/auth/login", json={"username": "admin", "password": "admin123456"})
    assert ok.status_code == 200
    assert ok.json()["data"]["user"]["role"] == "super_admin"

    bad = client.post("/api/v1/admin/auth/login", json={"username": "admin", "password": "wrong"})
    assert bad.status_code == 401


def test_provider_and_provider_api_key_do_not_store_plaintext(client, admin_headers):
    data = create_full_config(client, admin_headers)
    assert data["provider_key"]["key_mask"] == "sk-****cret"
    assert "api_key" not in data["provider_key"]

    db = next(client.app.dependency_overrides[get_db]())
    try:
        row = db.scalar(select(ProviderApiKey))
        assert row.encrypted_api_key != "sk-real-secret"
        assert decrypt_api_key(row.encrypted_api_key) == "sk-real-secret"
    finally:
        db.close()


def test_access_key_can_be_copied_and_hash_stored(client, admin_headers):
    data = create_full_config(client, admin_headers)
    full_key = data["access_key"]["access_key"]
    assert full_key.startswith("lcg_ak_")

    app_id = data["app"]["id"]
    listed = unwrap(client.get(f"/api/v1/admin/apps/{app_id}/access-keys", headers=admin_headers))
    assert listed[0]["access_key"] == full_key
    assert listed[0]["key_mask"].endswith(".****")

    db = next(client.app.dependency_overrides[get_db]())
    try:
        row = db.scalar(select(AppAccessKey))
        assert row.key_hash not in full_key
        assert row.key_prefix in full_key
    finally:
        db.close()


def test_runtime_config_success_and_invalid_access_key(client, admin_headers):
    data = create_full_config(client, admin_headers)
    headers = {"Authorization": f"Bearer {data['access_key']['access_key']}"}
    response = client.get("/api/v1/runtime/configs/chat-default?env=prod", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider"]["code"] == "volcengine"
    assert body["model"] == "doubao-seed-1.6"
    assert body["api_key"] == "sk-real-secret"
    assert body["params"]["max_tokens"] == 4096

    bad = client.get("/api/v1/runtime/configs/chat-default?env=prod", headers={"Authorization": "Bearer lcg_ak_bad.bad"})
    assert bad.status_code == 401


def test_runtime_forbidden_without_permission(client, admin_headers):
    data = create_full_config(client, admin_headers)
    other_app = unwrap(
        client.post(
            "/api/v1/admin/apps",
            headers=admin_headers,
            json={"app_code": "design-api", "app_name": "设计服务", "status": "enabled"},
        )
    )
    other_key = unwrap(client.post(f"/api/v1/admin/apps/{other_app['id']}/access-keys", headers=admin_headers, json={"name": "design-key"}))
    response = client.get(
        "/api/v1/runtime/configs/chat-default?env=prod",
        headers={"Authorization": f"Bearer {other_key['access_key']}"},
    )
    assert response.status_code == 403
    assert data["access_key"]["access_key"]


def test_alias_disabled_and_alias_update_bump_version(client, admin_headers):
    data = create_full_config(client, admin_headers)
    runtime_headers = {"Authorization": f"Bearer {data['access_key']['access_key']}"}
    version_before = client.get("/api/v1/runtime/config-version?env=prod", headers=runtime_headers).json()["version"]

    updated = unwrap(
        client.put(
            f"/api/v1/admin/aliases/{data['alias']['id']}",
            headers=admin_headers,
            json={
                "alias": "chat-default",
                "env": "prod",
                "model_id": data["model"]["id"],
                "provider_api_key_id": data["provider_key"]["id"],
                "default_params": {"temperature": 0.2},
                "status": "enabled",
            },
        )
    )
    assert updated["version"] == data["alias"]["version"] + 1
    version_after = client.get("/api/v1/runtime/config-version?env=prod", headers=runtime_headers).json()["version"]
    assert version_after == version_before + 1

    unwrap(client.post(f"/api/v1/admin/aliases/{data['alias']['id']}/disable", headers=admin_headers))
    disabled = client.get("/api/v1/runtime/configs/chat-default?env=prod", headers=runtime_headers)
    assert disabled.status_code == 409


def test_simple_config_item_creates_runtime_ready_config(client, admin_headers):
    created = unwrap(
        client.post(
            "/api/v1/admin/config-items",
            headers=admin_headers,
            json={
                "alias": "chat-simple",
                "env": "prod",
                "provider_code": "volcengine",
                "provider_name": "火山引擎",
                "base_url": "https://ark.cn-beijing.volces.com/api/v3",
                "api_key": "sk-simple-secret",
                "model_name": "doubao-seed-1.6",
                "model_type": "chat",
                "default_params": {"temperature": 0.5, "max_tokens": 2048},
                "app_code": "simple-client",
                "app_name": "简单客户端",
                "access_key_name": "simple-client-key",
            },
        )
    )
    assert created["alias"] == "chat-simple"
    assert created["access_key"].startswith("lcg_ak_")
    assert "client.get_config(\"chat-simple\")" in created["sdk_example"]

    listed = unwrap(client.get("/api/v1/admin/config-items", headers=admin_headers))
    assert listed[0]["alias"] == "chat-simple"
    assert listed[0]["key_mask"] == "sk-****cret"
    assert listed[0]["access_key"] == created["access_key"]

    runtime = client.get(
        "/api/v1/runtime/configs/chat-simple?env=prod",
        headers={"Authorization": f"Bearer {created['access_key']}"},
    )
    assert runtime.status_code == 200, runtime.text
    payload = runtime.json()
    assert payload["model"] == "doubao-seed-1.6"
    assert payload["api_key"] == "sk-simple-secret"
    assert payload["params"]["max_tokens"] == 2048

    updated = unwrap(
        client.put(
            f"/api/v1/admin/config-items/{created['id']}",
            headers=admin_headers,
            json={
                "alias": "seed5",
                "env": "prod",
                "provider_code": "volcengine",
                "provider_name": "火山引擎",
                "base_url": "https://ark.cn-beijing.volces.com/api/v3",
                "api_key": "sk-updated-secret",
                "model_name": "doubao-seed-evolving",
                "model_type": "chat",
                "default_params": {"temperature": 0.7, "max_tokens": 4096},
                "app_code": "simple-client",
                "app_name": "简单客户端",
                "access_key_name": "simple-client-key",
                "create_access_key": True,
            },
        )
    )
    assert updated["alias"] == "seed5"
    assert updated["model_name"] == "doubao-seed-evolving"
    assert updated["access_key"].startswith("lcg_ak_")

    runtime_after_edit = client.get(
        "/api/v1/runtime/configs/seed5?env=prod",
        headers={"Authorization": f"Bearer {updated['access_key']}"},
    )
    assert runtime_after_edit.status_code == 200, runtime_after_edit.text
    assert runtime_after_edit.json()["api_key"] == "sk-updated-secret"


def test_config_item_base_url_update_does_not_affect_other_items(client, admin_headers):
    first = unwrap(
        client.post(
            "/api/v1/admin/config-items",
            headers=admin_headers,
            json={
                "alias": "first-chat",
                "env": "prod",
                "provider_code": "shared-provider",
                "provider_name": "共享供应商",
                "base_url": "https://first.example.com/v1",
                "api_key": "sk-first-secret",
                "model_name": "model-a",
                "model_type": "chat",
                "default_params": {"temperature": 0.5},
                "app_code": "first-client",
                "app_name": "第一个客户端",
                "access_key_name": "first-key",
            },
        )
    )
    second = unwrap(
        client.post(
            "/api/v1/admin/config-items",
            headers=admin_headers,
            json={
                "alias": "second-chat",
                "env": "prod",
                "provider_code": "shared-provider",
                "provider_name": "共享供应商",
                "base_url": "https://second.example.com/v1",
                "api_key": "sk-second-secret",
                "model_name": "model-b",
                "model_type": "chat",
                "default_params": {"temperature": 0.6},
                "app_code": "second-client",
                "app_name": "第二个客户端",
                "access_key_name": "second-key",
            },
        )
    )
    assert first["provider_code"] == "shared-provider"
    assert second["provider_code"] == "shared-provider"

    updated = unwrap(
        client.put(
            f"/api/v1/admin/config-items/{first['id']}",
            headers=admin_headers,
            json={
                "alias": "first-chat",
                "env": "prod",
                "provider_code": "shared-provider",
                "provider_name": "共享供应商",
                "base_url": "https://first-updated.example.com/v1",
                "model_name": "model-a",
                "model_type": "chat",
                "default_params": {"temperature": 0.7},
                "app_code": "first-client",
                "app_name": "第一个客户端",
                "access_key_name": "first-key",
                "create_access_key": False,
            },
        )
    )
    assert updated["base_url"] == "https://first-updated.example.com/v1"

    items = unwrap(client.get("/api/v1/admin/config-items", headers=admin_headers))
    by_alias = {item["alias"]: item for item in items}
    assert by_alias["first-chat"]["base_url"] == "https://first-updated.example.com/v1"
    assert by_alias["second-chat"]["base_url"] == "https://second.example.com/v1"

    first_runtime = client.get(
        "/api/v1/runtime/configs/first-chat?env=prod",
        headers={"Authorization": f"Bearer {first['access_key']}"},
    )
    second_runtime = client.get(
        "/api/v1/runtime/configs/second-chat?env=prod",
        headers={"Authorization": f"Bearer {second['access_key']}"},
    )
    assert first_runtime.status_code == 200, first_runtime.text
    assert second_runtime.status_code == 200, second_runtime.text
    assert first_runtime.json()["base_url"] == "https://first-updated.example.com/v1"
    assert second_runtime.json()["base_url"] == "https://second.example.com/v1"


def test_config_item_call_type_is_returned_outside_params(client, admin_headers):
    created = unwrap(
        client.post(
            "/api/v1/admin/config-items",
            headers=admin_headers,
            json={
                "alias": "seedream-image",
                "env": "prod",
                "provider_code": "volcengine",
                "provider_name": "火山引擎",
                "base_url": "https://ark.cn-beijing.volces.com/api/v3",
                "api_key": "sk-image-secret",
                "model_name": "doubao-seedream-5-0-260128",
                "model_type": "image",
                "call_type": "image",
                "default_params": {"size": "2K", "response_format": "url", "watermark": True},
                "app_code": "image-client",
                "app_name": "图片客户端",
                "access_key_name": "image-key",
            },
        )
    )
    assert created["call_type"] == "image"
    assert "call_type" not in created["params"]

    listed = unwrap(client.get("/api/v1/admin/config-items", headers=admin_headers))
    item = next(row for row in listed if row["alias"] == "seedream-image")
    assert item["call_type"] == "image"
    assert "call_type" not in item["params"]

    runtime = client.get(
        "/api/v1/runtime/configs/seedream-image?env=prod",
        headers={"Authorization": f"Bearer {created['access_key']}"},
    )
    assert runtime.status_code == 200, runtime.text
    payload = runtime.json()
    assert payload["call_type"] == "image"
    assert payload["params"] == {"size": "2K", "response_format": "url", "watermark": True}


def test_runtime_reports_api_key_decrypt_failure(client, admin_headers):
    created = unwrap(
        client.post(
            "/api/v1/admin/config-items",
            headers=admin_headers,
            json={
                "alias": "broken-key",
                "env": "prod",
                "provider_code": "volcengine",
                "provider_name": "火山引擎",
                "base_url": "https://ark.cn-beijing.volces.com/api/v3",
                "api_key": "sk-simple-secret",
                "model_name": "doubao-seed-1.6",
                "model_type": "chat",
                "default_params": {"temperature": 0.5},
                "app_code": "broken-client",
                "app_name": "异常客户端",
                "access_key_name": "broken-client-key",
            },
        )
    )

    override_get_db = client.app.dependency_overrides[get_db]
    db_iter = override_get_db()
    db = next(db_iter)
    try:
        provider_key = db.scalar(select(ProviderApiKey))
        provider_key.encrypted_api_key = "not-a-fernet-token"
        db.commit()
    finally:
        db.close()

    runtime = client.get(
        "/api/v1/runtime/configs/broken-key?env=prod",
        headers={"Authorization": f"Bearer {created['access_key']}"},
    )
    assert runtime.status_code == 500
    assert runtime.json()["detail"] == "API_KEY_DECRYPT_FAILED"
