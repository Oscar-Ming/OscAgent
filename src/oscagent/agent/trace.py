from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TraceStep:
    tool_name: str
    arguments: dict[str, object]
    observation: str


@dataclass
class Trace:
    steps: list[TraceStep] = field(default_factory=list)

    def add_step(self, tool_name: str, arguments: dict[str, object], observation: str) -> None:
        self.steps.append(
            TraceStep(
                tool_name=tool_name,
                arguments=arguments,
                observation=observation,
            )
        )

    def to_markdown(self) -> str:
        if not self.steps:
            return "No tool calls."

        lines: list[str] = []
        for index, step in enumerate(self.steps, start=1):
            lines.append(f"{index}. `{step.tool_name}` {step.arguments}")
        return "\n".join(lines)
