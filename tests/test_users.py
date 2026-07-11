from tests.conftest import login, auth_headers


def test_admin_can_create_usuario(client, seeded):
    token = login(client, "admin@untels.edu.pe", "admin123")
    r = client.post(
        "/api/v1/users",
        json={
            "full_name": "Nuevo Estudiante",
            "email": "nuevo@untels.edu.pe",
            "role": "usuario",
            "password": "clave123",
        },
        headers=auth_headers(token),
    )
    assert r.status_code == 201, r.text
    assert r.json()["role"] == "usuario"


def test_admin_can_create_all_roles(client, seeded):
    token = login(client, "admin@untels.edu.pe", "admin123")
    for i, role in enumerate(["usuario", "tecnico", "supervisor", "admin"]):
        r = client.post(
            "/api/v1/users",
            json={
                "full_name": f"Nuevo {role}",
                "email": f"nuevo{i}@untels.edu.pe",
                "role": role,
                "password": "clave123",
            },
            headers=auth_headers(token),
        )
        assert r.status_code == 201, f"falló para rol {role}: {r.text}"


def test_admin_rejects_invalid_role(client, seeded):
    token = login(client, "admin@untels.edu.pe", "admin123")
    r = client.post(
        "/api/v1/users",
        json={
            "full_name": "Rol Malo",
            "email": "malo@untels.edu.pe",
            "role": "medico",
            "password": "x",
        },
        headers=auth_headers(token),
    )
    assert r.status_code == 400


def test_tecnico_cannot_list_users(client, seeded):
    token = login(client, "tecnico@untels.edu.pe", "tecnico123")
    r = client.get("/api/v1/users", headers=auth_headers(token))
    assert r.status_code == 403


def test_usuario_cannot_list_users(client, seeded):
    token = login(client, "estudiante@untels.edu.pe", "estudiante123")
    r = client.get("/api/v1/users", headers=auth_headers(token))
    assert r.status_code == 403


def test_admin_lists_users_filtered_by_role(client, seeded):
    token = login(client, "admin@untels.edu.pe", "admin123")
    r = client.get(
        "/api/v1/users",
        params={"role": "tecnico"},
        headers=auth_headers(token),
    )
    assert r.status_code == 200
    roles = {u["role"] for u in r.json()}
    assert roles == {"tecnico"}


def test_qr_regenerate_endpoint_removed(client, seeded):
    token = login(client, "admin@untels.edu.pe", "admin123")
    r = client.post(
        f"/api/v1/users/{seeded['users']['estudiante'].id}/qr-token/regenerate",
        headers=auth_headers(token),
    )
    assert r.status_code == 404
