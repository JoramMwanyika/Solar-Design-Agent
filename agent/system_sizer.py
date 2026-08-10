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
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


def load_pv_panel_specs() -> dict:
    """Loads PV panel specs from the Jinko JSON datasheet if available, otherwise returns defaults."""
    defaults = {
        "panel_wp": 625,
        "panel_voc": 49.28,
        "panel_vmp": 41.5,
        "panel_imp": 15.06,
    }
    try:
        jinko_path = Path(__file__).parent.parent / "datasheets/pv_modules/Jinko_TigerNeo_N-Type_625W.json"
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
    except Exception as e:
        print(f"[Error loading Jinko datasheet in system_sizer]: {e}")
    return defaults


def select_inverter_model(system_type: str, inverter_kw_std: float, system_voltage_dc: float) -> str:
    """
    Selects standard inverter manufacturer model name/number based on capacity and system specs.
    Aligns with datasheets:
    - Grid-Tied: Huawei SUN2000 Series (L1 for residential single-phase, M1/M2/M3/M0/M1 for commercial three-phase)
    - Off-Grid / Hybrid: Deye Low Voltage (LP3 / 48V) or High Voltage (HP3) Hybrid series.
    """
    kw_int = int(inverter_kw_std)
    if system_type == "grid-tied":
        if kw_int in (2, 3, 4, 5, 6):
            return f"Huawei SUN2000-{kw_int}KTL-L1"
        elif kw_int in (8, 10, 12, 15):
            return f"Huawei SUN2000-{kw_int}KTL-M1"
        elif kw_int == 20:
            return f"Huawei SUN2000-20KTL-M2"
        elif kw_int in (30, 36, 40):
            return f"Huawei SUN2000-{kw_int}KTL-M3"
        elif kw_int == 50:
            return f"Huawei SUN2000-50KTL-M0"
        elif kw_int == 80:
            return f"Huawei SUN2000-80KTL-M0"
        elif kw_int == 100:
            return f"Huawei SUN2000-100KTL-M1"
        elif kw_int == 150:
            return f"Huawei SUN2000-150KTL-M0"
        else:
            return f"Huawei SUN2000-{kw_int}KTL-M3"
    else:
        # Off-Grid / Hybrid
        if system_voltage_dc <= 48 and inverter_kw_std <= 20:
            # Low Voltage (LV) Hybrid e.g. Deye SUN-3-12K-SG05LP3-EU-SM2
            return f"Deye SUN-{kw_int}K-SG05LP3-EU-SM2"
        else:
            # High Voltage (HV) Hybrid
            if kw_int <= 25:
                return f"Deye SUN-{kw_int}K-SG01HP3-EU-AM2"
            elif kw_int <= 50:
                return f"Deye SUN-{kw_int}K-SG01HP3-EU-BM4"
            elif kw_int <= 80:
                return f"Deye SUN-{kw_int}K-SG02HP3-EU-EM6"
            else:
                return f"Deye SUN-{kw_int}K-SG01HP3-EU"


@dataclass
class LoadItem:
    name: str
    wattage: float       # Active Power P in Watts
    quantity: int = 1
    hours_per_day: float = 1.0
    apparent_wattage: Optional[float] = None # Apparent Power S in VA
    power_factor: float = 0.85
    is_time_series: bool = False
    explicit_daily_energy_wh: Optional[float] = None

    @property
    def daily_energy_wh(self) -> float:
        if self.explicit_daily_energy_wh is not None and self.explicit_daily_energy_wh > 0:
            return self.explicit_daily_energy_wh
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
    panels_per_string: int
    stringing_grid: list = field(default_factory=list)


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
    inverter_brand: str = "Huawei SUN2000 Series"
    voltage_architecture: str = "High Voltage (HV: 1000V DC)"
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
                "stringing_grid": self.stringing.stringing_grid if self.stringing else [],
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
                "brand": self.inverter_brand,
                "voltage_architecture": self.voltage_architecture,
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
    panel_vmp: float = 41.52,
    panel_imp: float = 15.05,
    max_inverter_vin: float = 1000.0,
    tmin_celsius: float = 10.0,
    temp_coeff_k: float = -0.0029,
    dc_cable_distance_m: float = 50.0,
    ac_cable_distance_m: float = 100.0,
) -> SizingResult:
    """
    Facade router routing system sizing to specialized engines based on input characteristics.
    """
    is_logged_data = len(loads) > 0 and any(l.is_time_series for l in loads)
    if is_logged_data:
        return size_system_by_logged_data(
            system_type=system_type,
            loads=loads,
            location=location,
            days_of_autonomy=days_of_autonomy,
            dod=dod,
            system_voltage_dc=system_voltage_dc,
            battery_voltage=battery_voltage,
            battery_module_kwh=battery_module_kwh,
            panel_wp=panel_wp,
            panel_voc=panel_voc,
            panel_vmp=panel_vmp,
            panel_imp=panel_imp,
            max_inverter_vin=max_inverter_vin,
            tmin_celsius=tmin_celsius,
            temp_coeff_k=temp_coeff_k,
            dc_cable_distance_m=dc_cable_distance_m,
            ac_cable_distance_m=ac_cable_distance_m,
        )
    else:
        return size_system_by_load_profile(
            system_type=system_type,
            loads=loads,
            location=location,
            days_of_autonomy=days_of_autonomy,
            dod=dod,
            system_voltage_dc=system_voltage_dc,
            battery_voltage=battery_voltage,
            battery_module_kwh=battery_module_kwh,
            panel_wp=panel_wp,
            panel_voc=panel_voc,
            panel_vmp=panel_vmp,
            panel_imp=panel_imp,
            max_inverter_vin=max_inverter_vin,
            tmin_celsius=tmin_celsius,
            temp_coeff_k=temp_coeff_k,
            dc_cable_distance_m=dc_cable_distance_m,
            ac_cable_distance_m=ac_cable_distance_m,
        )


def size_system_by_load_profile(
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
    panel_vmp: float = 41.52,
    panel_imp: float = 15.05,
    max_inverter_vin: float = 1000.0,
    tmin_celsius: float = 10.0,
    temp_coeff_k: float = -0.0029,
    dc_cable_distance_m: float = 50.0,
    ac_cable_distance_m: float = 100.0,
) -> SizingResult:
    """
    Sizing Agent specifically for Load Profile data (Appliance list).
    """
    # Standard Appliance Schedule: Peak is SUM of all connected items, Daily Energy is SUM(item * hours)
    total_peak_w = sum(l.total_wattage for l in loads)
    total_peak_va = sum(l.total_va for l in loads)
    daily_energy_wh = sum(l.daily_energy_wh for l in loads)

    return _execute_core_sizing_math(
        system_type=system_type,
        daily_energy_wh=daily_energy_wh,
        total_peak_w=total_peak_w,
        total_peak_va=total_peak_va,
        location=location,
        days_of_autonomy=days_of_autonomy,
        dod=dod,
        system_voltage_dc=system_voltage_dc,
        battery_voltage=battery_voltage,
        battery_module_kwh=battery_module_kwh,
        panel_wp=panel_wp,
        panel_voc=panel_voc,
        panel_vmp=panel_vmp,
        panel_imp=panel_imp,
        max_inverter_vin=max_inverter_vin,
        tmin_celsius=tmin_celsius,
        temp_coeff_k=temp_coeff_k,
        dc_cable_distance_m=dc_cable_distance_m,
        ac_cable_distance_m=ac_cable_distance_m,
    )


def size_system_by_logged_data(
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
    panel_vmp: float = 41.52,
    panel_imp: float = 15.05,
    max_inverter_vin: float = 1000.0,
    tmin_celsius: float = 10.0,
    temp_coeff_k: float = -0.0029,
    dc_cable_distance_m: float = 50.0,
    ac_cable_distance_m: float = 100.0,
) -> SizingResult:
    """
    Sizing Agent specifically for time-series Logged data (SCADA/meter files).
    """
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

    return _execute_core_sizing_math(
        system_type=system_type,
        daily_energy_wh=daily_energy_wh,
        total_peak_w=total_peak_w,
        total_peak_va=total_peak_va,
        location=location,
        days_of_autonomy=days_of_autonomy,
        dod=dod,
        system_voltage_dc=system_voltage_dc,
        battery_voltage=battery_voltage,
        battery_module_kwh=battery_module_kwh,
        panel_wp=panel_wp,
        panel_voc=panel_voc,
        panel_vmp=panel_vmp,
        panel_imp=panel_imp,
        max_inverter_vin=max_inverter_vin,
        tmin_celsius=tmin_celsius,
        temp_coeff_k=temp_coeff_k,
        dc_cable_distance_m=dc_cable_distance_m,
        ac_cable_distance_m=ac_cable_distance_m,
    )


def size_system_by_bill_analysis(
    system_type: str,
    monthly_energy_kwh: float,
    billing_days: int = 30,
    customer_type: str = "Residential",
    max_demand_kw: float = 0.0,
    location: str = "East Africa",
    days_of_autonomy: float = 2.0,
    dod: float = 0.8,
    system_voltage_dc: int = 48,
    battery_voltage: float = 51.2,
    battery_module_kwh: float = 14.33,
    panel_wp: int = 625,
    panel_voc: float = 49.28,
    panel_vmp: float = 41.52,
    panel_imp: float = 15.05,
    max_inverter_vin: float = 1000.0,
    tmin_celsius: float = 10.0,
    temp_coeff_k: float = -0.0029,
    dc_cable_distance_m: float = 50.0,
    ac_cable_distance_m: float = 100.0,
) -> SizingResult:
    """
    Sizing Agent specifically for monthly utility bill analysis.
    """
    # 1. Energy Analysis
    daily_energy_wh = (monthly_energy_kwh / max(1, billing_days)) * 1000.0
    
    # Estimate peak demand if not provided
    if max_demand_kw <= 0:
        lf = 0.5 if customer_type == "Commercial" else (0.7 if customer_type == "Industrial" else 0.3)
        peak_w = (daily_energy_wh / 24.0) / lf
    else:
        peak_w = max_demand_kw * 1000.0
        
    # Estimate peak apparent demand (assuming PF = 0.85)
    peak_va = peak_w / 0.85

    return _execute_core_sizing_math(
        system_type=system_type,
        daily_energy_wh=daily_energy_wh,
        total_peak_w=peak_w,
        total_peak_va=peak_va,
        location=location,
        days_of_autonomy=days_of_autonomy,
        dod=dod,
        system_voltage_dc=system_voltage_dc,
        battery_voltage=battery_voltage,
        battery_module_kwh=battery_module_kwh,
        panel_wp=panel_wp,
        panel_voc=panel_voc,
        panel_vmp=panel_vmp,
        panel_imp=panel_imp,
        max_inverter_vin=max_inverter_vin,
        tmin_celsius=tmin_celsius,
        temp_coeff_k=temp_coeff_k,
        dc_cable_distance_m=dc_cable_distance_m,
        ac_cable_distance_m=ac_cable_distance_m,
    )


def load_inverter_specs(inverter_brand: str) -> dict:
    """
    Loads specifications of the chosen inverter brand/model from the generated JSON datasheets.
    """
    import os
    import re
    inv_dir = Path(__file__).parent.parent / "datasheets/inverters"
    brand_lower = inverter_brand.lower()
    
    # 1. Determine JSON filename matching the brand
    json_file = None
    if "huawei" in brand_lower:
        if "l1" in brand_lower or any(f"-{x}k" in brand_lower for x in [2,3,4,5,6]):
            json_file = "Huawei_SUN2000-2-6KTL-L1.json"
        else:
            json_file = "Huawei_SUN2000-30-40KTL-M3.json"
    elif "goodwe" in brand_lower or "gw" in brand_lower:
        json_file = "GoodWe_GW5-20K-ET-L-G10.json"
    elif "solis" in brand_lower:
        json_file = "Solis_S6-EH3P30-50K-H.json"
    elif "deye" in brand_lower or "sunsynk" in brand_lower:
        # Re-ordered specific to general to avoid incorrect matching
        if "em6" in brand_lower:
            json_file = "Deye_SUN-60-80K-SG02HP3-EU-EM6.json"
        elif "bm4" in brand_lower:
            json_file = "Deye_SUN-25-50K-SG01HP3-EU-BM4.json"
        elif "am2" in brand_lower or "sg01hp3" in brand_lower:
            json_file = "Deye_SUN-5-25K-SG01HP3-EU-AM2.json"
        elif "sg05lp1" in brand_lower or "lp1" in brand_lower:
            json_file = "Deye_SUN-3.6-10K-SG05LP1-EU.json"
        elif "sg05lp3" in brand_lower or "lp3" in brand_lower:
            json_file = "Deye_SUN-3-12K-SG05LP3-EU-SM2.json"
        else:
            # Fallbacks based on size
            m = re.search(r"sun-(\d+)k", brand_lower)
            if m:
                kw = int(m.group(1))
                if kw <= 12:
                    json_file = "Deye_SUN-3-12K-SG05LP3-EU-SM2.json"
                elif kw <= 25:
                    json_file = "Deye_SUN-5-25K-SG01HP3-EU-AM2.json"
                elif kw <= 50:
                    json_file = "Deye_SUN-25-50K-SG01HP3-EU-BM4.json"
                else:
                    json_file = "Deye_SUN-60-80K-SG02HP3-EU-EM6.json"
            else:
                json_file = "Deye_SUN-3-12K-SG05LP3-EU-SM2.json"
                
    if not json_file:
        json_file = "Deye_SUN-3-12K-SG05LP3-EU-SM2.json"

    specs_path = inv_dir / json_file
    if not specs_path.exists():
        # Sensible defaults matching the system type voltage tier
        is_hv = "hv" in brand_lower or "em6" in brand_lower or "bm4" in brand_lower or "am2" in brand_lower or "m3" in brand_lower or "solis" in brand_lower
        return {
            "num_mppts": 4 if is_hv else 2,
            "inputs_per_mppt": 2 if is_hv else 1,
            "max_vin": 1000.0 if is_hv else 500.0,
            "mppt_min_v": 200.0 if is_hv else 40.0,
            "mppt_max_v": 850.0 if is_hv else 460.0,
        }
        
    try:
        with open(specs_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        ts = data.get("technical_specifications", {})
        dc = ts.get("dc_input", ts)
        
        num_mppts = dc.get("number_of_mppt") or dc.get("mppt_qty") or 2
        max_vin = dc.get("max_dc_input_voltage_v") or dc.get("max_dc_input_voltage_vin_max_v") or 800.0
        mppt_min = dc.get("mppt_voltage_min_v") or dc.get("mppt_operating_voltage_min_v") or 150.0
        mppt_max = dc.get("mppt_voltage_max_v") or dc.get("mppt_operating_voltage_max_v") or 850.0
        
        # Inputs per MPPT mapping
        inputs_per_mppt = 1
        if "huawei" in brand_lower:
            inputs_per_mppt = 1 if "l1" in brand_lower else 2
        elif "solis" in brand_lower:
            inputs_per_mppt = 2
        elif "deye" in brand_lower:
            if any(x in brand_lower for x in ["am2", "bm4", "em6", "hp3"]):
                inputs_per_mppt = 2
            else:
                inputs_per_mppt = 1
                
        return {
            "num_mppts": int(num_mppts),
            "inputs_per_mppt": int(inputs_per_mppt),
            "max_vin": float(max_vin),
            "mppt_min_v": float(mppt_min),
            "mppt_max_v": float(mppt_max),
        }
    except Exception:
        return {
            "num_mppts": 2,
            "inputs_per_mppt": 1,
            "max_vin": 500.0,
            "mppt_min_v": 40.0,
            "mppt_max_v": 460.0,
        }


def find_stringing_distribution(panel_qty: int, num_mppts: int, inputs_per_mppt: int, min_panels_per_string: int, max_panels_per_string: int) -> list:
    """
    Finds the optimal allocation of strings to MPPTs.
    Returns a list of length `num_mppts`, where each element is (num_strings, panels_per_string).
    """
    solutions = []
    
    # DFS to find all valid string allocations
    def search(mppt_idx, current_alloc, remaining_panels):
        if mppt_idx == num_mppts:
            if remaining_panels == 0:
                solutions.append(list(current_alloc))
            return
            
        # Try s_i = 0
        search(mppt_idx + 1, current_alloc + [(0, 0)], remaining_panels)
        
        # Try s_i strings (from 1 up to inputs_per_mppt)
        for s in range(1, inputs_per_mppt + 1):
            for p in range(min_panels_per_string, max_panels_per_string + 1):
                use_panels = s * p
                if use_panels <= remaining_panels:
                    search(mppt_idx + 1, current_alloc + [(s, p)], remaining_panels - use_panels)

    search(0, [], panel_qty)
    
    if not solutions:
        # Fallback if no exact solution fits: distribute panels as evenly as possible using 1 string per MPPT
        # up to max_panels_per_string
        fallback = []
        rem = panel_qty
        for i in range(num_mppts):
            if rem <= 0:
                fallback.append((0, 0))
            else:
                take = min(rem, max_panels_per_string)
                fallback.append((1, take))
                rem -= take
        return fallback

    # Score solutions to pick the absolute best one
    best_sol = None
    best_score = float('inf')
    
    for sol in solutions:
        active_p = [p for s, p in sol if s > 0]
        active_s = [s for s, p in sol if s > 0]
        
        if not active_p:
            continue
            
        p_max = max(active_p)
        p_min = min(active_p)
        p_diff = p_max - p_min  # minimize string length diff between trackers
        
        s_max = max(active_s)
        s_min = min(active_s)
        s_diff = s_max - s_min  # minimize parallel string count diff between trackers
        
        total_s = sum(active_s)
        num_active = len(active_p)
        
        # Calculate average string length
        avg_len = sum(p for s, p in sol if s > 0) / len(active_p)
        
        # Score prioritizing:
        # 1. Fewer total strings (lower installation complexity)
        # 2. Balanced loading between trackers
        # 3. Longer string lengths (higher DC voltage, closer to inverter rated voltage)
        score = (total_s * 1000) + (p_diff * 100) + (s_diff * 50) - (avg_len * 10) - (num_active * 5)
        
        if score < best_score:
            best_score = score
            best_sol = sol
            
    return best_sol


def build_stringing_grid(sol: list, num_mppts: int, inputs_per_mppt: int) -> list:
    """
    Transforms [(num_strings, panels_per_string), ...] into a 2D grid
    of shape (inputs_per_mppt, num_mppts) containing panel count integers.
    """
    grid = [[None] * num_mppts for _ in range(inputs_per_mppt)]
    for mppt_idx, (num_strings, panels_per_string) in enumerate(sol):
        for s_idx in range(num_strings):
            grid[s_idx][mppt_idx] = panels_per_string
    return grid


def _execute_core_sizing_math(
    system_type: str,
    daily_energy_wh: float,
    total_peak_w: float,
    total_peak_va: float,
    location: str,
    days_of_autonomy: float,
    dod: float,
    system_voltage_dc: int,
    battery_voltage: float,
    battery_module_kwh: float,
    panel_wp: int,
    panel_voc: float,
    panel_vmp: float,
    panel_imp: float,
    max_inverter_vin: float,
    tmin_celsius: float,
    temp_coeff_k: float,
    dc_cable_distance_m: float,
    ac_cable_distance_m: float,
) -> SizingResult:
    """
    Unified core calculation engine executing precise workbook equations.
    """
    specs = load_pv_panel_specs()
    if panel_wp == 625:
        panel_wp = specs["panel_wp"]
    if panel_voc == 49.28:
        panel_voc = specs["panel_voc"]
    if panel_vmp in (41.5, 41.52):
        panel_vmp = specs["panel_vmp"]
    if panel_imp in (15.06, 15.05):
        panel_imp = specs["panel_imp"]

    psh = get_psh(location)
    
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
    
    # 3. Inverter Brand, Rating & Architecture Selection
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

    # Enforce User Directives for Inverter Brand & Architecture:
    # 1. Grid-tied -> Huawei inverters
    # 2. Off-grid / Hybrid -> Deye or Solis inverters (Check Low Voltage vs High Voltage)
    inverter_brand = select_inverter_model(system_type, inverter_kw_std, system_voltage_dc)
    
    # Load exact datasheet specs
    specs = load_inverter_specs(inverter_brand)
    num_mppts = specs["num_mppts"]
    inputs_per_mppt = specs["inputs_per_mppt"]
    max_inverter_vin = specs["max_vin"]
    
    if system_type == "grid-tied":
        voltage_architecture = f"High Voltage (HV: {int(max_inverter_vin)}V DC)"
    else:
        if system_voltage_dc <= 48 and inverter_kw_std <= 20:
            voltage_architecture = f"Low Voltage (LV: 48V BESS / {int(max_inverter_vin)}V DC)"
        else:
            voltage_architecture = f"High Voltage (HV: {int(max_inverter_vin)}V DC / 384V BESS)"

    # 4. Stringing & MPPT Calculations using exact datasheet limits
    # Max panels per string = floor( Max Vin / (Voc * (1 + K * (Tmin - 25))) )
    voc_adjusted = panel_voc * (1.0 + temp_coeff_k * (tmin_celsius - 25.0))
    max_panels_per_string = max(1, math.floor(max_inverter_vin / voc_adjusted))
    
    # Minimum panels to start the inverter MPPT
    min_panels_per_string = max(3, math.ceil(specs["mppt_min_v"] / panel_vmp))
    
    # Partition panels to each inverter unit
    panels_per_inverter = panel_qty // inverter_qty
    remainder = panel_qty % inverter_qty
    
    # Sizing for the primary inverter unit
    target_qty = panels_per_inverter + (1 if remainder > 0 else 0)
    
    # Optimal distribution search
    sol = find_stringing_distribution(
        panel_qty=target_qty,
        num_mppts=num_mppts,
        inputs_per_mppt=inputs_per_mppt,
        min_panels_per_string=min_panels_per_string,
        max_panels_per_string=max_panels_per_string
    )
    
    grid = build_stringing_grid(sol, num_mppts, inputs_per_mppt)
    
    # Compute active strings and panels per string from the solution
    total_strings_per_inv = sum(s for s, p in sol)
    total_strings = total_strings_per_inv * inverter_qty
    
    active_lengths = [p for s, p in sol if s > 0]
    if active_lengths:
        panels_per_string = int(round(sum(active_lengths) / len(active_lengths)))
    else:
        panels_per_string = 0
        
    string_voltage_v = panels_per_string * panel_vmp
    
    # Panels per MPPT formula:
    # (Max PV Input Power / Number of MPPTs) / Power of selected panel
    max_pv_input_kw = inverter_kw_std * (1.3 if system_voltage_dc <= 48 else 1.5)
    max_power_per_mppt_kw = max_pv_input_kw / num_mppts
    panels_per_mppt = max(1, math.floor(max_power_per_mppt_kw / single_module_kw))
    
    stringing = StringingResult(
        panel_wp=panel_wp,
        panel_voc=panel_voc,
        max_inverter_vin=max_inverter_vin,
        tmin_celsius=tmin_celsius,
        temp_coeff_k=temp_coeff_k,
        max_panels_per_string=max_panels_per_string,
        panels_per_mppt=panels_per_mppt,
        total_strings=total_strings,
        string_voltage_v=string_voltage_v,
        panels_per_string=panels_per_string,
        stringing_grid=grid,
    )
    
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
    # Voltage Drop (V.D) = 0.03 * (No of panels in largest selected string * Voc of selected panel)
    dc_allowable_vd = 0.03 * (panels_per_string * panel_voc)
    rho_copper = 0.0178 # ohm.mm²/m (r)
    # L should not be less than 50m
    effective_L = max(50.0, dc_cable_distance_m)
    dc_area_calc = (panel_imp * rho_copper * 2.0 * effective_L) / max(0.1, dc_allowable_vd)
    dc_recommended_sqmm = 4 if dc_area_calc <= 4 else (6 if dc_area_calc <= 6 else 10)
    dc_total_length = effective_L * 2.0 * total_strings
    
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
        inverter_brand=inverter_brand,
        voltage_architecture=voltage_architecture,
        mppt_rating_per_unit=max(60, math.ceil(panel_imp * 2)),
        mppt_qty=num_mppts * inverter_qty,
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
        f"| **Selected Inverter Model** | `{result.inverter_brand}` | Grid-Tied → Huawei SUN2000 / Hybrid → Deye Hybrid |",
        f"| **Voltage Architecture** | `{result.voltage_architecture}` | LV: 48V BESS / 500V DC / HV: 384V+ BESS / 1000V DC |",
        f"| **Proposed Inverter Size** | `{result.inverter_kw:.1f} kW` (`{result.inverter_kva:.1f} kVA`) | Sized with `1.25x` safety factor |",
        f"| **No. of Inverters** | `{result.inverter_qty} pcs` | Total AC Capacity: `{result.inverter_kw * result.inverter_qty:.1f} kW` |",
        "",
        "### 🔗 2. Stringing & MPPT Configuration",
        "| Parameter | Specification | Calculation / Reference |",
        "|---|---|---|",
        f"| **Max Inverter DC Input ($V_{{in,max}}$)** | `{result.stringing.max_inverter_vin:.0f} V DC` | Retreived from Inverter Datasheet |",
        f"| **Panel Open Circuit Voltage ($V_{{oc}}$)** | `{result.stringing.panel_voc:.2f} V DC` | Retreived from Panel Datasheet |",
        f"| **Max Panels in a String** | `{result.stringing.max_panels_per_string} pcs` | Formula: `floor(Vin_max / (Voc * (1 + K*(Tmin - 25°C))))` |",
        f"| **Panels per MPPT** | `{result.stringing.panels_per_mppt} panels/MPPT` | Rule: `floor((Max PV Input Power / No. of MPPTs) / Panel kWp)` |",
        f"| **Total Number of Strings** | `{result.stringing.total_strings} strings` | Recommended stringing distribution |",
        f"| **Operating String Voltage** | `{result.stringing.string_voltage_v:.1f} V DC` | Optimal MPPT tracking window |",
    ]

    if result.stringing and hasattr(result.stringing, "stringing_grid") and result.stringing.stringing_grid:
        grid = result.stringing.stringing_grid
        lines += [
            "",
            "#### 📊 MPPT Stringing Grid Configuration Detail",
            "*(Number of panels per Input string, mapped to each MPP Tracker)*",
            "",
            "| Input \\ MPPT | " + " | ".join(f"**MPPT {i+1}**" for i in range(len(grid[0]))) + " |",
            "|---| " + " | ".join("---" for _ in range(len(grid[0]))) + " |"
        ]
        for row_idx, row in enumerate(grid):
            row_cols = []
            for val in row:
                row_cols.append(f"**{val}**" if val is not None else "-")
            lines.append(f"| **Input {row_idx + 1}** | " + " | ".join(row_cols) + " |")

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
            f"| **PV DC String Cable** | `{cs.dc_recommended_cable_sqmm} mm²` TCU/XLPO (`1.5/1.5kVdc`) | Formula: `I*r*2L / VD` (Total length: `{cs.dc_total_length_m:.0f} m`) | 1000V DC Isolator & Type II SPD |",
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
