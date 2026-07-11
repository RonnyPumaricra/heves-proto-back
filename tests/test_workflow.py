"""Tests para la máquina de estados y los endpoints dedicados de Iteración 2."""
from tests.conftest import login, auth_headers


def _create_ticket(client, token, title="Test"):
    r = client.post(
        "/api/v1/tickets",
        json={"title": title, "description": "x", "priority": "media"},
        headers=auth_headers(token),
    )
    assert r.status_code == 201, r.text
    return r.json()


def _login_all(client):
    return {
        "admin": login(client, "admin@untels.edu.pe", "admin123"),
        "supervisor": login(client, "supervisor@untels.edu.pe", "supervisor123"),
        "tecnico": login(client, "tecnico@untels.edu.pe", "tecnico123"),
        "estudiante": login(client, "estudiante@untels.edu.pe", "estudiante123"),
        "docente": login(client, "docente@untels.edu.pe", "docente123"),
    }


# --- Asignación ---------------------------------------------------------------

def test_supervisor_can_assign_creates_ticket_to_tecnico(client, seeded):
    tokens = _login_all(client)
    t = _create_ticket(client, tokens["estudiante"])

    r = client.patch(
        f"/api/v1/tickets/{t['id']}/asignacion",
        json={"tecnico_id": seeded["users"]["tecnico"].id},
        headers=auth_headers(tokens["supervisor"]),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ASIGNADO"
    assert body["assigned_to"]["id"] == seeded["users"]["tecnico"].id


def test_admin_can_assign(client, seeded):
    tokens = _login_all(client)
    t = _create_ticket(client, tokens["estudiante"])
    r = client.patch(
        f"/api/v1/tickets/{t['id']}/asignacion",
        json={"tecnico_id": seeded["users"]["tecnico"].id},
        headers=auth_headers(tokens["admin"]),
    )
    assert r.status_code == 200


def test_tecnico_cannot_assign(client, seeded):
    tokens = _login_all(client)
    t = _create_ticket(client, tokens["estudiante"])
    r = client.patch(
        f"/api/v1/tickets/{t['id']}/asignacion",
        json={"tecnico_id": seeded["users"]["tecnico"].id},
        headers=auth_headers(tokens["tecnico"]),
    )
    assert r.status_code == 403


def test_usuario_cannot_assign(client, seeded):
    tokens = _login_all(client)
    t = _create_ticket(client, tokens["estudiante"])
    r = client.patch(
        f"/api/v1/tickets/{t['id']}/asignacion",
        json={"tecnico_id": seeded["users"]["tecnico"].id},
        headers=auth_headers(tokens["estudiante"]),
    )
    assert r.status_code == 403


def test_cannot_assign_non_tecnico(client, seeded):
    tokens = _login_all(client)
    t = _create_ticket(client, tokens["estudiante"])
    r = client.patch(
        f"/api/v1/tickets/{t['id']}/asignacion",
        json={"tecnico_id": seeded["users"]["estudiante"].id},
        headers=auth_headers(tokens["supervisor"]),
    )
    assert r.status_code == 400


def test_reassignment_is_allowed_while_in_process(client, seeded):
    tokens = _login_all(client)
    t = _create_ticket(client, tokens["estudiante"])
    other_tec_r = client.post(
        "/api/v1/users",
        json={
            "full_name": "Otro Técnico",
            "email": "otrotec@untels.edu.pe",
            "role": "tecnico",
            "password": "x123",
        },
        headers=auth_headers(tokens["admin"]),
    )
    other_tec_id = other_tec_r.json()["id"]

    client.patch(
        f"/api/v1/tickets/{t['id']}/asignacion",
        json={"tecnico_id": seeded["users"]["tecnico"].id},
        headers=auth_headers(tokens["supervisor"]),
    )
    client.patch(
        f"/api/v1/tickets/{t['id']}/estado",
        json={"status": "EN_PROCESO"},
        headers=auth_headers(tokens["tecnico"]),
    )

    r = client.patch(
        f"/api/v1/tickets/{t['id']}/asignacion",
        json={"tecnico_id": other_tec_id},
        headers=auth_headers(tokens["supervisor"]),
    )
    assert r.status_code == 200
    assert r.json()["assigned_to"]["id"] == other_tec_id
    assert r.json()["status"] == "ASIGNADO"


# --- Máquina de estados -------------------------------------------------------

def _walk_to_state(client, tokens, ticket_id, tecnico_id, target):
    """Lleva un ticket recién creado hasta el estado target."""
    order = ["CREADO", "ASIGNADO", "EN_PROCESO", "RESUELTO", "CERRADO"]
    if target == "CREADO":
        return

    r = client.patch(
        f"/api/v1/tickets/{ticket_id}/asignacion",
        json={"tecnico_id": tecnico_id},
        headers=auth_headers(tokens["supervisor"]),
    )
    assert r.status_code == 200
    if target == "ASIGNADO":
        return

    r = client.patch(
        f"/api/v1/tickets/{ticket_id}/estado",
        json={"status": "EN_PROCESO"},
        headers=auth_headers(tokens["tecnico"]),
    )
    assert r.status_code == 200
    if target == "EN_PROCESO":
        return

    r = client.patch(
        f"/api/v1/tickets/{ticket_id}/estado",
        json={"status": "RESUELTO"},
        headers=auth_headers(tokens["tecnico"]),
    )
    assert r.status_code == 200
    if target == "RESUELTO":
        return

    r = client.patch(
        f"/api/v1/tickets/{ticket_id}/estado",
        json={"status": "CERRADO"},
        headers=auth_headers(tokens["estudiante"]),
    )
    assert r.status_code == 200


def test_full_happy_path_sets_closed_at(client, seeded):
    tokens = _login_all(client)
    t = _create_ticket(client, tokens["estudiante"])
    _walk_to_state(
        client, tokens, t["id"], seeded["users"]["tecnico"].id, "CERRADO"
    )

    r = client.get(f"/api/v1/tickets/{t['id']}", headers=auth_headers(tokens["admin"]))
    body = r.json()
    assert body["status"] == "CERRADO"
    assert body["closed_at"] is not None


def test_tecnico_not_assigned_cannot_move_to_in_progress(client, seeded):
    tokens = _login_all(client)
    t = _create_ticket(client, tokens["estudiante"])

    other_r = client.post(
        "/api/v1/users",
        json={
            "full_name": "Otro",
            "email": "otro@untels.edu.pe",
            "role": "tecnico",
            "password": "x",
        },
        headers=auth_headers(tokens["admin"]),
    )
    other_id = other_r.json()["id"]
    client.patch(
        f"/api/v1/tickets/{t['id']}/asignacion",
        json={"tecnico_id": other_id},
        headers=auth_headers(tokens["supervisor"]),
    )

    r = client.patch(
        f"/api/v1/tickets/{t['id']}/estado",
        json={"status": "EN_PROCESO"},
        headers=auth_headers(tokens["tecnico"]),
    )
    assert r.status_code == 403


def test_reporter_can_close_after_resuelto(client, seeded):
    tokens = _login_all(client)
    t = _create_ticket(client, tokens["estudiante"])
    _walk_to_state(
        client, tokens, t["id"], seeded["users"]["tecnico"].id, "RESUELTO"
    )

    r = client.patch(
        f"/api/v1/tickets/{t['id']}/estado",
        json={"status": "CERRADO"},
        headers=auth_headers(tokens["estudiante"]),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "CERRADO"


def test_non_reporter_cannot_close(client, seeded):
    tokens = _login_all(client)
    t = _create_ticket(client, tokens["estudiante"])
    _walk_to_state(
        client, tokens, t["id"], seeded["users"]["tecnico"].id, "RESUELTO"
    )

    # Otro usuario intenta cerrar
    r = client.patch(
        f"/api/v1/tickets/{t['id']}/estado",
        json={"status": "CERRADO"},
        headers=auth_headers(tokens["docente"]),
    )
    assert r.status_code == 403

    # Técnico intenta cerrar (no está en la lista de roles permitidos para esta transición)
    r = client.patch(
        f"/api/v1/tickets/{t['id']}/estado",
        json={"status": "CERRADO"},
        headers=auth_headers(tokens["tecnico"]),
    )
    assert r.status_code == 403


def test_admin_can_close(client, seeded):
    tokens = _login_all(client)
    t = _create_ticket(client, tokens["estudiante"])
    _walk_to_state(
        client, tokens, t["id"], seeded["users"]["tecnico"].id, "RESUELTO"
    )
    r = client.patch(
        f"/api/v1/tickets/{t['id']}/estado",
        json={"status": "CERRADO"},
        headers=auth_headers(tokens["admin"]),
    )
    assert r.status_code == 200


def test_illegal_transition_skip_asignado(client, seeded):
    tokens = _login_all(client)
    t = _create_ticket(client, tokens["estudiante"])
    r = client.patch(
        f"/api/v1/tickets/{t['id']}/estado",
        json={"status": "EN_PROCESO"},
        headers=auth_headers(tokens["tecnico"]),
    )
    assert r.status_code == 400  # CREADO → EN_PROCESO no está definido


def test_illegal_transition_back_to_creado(client, seeded):
    tokens = _login_all(client)
    t = _create_ticket(client, tokens["estudiante"])
    _walk_to_state(
        client, tokens, t["id"], seeded["users"]["tecnico"].id, "ASIGNADO"
    )
    r = client.patch(
        f"/api/v1/tickets/{t['id']}/estado",
        json={"status": "CREADO"},
        headers=auth_headers(tokens["admin"]),
    )
    assert r.status_code == 400


def test_invalid_status_value_400(client, seeded):
    tokens = _login_all(client)
    t = _create_ticket(client, tokens["estudiante"])
    r = client.patch(
        f"/api/v1/tickets/{t['id']}/estado",
        json={"status": "MAGIC"},
        headers=auth_headers(tokens["admin"]),
    )
    assert r.status_code == 400


# --- Cambio de rol dedicado ---------------------------------------------------

def test_admin_can_change_user_role(client, seeded):
    tokens = _login_all(client)
    r = client.patch(
        f"/api/v1/users/{seeded['users']['tecnico'].id}/rol",
        json={"role": "supervisor"},
        headers=auth_headers(tokens["admin"]),
    )
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "supervisor"


def test_change_role_rejects_invalid(client, seeded):
    tokens = _login_all(client)
    r = client.patch(
        f"/api/v1/users/{seeded['users']['tecnico'].id}/rol",
        json={"role": "medico"},
        headers=auth_headers(tokens["admin"]),
    )
    assert r.status_code == 400


def test_non_admin_cannot_change_role(client, seeded):
    tokens = _login_all(client)
    r = client.patch(
        f"/api/v1/users/{seeded['users']['estudiante'].id}/rol",
        json={"role": "tecnico"},
        headers=auth_headers(tokens["supervisor"]),
    )
    assert r.status_code == 403
