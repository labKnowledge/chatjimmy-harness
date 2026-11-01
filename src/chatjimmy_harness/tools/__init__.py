"""Local tools the agent harness can call on behalf of the model."""

from chatjimmy_harness.tools.base import ToolContext, ToolResult, ToolSpec
from chatjimmy_harness.tools.registry import (
    DEFAULT_TOOL_NAMES,
    build_registry,
    tool_specs_prompt,
)

__all__ = [
    "DEFAULT_TOOL_NAMES",
    "ToolContext",
    "ToolResult",
    "ToolSpec",
    "build_registry",
    "tool_specs_prompt",
]
