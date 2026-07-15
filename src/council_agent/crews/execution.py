"""Execution crew: carry out the plan."""

from __future__ import annotations

from crewai import Agent, Crew, Process, Task

from council_agent.config.presets import Preset
from council_agent.crews.base import crew_output_text
from council_agent.llm.openrouter import make_llm
from council_agent.types import ExecutionResult, PlanArtifact

EXECUTION_BACKSTORY = (
    "You are a focused executor. Follow the plan precisely, produce concrete "
    "deliverables, and explain your reasoning clearly."
)

EXECUTION_TASK_DESCRIPTION = """
Execute the following plan for the original user request.

Original request:
{prompt}

Plan steps:
{steps}

Success criteria:
{success_criteria}

Produce the complete deliverable. Be thorough and address every step.
"""


def _format_plan_sections(plan: PlanArtifact) -> dict[str, str]:
    steps = "\n".join(f"- {s}" for s in plan.steps) or "- (no steps)"
    criteria = "\n".join(f"- {c}" for c in plan.success_criteria) or "- (none)"
    return {"steps": steps, "success_criteria": criteria}


def build_execution_crew(preset: Preset, api_key: str) -> Crew:
    role = preset.execution
    agent = Agent(
        role="Task Executor",
        goal="Execute the plan and produce a complete deliverable",
        backstory=EXECUTION_BACKSTORY,
        llm=make_llm(role.model, role.temperature, api_key),
        verbose=False,
    )
    task = Task(
        description=EXECUTION_TASK_DESCRIPTION,
        expected_output="A complete deliverable addressing all plan steps",
        agent=agent,
    )
    return Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)


def run_execution(crew: Crew, prompt: str, plan: PlanArtifact) -> ExecutionResult:
    sections = _format_plan_sections(plan)
    result = crew.kickoff(
        inputs={
            "prompt": prompt,
            "steps": sections["steps"],
            "success_criteria": sections["success_criteria"],
        }
    )
    return ExecutionResult(raw=crew_output_text(result))
