"""Tool-use API loop for Anthropic Claude conversations.

Handles the multi-turn tool_use protocol: sends messages to the API,
executes tool calls via handlers, and loops until Claude produces a
final text response or the round limit is reached.
"""

import asyncio
from dataclasses import dataclass, field

import httpx

from app.core.logging import get_logger
from app.modules.tool_handlers import TOOL_HANDLERS, ToolContext

logger = get_logger("tool_executor")

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-haiku-4-5-20251001"


@dataclass
class ConversationResult:
    """Result from a tool_use conversation loop."""
    text: str
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    model: str = DEFAULT_MODEL
    rounds: int = 0


async def run_tool_conversation(
    system_prompt: str,
    tools: list[dict],
    messages: list[dict],
    ctx: ToolContext,
    api_key: str,
    model: str = DEFAULT_MODEL,
    max_rounds: int = 5,
) -> ConversationResult:
    """Run a tool_use conversation loop with the Anthropic API.

    Calls the API, executes any tool_use requests via handlers, appends
    tool_results, and loops until Claude emits a final text response
    or `max_rounds` is exhausted.

    Returns a ConversationResult with the text and cumulative token usage.
    """
    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "Content-Type": "application/json",
    }

    total_input = 0
    total_output = 0

    for round_num in range(max_rounds):
        # Call the Anthropic API
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    ANTHROPIC_API_URL,
                    json={
                        "model": model,
                        "max_tokens": 500,
                        "system": system_prompt,
                        "tools": tools,
                        "messages": messages,
                    },
                    headers=headers,
                    timeout=20.0,
                )

            if response.status_code != 200:
                logger.error(
                    "Anthropic API error (round %d): %d — %s",
                    round_num + 1, response.status_code, response.text[:200],
                )
                # Retry once on server error
                if round_num == 0 and response.status_code >= 500:
                    await asyncio.sleep(1)
                    continue
                return ConversationResult(text=_fallback_message(), total_input_tokens=total_input, total_output_tokens=total_output, model=model, rounds=round_num + 1)

            data = response.json()

        except Exception as e:
            logger.error("Anthropic API request failed (round %d): %s", round_num + 1, e)
            if round_num == 0:
                await asyncio.sleep(1)
                continue
            return ConversationResult(text=_fallback_message(), total_input_tokens=total_input, total_output_tokens=total_output, model=model, rounds=round_num + 1)

        # Accumulate token usage
        usage = data.get("usage", {})
        total_input += usage.get("input_tokens", 0)
        total_output += usage.get("output_tokens", 0)

        stop_reason = data.get("stop_reason")
        content_blocks = data.get("content", [])

        # If Claude is done talking, extract the text
        if stop_reason == "end_turn":
            return ConversationResult(text=_extract_text(content_blocks), total_input_tokens=total_input, total_output_tokens=total_output, model=model, rounds=round_num + 1)

        # If Claude wants to use tools, execute them
        if stop_reason == "tool_use":
            # Append the full assistant message (with tool_use blocks)
            messages.append({"role": "assistant", "content": content_blocks})

            # Execute each tool_use block and collect results
            tool_results = []
            for block in content_blocks:
                if block.get("type") != "tool_use":
                    continue

                tool_name = block["name"]
                tool_input = block.get("input", {})
                tool_use_id = block["id"]

                result_content = await _execute_tool(ctx, tool_name, tool_input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": result_content,
                })

                # Track tool calls for test mode visibility
                ctx.tool_calls.append({
                    "tool": tool_name,
                    "input": tool_input,
                    "output": result_content,
                })

            # Append tool results as a user message
            messages.append({"role": "user", "content": tool_results})
            continue

        # Unexpected stop reason — extract whatever text we got
        logger.warning("Unexpected stop_reason: %s", stop_reason)
        text = _extract_text(content_blocks)
        final_text = text if text else _fallback_message()
        return ConversationResult(text=final_text, total_input_tokens=total_input, total_output_tokens=total_output, model=model, rounds=round_num + 1)

    # Exceeded max rounds
    logger.warning("Tool conversation exceeded %d rounds", max_rounds)
    final_text = _extract_text(content_blocks) if content_blocks else _fallback_message()
    return ConversationResult(text=final_text, total_input_tokens=total_input, total_output_tokens=total_output, model=model, rounds=round_num + 1)


async def _execute_tool(ctx: ToolContext, tool_name: str, tool_input: dict) -> str:
    """Execute a single tool call via the handler registry."""
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        logger.warning("Unknown tool requested: %s", tool_name)
        return f'{{"error": "Unknown tool: {tool_name}"}}'

    try:
        result = await handler(ctx, tool_input)
        logger.debug("Tool %s executed successfully", tool_name)
        return result
    except Exception as e:
        logger.error("Tool %s failed: %s", tool_name, e)
        return f'{{"error": "Tool execution failed: {str(e)}"}}'


def _extract_text(content_blocks: list[dict]) -> str:
    """Extract concatenated text from content blocks."""
    parts = []
    for block in content_blocks:
        if block.get("type") == "text":
            parts.append(block["text"])
    return " ".join(parts).strip() if parts else ""


def _fallback_message() -> str:
    return "Sorry, I'm having a technical issue right now. Please try again shortly."
