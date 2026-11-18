import sqlite3
import json
import os
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "kirana.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        sku TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        aliases TEXT NOT NULL,
        current_stock REAL NOT NULL,
        unit TEXT NOT NULL,
        cost_price REAL NOT NULL,
        selling_price REAL NOT NULL,
        daily_avg_sales REAL NOT NULL,
        expiry_days INTEGER NOT NULL,
        status TEXT NOT NULL,
        notes TEXT
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS khata (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT NOT NULL,
        customer_phone TEXT,
        amount REAL NOT NULL,
        entry_type TEXT NOT NULL,
        notes TEXT,
        created_at TEXT NOT NULL
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS shop_config (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agent_traces (
        id TEXT PRIMARY KEY,
        timestamp TEXT NOT NULL,
        stage TEXT NOT NULL,
        message TEXT NOT NULL,
        tool_name TEXT,
        tool_args TEXT,
        tool_result TEXT,
        status TEXT NOT NULL
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        status TEXT NOT NULL,
        items_json TEXT NOT NULL,
        total_cost REAL NOT NULL,
        whatsapp_text TEXT,
        notes TEXT
    )
    """)
    
    conn.commit()
    conn.close()

def get_config_val(key: str, default: Any = None) -> Any:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM shop_config WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    if row:
        try:
            return json.loads(row["value"])
        except Exception:
            return row["value"]
    return default

def set_config_val(key: str, value: Any):
    conn = get_connection()
    cursor = conn.cursor()
    val_str = json.dumps(value) if not isinstance(value, str) else value
    cursor.execute("INSERT OR REPLACE INTO shop_config (key, value) VALUES (?, ?)", (key, val_str))
    conn.commit()
    conn.close()

def get_all_inventory() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM inventory ORDER BY sku ASC")
    rows = cursor.fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["aliases"] = json.loads(d["aliases"])
        result.append(d)
    return result

def get_inventory_item(sku: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM inventory WHERE sku = ?", (sku,))
    row = cursor.fetchone()
    conn.close()
    if row:
        d = dict(row)
        d["aliases"] = json.loads(d["aliases"])
        return d
    return None

def update_inventory_stock(sku: str, new_stock: float):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE inventory SET current_stock = ? WHERE sku = ?", (new_stock, sku))
    conn.commit()
    conn.close()

def add_inventory_stock(sku: str, qty_to_add: float):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE inventory SET current_stock = current_stock + ? WHERE sku = ?", (qty_to_add, sku))
    conn.commit()
    conn.close()

def get_all_khata() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM khata ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_khata_entry(customer_name: str, amount: float, notes: str = "", customer_phone: str = "+91 98765 43210") -> int:
    import datetime
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO khata (customer_name, customer_phone, amount, entry_type, notes, created_at)
    VALUES (?, ?, ?, 'credit_given', ?, ?)
    """, (customer_name, customer_phone, amount, notes, now_str))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id

def log_agent_trace(stage: str, message: str, tool_name: str = None, tool_args: Any = None, tool_result: Any = None, status: str = "info"):
    import datetime
    import uuid
    trace_id = f"tr_{uuid.uuid4().hex[:8]}"
    now_str = datetime.datetime.now().strftime("%H:%M:%S")
    args_str = json.dumps(tool_args) if tool_args is not None else None
    res_str = json.dumps(tool_result) if tool_result is not None else None
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO agent_traces (id, timestamp, stage, message, tool_name, tool_args, tool_result, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (trace_id, now_str, stage, message, tool_name, args_str, res_str, status))
    conn.commit()
    conn.close()
    return {
        "id": trace_id,
        "timestamp": now_str,
        "stage": stage,
        "message": message,
        "tool_name": tool_name,
        "tool_args": tool_args,
        "tool_result": tool_result,
        "status": status
    }

def get_all_traces(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM agent_traces ORDER BY rowid DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    results = []
    for r in reversed(rows):
        d = dict(r)
        if d["tool_args"]:
            try:
                d["tool_args"] = json.loads(d["tool_args"])
            except Exception:
                pass
        if d["tool_result"]:
            try:
                d["tool_result"] = json.loads(d["tool_result"])
            except Exception:
                pass
        results.append(d)
    return results

def clear_traces():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM agent_traces")
    conn.commit()
    conn.close()
