"""Unit tests for MCP tools.

Tests tool definitions, argument validation, and TaskService delegation.
"""

import pytest
import pytest_asyncio
from uuid import UUID

from src.services.mcp_tools import TOOL_DEFINITIONS, MCPToolExecutor
from src.services.task_service import TaskService
from src.models.task_schemas import TaskCreateRequest


class TestToolDefinitions:
    """Tests for MCP tool definitions structure."""

    def test_all_required_tools_defined(self):
        """Verify all 5 required tools are defined."""
        tool_names = {t["function"]["name"] for t in TOOL_DEFINITIONS}
        expected = {"create_task", "list_tasks", "complete_task", "update_task", "delete_task"}
        assert tool_names == expected

    def test_create_task_tool_structure(self):
        """Verify create_task tool has correct parameters."""
        tool = next(t for t in TOOL_DEFINITIONS if t["function"]["name"] == "create_task")

        assert tool["type"] == "function"
        assert "title" in tool["function"]["parameters"]["properties"]
        assert "description" in tool["function"]["parameters"]["properties"]
        assert "title" in tool["function"]["parameters"]["required"]

    def test_list_tasks_tool_has_filter_parameter(self):
        """Verify list_tasks tool has filter parameter with enum."""
        tool = next(t for t in TOOL_DEFINITIONS if t["function"]["name"] == "list_tasks")

        filter_prop = tool["function"]["parameters"]["properties"]["filter"]
        assert filter_prop["type"] == "string"
        assert set(filter_prop["enum"]) == {"all", "pending", "completed"}

    def test_complete_task_requires_identifier(self):
        """Verify complete_task tool requires task_identifier."""
        tool = next(t for t in TOOL_DEFINITIONS if t["function"]["name"] == "complete_task")

        assert "task_identifier" in tool["function"]["parameters"]["properties"]
        assert "task_identifier" in tool["function"]["parameters"]["required"]


class TestMCPToolExecutorCreateTask:
    """Tests for create_task MCP tool execution (US1)."""

    @pytest_asyncio.fixture
    async def executor(self, async_session, test_user):
        """Create MCPToolExecutor with test context."""
        return MCPToolExecutor(async_session, UUID(test_user["user_id"]))

    @pytest.mark.asyncio
    async def test_create_task_success(self, executor, async_session, test_user):
        """Test successful task creation via MCP tool."""
        result = await executor.execute_tool(
            "create_task",
            {"title": "Buy groceries"}
        )

        assert result["success"] is True
        assert result["result"]["title"] == "Buy groceries"
        assert "id" in result["result"]
        assert "Created task" in result["result"]["message"]

    @pytest.mark.asyncio
    async def test_create_task_with_description(self, executor, async_session, test_user):
        """Test task creation with optional description."""
        result = await executor.execute_tool(
            "create_task",
            {"title": "Call mom", "description": "Discuss holiday plans"}
        )

        assert result["success"] is True
        assert result["result"]["title"] == "Call mom"
        assert result["result"]["description"] == "Discuss holiday plans"

    @pytest.mark.asyncio
    async def test_create_task_empty_title_fails(self, executor):
        """Test that empty title returns error."""
        result = await executor.execute_tool(
            "create_task",
            {"title": ""}
        )

        assert result["success"] is False
        assert "required" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_create_task_whitespace_title_fails(self, executor):
        """Test that whitespace-only title returns error."""
        result = await executor.execute_tool(
            "create_task",
            {"title": "   "}
        )

        assert result["success"] is False
        assert "required" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_create_task_extracts_title_from_natural_language(self, executor, async_session, test_user):
        """Test task creation extracts clean title.

        Note: Title extraction from natural language is done by the AI agent,
        not the MCP tool. The tool receives the extracted title directly.
        This test verifies the tool handles the extracted title correctly.
        """
        # AI would extract "buy milk" from "Add buy milk to my list"
        result = await executor.execute_tool(
            "create_task",
            {"title": "buy milk"}
        )

        assert result["success"] is True
        assert result["result"]["title"] == "buy milk"


class TestMCPToolExecutorListTasks:
    """Tests for list_tasks MCP tool execution (US2)."""

    @pytest_asyncio.fixture
    async def executor(self, async_session, test_user):
        """Create MCPToolExecutor with test context."""
        return MCPToolExecutor(async_session, UUID(test_user["user_id"]))

    @pytest.mark.asyncio
    async def test_list_tasks_empty(self, executor):
        """Test listing when no tasks exist."""
        result = await executor.execute_tool("list_tasks", {})

        assert result["success"] is True
        assert result["result"]["tasks"] == []
        assert result["result"]["count"] == 0

    @pytest.mark.asyncio
    async def test_list_tasks_returns_all_by_default(self, executor, async_session, test_user):
        """Test list_tasks returns all tasks by default."""
        # Create test tasks
        await executor.execute_tool("create_task", {"title": "Task 1"})
        await executor.execute_tool("create_task", {"title": "Task 2"})

        result = await executor.execute_tool("list_tasks", {})

        assert result["success"] is True
        assert result["result"]["count"] == 2
        assert result["result"]["filter"] == "all"

    @pytest.mark.asyncio
    async def test_list_tasks_filter_pending(self, executor, async_session, test_user):
        """Test filtering pending tasks only."""
        # Create tasks
        await executor.execute_tool("create_task", {"title": "Pending task"})
        create_result = await executor.execute_tool("create_task", {"title": "To complete"})

        # Complete one task
        await executor.execute_tool("complete_task", {"task_identifier": "To complete"})

        result = await executor.execute_tool("list_tasks", {"filter": "pending"})

        assert result["success"] is True
        assert result["result"]["count"] == 1
        assert result["result"]["tasks"][0]["title"] == "Pending task"
        assert result["result"]["filter"] == "pending"

    @pytest.mark.asyncio
    async def test_list_tasks_includes_position(self, executor, async_session, test_user):
        """Test that listed tasks include position numbers."""
        await executor.execute_tool("create_task", {"title": "First"})
        await executor.execute_tool("create_task", {"title": "Second"})

        result = await executor.execute_tool("list_tasks", {})

        assert result["result"]["tasks"][0]["position"] == 1
        assert result["result"]["tasks"][1]["position"] == 2


class TestMCPToolExecutorCompleteTask:
    """Tests for complete_task MCP tool execution (US3)."""

    @pytest_asyncio.fixture
    async def executor(self, async_session, test_user):
        """Create MCPToolExecutor with test context."""
        return MCPToolExecutor(async_session, UUID(test_user["user_id"]))

    @pytest.mark.asyncio
    async def test_complete_task_by_title(self, executor, async_session, test_user):
        """Test completing a task by exact title match."""
        await executor.execute_tool("create_task", {"title": "Buy groceries"})

        result = await executor.execute_tool(
            "complete_task",
            {"task_identifier": "Buy groceries"}
        )

        assert result["success"] is True
        assert result["result"]["completed"] is True
        assert "complete" in result["result"]["message"].lower()

    @pytest.mark.asyncio
    async def test_complete_task_by_position(self, executor, async_session, test_user):
        """Test completing a task by position number."""
        await executor.execute_tool("create_task", {"title": "First task"})
        await executor.execute_tool("create_task", {"title": "Second task"})

        result = await executor.execute_tool(
            "complete_task",
            {"task_identifier": "1"}
        )

        assert result["success"] is True
        assert result["result"]["title"] == "First task"
        assert result["result"]["completed"] is True

    @pytest.mark.asyncio
    async def test_complete_task_not_found(self, executor):
        """Test error when task not found."""
        result = await executor.execute_tool(
            "complete_task",
            {"task_identifier": "nonexistent task"}
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_complete_already_completed_task(self, executor, async_session, test_user):
        """Test completing an already completed task."""
        await executor.execute_tool("create_task", {"title": "Done task"})
        await executor.execute_tool("complete_task", {"task_identifier": "Done task"})

        result = await executor.execute_tool(
            "complete_task",
            {"task_identifier": "Done task"}
        )

        assert result["success"] is True
        assert "already completed" in result["result"]["message"].lower()


class TestMCPToolExecutorDeleteTask:
    """Tests for delete_task MCP tool execution (US4)."""

    @pytest_asyncio.fixture
    async def executor(self, async_session, test_user):
        """Create MCPToolExecutor with test context."""
        return MCPToolExecutor(async_session, UUID(test_user["user_id"]))

    @pytest.mark.asyncio
    async def test_delete_task_by_title(self, executor, async_session, test_user):
        """Test deleting a task by title."""
        await executor.execute_tool("create_task", {"title": "To delete"})

        result = await executor.execute_tool(
            "delete_task",
            {"task_identifier": "To delete"}
        )

        assert result["success"] is True
        assert "Deleted" in result["result"]["message"]

        # Verify task is gone
        list_result = await executor.execute_tool("list_tasks", {})
        assert list_result["result"]["count"] == 0

    @pytest.mark.asyncio
    async def test_delete_task_not_found(self, executor):
        """Test error when task to delete not found."""
        result = await executor.execute_tool(
            "delete_task",
            {"task_identifier": "nonexistent"}
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower()


class TestMCPToolExecutorUpdateTask:
    """Tests for update_task MCP tool execution (US5)."""

    @pytest_asyncio.fixture
    async def executor(self, async_session, test_user):
        """Create MCPToolExecutor with test context."""
        return MCPToolExecutor(async_session, UUID(test_user["user_id"]))

    @pytest.mark.asyncio
    async def test_update_task_title(self, executor, async_session, test_user):
        """Test updating a task's title."""
        await executor.execute_tool("create_task", {"title": "Old title"})

        result = await executor.execute_tool(
            "update_task",
            {"task_identifier": "Old title", "new_title": "New title"}
        )

        assert result["success"] is True
        assert result["result"]["title"] == "New title"

    @pytest.mark.asyncio
    async def test_update_task_description(self, executor, async_session, test_user):
        """Test updating a task's description."""
        await executor.execute_tool("create_task", {"title": "Task"})

        result = await executor.execute_tool(
            "update_task",
            {"task_identifier": "Task", "new_description": "New description"}
        )

        assert result["success"] is True
        assert result["result"]["description"] == "New description"

    @pytest.mark.asyncio
    async def test_update_task_requires_change(self, executor, async_session, test_user):
        """Test that update requires at least one field to change."""
        await executor.execute_tool("create_task", {"title": "Task"})

        result = await executor.execute_tool(
            "update_task",
            {"task_identifier": "Task"}
        )

        assert result["success"] is False
        assert "required" in result["error"].lower()
