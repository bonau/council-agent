"""Planning crew: decompose user prompt into a structured plan."""

from __future__ import annotations

import json

from crewai import Agent, Crew, Process, Task

from council_agent.config.presets import Preset
from council_agent.crews.base import crew_output_text, extract_json_block
from council_agent.llm.openrouter import make_llm
from council_agent.types import PlanArtifact

PLANNING_BACKSTORY = (
    "You are a strategic planner. Break complex requests into clear, "
    "actionable steps with explicit success criteria and risk awareness."
)

PLANNING_TASK_DESCRIPTION = """
Analyze the following user request and produce a structured execution plan.

User request:
{prompt}

Respond with a JSON object only (no extra text) using this schema:
{{
  "steps": ["step 1", "step 2", ...],
  "success_criteria": ["criterion 1", ...],
  "risks": ["risk 1", ...]
}}
"""


def build_planning_crew(preset: Preset, api_key: str) -> Crew:
    role = preset.planning
    agent = Agent(
        role="Planning Strategist",
        goal="Produce a clear, structured plan for the user's request",
        backstory=PLANNING_BACKSTORY,
        llm=make_llm(role.model, role.temperature, api_key),
        verbose=False,
    )
    task = Task(
        description=PLANNING_TASK_DESCRIPTION,
        expected_output="A JSON object with steps, success_criteria, and risks arrays",
        agent=agent,
    )
    return Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)


def run_planning(crew: Crew, prompt: str) -> PlanArtifact:
    result = crew.kickoff(inputs={"prompt": prompt})
    raw = crew_output_text(result)
    try:
        data = extract_json_block(raw)
        return PlanArtifact(
            raw=raw,
            steps=[str(s) for s in data.get("steps", [])],
            success_criteria=[str(s) for s in data.get("success_criteria", [])],
            risks=[str(s) for s in data.get("risks", [])],
        )
    except (ValueError, json.JSONDecodeError):
        return PlanArtifact(
            raw=raw,
            steps=[raw],
            success_criteria=["Plan addresses the user request"],
            risks=[],
        )
