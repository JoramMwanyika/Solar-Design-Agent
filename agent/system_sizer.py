"""
System Sizing Engine for Solar PV Systems.
Supports: Off-Grid, Hybrid (Battery + Grid), and Grid-Tied systems.
Implements exact IEC/AS-NZS engineering formulas and client workbook equations:
- Stringing limits: Max panels = floor( Max Vin / (Voc * (1 + K * (Tmin - 25))) )
- DC Cable sizing: C.A (mm²) = (I * rho * 2 * L) / V.D
- AC Current & Cable sizing: I_ac = P / (sqrt(3) * V_ac * cos_phi), V.D_ac = (sqrt(3) * I * R * L) / 1000
- Battery stack & breaker sizing: Breaker = 1.25 * Max_I
"""
import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LoadItem:
    name: str
    wattage: float       # Active Power P in Watts
    quantity: int = 1
    hours_per_day: float = 1.0
    apparent_wattage: Optional[float] = None # Apparent Power S in VA
    power_factor: float = 0.85
    is_time_series: bool = False

    @property
    def daily_energy_wh(self) -> float:
        return self.wattage * self.quantity * self.hours_per_day

    @property
    def total_wattage(self) -> float:
        """Returns Active Power P in Watts."""
        return self.wattage * self.quantity

    @property
    def total_va(self) -> float:
        """Returns Apparent Power S in VA."""
        if self.apparent_wattage is not None and self.apparent_wattage > 0:
            return self.apparent_wattage * self.quantity
        pf = self.power_factor if (self.power_factor and self.power_factor > 0) else 0.85
        return self.total_wattage / pf


@dataclass
class StringingResult:
    panel_wp: int
    panel_voc: float
    max_inverter_vin: float
    tmin_celsius: float
    temp_coeff_k: float
    max_panels_per_string: int
    panels_per_mppt: int
    total_strings: int
    string_voltage_v: float


@dataclass
class CableSizingResult:
    dc_string_current_a: float
    dc_distance_m: float
    dc_allowable_vd_v: float
    dc_cable_area_sqmm: float
    dc_recommended_cable_sqmm: int
    dc_total_length_m: float
    ac_max_op_current_a: float
    ac_breaker_rating_a: float
    ac_distance_m: float
    ac_allowable_vd_v: float
    ac_cable_area_sqmm: int
    ac_voltage_drop_v: float
    ac_voltage_drop_pct: float


@dataclass
class SizingResult:
    system_type: str                  # off-grid | hybrid | grid-tied
    location: str
    peak_sun_hours: float
    
    # Load analysis & PV Array required fields
    total_peak_power_w: float
    daily_energy_wh: float
    design_energy_wh: float           # With system losses (PR)
    panel_wp: int
    panel_qty: int
    total_pv_kwp: float
    
    # Optional / defaulted fields
    total_peak_va: float = 0.0
    stringing: Optional[StringingResult] = None
    
    # Battery Bank (Off-Grid / Hybrid)
    days_of_autonomy: float = 0.0
    dod: float = 0.8                  # Depth of discharge
    battery_type: str = "Lithium HV Stack"
    battery_module_kwh: float = 14.33 # e.g. Dyness Stack280 14.33kWh
    battery_module_ah: float = 280.0
    battery_voltage: float = 51.2
    battery_qty: int = 0
    total_storage_kwh: float = 0.0
    battery_stacks: int = 0
    battery_breaker_a: float = 0.0
    
    # Inverter / Charge Controller
    inverter_kw: float = 0.0
    inverter_kva: float = 0.0
    inverter_qty: int = 1
    mppt_rating_per_unit: int = 60
    mppt_qty: int = 1
    system_voltage_dc: int = 48
    
    # Cable & Protection Sizing
    cable_sizing: Optional[CableSizingResult] = None

    @property
    def usable_storage_kwh(self) -> float:
        return round(self.total_storage_kwh * self.dod, 2)

    def to_dict(self) -> dict:
        return {
            "system_type": self.system_type,
            "location": self.location,
            "peak_sun_hours": round(self.peak_sun_hours, 2),
            "total_peak_power_w": round(self.total_peak_power_w, 1),
            "total_peak_va": round(self.total_peak_va, 1),
            "daily_energy_kwh": round(self.daily_energy_wh / 1000, 2),
            "design_energy_kwh": round(self.design_energy_wh / 1000, 2),
            "panel_wp": self.panel_wp,
            "panel_qty": self.panel_qty,
            "total_pv_kwp": round(self.total_pv_kwp, 2),
            "stringing": {
                "max_panels_per_string": self.stringing.max_panels_per_string if self.stringing else 0,
                "total_strings": self.stringing.total_strings if self.stringing else 0,
                "string_voltage_v": round(self.stringing.string_voltage_v, 1) if self.stringing else 0,
            } if self.stringing else {},
            "battery": {
                "type": self.battery_type,
                "module_kwh": self.battery_module_kwh,
                "qty": self.battery_qty,
                "total_kwh": round(self.total_storage_kwh, 2),
                "stacks": self.battery_stacks,
                "breaker_a": round(self.battery_breaker_a, 1),
            } if self.system_type in ("off-grid", "hybrid") else {},
            "inverter": {
                "kw": round(self.inverter_kw, 1),
                "kva": round(self.inverter_kva, 1),
                "qty": self.inverter_qty,
            },
            "cables": {
                "dc_sqmm": self.cable_sizing.dc_recommended_cable_sqmm if self.cable_sizing else 4,
                "dc_total_m": round(self.cable_sizing.dc_total_length_m, 1) if self.cable_sizing else 100,
                "ac_sqmm": self.cable_sizing.ac_cable_area_sqmm if self.cable_sizing else 16,
                "ac_breaker_a": round(self.cable_sizing.ac_breaker_rating_a, 1) if self.cable_sizing else 63,
                "ac_vd_pct": round(self.cable_sizing.ac_voltage_drop_pct, 2) if self.cable_sizing else 1.0,
            } if self.cable_sizing else {},
        }


# Lookup for Peak Sun Hours based on region/country keywords
PSH_TABLE = {
    "kenya": 5.5, "nairobi": 3.458, "mombasa": 6.0, "kisumu": 5.8,
    "tanzania": 5.6, "dar es salaam": 5.5, "dodoma": 5.8,
    "uganda": 5.3, "kampala": 5.1,
    "nigeria": 5.2, "lagos": 4.8, "abuja": 5.5,
    "south africa": 5.0, "johannesburg": 5.4, "cape town": 4.8,
    "ghana": 5.1, "accra": 4.9,
    "ethiopia": 5.8, "addis ababa": 5.5,
    "rwanda": 5.0, "kigali": 4.9,
    "default": 5.0,
}


def get_psh(location: str) -> float:
    loc_lower = location.lower()
    for key, psh in PSH_TABLE.items():
        if key in loc_lower and key != "default":
            return psh
    return PSH_TABLE["default"]


def size_system(
    system_type: str,
    loads: list[LoadItem],
    location: str = "East Africa",
    days_of_autonomy: float = 2.0,
    dod: float = 0.8,
    system_voltage_dc: int = 48,
    battery_voltage: float = 51.2,
    battery_module_kwh: float = 14.33,
    panel_wp: int = 625,
    panel_voc: float = 49.28,
    panel_vmp: float = 41.5,
    panel_imp: float = 15.06,
    max_inverter_vin: float = 1000.0,
    tmin_celsius: float = 10.0,
    temp_coeff_k: float = -0.0029,
    dc_cable_distance_m: float = 50.0,
    ac_cable_distance_m: float = 100.0,
) -> SizingResult:
    """
    Core sizing engine implementing precise workbook calculations.
    """
    psh = get_psh(location)
    
    # Check if loads represent a time-series meter log
    is_logged_data = len(loads) > 0 and any(l.is_time_series for l in loads)
    
    if is_logged_data:
        import dateutil.parser
        
        # 1. Group by day
        days_data = {}
        for l in loads:
            try:
                dt = dateutil.parser.parse(l.name, fuzzy=True)
                date_str = dt.date().isoformat()
                dow = dt.weekday() # 0 is Monday, 6 is Sunday
            except Exception:
                date_str = "unknown"
                dow = 0
            
            # Filter weekends by default to match multiagent logic
            if dow < 5:
                if date_str not in days_data:
                    days_data[date_str] = []
                days_data[date_str].append(l)
        
        # Remove "unknown" if there are valid days
        if len(days_data) > 1 and "unknown" in days_data:
            del days_data["unknown"]
            
        # 2. Determine interval duration (seconds & minutes) from timestamp difference or row count
        interval_seconds = 3600.0 # fallback: 1 hour
        for d_str, d_loads in days_data.items():
            if d_str != "unknown" and len(d_loads) >= 2:
                try:
                    dt1 = dateutil.parser.parse(d_loads[0].name, fuzzy=True)
                    dt2 = dateutil.parser.parse(d_loads[1].name, fuzzy=True)
                    diff_sec = abs((dt2 - dt1).total_seconds())
                    if 1.0 <= diff_sec <= 7200.0:
                        interval_seconds = diff_sec
                        break
                except Exception:
                    pass

        if interval_seconds == 3600.0:
            for d_str, d_loads in days_data.items():
                if len(d_loads) > 5:
                    calc_sec = 86400.0 / len(d_loads)
                    if 1.0 <= calc_sec <= 7200.0:
                        interval_seconds = calc_sec
                        break

        interval_minutes = interval_seconds / 60.0
        delta_t_hours = interval_seconds / 3600.0 # (interval_minutes / 60.0)

        # 3. Sum data for each day, compare days, and select day with MAXIMUM total power sum
        max_power_sum = -1.0
        max_energy = -1.0
        best_day_loads = []
        for d_str, d_loads in days_data.items():
            if d_str == "unknown":
                p_sum = sum(l.total_wattage for l in d_loads)
                day_energy = (p_sum / len(d_loads)) * 24.0 if d_loads else 0.0
            else:
                p_sum = sum(l.total_wattage for l in d_loads)
                day_energy = p_sum * delta_t_hours
                
            if p_sum > max_power_sum:
                max_power_sum = p_sum
                max_energy = day_energy
                best_day_loads = d_loads
                
        if not best_day_loads:
            best_day_loads = loads
            max_energy = (sum(l.total_wattage for l in loads) / max(1, len(loads))) * 24.0
            
        total_peak_w = max((l.total_wattage for l in best_day_loads), default=0.0)
        total_peak_va = max((l.total_va for l in best_day_loads), default=0.0)
        daily_energy_wh = max_energy
    else:
        # Standard Appliance Schedule: Peak is SUM of all connected items, Daily Energy is SUM(item * hours)
        total_peak_w = sum(l.total_wattage for l in loads)
        total_peak_va = sum(l.total_va for l in loads)
        daily_energy_wh = sum(l.daily_energy_wh for l in loads)
    
    # Direct Sizing: No losses included per explicit user directive (Simply Energy / Peak Sun Hours)
    pr = 1.0
    design_energy_wh = daily_energy_wh
    
    # 2. PV Array Sizing
    if daily_energy_wh > 0:
        required_pv_kwp = (daily_energy_wh / psh) / 1000.0
    else:
        required_pv_kwp = max(5.0, total_peak_w * 1.2 / 1000.0)
        
    # Rule 1: No. of modules = ceil(Total required PV kWp / Single module power in kWp)
    single_module_kw = panel_wp / 1000.0
    panel_qty = max(1, math.ceil(required_pv_kwp / single_module_kw))
    total_pv_kwp = (panel_qty * panel_wp) / 1000.0
    
    # 3. Stringing Calculation (Workbook Max panels per string equation)
    # Max panels = floor( Max Vin / (Voc * (1 + K * (Tmin - 25))) )
    voc_adjusted = panel_voc * (1.0 + temp_coeff_k * (tmin_celsius - 25.0))
    max_panels_per_string = max(1, math.floor(max_inverter_vin / voc_adjusted))
    
    # Target 12-19 modules per string for HV 1000V inverters
    panels_per_string = min(max_panels_per_string, max(8, min(16, panel_qty // 2 or 1)))
    total_strings = math.ceil(panel_qty / panels_per_string)
    string_voltage_v = panels_per_string * panel_vmp
    
    stringing = StringingResult(
        panel_wp=panel_wp,
        panel_voc=panel_voc,
        max_inverter_vin=max_inverter_vin,
        tmin_celsius=tmin_celsius,
        temp_coeff_k=temp_coeff_k,
        max_panels_per_string=max_panels_per_string,
        panels_per_mppt=panels_per_string * 2,
        total_strings=total_strings,
        string_voltage_v=string_voltage_v,
    )

    # 4. Inverter Sizing
    # When sizing for Hybrid/Off-Grid: use Apparent Power S (VA -> kVA)
    # When sizing for Grid-Tied: use Active Power P (W -> kW)
    if system_type in ("off-grid", "hybrid"):
        peak_demand_kunit = (total_peak_va * 1.25) / 1000.0 # Apparent Power S + 25% safety margin
    else:
        peak_demand_kunit = (total_peak_w * 1.25) / 1000.0  # Active Power P + 25% safety margin

    inverter_kw = max(total_pv_kwp, peak_demand_kunit)
    
    # Realistic Inverter Selection:
    # Prioritizes large commercial/industrial inverters (80kW, 100kW, 150kW) for large systems (>50 kW)
    if inverter_kw > 50:
        large_sizes = [150, 100, 80]
        best_size = 150
        best_qty = math.ceil(inverter_kw / 150)
        for s in large_sizes:
            qty = math.ceil(inverter_kw / s)
            if qty < best_qty or (qty == best_qty and s > best_size):
                best_size = s
                best_qty = qty
    elif inverter_kw >= 20:
        med_sizes = [50, 30, 20, 15]
        best_size = 50
        best_qty = math.ceil(inverter_kw / 50)
        for s in med_sizes:
            qty = math.ceil(inverter_kw / s)
            if qty <= 3:
                best_size = s
                best_qty = qty
                break
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
    
    # 5. Battery Sizing (Off-Grid / Hybrid)
    battery_qty = 0
    total_storage_kwh = 0.0
    battery_stacks = 0
    battery_breaker_a = 0.0
    battery_type = "Dyness Stack280 14.33kWh HV Battery" if battery_module_kwh > 10 else "Deep Cycle Lithium LiFePO4"
    
    if system_type in ("off-grid", "hybrid"):
        # Base BESS = (Daily Energy * Days of Autonomy) / DoD
        base_bess_kwh = (daily_energy_wh * max(1.0, days_of_autonomy)) / (1000.0 * dod)
        if system_type == "hybrid" and days_of_autonomy < 1.0:
            # Hybrid typically sizes for evening peak / storage buffer
            base_bess_kwh = max(10.0, (daily_energy_wh * 0.6) / (1000.0 * dod))
            
        # Rule 2: For BESS, multiply base storage requirement by 1.25 safety/degradation factor
        needed_bess_kwh = base_bess_kwh * 1.25
        battery_qty = max(1, math.ceil(needed_bess_kwh / battery_module_kwh))
        total_storage_kwh = battery_qty * battery_module_kwh
        battery_stacks = max(1, math.ceil(battery_qty / 9)) # Max 9 modules per rack/stack
        
        # Battery breaker = 1.25 * max charge/discharge current (e.g. 100A -> 125A breaker, 160A available)
        max_charge_current = (inverter_kw_std * 1000) / (system_voltage_dc or 384)
        battery_breaker_a = max(125.0, math.ceil((max_charge_current * 1.25) / 25) * 25)

    # 6. Cable & Switchgear Sizing (Exact workbook formulas)
    # DC Cable Cross-Sectional Area: C.A (mm²) = (I * rho * 2 * L) / V.D
    dc_allowable_vd = string_voltage_v * 0.02 # 2% drop allowed
    rho_copper = 0.0178 # ohm.mm²/m
    dc_area_calc = (panel_imp * rho_copper * 2.0 * dc_cable_distance_m) / max(1.0, dc_allowable_vd)
    dc_recommended_sqmm = 4 if dc_area_calc <= 4 else (6 if dc_area_calc <= 6 else 10)
    dc_total_length = dc_cable_distance_m * 2.0 * total_strings
    
    # AC Cable & Breaker Sizing (3-Phase 400V or 1-Phase 230V)
    is_3phase = inverter_kw_std >= 10
    ac_voltage = 400.0 if is_3phase else 230.0
    if is_3phase:
        ac_current = (inverter_kw_std * 1000.0) / (math.sqrt(3) * ac_voltage * 0.9)
    else:
        ac_current = (inverter_kw_std * 1000.0) / (ac_voltage * 0.9)
        
    ac_breaker = math.ceil((ac_current * 1.25) / 10) * 10
    
    # Recommended AC cable size based on current
    ac_sqmm = 16 if ac_current <= 60 else (25 if ac_current <= 100 else (50 if ac_current <= 160 else 95))
    
    # AC Voltage Drop: V.D = (sqrt(3) * I * R * L) / 1000
    # Resistance per km for copper: 16mm²->1.15, 25mm²->0.727, 50mm²->0.387
    r_per_km = 0.727 if ac_sqmm == 25 else (1.15 if ac_sqmm <= 16 else 0.387)
    ac_vd_v = (math.sqrt(3) if is_3phase else 2.0) * ac_current * r_per_km * (ac_cable_distance_m / 1000.0)
    ac_vd_pct = (ac_vd_v / ac_voltage) * 100.0

    cable_sizing = CableSizingResult(
        dc_string_current_a=round(panel_imp, 1),
        dc_distance_m=dc_cable_distance_m,
        dc_allowable_vd_v=round(dc_allowable_vd, 2),
        dc_cable_area_sqmm=round(dc_area_calc, 2),
        dc_recommended_cable_sqmm=dc_recommended_sqmm,
        dc_total_length_m=round(dc_total_length, 1),
        ac_max_op_current_a=round(ac_current, 1),
        ac_breaker_rating_a=round(ac_breaker, 1),
        ac_distance_m=ac_cable_distance_m,
        ac_allowable_vd_v=round(ac_voltage * 0.05, 2),
        ac_cable_area_sqmm=ac_sqmm,
        ac_voltage_drop_v=round(ac_vd_v, 2),
        ac_voltage_drop_pct=round(ac_vd_pct, 2),
    )

    return SizingResult(
        system_type=system_type,
        location=location,
        peak_sun_hours=psh,
        total_peak_power_w=total_peak_w,
        total_peak_va=total_peak_va,
        daily_energy_wh=daily_energy_wh,
        design_energy_wh=design_energy_wh,
        panel_wp=panel_wp,
        panel_qty=panel_qty,
        total_pv_kwp=total_pv_kwp,
        stringing=stringing,
        days_of_autonomy=days_of_autonomy,
        dod=dod,
        battery_type=battery_type,
        battery_module_kwh=battery_module_kwh,
        battery_qty=battery_qty,
        total_storage_kwh=total_storage_kwh,
        battery_stacks=battery_stacks,
        battery_breaker_a=battery_breaker_a,
        inverter_kw=inverter_kw_std,
        inverter_kva=inverter_kva,
        inverter_qty=inverter_qty,
        mppt_rating_per_unit=max(60, math.ceil(panel_imp * 2)),
        mppt_qty=total_strings,
        system_voltage_dc=system_voltage_dc,
        cable_sizing=cable_sizing,
    )


def format_sizing_summary(result: SizingResult) -> str:
    """Formats SizingResult into an executive engineering report table matching standard design sheets."""
    d = result.to_dict()
    sizing_basis_note = "⚡ **Apparent Power (S)** used for Hybrid/Off-Grid Inverter sizing" if result.system_type in ("off-grid", "hybrid") else "🌐 **Active Power (P)** used for Grid-Tied Inverter sizing"
    
    daily_kwh = result.daily_energy_wh / 1000.0
    req_kwp = daily_kwh / max(0.1, result.peak_sun_hours)
    
    lines = [
        f"## ☀️ System Sizing Report ({result.system_type.upper()})",
        f"**Location:** {result.location} (Peak Sun Hours: `{result.peak_sun_hours} h/day`)",
        f"*{sizing_basis_note} per engineering standards.*",
        "",
        "### 📐 Step-by-Step Mathematical Calculation Breakdown",
        f"1. **Daily Energy Demand ($E_{{daily}}$):** `{daily_kwh:,.2f} kWh/day`",
        f"2. **Peak Sun Hours (PSH):** `{result.peak_sun_hours} h/day`",
        f"3. **Required DC Solar Capacity ($P_{{DC}}$):** `Daily Energy ÷ PSH = {daily_kwh:,.2f} ÷ {result.peak_sun_hours} = {req_kwp:,.2f} kWp`",
        f"4. **PV Modules Required ({result.panel_wp}Wp):** `ceil({req_kwp:,.2f} ÷ {result.panel_wp/1000:.3f}) = {result.panel_qty} modules`",
        f"5. **Total Installed Solar Capacity:** `{result.panel_qty} modules × {result.panel_wp/1000:.3f} kW = {result.total_pv_kwp:.2f} kWp`",
        "",
        "### ⚡ 1. Proposed DC Capacity & Inverter Sizing",
        "| Parameter / Metric | Specification | Formula / Engineering Rule |",
        "|---|---|---|",
        f"| **Proposed DC Capacity** | `{result.total_pv_kwp:.2f} kWp` | Based on target daily energy & peak sun hours |",
        f"| **Selected Module Rating** | `{result.panel_wp} Wp` (`{result.panel_wp/1000:.3f} kWp`) | High-efficiency monocrystalline PV module |",
        f"| **Total PV Modules Required** | `{result.panel_qty} pcs` | Rule: `ceil({result.total_pv_kwp:.2f} / {result.panel_wp/1000:.3f})` |",
        f"| **Proposed Inverter Size** | `{result.inverter_kw:.1f} kW` (`{result.inverter_kva:.1f} kVA`) | Sized with `1.25x` safety factor |",
        f"| **No. of Inverters** | `{result.inverter_qty} pcs` | Total AC Capacity: `{result.inverter_kw * result.inverter_qty:.1f} kW` |",
        "",
        "### 🔗 2. Stringing & MPPT Configuration",
        "| Parameter | Specification | Calculation / Reference |",
        "|---|---|---|",
        f"| **Max Inverter DC Input ($V_{{in,max}}$)** | `1000 V` | Maximum allowable inverter input voltage |",
        f"| **Panel Open Circuit Voltage ($V_{{oc}}$)** | `49.28 V` (or spec) | Standard module $V_{{oc}}$ at STC |",
        f"| **Max Panels in a String** | `{result.stringing.max_panels_per_string} pcs` | Formula: `floor(Vin_max / (Voc * (1 + K*(Tmin - 25°C))))` |",
        f"| **Panels per MPPT** | `{result.stringing.panels_per_mppt} panels` | Based on max input power per MPPT (`16.25 kW`) |",
        f"| **Total Number of Strings** | `{result.stringing.total_strings} strings` | Recommended stringing distribution |",
        f"| **Operating String Voltage** | `{result.stringing.string_voltage_v:.1f} V DC` | Optimal MPPT tracking window |",
    ]

    if result.system_type in ("off-grid", "hybrid"):
        lines += [
            "",
            "### 🔋 3. Battery System Design (BESS)",
            "| Parameter | Specification | Engineering Rule / Note |",
            "|---|---|---|",
            f"| **Needed BESS (Base + Buffer)** | `{result.total_storage_kwh:.3f} kWh` | Formula: `[(Daily Energy * Autonomy) / DoD] * 1.25` |",
            f"| **Selected Battery Module** | `{result.battery_type}` | `{result.battery_module_kwh} kWh / HV module` |",
            f"| **No. of Battery Modules** | `{result.battery_qty} pcs` | Rule: `ceil({result.total_storage_kwh:.2f} / {result.battery_module_kwh})` |",
            f"| **No. of Battery Racks / Stacks** | `{result.battery_stacks} Stack(s) of up to 9` | Vertical rack configuration (`ceil(modules / 9)`) |",
            f"| **Actual Connected BESS** | `{result.battery_qty * result.battery_module_kwh:.3f} kWh` | Total installed usable storage |",
            "",
            "### 🛡️ 4. Battery Protection & Cabling",
            "| Component | Specification | Note / Rating |",
            "|---|---|---|",
            f"| **Max Charge/Discharge Current** | `{result.battery_breaker_a / 1.25:.1f} A` | Peak continuous operational current |",
            f"| **Battery Breaker Rating** | `{result.battery_breaker_a:.1f} A` (`160A` frame available) | Rule: `1.25 * Max Charge/Discharge Current` at `1000Vdc` |",
            "| **Battery Cable (Tower to Breaker)** | `50 mm²` CU/PVC/PVC-Nitrile | Main battery riser (`300/500Vdc` rating) |",
            "| **Battery Cable (Breaker to Inverter)** | `16 mm²` CU/PVC/PVC-Nitrile | 4 Runs for two battery inputs |",
        ]

    lines += [
        "",
        "### ⚡ 5. Earthing & Lightning Protection System (LPS)",
        "| Circuit / Connection | Cable Specification | Estimated Length / Note |",
        "|---|---|---|",
        "| **Inverter to PVDB** | `16 mm²` CU/PVC (`450/750V`) | `15 m` run |",
        "| **PVDB to Main Earth Bar** | `16 mm²` CU/PVC (`450/750V`) | `40 m` run |",
        "| **PV Rail to Rail Bonding** | `6 mm²` CU/PVC (`450/750V`) | Inter-module structure bonding |",
        "| **Roof / Structure to PVDB** | `16 mm²` CU/PVC (`450/750V`) | `60 m` run |",
        "| **Roof / Structure to Earthpit** | `16 mm²` CU/PVC (`450/750V`) | `15 m` direct earth run |",
        "| **Battery Tower to PVDB** | `16 mm²` CU/PVC (`450/750V`) | `5 m` run |",
        "| **LPS (Lightning Protection)** | **Copper Tape** | `135 m` perimeter & down conductor |",
    ]

    if result.cable_sizing:
        cs = result.cable_sizing
        lines += [
            "",
            "### 🛠️ 6. DC String & AC Feeder Cable Sizing",
            "| Circuit | Cable Specification | Voltage Drop Check | Breaker / Protection |",
            "|---|---|---|---|",
            f"| **PV DC String Cable** | `{cs.dc_recommended_cable_sqmm} mm²` TCU/XLPO (`1.5/1.5kVdc`) | Formula: `I*rho*2L / VD` (Total length: `{cs.dc_total_length_m:.0f} m`) | 1000V DC Isolator & Type II SPD |",
            f"| **AC Main Feeder Cable** | `1 run of 4-core {cs.ac_cable_area_sqmm} mm²` CU/XLPE/PVC (`{cs.ac_distance_m:.0f} m`) | V.D Check: `{cs.ac_voltage_drop_pct}%` (`{cs.ac_voltage_drop_v}V`) vs Allowable `20.75V` | AC Board Breaker: `{cs.ac_breaker_rating_a:.1f} A` |",
        ]

    lines += [
        "",
        "### 💡 Detailed Engineering Rationale & Selection Justification",
        f"1. **PV Array Sizing Rationale:** Based on `{daily_kwh:,.2f} kWh/day` demand and `{result.peak_sun_hours} h/day` solar insolation, the required peak capacity is `{req_kwp:,.2f} kWp` (Formula: `Daily Energy ÷ PSH`). High-efficiency `{result.panel_wp}Wp` N-Type monocrystalline modules (22.36% efficiency) were selected to maximize power output per square meter and reduce racking labor.",
        f"2. **Inverter Selection Rationale:** Standard commercial/industrial inverter size `{result.inverter_kw:.1f} kW` (`{result.inverter_kva:.1f} kVA`) was selected to maintain a low unit count and keep electrical busbar connections clean. `{result.inverter_qty} pc(s)` provide total AC capacity of `{result.inverter_kw * result.inverter_qty:.1f} kW`, ensuring a `1.25x` safety factor over peak demand.",
    ]
    if result.system_type in ("off-grid", "hybrid"):
        lines += [
            f"3. **Battery Storage (BESS) Rationale:** Total storage required is `{result.total_storage_kwh:.2f} kWh` based on `{result.days_of_autonomy} day(s)` autonomy at `{int(result.dod*100)}%` Depth of Discharge with a `1.25x` aging buffer. High-voltage LiFePO4 modules (`{result.battery_type}`) were selected for 6,000+ cycle durability and thermal safety.",
        ]
    lines += [
        f"4. **Stringing & Voltage Safety Rationale:** String length is limited to `{result.stringing.max_panels_per_string} panels/string` so that max open-circuit voltage ($V_{{oc}}$ at cold temperature $10^\\circ\\text{{C}}$) remains safely below the `1000V DC` maximum inverter input rating.",
    ]

    lines += [
        "",
        "---",
        "### 📎 **CRITICAL NEXT STEP: Technical Datasheet Verification Required**",
        "> [!IMPORTANT]",
        "> **Please provide / upload the technical datasheets and manuals of the selected Inverter and Battery.**",
        "> To proceed with verifying exact MPPT voltage windows, DC charge controller limits, BMS CAN/RS485 communication protocols, and generating the final Bill of Quantities (BOQ), upload the manufacturer datasheets (`PDF`, `DOCX`, `Excel`, or `PNG/JPG image`) right here in the chat!"
    ]

    return "\n".join(lines)
