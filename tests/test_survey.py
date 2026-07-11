"""Tests para encuesta de satisfacción (Iteración 5)."""
from tests.conftest import login, auth_headers


def _login_all(client):
    return {
        "admin": login(client, "admin@untels.edu.pe", "admin123"),
        "supervisor": login(client, "supervisor@untels.edu.pe", "supervisor123"),
        "tecnico": login(client, "tecnico@untels.edu.pe", "tecnico123"),
        "estudiante": login(client, "estudiante@untels.edu.pe", "estudiante123"),
        "docente": login(client, "docente@untels.edu.pe", "docente123"),
    }


def _create_and_close(client, tokens, tecnico_id):
    r = client.post(
        "/api/v1/tickets",
        json={"title": "T", "description": "d", "priority": "media"},
        headers=auth_headers(tokens["estudiante"]),
    )
    t = r.json()
    client.patch(
        f"/api/v1/tickets/{t['id']}/asignacion",
        json={"tecnico_id": tecnico_id},
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
    return t


# --- Envío -------------------------------------------------------------------

def test_reporter_can_submit_survey_after_close(client, seeded):
    tokens = _login_all(client)
    t = _create_and_close(client, tokens, seeded["users"]["tecnico"].id)
    r = client.post(
        f"/api/v1/tickets/{t['id']}/survey",
        json={"rating": 5, "comment": "Excelente"},
        headers=auth_headers(tokens["estudiante"]),
    )
    assert r.status_code == 201, r.text
    assert r.json()["rating"] == 5
    assert r.json()["comment"] == "Excelente"


def test_survey_embedded_in_ticket_after_submit(client, seeded):
    tokens = _login_all(client)
    t = _create_and_close(client, tokens, seeded["users"]["tecnico"].id)
    client.post(
        f"/api/v1/tickets/{t['id']}/survey",
        json={"rating": 4, "comment": None},
        headers=auth_headers(tokens["estudiante"]),
    )
    r = client.get(f"/api/v1/tickets/{t['id']}", headers=auth_headers(tokens["estudiante"]))
    assert r.status_code == 200
    body = r.json()
    assert body["survey"] is not None
    assert body["survey"]["rating"] == 4


def test_ticket_without_survey_has_null_field(client, seeded):
    tokens = _login_all(client)
    r = client.post(
        "/api/v1/tickets",
        json={"title": "T", "description": "d", "priority": "media"},
        headers=auth_headers(tokens["estudiante"]),
    )
    t = r.json()
    assert t["survey"] is None


# --- Rechazos ----------------------------------------------------------------

def test_cannot_submit_before_close(client, seeded):
    tokens = _login_all(client)
    r = client.post(
        "/api/v1/tickets",
        json={"title": "T", "description": "d", "priority": "media"},
        headers=auth_headers(tokens["estudiante"]),
    )
    t = r.json()
    r = client.post(
        f"/api/v1/tickets/{t['id']}/survey",
        json={"rating": 4},
        headers=auth_headers(tokens["estudiante"]),
    )
    assert r.status_code == 400


def test_non_reporter_cannot_submit(client, seeded):
    tokens = _login_all(client)
    t = _create_and_close(client, tokens, seeded["users"]["tecnico"].id)
    r = client.post(
        f"/api/v1/tickets/{t['id']}/survey",
        json={"rating": 5},
        headers=auth_headers(tokens["docente"]),
    )
    assert r.status_code == 403


def test_tecnico_cannot_submit(client, seeded):
    tokens = _login_all(client)
    t = _create_and_close(client, tokens, seeded["users"]["tecnico"].id)
    r = client.post(
        f"/api/v1/tickets/{t['id']}/survey",
        json={"rating": 5},
        headers=auth_headers(tokens["tecnico"]),
    )
    assert r.status_code == 403


def test_duplicate_survey_rejected(client, seeded):
    tokens = _login_all(client)
    t = _create_and_close(client, tokens, seeded["users"]["tecnico"].id)
    r1 = client.post(
        f"/api/v1/tickets/{t['id']}/survey",
        json={"rating": 5},
        headers=auth_headers(tokens["estudiante"]),
    )
    assert r1.status_code == 201
    r2 = client.post(
        f"/api/v1/tickets/{t['id']}/survey",
        json={"rating": 3},
        headers=auth_headers(tokens["estudiante"]),
    )
    assert r2.status_code == 400


def test_rating_out_of_range_rejected(client, seeded):
    tokens = _login_all(client)
    t = _create_and_close(client, tokens, seeded["users"]["tecnico"].id)
    r = client.post(
        f"/api/v1/tickets/{t['id']}/survey",
        json={"rating": 6},
        headers=auth_headers(tokens["estudiante"]),
    )
    assert r.status_code == 422

    r = client.post(
        f"/api/v1/tickets/{t['id']}/survey",
        json={"rating": 0},
        headers=auth_headers(tokens["estudiante"]),
    )
    assert r.status_code == 422


def test_survey_on_missing_ticket_404(client, seeded):
    tokens = _login_all(client)
    r = client.post(
        "/api/v1/tickets/9999/survey",
        json={"rating": 5},
        headers=auth_headers(tokens["estudiante"]),
    )
    assert r.status_code == 404


# --- CSAT stats --------------------------------------------------------------

def test_csat_reflects_submitted_surveys(client, seeded):
    tokens = _login_all(client)
    t1 = _create_and_close(client, tokens, seeded["users"]["tecnico"].id)
    t2 = _create_and_close(client, tokens, seeded["users"]["tecnico"].id)
    client.post(
        f"/api/v1/tickets/{t1['id']}/survey",
        json={"rating": 5},
        headers=auth_headers(tokens["estudiante"]),
    )
    client.post(
        f"/api/v1/tickets/{t2['id']}/survey",
        json={"rating": 3},
        headers=auth_headers(tokens["estudiante"]),
    )

    r = client.get("/api/v1/stats/summary", headers=auth_headers(tokens["supervisor"]))
    body = r.json()
    assert "csat" in body
    assert body["csat"]["avg_rating"] == 4.0
    assert body["csat"]["response_count"] == 2
    assert body["csat"]["response_rate_percent"] == 100.0
    assert body["csat"]["distribution"]["5"] == 1
    assert body["csat"]["distribution"]["3"] == 1


def test_csat_null_when_no_surveys(client, seeded):
    tokens = _login_all(client)
    r = client.get("/api/v1/stats/summary", headers=auth_headers(tokens["supervisor"]))
    csat = r.json()["csat"]
    assert csat["avg_rating"] is None
    assert csat["response_count"] == 0
    assert csat["response_rate_percent"] is None


def test_csat_response_rate_partial(client, seeded):
    tokens = _login_all(client)
    t1 = _create_and_close(client, tokens, seeded["users"]["tecnico"].id)
    _ = _create_and_close(client, tokens, seeded["users"]["tecnico"].id)
    client.post(
        f"/api/v1/tickets/{t1['id']}/survey",
        json={"rating": 4},
        headers=auth_headers(tokens["estudiante"]),
    )
    r = client.get("/api/v1/stats/summary", headers=auth_headers(tokens["supervisor"]))
    assert r.json()["csat"]["response_rate_percent"] == 50.0
