from tests.conftest import login, auth_headers


def test_login_ok_for_each_role(client, seeded):
    creds = [
        ("admin@untels.edu.pe", "admin123", "admin"),
        ("tecnico@untels.edu.pe", "tecnico123", "tecnico"),
        ("supervisor@untels.edu.pe", "supervisor123", "supervisor"),
        ("estudiante@untels.edu.pe", "estudiante123", "usuario"),
        ("docente@untels.edu.pe", "docente123", "usuario"),
    ]
    for email, password, expected_role in creds:
        r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, f"login falló para {email}: {r.text}"
        body = r.json()
        assert body["role"] == expected_role
        assert body["access_token"]


def test_login_wrong_password_401(client, seeded):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@untels.edu.pe", "password": "nope"},
    )
    assert r.status_code == 401


def test_login_unknown_email_401(client, seeded):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@untels.edu.pe", "password": "x"},
    )
    assert r.status_code == 401


def test_me_returns_user(client, seeded):
    token = login(client, "estudiante@untels.edu.pe", "estudiante123")
    r = client.get("/api/v1/auth/me", headers=auth_headers(token))
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "usuario"
    assert body["email"] == "estudiante@untels.edu.pe"
    assert body["area_name"] == "Aulas"


def test_me_without_token_401(client, seeded):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_qr_login_endpoint_removed(client, seeded):
    r = client.post("/api/v1/auth/qr-login", json={"token": "abc"})
    assert r.status_code == 404
