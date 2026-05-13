from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

app = FastAPI(
    title="Smart Building Operations OS",
    version="1.0.0",
    description="Smart Building Operations OS API for multi-building enterprise operations.",
)
SLA_HOURS_BY_PRIORITY = {"high": 4, "medium": 24, "low": 48}
SERVICE_PREDICTION_MULTIPLIER = 30
QR_TICKET_PREFIX = "QR:"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Building(BaseModel):
    id: int
    name: str
    address: str


class Floor(BaseModel):
    id: int
    building_id: int
    name: str


class Room(BaseModel):
    id: int
    floor_id: int
    name: str


class UtilityReading(BaseModel):
    id: int
    building_id: int
    water_liters: float
    electricity_kwh: float
    recorded_at: datetime = Field(default_factory=utc_now)


class MaintenanceTicketCreate(BaseModel):
    building_id: int
    room_id: int
    title: str
    description: str
    priority: Literal["low", "medium", "high"] = "medium"


class MaintenanceTicket(BaseModel):
    id: int
    building_id: int
    room_id: int
    title: str
    description: str
    priority: Literal["low", "medium", "high"]
    status: Literal["open", "assigned", "in_progress", "done"] = "open"
    created_at: datetime = Field(default_factory=utc_now)
    sla_due_at: datetime
    technician_id: int | None = None


class QRMaintenanceRequest(BaseModel):
    qr_code: str
    building_id: int | None = None
    room_id: int
    title: str
    description: str


class AssignTechnicianRequest(BaseModel):
    technician_id: int


class PreventiveTask(BaseModel):
    id: int
    building_id: int
    asset_id: int
    task: str
    next_due: datetime


class SparePart(BaseModel):
    id: int
    name: str
    quantity: int
    reorder_level: int


class StaffMember(BaseModel):
    id: int
    name: str
    role: Literal["admin", "manager", "technician", "security", "staff"]


class Vendor(BaseModel):
    id: int
    name: str
    service_type: str


class SecurityIncident(BaseModel):
    id: int
    building_id: int
    severity: Literal["low", "medium", "high"]
    description: str
    created_at: datetime = Field(default_factory=utc_now)


class Visitor(BaseModel):
    id: int
    building_id: int
    name: str
    host_staff_id: int
    check_in_at: datetime = Field(default_factory=utc_now)


class Asset(BaseModel):
    id: int
    building_id: int
    name: str
    category: str
    health_score: float


class ChatRequest(BaseModel):
    question: str


buildings = [
    Building(id=1, name="HQ Tower", address="Downtown"),
    Building(id=2, name="Factory Annex", address="Industrial Zone"),
]
floors = [
    Floor(id=1, building_id=1, name="Floor 1"),
    Floor(id=2, building_id=1, name="Floor 2"),
    Floor(id=3, building_id=2, name="Ground Floor"),
]
rooms = [
    Room(id=1, floor_id=1, name="101"),
    Room(id=2, floor_id=1, name="102"),
    Room(id=3, floor_id=3, name="A1"),
]
utility_readings = [
    UtilityReading(id=1, building_id=1, water_liters=8500, electricity_kwh=3200),
    UtilityReading(id=2, building_id=2, water_liters=12000, electricity_kwh=5100),
]
staff = [
    StaffMember(id=1, name="Amina Rahman", role="manager"),
    StaffMember(id=2, name="Reza Khan", role="technician"),
    StaffMember(id=3, name="Sadia Noor", role="security"),
]
vendors = [Vendor(id=1, name="CoolAir HVAC", service_type="HVAC")]
incidents: list[SecurityIncident] = []
visitors: list[Visitor] = []
assets = [
    Asset(id=1, building_id=1, name="Chiller Unit", category="HVAC", health_score=0.86),
    Asset(id=2, building_id=2, name="Pump P-9", category="Water", health_score=0.74),
]
spare_parts = [
    SparePart(id=1, name="HVAC Filter", quantity=25, reorder_level=10),
    SparePart(id=2, name="Bearing Set", quantity=4, reorder_level=5),
]
preventive_tasks = [
    PreventiveTask(
        id=1,
        building_id=1,
        asset_id=1,
        task="Replace filter cartridge",
        next_due=utc_now() + timedelta(days=14),
    )
]
maintenance_tickets: list[MaintenanceTicket] = []
notifications: list[dict] = []


def require_role(allowed: set[str]):
    def _dep(x_role: str = Header(default="staff", alias="X-Role")) -> str:
        if x_role not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient role permissions")
        return x_role

    return _dep


def derive_building_id_from_qr(qr_code: str) -> int | None:
    if qr_code.startswith("B") and "-" in qr_code:
        candidate = qr_code.split("-", 1)[0].removeprefix("B")
        if candidate.isdigit():
            return int(candidate)
    return None


def resolve_building_context(payload: QRMaintenanceRequest) -> int:
    building_id = payload.building_id or derive_building_id_from_qr(payload.qr_code)
    if building_id is None:
        raise HTTPException(
            status_code=400,
            detail="Unable to derive building ID from QR code; provide building_id explicitly.",
        )
    return building_id


@app.get("/", response_class=HTMLResponse)
def frontend_dashboard() -> str:
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Smart Building Operations OS</title>
  <style>
    :root { --bg:#0e1117; --card:#161b22; --text:#f0f6fc; --muted:#8b949e; --accent:#2f81f7; }
    body.light { --bg:#f6f8fa; --card:#fff; --text:#1f2328; --muted:#57606a; --accent:#0969da; }
    body { margin:0; font-family:Inter,system-ui,sans-serif; background:var(--bg); color:var(--text); }
    .wrap { max-width:1200px; margin:0 auto; padding:16px; }
    .top { display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap; }
    .btn { border:1px solid var(--accent); color:var(--text); background:transparent; padding:8px 12px; border-radius:8px; cursor:pointer; }
    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px; margin-top:16px; }
    .card { background:var(--card); border-radius:10px; padding:12px; border:1px solid rgba(127,127,127,.18); }
    .label { color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.06em; }
    .value { font-size:22px; font-weight:700; margin-top:6px; }
    .activity { margin-top:16px; }
    ul { margin:8px 0 0; padding-left:18px; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <div>
        <h1 style="margin:0">Building Operations Dashboard</h1>
        <p style="margin:4px 0 0;color:var(--muted)">Live operations for multi-building environments</p>
      </div>
      <button id="theme" class="btn">Toggle Dark/Light</button>
    </div>

    <div id="cards" class="grid"></div>

    <div class="card activity">
      <div class="label">Live Activity Panel</div>
      <ul id="activity"></ul>
    </div>
  </div>

  <script>
    const body = document.body;
    document.getElementById('theme').onclick = () => body.classList.toggle('light');

    async function load() {
      const r = await fetch('/api/dashboard');
      const d = await r.json();
      const cards = [
        ['Buildings', d.buildings],
        ['Open Tickets', d.maintenance.open_tickets],
        ['Technicians', d.staff.technicians],
        ['Water (L)', d.utilities.total_water_liters],
        ['Electricity (kWh)', d.utilities.total_electricity_kwh],
        ['AI Alerts', d.ai_anomaly_alerts.length],
      ];
      const c = document.getElementById('cards');
      c.innerHTML = cards.map(([k,v]) => `<div class="card"><div class="label">${k}</div><div class="value">${v}</div></div>`).join('');

      const a = document.getElementById('activity');
      a.innerHTML = d.live_activity.map(i => `<li>${i}</li>`).join('');
    }
    load();
  </script>
</body>
</html>
    """


@app.get("/api/buildings", response_model=list[Building])
def list_buildings() -> list[Building]:
    return buildings


@app.get("/api/buildings/{building_id}/floors", response_model=list[Floor])
def list_floors(building_id: int) -> list[Floor]:
    return [f for f in floors if f.building_id == building_id]


@app.get("/api/floors/{floor_id}/rooms", response_model=list[Room])
def list_rooms(floor_id: int) -> list[Room]:
    return [r for r in rooms if r.floor_id == floor_id]


@app.get("/api/utilities", response_model=list[UtilityReading])
def list_utilities() -> list[UtilityReading]:
    return utility_readings


@app.get("/api/staff", response_model=list[StaffMember])
def list_staff() -> list[StaffMember]:
    return staff


@app.get("/api/vendors", response_model=list[Vendor])
def list_vendors() -> list[Vendor]:
    return vendors


@app.get("/api/security/incidents", response_model=list[SecurityIncident])
def list_incidents() -> list[SecurityIncident]:
    return incidents


@app.post("/api/security/incidents", response_model=SecurityIncident)
def create_incident(
    payload: SecurityIncident,
    _: str = Depends(require_role({"admin", "security", "manager"})),
) -> SecurityIncident:
    incidents.append(payload)
    notifications.append({"type": "security_incident", "message": payload.description})
    return payload


@app.get("/api/visitors", response_model=list[Visitor])
def list_visitors() -> list[Visitor]:
    return visitors


@app.post("/api/visitors", response_model=Visitor)
def register_visitor(
    payload: Visitor,
    _: str = Depends(require_role({"admin", "security", "manager"})),
) -> Visitor:
    visitors.append(payload)
    notifications.append({"type": "visitor_registered", "message": f"Visitor {payload.name} checked in"})
    return payload


@app.get("/api/assets", response_model=list[Asset])
def list_assets() -> list[Asset]:
    return assets


@app.post("/api/maintenance/tickets", response_model=MaintenanceTicket)
def create_ticket(
    payload: MaintenanceTicketCreate,
    _: str = Depends(require_role({"admin", "manager", "staff"})),
) -> MaintenanceTicket:
    ticket = MaintenanceTicket(
        id=len(maintenance_tickets) + 1,
        building_id=payload.building_id,
        room_id=payload.room_id,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        sla_due_at=utc_now() + timedelta(hours=SLA_HOURS_BY_PRIORITY.get(payload.priority, 24)),
    )
    maintenance_tickets.append(ticket)
    notifications.append({"type": "ticket_created", "message": f"Ticket #{ticket.id}: {ticket.title}"})
    return ticket


@app.post("/api/maintenance/qr-request", response_model=MaintenanceTicket)
def qr_maintenance_request(payload: QRMaintenanceRequest) -> MaintenanceTicket:
    building_id = resolve_building_context(payload)
    return create_ticket(
        MaintenanceTicketCreate(
            building_id=building_id,
            room_id=payload.room_id,
            title=f"{QR_TICKET_PREFIX}{payload.title}",
            description=f"{payload.description} (source={payload.qr_code})",
            priority="medium",
        ),
        "staff",
    )


@app.post("/api/maintenance/tickets/{ticket_id}/assign", response_model=MaintenanceTicket)
def assign_technician(
    ticket_id: int,
    payload: AssignTechnicianRequest,
    _: str = Depends(require_role({"admin", "manager"})),
) -> MaintenanceTicket:
    for i, ticket in enumerate(maintenance_tickets):
        if ticket.id == ticket_id:
            updated = ticket.model_copy(update={"technician_id": payload.technician_id, "status": "assigned"})
            maintenance_tickets[i] = updated
            notifications.append(
                {
                    "type": "technician_assignment",
                    "message": f"Ticket #{ticket_id} assigned to technician {payload.technician_id}",
                }
            )
            return updated
    raise HTTPException(status_code=404, detail="Ticket not found")


@app.get("/api/maintenance/board")
def maintenance_board() -> dict:
    buckets: dict[str, list[dict]] = {"open": [], "assigned": [], "in_progress": [], "done": []}
    now = utc_now()
    for ticket in maintenance_tickets:
        item = ticket.model_dump()
        item["sla_breached"] = ticket.sla_due_at < now and ticket.status != "done"
        buckets[ticket.status].append(item)
    return buckets


@app.get("/api/maintenance/preventive", response_model=list[PreventiveTask])
def preventive_scheduler() -> list[PreventiveTask]:
    return preventive_tasks


@app.get("/api/inventory/spare-parts", response_model=list[SparePart])
def list_spare_parts() -> list[SparePart]:
    return spare_parts


@app.get("/api/notifications")
def list_notifications() -> list[dict]:
    return notifications[-50:]


@app.get("/api/analytics/buildings/{building_id}")
def building_analytics(building_id: int) -> dict:
    building_tickets = [t for t in maintenance_tickets if t.building_id == building_id]
    readings = [r for r in utility_readings if r.building_id == building_id]
    total_water = 0.0
    total_electricity = 0.0
    for reading in readings:
        total_water += reading.water_liters
        total_electricity += reading.electricity_kwh
    return {
        "building_id": building_id,
        "ticket_count": len(building_tickets),
        "avg_water_liters": (total_water / len(readings)) if readings else 0,
        "avg_electricity_kwh": (total_electricity / len(readings)) if readings else 0,
    }


@app.get("/api/ai/anomaly-alerts")
def ai_anomaly_alerts() -> list[dict]:
    alerts = []
    for reading in utility_readings:
        if reading.electricity_kwh > 5000:
            alerts.append(
                {
                    "building_id": reading.building_id,
                    "type": "electricity_spike",
                    "message": "Electricity usage exceeded forecast threshold",
                }
            )
    return alerts


@app.get("/api/ai/predictive-maintenance")
def predictive_maintenance() -> list[dict]:
    return [
        {
            "asset_id": a.id,
            "asset_name": a.name,
            "predicted_days_to_service": max(1, int((1 - a.health_score) * SERVICE_PREDICTION_MULTIPLIER)),
        }
        for a in assets
    ]


@app.get("/api/ai/utility-forecast")
def utility_forecast() -> dict:
    return {
        "next_month_water_liters": round(sum(r.water_liters for r in utility_readings) * 1.04, 2),
        "next_month_electricity_kwh": round(sum(r.electricity_kwh for r in utility_readings) * 1.03, 2),
    }


@app.get("/api/ai/equipment-failure-prediction")
def equipment_failure_prediction() -> list[dict]:
    return [
        {
            "asset_id": a.id,
            "failure_risk": round(1 - a.health_score, 2),
            "recommendation": "Schedule inspection" if a.health_score < 0.8 else "Continue monitoring",
        }
        for a in assets
    ]


@app.post("/api/ai/chatbot")
def ai_chatbot(payload: ChatRequest) -> dict:
    q = payload.question.lower()
    if "ticket" in q:
        answer = f"There are currently {len([t for t in maintenance_tickets if t.status != 'done'])} active tickets."
    elif "utility" in q or "electricity" in q or "water" in q:
        forecast = utility_forecast()
        answer = (
            "Forecasted next month usage: "
            f"{forecast['next_month_water_liters']}L water and {forecast['next_month_electricity_kwh']} kWh electricity."
        )
    else:
        answer = "I can help with maintenance, utility, and incident summaries."
    return {"answer": answer}


@app.get("/api/reports/buildings/{building_id}.pdf")
def export_building_report(building_id: int) -> Response:
    data = building_analytics(building_id)
    content = (
        "%PDF-1.4\n"
        "1 0 obj<<>>endobj\n"
        "2 0 obj<< /Length 44 >>stream\n"
        f"Building {building_id} report tickets={data['ticket_count']}\n"
        "endstream endobj\n"
        "trailer<<>>\n%%EOF\n"
    ).encode("utf-8")
    return Response(content=BytesIO(content).getvalue(), media_type="application/pdf")


@app.get("/api/dashboard")
def dashboard() -> dict:
    total_water = sum(r.water_liters for r in utility_readings)
    total_electricity = sum(r.electricity_kwh for r in utility_readings)
    open_tickets = len([t for t in maintenance_tickets if t.status != "done"])
    return {
        "buildings": len(buildings),
        "maintenance": {
            "open_tickets": open_tickets,
            "board_url": "/api/maintenance/board",
            "preventive_tasks": len(preventive_tasks),
        },
        "staff": {"total": len(staff), "technicians": len([s for s in staff if s.role == "technician"])},
        "utilities": {
            "total_water_liters": total_water,
            "total_electricity_kwh": total_electricity,
        },
        "ai_anomaly_alerts": ai_anomaly_alerts(),
        "live_activity": [
            "Ticket board updated in real-time endpoint",
            "Preventive maintenance schedule refreshed",
            "Utility usage monitor active",
            "AI anomaly scanner completed",
        ],
    }
