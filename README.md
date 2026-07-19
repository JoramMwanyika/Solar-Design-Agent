# Solar Design Agent

An AI-powered solar PV system sizing, design, and Bill of Quantities (BOQ) generation suite built with **Streamlit** and multi-model AI orchestration (**Featherless AI / OpenAI-compatible models**, **GitHub Models (`gpt-4o`)**, and **Google Gemini Vision API**), backed by **Supabase** for enterprise-grade authentication and project data storage.

---

## 🌟 Key Features

- 💬 **Multi-Engine AI Chat (`SolarBot`)** — Switch seamlessly between **Featherless AI** (default high-speed LLM), **GitHub Models (`gpt-4o`)**, and **Google Gemini** directly from the UI.
- 📐 **Universal Load & Meter Data Parser** — Automatically extracts, filters, and analyzes loads uploaded via CSV/Excel sheets:
  - **Standard Appliance Schedules:** Automatically detects `Appliance`, `Wattage (W/kW)`, `Apparent Power (VA/kVA)`, `Quantity`, and `Daily Hours` to calculate total connected load and daily energy consumption.
  - **Logged Meter & Time-Series Data (`Fluke / SCADA / Loggers`):** Automatically filters top metadata/header rows, identifies logging intervals, calculates **Peak Active Demand ($P_{\max}$)** and **Peak Apparent Demand ($S_{\max}$)** across the logging window, and computes daily energy consumption ($\text{Average } P \times 24\text{ hours}$).
- ☀️ **Precision Engineering & Sizing Engine** — Implements exact IEC 62548 and AS/NZS 4509 workbook equations with strict design rules for PV arrays, stringing limits, DC/AC cabling, and battery banks.
- 📋 **Automated BOQ Export** — Generates formatted, client-ready Bill of Quantities (`.xlsx` Excel and Markdown) listing exact engineering quantities without pricing.
- 📄 **Multi-Modal Report Extraction** — Upload and extract site parameters from PDF, DOCX, Excel, CSV, or site photos (`PNG/JPG`).
- 🔐 **Multi-User Auth & Role Management** — Supabase-backed authentication with admin controls and project archiving.

---

## 🛠️ Engineering Sizing Rules & Formulas

The internal calculation core (`agent/system_sizer.py`) and AI prompts strictly enforce the following engineering standards:

### 1. Inverter Sizing Basis ($P$ vs. $S$)
- **Hybrid & Off-Grid Systems:** Sized based on **Apparent Power ($S$ in kVA)** with a `1.25×` safety margin to account for power factor ($PF$) and reactive inductive surge currents.
- **Grid-Tied Systems:** Sized based on **Active Power ($P$ in kW)** with a `1.25×` safety margin.

### 2. PV Module Quantity Sizing (Rule 1)
The number of solar panels required is calculated strictly from the required array capacity divided by the rating of the selected module:
$$\text{No. of Modules} = \left\lceil \frac{\text{Total Required PV Array Capacity (kWp)}}{\text{Single Module Power Rating (kWp)}} \right\rceil$$
*Example: For a `12.50 kWp` target array using `625 Wp` (`0.625 kWp`) modules:*
$$\text{Modules} = \left\lceil \frac{12.50}{0.625} \right\rceil = 20\text{ modules}$$

### 3. Battery Energy Storage System (BESS) Capacity (Rule 2)
To guarantee multi-day autonomy and account for conversion/aging losses, battery sizing applies a mandatory **`1.25×` safety/degradation factor**:
$$\text{Total Needed BESS (kWh)} = \left[ \frac{\text{Daily Energy Consumption (kWh)} \times \text{Days of Autonomy}}{\text{Depth of Discharge (DoD)}} \right] \times \mathbf{1.25}$$
- **Why `1.25×`?** Accounts for bidirectional battery inverter round-trip losses (~10–15%) and year-10 capacity degradation (~10% safety buffer over a 10-year warranty cycle).
- **Module Sizing:** $\text{Battery Modules} = \left\lceil \frac{\text{Total Needed BESS (kWh)}}{\text{Module Capacity (e.g., 14.33 kWh)}} \right\rceil$
- **Racks/Stacks:** Maximum 9 modules per vertical HV rack (`ceil(modules / 9)`).
- **Battery Breaker:** $\text{Rating (A)} = 1.25 \times I_{\text{max charge/discharge}}$ (rounded up to standard MCCB ratings: `125A`, `160A`, `250A` at `1000Vdc`).

### 4. PV Array Stringing & Voltage Check
- **Temperature Adjustment:** $V_{oc,\text{adj}} = V_{oc} \times [1 + K \times (T_{\min} - 25^\circ\text{C})]$
- **String Length Limit:** $\text{Max Panels per String} = \lfloor V_{\text{in, max}} / V_{oc,\text{adj}} \rfloor$ (Targeting `12–19` modules per string for `1000Vdc` HV inverters).

---

## 🚀 Setup & Installation

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your API keys:
```bash
cp .env.example .env
```

Edit `.env`:
```env
# AI Models (At least one key is required; Featherless is recommended for high speed without rate limits)
FEATHERLESS_API_KEY=your_featherless_api_key
FEATHERLESS_MODEL=meta-llama/Llama-3.3-70B-Instruct
GITHUB_TOKEN=your_github_personal_access_token_for_models
GITHUB_MODEL=gpt-4o
GEMINI_API_KEY=your_gemini_api_key

# Supabase Database & Auth
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
```

### 3. Set Up Supabase Database
1. Create a project at [supabase.com](https://supabase.com).
2. Go to the **SQL Editor** and execute the contents of `db/schema.sql`.

### 4. Create First Admin User
1. In the Supabase Dashboard $\to$ **Authentication** $\to$ **Users** $\to$ **Add User**, create an account with email and password.
2. In the **SQL Editor**, grant admin privileges:
```sql
UPDATE public.profiles SET role = 'admin' WHERE id = 'your-user-uuid';
```

### 5. Launch the Application
```bash
streamlit run app.py
```

---

## 📁 Project Structure
```
Solar-Design-Agent/
├── app.py                    # Main application & routing
├── pages/
│   ├── 1_Chat.py             # AI conversational interface & quick-sizing form
│   ├── 2_My_Projects.py      # Saved project history & BOQ downloads
│   └── 3_Admin.py            # User management & system analytics
├── agent/
│   ├── orchestrator.py       # Multi-engine AI orchestrator (Featherless / GitHub / Gemini)
│   ├── system_sizer.py       # Core sizing math & workbook equations
│   ├── boq_generator.py      # Excel & Markdown BOQ generator
│   └── report_analyzer.py    # Multi-modal report & site visit extraction
├── auth/
│   ├── supabase_client.py    # Supabase connection client
│   ├── login.py              # Login & signup UI flows
│   └── admin.py              # Admin privileges management
├── db/
│   ├── schema.sql            # Database tables & RLS policies
│   └── queries.py            # CRUD operations for projects/users
├── prompts/                  # System, sizing, and BOQ instructions
│   ├── system_prompt.txt
│   ├── sizing_prompt.txt
│   └── boq_prompt.txt
├── utils/
│   └── file_parser.py        # Universal Spreadsheet & Time-Series meter log parser
├── requirements.txt
└── .env.example
```

---

## 📊 Supported System Types
| Type | Primary Power Basis | Storage | Description |
|---|---|---|---|
| 🔋 **Off-Grid** | **Apparent Power ($S$)** | Yes (With Autonomy) | Standalone systems for complete grid independence. |
| ⚡ **Hybrid** | **Apparent Power ($S$)** | Yes (Buffer/Peak Share) | Solar + BESS + Grid backup. Prioritizes self-consumption and evening shift. |
| 🌐 **Grid-Tied** | **Active Power ($P$)** | No | Direct grid-tied export systems sized against roof area or peak demand. |

---

## 📋 Bill of Quantities (BOQ) Categories
Generated BOQs are strictly organized into 11 procurement sections (`Quantities Only` — NO pricing):
1. **Solar PV Modules** (`Wp` rating & total count)
2. **Mounting Structure & Hardware** (Rails, clamps, roof hooks / ground tilt structures)
3. **Battery Energy Storage System (BESS)** (HV/LV battery stacks, BMS, racks, breakers)
4. **Charge Controller / MPPT Units** (If external charge controllers apply)
5. **Inverter System** (Hybrid / Off-grid / Grid-tied inverters)
6. **DC Cabling & Protection** (PV string cables, DC isolators, fuse holders, SPDs)
7. **AC Cabling & Switchgear** (AC distribution cables, MCCBs, RCBOs, changeover switches)
8. **Monitoring & Control** (Smart meters, data loggers, communication modules)
9. **Earthing & Lightning Protection System (LPS)** (Copper earth rods, tape, bonding cables)
10. **Installation Accessories** (Conduits, cable trays, glands, warning labels)
11. **Civil & Installation Works** (Concrete plinths, trenching, testing & commissioning)
