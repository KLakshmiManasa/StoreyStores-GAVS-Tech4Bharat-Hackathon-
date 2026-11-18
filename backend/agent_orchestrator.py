import os
import json
import time
from typing import Dict, Any, List, Optional
import httpx

from backend.database import (
    log_agent_trace,
    get_config_val,
    set_config_val
)
from backend.agent_tools import (
    get_shop_state,
    forecast_demand,
    detect_expiry_and_dead_stock,
    optimize_order,
    draft_distributor_whatsapp,
    request_owner_approval,
    send_order_and_track,
    handle_distributor_stockout
)

# Tool schema descriptions for LLM function calling
TOOL_DEFINITIONS = [
    {
        "name": "get_shop_state",
        "description": "Fetches current inventory levels, available cash budget, outstanding khata credit, and shop configuration for StoreyStores.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "forecast_demand",
        "description": "Calculates projected daily sales, days of stock left, and identifies imminent stockout risks considering whether Festival Surge Mode is active.",
        "parameters": {
            "type": "object",
            "properties": {
                "festival_mode": {"type": "boolean", "description": "Whether upcoming festival (Diwali/weekend) surge is enabled"}
            },
            "required": []
        }
    },
    {
        "name": "detect_expiry_and_dead_stock",
        "description": "Identifies items approaching expiration within 15 days (capital at risk) and dead-stock items blocking working capital.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "optimize_order",
        "description": "Applies budget-constrained order optimization to calculate optimal replenishment quantities prioritizing stockout items and enforcing cash limit.",
        "parameters": {
            "type": "object",
            "properties": {
                "budget": {"type": "number", "description": "Available cash budget in INR (e.g. 20000)"}
            },
            "required": []
        }
    },
    {
        "name": "request_owner_approval",
        "description": "HARD GUARDRAIL: Pauses execution and displays the proposed distributor purchase order to the shop owner for interactive confirmation or quantity adjustments.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_summary": {"type": "object", "description": "The generated order draft"}
            },
            "required": ["order_summary"]
        }
    },
    {
        "name": "send_order_and_track",
        "description": "Simulates sending confirmed WhatsApp purchase order to Balaji Wholesale Distributors and tracks dispatch.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "The approved order ID"}
            },
            "required": ["order_id"]
        }
    },
    {
        "name": "handle_distributor_stockout",
        "description": "Autonomous exception recovery triggered when distributor reports an out-of-stock item, recalculating alternatives and drafting revised order.",
        "parameters": {
            "type": "object",
            "properties": {
                "out_of_stock_sku": {"type": "string", "description": "SKU that is out of stock at supplier"},
                "supplier_note": {"type": "string", "description": "Distributor WhatsApp reply note"}
            },
            "required": []
        }
    }
]

class KiranaAgentOrchestrator:
    def __init__(self):
        self.openai_key = os.getenv("OPENAI_API_KEY", "")
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")

    def execute_full_cycle(self, festival_mode: Optional[bool] = None, budget: Optional[float] = None) -> Dict[str, Any]:
        """
        Executes an end-to-end autonomous audit and replenishment cycle.
        Step 1: OBSERVE - Fetch shop inventory & state
        Step 2: ANALYZE - Demand forecasting & stockout risk calculation
        Step 3: AUDIT - Expiry & dead-stock capital inspection
        Step 4: PLAN - Budget-constrained order optimization
        Step 5: GUARDRAIL - Halt for shop owner review & approval
        """
        mode = get_config_val("agent_mode", "mock")
        if festival_mode is not None:
            set_config_val("festival_mode", festival_mode)
        if budget is not None:
            set_config_val("cash_budget", budget)
            
        current_fest = get_config_val("festival_mode", False)
        current_budget = get_config_val("cash_budget", 20000.0)
        
        # --- Step 1: OBSERVE ---
        log_agent_trace(
            stage="OBSERVE",
            message="Agent initiating autonomous shop health & replenishment audit.",
            tool_name="get_shop_state",
            tool_args={},
            tool_result={"status": "Fetching current catalog and cash position"},
            status="info"
        )
        shop_state = get_shop_state()
        
        # --- Step 2: ANALYZE ---
        log_agent_trace(
            stage="THINK",
            message=f"Analyzing demand forecast under {'FESTIVAL SURGE (+80% Oil/Dal/Snacks)' if current_fest else 'STANDARD BASELINE'} conditions.",
            tool_name=None,
            status="info"
        )
        forecast_res = forecast_demand(current_fest)
        log_agent_trace(
            stage="TOOL_RESULT",
            message=f"Forecast complete: Identified {forecast_res['critical_stockouts_count']} items with imminent stockout before distributor visit.",
            tool_name="forecast_demand",
            tool_args={"festival_mode": current_fest},
            tool_result={
                "critical_stockouts": [i["name"] for i in forecast_res["stockout_items"]],
                "cycle_days": forecast_res["distributor_cycle_days"]
            },
            status="warning" if forecast_res["critical_stockouts_count"] > 0 else "info"
        )
        
        # --- Step 3: AUDIT EXPIRY & DEAD STOCK ---
        log_agent_trace(
            stage="THINK",
            message="Scanning shelf inventory for capital leakage, expiry threats (<15 days), and zero-velocity dead stock (<0.1 units/day).",
            tool_name=None,
            status="info"
        )
        expiry_dead_res = detect_expiry_and_dead_stock()
        log_agent_trace(
            stage="TOOL_RESULT",
            message=f"Audit Alert: ₹{expiry_dead_res['total_at_risk_expiry_value']:,} at risk of imminent expiration; ₹{expiry_dead_res['total_blocked_dead_capital']:,} locked in dead inventory.",
            tool_name="detect_expiry_and_dead_stock",
            tool_args={},
            tool_result={
                "near_expiry": expiry_dead_res["near_expiry_items"],
                "dead_stock": expiry_dead_res["dead_stock_items"]
            },
            status="warning"
        )
        
        # --- Step 4: PLAN (OPTIMIZE ORDER) ---
        log_agent_trace(
            stage="THINK",
            message=f"Formulating optimal replenishment order strictly constrained within ₹{current_budget:,} cash limit.",
            tool_name="optimize_order",
            tool_args={"budget": current_budget},
            status="info"
        )
        order_draft = optimize_order(current_budget)
        log_agent_trace(
            stage="TOOL_RESULT",
            message=f"Order drafted: {order_draft['item_count']} line items totalling ₹{order_draft['total_order_cost']:,}. Remaining liquidity: ₹{order_draft['remaining_budget']:,}.",
            tool_name="optimize_order",
            tool_args={"budget": current_budget},
            tool_result=order_draft,
            status="info"
        )
        
        # --- Step 5: HARD GUARDRAIL ---
        approval_summary = request_owner_approval(order_draft)
        
        return {
            "cycle_status": "AWAITING_OWNER_APPROVAL",
            "shop_state": shop_state,
            "forecast": forecast_res,
            "expiry_dead": expiry_dead_res,
            "draft_order": approval_summary
        }

    def approve_and_send_order(self, order_id: str, custom_items: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Called when the shopkeeper reviews and approves the order (or updates quantities).
        """
        active_order = get_config_val("active_order", {})
        if custom_items:
            # Recalculate totals
            new_total = sum(float(it.get("quantity", 0)) * float(it.get("unit_cost", 0)) for it in custom_items)
            for it in custom_items:
                it["total_cost"] = round(float(it.get("quantity", 0)) * float(it.get("unit_cost", 0)), 2)
            active_order["items"] = custom_items
            active_order["total_order_cost"] = round(new_total, 2)
            current_budget = get_config_val("cash_budget", 20000.0)
            active_order["remaining_budget"] = round(current_budget - new_total, 2)
            set_config_val("active_order", active_order)
            
        log_agent_trace(
            stage="GUARDRAIL",
            message="Human-in-the-Loop: Shopkeeper of StoreyStores APPROVED order. Proceeding to supplier transmission.",
            tool_name="request_owner_approval",
            tool_result={"decision": "APPROVED", "modified_by_user": bool(custom_items)},
            status="success"
        )
        
        sent_order = send_order_and_track(order_id)
        return sent_order

    def reject_order(self, order_id: str, reason: str = "Rejected by owner") -> Dict[str, Any]:
        active_order = get_config_val("active_order", {})
        active_order["status"] = "REJECTED"
        active_order["rejection_reason"] = reason
        set_config_val("active_order", active_order)
        
        log_agent_trace(
            stage="GUARDRAIL",
            message=f"Human-in-the-Loop: Order {order_id} was REJECTED by Shopkeeper. Reason: {reason}",
            tool_name="request_owner_approval",
            tool_result={"decision": "REJECTED"},
            status="warning"
        )
        return active_order

    def simulate_distributor_stockout(self, out_of_stock_sku: str = "SKU02", supplier_note: Optional[str] = None) -> Dict[str, Any]:
        """
        Simulates distributor WhatsApp reply saying item is out of stock,
        triggering autonomous recovery.
        """
        note = supplier_note or "Bhaiya, Sunflower Cooking Oil 1L pouch is out of stock in warehouse! Only 5L Fortune Jar (₹590 cost, ₹650 MRP) or Palm Oil available."
        return handle_distributor_stockout(out_of_stock_sku, note)

orchestrator = KiranaAgentOrchestrator()
