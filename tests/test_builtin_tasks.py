"""Tests for the built-in tasks plugin."""

from datetime import datetime, timedelta

import pytest

from mother.plugins.builtin.tasks import TasksPlugin
from mother.plugins.builtin.tasks.storage import (
    Task,
    TaskPriority,
    TaskStatus,
    TaskStore,
    parse_due_date,
)


class TestParseDueDate:
    """Tests for due date parsing."""

    def test_parse_today(self):
        """Test parsing 'today'."""
        result = parse_due_date("today")
        assert result is not None
        assert result.date() == datetime.now().date()

    def test_parse_tomorrow(self):
        """Test parsing 'tomorrow'."""
        result = parse_due_date("tomorrow")
        assert result is not None
        expected = (datetime.now() + timedelta(days=1)).date()
        assert result.date() == expected

    def test_parse_relative_days(self):
        """Test parsing '+Nd' format."""
        result = parse_due_date("+7d")
        assert result is not None
        expected = (datetime.now() + timedelta(days=7)).date()
        assert result.date() == expected

    def test_parse_iso_date(self):
        """Test parsing ISO format."""
        result = parse_due_date("2024-12-31")
        assert result is not None
        assert result.year == 2024
        assert result.month == 12
        assert result.day == 31

    def test_parse_empty(self):
        """Test parsing empty string."""
        result = parse_due_date("")
        assert result is None

    def test_parse_invalid(self):
        """Test parsing invalid string."""
        result = parse_due_date("not a date")
        assert result is None


class TestTaskPriority:
    """Tests for task priority."""

    def test_priority_score(self):
        """Test priority scores are ordered correctly."""
        assert TaskPriority.CRITICAL.score > TaskPriority.HIGH.score
        assert TaskPriority.HIGH.score > TaskPriority.NORMAL.score
        assert TaskPriority.NORMAL.score > TaskPriority.LOW.score
        assert TaskPriority.LOW.score > TaskPriority.SOMEDAY.score


class TestTask:
    """Tests for Task dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        task = Task(
            task_id="abc123",
            title="Test task",
            status=TaskStatus.TODO,
            priority=TaskPriority.HIGH,
            area="work",
        )
        data = task.to_dict()
        assert data["task_id"] == "abc123"
        assert data["title"] == "Test task"
        assert data["status"] == "todo"
        assert data["priority"] == "high"
        assert data["area"] == "work"

    def test_is_overdue_no_due_date(self):
        """Test is_overdue with no due date."""
        task = Task(task_id="abc", title="Test")
        assert task.is_overdue is False

    def test_is_overdue_future(self):
        """Test is_overdue with future due date."""
        task = Task(
            task_id="abc",
            title="Test",
            due_date=datetime.now() + timedelta(days=7),
        )
        assert task.is_overdue is False

    def test_is_overdue_past(self):
        """Test is_overdue with past due date."""
        task = Task(
            task_id="abc",
            title="Test",
            due_date=datetime.now() - timedelta(days=1),
        )
        assert task.is_overdue is True

    def test_is_overdue_completed(self):
        """Test completed tasks are not overdue."""
        task = Task(
            task_id="abc",
            title="Test",
            status=TaskStatus.COMPLETED,
            due_date=datetime.now() - timedelta(days=1),
        )
        assert task.is_overdue is False

    def test_urgency_score_no_due(self):
        """Test urgency score with no due date."""
        task = Task(task_id="abc", title="Test")
        assert task.urgency_score == 0

    def test_urgency_score_overdue(self):
        """Test urgency score for overdue task."""
        task = Task(
            task_id="abc",
            title="Test",
            due_date=datetime.now() - timedelta(days=1),
        )
        assert task.urgency_score >= 80

    def test_total_score(self):
        """Test total score calculation."""
        task = Task(
            task_id="abc",
            title="Test",
            priority=TaskPriority.CRITICAL,
            due_date=datetime.now(),  # Due today
        )
        assert task.total_score > 0


class TestTaskStore:
    """Tests for TaskStore."""

    @pytest.fixture
    def store(self, tmp_path):
        """Create a temporary task store."""
        return TaskStore(tmp_path / "tasks.db")

    @pytest.fixture
    def sample_task(self, store):
        """Create a sample task."""
        task = Task(
            task_id=store.generate_task_id(),
            title="Sample task",
            status=TaskStatus.TODO,
            priority=TaskPriority.HIGH,
            area="work",
        )
        store.add_task(task)
        return task

    def test_add_and_get_task(self, store):
        """Test adding and retrieving a task."""
        task = Task(
            task_id=store.generate_task_id(),
            title="Test task",
            priority=TaskPriority.NORMAL,
        )
        task_id = store.add_task(task)

        retrieved = store.get_task(task_id)
        assert retrieved is not None
        assert retrieved.title == "Test task"

    def test_update_task(self, store, sample_task):
        """Test updating a task."""
        sample_task.title = "Updated title"
        sample_task.priority = TaskPriority.CRITICAL

        success = store.update_task(sample_task)
        assert success is True

        retrieved = store.get_task(sample_task.task_id)
        assert retrieved.title == "Updated title"
        assert retrieved.priority == TaskPriority.CRITICAL

    def test_delete_task(self, store, sample_task):
        """Test deleting a task."""
        success = store.delete_task(sample_task.task_id)
        assert success is True

        retrieved = store.get_task(sample_task.task_id)
        assert retrieved is None

    def test_complete_task(self, store, sample_task):
        """Test completing a task."""
        success = store.complete_task(sample_task.task_id)
        assert success is True

        retrieved = store.get_task(sample_task.task_id)
        assert retrieved.status == TaskStatus.COMPLETED
        assert retrieved.completed_at is not None

    def test_list_tasks(self, store):
        """Test listing tasks."""
        # Add multiple tasks
        for i in range(5):
            task = Task(
                task_id=store.generate_task_id(),
                title=f"Task {i}",
            )
            store.add_task(task)

        tasks = store.list_tasks()
        assert len(tasks) == 5

    def test_list_tasks_by_status(self, store, sample_task):
        """Test filtering by status."""
        # Add a completed task
        completed = Task(
            task_id=store.generate_task_id(),
            title="Completed task",
            status=TaskStatus.COMPLETED,
        )
        store.add_task(completed)

        todo_tasks = store.list_tasks(status=TaskStatus.TODO)
        assert len(todo_tasks) == 1
        assert todo_tasks[0].title == "Sample task"

    def test_list_tasks_by_area(self, store, sample_task):
        """Test filtering by area."""
        # Add another task with different area
        other = Task(
            task_id=store.generate_task_id(),
            title="Personal task",
            area="personal",
        )
        store.add_task(other)

        work_tasks = store.list_tasks(area="work")
        assert len(work_tasks) == 1
        assert work_tasks[0].area == "work"

    def test_get_top_tasks(self, store):
        """Test getting top priority tasks."""
        # Add tasks with different priorities
        priorities = [
            TaskPriority.LOW,
            TaskPriority.CRITICAL,
            TaskPriority.NORMAL,
            TaskPriority.HIGH,
        ]
        for i, priority in enumerate(priorities):
            task = Task(
                task_id=store.generate_task_id(),
                title=f"Task {priority.value}",
                priority=priority,
            )
            store.add_task(task)

        top = store.get_top_tasks(limit=2)
        assert len(top) == 2
        # Critical should be first
        assert top[0].priority == TaskPriority.CRITICAL

    def test_get_focus_task(self, store):
        """Test getting focus task."""
        task = Task(
            task_id=store.generate_task_id(),
            title="Only task",
            priority=TaskPriority.HIGH,
        )
        store.add_task(task)

        focus = store.get_focus_task()
        assert focus is not None
        assert focus.title == "Only task"

    def test_get_focus_task_empty(self, store):
        """Test focus task when no tasks."""
        focus = store.get_focus_task()
        assert focus is None

    def test_search_tasks(self, store):
        """Test searching tasks."""
        task1 = Task(
            task_id=store.generate_task_id(),
            title="Buy groceries",
            notes="milk, eggs, bread",
        )
        task2 = Task(
            task_id=store.generate_task_id(),
            title="Call mom",
        )
        store.add_task(task1)
        store.add_task(task2)

        results = store.search_tasks("groceries")
        assert len(results) == 1
        assert results[0].title == "Buy groceries"

    def test_get_stats(self, store, sample_task):
        """Test getting statistics."""
        stats = store.get_stats()
        assert stats["total"] == 1
        assert "by_status" in stats
        assert "by_priority" in stats

    def test_get_areas(self, store, sample_task):
        """Test getting areas list."""
        areas = store.get_areas()
        assert "work" in areas


class TestTasksPlugin:
    """Tests for TasksPlugin."""

    @pytest.fixture
    def plugin(self, tmp_path):
        """Create a plugin with temporary storage."""
        return TasksPlugin(config={"db_path": str(tmp_path / "tasks.db")})

    def test_init(self, plugin):
        """Test plugin initialization."""
        assert plugin.manifest.plugin.name == "tasks"
        assert plugin.manifest.plugin.version == "1.0.0"

    def test_capabilities(self, plugin):
        """Test plugin capabilities."""
        caps = plugin.get_capabilities()
        assert len(caps) == 11
        cap_names = [c.name for c in caps]
        assert "focus" in cap_names
        assert "top" in cap_names
        assert "add" in cap_names
        assert "list" in cap_names
        assert "complete" in cap_names
        assert "delete" in cap_names
        assert "search" in cap_names

    def test_delete_requires_confirmation(self, plugin):
        """Test delete requires confirmation."""
        caps = plugin.get_capabilities()
        delete_cap = next(c for c in caps if c.name == "delete")
        assert delete_cap.confirmation_required is True

    @pytest.mark.asyncio
    async def test_unknown_capability(self, plugin):
        """Test unknown capability."""
        result = await plugin.execute("unknown", {})
        assert result.success is False
        assert result.error_code == "UNKNOWN_CAPABILITY"

    @pytest.mark.asyncio
    async def test_add_task(self, plugin):
        """Test adding a task."""
        result = await plugin.execute(
            "add",
            {"title": "New task", "priority": "high", "area": "work"},
        )
        assert result.success is True
        assert result.data["title"] == "New task"
        assert result.data["priority"] == "high"

    @pytest.mark.asyncio
    async def test_add_task_with_due(self, plugin):
        """Test adding task with due date."""
        result = await plugin.execute(
            "add",
            {"title": "Due task", "due": "+7d"},
        )
        assert result.success is True
        assert result.data["due_date"] is not None

    @pytest.mark.asyncio
    async def test_add_task_invalid_priority(self, plugin):
        """Test adding task with invalid priority."""
        result = await plugin.execute(
            "add",
            {"title": "Task", "priority": "invalid"},
        )
        assert result.success is False
        assert result.error_code == "INVALID_INPUT"

    @pytest.mark.asyncio
    async def test_list_tasks(self, plugin):
        """Test listing tasks."""
        # Add some tasks
        await plugin.execute("add", {"title": "Task 1"})
        await plugin.execute("add", {"title": "Task 2"})

        result = await plugin.execute("list", {})
        assert result.success is True
        assert result.data["count"] == 2

    @pytest.mark.asyncio
    async def test_list_tasks_with_filter(self, plugin):
        """Test listing with status filter."""
        await plugin.execute("add", {"title": "Task 1"})

        result = await plugin.execute("list", {"status": "todo"})
        assert result.success is True
        assert result.data["count"] == 1

    @pytest.mark.asyncio
    async def test_complete_task(self, plugin):
        """Test completing a task."""
        add_result = await plugin.execute("add", {"title": "Complete me"})
        task_id = add_result.data["task_id"]

        result = await plugin.execute("complete", {"task_id": task_id})
        assert result.success is True

        # Verify completed
        get_result = await plugin.execute("get", {"task_id": task_id})
        assert get_result.data["status"] == "completed"

    @pytest.mark.asyncio
    async def test_complete_not_found(self, plugin):
        """Test completing non-existent task."""
        result = await plugin.execute("complete", {"task_id": "nonexistent"})
        assert result.success is False
        assert result.error_code == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_update_task(self, plugin):
        """Test updating a task."""
        add_result = await plugin.execute("add", {"title": "Original"})
        task_id = add_result.data["task_id"]

        result = await plugin.execute(
            "update",
            {"task_id": task_id, "title": "Updated", "priority": "critical"},
        )
        assert result.success is True
        assert result.data["title"] == "Updated"
        assert result.data["priority"] == "critical"

    @pytest.mark.asyncio
    async def test_delete_task(self, plugin):
        """Test deleting a task."""
        add_result = await plugin.execute("add", {"title": "Delete me"})
        task_id = add_result.data["task_id"]

        result = await plugin.execute("delete", {"task_id": task_id})
        assert result.success is True

        # Verify deleted
        get_result = await plugin.execute("get", {"task_id": task_id})
        assert get_result.success is False

    @pytest.mark.asyncio
    async def test_focus_no_tasks(self, plugin):
        """Test focus with no tasks."""
        result = await plugin.execute("focus", {})
        assert result.success is True
        assert result.data["has_task"] is False

    @pytest.mark.asyncio
    async def test_focus_with_tasks(self, plugin):
        """Test focus with tasks."""
        await plugin.execute("add", {"title": "Important", "priority": "critical"})

        result = await plugin.execute("focus", {})
        assert result.success is True
        assert result.data["has_task"] is True
        assert result.data["task"]["title"] == "Important"

    @pytest.mark.asyncio
    async def test_top(self, plugin):
        """Test getting top tasks."""
        await plugin.execute("add", {"title": "Low", "priority": "low"})
        await plugin.execute("add", {"title": "High", "priority": "high"})
        await plugin.execute("add", {"title": "Critical", "priority": "critical"})

        result = await plugin.execute("top", {"limit": 2})
        assert result.success is True
        assert result.data["count"] == 2
        # Critical should be first
        assert result.data["tasks"][0]["priority"] == "critical"

    @pytest.mark.asyncio
    async def test_search(self, plugin):
        """Test searching tasks."""
        await plugin.execute("add", {"title": "Buy groceries"})
        await plugin.execute("add", {"title": "Call mom"})

        result = await plugin.execute("search", {"query": "groceries"})
        assert result.success is True
        assert result.data["count"] == 1

    @pytest.mark.asyncio
    async def test_stats(self, plugin):
        """Test getting stats."""
        await plugin.execute("add", {"title": "Task 1"})
        await plugin.execute("add", {"title": "Task 2", "priority": "high"})

        result = await plugin.execute("stats", {})
        assert result.success is True
        assert result.data["total"] == 2

    @pytest.mark.asyncio
    async def test_areas(self, plugin):
        """Test getting areas."""
        await plugin.execute("add", {"title": "Work task", "area": "work"})
        await plugin.execute("add", {"title": "Personal task", "area": "personal"})

        result = await plugin.execute("areas", {})
        assert result.success is True
        assert "work" in result.data["areas"]
        assert "personal" in result.data["areas"]
