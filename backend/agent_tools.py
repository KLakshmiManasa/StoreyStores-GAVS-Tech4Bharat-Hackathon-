import json
import re
from typing import Dict, Any, List, Optional
from backend.database import (
    get_all_inventory,
    get_inventory_item,
    update_inventory_stock,
    add_inventory_stock,
    get_config_val,
    set_config_val,
    add_khata_entry,
    get_all_khata,
    log_agent_trace
)

# Tool 1: get_shop_state
def get_shop_state() -> Dict[str, Any]:
    inventory = get_all_inventory()
    budget = get_config_val("cash_budget", 20000.0)
    festival_mode = get_config_val("festival_mode", False)
    next_distributor_days = get_config_val("next_distributor_days", 3)
    khata = get_all_khata()
    
    total_inventory_cost_value = sum(i["current_stock"] * i["cost_price"] for i in inventory)
    total_khata_outstanding = sum(k["amount"] for k in khata)
    
    result = {
        "shop_name": get_config_val("shop_name", "StoreyStores"),
        "cash_budget": budget,
        "festival_mode": festival_mode,
        "next_distributor_days": next_distributor_days,
        "total_skus": len(inventory),
        "inventory_cost_value": round(total_inventory_cost_value, 2),
        "khata_outstanding_total": round(total_khata_outstanding, 2),
        "items": inventory
    }
    return result

# Tool 2: forecast_demand
def forecast_demand(festival_mode: Optional[bool] = None) -> Dict[str, Any]:
    if festival_mode is None:
        festival_mode = get_config_val("festival_mode", False)
        
    inventory = get_all_inventory()
    next_distributor_days = get_config_val("next_distributor_days", 3)
    
    # Category multipliers when festival mode is on
    # E.g. Diwali / Weekend surge: +80% on Edible Oils, +60% on Snacks, +70% on Pulses
    multipliers = {
        "Edible Oils": 1.80 if festival_mode else 1.0,
        "Biscuits & Snacks": 1.60 if festival_mode else 1.0,
        "Pulses & Grains": 1.70 if festival_mode else 1.0,
        "Dairy Products": 1.20 if festival_mode else 1.0,
        "Personal Care": 1.10 if festival_mode else 1.0,
        "Beverages": 1.00  # exotic dead stock does not surge
    }
    
    forecasts = []
    stockout_risks = []
    
    for item in inventory:
        cat = item["category"]
        mult = multipliers.get(cat, 1.0)
        adj_daily = round(item["daily_avg_sales"] * mult, 2)
        
        if adj_daily > 0:
            days_left = round(item["current_stock"] / adj_daily, 1)
        else:
            days_left = 999.0
            
        stockout_before_visit = days_left < next_distributor_days
        
        # Target coverage: 7 days of demand
        target_stock = round(adj_daily * 7, 0)
        shortfall = max(0.0, round(target_stock - item["current_stock"], 0))
        
        f_entry = {
            "sku": item["sku"],
            "name": item["name"],
            "category": item["category"],
            "current_stock": item["current_stock"],
            "unit": item["unit"],
            "base_daily_sales": item["daily_avg_sales"],
            "demand_multiplier": mult,
            "projected_daily_demand": adj_daily,
            "days_of_stock_left": days_left,
            "stockout_before_distributor": stockout_before_visit,
            "target_coverage_units": target_stock,
            "shortfall_units": shortfall
        }
        forecasts.append(f_entry)
        if stockout_before_visit:
            stockout_risks.append(f_entry)
            
    return {
        "festival_mode": festival_mode,
        "distributor_cycle_days": next_distributor_days,
        "critical_stockouts_count": len(stockout_risks),
        "stockout_items": stockout_risks,
        "forecasts": forecasts
    }

# Tool 3: detect_expiry_and_dead_stock
def detect_expiry_and_dead_stock() -> Dict[str, Any]:
    inventory = get_all_inventory()
    
    near_expiry_items = []
    dead_stock_items = []
    overstocked_items = []
    
    total_at_risk_expiry_val = 0.0
    total_blocked_dead_val = 0.0
    
    for item in inventory:
        capital = round(item["current_stock"] * item["cost_price"], 2)
        
        # Expiry rule: <= 15 days
        if item["expiry_days"] <= 15:
            near_expiry_items.append({
                "sku": item["sku"],
                "name": item["name"],
                "days_to_expiry": item["expiry_days"],
                "current_stock": item["current_stock"],
                "unit": item["unit"],
                "capital_at_risk": capital,
                "urgency": "HIGH" if item["expiry_days"] <= 10 else "MEDIUM",
                "recommended_action": f"Bundle offer: 20% discount with {item['name']} or initiate distributor return within 5 days"
            })
            total_at_risk_expiry_val += capital
            
        # Dead stock rule: daily sales < 0.1
        elif item["daily_avg_sales"] < 0.1:
            dead_stock_items.append({
                "sku": item["sku"],
                "name": item["name"],
                "daily_sales_velocity": item["daily_avg_sales"],
                "current_stock": item["current_stock"],
                "unit": item["unit"],
                "blocked_capital": capital,
                "recommended_action": f"Liquidation sale at ₹{item['cost_price']} (cost recovery) to free up shelf space for fast-moving items"
            })
            total_blocked_dead_val += capital
            
        # Overstocked rule: stock > 50 days of sales
        elif item["daily_avg_sales"] > 0 and (item["current_stock"] / item["daily_avg_sales"]) > 50:
            overstocked_items.append({
                "sku": item["sku"],
                "name": item["name"],
                "days_cover": round(item["current_stock"] / item["daily_avg_sales"], 1),
                "stock": item["current_stock"],
                "recommended_action": "Freeze replenishment. Let organic customer demand deplete current stock."
            })
            
    return {
        "total_at_risk_expiry_value": round(total_at_risk_expiry_val, 2),
        "total_blocked_dead_capital": round(total_blocked_dead_val, 2),
        "near_expiry_count": len(near_expiry_items),
        "dead_stock_count": len(dead_stock_items),
        "near_expiry_items": near_expiry_items,
        "dead_stock_items": dead_stock_items,
        "overstocked_items": overstocked_items
    }

# Tool 4: optimize_order
def optimize_order(budget: Optional[float] = None) -> Dict[str, Any]:
    if budget is None:
        budget = float(get_config_val("cash_budget", 20000.0))
        
    festival_mode = get_config_val("festival_mode", False)
    forecast_data = forecast_demand(festival_mode)
    inventory_map = {i["sku"]: i for i in get_all_inventory()}
    
    # Exclude dead stock and overstocked from reordering
    candidates = []
    for f in forecast_data["forecasts"]:
        sku = f["sku"]
        inv = inventory_map[sku]
        
        # Skip dead stock or very slow moving
        if inv["daily_avg_sales"] < 0.1 or inv["status"] == "dead_stock":
            continue
        # Skip overstocked
        if f["days_of_stock_left"] > 25:
            continue
            
        shortfall = f["shortfall_units"]
        if shortfall <= 0:
            # Check if stock is low anyway
            if f["days_of_stock_left"] < 4:
                shortfall = max(5.0, round(f["projected_daily_demand"] * 5, 0))
            else:
                continue
                
        unit_cost = inv["cost_price"]
        unit_price = inv["selling_price"]
        margin_pct = round(((unit_price - unit_cost) / unit_price) * 100, 1)
        urgency = 100.0 / (f["days_of_stock_left"] + 0.1)
        score = urgency * (margin_pct / 10.0)
        
        candidates.append({
            "sku": sku,
            "name": inv["name"],
            "unit": inv["unit"],
            "unit_cost": unit_cost,
            "unit_price": unit_price,
            "days_left": f["days_of_stock_left"],
            "recommended_qty": shortfall,
            "score": score,
            "margin_pct": margin_pct
        })
        
    # Sort candidates by score descending
    candidates.sort(key=lambda x: x["score"], reverse=True)
    
    order_items = []
    current_cost = 0.0
    
    for c in candidates:
        qty = c["recommended_qty"]
        line_cost = qty * c["unit_cost"]
        
        # Enforce budget constraint
        if current_cost + line_cost <= budget:
            order_items.append({
                "sku": c["sku"],
                "name": c["name"],
                "quantity": int(qty),
                "unit": c["unit"],
                "unit_cost": c["unit_cost"],
                "total_cost": round(line_cost, 2),
                "days_left": c["days_left"],
                "margin_pct": c["margin_pct"]
            })
            current_cost += line_cost
        else:
            # Partial fill if budget allows some units
            avail = budget - current_cost
            partial_qty = int(avail // c["unit_cost"])
            if partial_qty > 0:
                p_cost = partial_qty * c["unit_cost"]
                order_items.append({
                    "sku": c["sku"],
                    "name": c["name"],
                    "quantity": partial_qty,
                    "unit": c["unit"],
                    "unit_cost": c["unit_cost"],
                    "total_cost": round(p_cost, 2),
                    "days_left": c["days_left"],
                    "margin_pct": c["margin_pct"]
                })
                current_cost += p_cost
                
    remaining_budget = round(budget - current_cost, 2)
    
    # Draft summary
    order_id = f"PO_{get_config_val('next_distributor_days', 3)}D_SURGE"
    order_summary = {
        "order_id": order_id,
        "festival_mode": festival_mode,
        "allocated_budget": budget,
        "total_order_cost": round(current_cost, 2),
        "remaining_budget": remaining_budget,
        "item_count": len(order_items),
        "items": order_items,
        "status": "DRAFT"
    }
    
    set_config_val("active_order", order_summary)
    return order_summary

# Tool 5: draft_distributor_whatsapp
def draft_distributor_whatsapp(order_items: List[Dict[str, Any]], supplier_name: str = "Balaji Wholesale Distributors") -> str:
    lines = [
        f"Namaste {supplier_name} ji 🙏",
        "This is *StoreyStores* (Kirana - Main Bazar).",
        "Please send following urgent replenishment order for tomorrow morning delivery:\n"
    ]
    
    total = 0.0
    for idx, item in enumerate(order_items, start=1):
        name = item.get("name")
        qty = item.get("quantity")
        unit = item.get("unit", "units")
        cost = item.get("total_cost", 0.0)
        total += cost
        lines.append(f"{idx}. *{name}* — {qty} {unit}")
        
    lines.append(f"\n*Estimated Order Value:* ₹{round(total, 2):,}")
    lines.append("Payment mode: UPI / Cash upon invoice verification.")
    lines.append("Please confirm vehicle dispatch time. Dhanyavaad! 🙏")
    
    whatsapp_msg = "\n".join(lines)
    return whatsapp_msg

# Tool 6: request_owner_approval
def request_owner_approval(order_summary: Dict[str, Any]) -> Dict[str, Any]:
    whatsapp_text = draft_distributor_whatsapp(order_summary.get("items", []))
    order_summary["whatsapp_message"] = whatsapp_text
    order_summary["status"] = "AWAITING_OWNER_APPROVAL"
    set_config_val("active_order", order_summary)
    
    log_agent_trace(
        stage="GUARDRAIL",
        message="HARD GUARDRAIL TRIGGERED: Order requires Shopkeeper confirmation before transmission.",
        tool_name="request_owner_approval",
        tool_args={"order_id": order_summary.get("order_id"), "total_cost": order_summary.get("total_order_cost")},
        tool_result={"approval_status": "PAUSED_FOR_USER", "action_required": "Approve / Edit Quantities in UI"},
        status="pause"
    )
    return order_summary

# Tool 7: send_order_and_track
def send_order_and_track(order_id: str) -> Dict[str, Any]:
    active_order = get_config_val("active_order", {})
    if not active_order:
        return {"error": "No active order found to transmit."}
        
    total_cost = active_order.get("total_order_cost", 0.0)
    current_budget = get_config_val("cash_budget", 20000.0)
    
    # Deduct cash budget
    new_budget = max(0.0, round(current_budget - total_cost, 2))
    set_config_val("cash_budget", new_budget)
    
    active_order["status"] = "SENT_TO_DISTRIBUTOR"
    active_order["tracking_id"] = f"DISPATCH_BWD_{order_id[-6:]}"
    active_order["estimated_delivery"] = "Tomorrow 09:30 AM"
    set_config_val("active_order", active_order)
    
    log_agent_trace(
        stage="ACTION",
        message=f"Order {order_id} successfully transmitted to Balaji Distributors via WhatsApp Simulator. Budget updated.",
        tool_name="send_order_and_track",
        tool_args={"order_id": order_id, "recipient": "+91 98450 12345"},
        tool_result={"status": "SENT", "tracking_id": active_order["tracking_id"], "new_budget": new_budget},
        status="success"
    )
    return active_order

# Tool 8: handle_distributor_stockout (Autonomous Exception Recovery)
def handle_distributor_stockout(out_of_stock_sku: str = "SKU02", supplier_note: Optional[str] = None) -> Dict[str, Any]:
    active_order = get_config_val("active_order", {})
    if not active_order or "items" not in active_order:
        return {"error": "No sent order available to simulate stockout on."}
        
    log_agent_trace(
        stage="RECOVERY",
        message=f"EXCEPTION DETECTED: Distributor reported stockout on SKU02 (Sunflower Cooking Oil 1L pouches).",
        tool_name="handle_distributor_stockout",
        tool_args={"out_of_stock_sku": out_of_stock_sku, "supplier_note": supplier_note or "1L pouches out of stock at central warehouse"},
        tool_result={"trigger": "Autonomous alternative evaluation initiated"},
        status="recovery"
    )
    
    # Filter out or substitute the item
    # In Kirana shops, if 1L Sunflower oil pouches are out of stock,
    # the best substitute is Fortune 5L Sunflower Jar (family pack for Diwali) OR Palm Oil.
    old_items = active_order.get("items", [])
    revised_items = []
    
    substituted = False
    for it in old_items:
        if it.get("sku") == out_of_stock_sku:
            substituted = True
            # Substitute with 5L Cooking Oil Jar
            revised_items.append({
                "sku": "SKU02-5L",
                "name": "Fortune Sunflower Oil (5L Family Jar)",
                "quantity": 3,
                "unit": "jars",
                "unit_cost": 590.00,
                "total_cost": 1770.00,
                "days_left": it.get("days_left", 1.3),
                "margin_pct": 14.5,
                "substitution_reason": "High festive demand; satisfies 15L equivalent demand while 1L pouch is out of stock"
            })
        else:
            revised_items.append(it)
            
    if not substituted:
        # If SKU02 was not in items, add 5L Jar
        revised_items.append({
            "sku": "SKU02-5L",
            "name": "Fortune Sunflower Oil (5L Family Jar)",
            "quantity": 3,
            "unit": "jars",
            "unit_cost": 590.00,
            "total_cost": 1770.00,
            "days_left": 1.3,
            "margin_pct": 14.5,
            "substitution_reason": "Direct festive substitute for out-of-stock 1L oil"
        })
        
    revised_total = sum(i["total_cost"] for i in revised_items)
    budget = get_config_val("cash_budget", 20000.0)
    
    revised_order = {
        "order_id": f"{active_order.get('order_id', 'PO')}_REVISED_v2",
        "festival_mode": active_order.get("festival_mode", False),
        "allocated_budget": budget,
        "total_order_cost": round(revised_total, 2),
        "remaining_budget": round(budget - revised_total, 2),
        "item_count": len(revised_items),
        "items": revised_items,
        "status": "AWAITING_OWNER_APPROVAL",
        "is_exception_revision": True,
        "distributor_alert": supplier_note or "Sunflower Cooking Oil 1L pouch out of stock in warehouse! Only 5L Fortune Jar (₹590 cost, ₹650 MRP) or Palm Oil available."
    }
    
    revised_order["whatsapp_message"] = draft_distributor_whatsapp(revised_items, "Balaji Wholesale (Revised PO)")
    set_config_val("active_order", revised_order)
    
    log_agent_trace(
        stage="GUARDRAIL",
        message="EXCEPTION PLAN FORMED: Substituted 12x 1L pouches with 3x 5L Family Jars (₹1,770). Halting for Owner Re-Approval.",
        tool_name="request_owner_approval",
        tool_args={"revised_order_id": revised_order["order_id"], "new_total": revised_total},
        tool_result={"status": "PAUSED_FOR_USER_REAPPROVAL", "action": "Owner must confirm substitute selection"},
        status="pause"
    )
    
    return revised_order

# Fuzzy & Alias Resolution for Voice Input
def parse_voice_khata_input(transcript: str) -> Dict[str, Any]:
    transcript_lower = transcript.lower().strip()
    inventory = get_all_inventory()
    
    actions_taken = []
    stock_updates = []
    khata_entries = []
    
    # 1. Parse Khata (credit) entries: e.g. "Ramesh ka 450 rupaye udhaar likh lo"
    khata_pattern = re.search(r'([a-zA-Z\s]+?)\s+ka\s+(\d+(?:\.\d+)?)\s*(?:rupaye|rs|inr)?\s*(?:udhaar|udhar|khata|baki)', transcript_lower)
    if khata_pattern:
        raw_name = khata_pattern.group(1).strip()
        # Clean leading conjunctions like 'aur ', 'and '
        raw_name = re.sub(r'^(?:aur|and|tatha|bhi)\s+', '', raw_name, flags=re.IGNORECASE)
        cust_name = raw_name.strip().title()
        amt = float(khata_pattern.group(2))
        add_khata_entry(cust_name, amt, f"Voice log: '{transcript}'")
        khata_entries.append({"customer": cust_name, "amount": amt})
        actions_taken.append(f"Recorded ₹{amt} Khata credit for {cust_name}")
        
    # 2. Parse Stock updates via aliases
    # Map keywords to SKUs
    for item in inventory:
        sku = item["sku"]
        name = item["name"]
        aliases = item["aliases"]
        
        # Check if any alias appears in transcript
        matched_alias = None
        for alias in aliases:
            if alias.lower() in transcript_lower:
                matched_alias = alias
                break
                
        if matched_alias:
            # Try to extract quantity near the alias: e.g. "10 packet", "4 packet", "20 bar", "10 bacha hai"
            # Pattern: (\d+)\s*(?:packet|pouches|bars|boxes|bar|pouch|pkt|kg|units)?\s*(?:bacha|hai|stock)?
            alias_escaped = re.escape(matched_alias.lower())
            
            # Look before alias or after alias
            # e.g., "Parle-G 10 packet" or "tel 4 packet"
            q_after = re.search(alias_escaped + r'[\s:]+(\d+(?:\.\d+)?)\s*(?:packet|pouches|bars|boxes|bar|pouch|pkt|kg|units|litres|l)?', transcript_lower)
            q_before = re.search(r'(\d+(?:\.\d+)?)\s*(?:packet|pouches|bars|boxes|bar|pouch|pkt|kg|units|litres|l)?\s+' + alias_escaped, transcript_lower)
            
            found_qty = None
            if q_after:
                found_qty = float(q_after.group(1))
            elif q_before:
                found_qty = float(q_before.group(1))
                
            if found_qty is not None:
                update_inventory_stock(sku, found_qty)
                stock_updates.append({
                    "sku": sku,
                    "name": name,
                    "matched_alias": matched_alias,
                    "new_stock": found_qty
                })
                actions_taken.append(f"Updated {name} ({sku}) stock to {found_qty} {item['unit']}")
                
    summary = {
        "raw_transcript": transcript,
        "actions_taken": actions_taken,
        "stock_updates": stock_updates,
        "khata_entries": khata_entries
    }
    
    log_agent_trace(
        stage="TOOL_CALL",
        message=f"Voice Assistant processed: '{transcript}'",
        tool_name="parse_voice_khata_input",
        tool_args={"transcript": transcript},
        tool_result=summary,
        status="success" if actions_taken else "info"
    )
    
    return summary
