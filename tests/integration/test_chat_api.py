"""Integration tests for Chat API endpoints.

Tests the full request/response cycle including authentication,
AI orchestration, and database persistence.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import UUID

from src.services.chat_service import ChatService


class TestChatServiceIntegration:
    """Integration tests for ChatService."""

    @pytest.mark.asyncio
    async def test_process_chat_message_creates_conversation(
        self, async_session, test_user
    ):
        """Test that processing a message creates a conversation if none exists."""
        user_id = UUID(test_user["user_id"])

        # Mock OpenAI client to avoid real API calls
        with patch("src.agents.todo_agent.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            # Mock the chat completion response
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "I've added 'buy groceries' to your list."
            mock_response.choices[0].message.tool_calls = None
            mock_client.chat.completions.create.return_value = mock_response

            result = await ChatService.process_chat_message(
                async_session,
                user_id,
                "Add buy groceries to my list"
            )

            assert "conversation_id" in result
            assert "message_id" in result
            assert "response" in result
            assert result["response"] is not None

    @pytest.mark.asyncio
    async def test_process_chat_message_persists_messages(
        self, async_session, test_user
    ):
        """Test that both user and assistant messages are persisted."""
        user_id = UUID(test_user["user_id"])

        with patch("src.agents.todo_agent.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Task created!"
            mock_response.choices[0].message.tool_calls = None
            mock_client.chat.completions.create.return_value = mock_response

            result = await ChatService.process_chat_message(
                async_session,
                user_id,
                "Add test task"
            )

            # Get message history
            history = await ChatService.get_message_history(
                async_session,
                user_id,
                limit=10
            )

            assert len(history["messages"]) == 2
            assert history["messages"][0]["role"] == "user"
            assert history["messages"][0]["content"] == "Add test task"
            assert history["messages"][1]["role"] == "assistant"
            assert history["messages"][1]["content"] == "Task created!"

    @pytest.mark.asyncio
    async def test_process_chat_message_with_tool_call(
        self, async_session, test_user
    ):
        """Test that tool calls are executed and logged."""
        user_id = UUID(test_user["user_id"])

        with patch("src.agents.todo_agent.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            # First response with tool call
            mock_tool_call = MagicMock()
            mock_tool_call.id = "call_123"
            mock_tool_call.function.name = "create_task"
            mock_tool_call.function.arguments = '{"title": "buy groceries"}'

            mock_response1 = MagicMock()
            mock_response1.choices = [MagicMock()]
            mock_response1.choices[0].message.content = None
            mock_response1.choices[0].message.tool_calls = [mock_tool_call]
            mock_response1.choices[0].message.model_dump.return_value = {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "create_task",
                        "arguments": '{"title": "buy groceries"}'
                    }
                }]
            }

            # Second response after tool execution
            mock_response2 = MagicMock()
            mock_response2.choices = [MagicMock()]
            mock_response2.choices[0].message.content = "I've added 'buy groceries' to your list."

            mock_client.chat.completions.create.side_effect = [mock_response1, mock_response2]

            result = await ChatService.process_chat_message(
                async_session,
                user_id,
                "Add buy groceries"
            )

            assert result["response"] == "I've added 'buy groceries' to your list."
            assert len(result["tool_calls"]) == 1
            assert result["tool_calls"][0]["tool"] == "create_task"
            assert result["tool_calls"][0]["result"] == "success"

    @pytest.mark.asyncio
    async def test_get_or_create_conversation_reuses_existing(
        self, async_session, test_user
    ):
        """Test that existing conversation is reused."""
        user_id = UUID(test_user["user_id"])

        # Create first conversation
        conv1 = await ChatService.get_or_create_conversation(async_session, user_id)

        # Get conversation again
        conv2 = await ChatService.get_or_create_conversation(async_session, user_id)

        assert conv1.id == conv2.id

    @pytest.mark.asyncio
    async def test_get_recent_messages_limits_results(
        self, async_session, test_user
    ):
        """Test that get_recent_messages respects limit parameter."""
        user_id = UUID(test_user["user_id"])
        conv = await ChatService.get_or_create_conversation(async_session, user_id)

        # Add multiple messages
        for i in range(10):
            await ChatService.add_message(
                async_session,
                conv.id,
                "user" if i % 2 == 0 else "assistant",
                f"Message {i}"
            )

        # Get with limit
        messages = await ChatService.get_recent_messages(
            async_session,
            conv.id,
            limit=5
        )

        assert len(messages) == 5
        # Should be the most recent 5 messages
        assert messages[0].content == "Message 5"
        assert messages[4].content == "Message 9"

    @pytest.mark.asyncio
    async def test_message_history_pagination(
        self, async_session, test_user
    ):
        """Test message history pagination with 'before' parameter."""
        user_id = UUID(test_user["user_id"])
        conv = await ChatService.get_or_create_conversation(async_session, user_id)

        # Add multiple messages
        for i in range(5):
            await ChatService.add_message(
                async_session,
                conv.id,
                "user",
                f"Message {i}"
            )

        # Get history with small limit
        history = await ChatService.get_message_history(
            async_session,
            user_id,
            limit=3
        )

        assert len(history["messages"]) == 3
        assert history["has_more"] is True


class TestUserStory1AddTask:
    """Integration tests for User Story 1 - Add Task via Chat."""

    @pytest.mark.asyncio
    async def test_add_task_creates_task_in_database(
        self, async_session, test_user
    ):
        """Test that sending 'Add X' creates a task in the database."""
        user_id = UUID(test_user["user_id"])

        with patch("src.agents.todo_agent.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            # Simulate tool call for task creation
            mock_tool_call = MagicMock()
            mock_tool_call.id = "call_123"
            mock_tool_call.function.name = "create_task"
            mock_tool_call.function.arguments = '{"title": "buy groceries"}'

            mock_response1 = MagicMock()
            mock_response1.choices = [MagicMock()]
            mock_response1.choices[0].message.content = None
            mock_response1.choices[0].message.tool_calls = [mock_tool_call]
            mock_response1.choices[0].message.model_dump.return_value = {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "create_task",
                        "arguments": '{"title": "buy groceries"}'
                    }
                }]
            }

            mock_response2 = MagicMock()
            mock_response2.choices = [MagicMock()]
            mock_response2.choices[0].message.content = "Added!"

            mock_client.chat.completions.create.side_effect = [mock_response1, mock_response2]

            await ChatService.process_chat_message(
                async_session,
                user_id,
                "Add buy groceries to my list"
            )

            # Verify task was created
            from src.services.task_service import TaskService
            tasks = await TaskService.get_all_tasks(async_session, user_id)

            assert len(tasks) == 1
            assert tasks[0].title == "buy groceries"

    @pytest.mark.asyncio
    async def test_add_task_returns_confirmation(
        self, async_session, test_user
    ):
        """Test that adding a task returns confirmation message."""
        user_id = UUID(test_user["user_id"])

        with patch("src.agents.todo_agent.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "I've added 'buy milk' to your task list."
            mock_response.choices[0].message.tool_calls = None
            mock_client.chat.completions.create.return_value = mock_response

            result = await ChatService.process_chat_message(
                async_session,
                user_id,
                "Add buy milk"
            )

            assert "buy milk" in result["response"].lower() or "added" in result["response"].lower()


class TestUserStory2ViewTasks:
    """Integration tests for User Story 2 - View Tasks via Chat."""

    @pytest.mark.asyncio
    async def test_list_tasks_returns_all_tasks(
        self, async_session, test_user
    ):
        """Test that asking to see tasks returns the task list."""
        user_id = UUID(test_user["user_id"])

        # Create some tasks first
        from src.services.task_service import TaskService
        from src.models.task_schemas import TaskCreateRequest

        await TaskService.create_task(
            async_session,
            user_id,
            TaskCreateRequest(title="Task 1")
        )
        await TaskService.create_task(
            async_session,
            user_id,
            TaskCreateRequest(title="Task 2")
        )

        with patch("src.agents.todo_agent.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Here are your tasks:\n1. Task 1\n2. Task 2"
            mock_response.choices[0].message.tool_calls = None
            mock_client.chat.completions.create.return_value = mock_response

            result = await ChatService.process_chat_message(
                async_session,
                user_id,
                "What do I need to do?"
            )

            assert "Task 1" in result["response"] or "tasks" in result["response"].lower()
