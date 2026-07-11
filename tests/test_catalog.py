"""Tests para CRUDs de admin y filtros de catálogo (Iteración 6)."""
from tests.conftest import login, auth_headers


def _login_all(client):
    return {
        "admin": login(client, "admin@untels.edu.pe", "admin123"),
        "supervisor": login(client, "supervisor@untels.edu.pe", "supervisor123"),
        "tecnico": login(client, "tecnico@untels.edu.pe", "tecnico123"),
        "estudiante": login(client, "estudiante@untels.edu.pe", "estudiante123"),
    }


# --- Areas -------------------------------------------------------------------

def test_admin_can_update_area(client, seeded):
    tokens = _login_all(client)
    r = client.patch(
        f"/api/v1/areas/{seeded['areas']['labs'].id}",
        json={"name": "Laboratorios de Cómputo"},
        headers=auth_headers(tokens["admin"]),
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Laboratorios de Cómputo"


def test_update_area_rejects_duplicate_name(client, seeded):
    tokens = _login_all(client)
    r = client.patch(
        f"/api/v1/areas/{seeded['areas']['labs'].id}",
        json={"name": "Aulas"},
        headers=auth_headers(tokens["admin"]),
    )
    assert r.status_code == 400


def test_admin_can_delete_unused_area(client, seeded):
    tokens = _login_all(client)
    new_area = client.post(
        "/api/v1/areas",
        json={"name": "Área Fantasma"},
        headers=auth_headers(tokens["admin"]),
    ).json()
    r = client.delete(
        f"/api/v1/areas/{new_area['id']}",
        headers=auth_headers(tokens["admin"]),
    )
    assert r.status_code == 204
    r = client.get("/api/v1/areas", headers=auth_headers(tokens["admin"]))
    assert new_area["id"] not in [a["id"] for a in r.json()]


def test_cannot_delete_area_with_tickets(client, seeded):
    tokens = _login_all(client)
    # Crea un ticket que usa el área "Aulas" (heredada del estudiante)
    client.post(
        "/api/v1/tickets",
        json={"title": "t", "description": "d", "priority": "media"},
        headers=auth_headers(tokens["estudiante"]),
    )
    r = client.delete(
        f"/api/v1/areas/{seeded['areas']['aulas'].id}",
        headers=auth_headers(tokens["admin"]),
    )
    assert r.status_code == 400


def test_cannot_delete_area_with_users(client, seeded):
    tokens = _login_all(client)
    r = client.delete(
        f"/api/v1/areas/{seeded['areas']['aulas'].id}",
        headers=auth_headers(tokens["admin"]),
    )
    # aulas está referenciada por estudiante
    assert r.status_code == 400


def test_delete_area_requires_admin(client, seeded):
    tokens = _login_all(client)
    r = client.delete(
        f"/api/v1/areas/{seeded['areas']['labs'].id}",
        headers=auth_headers(tokens["supervisor"]),
    )
    assert r.status_code == 403


def test_delete_missing_area_404(client, seeded):
    tokens = _login_all(client)
    r = client.delete("/api/v1/areas/9999", headers=auth_headers(tokens["admin"]))
    assert r.status_code == 404


# --- Devices -----------------------------------------------------------------

def test_admin_can_soft_delete_device(client, seeded):
    tokens = _login_all(client)
    r = client.delete(
        f"/api/v1/devices/{seeded['devices']['pc'].id}",
        headers=auth_headers(tokens["admin"]),
    )
    assert r.status_code == 204

    # Ya no aparece en la lista (list filtra por is_active)
    r = client.get("/api/v1/devices", headers=auth_headers(tokens["admin"]))
    ids = [d["id"] for d in r.json()]
    assert seeded["devices"]["pc"].id not in ids


def test_delete_device_requires_admin(client, seeded):
    tokens = _login_all(client)
    r = client.delete(
        f"/api/v1/devices/{seeded['devices']['pc'].id}",
        headers=auth_headers(tokens["supervisor"]),
    )
    assert r.status_code == 403


def test_delete_missing_device_404(client, seeded):
    tokens = _login_all(client)
    r = client.delete("/api/v1/devices/9999", headers=auth_headers(tokens["admin"]))
    assert r.status_code == 404


# --- Filtro creadoPor --------------------------------------------------------

def test_filter_creado_por_returns_only_reporters_tickets(client, seeded):
    tokens = _login_all(client)
    client.post(
        "/api/v1/tickets",
        json={"title": "del estudiante", "description": "d", "priority": "media"},
        headers=auth_headers(tokens["estudiante"]),
    )
    client.post(
        "/api/v1/tickets",
        json={"title": "del docente", "description": "d", "priority": "media"},
        headers=auth_headers(login(client, "docente@untels.edu.pe", "docente123")),
    )
    r = client.get(
        "/api/v1/tickets",
        params={"creadoPor": seeded["users"]["estudiante"].id},
        headers=auth_headers(tokens["supervisor"]),
    )
    assert r.status_code == 200
    titles = [t["title"] for t in r.json()]
    assert titles == ["del estudiante"]


def test_filter_creado_por_empty_result(client, seeded):
    tokens = _login_all(client)
    r = client.get(
        "/api/v1/tickets",
        params={"creadoPor": seeded["users"]["docente"].id},
        headers=auth_headers(tokens["supervisor"]),
    )
    assert r.status_code == 200
    assert r.json() == []
