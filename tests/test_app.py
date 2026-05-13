from fastapi.testclient import TestClient

from app.main import app, derive_building_id_from_qr


client = TestClient(app)


def test_dashboard_contains_core_panels():
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    payload = response.json()
    assert payload["buildings"] == 2
    assert "maintenance" in payload
    assert "utilities" in payload
    assert "ai_anomaly_alerts" in payload


def test_qr_maintenance_request_creates_ticket_and_board_view():
    response = client.post(
        "/api/maintenance/qr-request",
        json={
            "qr_code": "B2-ROOM-101-QR",
            "room_id": 1,
            "title": "Leaking tap",
            "description": "Water leak near sink",
        },
    )
    assert response.status_code == 200
    ticket = response.json()
    board = client.get("/api/maintenance/board")
    assert board.status_code == 200
    assert any(item["id"] == ticket["id"] for item in board.json()["open"])
    assert ticket["building_id"] == 2


def test_qr_request_without_building_context_is_rejected():
    response = client.post(
        "/api/maintenance/qr-request",
        json={
            "qr_code": "ROOM-101-QR",
            "room_id": 1,
            "title": "Leaking tap",
            "description": "Water leak near sink",
        },
    )
    assert response.status_code == 400


def test_manager_can_assign_technician_but_staff_cannot():
    ticket_response = client.post(
        "/api/maintenance/tickets",
        json={
            "building_id": 1,
            "room_id": 1,
            "title": "AC issue",
            "description": "AC not cooling",
            "priority": "high",
        },
        headers={"X-Role": "staff"},
    )
    ticket_id = ticket_response.json()["id"]

    denied = client.post(
        f"/api/maintenance/tickets/{ticket_id}/assign",
        json={"technician_id": 2},
        headers={"X-Role": "staff"},
    )
    assert denied.status_code == 403

    allowed = client.post(
        f"/api/maintenance/tickets/{ticket_id}/assign",
        json={"technician_id": 2},
        headers={"X-Role": "manager"},
    )
    assert allowed.status_code == 200
    assert allowed.json()["status"] == "assigned"


def test_pdf_report_export_has_pdf_content_type():
    response = client.get("/api/reports/buildings/1.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")


def test_qr_building_id_parser_handles_valid_and_invalid_codes():
    assert derive_building_id_from_qr("B2-ROOM-100") == 2
    assert derive_building_id_from_qr("BXYZ-ROOM-100") is None
    assert derive_building_id_from_qr("ROOM-100") is None
