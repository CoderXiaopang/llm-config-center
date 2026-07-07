def test_audit_log_sanitizes_sensitive_values(client, admin_headers):
    client.post(
        "/api/v1/admin/providers",
        headers=admin_headers,
        json={"code": "dashscope", "name": "阿里百炼", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
    )
    provider_id = client.get("/api/v1/admin/providers", headers=admin_headers).json()["data"][0]["id"]
    client.post(
        "/api/v1/admin/provider-api-keys",
        headers=admin_headers,
        json={"provider_id": provider_id, "name": "阿里生产 Key", "api_key": "sk-sensitive-value"},
    )
    logs = client.get("/api/v1/admin/audit-logs", headers=admin_headers).json()["data"]["items"]
    text = str(logs)
    assert "sk-sensitive-value" not in text
    assert "'api_key': '***'" in text

