"""
BOQ Generator for Solar PV Systems.
Generates structured Bill of Quantities aligned with client sample workbooks:
- 14-15 standard installation & equipment categories
- Strict quantities-only mode ("Pricing in BOQ — should include quantities only")
- Includes exact items: PV modules, mounting structure, solar string cables, inverters/BESS,
  DCDB/ACDB switchgear, earthing/LPS, cable containment/trunking, civil works, installation & commissioning.
- Exports both professional Excel (.xlsx) using openpyxl and clean Markdown tables.
"""
from io import BytesIO
from typing import Dict, List, Optional
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


def generate_boq(sizing: dict, project_name: str = "Solar PV System") -> List[Dict]:
    """
    Generates a standardized BOQ item list from sizing results.
    Strictly outputs quantities only (unit costs / total costs left empty/0 per client spec).
    """
    boq: List[Dict] = []
    
    # Extract key sizing parameters
    panel_qty = sizing.get("panel_qty", 80)
    panel_wp = sizing.get("panel_wp", 625)
    inverter_kw = sizing.get("inverter", {}).get("kw", 50)
    inverter_qty = sizing.get("inverter", {}).get("qty", 1)
    
    battery_info = sizing.get("battery", {})
    battery_qty = battery_info.get("qty", 0)
    battery_type = battery_info.get("type", "Dyness Stack280 14.33kWh HV Battery")
    
    string_info = sizing.get("stringing", {})
    total_strings = string_info.get("total_strings", 6)
    
    cables_info = sizing.get("cables", {})
    dc_sqmm = cables_info.get("dc_sqmm", 4)
    dc_total_m = cables_info.get("dc_total_m", 120)
    ac_sqmm = cables_info.get("ac_sqmm", 25)
    ac_breaker_a = cables_info.get("ac_breaker_a", 125)
    
    system_type = sizing.get("system_type", "hybrid")

    # 1. Solar Panels
    boq.append({
        "item_no": "1",
        "category": "Solar Panels",
        "description": f"{panel_wp}Wp High-Efficiency Monocrystalline PV Modules (Tier 1 Jinko/JA Solar/Longi)",
        "unit": "Pcs",
        "quantity": panel_qty,
        "unit_cost": "",
        "total_cost": "",
        "remarks": f"Total PV Capacity: {(panel_qty * panel_wp)/1000:.2f} kWp"
    })

    # 2. Solar Mounting Structure & Accessories
    boq.append({
        "item_no": "2.1",
        "category": "Mounting Structure",
        "description": "Anodized Aluminum Roof/Carport Mounting Structure Rails, L-Feet, Roof Hooks & Clamps",
        "unit": "Set",
        "quantity": panel_qty,
        "unit_cost": "",
        "total_cost": "",
        "remarks": "Includes mid/end clamps, earthing clips, and EPDM waterproof rubber gaskets"
    })
    boq.append({
        "item_no": "2.2",
        "category": "Mounting Structure",
        "description": "Stainless steel fasteners, hanger bolts, and structural rail joiners/connectors",
        "unit": "Lot",
        "quantity": 1,
        "unit_cost": "",
        "total_cost": "",
        "remarks": "Corrosion resistant grade A2/A4"
    })

    # 3. Solar String Cables & Connectors
    boq.append({
        "item_no": "3.1",
        "category": "DC Cabling",
        "description": f"Solar DC Cable {dc_sqmm}mm² Red (Tinned Copper, XLPO, 1.5/1.5kVdc UV Resistant)",
        "unit": "m",
        "quantity": max(100, int(dc_total_m * 0.55)),
        "unit_cost": "",
        "total_cost": "",
        "remarks": "Positive string runs from array to PVDB"
    })
    boq.append({
        "item_no": "3.2",
        "category": "DC Cabling",
        "description": f"Solar DC Cable {dc_sqmm}mm² Black (Tinned Copper, XLPO, 1.5/1.5kVdc UV Resistant)",
        "unit": "m",
        "quantity": max(100, int(dc_total_m * 0.55)),
        "unit_cost": "",
        "total_cost": "",
        "remarks": "Negative string runs from array to PVDB"
    })
    boq.append({
        "item_no": "3.3",
        "category": "DC Cabling",
        "description": "MC4 Male/Female Waterproof Branch & String Connectors (1500V DC rated, IP68)",
        "unit": "Pair",
        "quantity": max(10, total_strings * 3),
        "unit_cost": "",
        "total_cost": "",
        "remarks": "Original Staubli or certified equivalent"
    })

    # 4. Inverters & BESS
    inv_desc = f"{inverter_kw}kW On-Grid / Hybrid 3-Phase Solar Inverter (Deye / Huawei / GoodWe / Sungrow)"
    boq.append({
        "item_no": "4.1",
        "category": "Power Conversion",
        "description": inv_desc,
        "unit": "Pcs",
        "quantity": inverter_qty,
        "unit_cost": "",
        "total_cost": "",
        "remarks": "Includes Wi-Fi/4G smart dongle and CT current sensors for zero-export"
    })

    if system_type in ("off-grid", "hybrid") and battery_qty > 0:
        boq.append({
            "item_no": "4.2",
            "category": "Battery Storage (BESS)",
            "description": f"{battery_type} (High Voltage LFP Battery Stack)",
            "unit": "Pcs",
            "quantity": battery_qty,
            "unit_cost": "",
            "total_cost": "",
            "remarks": f"Total BESS capacity: {battery_qty * 14.33:.1f} kWh"
        })
        boq.append({
            "item_no": "4.3",
            "category": "Battery Storage (BESS)",
            "description": "High Voltage Battery Rack / Stack Enclosure, BMS Controller & Communication cables",
            "unit": "Set",
            "quantity": max(1, (battery_qty + 8) // 9),
            "unit_cost": "",
            "total_cost": "",
            "remarks": "Includes HV BMS control box and base pedestal"
        })

    # 5. DC Protection & Switchgear
    boq.append({
        "item_no": "5.1",
        "category": "DC Switchgear",
        "description": f"PV Combiner Box / DC Distribution Board (PVDB) for {total_strings} Strings with 1000V DC SPD Type II, Fuses & Isolator",
        "unit": "Set",
        "quantity": 1,
        "unit_cost": "",
        "total_cost": "",
        "remarks": "IP65 weatherproof polycarbonate wall-mounted enclosure"
    })
    if battery_qty > 0:
        boq.append({
            "item_no": "5.2",
            "category": "DC Switchgear",
            "description": "Battery Breaker Box with 160A/250A 1000V DC Molded Case Circuit Breaker (MCCB)",
            "unit": "Set",
            "quantity": 1,
            "unit_cost": "",
            "total_cost": "",
            "remarks": "Sized with 1.25x safety margin for high charge/discharge current"
        })

    # 6. AC Switchgear & Board
    boq.append({
        "item_no": "6",
        "category": "AC Switchgear",
        "description": f"AC Distribution Board (ACDB) with {ac_breaker_a}A 4-Pole MCCB, Type II AC SPD, Over/Under Voltage Relay & Pilot Lights",
        "unit": "Set",
        "quantity": 1,
        "unit_cost": "",
        "total_cost": "",
        "remarks": "Connects inverter output to main facility supply/grid panel"
    })

    # 7. DC & AC Cables / Feeder Runs
    if battery_qty > 0:
        boq.append({
            "item_no": "7.1",
            "category": "Cabling & Feeder Runs",
            "description": "Battery HV Power Cable 50mm² / 16mm² CU/PVC/PVC-Nitrile (Tower to Breaker & Inverter)",
            "unit": "m",
            "quantity": 30,
            "unit_cost": "",
            "total_cost": "",
            "remarks": "Flexible orange/black battery power runs with heavy duty lugs"
        })
    boq.append({
        "item_no": "7.2",
        "category": "Cabling & Feeder Runs",
        "description": f"4-Core {ac_sqmm}mm² CU/XLPE/PVC Armoured/Unarmoured AC Main Feeder Cable (0.6/1kV)",
        "unit": "m",
        "quantity": max(50, int(sizing.get("cables", {}).get("ac_distance_m", 60))),
        "unit_cost": "",
        "total_cost": "",
        "remarks": "Main AC interconnection between inverter and facility switchboard"
    })
    boq.append({
        "item_no": "7.3",
        "category": "Cabling & Feeder Runs",
        "description": "Heavy duty tinned copper cable lugs, cable ties, glands, heat shrink tubes, and warning labels",
        "unit": "Lot",
        "quantity": 1,
        "unit_cost": "",
        "total_cost": "",
        "remarks": "Complete electrical termination kit"
    })

    # 8. Earthing & Lightning Protection System (LPS)
    boq.append({
        "item_no": "8.1",
        "category": "Earthing & LPS",
        "description": "Earthing Cable 16mm² CU/PVC Green/Yellow (Inverter, PVDB, Roof to Main Earthpit)",
        "unit": "m",
        "quantity": 120,
        "unit_cost": "",
        "total_cost": "",
        "remarks": "Dedicated clean earth and structure bonding runs"
    })
    boq.append({
        "item_no": "8.2",
        "category": "Earthing & LPS",
        "description": "Earthing Cable 6mm² CU/PVC Green/Yellow (Rail-to-Rail inter-bonding)",
        "unit": "m",
        "quantity": 60,
        "unit_cost": "",
        "total_cost": "",
        "remarks": "Equipotential bonding of all solar array rails"
    })
    boq.append({
        "item_no": "8.3",
        "category": "Earthing & LPS",
        "description": "Pure Copper Earth Rod (1.5m x 16mm) with heavy duty brass clamp & inspection pit cover",
        "unit": "Set",
        "quantity": 3,
        "unit_cost": "",
        "total_cost": "",
        "remarks": "Achieving earth resistance < 5 ohms"
    })
    boq.append({
        "item_no": "8.4",
        "category": "Earthing & LPS",
        "description": "25x3mm Copper Tape / Air terminal system for Lightning Protection System (LPS)",
        "unit": "m",
        "quantity": 40,
        "unit_cost": "",
        "total_cost": "",
        "remarks": "Surge and direct strike mitigation"
    })

    # 9. Containment & Cable Trunking
    boq.append({
        "item_no": "9.1",
        "category": "Containment",
        "description": "Hot-dip galvanized perforated cable tray (150x50mm) with covers and jointing brackets",
        "unit": "m",
        "quantity": 45,
        "unit_cost": "",
        "total_cost": "",
        "remarks": "Outdoor / rooftop cable protection"
    })
    boq.append({
        "item_no": "9.2",
        "category": "Containment",
        "description": "Heavy duty PVC trunking and flexible conduit pipes (25mm/32mm) with saddles and fittings",
        "unit": "Lot",
        "quantity": 1,
        "unit_cost": "",
        "total_cost": "",
        "remarks": "Indoor wall-mounted and drop cable runs"
    })

    # 10. Civil Works & Foundations
    boq.append({
        "item_no": "10.1",
        "category": "Civil Works",
        "description": "Reinforced concrete plinth / equipment foundation for inverter, BESS rack and outdoor enclosures",
        "unit": "Lot",
        "quantity": 1,
        "unit_cost": "",
        "total_cost": "",
        "remarks": "Grade C25/30 concrete with cable trenching if outdoor"
    })
    boq.append({
        "item_no": "10.2",
        "category": "Civil Works",
        "description": "Earth pit excavation, chemical treatment (Bentonite/Marconite) and backfilling",
        "unit": "Lot",
        "quantity": 1,
        "unit_cost": "",
        "total_cost": "",
        "remarks": "For grounding system installation"
    })

    # 11. Installation & Electrical Assembly
    boq.append({
        "item_no": "11.1",
        "category": "Installation Services",
        "description": "Mechanical installation of mounting structures and alignment/clamping of solar modules",
        "unit": "Lot",
        "quantity": 1,
        "unit_cost": "",
        "total_cost": "",
        "remarks": "Certified mechanical solar installation crew"
    })
    boq.append({
        "item_no": "11.2",
        "category": "Installation Services",
        "description": "Complete electrical wiring, cable pulling, termination, switchgear mounting and interconnections",
        "unit": "Lot",
        "quantity": 1,
        "unit_cost": "",
        "total_cost": "",
        "remarks": "Licensed electrical technicians per local codes"
    })

    # 12. Testing, Commissioning & Documentation
    boq.append({
        "item_no": "12.1",
        "category": "Testing & Commissioning",
        "description": "System testing (Voc, Isc, insulation resistance, earth resistance), inverter programming and grid commissioning",
        "unit": "Lot",
        "quantity": 1,
        "unit_cost": "",
        "total_cost": "",
        "remarks": "Full handover checklist with performance verification"
    })
    boq.append({
        "item_no": "12.2",
        "category": "Testing & Commissioning",
        "description": "As-Built electrical single-line drawings (SLD), operation & maintenance manuals, and user training",
        "unit": "Set",
        "quantity": 1,
        "unit_cost": "",
        "total_cost": "",
        "remarks": "Includes factory warranty certificates for panels/inverters/batteries"
    })

    # 13. Smart Monitoring System
    boq.append({
        "item_no": "13",
        "category": "Monitoring",
        "description": "Smart Energy Meter with 3-Phase CT coils for real-time generation, load tracking & remote portal access",
        "unit": "Set",
        "quantity": 1,
        "unit_cost": "",
        "total_cost": "",
        "remarks": "Includes lifetime cloud monitoring account setup"
    })

    # 14. Transportation & Site Logistics
    boq.append({
        "item_no": "14",
        "category": "Logistics",
        "description": "Transportation, insurance in transit, offloading and site material handling for all equipment",
        "unit": "Lot",
        "quantity": 1,
        "unit_cost": "",
        "total_cost": "",
        "remarks": "Delivery directly to project site"
    })

    return boq


def boq_to_markdown_table(boq_items: List[Dict]) -> str:
    """Converts BOQ items list into a clean markdown table (Quantities only mode)."""
    lines = [
        "| Item | Category | Description & Specifications | Qty | Unit | Unit Cost | Total Cost | Remarks |",
        "|---|---|---|:---:|:---:|:---:|:---:|---|",
    ]
    for item in boq_items:
        lines.append(
            f"| `{item.get('item_no', '')}` | **{item.get('category', '')}** | {item.get('description', '')} | "
            f"**{item.get('quantity', '')}** | `{item.get('unit', '')}` | - | - | *{item.get('remarks', '')}* |"
        )
    return "\n".join(lines)


def boq_to_markdown(boq: List[Dict], project_name: str = "Solar PV System") -> str:
    """Convenience wrapper around boq_to_markdown_table with header."""
    return f"## 📋 Bill of Quantities (BOQ) — {project_name}\n\n" + boq_to_markdown_table(boq)


def generate_boq_excel(
    boq_items: List[Dict],
    project_name: str = "Solar PV System",
    system_type: str = "hybrid",
    location: str = "",
    client_name: str = "",
    prepared_by: str = "",
    sizing_summary: Optional[Dict] = None,
) -> bytes:
    """
    Generates a professional, beautifully styled Excel spreadsheet (.xlsx) for the BOQ.
    Strict quantities-only pricing rule is applied (Unit Cost and Total Cost columns are left open for procurement).
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Bill of Quantities"

    # Fonts & Fills
    title_font = Font(name="Calibri", size=16, bold=True, color="FFFFFF")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    data_font = Font(name="Calibri", size=10)
    bold_font = Font(name="Calibri", size=10, bold=True)
    
    header_fill = PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid") # Navy Blue
    category_fill = PatternFill(start_color="E8EEF5", end_color="E8EEF5", fill_type="solid") # Soft Blue/Grey
    price_col_fill = PatternFill(start_color="FFF0F0", end_color="FFF0F0", fill_type="solid") # Soft Salmon per client template

    thin_border = Border(
        left=Side(style="thin", color="CCCCCC"),
        right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"),
        bottom=Side(style="thin", color="CCCCCC"),
    )

    # Title Block
    ws.merge_cells("A1:H1")
    ws["A1"] = f"BILL OF QUANTITIES — {project_name.upper()}"
    ws["A1"].font = title_font
    ws["A1"].fill = header_fill
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 36

    # Metadata Header
    ws["A3"] = "Project Name:"
    ws["B3"] = project_name
    ws["A4"] = "Client Name:"
    ws["B4"] = client_name or "General Client"
    ws["E3"] = "System Type:"
    ws["F3"] = system_type.upper()
    ws["E4"] = "Location:"
    ws["F4"] = location or "East Africa"
    ws["E5"] = "Prepared By:"
    ws["F5"] = prepared_by or "Solar Design Agent AI"
    
    for row in range(3, 6):
        for col in [1, 5]:
            ws.cell(row=row, column=col).font = bold_font

    # Table Headers
    headers = ["Item No.", "Category", "Description & Specifications", "Qty", "Unit", "Rate / Unit Cost", "Total Cost", "Remarks"]
    header_row = 7
    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=header_row, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[header_row].height = 26

    # Insert Items
    curr_row = 8
    curr_category = ""
    for item in boq_items:
        # Category separator row if new category
        cat = item.get("category", "")
        if cat != curr_category:
            curr_category = cat
            ws.merge_cells(start_row=curr_row, start_column=1, end_row=curr_row, end_column=8)
            cat_cell = ws.cell(row=curr_row, column=1, value=f"  {curr_category.upper()}")
            cat_cell.font = bold_font
            cat_cell.fill = category_fill
            cat_cell.alignment = Alignment(vertical="center")
            ws.row_dimensions[curr_row].height = 22
            for c in range(1, 9):
                ws.cell(row=curr_row, column=c).border = thin_border
            curr_row += 1

        # Item row
        ws.cell(row=curr_row, column=1, value=item.get("item_no", "")).alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(row=curr_row, column=2, value=cat).alignment = Alignment(vertical="center")
        desc_cell = ws.cell(row=curr_row, column=3, value=item.get("description", ""))
        desc_cell.alignment = Alignment(vertical="center", wrap_text=True)
        
        ws.cell(row=curr_row, column=4, value=item.get("quantity", "")).alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(row=curr_row, column=5, value=item.get("unit", "")).alignment = Alignment(horizontal="center", vertical="center")
        
        # Unit Cost & Total Cost columns left blank with soft salmon fill ("Pricing in BOQ — should include quantities only")
        uc_cell = ws.cell(row=curr_row, column=6, value="")
        uc_cell.fill = price_col_fill
        tc_cell = ws.cell(row=curr_row, column=7, value="")
        tc_cell.fill = price_col_fill
        
        ws.cell(row=curr_row, column=8, value=item.get("remarks", "")).alignment = Alignment(vertical="center")

        for c in range(1, 9):
            ws.cell(row=curr_row, column=c).font = data_font
            ws.cell(row=curr_row, column=c).border = thin_border
            
        ws.row_dimensions[curr_row].height = 24
        curr_row += 1

    # Summary Row
    ws.merge_cells(start_row=curr_row, start_column=1, end_row=curr_row, end_column=5)
    sum_cell = ws.cell(row=curr_row, column=1, value="SUB-TOTAL FOR EQUIPMENT & INSTALLATION (QUANTITIES ONLY)")
    sum_cell.font = bold_font
    sum_cell.alignment = Alignment(horizontal="right", vertical="center")
    ws.cell(row=curr_row, column=6).fill = price_col_fill
    ws.cell(row=curr_row, column=7).fill = price_col_fill
    ws.row_dimensions[curr_row].height = 26
    for c in range(1, 9):
        ws.cell(row=curr_row, column=c).border = thin_border

    # Auto-adjust column widths
    col_widths = {1: 10, 2: 22, 3: 45, 4: 10, 5: 10, 6: 16, 7: 16, 8: 35}
    for col_idx, width in col_widths.items():
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    out = BytesIO()
    wb.save(out)
    return out.getvalue()
