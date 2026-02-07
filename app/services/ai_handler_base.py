"""Base AI handler with shared tool-calling loop.

This module provides a mixin class with a reusable tool-calling loop
that can be used by both ConversationHandler and OnboardingHandler.
"""

import logging
from typing import Any, Awaitable, Callable

from app.ai.client import OpenAIClient

logger = logging.getLogger(__name__)


class ToolCallingMixin:
    """Shared tool-calling loop for all AI handlers.

    This mixin provides _process_with_tools() which implements the standard
    tool loop: send message to AI, execute tools if requested, repeat until
    AI gives a final response.

    Subclasses must provide:
        - self.client: OpenAIClient instance
    """

    client: OpenAIClient

    async def _process_with_tools_generic(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_executor: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
        max_iterations: int = 5,
    ) -> str:
        """Universal tool loop - works for any tool set.

        This implements the tool use loop:
        1. Send message to AI
        2. If AI wants to use a tool, execute it via tool_executor
        3. Send tool result back to AI
        4. Repeat until AI gives a final response

        Args:
            system_prompt: System prompt for AI
            messages: Conversation history (will be modified in place)
            tools: Tool definitions
            tool_executor: Async function(tool_name, tool_input) -> result
            max_iterations: Max tool calling rounds to prevent infinite loops

        Returns:
            Final response text from AI
        """
        response = None

        for iteration in range(max_iterations):
            logger.debug(f"Tool loop iteration {iteration + 1}")

            response = self.client.create_message(
                system_prompt=system_prompt,
                messages=messages,
                tools=tools,
            )

            if self.client.has_tool_calls(response):
                tool_calls = self.client.extract_tool_calls(response)
                logger.info(f"AI wants to use {len(tool_calls)} tool(s)")

                # Add assistant's response (with tool calls) to messages
                messages.append(
                    self.client.format_assistant_message_with_tool_calls(response)
                )

                # Execute each tool and add results
                for tool_call in tool_calls:
                    result = await tool_executor(tool_call["name"], tool_call["input"])
                    messages.append(
                        self.client.format_tool_result_message(tool_call["id"], result)
                    )
            else:
                # AI gave a final response
                response_text = self.client.extract_text_response(response)
                logger.info(f"AI final response: {response_text[:100]}...")
                return response_text

        # If we hit max iterations, return what we have
        logger.warning("Hit max tool iterations, returning last response")
        return self.client.extract_text_response(response) if response else "Lo siento, hubo un error."
