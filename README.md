# Solar Design AI Agent - Architecture & Sizing Guide

An AI-powered solar PV design, system sizing, and Bill of Quantities (BOQ) generation suite built with **Streamlit** and multi-model AI orchestration (**Featherless AI / OpenAI-compatible models**, **GitHub Models (`gpt-4o`)**, and **Google Gemini**), backed by **Supabase** for project data persistence.

---

## 🚀 How the Agent Works

The agent acts as a co-pilot for solar engineers, translating raw inputs (like utility bills, appliance lists, roof blueprints, or time-series logger files) into complete engineering designs. 

The architecture consists of three interconnected layers:
1. **The Orchestration Layer (`agent/orchestrator.py`):** Acts as the supervisor. It parses text instructions, coordinates between sizers, calls appropriate sizers or file parsers, and generates the natural language design logic.
2. **The Sizing Engine (`agent/system_sizer.py`):** A deterministic math engine that applies exact IEC 62548, IEC 60364, and AS/NZS 4509 standards to size components, wires, and safety systems.
3. **The Data Layer (`db/queries.py`):** Saves user configurations, chat history, and system designs to Supabase in real-time, allowing users to restore state seamlessly upon logging back in.

---

## 🛠️ Detailed Feature Descriptions & Engineering Formulas

### 1. Load Analysis & Meter Data Sizing Agents
The system sizing logic is divided into three specialized parts to handle each energy data source independently and efficiently:
*   **Load Profile Sizer (`size_system_by_load_profile`):** Specifically processes discrete manual lists of appliances and connected loads. Sums peak demand and active/apparent energy schedules directly.
*   **Logged Data Sizer (`size_system_by_logged_data`):** Specifically processes time-series logger logs (e.g., CSV/Excel). Performs weekday log filtering, interval length parsing, daily totals aggregation, and worst-case weekday selection.
*   **Bill Analysis Sizer (`size_system_by_bill_analysis`):** Specifically processes utility bills (e.g., monthly kWh and billing days). Estimates peak demand using load factors (Residential: 0.3, Commercial: 0.5, Industrial: 0.7) and estimates power factors where necessary.

These sizers extract design parameters ($E_{\text{daily}}$, $P_{\text{peak}}$, $S_{\text{peak}}$) and pass them to a unified core calculation function (`_execute_core_sizing_math`) to execute exact workbook sizing.

---

### 1.1 Sizing Formulas & Equations

#### Formulas & Equations:
*   **Apparent Power ($S$):**
    $$S_i = \frac{P_i}{PF_i}$$
    *Where $P_i$ is the active power in Watts, and $PF_i$ is the power factor (default is $0.85$).*
*   **Daily Energy ($E_{\text{daily}}$) for Appliance Schedules:**
    $$E_{\text{daily}} = \sum (P_i \times \text{Qty}_i \times \text{Hours Per Day}_i)$$
*   **Daily Energy ($E_{\text{daily}}$) for Time-Series Logged Data:**
    $$E_{\text{daily}} = \left( \sum_{k=1}^{N} P_k \right) \times \Delta t_{\text{hours}}$$
    *Where $\Delta t_{\text{hours}}$ is the log interval in hours (e.g., $0.25$ for 15-minute logs).*

---

### 2. Solar PV Sizing & Module Quantity Estimation (Rule 1)
PV array capacity is determined based on the daily energy consumption and the location's specific **Peak Sun Hours (PSH)**. No system losses are applied during direct sizing per standard user workbook directives.

#### Formulas & Equations:
*   **Required PV Capacity ($P_{\text{pv, req}}$ in kWp):**
    $$P_{\text{pv, req}} = \frac{E_{\text{daily}}}{PSH \times 1000}$$
*   **Number of Modules ($N_{\text{panels}}$) - Rule 1:**
    $$N_{\text{panels}} = \left\lceil \frac{P_{\text{pv, req}}}{P_{\text{panel, Wp}} / 1000} \right\rceil$$
    *Where $P_{\text{panel, Wp}}$ is the single panel rating in Watts (e.g., 625Wp).*
*   **Actual PV Capacity ($P_{\text{pv, actual}}$ in kWp):**
    $$P_{\text{pv, actual}} = \frac{N_{\text{panels}} \times P_{\text{panel, Wp}}}{1000}$$

---

### 3. Inverter Sizing & Architecture Selection
The active/apparent demand of the system is scaled with a **$1.25\times$ safety margin** to protect the inverter against overload and transient start-up surges.
*   **Hybrid / Off-Grid systems:** Sized against **Apparent Power (S in kVA)** to accommodate low power factors and inductive starting currents.
*   **Grid-Tied systems:** Sized against **Active Power (P in kW)**.

#### Formulas & Equations:
*   **Inverter Rating ($P_{\text{inv, req}}$):**
    $$P_{\text{inv, req}} = \max\left(P_{\text{pv, actual}}, \frac{P_{\text{peak}} \times 1.25}{1000}\right)$$
*   **Inverter Selection:** The system matches $P_{\text{inv, req}}$ to standard manufacturer sizes (e.g., Residential: 3/5/8/10/12/15kW; Commercial/Industrial: 20/30/50/80/100/150kW) and calculates the required quantity ($N_{\text{inverters}}$).
*   **Brand & Architecture Rules:**
    *   *Grid-Tied:* Defaults to Huawei SUN2000 Series (High Voltage: 1100V DC).
    *   *Hybrid / Off-Grid ($\le 15$kW & $48$V):* Defaults to Deye/Sunsynk/Solis Low Voltage Hybrid (LV: 48V Battery / 500V DC Voc).
    *   *Hybrid / Off-Grid ($> 15$kW or HV):* Defaults to High Voltage Hybrid architecture (HV: 1000V DC Voc / 384V BESS).

---

### 4. MPPT & PV Stringing Calculations
String configurations are calculated to avoid overvoltage under extreme cold temperatures while maximizing MPPT performance.

#### Formulas & Equations:
*   **Temperature-Adjusted Open-Circuit Voltage ($V_{oc,\text{adj}}$):**
    $$V_{oc,\text{adj}} = V_{oc} \times \left[ 1 + K_v \times (T_{\min} - 25) \right]$$
    *Where $V_{oc}$ is the nominal module open-circuit voltage, $K_v$ is the temperature coefficient (default $-0.0029$ V/°C), and $T_{\min}$ is the minimum expected ambient temperature (default $10^\circ$C).*
*   **Maximum Modules per String ($N_{\text{string, max}}$):**
    $$N_{\text{string, max}} = \left\lfloor \frac{V_{\text{inv, max}}}{V_{oc,\text{adj}}} \right\rfloor$$
    *Where $V_{\text{inv, max}}$ is the maximum allowable inverter DC input voltage (e.g., 1000V or 1100V).*
*   **PV Input Power Limit per MPPT:**
    $$\text{Max MPPT Input Power} = \frac{P_{\text{inv, std}} \times \text{Overloading Factor}}{N_{\text{mppts}}}$$
    *Where overloading factor is $1.3$ for LV inverters and $1.5$ for HV commercial inverters.*
*   **Panels per MPPT:**
    $$\text{Panels per MPPT} = \left\lfloor \frac{\text{Max MPPT Input Power}}{P_{\text{panel, Wp}} / 1000} \right\rfloor$$

---

### 5. Battery Sizing (Rule 2)
Autonomy calculations determine the battery bank size using a **mandatory $1.25\times$ aging and degradation factor** (Rule 2) to guarantee capacity throughout a 10-year warranty cycle.

#### Formulas & Equations:
*   **Base Battery Capacity ($E_{\text{bess, base}}$ in kWh):**
    $$E_{\text{bess, base}} = \frac{E_{\text{daily}} \times \text{Days of Autonomy}}{DoD}$$
    *Where $DoD$ is the depth of discharge (default $0.80$ for Lithium Chemistry).*
*   **Target Battery Capacity ($E_{\text{bess, req}}$) - Rule 2:**
    $$E_{\text{bess, req}} = E_{\text{bess, base}} \times 1.25$$
*   **Number of Battery Modules ($N_{\text{batteries}}$):**
    $$N_{\text{batteries}} = \left\lceil \frac{E_{\text{bess, req}}}{E_{\text{module, kWh}}} \right\rceil$$
    *Where $E_{\text{module, kWh}}$ is the module capacity (default 14.33 kWh per module).*
*   **Battery Stacks/Racks:**
    $$N_{\text{racks}} = \left\lceil \frac{N_{\text{batteries}}}{9} \right\rceil$$
    *(Maximum 9 modules per vertical high-voltage stack).*

---

### 6. Cable & Protection Sizing
Implements standard copper wire sizing calculations based on allowable voltage drop (max 2% for DC strings and 5% for AC circuits) and current-carrying capacities.

#### Formulas & Equations:
*   **DC Cable Area Calculation ($A_{\text{dc}}$ in mm²):**
    $$A_{\text{dc}} = \frac{I_{mp} \times \rho_{\text{copper}} \times 2 \times L_{\text{dc}}}{V_{\text{allow, dc}}}$$
    *Where $I_{mp}$ is the module current, $L_{\text{dc}}$ is the one-way distance ($50$m), $\rho_{\text{copper}}$ is the resistivity of copper ($0.0178$ $\Omega\cdot\text{mm}^2/\text{m}$), and $V_{\text{allow, dc}}$ is the allowable voltage drop ($V_{\text{string}} \times 0.02$). Recommended size is rounded up to standard sizes: $4\text{ mm}^2$ or $6\text{ mm}^2$.*
*   **AC Current Sizing ($I_{\text{ac}}$):**
    *   **Single-Phase (1-Phase / 230V):**
        $$I_{\text{ac}} = \frac{P_{\text{inv, std}} \times 1000}{V_{\text{ac}} \times 0.9}$$
    *   **Three-Phase (3-Phase / 400V):**
        $$I_{\text{ac}} = \frac{P_{\text{inv, std}} \times 1000}{\sqrt{3} \times V_{\text{ac}} \times 0.9}$$
*   **AC Breaker Sizing ($I_{\text{breaker}}$):**
    $$I_{\text{breaker}} = \left\lceil \frac{I_{\text{ac}} \times 1.25}{10} \right\rceil \times 10$$
*   **AC Cable Area ($A_{\text{ac}}$):** Selected based on AC current thresholds ($16\text{ mm}^2 \le 60\text{A}$, $25\text{ mm}^2 \le 100\text{A}$, $50\text{ mm}^2 \le 160\text{A}$, $95\text{ mm}^2 > 160\text{A}$).
*   **AC Voltage Drop Calculation ($V_{\text{drop, ac}}$):**
    $$V_{\text{drop, ac}} = K_{\text{phase}} \times I_{\text{ac}} \times R_{\text{cable}} \times \left( \frac{L_{\text{ac}}}{1000} \right)$$
    *Where $K_{\text{phase}} = \sqrt{3}$ for 3-phase systems and $2.0$ for 1-phase systems, $L_{\text{ac}}$ is the AC run ($100$m), and $R_{\text{cable}}$ is the temperature-adjusted copper wire resistance per km ($1.15$ $\Omega/\text{km}$ for $16\text{ mm}^2$, $0.727$ $\Omega/\text{km}$ for $25\text{ mm}^2$, $0.387$ $\Omega/\text{km}$ for $50\text{ mm}^2$).*
*   **AC Voltage Drop Percentage:**
    $$\%V_{\text{drop, ac}} = \left( \frac{V_{\text{drop, ac}}}{V_{\text{ac}}} \right) \times 100$$
*   **DC Battery Breaker Sizing ($I_{\text{batt, breaker}}$):**
    $$I_{\text{batt, max}} = \frac{P_{\text{inv, std}} \times 1000}{V_{\text{bess, dc}}}$$
    $$I_{\text{batt, breaker}} = \max\left(125\text{A}, \left\lceil \frac{I_{\text{batt, max}} \times 1.25}{25} \right\rceil \times 25\right)$$
    *Where $V_{\text{bess, dc}}$ is the DC system battery voltage (48V or 384V).*

---

### 7. Bill of Quantities (BOQ) Generator
Generates procurement-ready lists in Excel (`.xlsx`) and Markdown format, broken down into 11 procurement categories without pricing:
1. **Solar PV Modules:** Total quantity and module power rating.
2. **Mounting Structure & Hardware:** Clamps, rails, hooks, and tilt frames.
3. **Battery Energy Storage System (BESS):** Lithium battery stacks, racks, BMS, and main breakers.
4. **Charge Controller / MPPT Units:** External charge controllers (if LV/off-grid).
5. **Inverter System:** Standard hybrid/grid-tied inverters.
6. **DC Cabling & Protection:** Solar PV cables, DC fuses, isolators, and SPDs.
7. **AC Cabling & Switchgear:** AC distribution cables, main breaker MCCBs, and sub-circuits.
8. **Monitoring & Control:** Smart energy meters and communication modules.
9. **Earthing & Lightning Protection System (LPS):** Copper earth rods, tape, and grounding lines.
10. **Installation Accessories:** Cable trays, flexible conduits, warning signs, and glands.
11. **Civil & Installation Works:** Inverter plinths, cable trenching, and commissioning testing.

---

## 💾 Database Architecture

The system stores all configurations and message logs in Supabase:
*   `profiles`: Registers user accounts, credentials, and access roles (e.g. `admin`).
*   `projects`: Stores project metadata (Name, Location, System Type, Daily Load, Roof Area).
*   `chat_sessions`: Saves conversational logs, enabling users to retrieve historic chat history.
*   `system_designs`: Stores the calculated sizing outputs, cable runs, string limits, and BOQ items, linking them directly to active chat sessions for real-time loading.
