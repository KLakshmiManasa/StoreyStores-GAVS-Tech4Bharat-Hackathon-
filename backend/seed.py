import json
import sqlite3
from backend.database import get_connection, init_db, log_agent_trace

SEED_INVENTORY = [
    {
        "sku": "SKU01",
        "name": "Parle-G Biscuit (₹5)",
        "category": "Biscuits & Snacks",
        "aliases": ["parle biscuit", "parle g small", "parle 5 rs", "parle-g", "biscuit", "parle"],
        "current_stock": 10.0,
        "unit": "packets",
        "cost_price": 4.20,
        "selling_price": 5.00,
        "daily_avg_sales": 6.0,
        "expiry_days": 90,
        "status": "healthy",
        "notes": "High velocity staple, low margin"
    },
    {
        "sku": "SKU02",
        "name": "Sunflower Cooking Oil (1L)",
        "category": "Edible Oils",
        "aliases": ["tel", "oil packet", "sunflower oil", "cooking oil", "refined oil"],
        "current_stock": 4.0,
        "unit": "pouches",
        "cost_price": 135.00,
        "selling_price": 155.00,
        "daily_avg_sales": 3.0,
        "expiry_days": 120,
        "status": "stockout_risk",
        "notes": "Stock critical! Only 1.3 days left before distributor arrives."
    },
    {
        "sku": "SKU03",
        "name": "Dairy Milk Powder (500g)",
        "category": "Dairy Products",
        "aliases": ["milk powder", "doodh powder", "dairy milk", "dry milk", "powder doodh"],
        "current_stock": 20.0,
        "unit": "packets",
        "cost_price": 180.00,
        "selling_price": 210.00,
        "daily_avg_sales": 1.0,
        "expiry_days": 8,
        "status": "near_expiry",
        "notes": "URGENT: Expiring in 8 days! Capital at risk: ₹3,600. Needs bundle discount or supplier return."
    },
    {
        "sku": "SKU04",
        "name": "Lux Bathing Soap (100g)",
        "category": "Personal Care",
        "aliases": ["soap", "sabun", "lux", "bath soap"],
        "current_stock": 35.0,
        "unit": "bars",
        "cost_price": 28.00,
        "selling_price": 35.00,
        "daily_avg_sales": 0.5,
        "expiry_days": 300,
        "status": "overstocked",
        "notes": "70 days of stock sitting on shelf. Do not reorder."
    },
    {
        "sku": "SKU05",
        "name": "Toor Dal (1kg)",
        "category": "Pulses & Grains",
        "aliases": ["dal", "arhar dal", "toor", "toor dal", "tuvar dal"],
        "current_stock": 6.0,
        "unit": "packets",
        "cost_price": 145.00,
        "selling_price": 175.00,
        "daily_avg_sales": 2.5,
        "expiry_days": 150,
        "status": "stockout_risk",
        "notes": "Only 2.4 days stock remaining. Daily essential."
    },
    {
        "sku": "SKU06",
        "name": "Exotic Herbal Tea (250g)",
        "category": "Beverages",
        "aliases": ["green tea", "herbal tea", "exotic tea", "organic tea"],
        "current_stock": 25.0,
        "unit": "boxes",
        "cost_price": 220.00,
        "selling_price": 280.00,
        "daily_avg_sales": 0.05,
        "expiry_days": 180,
        "status": "dead_stock",
        "notes": "Sold only 1 box in 3 weeks. ₹5,500 working capital locked. Recommend clearance sale."
    }
]

SEED_KHATA = [
    {
        "customer_name": "Ramesh Kumar (Auto Driver)",
        "customer_phone": "+91 98451 22345",
        "amount": 450.0,
        "entry_type": "credit_given",
        "notes": "Grocery & biscuits on credit - promised pay on Saturday"
    },
    {
        "customer_name": "Sharmaji (Building 4)",
        "customer_phone": "+91 99123 45678",
        "amount": 820.0,
        "entry_type": "credit_given",
        "notes": "Monthly provision balance"
    },
    {
        "customer_name": "Priya Teacher",
        "customer_phone": "+91 98765 11223",
        "amount": 310.0,
        "entry_type": "credit_given",
        "notes": "Tea powder and snacks"
    }
]

def seed_database():
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    
    # Clear existing data
    cursor.execute("DELETE FROM inventory")
    cursor.execute("DELETE FROM khata")
    cursor.execute("DELETE FROM shop_config")
    cursor.execute("DELETE FROM agent_traces")
    cursor.execute("DELETE FROM orders")
    
    # Insert inventory
    for item in SEED_INVENTORY:
        cursor.execute("""
        INSERT INTO inventory (sku, name, category, aliases, current_stock, unit, cost_price, selling_price, daily_avg_sales, expiry_days, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item["sku"],
            item["name"],
            item["category"],
            json.dumps(item["aliases"]),
            item["current_stock"],
            item["unit"],
            item["cost_price"],
            item["selling_price"],
            item["daily_avg_sales"],
            item["expiry_days"],
            item["status"],
            item["notes"]
        ))
        
    # Insert khata
    import datetime
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for k in SEED_KHATA:
        cursor.execute("""
        INSERT INTO khata (customer_name, customer_phone, amount, entry_type, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (k["customer_name"], k["customer_phone"], k["amount"], k["entry_type"], k["notes"], now_str))
        
    # Set default shop config
    cursor.execute("INSERT INTO shop_config (key, value) VALUES (?, ?)", ("shop_name", json.dumps("StoreyStores")))
    cursor.execute("INSERT INTO shop_config (key, value) VALUES (?, ?)", ("cash_budget", json.dumps(20000.0)))
    cursor.execute("INSERT INTO shop_config (key, value) VALUES (?, ?)", ("festival_mode", json.dumps(False)))
    cursor.execute("INSERT INTO shop_config (key, value) VALUES (?, ?)", ("agent_mode", json.dumps("mock")))
    cursor.execute("INSERT INTO shop_config (key, value) VALUES (?, ?)", ("next_distributor_days", json.dumps(3)))
    cursor.execute("INSERT INTO shop_config (key, value) VALUES (?, ?)", ("active_order", json.dumps(None)))
    
    conn.commit()
    conn.close()
    
    # Log initial trace
    log_agent_trace(
        stage="OBSERVE",
        message="StoreyStores system initialized. Initial inventory and cash budget (₹20,000) loaded.",
        tool_name="get_shop_state",
        tool_result={"shop_name": "StoreyStores", "budget": 20000.0, "total_skus": 6},
        status="info"
    )

if __name__ == "__main__":
    seed_database()
    print("Database seeded successfully with StoreyStores state!")
