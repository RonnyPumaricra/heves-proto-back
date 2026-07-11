from tests.conftest import login, auth_headers


def _create_ticket(client, token, **overrides):
    payload = {
        "title": "No abre el aula virtual",
        "description": "Redirige al login todo el tiempo",
        "priority": "alta",
    }
    payload.update(overrides)
    r = client.post("/api/v1/tickets", json=payload, headers=auth_headers(token))
    return r


def test_usuario_can_create_ticket_with_priority(client, seeded):
    token = login(client, "estudiante@untels.edu.pe", "estudiante123")
    r = _create_ticket(client, token)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["priority"] == "alta"
    assert body["status"] == "open"
    assert body["reporter"]["full_name"] == "Estudiante"
    # Área heredada de la del usuario
    assert body["area_name"] == "Aulas"


def test_ticket_without_device_is_allowed(client, seeded):
    token = login(client, "docente@untels.edu.pe", "docente123")
    r = _create_ticket(client, token, device_id=None)
    assert r.status_code == 201, r.text
    assert r.json()["device"] is None


def test_ticket_with_device_attaches_it(client, seeded):
    token = login(client, "estudiante@untels.edu.pe", "estudiante123")
    r = _create_ticket(client, token, device_id=seeded["devices"]["pc"].id)
    assert r.status_code == 201
    body = r.json()
    assert body["device"]["name"] == "PC Aula 302"


def test_invalid_priority_rejected(client, seeded):
    token = login(client, "estudiante@untels.edu.pe", "estudiante123")
    r = _create_ticket(client, token, priority="urgentisima")
    assert r.status_code == 400


def test_usuario_only_sees_own_tickets_in_me(client, seeded):
    token_est = login(client, "estudiante@untels.edu.pe", "estudiante123")
    token_doc = login(client, "docente@untels.edu.pe", "docente123")
    _create_ticket(client, token_est, title="Ticket del estudiante")
    _create_ticket(client, token_doc, title="Ticket del docente")

    r = client.get("/api/v1/tickets/me", headers=auth_headers(token_est))
    assert r.status_code == 200
    titles = [t["title"] for t in r.json()]
    assert titles == ["Ticket del estudiante"]


def test_usuario_cannot_list_all_tickets(client, seeded):
    token = login(client, "estudiante@untels.edu.pe", "estudiante123")
    r = client.get("/api/v1/tickets", headers=auth_headers(token))
    assert r.status_code == 403


def test_tecnico_can_list_all_tickets(client, seeded):
    token_est = login(client, "estudiante@untels.edu.pe", "estudiante123")
    _create_ticket(client, token_est)

    token_tec = login(client, "tecnico@untels.edu.pe", "tecnico123")
    r = client.get("/api/v1/tickets", headers=auth_headers(token_tec))
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_admin_can_list_all_tickets(client, seeded):
    token_est = login(client, "estudiante@untels.edu.pe", "estudiante123")
    _create_ticket(client, token_est)

    token_adm = login(client, "admin@untels.edu.pe", "admin123")
    r = client.get("/api/v1/tickets", headers=auth_headers(token_adm))
    assert r.status_code == 200


def test_tecnico_can_update_ticket_priority_and_status(client, seeded):
    token_est = login(client, "estudiante@untels.edu.pe", "estudiante123")
    created = _create_ticket(client, token_est).json()

    token_tec = login(client, "tecnico@untels.edu.pe", "tecnico123")
    r = client.patch(
        f"/api/v1/tickets/{created['id']}",
        json={"status": "in_progress", "priority": "critica"},
        headers=auth_headers(token_tec),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "in_progress"
    assert r.json()["priority"] == "critica"


def test_usuario_cannot_update_ticket(client, seeded):
    token_est = login(client, "estudiante@untels.edu.pe", "estudiante123")
    created = _create_ticket(client, token_est).json()

    r = client.patch(
        f"/api/v1/tickets/{created['id']}",
        json={"status": "in_progress"},
        headers=auth_headers(token_est),
    )
    assert r.status_code == 403


def test_usuario_cannot_read_other_users_ticket(client, seeded):
    token_est = login(client, "estudiante@untels.edu.pe", "estudiante123")
    created = _create_ticket(client, token_est).json()

    token_doc = login(client, "docente@untels.edu.pe", "docente123")
    r = client.get(f"/api/v1/tickets/{created['id']}", headers=auth_headers(token_doc))
    assert r.status_code == 403


def test_filter_by_priority(client, seeded):
    token_est = login(client, "estudiante@untels.edu.pe", "estudiante123")
    _create_ticket(client, token_est, priority="alta", title="Uno")
    _create_ticket(client, token_est, priority="baja", title="Dos")

    token_tec = login(client, "tecnico@untels.edu.pe", "tecnico123")
    r = client.get(
        "/api/v1/tickets",
        params={"priority": "alta"},
        headers=auth_headers(token_tec),
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["title"] == "Uno"
