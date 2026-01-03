"""Action Jackson (acnjxn) tool wrapper for Mother agent."""

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from .base import ToolWrapper, ToolResult


class AcnjxnWrapper(ToolWrapper):
    """Wrapper for acnjxn (Action Jackson) task manager.

    Provides AI-enhanced task management with:
    - Priority-based task recommendations
    - Conflict detection with goals/values
    - Life context-aware scheduling
    """

    def __init__(self, acnjxn_bin: Optional[Path] = None):
        """Initialize acnjxn wrapper."""
        self.acnjxn_bin = acnjxn_bin or Path.home() / ".local" / "bin" / "acnjxn"

        # Check for venv-based installation
        if not self.acnjxn_bin.exists():
            venv_bin = Path.home() / "projects" / "acnjxn" / ".venv" / "bin" / "acnjxn"
            if venv_bin.exists():
                self.acnjxn_bin = venv_bin

    @property
    def name(self) -> str:
        return "acnjxn"

    @property
    def description(self) -> str:
        return """Action Jackson - AI-Enhanced Task Manager and Personal Assistant.

Understands the owner's life context, goals, values, and constraints to provide
intelligent task prioritization and conflict detection.

Key capabilities:
- Get the single most important task to focus on right now
- Prioritize tasks based on life areas, goals, and energy levels
- Detect conflicts between activities and goals (e.g., BBQ vs weight loss)
- Add and manage tasks with rich context
- Provide AI-powered advice on task management"""

    def get_commands(self) -> Dict[str, Dict[str, Any]]:
        """Return available commands with their schemas."""
        return {
            "focus": {
                "description": "Get THE single most important task to focus on right now",
                "parameters": [],
                "confirmation_required": False,
            },
            "top": {
                "description": "Get top priority tasks",
                "parameters": [
                    {
                        "name": "limit",
                        "type": "integer",
                        "description": "Number of tasks to return (default: 5)",
                    },
                ],
                "confirmation_required": False,
            },
            "add": {
                "description": "Add a new task with smart inference. Automatically detects life area, client, and context from the task description.",
                "parameters": [
                    {
                        "name": "title",
                        "type": "string",
                        "description": "Task title/description",
                        "required": True,
                    },
                    {
                        "name": "area",
                        "type": "string",
                        "description": "Life area (family, health, finance, hucke_sanker, cleary, lawkraft, morpheus_mark, clients). Auto-detected if not specified.",
                    },
                    {
                        "name": "due",
                        "type": "string",
                        "description": "Due date (YYYY-MM-DD or +Nd for N days from now, e.g. +7d for next week)",
                    },
                    {
                        "name": "priority",
                        "type": "string",
                        "description": "Priority level: critical, high, normal, low, someday",
                    },
                    {
                        "name": "client",
                        "type": "string",
                        "description": "Client name if applicable",
                    },
                    {
                        "name": "project",
                        "type": "string",
                        "description": "Project name if applicable",
                    },
                    {
                        "name": "notes",
                        "type": "string",
                        "description": "Additional notes",
                    },
                ],
                "confirmation_required": False,
            },
            "list": {
                "description": "List tasks with optional filters",
                "parameters": [
                    {
                        "name": "area",
                        "type": "string",
                        "description": "Filter by life area",
                    },
                    {
                        "name": "status",
                        "type": "string",
                        "description": "Filter by status: inbox, todo, in_progress, waiting, completed",
                    },
                    {
                        "name": "overdue",
                        "type": "boolean",
                        "description": "Show only overdue tasks",
                    },
                    {
                        "name": "limit",
                        "type": "integer",
                        "description": "Maximum number of tasks (default: 20)",
                    },
                ],
                "confirmation_required": False,
            },
            "conflict": {
                "description": "Check if an activity conflicts with goals or values",
                "parameters": [
                    {
                        "name": "activity",
                        "type": "string",
                        "description": "Description of the activity to check (e.g., 'going to a BBQ party')",
                        "required": True,
                    },
                ],
                "confirmation_required": False,
            },
            "complete": {
                "description": "Mark a task as completed",
                "parameters": [
                    {
                        "name": "task_id",
                        "type": "string",
                        "description": "Task ID to complete",
                        "required": True,
                    },
                ],
                "confirmation_required": False,
            },
            "search": {
                "description": "Search tasks by title or description",
                "parameters": [
                    {
                        "name": "query",
                        "type": "string",
                        "description": "Search query",
                        "required": True,
                    },
                    {
                        "name": "limit",
                        "type": "integer",
                        "description": "Maximum results (default: 10)",
                    },
                ],
                "confirmation_required": False,
            },
            "ask": {
                "description": "Ask the AI advisor a question about tasks or priorities",
                "parameters": [
                    {
                        "name": "question",
                        "type": "string",
                        "description": "Question to ask (e.g., 'What should I prioritize today?')",
                        "required": True,
                    },
                ],
                "confirmation_required": False,
            },
            "status": {
                "description": "Get task statistics and system status",
                "parameters": [],
                "confirmation_required": False,
            },
            "weigh": {
                "description": "Evaluate an activity against your values and life vision. Returns value alignment score (0-100), vision alignment score (0-100), trade-offs, and a verdict (proceed/caution/defer/skip). Use this to help decide whether to commit to activities.",
                "parameters": [
                    {
                        "name": "activity",
                        "type": "string",
                        "description": "Activity to evaluate (e.g., 'attending a conference in Munich', 'going to a BBQ party')",
                        "required": True,
                    },
                    {
                        "name": "area",
                        "type": "string",
                        "description": "Life area context (optional, auto-detected if not specified)",
                    },
                ],
                "confirmation_required": False,
            },
            "reflect": {
                "description": "Start a Socratic reflection session. Returns a thought-provoking opening question to help examine life, goals, and values. Use for weekly reviews, exploring purpose, or examining values.",
                "parameters": [
                    {
                        "name": "focus",
                        "type": "string",
                        "description": "Reflection focus: 'weekly' for weekly review, 'purpose' to explore life purpose, 'values' to examine values, or omit for open reflection",
                        "enum": ["weekly", "purpose", "values"],
                    },
                ],
                "confirmation_required": False,
            },
            "think": {
                "description": "Deep thinking on a specific question. Returns a Socratic response that helps explore the question from multiple angles. Use when wrestling with important decisions or life questions.",
                "parameters": [
                    {
                        "name": "question",
                        "type": "string",
                        "description": "The question to think deeply about (e.g., 'Am I on the right path?', 'Should I take on more clients?', 'What am I avoiding?')",
                        "required": True,
                    },
                ],
                "confirmation_required": False,
            },
            "soul": {
                "description": "Show the owner's core identity: values (ranked by priority), life purpose, guiding principles, and current life season. Use this to understand what matters most to the owner.",
                "parameters": [],
                "confirmation_required": False,
            },
            "goals": {
                "description": "Show the owner's life goals with progress tracking. Includes goal status, progress percentage, target dates, and milestones.",
                "parameters": [
                    {
                        "name": "show_all",
                        "type": "boolean",
                        "description": "Include completed and inactive goals (default: only active goals)",
                    },
                ],
                "confirmation_required": False,
            },
        }

    def build_command(self, command: str, args: Dict[str, Any]) -> list:
        """Build CLI command from arguments."""
        cmd = [str(self.acnjxn_bin), command]

        if command == "focus":
            # No additional args needed
            pass

        elif command == "top":
            if limit := args.get("limit"):
                cmd.extend(["--limit", str(limit)])

        elif command == "add":
            cmd.append(args.get("title", "Untitled"))
            if area := args.get("area"):
                cmd.extend(["--area", area])
            if due := args.get("due"):
                cmd.extend(["--due", due])
            if priority := args.get("priority"):
                cmd.extend(["--priority", priority])
            if client := args.get("client"):
                cmd.extend(["--client", client])
            if project := args.get("project"):
                cmd.extend(["--project", project])
            if notes := args.get("notes"):
                cmd.extend(["--notes", notes])

        elif command == "list":
            if area := args.get("area"):
                cmd.extend(["--area", area])
            if status := args.get("status"):
                cmd.extend(["--status", status])
            if args.get("overdue"):
                cmd.append("--overdue")
            if limit := args.get("limit"):
                cmd.extend(["--limit", str(limit)])

        elif command == "conflict":
            activity = args.get("activity", "")
            cmd.append(activity)

        elif command == "complete":
            cmd.append(args.get("task_id", ""))

        elif command == "search":
            cmd.append(args.get("query", ""))
            if limit := args.get("limit"):
                cmd.extend(["--limit", str(limit)])

        elif command == "ask":
            cmd.append(args.get("question", ""))

        elif command == "status":
            pass

        elif command == "weigh":
            cmd.append(args.get("activity", ""))
            if area := args.get("area"):
                cmd.extend(["--area", area])
            cmd.append("--no-action")  # Non-interactive for mother

        elif command == "reflect":
            focus = args.get("focus")
            if focus == "weekly":
                cmd.append("--weekly")
            elif focus == "purpose":
                cmd.append("--purpose")
            elif focus == "values":
                cmd.append("--values")
            cmd.append("--single")  # Non-interactive for mother

        elif command == "think":
            cmd.append(args.get("question", ""))
            cmd.append("--single")  # Non-interactive for mother

        elif command == "soul":
            pass  # No arguments needed

        elif command == "goals":
            if args.get("show_all"):
                cmd.append("--all")

        return cmd

    def execute(self, command: str, args: Dict[str, Any]) -> ToolResult:
        """Execute an acnjxn command."""
        import time

        start_time = time.time()

        if not self.acnjxn_bin.exists():
            return ToolResult(
                success=False,
                exit_code=1,
                stdout="",
                stderr=f"acnjxn not found at {self.acnjxn_bin}",
                error_message="acnjxn CLI not installed",
                execution_time=0,
            )

        cmd = self.build_command(command, args)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                env=os.environ.copy(),
            )

            execution_time = time.time() - start_time

            return ToolResult(
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                execution_time=execution_time,
                parsed_data=self.parse_output(command, result.stdout),
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="Command timed out after 60 seconds",
                error_message="Timeout",
                execution_time=60,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                error_message=str(e),
                execution_time=time.time() - start_time,
            )

    def parse_output(self, command: str, output: str) -> Optional[Dict[str, Any]]:
        """Parse command output into structured data."""
        from ..parsers.output import OutputParser, strip_ansi

        parser = OutputParser()

        # Strip ANSI codes
        clean_output = strip_ansi(output)

        if command == "focus":
            return self._parse_focus_output(clean_output)
        elif command == "top":
            return self._parse_top_output(clean_output)
        elif command == "status":
            return self._parse_status_output(clean_output)
        elif command == "conflict":
            return self._parse_conflict_output(clean_output)
        elif command == "weigh":
            return self._parse_weigh_output(clean_output)
        else:
            return {"raw": clean_output}

    def _parse_focus_output(self, output: str) -> Dict[str, Any]:
        """Parse focus command output."""
        result = {
            "has_task": False,
            "task": None,
            "explanation": "",
            "conflicts": [],
            "warnings": [],
        }

        lines = output.strip().split("\n")
        current_section = None

        for line in lines:
            line_clean = line.strip()

            if "YOUR #1 PRIORITY" in line_clean.upper():
                result["has_task"] = True
                current_section = "task"
            elif "Area:" in line_clean:
                parts = line_clean.split("|")
                if len(parts) >= 1:
                    result["area"] = parts[0].replace("Area:", "").strip()
                if len(parts) >= 2:
                    score_part = parts[1].strip()
                    if "Score:" in score_part:
                        try:
                            result["score"] = float(score_part.replace("Score:", "").strip())
                        except ValueError:
                            pass
            elif "Score" in line_clean and ":" in line_clean:
                result["explanation"] = line_clean
            elif "CONFLICTS" in line_clean.upper():
                current_section = "conflicts"
            elif "WARNING" in line_clean.upper():
                result["warnings"].append(line_clean)
            elif current_section == "task" and line_clean and not line_clean.startswith("Area"):
                # Skip Rich box borders
                if line_clean.startswith(("╭", "│", "╰", "─", "┌", "└", "┐", "┘")):
                    continue
                if not result.get("task"):
                    result["task"] = line_clean
            elif current_section == "conflicts" and line_clean.startswith("-"):
                result["conflicts"].append(line_clean[1:].strip())

        return result

    def _parse_top_output(self, output: str) -> Dict[str, Any]:
        """Parse top priorities output."""
        tasks = []
        lines = output.strip().split("\n")

        for line in lines:
            # Look for numbered entries like "1. [85] Task title"
            if line.strip() and line.strip()[0].isdigit() and "." in line:
                tasks.append(line.strip())

        return {"tasks": tasks, "count": len(tasks)}

    def _parse_status_output(self, output: str) -> Dict[str, Any]:
        """Parse status output."""
        result = {}
        lines = output.strip().split("\n")

        for line in lines:
            if "Total tasks:" in line:
                try:
                    result["total"] = int(line.split(":")[-1].strip())
                except ValueError:
                    pass
            elif "Active:" in line:
                try:
                    result["active"] = int(line.split(":")[-1].strip())
                except ValueError:
                    pass
            elif "Overdue:" in line:
                try:
                    result["overdue"] = int(line.split(":")[-1].strip())
                except ValueError:
                    pass

        return result

    def _parse_conflict_output(self, output: str) -> Dict[str, Any]:
        """Parse conflict check output."""
        result = {
            "has_conflicts": False,
            "conflicts": [],
            "recommendation": "proceed",
            "reasoning": "",
        }

        if "No conflicts detected" in output:
            return result

        lines = output.strip().split("\n")
        current_conflict = None

        for line in lines:
            line_clean = line.strip()

            if any(severity in line_clean for severity in ["LOW:", "MEDIUM:", "HIGH:", "CRITICAL:"]):
                result["has_conflicts"] = True
                current_conflict = {"severity": "", "description": ""}
                for severity in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
                    if severity in line_clean:
                        current_conflict["severity"] = severity.lower()
                        current_conflict["description"] = line_clean.split(":", 1)[-1].strip()
                        break
                result["conflicts"].append(current_conflict)
            elif "RECOMMENDATION:" in line_clean.upper():
                rec = line_clean.split(":")[-1].strip().lower()
                result["recommendation"] = rec
            elif "Suggestion:" in line_clean and current_conflict:
                current_conflict["suggestion"] = line_clean.split(":", 1)[-1].strip()

        return result

    def _parse_weigh_output(self, output: str) -> Dict[str, Any]:
        """Parse weigh command output."""
        import re

        result = {
            "value_score": 0,
            "vision_score": 0,
            "verdict": "unknown",
            "trade_offs": [],
            "recommendation": "",
        }

        lines = output.strip().split("\n")

        for line in lines:
            line_clean = line.strip()

            if "VALUE SCORE" in line_clean.upper():
                # Extract score from line like "VALUE SCORE    ██████████ 75/100"
                match = re.search(r'(\d+)/100', line_clean)
                if match:
                    result["value_score"] = int(match.group(1))
            elif "VISION SCORE" in line_clean.upper():
                match = re.search(r'(\d+)/100', line_clean)
                if match:
                    result["vision_score"] = int(match.group(1))
            elif any(v in line_clean.upper() for v in ["PROCEED", "CAUTION", "DEFER", "SKIP"]):
                for verdict in ["PROCEED_AWARE", "PROCEED", "CAUTION", "DEFER", "SKIP"]:
                    if verdict in line_clean.upper():
                        result["verdict"] = verdict.lower()
                        break
            elif "⚖" in line_clean or "Trade-off" in line_clean:
                result["trade_offs"].append(line_clean.replace("⚖", "").strip())

        return result
