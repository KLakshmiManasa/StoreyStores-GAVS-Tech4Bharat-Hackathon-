import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_full_pipeline():
    print("1. Testing GET /api/state...")
    res = client.get("/api/state")
    assert res.status_code == 200, f"Failed: {res.text}"
    data = res.json()
    print(f"   Shop: {data['shop_name']}, Budget: ₹{data['cash_budget']}, SKUs: {len(data['inventory'])}")
    assert len(data['inventory']) == 6
    assert data['cash_budget'] == 20000.0
    
    print("\n2. Testing Voice Zero-POS: 'Parle-G 10 packet bacha hai, tel 4 packet, aur Ramesh ka 450 rupaye udhaar likh lo'...")
    res = client.post("/api/voice/process", json={"transcript": "Parle-G 10 packet bacha hai, tel 4 packet, aur Ramesh ka 450 rupaye udhaar likh lo"})
    assert res.status_code == 200
    v_data = res.json()
    print("   Actions taken:", v_data["actions_taken"])
    assert len(v_data["stock_updates"]) >= 1
    assert len(v_data["khata_entries"]) >= 1
    
    print("\n3. Testing Festival Mode toggle (+80% demand)...")
    res = client.post("/api/festival-mode", json={"enabled": True})
    assert res.status_code == 200
    assert res.json()["festival_mode"] == True
    
    print("\n4. Testing Full Agentic Audit Loop...")
    res = client.post("/api/agent/run-audit")
    assert res.status_code == 200
    audit_data = res.json()
    print("   Audit cycle status:", audit_data["cycle_status"])
    print(f"   Items in proposed order: {len(audit_data['draft_order']['items'])}")
    print(f"   Total Order Cost: ₹{audit_data['draft_order']['total_order_cost']}")
    assert audit_data["cycle_status"] == "AWAITING_OWNER_APPROVAL"
    
    order_id = audit_data["draft_order"]["order_id"]
    
    print(f"\n5. Testing Owner Approval for order {order_id}...")
    res = client.post("/api/agent/approve-order", json={"order_id": order_id, "action": "approve"})
    assert res.status_code == 200
    appr_data = res.json()
    print("   Order sent status:", appr_data.get("status"))
    print(f"   Remaining Budget: ₹{appr_data.get('remaining_budget')}")
    assert appr_data.get("status") == "SENT_TO_DISTRIBUTOR"
    
    print("\n6. Testing Exception Handling Demo ('Simulate Distributor Stockout')...")
    res = client.post("/api/agent/simulate-stockout", json={"out_of_stock_sku": "SKU02"})
    assert res.status_code == 200
    exc_data = res.json()
    print("   Exception recovery order status:", exc_data.get("status"))
    print("   Substituted items count:", len(exc_data.get("items", [])))
    print("   Revised order total:", exc_data.get("total_order_cost"))
    assert exc_data.get("status") == "AWAITING_OWNER_APPROVAL"
    assert exc_data.get("is_exception_revision") == True
    
    print("\n7. Testing Distributor Bill OCR and Inward Confirmation...")
    bill_res = client.get("/api/ocr/sample-bill")
    assert bill_res.status_code == 200
    bill = bill_res.json()
    print(f"   Distributor: {bill['distributor_name']}, Total: ₹{bill['grand_total']}")
    
    inward_res = client.post("/api/ocr/confirm-inward", json=bill)
    assert inward_res.status_code == 200
    print("   Inward result:", inward_res.json())
    
    print("\n8. Testing Agent Traces...")
    traces_res = client.get("/api/traces")
    assert traces_res.status_code == 200
    traces = traces_res.json()["traces"]
    print(f"   Total Agent Trace Steps recorded: {len(traces)}")
    assert len(traces) > 0
    stages = set(t["stage"] for t in traces)
    print("   Stages present in trace:", stages)
    assert "OBSERVE" in stages or "THINK" in stages
    assert "GUARDRAIL" in stages
    assert "RECOVERY" in stages
    
    print("\n9. Testing Reset Demo State...")
    reset_res = client.post("/api/reset-demo")
    assert reset_res.status_code == 200
    print("   Reset status:", reset_res.json())
    
    print("\nALL BACKEND API TESTS PASSED SUCCESSFULLY! 🚀")

if __name__ == "__main__":
    test_full_pipeline()
