"""Tests para SLA policies, cálculo de dues, compliance y endpoints (Iteración 4)."""
from datetime import datetime, timedelta, timezone

from app.models.sla_policy import SLAPolicy
from app.models.ticket import Ticket
from app.services.sla import compute_sla_status
from tests.conftest import login, auth_headers


DEFAULTS = {
    "critica": (15, 120),
    "alta": (60, 480),
    "media": (240, 1440),
    "baja": (480, 2880),
}


def _seed_policies(db_session):
    for pri, (resp, resol) in DEFAULTS.items():
        db_session.merge(SLAPolicy(priority=pri, response_minutes=resp, resolution_minutes=resol))
    db_session.commit()


def _create_ticket(client, token, priority="media"):
    r = client.post(
        "/api/v1/tickets",
        json={"title": "T", "description": "d", "priority": priority},
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
    }


# --- Cálculo de dues al crear -------------------------------------------------

def test_create_ticket_sets_dues_from_policy(client, seeded, db_session):
    _seed_policies(db_session)
    tokens = _login_all(client)
    t = _create_ticket(client, tokens["estudiante"], priority="alta")

    assert t["sla_response_due_at"] is not None
    assert t["sla_resolution_due_at"] is not None
    created = datetime.fromisoformat(t["created_at"])
    response_due = datetime.fromisoformat(t["sla_response_due_at"])
    resolution_due = datetime.fromisoformat(t["sla_resolution_due_at"])
    assert abs((response_due - created).total_seconds() / 60 - 60) < 1
    assert abs((resolution_due - created).total_seconds() / 60 - 480) < 1


def test_ticket_without_policy_leaves_dues_null(client, seeded, db_session):
    # NO seedeamos políticas
    tokens = _login_all(client)
    t = _create_ticket(client, tokens["estudiante"], priority="media")
    assert t["sla_response_due_at"] is None
    assert t["sla_resolution_due_at"] is None
    assert t["sla_status"] == "on_track"


def test_priority_change_recomputes_dues(client, seeded, db_session):
    _seed_policies(db_session)
    tokens = _login_all(client)
    t = _create_ticket(client, tokens["estudiante"], priority="baja")
    old_resolution_due = datetime.fromisoformat(t["sla_resolution_due_at"])

    r = client.patch(
        f"/api/v1/tickets/{t['id']}",
        json={"priority": "critica"},
        headers=auth_headers(tokens["admin"]),
    )
    body = r.json()
    new_resolution_due = datetime.fromisoformat(body["sla_resolution_due_at"])
    # baja=2880min, critica=120min → nuevo due debe ser mucho antes
    assert (old_resolution_due - new_resolution_due).total_seconds() > 60 * 100


# --- compute_sla_status unit -------------------------------------------------

def _mk_ticket(**overrides):
    t = Ticket(
        title="x",
        description="x",
        priority="media",
        status="CREADO",
        reporter_id=1,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    for k, v in overrides.items():
        setattr(t, k, v)
    return t


def test_sla_status_on_track_when_lots_of_time_left():
    now = datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc)
    t = _mk_ticket(
        sla_resolution_due_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    assert compute_sla_status(t, now) == "on_track"


def test_sla_status_at_risk_when_less_than_20_percent_remaining():
    now = datetime(2026, 1, 1, 20, 0, tzinfo=timezone.utc)  # 20h vividas de 24
    t = _mk_ticket(
        sla_resolution_due_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    assert compute_sla_status(t, now) == "at_risk"


def test_sla_status_breached_when_past_due_and_not_resolved():
    now = datetime(2026, 1, 3, tzinfo=timezone.utc)
    t = _mk_ticket(
        sla_resolution_due_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    assert compute_sla_status(t, now) == "breached"


def test_sla_status_met_when_resolved_before_due():
    now = datetime(2026, 1, 3, tzinfo=timezone.utc)
    t = _mk_ticket(
        sla_resolution_due_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        resolved_at=datetime(2026, 1, 1, 12, tzinfo=timezone.utc),
    )
    assert compute_sla_status(t, now) == "met"


def test_sla_status_breached_when_resolved_after_due():
    now = datetime(2026, 1, 3, tzinfo=timezone.utc)
    t = _mk_ticket(
        sla_resolution_due_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        resolved_at=datetime(2026, 1, 2, 6, tzinfo=timezone.utc),
    )
    assert compute_sla_status(t, now) == "breached"


# --- Endpoints /sla-policies -------------------------------------------------

def test_authenticated_user_can_list_policies(client, seeded, db_session):
    _seed_policies(db_session)
    tokens = _login_all(client)
    r = client.get("/api/v1/sla-policies", headers=auth_headers(tokens["estudiante"]))
    assert r.status_code == 200
    rows = r.json()
    assert {p["priority"] for p in rows} == set(DEFAULTS.keys())


def test_only_admin_can_patch_policy(client, seeded, db_session):
    _seed_policies(db_session)
    tokens = _login_all(client)
    for user_token in (tokens["supervisor"], tokens["tecnico"], tokens["estudiante"]):
        r = client.patch(
            "/api/v1/sla-policies/critica",
            json={"response_minutes": 5, "resolution_minutes": 60},
            headers=auth_headers(user_token),
        )
        assert r.status_code == 403


def test_admin_patch_recomputes_open_tickets(client, seeded, db_session):
    _seed_policies(db_session)
    tokens = _login_all(client)
    t = _create_ticket(client, tokens["estudiante"], priority="critica")
    old_due = datetime.fromisoformat(t["sla_resolution_due_at"])

    r = client.patch(
        "/api/v1/sla-policies/critica",
        json={"response_minutes": 5, "resolution_minutes": 30},
        headers=auth_headers(tokens["admin"]),
    )
    assert r.status_code == 200

    # Consultar el ticket para ver el nuevo due
    r2 = client.get(f"/api/v1/tickets/{t['id']}", headers=auth_headers(tokens["admin"]))
    new_due = datetime.fromisoformat(r2.json()["sla_resolution_due_at"])
    assert (old_due - new_due).total_seconds() > 60  # más ajustado ahora


def test_admin_patch_rejects_zero_or_negative(client, seeded, db_session):
    _seed_policies(db_session)
    tokens = _login_all(client)
    r = client.patch(
        "/api/v1/sla-policies/alta",
        json={"response_minutes": 0, "resolution_minutes": 30},
        headers=auth_headers(tokens["admin"]),
    )
    assert r.status_code == 422


# --- Timestamps de ciclo -----------------------------------------------------

def test_first_assigned_at_set_on_asignacion(client, seeded, db_session):
    _seed_policies(db_session)
    tokens = _login_all(client)
    t = _create_ticket(client, tokens["estudiante"])
    r = client.patch(
        f"/api/v1/tickets/{t['id']}/asignacion",
        json={"tecnico_id": seeded["users"]["tecnico"].id},
        headers=auth_headers(tokens["supervisor"]),
    )
    assert r.status_code == 200
    assert r.json()["first_assigned_at"] is not None


def test_resolved_at_set_on_transition_to_resuelto(client, seeded, db_session):
    _seed_policies(db_session)
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
    r = client.patch(
        f"/api/v1/tickets/{t['id']}/estado",
        json={"status": "RESUELTO"},
        headers=auth_headers(tokens["tecnico"]),
    )
    assert r.status_code == 200
    assert r.json()["resolved_at"] is not None


# --- Stats extendidas --------------------------------------------------------

def test_summary_includes_sla_and_averages(client, seeded, db_session):
    _seed_policies(db_session)
    tokens = _login_all(client)
    _create_ticket(client, tokens["estudiante"])
    r = client.get("/api/v1/stats/summary", headers=auth_headers(tokens["supervisor"]))
    assert r.status_code == 200
    body = r.json()
    assert "sla" in body
    assert set(body["sla"].keys()) >= {"compliance_percent", "on_track", "at_risk", "breached", "met"}
    assert "avg_response_minutes" in body
    assert "avg_resolution_minutes" in body


def test_by_technician_includes_workload(client, seeded, db_session):
    _seed_policies(db_session)
    tokens = _login_all(client)
    t = _create_ticket(client, tokens["estudiante"])
    client.patch(
        f"/api/v1/tickets/{t['id']}/asignacion",
        json={"tecnico_id": seeded["users"]["tecnico"].id},
        headers=auth_headers(tokens["supervisor"]),
    )
    r = client.get("/api/v1/stats/by-technician", headers=auth_headers(tokens["supervisor"]))
    assert r.status_code == 200
    rows = r.json()
    tec_row = next(r for r in rows if r["tecnico_id"] == seeded["users"]["tecnico"].id)
    assert tec_row["total"] == 1
    assert tec_row["open"] == 1
    assert tec_row["resolved"] == 0


def test_by_technician_requires_supervisor_or_admin(client, seeded, db_session):
    _seed_policies(db_session)
    tokens = _login_all(client)
    r = client.get("/api/v1/stats/by-technician", headers=auth_headers(tokens["tecnico"]))
    assert r.status_code == 403
