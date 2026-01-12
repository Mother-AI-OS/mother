"""Cognitive reasoning module for Mother agent.

Provides:
- Reflection loop: Post-tool assessment of results
- Reasoning phase: Explicit think-before-act with goal decomposition
- Confidence tracking: Uncertainty handling and adaptive behavior
- Dynamic context: Update memory context during execution
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger("mother.cognitive")


class ThinkingMode(Enum):
    """Cognitive processing modes."""

    REACTIVE = "reactive"  # Quick, direct response
    DELIBERATE = "deliberate"  # Multi-step reasoning
    REFLECTIVE = "reflective"  # Post-action assessment


class Confidence(Enum):
    """Confidence levels for actions and conclusions."""

    HIGH = "high"  # >80% certain
    MEDIUM = "medium"  # 50-80% certain
    LOW = "low"  # <50% certain
    UNCERTAIN = "uncertain"  # Need more information


@dataclass
class ThoughtChain:
    """A chain of reasoning steps."""

    id: str
    goal: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    hypotheses: list[str] = field(default_factory=list)
    conclusions: list[str] = field(default_factory=list)
    confidence: Confidence = Confidence.MEDIUM
    created_at: datetime = field(default_factory=datetime.now)

    def add_step(
        self,
        step_type: str,
        content: str,
        evidence: list[str] | None = None,
        confidence: Confidence | None = None,
    ) -> None:
        """Add a reasoning step."""
        self.steps.append(
            {
                "type": step_type,
                "content": content,
                "evidence": evidence or [],
                "confidence": (confidence or Confidence.MEDIUM).value,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "goal": self.goal,
            "steps": self.steps,
            "hypotheses": self.hypotheses,
            "conclusions": self.conclusions,
            "confidence": self.confidence.value,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ReflectionResult:
    """Result of a reflection on tool execution."""

    tool_name: str
    expected_outcome: str
    actual_outcome: str
    success: bool
    insight: str
    should_retry: bool = False
    alternative_approach: str | None = None
    confidence_delta: int = 0  # Change in confidence (-100 to +100)


@dataclass
class CognitiveState:
    """Current cognitive state of the agent."""

    current_goal: str | None = None
    sub_goals: list[str] = field(default_factory=list)
    active_hypotheses: list[str] = field(default_factory=list)
    confirmed_facts: list[str] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    current_thought_chain: ThoughtChain | None = None
    confidence: Confidence = Confidence.MEDIUM
    thinking_mode: ThinkingMode = ThinkingMode.REACTIVE
    reflections: list[ReflectionResult] = field(default_factory=list)
    learned_patterns: list[dict[str, Any]] = field(default_factory=list)


class CognitiveEngine:
    """
    Engine for cognitive reasoning and reflection.

    Provides structured thinking capabilities:
    1. Goal decomposition - Break complex goals into sub-goals
    2. Hypothesis generation - Form hypotheses before action
    3. Reflection - Assess results and learn from outcomes
    4. Confidence tracking - Adjust behavior based on certainty
    """

    # Reasoning prompt for goal decomposition
    REASONING_PROMPT = """Analyze this request and break it down into clear reasoning steps.

Request: {request}

Context (what we know):
{context}

Provide your analysis in this JSON format:
{{
    "understanding": "What the user wants to achieve",
    "sub_goals": ["List of sub-goals to achieve the main goal"],
    "hypotheses": ["Assumptions we're making that should be validated"],
    "information_needed": ["What we need to find out first"],
    "approach": "Step-by-step approach to solve this",
    "potential_issues": ["Things that could go wrong"],
    "confidence": "high|medium|low|uncertain"
}}"""

    # Reflection prompt for post-action assessment
    REFLECTION_PROMPT = """Reflect on the outcome of this action.

Action: {action}
Expected: {expected}
Actual Result: {actual}

Provide your reflection in this JSON format:
{{
    "success": true/false,
    "insight": "What we learned from this action",
    "should_retry": true/false,
    "alternative_approach": "If retry needed, what to try instead (null otherwise)",
    "confidence_adjustment": -100 to +100 (how much to adjust confidence),
    "pattern_learned": "Any pattern we should remember for future (null if none)"
}}"""

    def __init__(self) -> None:
        self.state = CognitiveState()
        self._pattern_cache: list[dict[str, Any]] = []

    def reset(self) -> None:
        """Reset cognitive state for new task."""
        self.state = CognitiveState()

    def set_goal(self, goal: str) -> None:
        """Set the current high-level goal."""
        self.state.current_goal = goal
        self.state.thinking_mode = self._determine_thinking_mode(goal)
        logger.info(f"Set goal: {goal} (mode: {self.state.thinking_mode.value})")

    def _determine_thinking_mode(self, goal: str) -> ThinkingMode:
        """Determine appropriate thinking mode based on goal complexity."""
        # Simple heuristics for now - can be enhanced with ML
        complexity_indicators = [
            "analyze",
            "research",
            "investigate",
            "plan",
            "compare",
            "evaluate",
            "design",
            "create",
            "build",
            "implement",
            "debug",
            "troubleshoot",
            "multiple",
            "several",
            "all",
            "each",
        ]

        goal_lower = goal.lower()
        complexity_score = sum(1 for word in complexity_indicators if word in goal_lower)

        if complexity_score >= 3:
            return ThinkingMode.DELIBERATE
        elif complexity_score >= 1:
            return ThinkingMode.REACTIVE
        else:
            return ThinkingMode.REACTIVE

    def should_reason_first(self) -> bool:
        """Determine if we should do explicit reasoning before acting."""
        return self.state.thinking_mode == ThinkingMode.DELIBERATE

    def generate_reasoning_prompt(self, request: str, context: str = "") -> str:
        """Generate prompt for LLM reasoning phase."""
        return self.REASONING_PROMPT.format(request=request, context=context)

    def process_reasoning_response(self, response: str) -> dict[str, Any] | None:
        """Process LLM reasoning response and update cognitive state."""
        try:
            # Parse JSON from response
            json_text = response.strip()
            if json_text.startswith("```"):
                lines = json_text.split("\n")
                json_text = "\n".join(lines[1:-1])

            reasoning = json.loads(json_text)

            # Update cognitive state
            self.state.sub_goals = reasoning.get("sub_goals", [])
            self.state.active_hypotheses = reasoning.get("hypotheses", [])
            self.state.uncertainties = reasoning.get("information_needed", [])

            # Set confidence
            confidence_str = reasoning.get("confidence", "medium")
            self.state.confidence = Confidence(confidence_str)

            # Create thought chain
            import uuid

            self.state.current_thought_chain = ThoughtChain(
                id=str(uuid.uuid4()),
                goal=self.state.current_goal or reasoning.get("understanding", ""),
                hypotheses=self.state.active_hypotheses,
            )
            self.state.current_thought_chain.add_step(
                step_type="understanding",
                content=reasoning.get("understanding", ""),
                confidence=self.state.confidence,
            )
            self.state.current_thought_chain.add_step(
                step_type="approach",
                content=reasoning.get("approach", ""),
            )

            logger.info(
                f"Reasoning complete: {len(self.state.sub_goals)} sub-goals, "
                f"{len(self.state.active_hypotheses)} hypotheses, "
                f"confidence: {self.state.confidence.value}"
            )

            return reasoning

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse reasoning response: {e}")
            return None

    def generate_reflection_prompt(
        self,
        action: str,
        expected: str,
        actual: str,
    ) -> str:
        """Generate prompt for LLM reflection phase."""
        return self.REFLECTION_PROMPT.format(
            action=action,
            expected=expected,
            actual=actual,
        )

    def process_reflection_response(
        self,
        response: str,
        tool_name: str,
        expected: str,
        actual: str,
    ) -> ReflectionResult:
        """Process LLM reflection response and return structured result."""
        try:
            # Parse JSON from response
            json_text = response.strip()
            if json_text.startswith("```"):
                lines = json_text.split("\n")
                json_text = "\n".join(lines[1:-1])

            reflection = json.loads(json_text)

            result = ReflectionResult(
                tool_name=tool_name,
                expected_outcome=expected,
                actual_outcome=actual,
                success=reflection.get("success", True),
                insight=reflection.get("insight", ""),
                should_retry=reflection.get("should_retry", False),
                alternative_approach=reflection.get("alternative_approach"),
                confidence_delta=reflection.get("confidence_adjustment", 0),
            )

            # Store reflection
            self.state.reflections.append(result)

            # Learn pattern if provided
            pattern = reflection.get("pattern_learned")
            if pattern:
                self._learn_pattern(tool_name, pattern)

            # Update confidence
            self._adjust_confidence(result.confidence_delta)

            # Add to thought chain if active
            if self.state.current_thought_chain:
                self.state.current_thought_chain.add_step(
                    step_type="reflection",
                    content=result.insight,
                    evidence=[f"Tool: {tool_name}", f"Success: {result.success}"],
                )

            logger.info(
                f"Reflection: {tool_name} - {'success' if result.success else 'failed'} "
                f"(insight: {result.insight[:50]}...)"
            )

            return result

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse reflection response: {e}")
            # Return default reflection
            return ReflectionResult(
                tool_name=tool_name,
                expected_outcome=expected,
                actual_outcome=actual,
                success="error" not in actual.lower(),
                insight="Unable to parse reflection",
            )

    def _learn_pattern(self, tool_name: str, pattern: str) -> None:
        """Learn a pattern from experience."""
        learned = {
            "tool": tool_name,
            "pattern": pattern,
            "learned_at": datetime.now().isoformat(),
            "times_useful": 0,
        }
        self.state.learned_patterns.append(learned)
        self._pattern_cache.append(learned)
        logger.info(f"Learned pattern: {pattern}")

    def _adjust_confidence(self, delta: int) -> None:
        """Adjust confidence based on reflection."""
        # Map confidence to numeric value
        confidence_map = {
            Confidence.UNCERTAIN: 25,
            Confidence.LOW: 40,
            Confidence.MEDIUM: 65,
            Confidence.HIGH: 85,
        }

        current_value = confidence_map[self.state.confidence]
        new_value = max(0, min(100, current_value + delta))

        # Map back to enum
        if new_value >= 80:
            self.state.confidence = Confidence.HIGH
        elif new_value >= 50:
            self.state.confidence = Confidence.MEDIUM
        elif new_value >= 30:
            self.state.confidence = Confidence.LOW
        else:
            self.state.confidence = Confidence.UNCERTAIN

    def get_relevant_patterns(self, tool_name: str) -> list[str]:
        """Get learned patterns relevant to a tool."""
        return [p["pattern"] for p in self._pattern_cache if p["tool"] == tool_name or p["tool"] == "*"]

    def confirm_hypothesis(self, hypothesis: str) -> None:
        """Mark a hypothesis as confirmed."""
        if hypothesis in self.state.active_hypotheses:
            self.state.active_hypotheses.remove(hypothesis)
            self.state.confirmed_facts.append(hypothesis)
            logger.debug(f"Confirmed hypothesis: {hypothesis}")

    def reject_hypothesis(self, hypothesis: str, reason: str) -> None:
        """Reject a hypothesis with reason."""
        if hypothesis in self.state.active_hypotheses:
            self.state.active_hypotheses.remove(hypothesis)
            self.state.uncertainties.append(f"Rejected: {hypothesis} - {reason}")
            logger.debug(f"Rejected hypothesis: {hypothesis} ({reason})")

    def get_cognitive_summary(self) -> str:
        """Get a summary of current cognitive state for context injection."""
        parts = []

        if self.state.current_goal:
            parts.append(f"**Current Goal:** {self.state.current_goal}")

        if self.state.sub_goals:
            parts.append(f"**Sub-goals:** {', '.join(self.state.sub_goals[:3])}")

        if self.state.confirmed_facts:
            parts.append(f"**Known Facts:** {', '.join(self.state.confirmed_facts[:3])}")

        if self.state.active_hypotheses:
            parts.append(f"**Hypotheses to verify:** {', '.join(self.state.active_hypotheses[:2])}")

        if self.state.uncertainties:
            parts.append(f"**Uncertainties:** {', '.join(self.state.uncertainties[:2])}")

        parts.append(f"**Confidence:** {self.state.confidence.value}")

        # Include recent reflections if any
        if self.state.reflections:
            recent = self.state.reflections[-2:]
            insights = [r.insight for r in recent if r.insight]
            if insights:
                parts.append(f"**Recent insights:** {'; '.join(insights)}")

        return "\n".join(parts)

    def should_reflect_on_result(self, tool_result: dict[str, Any]) -> bool:
        """Determine if we should reflect on this tool result."""
        # Always reflect in deliberate mode
        if self.state.thinking_mode == ThinkingMode.DELIBERATE:
            return True

        # Reflect on errors
        if tool_result.get("is_error"):
            return True

        # Reflect if confidence is low
        if self.state.confidence in (Confidence.LOW, Confidence.UNCERTAIN):
            return True

        # Reflect periodically (every 3 tool calls)
        if len(self.state.reflections) % 3 == 0:
            return True

        return False

    def get_state_dict(self) -> dict[str, Any]:
        """Get cognitive state as dictionary for persistence."""
        return {
            "current_goal": self.state.current_goal,
            "sub_goals": self.state.sub_goals,
            "active_hypotheses": self.state.active_hypotheses,
            "confirmed_facts": self.state.confirmed_facts,
            "uncertainties": self.state.uncertainties,
            "confidence": self.state.confidence.value,
            "thinking_mode": self.state.thinking_mode.value,
            "reflections": [
                {
                    "tool": r.tool_name,
                    "success": r.success,
                    "insight": r.insight,
                }
                for r in self.state.reflections
            ],
            "thought_chain": self.state.current_thought_chain.to_dict() if self.state.current_thought_chain else None,
        }

    def restore_state(self, state_dict: dict[str, Any]) -> None:
        """Restore cognitive state from dictionary."""
        self.state.current_goal = state_dict.get("current_goal")
        self.state.sub_goals = state_dict.get("sub_goals", [])
        self.state.active_hypotheses = state_dict.get("active_hypotheses", [])
        self.state.confirmed_facts = state_dict.get("confirmed_facts", [])
        self.state.uncertainties = state_dict.get("uncertainties", [])

        confidence_str = state_dict.get("confidence", "medium")
        self.state.confidence = Confidence(confidence_str)

        mode_str = state_dict.get("thinking_mode", "reactive")
        self.state.thinking_mode = ThinkingMode(mode_str)
