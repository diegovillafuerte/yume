"""OpenAI GPT client wrapper with error handling."""

import json
import logging
from typing import Any

from openai import OpenAI, APIError, RateLimitError

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class OpenAIClient:
    """Wrapper around OpenAI's GPT API with tool support."""

    def __init__(self, api_key: str | None = None):
        """Initialize OpenAI client.

        Args:
            api_key: OpenAI API key (defaults to settings)
        """
        self.api_key = api_key or settings.openai_api_key
        if not self.api_key:
            logger.warning("No OpenAI API key configured - AI features will be disabled")
            self.client = None
        else:
            self.client = OpenAI(api_key=self.api_key)

    @property
    def is_configured(self) -> bool:
        """Check if client is properly configured."""
        return self.client is not None

    def create_message(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 1024,
        model: str = "gpt-4.1",
    ) -> dict[str, Any]:
        """Create a message using GPT.

        Args:
            system_prompt: System prompt for GPT
            messages: Conversation history
            tools: Available tools for GPT to use (OpenAI function format)
            max_tokens: Maximum tokens in response
            model: Model to use (default: gpt-4.1)

        Returns:
            GPT response as dictionary

        Raises:
            ValueError: If client is not configured
            APIError: If API call fails after retries
        """
        if not self.is_configured:
            raise ValueError("OpenAI client not configured - missing API key")

        logger.debug(
            f"Creating GPT message:\n"
            f"  Model: {model}\n"
            f"  Messages: {len(messages)}\n"
            f"  Tools: {len(tools) if tools else 0}"
        )

        try:
            # Build messages with system prompt
            full_messages = [{"role": "system", "content": system_prompt}] + messages

            # Build request parameters
            params: dict[str, Any] = {
                "model": model,
                "max_tokens": max_tokens,
                "messages": full_messages,
            }

            if tools:
                # Convert to OpenAI function format
                params["tools"] = self._convert_tools_to_openai_format(tools)
                params["tool_choice"] = "auto"

            # Make API call
            response = self.client.chat.completions.create(**params)

            logger.debug(
                f"GPT response:\n"
                f"  Finish reason: {response.choices[0].finish_reason}\n"
                f"  Usage: {response.usage.prompt_tokens} in, {response.usage.completion_tokens} out"
            )

            return response

        except RateLimitError as e:
            logger.warning(f"Rate limited by OpenAI: {e}")
            raise

        except APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    def _convert_tools_to_openai_format(
        self, tools: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Convert our tool format to OpenAI's function calling format.

        Args:
            tools: Tools in our format (with input_schema)

        Returns:
            Tools in OpenAI format (with parameters)
        """
        openai_tools = []
        for tool in tools:
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
                },
            }
            openai_tools.append(openai_tool)
        return openai_tools

    def extract_text_response(self, response: Any) -> str:
        """Extract text content from GPT's response.

        Args:
            response: GPT's response object

        Returns:
            Text content from the response
        """
        message = response.choices[0].message
        return message.content or ""

    def extract_tool_calls(self, response: Any) -> list[dict[str, Any]]:
        """Extract tool calls from GPT's response.

        Args:
            response: GPT's response object

        Returns:
            List of tool calls with name and input
        """
        message = response.choices[0].message
        tool_calls = []

        if message.tool_calls:
            for tool_call in message.tool_calls:
                tool_calls.append({
                    "id": tool_call.id,
                    "name": tool_call.function.name,
                    "input": json.loads(tool_call.function.arguments),
                })

        return tool_calls

    def has_tool_calls(self, response: Any) -> bool:
        """Check if response contains tool calls.

        Args:
            response: GPT's response object

        Returns:
            True if response contains tool calls
        """
        return response.choices[0].finish_reason == "tool_calls"

    def format_tool_result_message(
        self, tool_call_id: str, result: dict[str, Any]
    ) -> dict[str, Any]:
        """Format a tool result for sending back to GPT.

        Args:
            tool_call_id: ID of the tool call
            result: Result from tool execution

        Returns:
            Message formatted for OpenAI API
        """
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": json.dumps(result, ensure_ascii=False),
        }

    def format_assistant_message_with_tool_calls(
        self, response: Any
    ) -> dict[str, Any]:
        """Format assistant message with tool calls for conversation history.

        Args:
            response: GPT's response object

        Returns:
            Message formatted for conversation history
        """
        message = response.choices[0].message
        return {
            "role": "assistant",
            "content": message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in (message.tool_calls or [])
            ],
        }


# Singleton instance for easy access
_client: OpenAIClient | None = None


def get_openai_client() -> OpenAIClient:
    """Get singleton OpenAI client instance."""
    global _client
    if _client is None:
        _client = OpenAIClient()
    return _client
