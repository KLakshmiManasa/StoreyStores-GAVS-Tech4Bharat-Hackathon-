from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class InventoryItem(BaseModel):
    sku: str
    name: str
    category: str
    aliases: List[str] = []
    current_stock: float
    unit: str
    cost_price: float
    selling_price: float
    daily_avg_sales: float
    expiry_days: int
    status: str = "healthy"
    notes: Optional[str] = ""

class KhataEntry(BaseModel):
    id: Optional[int] = None
    customer_name: str
    customer_phone: Optional[str] = "+91 98765 43210"
    amount: float
    entry_type: str = "credit_given"  # or "payment_received"
    notes: Optional[str] = ""
    created_at: Optional[str] = ""

class ShopConfig(BaseModel):
    shop_name: str = "StoreyStores"
    cash_budget: float = 20000.0
    festival_mode: bool = False
    agent_mode: str = "mock"  # "mock" or "live"
    next_distributor_days: int = 3
    active_order: Optional[Dict[str, Any]] = None

class VoiceInputRequest(BaseModel):
    transcript: str

class BillItem(BaseModel):
    item_name: str
    sku: Optional[str] = None
    quantity: float
    unit_cost: float
    total: float
    expiry_days: int = 180

class BillScanResponse(BaseModel):
    distributor_name: str
    invoice_number: str
    date: str
    items: List[BillItem]
    grand_total: float
    confidence_score: float

class OrderApprovalRequest(BaseModel):
    order_id: str
    action: str  # "approve", "reject", "edit"
    custom_items: Optional[List[Dict[str, Any]]] = None

class SimulateStockoutRequest(BaseModel):
    out_of_stock_sku: str = "SKU02"
    supplier_note: Optional[str] = None

class AgentTraceStep(BaseModel):
    id: str
    timestamp: str
    stage: str  # OBSERVE, THINK, TOOL_CALL, TOOL_RESULT, GUARDRAIL, ACTION, RECOVERY
    message: str
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    tool_result: Optional[Dict[str, Any]] = None
    status: str = "info"  # info, success, warning, pause, recovery
