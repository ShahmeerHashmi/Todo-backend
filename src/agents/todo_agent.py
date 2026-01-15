"""Groq-powered Agent configuration for the todo assistant.

Uses OpenAI-compatible SDK with Groq's API for fast inference.
All AI actions MUST be performed through bound MCP tools.
"""

import os
import json
import re
from typing import Any
from uuid import UUID

from openai import OpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.mcp_tools import TOOL_DEFINITIONS, MCPToolExecutor
from src.config.logging import get_logger


def clean_response(text: str) -> str:
    """Remove <think> tags and their content from model responses."""
    if not text:
        return text
    # Remove <think>...</think> blocks
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    return cleaned.strip()

logger = get_logger(__name__)

# System prompt for the todo assistant
SYSTEM_PROMPT = """You are a helpful todo list assistant. Your job is to help users manage their tasks through natural conversation.

IMPORTANT: Respond directly without any thinking tags or internal reasoning. Just provide the response.

You have access to the following tools:
- create_task: Create new tasks when users want to add, remember, or track something
- list_tasks: Show tasks when users ask what they need to do or want to see their list
- complete_task: Mark tasks as done when users say they finished or completed something
- update_task: Change task titles when users want to rename or modify a task
- delete_task: Remove tasks when users want to get rid of or delete something

Guidelines:
1. Be conversational and friendly, keep responses brief
2. When creating tasks, extract the core action/item from the user's message
3. When listing tasks, format them in a clear, numbered list
4. When a user references a task, try to match it by title or position number
5. Confirm actions you've taken so the user knows what happened
6. If a request is ambiguous (e.g., multiple tasks match), ask for clarification
7. If no task matches a reference, politely inform the user

Examples of task creation:
- "Add buy groceries" → create task "buy groceries"
- "Remind me to call mom" → create task "call mom"
- "I need to pay bills" → create task "pay bills"

Remember: You can ONLY interact with tasks through the provided tools. Never make up task data.
Do NOT include <think> tags or show your reasoning. Just respond naturally."""


class TodoAgent:
    """OpenAI-powered agent for natural language task management.

    This agent processes user messages, determines the appropriate
    tool calls, and returns human-readable responses.
    """

    def __init__(self, session: AsyncSession, user_id: UUID):
        """Initialize the todo agent.

        Args:
            session: Database session for tool execution
            user_id: Authenticated user's UUID
        """
        self.session = session
        self.user_id = user_id
        self.client = OpenAI(
            api_key=os.getenv("GROQ_API_KEY"),
            base_url="https://api.groq.com/openai/v1",
        )
        self.tool_executor = MCPToolExecutor(session, user_id)
        self.model = "qwen/qwen3-32b"  # Qwen model with reliable tool/function calling support

    async def process_message(
        self,
        user_message: str,
        conversation_history: list[dict[str, str]]
    ) -> dict[str, Any]:
        """Process a user message and return the assistant's response.

        Args:
            user_message: The user's natural language message
            conversation_history: Previous messages for context

        Returns:
            Dict with 'response' text and 'tool_calls' list
        """
        logger.info(
            "agent_process_message",
            user_id=str(self.user_id),
            message_length=len(user_message)
        )

        # Build messages for OpenAI
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Add conversation history
        for msg in conversation_history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        # Add current user message
        messages.append({"role": "user", "content": user_message})

        # Call Groq API with tools
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
                max_tokens=1000
            )
        except Exception as e:
            logger.error("groq_api_error", error=str(e))
            raise

        # Process the response
        assistant_message = response.choices[0].message
        tool_calls_made = []

        # If the model returned a plain assistant message claiming it deleted
        # or removed a task but did not actually call any tools, attempt a
        # safe server-side remediation: infer the referenced task (most
        # recently visible) and invoke the delete tool ourselves. This
        # prevents hallucinated confirmations from leaving stale tasks in
        # the user's archive.
        if not assistant_message.tool_calls:
            assistant_text = (assistant_message.content or "").lower()
            # Detect deletion language in the assistant or explicit delete in user message
            if re.search(r"\b(delet|remov)e(d|s)?\b", assistant_text) and re.search(r"\b(delete|remove)\b", user_message, flags=re.I):
                try:
                    # List tasks and pick the most recent one as the likely referent
                    list_res = await self.tool_executor.execute_tool("list_tasks", {})
                    if list_res.get("success") and list_res.get("result"):
                        tasks = list_res["result"].get("tasks", [])
                        if tasks:
                            recent = tasks[0]
                            identifier = recent.get("title") or recent.get("id")
                            # Invoke delete_tool with inferred identifier
                            del_res = await self.tool_executor.execute_tool("delete_task", {"task_identifier": identifier})

                            tool_calls_made.append({
                                "tool": "delete_task",
                                "params": {"task_identifier": identifier},
                                "result": "success" if del_res.get("success") else "error"
                            })

                            # Use tool result message when available
                            if del_res.get("success") and del_res.get("result") and del_res["result"].get("message"):
                                response_text = del_res["result"]["message"]
                            else:
                                response_text = assistant_message.content

                            response_text = clean_response(response_text) if response_text else None

                            logger.info(
                                "agent_auto_delete_executed",
                                user_id=str(self.user_id),
                                inferred_identifier=str(identifier),
                                deletion_success=del_res.get("success")
                            )

                            return {
                                "response": response_text or "I've handled that for you.",
                                "tool_calls": tool_calls_made
                            }
                except Exception:
                    logger.warn("auto_delete_failed", user_id=str(self.user_id))

        # Handle tool calls if any
        if assistant_message.tool_calls:
            tool_results = []

            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}

                # Execute the tool
                result = await self.tool_executor.execute_tool(tool_name, arguments)

                tool_calls_made.append({
                    "tool": tool_name,
                    "params": arguments,
                    "result": "success" if result.get("success") else "error"
                })

                tool_results.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "content": json.dumps(result)
                })

            # Build assistant message with only supported fields (avoid 'annotations' etc.)
            assistant_msg_dict = {
                "role": "assistant",
                "content": assistant_message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in assistant_message.tool_calls
                ]
            }
            messages.append(assistant_msg_dict)
            messages.extend(tool_results)

            # Ask the model for a final response. If the model gives a non-empty
            # message and all tool calls succeeded, prefer it (keeps human-friendly
            # phrasing). If any tool failed or model returned nothing, fall back
            # to deterministic confirmations constructed from the tool results.
            final_response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=500
            )

            model_text = final_response.choices[0].message.content

            all_success = all(tc.get("result") == "success" for tc in tool_calls_made)

            if model_text and all_success:
                response_text = model_text
            else:
                confirmations = []
                for call in tool_calls_made:
                    tool = call.get("tool")
                    if call.get("result") == "success":
                        for tr in tool_results:
                            content = tr["content"]
                            try:
                                payload = json.loads(content)
                            except Exception:
                                payload = {}

                            if payload.get("success") and payload.get("result"):
                                msg = payload["result"].get("message")
                                if msg:
                                    confirmations.append(msg)
                                    break

                        if not any(tool in c for c in confirmations):
                            if tool == "create_task":
                                confirmations.append("Created task.")
                            elif tool == "delete_task":
                                confirmations.append("Deleted task.")
                            elif tool == "complete_task":
                                confirmations.append("Marked task as complete.")
                            elif tool == "update_task":
                                confirmations.append("Updated task.")
                            else:
                                confirmations.append("Action completed.")
                    else:
                        confirmations.append(f"Failed to execute {call.get('tool')}: {call.get('params')}")

                response_text = " ".join(confirmations) if confirmations else (model_text or None)
        else:
            # No tool calls, just return the response
            response_text = assistant_message.content

        # Clean up any <think> tags from Qwen model responses
        response_text = clean_response(response_text) if response_text else None

        logger.info(
            "agent_response_generated",
            user_id=str(self.user_id),
            tool_calls_count=len(tool_calls_made)
        )

        return {
            "response": response_text or "I'm here to help! What would you like to do with your tasks?",
            "tool_calls": tool_calls_made
        }
