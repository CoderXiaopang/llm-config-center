def unwrap(response):
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    return body["data"]


def test_user_management_create_update_disable_login_flow(client, admin_headers):
    created = unwrap(
        client.post(
            "/api/v1/admin/users",
            headers=admin_headers,
            json={
                "username": "operator1",
                "password": "op-pass-123",
                "display_name": "操作员一号",
                "role": "operator",
                "status": "enabled",
            },
        )
    )
    assert created["username"] == "operator1"
    assert "password" not in created
    assert "password_hash" not in created

    users = unwrap(client.get("/api/v1/admin/users", headers=admin_headers))
    assert any(item["username"] == "operator1" for item in users)
    assert "op-pass-123" not in str(users)

    login = client.post("/api/v1/admin/auth/login", json={"username": "operator1", "password": "op-pass-123"})
    assert login.status_code == 200

    updated = unwrap(
        client.put(
            f"/api/v1/admin/users/{created['id']}",
            headers=admin_headers,
            json={
                "username": "operator1",
                "display_name": "操作员一号改",
                "role": "admin",
                "status": "enabled",
            },
        )
    )
    assert updated["display_name"] == "操作员一号改"
    assert updated["role"] == "admin"

    unwrap(client.post(f"/api/v1/admin/users/{created['id']}/password", headers=admin_headers, json={"password": "new-pass-456"}))
    old_login = client.post("/api/v1/admin/auth/login", json={"username": "operator1", "password": "op-pass-123"})
    assert old_login.status_code == 401
    new_login = client.post("/api/v1/admin/auth/login", json={"username": "operator1", "password": "new-pass-456"})
    assert new_login.status_code == 200

    disabled = unwrap(client.post(f"/api/v1/admin/users/{created['id']}/disable", headers=admin_headers))
    assert disabled["status"] == "disabled"
    disabled_login = client.post("/api/v1/admin/auth/login", json={"username": "operator1", "password": "new-pass-456"})
    assert disabled_login.status_code == 401

