# Solar Design Agent — Project Rules

## Load Profile Sizing Rule

**When performing Load Profile / Appliance List sizing, the agent MUST follow this two-step workflow:**

1. **Step 1 — Compute daily energy from loads, hours of operation, diversity factor, and utilisation factor:**
   - For each appliance: `energy_wh = rating × quantity × hours_per_day × diversity_factor × utilisation_factor`
   - Total: `daily_energy_wh = sum(energy_wh for all appliances)`

2. **Step 2 — Size ALL components from that daily energy (NOT from raw wattage sums):**
   - PV Array: `Required kWp = daily_energy_kwh / PSH`
   - Battery: `Required kWh = (daily_energy_kwh × days_autonomy) / DoD × 1.25`
   - **Inverter AC Capacity:** `ac_capacity_kw = total_pv_kwp` or `ac_capacity_kw = total_pv_kwp / 1.25`. Use this AC capacity to select the inverter model and quantity.

> This rule is enforced in code:
> - `agent/system_sizer.py` → `size_system_by_load_profile()`: passes `total_peak_w=0.0` and `total_peak_va=0.0`
> - `agent/multiagent/tools/math_tools.py` → `analyze_appliance_list()`: returns `peak_demand_kw=0.0`
> - `agent/multiagent/supervisor.py`: routing prompt contains the Load Profile rule
> - `agent/multiagent/agents.py`: `appliance_analysis_agent` and `inverter_selection_agent` goals updated
> - `prompts/sizing_prompt.txt`: Rule #6 — Load Profile workflow

**Do NOT size the inverter from the connected load sum when working with appliance lists.**

## Diversity Factor & Unit Confirmation Rule

1. **Diversity Factor:** If a Diversity Factor is present in the provided context (e.g. state or user input), you MUST use it to scale the peak demand calculation (e.g. `Maximum Demand = Sum of Connected Loads / Diversity Factor`).
2. **Unit Confirmation:** ALWAYS verify and confirm your units (`W` vs `kW`, `Wh` vs `kWh`, `VA` vs `kVA`) before returning any final sizing recommendations to ensure no order-of-magnitude errors.
