# building-ops-os

Smart Building Operations OS platform with FastAPI backend, enterprise dashboard frontend, and Dockerized runtime services.

## Highlights

### Core modules
- Building dashboard
- Floor management
- Room management
- Utility monitoring
- Maintenance ticketing
- Staff management
- Vendor management
- Security incident logs
- Visitor registration
- Asset tracking

### Key features
- QR-based maintenance requests
- Real-time maintenance board
- Technician assignment
- SLA tracking
- Preventive maintenance scheduler
- Inventory and spare parts
- Building analytics
- Water and electricity usage tracking
- AI anomaly alerts

### AI features
- Predictive maintenance
- Utility consumption forecasting
- AI chatbot for staff support
- Equipment failure prediction

### Platform
- FastAPI backend (`/docs` and `/redoc` API documentation)
- Modern responsive dashboard (`/`) with dark/light mode and live activity panel
- Docker + PostgreSQL + Redis stack (`docker-compose.yml`)
- Multi-building support, role-based access checks, notification stream, PDF report export endpoint

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Run tests:

```bash
pytest -q
```

Run with Docker:

```bash
docker compose up --build
```
