import math
from typing import List, Dict, Any, Tuple

def get_location_psh(location: str) -> Dict[str, Any]:
    """Returns Peak Sun Hours (PSH) for a given location (e.g. Nairobi: 3.458, Mombasa: 3.927, Kilifi: 4.032)."""
    loc = str(location).lower()
    if "nairobi" in loc or "kitengela" in loc or "kiambu" in loc:
        psh = 3.458
    elif "mombasa" in loc:
        psh = 3.927
    elif "kilifi" in loc:
        psh = 4.032
    else:
        psh = 4.5
    return {"location": location, "peak_sun_hours": psh}

def analyze_utility_bill(monthly_energy_kwh: float, billing_days: int, max_demand_kw: float = 0.0, 
                         customer_type: str = "Residential", expansion_factor: float = 0.0, 
                         reactive_energy_kvarh: float = 0.0) -> Dict[str, Any]:
    """Scenario 1: Analyze a utility bill to generate the Unified Energy Output."""
    daily_energy = monthly_energy_kwh / max(1, billing_days)
    daily_energy_adjusted = daily_energy * (1 + expansion_factor)
    
    # Estimate peak demand if not provided
    confidence = 0.95
    if max_demand_kw <= 0:
        confidence = 0.70
        # Load factor heuristics: Residential ~0.3, Commercial ~0.5, Industrial ~0.7
        lf = 0.5 if customer_type == "Commercial" else (0.7 if customer_type == "Industrial" else 0.3)
        max_demand_kw = (daily_energy_adjusted) / (24 * lf)
    else:
        lf = daily_energy_adjusted / (24 * max_demand_kw) if max_demand_kw > 0 else 1.0

    # Power Factor estimation
    pf = 0.94
    if reactive_energy_kvarh > 0 and monthly_energy_kwh > 0:
        apparent_energy = math.sqrt(monthly_energy_kwh**2 + reactive_energy_kvarh**2)
        pf = monthly_energy_kwh / apparent_energy
        
    return {
        "daily_energy_kwh": round(daily_energy_adjusted, 2),
        "peak_demand_kw": round(max_demand_kw * (1 + expansion_factor), 2),
        "connected_load_kw": round(max_demand_kw * 1.5, 2), # Estimate
        "critical_load_kw": round(max_demand_kw * 0.4, 2),  # Estimate 40% critical
        "critical_energy_kwh": round(daily_energy_adjusted * 0.4, 2),
        "night_energy_kwh": round(daily_energy_adjusted * 0.5, 2), # Estimate 50% at night
        "load_factor": round(lf, 2),
        "demand_factor": 0.70,
        "diversity_factor": 1.2,
        "power_factor": round(pf, 2),
        "design_confidence": confidence
    }

def analyze_logger_data(intervals: List[Dict[str, Any]], interval_minutes: float, expected_days: int = 0) -> Dict[str, Any]:
    """
    Scenario 2: Analyze time-series logger data using Apparent Power (kVA).
    Groups data by day, filters for weekdays, and uses the highest energy day for sizing.
    intervals: List of dicts with 'apparent_power_kva', 'hour_of_day', 'day_of_week' (0=Mon, 6=Sun)
    """
    if not intervals:
        return analyze_utility_bill(0, 30)
        
    delta_t_hours = interval_minutes / 60.0
    
    # Calculate total weekday logged hours for the completeness check
    weekday_intervals_all = [i for i in intervals if i.get('day_of_week', 0) < 5]
    total_logged_hours = len(weekday_intervals_all) * delta_t_hours
    
    # If the logged data is not full, ignore it during sizing
    if expected_days > 0 and total_logged_hours < (expected_days * 24 * 0.8): # Require at least 80% completeness
        return analyze_utility_bill(0, 30)
        
    # Group intervals by calendar day (by detecting changes in day_of_week)
    days_data = []
    current_day = []
    current_dow = None
    
    for i in intervals:
        dow = i.get('day_of_week')
        if dow != current_dow:
            if current_day:
                days_data.append((current_dow, current_day))
            current_day = []
            current_dow = dow
        current_day.append(i)
        
    if current_day:
        days_data.append((current_dow, current_day))
        
    # Filter for weekdays only (Monday to Friday, day_of_week 0 to 4) and check 24-hour completeness
    expected_count_per_day = 86400.0 / max(1.0, delta_t_hours * 3600.0)
    
    valid_weekday_days = []
    for dow, day_intervals in days_data:
        if dow is not None and dow < 5:
            if len(day_intervals) >= 0.90 * expected_count_per_day:
                valid_weekday_days.append(day_intervals)
                
    if not valid_weekday_days:
        valid_weekday_days = [day_intervals for dow, day_intervals in days_data if dow is not None and dow < 5]
        
    if not valid_weekday_days:
        valid_weekday_days = [day_intervals for _, day_intervals in days_data]
        
    if not valid_weekday_days:
        return analyze_utility_bill(0, 30)
        
    # Find the day with the highest total power sum and energy
    max_power_sum = -1.0
    max_energy = 0.0
    best_day_intervals = []
    
    for day_intervals in valid_weekday_days:
        power_sum = sum(i.get('apparent_power_kva', i.get('active_power_kw', 0) / 0.94) for i in day_intervals)
        energy = power_sum * delta_t_hours
        if power_sum > max_power_sum:
            max_power_sum = power_sum
            max_energy = energy
            best_day_intervals = day_intervals
            
    if not best_day_intervals:
        return analyze_utility_bill(0, 30)
        
    # Calculate sizing metrics using ONLY the worst-case (highest energy) day
    peak_demand = max((i.get('apparent_power_kva', i.get('active_power_kw', 0) / 0.94) for i in best_day_intervals), default=0.0)
    daily_energy_avg = max_energy
    
    # Night load (18:00 to 06:00) for the best day
    night_intervals = [i for i in best_day_intervals if i.get('hour_of_day', 12) >= 18 or i.get('hour_of_day', 12) < 6]
    night_energy = sum(i.get('apparent_power_kva', i.get('active_power_kw', 0) / 0.94) * delta_t_hours for i in night_intervals)
    
    lf = daily_energy_avg / (24 * peak_demand) if peak_demand > 0 else 1.0
    
    return {
        "daily_energy_kwh": round(daily_energy_avg, 2), # Sized in kVAh
        "peak_demand_kw": round(peak_demand, 2), # Sized in kVA
        "connected_load_kw": round(peak_demand * 1.2, 2),
        "critical_load_kw": round(peak_demand * 0.5, 2),
        "critical_energy_kwh": round(daily_energy_avg * 0.5, 2),
        "night_energy_kwh": round(night_energy, 2),
        "load_factor": round(lf, 2),
        "demand_factor": 0.8,
        "diversity_factor": 1.1,
        "power_factor": 1.0, # Treated as 1.0 because we are already using apparent power (kVA)
        "design_confidence": 0.99 # Logger data is highly confident
    }

def analyze_appliance_list(appliances: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Scenario 3: Analyze a manual list of appliances.
    appliances: List of dicts with 'rated_power_w', 'qty', 'hours_per_day', 'simultaneous', 'priority' (Critical/Essential/Non-critical)
    """
    total_energy_wh = 0.0
    connected_load_w = 0.0
    simultaneous_demand_w = 0.0
    critical_load_w = 0.0
    critical_energy_wh = 0.0
    
    for app in appliances:
        p_w = app.get('rated_power_w', 0)
        qty = app.get('qty', 1)
        hpd = app.get('hours_per_day', 1.0)
        
        load_w = p_w * qty
        energy_wh = load_w * hpd
        
        total_energy_wh += energy_wh
        connected_load_w += load_w
        
        if app.get('simultaneous', True):
            simultaneous_demand_w += load_w
            
        if app.get('priority', '').lower() in ['critical', 'essential']:
            critical_load_w += load_w
            critical_energy_wh += energy_wh

    peak_demand_kw = simultaneous_demand_w / 1000.0
    connected_load_kw = connected_load_w / 1000.0
    daily_energy_kwh = total_energy_wh / 1000.0
    
    demand_factor = peak_demand_kw / connected_load_kw if connected_load_kw > 0 else 1.0
    lf = daily_energy_kwh / (24 * peak_demand_kw) if peak_demand_kw > 0 else 1.0
    
    return {
        "daily_energy_kwh": round(daily_energy_kwh, 2),
        "peak_demand_kw": round(peak_demand_kw, 2),
        "connected_load_kw": round(connected_load_kw, 2),
        "critical_load_kw": round(critical_load_w / 1000.0, 2),
        "critical_energy_kwh": round(critical_energy_wh / 1000.0, 2),
        "night_energy_kwh": round(daily_energy_kwh * 0.4, 2), # Estimate if schedules not strictly mapped
        "load_factor": round(lf, 2),
        "demand_factor": round(demand_factor, 2),
        "diversity_factor": 1.22,
        "power_factor": 0.94,
        "design_confidence": 0.97
    }

def size_pv_array(daily_energy_kwh: float, psh: float, peak_demand_kw: float, panel_wp: float, pr: float = 1.0) -> Dict[str, Any]:
    """
    Calculates the required PV kWp and panel quantity directly: Required DC Capacity (kWp) = Daily Energy / PSH (no losses included).
    """
    if daily_energy_kwh > 0:
        required_pv_kwp = daily_energy_kwh / max(0.1, psh)
    else:
        required_pv_kwp = max(5.0, peak_demand_kw * 1.2)
        
    single_module_kw = panel_wp / 1000.0
    panel_qty = max(1, math.ceil(required_pv_kwp / single_module_kw))
    total_pv_kwp = (panel_qty * panel_wp) / 1000.0
    
    return {
        "required_pv_kwp": required_pv_kwp,
        "panel_qty": panel_qty,
        "total_pv_kwp": total_pv_kwp
    }

def calculate_stringing(panel_qty: int, panel_voc: float, panel_vmp: float, max_inverter_vin: float, 
                        tmin_celsius: float, temp_coeff_k: float, panel_wp: float = 625.0,
                        inverter_kw_std: float = 150.0, num_mppts: int = 8, inverter_brand: str = "") -> Dict[str, Any]:
    """
    Calculates maximum panels per string, panels per MPPT, and total strings per user directives
    using exact inverter datasheet specifications and balanced layout distribution.
    """
    from agent.system_sizer import load_inverter_specs, find_stringing_distribution, build_stringing_grid, select_inverter_model, get_max_pv_input_power_kw
    
    if not inverter_brand:
        system_type = "grid-tied" if inverter_kw_std >= 80 else "hybrid"
        inverter_brand = select_inverter_model(system_type, inverter_kw_std, 48.0)
        
    specs = load_inverter_specs(inverter_brand)
    num_mppts = specs["num_mppts"]
    inputs_per_mppt = specs["inputs_per_mppt"]
    max_inverter_vin = specs["max_vin"]
    
    voc_adjusted = panel_voc * (1.0 + temp_coeff_k * (tmin_celsius - 25.0))
    max_panels_per_string = max(1, math.floor(max_inverter_vin / max(1.0, voc_adjusted)))
    min_panels_per_string = max(3, math.ceil(specs["mppt_min_v"] / panel_vmp))
    
    sol = find_stringing_distribution(
        panel_qty=panel_qty,
        num_mppts=num_mppts,
        inputs_per_mppt=inputs_per_mppt,
        min_panels_per_string=min_panels_per_string,
        max_panels_per_string=max_panels_per_string
    )
    
    grid = build_stringing_grid(sol, num_mppts, inputs_per_mppt)
    
    total_strings = sum(s for s, p in sol)
    active_lengths = [p for s, p in sol if s > 0]
    panels_per_string = int(round(sum(active_lengths) / len(active_lengths))) if active_lengths else 0
    string_voltage_v = panels_per_string * panel_vmp
    
    single_panel_kw = panel_wp / 1000.0
    max_pv_input_kw = specs.get("max_pv_input_power_kw") or get_max_pv_input_power_kw(inverter_brand, inverter_kw_std)
    max_kw_per_mppt = max_pv_input_kw / max(1, num_mppts)
    panels_per_mppt = max(1, math.floor(max_kw_per_mppt / single_panel_kw))
    
    return {
        "voc_adjusted": voc_adjusted,
        "max_panels_per_string": max_panels_per_string,
        "panels_per_string": panels_per_string,
        "total_strings": total_strings,
        "string_voltage_v": string_voltage_v,
        "panels_per_mppt": panels_per_mppt,
        "stringing_grid": grid
    }

def size_battery(system_type: str, daily_energy_kwh: float, days_of_autonomy: float, dod: float, 
                 battery_module_kwh: float, inverter_kw_std: float, system_voltage_dc: float) -> Dict[str, Any]:
    """
    Sizes battery capacity, module quantity, and breaker size.
    """
    if system_type not in ("off-grid", "hybrid"):
        return {"battery_qty": 0, "total_storage_kwh": 0.0, "battery_stacks": 0, "battery_breaker_a": 0.0, "needed_bess_kwh": 0.0}
        
    base_bess_kwh = (daily_energy_kwh * max(1.0, days_of_autonomy)) / max(0.1, dod)
    if system_type == "hybrid" and days_of_autonomy < 1.0:
        base_bess_kwh = max(10.0, (daily_energy_kwh * 0.6) / dod)
        
    needed_bess_kwh = base_bess_kwh * 1.25
    battery_qty = max(1, math.ceil(needed_bess_kwh / max(0.1, battery_module_kwh)))
    total_storage_kwh = battery_qty * battery_module_kwh
    battery_stacks = max(1, math.ceil(battery_qty / 9))
    
    max_charge_current = (inverter_kw_std * 1000) / max(1.0, system_voltage_dc or 384)
    battery_breaker_a = max(125.0, math.ceil((max_charge_current * 1.25) / 25) * 25)
    
    return {
        "needed_bess_kwh": needed_bess_kwh,
        "battery_qty": battery_qty,
        "total_storage_kwh": total_storage_kwh,
        "battery_stacks": battery_stacks,
        "battery_breaker_a": battery_breaker_a
    }

def size_inverter(system_type: str, peak_demand_kw: float, total_pv_kwp: float, power_factor: float = 0.94, system_voltage_dc: float = 48) -> Dict[str, Any]:
    """
    Selects standard inverter sizes based on load and PV.
    """
    # Convert active power (kW) to apparent power (kVA) if PF is provided
    peak_demand_kva = peak_demand_kw / max(0.1, power_factor)
    
    if system_type in ("off-grid", "hybrid"):
        peak_demand_kunit = peak_demand_kva * 1.25
    else:
        peak_demand_kunit = peak_demand_kw * 1.25
        
    inverter_kw = max(total_pv_kwp, peak_demand_kunit)
    
    if inverter_kw > 50:
        large_sizes = [150, 100, 80]
        best_size = 150
        best_qty = math.ceil(inverter_kw / 150)
        for s in large_sizes:
            qty = math.ceil(inverter_kw / s)
            if qty < best_qty or (qty == best_qty and s < best_size):
                best_size = s
                best_qty = qty
    elif inverter_kw >= 20:
        med_sizes = [50, 30, 20, 15]
        best_size = 50
        best_qty = math.ceil(inverter_kw / 50)
        for s in med_sizes:
            qty = math.ceil(inverter_kw / s)
            if qty <= 3:
                if qty < best_qty or (qty == best_qty and s < best_size):
                    best_size = s
                    best_qty = qty
    else:
        res_sizes = [3, 5, 8, 10, 12, 15]
        best_size = 15
        best_qty = 1
        for s in res_sizes:
            if s >= inverter_kw:
                best_size = s
                best_qty = 1
                break
        if inverter_kw > 15:
            best_size = 15
            best_qty = math.ceil(inverter_kw / 15)
            
    inverter_kw_std = float(best_size)
    inverter_qty = int(best_qty)
    inverter_kva = inverter_kw_std if system_type in ("off-grid", "hybrid") else inverter_kw_std / 0.9

    from agent.system_sizer import select_inverter_model
    inverter_brand = select_inverter_model(system_type, inverter_kw_std, system_voltage_dc)

    if system_type == "grid-tied":
        voltage_architecture = "High Voltage (HV: 1100V DC)"
        max_inverter_vin = 1100.0
        num_mppts = 10 if inverter_kw_std >= 100 else (6 if inverter_kw_std >= 80 else 4)
    else:
        if system_voltage_dc <= 48 and inverter_kw_std <= 20:
            voltage_architecture = "Low Voltage (LV: 48V BESS / 500V DC)"
            max_inverter_vin = 500.0
            num_mppts = 2
        else:
            voltage_architecture = "High Voltage (HV: 1000V DC / 384V BESS)"
            max_inverter_vin = 1000.0
            num_mppts = 8 if inverter_kw_std >= 80 else (6 if inverter_kw_std >= 30 else 4)
    
    return {
        "inverter_kw_std": inverter_kw_std,
        "inverter_kva": inverter_kva,
        "inverter_qty": inverter_qty,
        "inverter_brand": inverter_brand,
        "voltage_architecture": voltage_architecture,
        "max_inverter_vin": max_inverter_vin,
        "num_mppts": num_mppts
    }

def load_jinko_specs() -> Dict[str, Any]:
    """Loads PV panel specs from the Jinko JSON datasheet if available, otherwise returns defaults."""
    defaults = {
        "panel_wp": 625,
        "panel_voc": 49.28,
        "panel_vmp": 41.52,
        "panel_imp": 15.05,
    }
    try:
        from pathlib import Path
        import json
        jinko_path = Path(__file__).parent.parent.parent / "datasheets/pv_modules/Jinko_TigerNeo_N-Type_625W.json"
        if jinko_path.exists():
            with open(jinko_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            elec = data.get("electrical_specifications", {})
            return {
                "panel_wp": int(elec.get("rated_maximum_power_pmax_wp", defaults["panel_wp"])),
                "panel_voc": float(elec.get("open_circuit_voltage_voc_v", defaults["panel_voc"])),
                "panel_vmp": float(elec.get("maximum_power_voltage_vmp_v", defaults["panel_vmp"])),
                "panel_imp": float(elec.get("maximum_power_current_imp_a", defaults["panel_imp"])),
            }
    except Exception:
        pass
    return defaults


def size_cables(string_voltage_v: float, panel_imp: float, dc_cable_distance_m: float, total_strings: int, 
                inverter_kw_std: float, ac_cable_distance_m: float, panel_voc: float = None, panels_per_string: int = None) -> Dict[str, Any]:
    """
    Calculates DC and AC cable sizes and voltage drops.
    """
    specs = load_jinko_specs()
    if panel_voc is None:
        panel_voc = specs["panel_voc"]
    if panel_imp is None or panel_imp in (15.06, 15.05):
        panel_imp = specs["panel_imp"]
    
    if panels_per_string is None:
        panel_vmp = specs["panel_vmp"]
        panels_per_string = max(1, round(string_voltage_v / panel_vmp))
        
    dc_allowable_vd = 0.03 * (panels_per_string * panel_voc)
    rho_copper = 0.0178
    effective_L = max(50.0, dc_cable_distance_m)
    
    dc_area_calc = (panel_imp * rho_copper * 2.0 * effective_L) / max(0.1, dc_allowable_vd)
    dc_recommended_sqmm = 4 if dc_area_calc <= 4 else (6 if dc_area_calc <= 6 else 10)
    dc_total_length = effective_L * 2.0 * total_strings
    
    is_3phase = inverter_kw_std >= 10
    ac_voltage = 400.0 if is_3phase else 230.0
    if is_3phase:
        ac_current = (inverter_kw_std * 1000.0) / (math.sqrt(3) * ac_voltage * 0.9)
    else:
        ac_current = (inverter_kw_std * 1000.0) / (ac_voltage * 0.9)
        
    ac_breaker = math.ceil((ac_current * 1.25) / 10) * 10
    ac_sqmm = 16 if ac_current <= 60 else (25 if ac_current <= 100 else (50 if ac_current <= 160 else 95))
    
    r_per_km = 0.727 if ac_sqmm == 25 else (1.15 if ac_sqmm <= 16 else 0.387)
    ac_vd_v = (math.sqrt(3) if is_3phase else 2.0) * ac_current * r_per_km * (ac_cable_distance_m / 1000.0)
    ac_vd_pct = (ac_vd_v / ac_voltage) * 100.0
    
    return {
        "dc_area_calc": dc_area_calc,
        "dc_recommended_sqmm": dc_recommended_sqmm,
        "dc_total_length": dc_total_length,
        "ac_current": ac_current,
        "ac_breaker": ac_breaker,
        "ac_sqmm": ac_sqmm,
        "ac_vd_v": ac_vd_v,
        "ac_vd_pct": ac_vd_pct
    }
