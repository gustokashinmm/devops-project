# devops-project

DevOps course project: REST API (online shop) with CI/CD, Docker, monitoring.

## Status

🚧 In development

## Stack

- Python 3.12 + FastAPI + Uvicorn
- Docker + Docker Compose
- GitHub Actions (CI) + GHCR
- Prometheus + Grafana
- k6 (load testing)

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
