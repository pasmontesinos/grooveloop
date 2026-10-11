from __future__ import annotations

from typing import TYPE_CHECKING, Any

from grooveloop.shared.domain.agent_log_action import AgentLogAction
from grooveloop.shared.domain.agent_log_reader import AgentLogReader
from grooveloop.shared.domain.agent_run_reading import AgentRunReading
from grooveloop.shared.infrastructure.agent_action import describe_action, describe_actions, describe_last_action
from grooveloop.shared.infrastructure.claude_cost_split_parser import parse_cost_split
from grooveloop.shared.infrastructure.claude_run_verdict_parser import parse_run_verdict
from grooveloop.shared.infrastructure.claude_tool_tally_parser import parse_tool_tallies
from grooveloop.shared.infrastructure.claude_turn_growth_parser import parse_turn_growth
from grooveloop.shared.infrastructure.claude_turn_parser import parse_turns
from grooveloop.shared.infrastructure.claude_usage_parser import parse_usage

if TYPE_CHECKING:
    from grooveloop.shared.domain.agent_run_verdict import AgentRunVerdict
    from grooveloop.shared.domain.turn_growth import TurnGrowth

_ENGINE = "claude"
_ASSISTANT_EVENT = "assistant"
_TOOL_USE_BLOCK = "tool_use"


class ClaudeLogReader(AgentLogReader):
    @property
    def engine(self) -> str:
        return _ENGINE

    def read(self, log_text: str) -> AgentRunReading:
        total_cost_usd, models = parse_usage(log_text)
        turns, subagents = parse_turns(log_text)
        skills, tools = parse_tool_tallies(log_text)

        return AgentRunReading(
            total_cost_usd=total_cost_usd,
            models=models,
            turns=turns,
            subagents=subagents,
            skills=skills,
            tools=tools,
            cost_split=parse_cost_split(total_cost_usd, models),
        )

    def last_action(self, log_tail: str) -> str | None:
        return describe_last_action(log_tail, _describe)

    def turn_growth(self, log_text: str) -> list[TurnGrowth]:
        return parse_turn_growth(log_text)

    def actions(self, log_text: str) -> list[AgentLogAction]:
        return describe_actions(log_text, _actions_of)

    def verdict(self, log_tail: str, exit_code: int) -> AgentRunVerdict:
        return parse_run_verdict(log_tail, exit_code)


def _describe(event: dict[str, Any]) -> str | None:
    blocks = _tool_uses(event)
    if len(blocks) == 0:
        return None

    return describe_action(str(blocks[-1].get("name", "")), blocks[-1].get("input"))


def _actions_of(event: dict[str, Any]) -> list[AgentLogAction]:
    actions: list[AgentLogAction] = []
    for block in _tool_uses(event):
        description = describe_action(str(block.get("name", "")), block.get("input"))
        tool_use_id = block.get("id")
        if description is not None:
            actions.append(AgentLogAction(description, tool_use_id if isinstance(tool_use_id, str) else None))

    return actions


def _tool_uses(event: dict[str, Any]) -> list[dict[str, Any]]:
    if event.get("type") != _ASSISTANT_EVENT:
        return []

    message = event.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, list):
        return []

    return [block for block in content if isinstance(block, dict) and block.get("type") == _TOOL_USE_BLOCK]
