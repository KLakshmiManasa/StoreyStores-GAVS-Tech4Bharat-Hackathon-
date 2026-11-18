import os
import json
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from backend.database import (
    init_db,
    get_all_inventory,
    get_inventory_item,
    update_inventory_stock,
    add_inventory_stock,
    get_all_khata,
    add_khata_entry,
    get_config_val,
    set_config_val,
    get_all_traces,
    clear_traces,
    log_agent_trace
)
from backend.seed import seed_database
from backend.agent_tools import (
    get_shop_state,
    forecast_demand,
    detect_expiry_and_dead_stock,
    optimize_order,
    parse_voice_khata_input
)
from backend.agent_orchestrator import orchestrator
from backend.models import (
    VoiceInputRequest,
    OrderApprovalRequest,
    SimulateStockoutRequest
)

app = FastAPI(
    title="KiranaCopilot - StoreyStores",
    description="Agentic AI-Powered Kirana Stock Management System",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

@app.on_event("startup")
def startup_event():
    init_db()
    # Check if database is populated, if not seed it
    inv = get_all_inventory()
    if not inv:
        seed_database()

@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>KiranaCopilot Frontend Loading...</h1>")

@app.get("/api/state")
def get_full_state():
    inventory = get_all_inventory()
    khata = get_all_khata()
    festival_mode = get_config_val("festival_mode", False)
    budget = get_config_val("cash_budget", 20000.0)
    agent_mode = get_config_val("agent_mode", "mock")
    active_order = get_config_val("active_order", None)
    
    # Calculate live forecasts and metrics
    forecast = forecast_demand(festival_mode)
    expiry_dead = detect_expiry_and_dead_stock()
    
    # Merge forecast metrics into inventory items
    forecast_map = {f["sku"]: f for f in forecast["forecasts"]}
    for item in inventory:
        f = forecast_map.get(item["sku"], {})
        item["projected_daily_demand"] = f.get("projected_daily_demand", item["daily_avg_sales"])
        item["days_of_stock_left"] = f.get("days_of_stock_left", 999.0)
        item["stockout_before_distributor"] = f.get("stockout_before_distributor", False)
        item["shortfall_units"] = f.get("shortfall_units", 0.0)
        
    return {
        "shop_name": get_config_val("shop_name", "StoreyStores"),
        "cash_budget": budget,
        "festival_mode": festival_mode,
        "agent_mode": agent_mode,
        "next_distributor_days": get_config_val("next_distributor_days", 3),
        "inventory": inventory,
        "khata": khata,
        "active_order": active_order,
        "kpis": {
            "cash_budget": budget,
            "at_risk_expiry_value": expiry_dead["total_at_risk_expiry_value"],
            "blocked_dead_capital": expiry_dead["total_blocked_dead_capital"],
            "critical_stockouts_count": forecast["critical_stockouts_count"],
            "near_expiry_count": expiry_dead["near_expiry_count"],
            "dead_stock_count": expiry_dead["dead_stock_count"]
        },
        "forecast": forecast,
        "expiry_dead": expiry_dead
    }

@app.post("/api/festival-mode")
def toggle_festival_mode(data: Dict[str, bool]):
    enabled = data.get("enabled", False)
    set_config_val("festival_mode", enabled)
    
    log_agent_trace(
        stage="OBSERVE",
        message=f"Festival Surge Mode {'ENABLED (Diwali / Weekend +80% multipliers active)' if enabled else 'DISABLED (Standard baseline demand)'}.",
        tool_name="toggle_festival_mode",
        tool_args={"festival_mode": enabled},
        tool_result={"multiplier_applied": enabled},
        status="info"
    )
    return {"festival_mode": enabled}

@app.post("/api/budget")
def update_budget(data: Dict[str, float]):
    budget = float(data.get("budget", 20000.0))
    set_config_val("cash_budget", budget)
    log_agent_trace(
        stage="OBSERVE",
        message=f"Cash Budget adjusted by shop owner to ₹{budget:,}.",
        tool_name="update_budget",
        tool_args={"new_budget": budget},
        status="info"
    )
    return {"cash_budget": budget}

@app.post("/api/mode")
def update_agent_mode(data: Dict[str, str]):
    mode = data.get("mode", "mock")
    set_config_val("agent_mode", mode)
    return {"agent_mode": mode}

@app.post("/api/agent/run-audit")
def run_agent_audit():
    result = orchestrator.execute_full_cycle()
    return result

@app.post("/api/agent/approve-order")
def approve_order(req: OrderApprovalRequest):
    if req.action == "reject":
        return orchestrator.reject_order(req.order_id)
    return orchestrator.approve_and_send_order(req.order_id, req.custom_items)

@app.post("/api/agent/simulate-stockout")
def simulate_distributor_stockout(req: SimulateStockoutRequest):
    return orchestrator.simulate_distributor_stockout(req.out_of_stock_sku, req.supplier_note)

@app.post("/api/voice/process")
def process_voice_input(req: VoiceInputRequest):
    if not req.transcript or not req.transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript cannot be empty.")
    result = parse_voice_khata_input(req.transcript)
    return result

@app.get("/api/ocr/sample-bill")
def get_sample_bill():
    """
    Returns pre-formatted sample distributor invoice from Balaji Wholesale Distributors
    along with extracted line items and visual metadata.
    """
    return {
        "distributor_name": "Balaji Wholesale Distributors Pvt Ltd",
        "gstin": "29AABCB1234F1Z5",
        "invoice_number": "BWD-2026-9042",
        "date": "18-Nov-2026",
        "billed_to": "StoreyStores (Kirana), Main Bazaar",
        "items": [
            {
                "sku": "SKU01",
                "item_name": "Parle-G Biscuit (₹5 Pack)",
                "quantity": 50,
                "unit": "packets",
                "unit_cost": 4.15,
                "total": 207.50,
                "expiry_days": 180
            },
            {
                "sku": "SKU02",
                "item_name": "Sunflower Cooking Oil (1L Pouch)",
                "quantity": 20,
                "unit": "pouches",
                "unit_cost": 134.50,
                "total": 2690.00,
                "expiry_days": 150
            },
            {
                "sku": "SKU05",
                "item_name": "Toor Dal (1kg Packet)",
                "quantity": 15,
                "unit": "packets",
                "unit_cost": 142.00,
                "total": 2130.00,
                "expiry_days": 180
            }
        ],
        "subtotal": 5027.50,
        "gst_amount": 251.38,
        "grand_total": 5278.88,
        "confidence_score": 0.985
    }

@app.post("/api/ocr/confirm-inward")
def confirm_bill_inward(data: Dict[str, Any]):
    """
    Confirms bill reception: updates inventory current stock,
    deducts bill total from cash budget, and records trace.
    """
    items = data.get("items", [])
    grand_total = float(data.get("grand_total", 0.0))
    inv_num = data.get("invoice_number", "BWD-INWARD")
    
    current_budget = get_config_val("cash_budget", 20000.0)
    new_budget = max(0.0, round(current_budget - grand_total, 2))
    set_config_val("cash_budget", new_budget)
    
    updates = []
    for it in items:
        sku = it.get("sku")
        qty = float(it.get("quantity", 0))
        if sku:
            add_inventory_stock(sku, qty)
            updates.append(f"{sku}: +{qty}")
            
    log_agent_trace(
        stage="ACTION",
        message=f"Distributor Inward Confirmed for Invoice #{inv_num}. Stock credited ({', '.join(updates)}), ₹{grand_total:,} deducted from cash budget.",
        tool_name="confirm_bill_inward",
        tool_args={"invoice_number": inv_num, "grand_total": grand_total, "items_count": len(items)},
        tool_result={"new_budget": new_budget, "updates": updates},
        status="success"
    )
    
    return {
        "status": "SUCCESS",
        "new_budget": new_budget,
        "updated_items": updates
    }

@app.get("/api/traces")
def get_traces():
    return {"traces": get_all_traces(60)}

@app.post("/api/traces/clear")
def clear_all_traces():
    clear_traces()
    return {"status": "cleared"}

@app.post("/api/reset-demo")
def reset_demo_state():
    seed_database()
    return {"status": "reset_successful", "message": "StoreyStores reset to pristine initial state!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
