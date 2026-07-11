"""Tests para el historial de ticket (Iteración 3)."""
from tests.conftest import login, auth_headers


def _create_ticket(client, token, title="T1"):
    r = client.post(
        "/api/v1/tickets",
        json={"title": title, "description": "x", "priority": "media"},
        headers=auth_headers(token),
    )
    assert r.status_code == 201
    return r.json()


def _login_all(client):
    return {
        "admin": login(client, "admin@untels.edu.pe", "admin123"),
        "supervisor": login(client, "supervisor@untels.edu.pe", "supervisor123"),
        "tecnico": login(client, "tecnico@untels.edu.pe", "tecnico123"),
        "estudiante": login(client, "estudiante@untels.edu.pe", "estudiante123"),
        "docente": login(client, "docente@untels.edu.pe", "docente123"),
    }


def _get_history(client, ticket_id, token):
    r = client.get(f"/api/v1/tickets/{ticket_id}/history", headers=auth_headers(token))
    assert r.status_code == 200, r.text
    return r.json()


# --- Registro por PATCH -------------------------------------------------------

def test_assign_records_two_entries(client, seeded):
    tokens = _login_all(client)
    t = _create_ticket(client, tokens["estudiante"])

    client.patch(
        f"/api/v1/tickets/{t['id']}/asignacion",
        json={"tecnico_id": seeded["users"]["tecnico"].id},
        headers=auth_headers(tokens["supervisor"]),
    )

    entries = _get_history(client, t["id"], tokens["admin"])
    fields = [(e["field"], e["old_value"], e["new_value"]) for e in entries]
    assert ("assigned_to", None, "Tecnico") in fields
    assert ("status", "CREADO", "ASIGNADO") in fields
    assert all(e["actor_name"] == "Supervisor" for e in entries)


def test_status_transition_records_entry(client, seeded):
    tokens = _login_all(client)
    t = _create_ticket(client, tokens["estudiante"])
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

    entries = _get_history(client, t["id"], tokens["admin"])
    en_proceso = [e for e in entries if e["new_value"] == "EN_PROCESO"]
    assert len(en_proceso) == 1
    assert en_proceso[0]["field"] == "status"
    assert en_proceso[0]["old_value"] == "ASIGNADO"
    assert en_proceso[0]["actor_name"] == "Tecnico"


def test_generic_patch_records_priority_and_status(client, seeded):
    tokens = _login_all(client)
    t = _create_ticket(client, tokens["estudiante"])

    # Bring to ASIGNADO first so a generic status change is legal
    client.patch(
        f"/api/v1/tickets/{t['id']}/asignacion",
        json={"tecnico_id": seeded["users"]["tecnico"].id},
        headers=auth_headers(tokens["supervisor"]),
    )

    r = client.patch(
        f"/api/v1/tickets/{t['id']}",
        json={"priority": "critica", "status": "EN_PROCESO"},
        headers=auth_headers(tokens["admin"]),
    )
    assert r.status_code == 200

    entries = _get_history(client, t["id"], tokens["admin"])
    prio = [e for e in entries if e["field"] == "priority"]
    assert prio[-1]["old_value"] == "media"
    assert prio[-1]["new_value"] == "critica"
    stat = [e for e in entries if e["field"] == "status" and e["new_value"] == "EN_PROCESO"]
    assert len(stat) == 1


def test_generic_patch_records_area_change(client, seeded):
    tokens = _login_all(client)
    t = _create_ticket(client, tokens["estudiante"])
    r = client.patch(
        f"/api/v1/tickets/{t['id']}",
        json={"area_id": seeded["areas"]["labs"].id},
        headers=auth_headers(tokens["admin"]),
    )
    assert r.status_code == 200
    entries = _get_history(client, t["id"], tokens["admin"])
    area = [e for e in entries if e["field"] == "area"]
    assert area[-1]["old_value"] == "Aulas"
    assert area[-1]["new_value"] == "Laboratorios"


def test_full_lifecycle_creates_ordered_history(client, seeded):
    tokens = _login_all(client)
    t = _create_ticket(client, tokens["estudiante"])
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
    client.patch(
        f"/api/v1/tickets/{t['id']}/estado",
        json={"status": "RESUELTO"},
        headers=auth_headers(tokens["tecnico"]),
    )
    client.patch(
        f"/api/v1/tickets/{t['id']}/estado",
        json={"status": "CERRADO"},
        headers=auth_headers(tokens["estudiante"]),
    )

    entries = _get_history(client, t["id"], tokens["admin"])
    status_transitions = [
        (e["old_value"], e["new_value"]) for e in entries if e["field"] == "status"
    ]
    assert status_transitions == [
        ("CREADO", "ASIGNADO"),
        ("ASIGNADO", "EN_PROCESO"),
        ("EN_PROCESO", "RESUELTO"),
        ("RESUELTO", "CERRADO"),
    ]


def test_no_op_patch_records_nothing(client, seeded):
    tokens = _login_all(client)
    t = _create_ticket(client, tokens["estudiante"])
    r = client.patch(
        f"/api/v1/tickets/{t['id']}",
        json={"priority": "media"},  # sin cambio real
        headers=auth_headers(tokens["admin"]),
    )
    assert r.status_code == 200
    entries = _get_history(client, t["id"], tokens["admin"])
    assert entries == []


# --- Permisos del GET /history -----------------------------------------------

def test_reporter_can_view_history(client, seeded):
    tokens = _login_all(client)
    t = _create_ticket(client, tokens["estudiante"])
    client.patch(
        f"/api/v1/tickets/{t['id']}/asignacion",
        json={"tecnico_id": seeded["users"]["tecnico"].id},
        headers=auth_headers(tokens["supervisor"]),
    )
    r = client.get(f"/api/v1/tickets/{t['id']}/history", headers=auth_headers(tokens["estudiante"]))
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_assigned_tecnico_can_view_history(client, seeded):
    tokens = _login_all(client)
    t = _create_ticket(client, tokens["estudiante"])
    client.patch(
        f"/api/v1/tickets/{t['id']}/asignacion",
        json={"tecnico_id": seeded["users"]["tecnico"].id},
        headers=auth_headers(tokens["supervisor"]),
    )
    r = client.get(f"/api/v1/tickets/{t['id']}/history", headers=auth_headers(tokens["tecnico"]))
    assert r.status_code == 200


def test_other_usuario_cannot_view_history(client, seeded):
    tokens = _login_all(client)
    t = _create_ticket(client, tokens["estudiante"])
    r = client.get(f"/api/v1/tickets/{t['id']}/history", headers=auth_headers(tokens["docente"]))
    assert r.status_code == 403


def test_unassigned_tecnico_cannot_view_history(client, seeded):
    tokens = _login_all(client)
    other_r = client.post(
        "/api/v1/users",
        json={
            "full_name": "Otro Tec",
            "email": "otrotec2@untels.edu.pe",
            "role": "tecnico",
            "password": "x",
        },
        headers=auth_headers(tokens["admin"]),
    )
    other_token = login(client, "otrotec2@untels.edu.pe", "x")
    t = _create_ticket(client, tokens["estudiante"])
    client.patch(
        f"/api/v1/tickets/{t['id']}/asignacion",
        json={"tecnico_id": seeded["users"]["tecnico"].id},
        headers=auth_headers(tokens["supervisor"]),
    )
    r = client.get(f"/api/v1/tickets/{t['id']}/history", headers=auth_headers(other_token))
    assert r.status_code == 403


def test_supervisor_and_admin_can_view_any_history(client, seeded):
    tokens = _login_all(client)
    t = _create_ticket(client, tokens["docente"])
    for token in (tokens["supervisor"], tokens["admin"]):
        r = client.get(f"/api/v1/tickets/{t['id']}/history", headers=auth_headers(token))
        assert r.status_code == 200


def test_history_missing_ticket_404(client, seeded):
    tokens = _login_all(client)
    r = client.get("/api/v1/tickets/9999/history", headers=auth_headers(tokens["admin"]))
    assert r.status_code == 404
