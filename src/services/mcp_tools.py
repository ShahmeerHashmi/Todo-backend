"""MCP tool definitions for exposing task operations to the AI agent.

Per constitution mandate, all AI actions MUST map to existing task CRUD logic
through these MCP tools. No direct database access by AI agents.
"""

from typing import Any, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.task_service import TaskService
from src.models.task_schemas import TaskCreateRequest, TaskUpdateRequest
from src.config.logging import get_logger

logger = get_logger(__name__)


# Tool definitions for OpenAI Agent SDK
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a new task for the user. Use this when the user wants to add, create, or remember something.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The title/name of the task to create"
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional description for the task"
                    }
                },
                "required": ["title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "List the user's tasks. Use this when the user wants to see, show, or view their tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "string",
                        "enum": ["all", "pending", "completed"],
                        "description": "Filter tasks by status. Default is 'all'."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "complete_task",
            "description": "Mark a task as complete/done. Use this when the user wants to complete, finish, or mark a task as done.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_identifier": {
                        "type": "string",
                        "description": "The task title or position number (e.g., '1', '2') to mark as complete"
                    }
                },
                "required": ["task_identifier"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_task",
            "description": "Update a task's title or description. Use this when the user wants to change, rename, or modify a task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_identifier": {
                        "type": "string",
                        "description": "The current task title or position number to update"
                    },
                    "new_title": {
                        "type": "string",
                        "description": "The new title for the task"
                    },
                    "new_description": {
                        "type": "string",
                        "description": "The new description for the task (optional)"
                    }
                },
                "required": ["task_identifier"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_task",
            "description": "Delete a task. Use this when the user wants to remove, delete, or get rid of a task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_identifier": {
                        "type": "string",
                        "description": "The task title or position number to delete"
                    }
                },
                "required": ["task_identifier"]
            }
        }
    }
]


class MCPToolExecutor:
    """Executes MCP tools by delegating to existing TaskService.

    This class bridges the AI agent's tool calls to the existing
    task CRUD operations, ensuring all data access goes through
    the established service layer.
    """

    def __init__(self, session: AsyncSession, user_id: UUID):
        """Initialize the tool executor.

        Args:
            session: Database session for task operations
            user_id: Authenticated user's UUID for scoping
        """
        self.session = session
        self.user_id = user_id

    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a tool by name with the given arguments.

        Args:
            tool_name: Name of the MCP tool to execute
            arguments: Tool parameters from the AI agent

        Returns:
            Dict with 'success' bool and 'result' or 'error' message
        """
        logger.info(
            "mcp_tool_execution",
            tool=tool_name,
            user_id=str(self.user_id),
            arguments=arguments
        )

        try:
            if tool_name == "create_task":
                return await self._create_task(arguments)
            elif tool_name == "list_tasks":
                return await self._list_tasks(arguments)
            elif tool_name == "complete_task":
                return await self._complete_task(arguments)
            elif tool_name == "update_task":
                return await self._update_task(arguments)
            elif tool_name == "delete_task":
                return await self._delete_task(arguments)
            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            logger.error(
                "mcp_tool_error",
                tool=tool_name,
                user_id=str(self.user_id),
                error=str(e)
            )
            return {"success": False, "error": str(e)}

    async def _create_task(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Create a new task."""
        title = arguments.get("title", "").strip()
        description = arguments.get("description", "")

        if not title:
            return {"success": False, "error": "Task title is required"}

        request = TaskCreateRequest(title=title, description=description or None)
        task = await TaskService.create_task(self.session, self.user_id, request)

        return {
            "success": True,
            "result": {
                "id": str(task.id),
                "title": task.title,
                "description": task.description,
                "message": f"Created task: {task.title}"
            }
        }

    async def _list_tasks(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """List user's tasks with optional filter."""
        filter_type = arguments.get("filter", "all")

        tasks = await TaskService.get_all_tasks(self.session, self.user_id)

        # Apply filter
        if filter_type == "pending":
            tasks = [t for t in tasks if not t.completed]
        elif filter_type == "completed":
            tasks = [t for t in tasks if t.completed]

        task_list = [
            {
                "position": i + 1,
                "id": str(t.id),
                "title": t.title,
                "description": t.description,
                "completed": t.completed
            }
            for i, t in enumerate(tasks)
        ]

        return {
            "success": True,
            "result": {
                "tasks": task_list,
                "count": len(task_list),
                "filter": filter_type
            }
        }

    async def _complete_task(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Mark a task as complete."""
        identifier = arguments.get("task_identifier", "").strip()

        if not identifier:
            return {"success": False, "error": "Task identifier is required"}

        task = await self._find_task(identifier)
        if not task:
            return {
                "success": False,
                "error": f"Task not found matching '{identifier}'"
            }

        if task.completed:
            return {
                "success": True,
                "result": {
                    "title": task.title,
                    "message": f"Task '{task.title}' was already completed"
                }
            }

        updated_task = await TaskService.toggle_completion(
            self.session, self.user_id, task.id
        )

        return {
            "success": True,
            "result": {
                "id": str(updated_task.id),
                "title": updated_task.title,
                "completed": updated_task.completed,
                "message": f"Marked '{updated_task.title}' as complete"
            }
        }

    async def _update_task(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Update a task's title or description."""
        identifier = arguments.get("task_identifier", "").strip()
        new_title = arguments.get("new_title")
        new_description = arguments.get("new_description")

        if not identifier:
            return {"success": False, "error": "Task identifier is required"}

        if not new_title and new_description is None:
            return {"success": False, "error": "At least new_title or new_description required"}

        task = await self._find_task(identifier)
        if not task:
            return {
                "success": False,
                "error": f"Task not found matching '{identifier}'"
            }

        request = TaskUpdateRequest(
            title=new_title if new_title else None,
            description=new_description
        )

        updated_task = await TaskService.update_task(
            self.session, self.user_id, task.id, request
        )

        return {
            "success": True,
            "result": {
                "id": str(updated_task.id),
                "title": updated_task.title,
                "description": updated_task.description,
                "message": f"Updated task to: {updated_task.title}"
            }
        }

    async def _delete_task(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Delete a task."""
        identifier = arguments.get("task_identifier", "").strip()

        if not identifier:
            return {"success": False, "error": "Task identifier is required"}

        task = await self._find_task(identifier)
        if not task:
            return {
                "success": False,
                "error": f"Task not found matching '{identifier}'"
            }

        task_title = task.title
        await TaskService.delete_task(self.session, self.user_id, task.id)

        return {
            "success": True,
            "result": {
                "title": task_title,
                "message": f"Deleted task: {task_title}"
            }
        }

    async def _find_task(self, identifier: str):
        """Find a task by title or position number.

        Args:
            identifier: Task title (fuzzy match) or position number

        Returns:
            Task entity or None if not found
        """
        tasks = await TaskService.get_all_tasks(self.session, self.user_id)

        # Try position number first. The external UI and tests expect
        # positions to be oldest-first (position 1 => earliest created task).
        # We'll therefore interpret numeric identifiers against reversed
        # `tasks` (which are returned newest-first) and try the common
        # filtered lists in this order: pending, completed, then all tasks.
        if identifier.isdigit():
            position = int(identifier)

            # Use oldest-first ordering based on explicit timestamp sorting
            tasks_oldest_first = sorted(tasks, key=lambda t: t.created_at)

            # Pending tasks (not completed)
            pending = [t for t in tasks_oldest_first if not t.completed]
            if 1 <= position <= len(pending):
                return pending[position - 1]

            # Completed tasks
            completed = [t for t in tasks_oldest_first if t.completed]
            if 1 <= position <= len(completed):
                return completed[position - 1]

            # Fallback to all tasks
            if 1 <= position <= len(tasks_oldest_first):
                return tasks_oldest_first[position - 1]

        # Try exact title match
        for task in tasks:
            if task.title.lower() == identifier.lower():
                return task

        # Try partial title match
        identifier_lower = identifier.lower()
        for task in tasks:
            if identifier_lower in task.title.lower():
                return task

        return None
