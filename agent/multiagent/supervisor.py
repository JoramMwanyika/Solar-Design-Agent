import json
import math
from typing import Callable, Optional, Tuple, List, Dict, Any
from agent.multiagent.state import ProjectState
from agent.multiagent.agents import ALL_AGENTS, _extract_json
from agent.multiagent.tools.math_tools import (
    get_location_psh, size_pv_array, size_inverter, size_battery, load_jinko_specs
)

# Agents that produce the Unified Energy Output (i.e. trigger the full sizing pipeline)
ENERGY_ANALYSIS_AGENTS = {
    "Bill Analysis Agent",
    "Load Analysis Agent",
    "Appliance Analysis Agent",
}

# Mapping of state keys to their tool result keys for each sizing tool
_PV_RESULT_KEYS = {
    "required_pv_kwp": None,     # informational
    "panel_qty": "panel_qty",
    "total_pv_kwp": "total_pv_kwp",
}
_INV_RESULT_KEYS = {
    "inverter_kw_std": "inverter_kw",
    "inverter_kva": "inverter_kva",
    "inverter_qty": "inverter_qty",
    "inverter_brand": "inverter_brand",
    "voltage_architecture": "voltage_architecture",
}
_BAT_RESULT_KEYS = {
    "battery_qty": "battery_qty",
    "total_storage_kwh": "total_storage_kwh",
    "battery_stacks": "battery_stacks",
    "battery_breaker_a": "battery_breaker_a",
}


class SupervisorAgent:
    """
    The main orchestrator of the Multiagent System.
    It manages conversational memory, routes user requests to specialized agents,
    runs the agent tool-calling loops, and maintains state synchronization.
    """
    def __init__(self, llm_generate_func: Callable[[str], str]):
        self.generate_content = llm_generate_func

    def _format_history(self, history: Optional[List[Dict[str, str]]]) -> str:
        if not history:
            return "No previous conversation history."
        formatted = []
        recent = history[-8:]
        for msg in recent:
            role = "User" if msg.get("role") == "user" else "Assistant"
            content = msg.get("content", "")
            if len(content) > 600:
                content = content[:600] + "... [truncated]"
            formatted.append(f"{role}: {content}")
        return "\n".join(formatted)

    def _route(self, user_input: str, state_json: str, history_str: str) -> Tuple[Optional[str], str]:
        """Asks the LLM supervisor to decide the next specialized agent or answer directly."""
        prompt = (
            "You are SolarBot, an expert AI Solar PV Design Engineer and lead orchestrator of a multi-agent solar sizing system.\n"
            "Your role is to converse naturally with the customer, understand their needs, maintain context, and invoke specialized agents/tools when needed.\n\n"
            f"Recent Conversation History:\n{history_str}\n\n"
            f"Current Project State:\n{state_json}\n\n"
            f"New User Request:\n{user_input}\n\n"
            "Available Specialized Agents:\n" + "\n".join([f"- {name}: {agent.role}" for name, agent in ALL_AGENTS.items()]) + "\n\n"
            "Routing Instructions:\n"
            "1. If the user is providing project location, asking questions, seeking engineering advice, or chatting naturally, set next_agent to 'None' and provide a warm, professional, markdown response.\n"
            "2. If the user provides a bill, logger data, load schedule, or requests calculations, route to the relevant specialized agent.\n\n"
            "CRITICAL SYSTEM DESIGN & MATHEMATICAL RULES:\n"
            "- Inverter Brand Rule: Use Huawei inverters for Grid-Tied systems; use Deye or Solis inverters for Off-Grid / Hybrid systems.\n"
            "- Inverter Architecture: Distinguish between Low Voltage (LV 48V BESS / 500V DC Vin) and High Voltage (HV 384V+ BESS / 1000V DC Vin).\n"
            "- Panels per MPPT Rule: Panels per MPPT = floor((Max PV Input Power / No. of MPPTs) / Panel kWp).\n"
            "- Direct Sizing Formula: Required DC Capacity (kWp) = Daily Energy (kWh) ÷ Peak Sun Hours (h/day). Do NOT include loss factors.\n"
            "- Time-Series Logged Data Rule: Calculate total average energy for every day from logged Power_Total_average (Apparent Power S / Active Power P). Select the day with the HIGHEST average daily energy to size the DC capacity (Required DC Capacity kWp = max_daily_energy_kwh / PSH).\n"
            "- LOAD PROFILE / APPLIANCE LIST RULE (CRITICAL):\n"
            "    Step 1: If energy is given, use the given energy directly for sizing. If energy is not given, calculate energy for each load (rating × qty × hours × diversity_factor × utilisation_factor) and sum to get total daily energy.\n"
            "    Step 2: Output the exact `appliance_breakdown` returned by the tool. DO NOT do manual math!\n"
            "    Step 3: Size ALL components from that energy:\n"
            "      • PV Array : Required kWp = daily_energy_kwh / PSH\n"
            "      • Battery  : Required kWh = (daily_energy_kwh × days_autonomy) / DoD × 1.25\n"
            "      • Inverter : Call size_inverter with peak_demand_kw=0.0 so inverter_kw = total_pv_kwp (energy-driven, NOT connected load sum).\n\n"
            "Return ONLY a raw JSON block:\n"
            "If routing: {\"next_agent\": \"Agent Name\", \"reason\": \"...\"}\n"
            "If answering directly: {\"next_agent\": \"None\", \"response\": \"Your detailed conversational answer...\"}"
        )
        
        response_text = self.generate_content(prompt)
        data = _extract_json(response_text)
        if data:
            next_agent = data.get("next_agent", "None")
            detail = data.get("response", data.get("reason", ""))
            return next_agent, detail
        return "None", response_text.strip()

    def _run_agent(self, agent_name: str, state: ProjectState, context: str) -> Dict[str, Any]:
        """
        Runs a single agent's ReAct loop until completion or max iterations.
        Returns {"message": str, "tool_results": dict} where tool_results accumulates
        all tool outputs so the caller can apply them to state.
        """
        agent = ALL_AGENTS[agent_name]
        agent_context = context
        accumulated_tool_results: Dict[str, Any] = {}
        max_iterations = 6
        
        for _ in range(max_iterations):
            prompt = agent.get_system_prompt(json.dumps(state.to_dict(), indent=2)) + "\n\n" + agent_context
            llm_output = self.generate_content(prompt)
            result = agent.process_llm_response(llm_output, state)
            
            if result["type"] == "complete":
                msg = result.get("message", "Task complete.")
                if msg.startswith(f"**{agent.name}**"):
                    msg = msg[len(f"**{agent.name}**"):].lstrip(" :")
                return {"message": msg, "tool_results": accumulated_tool_results}
                
            elif result["type"] == "tool_call":
                tool_result = result.get("result", {})
                accumulated_tool_results.update(tool_result)
                # Apply energy output schema immediately to state so subsequent agents see it
                self._apply_energy_output_to_state(tool_result, state)
                agent_context += f"\nTool executed: {result['tool']}\nResult: {json.dumps(tool_result)}\n"
                
            elif result["type"] == "tool_error":
                agent_context += f"\nTool error: {result['tool']} failed - {result['error']}\n"
            else:
                return {"message": result.get("message", llm_output.strip()), "tool_results": accumulated_tool_results}
        
        return {"message": "Analysis completed.", "tool_results": accumulated_tool_results}

    def _apply_energy_output_to_state(self, tool_result: Dict[str, Any], state: ProjectState):
        """
        Applies Unified Energy Output schema fields from a tool result directly to state.
        This ensures subsequent agents see the latest values.
        """
        energy_fields = [
            "daily_energy_kwh", "peak_demand_kw", "connected_load_kw",
            "critical_load_kw", "critical_energy_kwh", "night_energy_kwh",
            "load_factor", "demand_factor", "diversity_factor", "power_factor",
            "design_confidence",
        ]
        for field in energy_fields:
            if field in tool_result:
                setattr(state, field, tool_result[field])

    def _run_full_sizing_pipeline(self, state: ProjectState) -> str:
        """
        Runs the deterministic sizing pipeline using math tools directly.
        Called after any Energy Analysis Agent sets daily_energy_kwh on state.
        Returns a full markdown summary of all sizing results.
        """
        # ── 1. Ensure PSH is set ────────────────────────────────────────────────
        if state.peak_sun_hours <= 0:
            psh_data = get_location_psh(state.location)
            state.peak_sun_hours = psh_data["peak_sun_hours"]
        psh = state.peak_sun_hours
        daily_kwh = state.daily_energy_kwh

        # ── 2. Size PV Array ────────────────────────────────────────────────────
        pv = size_pv_array(
            daily_energy_kwh=daily_kwh,
            psh=psh,
            peak_demand_kw=0.0,   # energy-driven; never use raw demand sum
            panel_wp=float(state.panel_wp),
        )
        state.total_pv_kwp = pv["total_pv_kwp"]
        state.panel_qty     = pv["panel_qty"]
        required_pv_kwp     = pv["required_pv_kwp"]

        # ── 3. Size Inverter ────────────────────────────────────────────────────
        # For load-profile and bill sources, peak_demand_kw was set to 0.0 by the
        # energy analysis agent, so the inverter is sized from PV capacity.
        inv = size_inverter(
            system_type=state.system_type,
            peak_demand_kw=state.peak_demand_kw,   # 0.0 for load-profile
            total_pv_kwp=state.total_pv_kwp,
            power_factor=state.power_factor,
            system_voltage_dc=float(state.system_voltage_dc),
        )
        state.inverter_kw           = inv["inverter_kw_std"]
        state.inverter_kva          = inv["inverter_kva"]
        state.inverter_qty          = inv["inverter_qty"]
        state.inverter_brand        = inv["inverter_brand"]
        state.voltage_architecture  = inv["voltage_architecture"]
        system_voltage_dc           = state.system_voltage_dc or 48

        # ── 4. Size Battery (off-grid / hybrid only) ────────────────────────────
        # Choose battery module size based on voltage architecture
        if system_voltage_dc > 48 or state.system_type not in ("off-grid", "hybrid"):
            battery_module_kwh = 14.33    # HV stacked BESS (e.g. Pylontech SC series)
        else:
            battery_module_kwh = 5.12     # LV 48V BESS (e.g. Pylontech US series)

        bat = size_battery(
            system_type=state.system_type,
            daily_energy_kwh=daily_kwh,
            days_of_autonomy=state.days_of_autonomy,
            dod=state.dod,
            battery_module_kwh=battery_module_kwh,
            inverter_kw_std=state.inverter_kw,
            system_voltage_dc=float(system_voltage_dc),
        )
        state.battery_qty        = bat["battery_qty"]
        state.total_storage_kwh  = bat["total_storage_kwh"]
        state.usable_storage_kwh = round(bat["total_storage_kwh"] * state.dod, 2)
        state.battery_stacks     = bat["battery_stacks"]
        state.battery_breaker_a  = bat["battery_breaker_a"]

        # ── 5. Panel specs for stringing info ───────────────────────────────────
        jinko = load_jinko_specs()
        panel_wp  = state.panel_wp
        panel_voc = jinko["panel_voc"]
        panel_vmp = jinko["panel_vmp"]

        # Basic stringing estimate for the summary (full stringing uses calculate_stringing tool)
        max_vin = inv.get("max_inverter_vin", 1000.0)
        max_pps = max(1, math.floor(max_vin / panel_voc)) if panel_voc > 0 else 20
        strings  = max(1, math.ceil(state.panel_qty / max(1, max_pps)))
        pps_actual = math.ceil(state.panel_qty / strings)
        state.panels_per_string = pps_actual
        state.pv_strings        = strings
        state.operating_dc_voltage = round(pps_actual * panel_vmp, 1)

        # ── 6. Build full markdown summary ─────────────────────────────────────
        pv_kwp_str = f"{state.total_pv_kwp:.2f} kWp"
        inv_str    = f"{state.inverter_qty}× {state.inverter_brand} ({state.inverter_kw:.0f} kW / {state.inverter_kva:.0f} kVA each)"
        bat_str    = (f"{state.battery_qty}× {battery_module_kwh} kWh modules = "
                      f"{state.total_storage_kwh:.1f} kWh gross | "
                      f"{state.usable_storage_kwh:.1f} kWh usable")

        md = (
            f"## ⚡ Solar PV System Sizing — Complete Results\n\n"
            f"**Location:** {state.location} | **PSH:** {psh} h/day | **System:** {state.system_type.title()}\n\n"
            f"---\n\n"
            f"### 🔌 Energy Basis\n"
            f"| Parameter | Value |\n"
            f"|---|---|\n"
            f"| Daily Energy Demand | **{daily_kwh:.2f} kWh/day** |\n"
            f"| Peak / Connected Load | {state.peak_demand_kw:.2f} kW / {state.connected_load_kw:.2f} kW |\n\n"
            f"### ☀️ PV Array\n"
            f"| Parameter | Value |\n"
            f"|---|---|\n"
            f"| Required DC Capacity | {required_pv_kwp:.2f} kWp (= {daily_kwh:.2f} kWh ÷ {psh} h/day) |\n"
            f"| Selected DC Capacity | **{pv_kwp_str}** |\n"
            f"| Panel Model | Jinko Tiger Neo N-Type {panel_wp}Wp |\n"
            f"| Panel Quantity | **{state.panel_qty} panels** |\n"
            f"| Strings × Panels/String | {strings} strings × {pps_actual} panels |\n"
            f"| Operating DC Voltage | ~{state.operating_dc_voltage} V |\n\n"
            f"### ⚡ Inverter\n"
            f"| Parameter | Value |\n"
            f"|---|---|\n"
            f"| Configuration | **{inv_str}** |\n"
            f"| Voltage Architecture | {state.voltage_architecture} |\n"
            f"| AC Capacity | {state.inverter_kw * state.inverter_qty:.0f} kW total |\n\n"
        )

        if state.system_type in ("off-grid", "hybrid"):
            md += (
                f"### 🔋 Battery Energy Storage\n"
                f"| Parameter | Value |\n"
                f"|---|---|\n"
                f"| Autonomy | {state.days_of_autonomy:.1f} day(s) @ {state.dod*100:.0f}% DoD |\n"
                f"| Configuration | **{bat_str}** |\n"
                f"| Stacks | {state.battery_stacks} stack(s) |\n"
                f"| DC Breaker | {state.battery_breaker_a:.0f} A |\n\n"
            )

        md += (
            f"---\n"
            f"*Type **'generate BOQ'** to create the Bill of Quantities, or ask any follow-up questions.*"
        )
        return md

    def process_message(self, user_input: str, state: ProjectState, history: Optional[List[Dict[str, str]]] = None) -> str:
        """
        Processes a user message through the multiagent system with full conversational memory.
        Returns the final text response to the user.
        """
        # 1. Quick Location Check & Exact PSH Lookup
        user_lower = user_input.lower()
        if any(kw in user_lower for kw in ("location", "nairobi", "mombasa", "kilifi", "kisumu", "nakuru", "eldoret")):
            loc_data = get_location_psh(user_input)
            extracted_loc = loc_data["location"].replace("Location", "").replace("location", "").strip(" :")
            if extracted_loc:
                state.location = extracted_loc
            state.peak_sun_hours = loc_data["peak_sun_hours"]

        history_str = self._format_history(history)
        state_json  = json.dumps(state.to_dict(), indent=2)
        
        next_agent_name, supervisor_response = self._route(user_input, state_json, history_str)
        
        if next_agent_name == "None" or next_agent_name not in ALL_AGENTS:
            # If state has location updated but no loads yet, build a clean friendly response
            if any(kw in user_lower for kw in ("location", "nairobi", "mombasa", "kilifi")) and state.daily_energy_kwh == 0 and not state.loads:
                return (
                    f"Got it! I've updated the project location to **{state.location}** "
                    f"(Peak Sun Hours: **{state.peak_sun_hours} h/day**).\n\n"
                    f"To calculate your solar PV system size and Bill of Quantities (BOQ), please:\n"
                    f"- 📎 Upload a `.csv` / `.xlsx` load schedule or logger data file, or\n"
                    f"- 💬 Tell me about your appliances (e.g. *'I have 5 lights, 2 fridges, and a 1.5kW pump'*)."
                )
            return supervisor_response
            
        # ── Run the routed agent ────────────────────────────────────────────────
        agent_context = (
            f"Recent Conversation History:\n{history_str}\n\n"
            f"User Request: {user_input}\n"
        )
        agent_result = self._run_agent(next_agent_name, state, agent_context)
        agent_message = agent_result["message"]

        # ── If an Energy Analysis Agent ran, automatically chain the full pipeline ──
        if next_agent_name in ENERGY_ANALYSIS_AGENTS and state.daily_energy_kwh > 0:
            try:
                sizing_md = self._run_full_sizing_pipeline(state)
                # Prepend the appliance breakdown message (from the energy agent) if non-trivial
                if agent_message and len(agent_message) > 50 and "daily_energy" not in agent_message.lower():
                    return f"{agent_message}\n\n---\n\n{sizing_md}"
                return sizing_md
            except Exception as e:
                # If pipeline fails, return energy agent message + error note
                return f"{agent_message}\n\n⚠️ Auto-sizing pipeline error: {e}"

        return agent_message
