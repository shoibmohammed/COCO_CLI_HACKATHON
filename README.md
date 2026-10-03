# MFG Predictive Maintenance & OEE Command Center

**An end-to-end, Snowflake-native predictive maintenance platform that detects machine failures before they happen, diagnoses root causes using AI, and orchestrates governed remediation — all without leaving Snowflake.**

---

## The Problem

Unplanned downtime costs manufacturers **$50B+ annually**. Traditional maintenance is reactive — machines fail, production stops, emergency repairs burn cash. Condition-based monitoring generates alerts, but engineers drown in false positives with no context on *what* is failing, *why*, or *what to do*.

## The Solution

This platform closes the loop from **sensor anomaly to maintenance action** in a single governed pipeline:

1. **Detect** — ML classification predicts failures 6 hours before they happen
2. **Diagnose** — Cortex Search retrieves the exact SOP from the maintenance knowledge base
3. **Remediate** — An agentic workflow creates a governed work order with parts and downtime estimates
4. **Approve** — A human reviews and approves (governance gate — no auto-execution)
5. **Dispatch** — Jira tickets are created and Email + Slack notifications are sent
6. **Audit** — Every action is logged in an immutable trail

---

## Live Demo Access

| Detail | Value |
|---|---|
| **Streamlit App** | `PM_OEE_DB.CORE.MFG_PM_COMMAND_CENTER` |
| **Account** | `WVUZIZU-WV57087` |
| **Judge Login** | Username: `HACKATHON_JUDGE` / Password: `JudgeDemo2026!` |

---

## Architecture

```
IoT Sensors (Snowpipe)
    |
    v
SENSOR_READINGS ──> Dynamic Tables (1-min lag)
    |                   |                    |
    v                   v                    v
MACHINE_HEALTH_RT   RISK_SCORES_RT     OEE_METRICS_RT
    |                   |
    v                   v
ML Classification ──> MACHINE_RISK_UNIFIED
    |
    v
Task DAG (every 5 min)
    |
    +──> Stage 1: SCAN_AND_DETECT_ANOMALIES (refresh DTs + ML inference)
    |
    +──> Stage 2: AUTO_DRAFT_WORK_ORDERS (agentic remediation)
    |
    +──> Stage 3: PROCESS_AUTOMATIC_NOTIFICATIONS (email + Slack)
    |
    v
Cortex Agent (PM_AGENT) ──> MCP Server ──> Atlassian MCP (Jira)
    |
    v
Streamlit Command Center (12 machines, 11 pages)
```

---

## Snowflake Platform Features Used

| # | Feature | How It's Used |
|---|---|---|
| 1 | **Dynamic Tables** (3) | Real-time fusion of sensor, risk, and OEE data with 1-minute target lag |
| 2 | **Snowflake ML Classification** | `PM_FAILURE_MODEL` trained on labeled sensor data; predicts 6-hour failure window |
| 3 | **Cortex Search** | Hybrid vector + keyword search over 3 maintenance SOPs (Bearing Manual, Coolant SOP, Drive Belt SOP) |
| 4 | **Cortex Agent** | `PM_AGENT` with 4 tools: MaintenanceSearch, GetMachineContext, GetFleetContext, CreateWorkOrder |
| 5 | **MCP Server (Internal)** | `PM_MCP_SERVER` exposing agent + search + procedures to CoCo and external MCP clients |
| 6 | **MCP Server (External)** | `ATLASSIAN_MCP_SERVER` — native OAuth DCR connector for Jira + Confluence |
| 7 | **Tasks (DAG)** | 3-stage pipeline: anomaly scan -> work orders -> notifications, every 5 minutes |
| 8 | **Alerts** | `HIGH_RISK_MACHINE_ALERT` — scans for risk >= 0.75 with 1-hour dedup |
| 9 | **Snowpipe** | `SENSOR_INGEST_PIPE` for CSV-based IoT telemetry ingestion |
| 10 | **Notification Integration (Email)** | `MFG_EMAIL_NOTIFICATION` — Snowflake-native email dispatch |
| 11 | **Notification Integration (Slack)** | `MFG_SLACK_NOTIFICATION` — webhook-based Slack alerts |
| 12 | **Streamlit in Snowflake** | 11-page command center with live data from Dynamic Tables |
| 13 | **Stored Procedures** (10) | Governed SQL procedures for ML inference, RUL estimation, remediation, notifications |
| 14 | **Marketplace Data** | 25,000 supply chain records from `SNOWFLAKE_SAMPLE_DATA.TPCH_SF1` |
| 15 | **CoCo Skills** (3) | anomaly-detection, work-order-drafting, maintenance-notify |

---

## Fleet Overview (12 Machines)

| Machine | Name | Type | Plant | Line | Criticality |
|---|---|---|---|---|---|
| Machine_01 | CNC Spindle A | CNC | Plant A | Line 1 | MEDIUM |
| Machine_02 | CNC Spindle B | CNC | Plant A | Line 1 | HIGH |
| Machine_03 | Precision Mill C | MILL | Plant A | Line 2 | CRITICAL |
| Machine_04 | Precision Mill D | MILL | Plant A | Line 2 | HIGH |
| Machine_05 | Hydraulic Press E | PRESS | Plant A | Line 3 | HIGH |
| Machine_06 | Surface Grinder F | GRINDER | Plant A | Line 3 | MEDIUM |
| Machine_07 | CNC Lathe G | LATHE | Plant B | Line 4 | CRITICAL |
| Machine_08 | CNC Lathe H | LATHE | Plant B | Line 4 | MEDIUM |
| Machine_09 | Injection Molder I | MOLDER | Plant B | Line 5 | HIGH |
| Machine_10 | Welding Robot J | ROBOT | Plant B | Line 5 | CRITICAL |
| Machine_11 | Heat Treat Furnace K | FURNACE | Plant B | Line 6 | HIGH |
| Machine_12 | Assembly Robot L | ROBOT | Plant B | Line 6 | MEDIUM |

---

## Data Model

### Core Tables (PM_OEE_DB.CORE)

| Table | Purpose | Rows |
|---|---|---|
| MACHINE_MASTER | 12-machine fleet registry | 12 |
| MACHINE_BASELINES | Statistical baselines per machine | 12 |
| ERP_ASSETS | Supplier, warranty, part numbers | 12 |
| SPARE_PARTS | Inventory with reorder points | 11 |
| MAINTENANCE_HISTORY | Historical failure records | 13 |
| SENSOR_READINGS | IoT telemetry (5-min intervals) | 2,400+ |
| PRODUCTION_EVENTS | OEE calculation inputs | 2,400+ |
| MAINTENANCE_DOCS | SOP text chunks for Cortex Search | 3 |
| ML_TRAINING_DATA | Labeled training set for ML model | 288 |
| ML_RISK_PREDICTIONS | Latest ML inference results | 12 |
| RUL_PREDICTIONS | Remaining Useful Life estimates | Per request |
| WORK_ORDERS | Governed work orders (PENDING_APPROVAL -> APPROVED) | Per scenario |
| ALERT_LOG | System alert events with dedup | Per scenario |
| NOTIFICATION_AUDIT | Email + Slack dispatch audit trail | Per scenario |
| JIRA_TICKET_AUDIT | Jira ticket creation audit | Per scenario |
| RAW_EXTERNAL_SUPPLY_CHAIN | Marketplace supply chain data | 25,000 |
| EXTERNAL_PART_CATALOG | Aggregated part catalog | 23,855 |

### Dynamic Tables (1-minute lag)

| Dynamic Table | Purpose |
|---|---|
| MACHINE_HEALTH_RT | Latest telemetry per machine joined with master + ERP |
| RISK_SCORES_RT | Z-score risk calculation per sensor reading |
| OEE_METRICS_RT | Availability, Performance, Quality, OEE per machine |

---

## Key Innovation: Governed Agentic Workflow

Most AI systems either **auto-execute** (dangerous) or **only advise** (slow). This platform introduces a **governed middle path**:

```
AI Detects Anomaly
    |
    v
Agent Diagnoses + Checks Inventory + Creates Work Order
    |
    v
Work Order Status: PENDING_APPROVAL  <-- Governance Gate
    |
    v
Human Reviews and Approves
    |
    v
Work Order Status: APPROVED
    |
    v
Jira Ticket Created + Notifications Sent
```

The AI does the heavy lifting (diagnosis, parts lookup, SOP retrieval, downtime estimation). But **no external action happens without human approval**. This is the pattern production manufacturing environments actually need.

---

## CoCo Skills (Cortex Code Integration)

Three skills orchestrate the maintenance lifecycle:

| Skill | Trigger Phrases | What It Does |
|---|---|---|
| **anomaly-detection** | "Scan for anomalies", "Check machine health" | Refreshes DTs, runs ML inference, logs alerts |
| **work-order-drafting** | "Create a work order", "Remediate Machine_03" | Diagnoses failure, checks inventory, creates governed WO |
| **maintenance-notify** | "Notify the team", "Send alerts" | Dispatches email + Slack for unnotified critical alerts |

The Task DAG chains all three: `anomaly-detection -> work-order-drafting -> maintenance-notify` every 5 minutes.

---

## Project Structure

```
MFG_Predictive_Maintenance/
|-- streamlit_app.py              # Main Streamlit entry point
|-- config.py                     # App configuration
|-- snowflake_connection.py       # Session management
|-- snowflake.yml                 # Snowflake project definition
|-- pages/                        # 11 Streamlit pages
|   |-- command_center.py         # Fleet health dashboard
|   |-- alerts.py                 # ML triage & alert history
|   |-- machine_intelligence.py   # Deep-dive diagnosis + remediation
|   |-- ai_copilot.py             # Conversational AI assistant
|   |-- work_orders.py            # Governed work order management
|   |-- supply_chain.py           # Marketplace supply chain data
|   |-- what_if_simulator.py      # Scenario injection
|   |-- reports.py                # Report generation
|   |-- system_status_page.py     # System health
|   +-- settings_page.py          # Configuration
|-- services/                     # 23 backend services
|-- components/                   # 9 reusable UI components
|-- skills/                       # 3 CoCo skill definitions
|-- sql/                          # 26 deployment SQL scripts
|-- data/maintenance_manuals/     # 3 SOP text files
+-- tests/                        # 35 test files
```

---

## Deployment

### One-Command Reset

```sql
CALL PM_OEE_DB.CORE.RESET_DEMO_STATE();
```

Resets all 12 machines to healthy baseline, clears transactional data, refreshes Dynamic Tables, and runs ML inference.

### 9-Stage Live Demo

The full demo runs through: Clean Slate -> Inject Failure -> ML Detection -> AI Diagnosis -> Work Order -> Human Approval -> Jira Ticket -> Email + Slack Notifications -> Executive Summary.

Each stage is driven by a single procedure call — no manual SQL required.

---

## What Makes This Different

1. **Predict Before Failure** — Unified OT + ERP + OEE stream through Dynamic Tables with ML scoring
2. **Ground Before Act** — Cortex Search retrieves evidence from SOPs before any recommendation
3. **Govern Before Execute** — Human approval gate between AI recommendation and external action

---

## Built With

- Snowflake (Dynamic Tables, ML, Cortex Search, Cortex Agent, MCP, Tasks, Alerts, Snowpipe, Streamlit)
- Cortex Code (CoCo) for deployment, skill authoring, and orchestration
- Python (Streamlit UI, Snowpark procedures)
- Atlassian MCP (Jira integration via OAuth DCR)
