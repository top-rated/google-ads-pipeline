import os
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config_loader import load_config, load_campaigns
from monitor import run_monitor_report
from optimize import run_optimization

app = FastAPI(
    title="Google Ads Pipeline API",
    description="Professional API for monitoring and optimizing Google Ads campaigns",
    version="1.0.0"
)

LOG_DIR = Path(__file__).parent / "logs"
scheduler = AsyncIOScheduler()

# --- Models ---

class MonitorReport(BaseModel):
    timestamp: str
    account_id: str
    period_days: int
    ad_approvals: dict
    campaign_performance: dict
    top_keywords: List[dict]
    top_search_terms: List[dict]
    anomalies: List[str]

class OptimizationResult(BaseModel):
    timestamp: str
    account_id: str
    mode: str
    days_since_launch: int
    changes: List[dict]
    recommendations: List[str]
    errors: List[str]
    log_file: Optional[str] = None

# --- Background Tasks ---

def scheduled_monitor():
    print(f"[{datetime.now()}] Running scheduled monitor...")
    run_monitor_report(days=1)

def scheduled_optimize():
    print(f"[{datetime.now()}] Running scheduled optimization...")
    run_optimization(dry_run=False, lookback_days=14)

@app.on_event("startup")
async def startup_event():
    # Schedule monitor every day at 08:00
    scheduler.add_job(scheduled_monitor, 'cron', hour=8, minute=0)
    # Schedule optimize every Monday at 09:00
    scheduler.add_job(scheduled_optimize, 'cron', day_of_week='mon', hour=9, minute=0)
    scheduler.start()

# --- Endpoints ---

@app.get("/health")
async def health_check():
    try:
        config = load_config()
        return {
            "status": "healthy",
            "account_id": config.get("customer_id"),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/monitor", response_model=MonitorReport)
async def trigger_monitor(days: int = 1):
    """Trigger a manual monitoring run and return the report."""
    try:
        report = run_monitor_report(days=days)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/optimize", response_model=OptimizationResult)
async def trigger_optimize(dry_run: bool = True, days: int = 14):
    """Trigger a manual optimization run."""
    try:
        result = run_optimization(dry_run=dry_run, lookback_days=days)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/campaigns")
async def list_campaigns():
    """List campaigns currently being managed."""
    try:
        allowed = load_campaigns()
        return {"managed_campaigns": list(allowed) if allowed else "ALL"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/logs")
async def list_logs(limit: int = 10):
    """List recent optimization logs."""
    if not LOG_DIR.exists():
        return {"logs": []}
    
    logs = sorted(LOG_DIR.glob("optimize_*.json"), key=os.path.getmtime, reverse=True)
    result = []
    for log_path in logs[:limit]:
        try:
            data = json.loads(log_path.read_text())
            result.append({
                "filename": log_path.name,
                "timestamp": data.get("timestamp"),
                "mode": data.get("mode"),
                "changes_count": len(data.get("changes", []))
            })
        except:
            continue
    return {"logs": result}

@app.get("/logs/{filename}")
async def get_log_detail(filename: str):
    """Retrieve details of a specific log file."""
    log_path = LOG_DIR / filename
    if not log_path.exists():
        raise HTTPException(status_code=44, detail="Log file not found")
    try:
        return json.loads(log_path.read_text())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
