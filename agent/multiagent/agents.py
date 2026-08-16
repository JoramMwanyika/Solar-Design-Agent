import json
import re
from typing import Dict, Any, List, Callable
from agent.multiagent.state import ProjectState

def _extract_json(text: str) -> dict | None:
    """
    Robustly extracts a JSON object from LLM output that may contain:
    - Markdown code fences (```json ... ```)
    - Explanatory prose before/after the JSON
    - Nested braces within string values
    Returns a parsed dict or None if no valid JSON is found.
    """
    # 1. Strip markdown code fences first
    clean = re.sub(r'```(?:json)?\s*', '', text, flags=re.IGNORECASE)
    clean = clean.replace('```', '')

    # 2. Find the outermost balanced {} block
    start = clean.find('{')
    if start == -1:
        return None
    depth = 0
    end = -1
    for i, ch in enumerate(clean[start:], start=start):
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end == -1:
        return None
    try:
        return json.loads(clean[start:end])
    except json.JSONDecodeError:
        return None

class MultiAgent:
    """Base class for all autonomous agents in the system."""
    def __init__(self, name: str, role: str, goal: str, tools: List[Callable] = None):
        self.name = name
        self.role = role
        self.goal = goal
        self.tools = {tool.__name__: tool for tool in (tools or [])}

    def get_system_prompt(self, state_json: str) -> str:
        prompt = f"You are the {self.name}. Your role is: {self.role}\n"
        prompt += f"Your goal is: {self.goal}\n\n"
        prompt += f"Current Project State:\n{state_json}\n\n"
        if self.tools:
            prompt += "You have access to the following mathematical tools:\n"
            for t_name, t_func in self.tools.items():
                prompt += f"- {t_name}: {t_func.__doc__}\n"
            prompt += "\nTo use a tool, respond with ONLY a raw JSON block (no markdown, no explanation): {\"tool\": \"tool_name\", \"kwargs\": {\"arg1\": val}}."
            prompt += "\nWhen done, respond with ONLY a raw JSON block: {\"status\": \"complete\", \"updates\": {\"state_key\": \"value\"}, \"message\": \"...\"}"
        else:
            prompt += "\nYou have no tools. Respond with ONLY a raw JSON block (no markdown, no explanation): {\"status\": \"complete\", \"updates\": {\"state_key\": \"value\"}, \"message\": \"...\"}"
        return prompt

    def process_llm_response(self, response_text: str, state: ProjectState) -> Dict[str, Any]:
        """Parses the LLM JSON response and either executes a tool or applies state updates."""
        data = _extract_json(response_text)
        if data is None:
            # Graceful fallback: treat the raw text as the agent's message
            msg = response_text.strip()[:1000]  # cap length
            return {"type": "complete", "message": msg}

        if "tool" in data and data["tool"] in self.tools:
            tool_name = data["tool"]
            kwargs = data.get("kwargs", {})
            try:
                result = self.tools[tool_name](**kwargs)
                return {"type": "tool_call", "tool": tool_name, "result": result}
            except Exception as e:
                return {"type": "tool_error", "tool": tool_name, "error": str(e)}

        if data.get("status") == "complete":
            updates = data.get("updates", {})
            for k, v in updates.items():
                if hasattr(state, k):
                    setattr(state, k, v)
            return {"type": "complete", "message": data.get("message", "Task finished.")}

        # JSON found but no recognisable keys — treat message field as response if present
        if "message" in data:
            return {"type": "complete", "message": data["message"]}

        # Last resort: graceful fallback with raw text
        return {"type": "complete", "message": response_text.strip()[:1000]}

# 1. Project Intake Agent
project_intake_agent = MultiAgent(
    name="Project Intake Agent",
    role="Customer requirements specialist.",
    goal="Understand customer needs and define the initial project scope (location, system_type, client_name)."
)

import agent.multiagent.tools.math_tools as mt

# 2. Bill Analysis Agent
bill_analysis_agent = MultiAgent(
    name="Bill Analysis Agent",
    role="Utility bill parser and standardizer.",
    goal="Extract energy consumption from bills and convert it to the Unified Energy Output schema.",
    tools=[mt.analyze_utility_bill]
)

# 3. Load Analysis Agent (Logger Data)
load_analysis_agent = MultiAgent(
    name="Load Analysis Agent",
    role="Time-series logger data specialist.",
    goal="Analyze interval logger data and convert it to the Unified Energy Output schema.",
    tools=[mt.analyze_logger_data]
)

# 3b. Appliance Analysis Agent (Manual Loads)
appliance_analysis_agent = MultiAgent(
    name="Appliance Analysis Agent",
    role="Appliance load profile calculator.",
    goal=(
        "Calculate daily energy and peak demand from a manual list of appliances "
        "to generate the Unified Energy Output schema. "
        "CRITICAL LOAD PROFILE WORKFLOW:\n"
        "  Step 1 — Pass the list to analyze_appliance_list. It will do all the math.\n"
        "  Step 2 — Output the exact `appliance_breakdown` returned by the tool to the user. DO NOT recalculate energy values yourself to prevent math errors!\n"
        "  Step 3 — Return peak_demand_kw=0.0 in the Unified Energy Output. "
        "This signals that the inverter must be sized from the Required PV Capacity "
        "(which is derived from daily energy), NOT from the raw connected load sum."
    ),
    tools=[mt.analyze_appliance_list]
)

# 4. Solar Resource Agent
solar_resource_agent = MultiAgent(
    name="Solar Resource Agent",
    role="Meteorological data specialist.",
    goal="Determine the Peak Sun Hours (PSH) for the project location.",
    tools=[mt.get_location_psh]
)

# 5. PV Design Agent
pv_design_agent = MultiAgent(
    name="PV Design Agent",
    role="Photovoltaic array designer.",
    goal="Size the PV array (kWp) using formula: Required DC Capacity (kWp) = Daily Energy / PSH (no losses included), calculate number of panels, max panels per string from panel Voc & inverter max Vin, and Panels per MPPT = floor((Max PV Input / No. MPPTs) / Panel kWp).",
    tools=[mt.size_pv_array, mt.calculate_stringing]
)

# 6. Battery Design Agent
battery_design_agent = MultiAgent(
    name="Battery Design Agent",
    role="Energy storage system designer.",
    goal="Calculate required battery capacity (kWh), module quantities, and breaker sizes.",
    tools=[mt.size_battery]
)

# 7. Inverter Selection Agent
inverter_selection_agent = MultiAgent(
    name="Inverter Selection Agent",
    role="Inverter configuration specialist.",
    goal=(
        "Choose compatible inverters: Huawei for Grid-Tied systems, Deye or Solis for Hybrid/Off-Grid systems. "
        "Check Low Voltage (48V) vs High Voltage (HV 384V+) for hybrid systems. "
        "LOAD PROFILE RULE: When sizing from a load profile / appliance list, call size_inverter with "
        "peak_demand_kw=0.0 so the inverter is sized from the Required PV Capacity (energy-driven). "
        "For Bill Analysis and Logged Data, use the actual peak_demand_kw from the state."
    ),
    tools=[mt.size_inverter]
)

# 8. Cable Design Agent
cable_design_agent = MultiAgent(
    name="Cable Design Agent",
    role="Electrical conductor specialist.",
    goal="Perform cable sizing and voltage drop calculations for DC and AC sides.",
    tools=[mt.size_cables]
)

# 9. Protection Design Agent
protection_design_agent = MultiAgent(
    name="Protection Design Agent",
    role="Safety and switchgear specialist.",
    goal="Select protective devices (breakers, fuses, SPDs) for the system."
)

# 10. Structural Agent
structural_agent = MultiAgent(
    name="Structural Agent",
    role="Mounting and structural verifier.",
    goal="Verify mounting requirements and roof space."
)

# 11. Validation Agent
validation_agent = MultiAgent(
    name="Validation Agent",
    role="Quality Assurance Engineer.",
    goal="Run final engineering checks across all components to ensure compatibility."
)

# 12. BOQ Agent
boq_agent = MultiAgent(
    name="BOQ Agent",
    role="Procurement specialist.",
    goal="Generate the detailed Bill of Quantities."
)

# 13. Proposal Agent
proposal_agent = MultiAgent(
    name="Proposal Agent",
    role="Client communications specialist.",
    goal="Generate the final client-ready design workbook and reports."
)

# 14. Engineering Review Agent
engineering_review_agent = MultiAgent(
    name="Engineering Review Agent",
    role="Senior Engineer.",
    goal="Produce a final engineering summary highlighting assumptions, warnings, and items for review."
)

ALL_AGENTS = {
    "Project Intake Agent": project_intake_agent,
    "Bill Analysis Agent": bill_analysis_agent,
    "Load Analysis Agent": load_analysis_agent,
    "Appliance Analysis Agent": appliance_analysis_agent,
    "Solar Resource Agent": solar_resource_agent,
    "PV Design Agent": pv_design_agent,
    "Battery Design Agent": battery_design_agent,
    "Inverter Selection Agent": inverter_selection_agent,
    "Cable Design Agent": cable_design_agent,
    "Protection Design Agent": protection_design_agent,
    "Structural Agent": structural_agent,
    "Validation Agent": validation_agent,
    "BOQ Agent": boq_agent,
    "Proposal Agent": proposal_agent,
    "Engineering Review Agent": engineering_review_agent,
}
