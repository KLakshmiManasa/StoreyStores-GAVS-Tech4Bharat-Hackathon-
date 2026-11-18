# 🛒 KiranaCopilot ("StoreyStores")
### *Autonomous Agentic AI Stock & Working Capital Copilot for Indian Kirana Stores*

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![SQLite](https://img.shields.io/badge/Database-SQLite3-003B57.svg?style=flat&logo=sqlite)](https://sqlite.org)
[![React](https://img.shields.io/badge/Frontend-React_18_(CDN)-61DAFB.svg?style=flat&logo=react)](https://react.dev)
[![TailwindCSS](https://img.shields.io/badge/Styling-Tailwind_CSS-38B2AC.svg?style=flat&logo=tailwind-css)](https://tailwindcss.com)

---

## 🌟 Overview
Small Indian grocery stores ("Kiranas") operate on paper diaries, tight working capital (e.g. ₹20,000 cash), and distributor rhythm cycles (e.g., weekly distributor visits). They suffer from:
1. **Critical stockouts** before distributor visit day during sudden demand surges (Diwali, weekends).
2. **Capital lockup & spoilage** in near-expiry items and dead stock.
3. **POS friction:** Kirana owners will never barcode-scan every ₹5 biscuit or loose packet.

**KiranaCopilot** is an agentic AI operating system for **StoreyStores** that combines:
- **Multimodal Zero-POS Data Capture:** Real-time Web Speech API + Colloquial Hinglish Fuzzy/Alias entity resolution + Distributor Invoice OCR scanner.
- **Dynamic Demand Forecasting:** Upcoming Festival Surge Mode (+80% demand surge on cooking oils, pulses, and snacks) with distributor cycle awareness (Thursday delivery).
- **Budget-Constrained Order Optimization:** Mathematically reorders stock to cover 7-10 days demand without exceeding the ₹20,000 cash limit.
- **Human-in-the-Loop Hard Guardrail:** The AI agent **pauses** execution to request owner approval, letting the shopkeeper review, adjust quantities, or reject.
- **Autonomous Exception Recovery:** Simulates real-world distributor stockouts (e.g. *"1L Sunflower Oil is out of stock in warehouse"*), where the agent automatically wakes up, formulates an alternative order (5L Fortune Jars), and seeks re-approval.
- **Judge's X-Ray Console:** Live side-by-side transparent ReAct trace (`OBSERVE -> THINK -> TOOL_CALL -> TOOL_RESULT -> GUARDRAIL -> ACTION -> RECOVERY`) showing JSON inputs/outputs.

---

## 📁 Project Directory Structure
```
GAVSHackculture/
├── backend/
│   ├── __init__.py
│   ├── main.py               # FastAPI application & API endpoints
│   ├── models.py             # Pydantic data schemas
│   ├── database.py           # SQLite connection, tables & trace logger
│   ├── seed.py               # Pre-seeded StoreyStores catalog & budget
│   ├── agent_tools.py        # 8 explicit tool functions & Hinglish entity parser
│   ├── agent_orchestrator.py # ReAct agent loop, tool execution & LLM/mock modes
│   ├── test_api.py           # Automated test suite verifying all 9 core flows
│   └── kirana.db             # Zero-setup local SQLite database (auto-generated)
├── frontend/
│   └── index.html            # Single-page React 18 / Tailwind dashboard & live console
├── run.py                    # One-command startup launcher
├── requirements.txt          # Python dependencies
└── README.md                 # Documentation & 5-Step Demo Script
```

---

## ⚡ Quickstart Guide (Under 2 Minutes)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Application
```bash
python run.py
```
*Alternatively:*
```bash
uvicorn backend.main:app --reload --port 8000
```

### 3. Open in Browser
Navigate to:
👉 **[http://localhost:8000](http://localhost:8000)**

*(No node, npm, or webpack build required. Everything is served instantly via FastAPI).*

---

## 🎙️ Pre-Seeded Shop State ("StoreyStores")

- **Available Cash Budget:** `₹20,000` (stored in SQLite, editable)
- **Distributor Delivery Cycle:** Next delivery in `3 days` (Thursday)
- **Initial Inventory Table:**

| SKU | Name | Category | Stock | Cost | Sell Price | Daily Sales | Expiry | Status & Notes |
|---|---|---|---|---|---|---|---|---|
| `SKU01` | **Parle-G Biscuit (₹5)** | Biscuits & Snacks | 10 pkts | ₹4.20 | ₹5.00 | 6.0/day | +90 days | High velocity staple |
| `SKU02` | **Sunflower Cooking Oil (1L)** | Edible Oils | 4 pouches | ₹135.00 | ₹155.00 | 3.0/day | +120 days | ⚠️ **Stockout Risk** (1.3 days left!) |
| `SKU03` | **Dairy Milk Powder (500g)** | Dairy Products | 20 pkts | ₹180.00 | ₹210.00 | 1.0/day | +8 days | 🚨 **Near Expiry** (₹3,600 at risk!) |
| `SKU04` | **Lux Bathing Soap** | Personal Care | 35 bars | ₹28.00 | ₹35.00 | 0.5/day | +300 days | 🐢 Overstocked (70 days cover) |
| `SKU05` | **Toor Dal (1kg)** | Pulses & Grains | 6 pkts | ₹145.00 | ₹175.00 | 2.5/day | +150 days | ⚠️ **Stockout Risk** (2.4 days left!) |
| `SKU06` | **Exotic Herbal Tea (250g)** | Beverages | 25 boxes | ₹220.00 | ₹280.00 | 0.05/day | +180 days | 🛑 **Dead Stock** (₹5,500 blocked!) |

---

## 🎬 5-Step Hackathon Demo Walkthrough Script

Follow these 5 steps to demonstrate the full power of KiranaCopilot to judges:

### Step 1: Multimodal Zero-POS Voice Capture & Khata Logging
1. In the **Left Column ("Multimodal Zero-POS")**, click the **Mic icon** (or click the 1st test chip):
   > *"Parle-G 10 packet bacha hai, tel 4 packet, aur Ramesh ka 450 rupaye udhaar likh lo"*
2. Click **"Process with Fuzzy & Alias Resolution"**.
3. **What Judges See:**
   - The alias engine resolves colloquial *"tel"* to `SKU02 (Sunflower Cooking Oil)` and *"Parle-G"* to `SKU01`.
   - In the Center Column under **"Khata Ledger"**, a new credit entry for **Ramesh (₹450)** is instantly created.
   - The **Judge's X-Ray Console** records the `TOOL_CALL: parse_voice_khata_input` with the structured JSON output.

### Step 2: Distributor Bill OCR & Automated Inwarding
1. In the Left Column, click **"Load Sample Distributor Bill"**.
2. A high-fidelity invoice popup appears from **"Balaji Wholesale Distributors Pvt Ltd"** (`Invoice #BWD-2026-9042`).
3. Click **"Confirm Stock Inward & Pay Bill"**.
4. **What Judges See:**
   - Inward items are credited to inventory (`+50 pkts Parle-G`, `+20 pouches Oil`, `+15 pkts Dal`).
   - The bill total (`₹5,278.88`) is automatically deducted from the **Available Cash Budget**.
   - The X-Ray console logs `ACTION: confirm_bill_inward`.

### Step 3: Festival Surge Mode & Imminent Stockout Threat
1. Toggle the **"Upcoming Festival Surge (Diwali / Weekend)"** switch to **ON**.
2. **What Judges See:**
   - Instant badge shows **+80% demand multiplier** applied to Cooking Oil, +70% on Dal, +60% on Snacks.
   - In the Center Column, Cooking Oil daily demand jumps to `5.4 pouches/day`, reducing stock coverage to just `0.7 days`.
   - The **Top KPI Bar** highlights critical stockout threats before Thursday's distributor delivery.

### Step 4: The Agentic ReAct Replenishment Loop & Hard Guardrail
1. Click the top button: **"Run Full Agentic Audit"**.
2. Watch the **Judge's X-Ray Console** step through the ReAct loop:
   - `OBSERVE`: `get_shop_state()` fetches catalog and current cash budget.
   - `ANALYZE`: `forecast_demand(festival_mode=True)` identifies 2 imminent stockouts.
   - `AUDIT`: `detect_expiry_and_dead_stock()` flags ₹3,600 near-expiry risk (Dairy Milk Powder) and ₹5,500 dead capital (Herbal Tea).
   - `PLAN`: `optimize_order(budget=20000)` computes replenishment covering 7-day surge while strictly respecting the cash limit.
   - `GUARDRAIL`: `request_owner_approval()` halts execution with status `AWAITING_OWNER_APPROVAL`.
3. An interactive **Order Approval Card** appears in the shopkeeper panel with a pre-formatted bilingual WhatsApp draft to Balaji Wholesale.
4. Click **"✓ Approve & Send to Balaji"**.
   - Agent triggers `send_order_and_track()`. Order status transitions to `SENT_TO_DISTRIBUTOR`.

### Step 5: Real-World Autonomous Exception Recovery
1. In the Order Card, click the red button: **"Simulate Distributor Stockout (1L Oil Out of Stock)"**.
2. A distributor WhatsApp simulation pops up:
   > *"Bhaiya, Sunflower Cooking Oil 1L pouch is out of stock in warehouse! Only 5L Fortune Jar (₹590 cost) or Palm Oil available."*
3. **Watch the Agent Autonomously Recover in the X-Ray Console:**
   - Event `RECOVERY: handle_distributor_stockout` is fired.
   - The agent evaluates alternatives, swaps the out-of-stock 1L pouches with **3x Fortune 5L Family Jars** (high festive demand), adjusts total costs, drafts a revised counter-proposal on WhatsApp, and re-engages the **Hard Guardrail** asking the shopkeeper for re-approval.
4. Click **"Reset Demo DB"** at any time to return StoreyStores to its starting state for the next judge!

---

## 🛠️ Agent Tools Specification

The AI agent orchestrator operates with 8 defined tools:

| Tool Name | Type | Purpose |
|---|---|---|
| `get_shop_state()` | Read | Reads inventory, cash budget, festival status, and outstanding khata. |
| `forecast_demand(festival_mode)` | Analytics | Computes category multipliers (+80% surge) and days of stock left. |
| `detect_expiry_and_dead_stock()` | Analytics | Detects items expiring in $\le 15$ days and velocity $< 0.1$/day. |
| `optimize_order(budget)` | Optimization | Solves budget-constrained knapsack replenishment ($Cost \le Budget$). |
| `draft_distributor_whatsapp(items)` | Generation | Formats professional Hinglish/English WhatsApp order dispatch. |
| `request_owner_approval(order)` | **Guardrail** | Pauses execution for mandatory Shopkeeper verification. |
| `send_order_and_track(order_id)` | Action | Transmits WhatsApp order and logs estimated delivery. |
| `handle_distributor_stockout(...)` | **Recovery** | Autonomous replanning when distributor inventory is depleted. |

---

## 🧪 Automated Testing
Run the comprehensive test suite verifying all 9 core flows:
```bash
python backend/test_api.py
```
Expected output:
```
1. Testing GET /api/state... [OK]
2. Testing Voice Zero-POS... [OK]
3. Testing Festival Mode toggle... [OK]
4. Testing Full Agentic Audit Loop... [OK]
5. Testing Owner Approval... [OK]
6. Testing Exception Handling Demo... [OK]
7. Testing Distributor Bill OCR... [OK]
8. Testing Agent Traces... [OK]
9. Testing Reset Demo State... [OK]
ALL BACKEND API TESTS PASSED SUCCESSFULLY! 🚀
```

---

## 💡 Why This Wins Hackathons
1. **Solves an authentic Bharat problem:** 12 million Kirana stores represent 88% of India's retail grocery market, yet zero existing enterprise tools fit their reality.
2. **True Agentic ReAct Loop:** Not a chatbot or wrapper; it executes a genuine `Observe -> Analyze -> Plan -> Guardrail -> Act -> Recover` workflow with visible JSON traces.
3. **100% Reliable Offline Demo Mode:** Works without API keys, flaky internet, or rate limits on stage.
4. **Zero-POS Design:** Voice + colloquial alias resolution + invoice OCR eliminates barcode scanners.
