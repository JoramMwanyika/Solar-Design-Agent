from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from agent.system_sizer import LoadItem

@dataclass
class ProjectState:
    """
    Holds the complete state of a solar design project as it moves through the multiagent system.
    """
    # 1. Intake / Project Details
    project_name: str = "Untitled Solar Project"
    client_name: str = ""
    location: str = "East Africa"
    system_type: str = "off-grid"  # 'off-grid', 'hybrid', 'grid-tied'
    
    # 2. Unified Energy Output (Single Source of Truth)
    daily_energy_kwh: float = 0.0
    peak_demand_kw: float = 0.0
    connected_load_kw: float = 0.0
    critical_load_kw: float = 0.0
    critical_energy_kwh: float = 0.0
    night_energy_kwh: float = 0.0
    load_factor: float = 1.0
    demand_factor: float = 1.0
    diversity_factor: float = 1.0
    power_factor: float = 0.94
    design_confidence: float = 1.0
    loads: List[Dict[str, Any]] = field(default_factory=list)
    
    # 3. Solar Resource & Preferences
    peak_sun_hours: float = 4.5
    days_of_autonomy: float = 1.0
    dod: float = 0.8
    system_voltage_dc: int = 48
    battery_voltage: float = 51.2
    panel_wp: int = 550
    
    # 4. PV Design
    total_pv_kwp: float = 0.0
    panel_qty: int = 0
    pv_strings: int = 0
    panels_per_string: int = 0
    operating_dc_voltage: float = 0.0
    
    # 5. Battery Design
    total_storage_kwh: float = 0.0
    usable_storage_kwh: float = 0.0
    battery_qty: int = 0
    battery_stacks: int = 0
    battery_breaker_a: float = 0.0
    
    # 6. Inverter Selection
    inverter_kw: float = 0.0
    inverter_kva: float = 0.0
    inverter_qty: int = 1
    ac_breaker_a: float = 0.0
    
    # 7. Cable & Protection
    dc_cable_mm2: float = 0.0
    ac_cable_mm2: float = 0.0
    
    # 8. Output & Review
    boq_items: List[Dict[str, Any]] = field(default_factory=list)
    engineering_review: str = ""
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_name": self.project_name,
            "client_name": self.client_name,
            "location": self.location,
            "system_type": self.system_type,
            "daily_energy_kwh": self.daily_energy_kwh,
            "peak_demand_kw": self.peak_demand_kw,
            "connected_load_kw": self.connected_load_kw,
            "critical_load_kw": self.critical_load_kw,
            "critical_energy_kwh": self.critical_energy_kwh,
            "night_energy_kwh": self.night_energy_kwh,
            "load_factor": self.load_factor,
            "demand_factor": self.demand_factor,
            "diversity_factor": self.diversity_factor,
            "power_factor": self.power_factor,
            "design_confidence": self.design_confidence,
            "peak_sun_hours": self.peak_sun_hours,
            "days_of_autonomy": self.days_of_autonomy,
            "dod": self.dod,
            "system_voltage_dc": self.system_voltage_dc,
            "battery_voltage": self.battery_voltage,
            "panel_wp": self.panel_wp,
            "total_pv_kwp": self.total_pv_kwp,
            "panel_qty": self.panel_qty,
            "pv_strings": self.pv_strings,
            "panels_per_string": self.panels_per_string,
            "operating_dc_voltage": self.operating_dc_voltage,
            "total_storage_kwh": self.total_storage_kwh,
            "usable_storage_kwh": self.usable_storage_kwh,
            "battery_qty": self.battery_qty,
            "battery_stacks": self.battery_stacks,
            "battery_breaker_a": self.battery_breaker_a,
            "inverter_kw": self.inverter_kw,
            "inverter_kva": self.inverter_kva,
            "inverter_qty": self.inverter_qty,
            "ac_breaker_a": self.ac_breaker_a,
            "dc_cable_mm2": self.dc_cable_mm2,
            "ac_cable_mm2": self.ac_cable_mm2,
            "engineering_review": self.engineering_review,
            "warnings": self.warnings,
            "loads": self.loads
        }
