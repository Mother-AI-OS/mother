"""Tests for the cognitive reasoning module."""

import json
import pytest
from datetime import datetime

from mother.agent.cognitive import (
    CognitiveEngine,
    CognitiveState,
    Confidence,
    ReflectionResult,
    ThinkingMode,
    ThoughtChain,
)


class TestConfidence:
    """Tests for Confidence enum."""

    def test_confidence_values(self):
        """Test confidence level values."""
        assert Confidence.HIGH.value == "high"
        assert Confidence.MEDIUM.value == "medium"
        assert Confidence.LOW.value == "low"
        assert Confidence.UNCERTAIN.value == "uncertain"


class TestThinkingMode:
    """Tests for ThinkingMode enum."""

    def test_thinking_mode_values(self):
        """Test thinking mode values."""
        assert ThinkingMode.REACTIVE.value == "reactive"
        assert ThinkingMode.DELIBERATE.value == "deliberate"
        assert ThinkingMode.REFLECTIVE.value == "reflective"


class TestThoughtChain:
    """Tests for ThoughtChain dataclass."""

    def test_creation(self):
        """Test thought chain creation."""
        chain = ThoughtChain(id="chain-1", goal="Test goal")

        assert chain.id == "chain-1"
        assert chain.goal == "Test goal"
        assert chain.steps == []
        assert chain.hypotheses == []
        assert chain.conclusions == []
        assert chain.confidence == Confidence.MEDIUM

    def test_add_step(self):
        """Test adding reasoning steps."""
        chain = ThoughtChain(id="chain-1", goal="Test goal")

        chain.add_step(
            step_type="understanding",
            content="Understood the problem",
            evidence=["fact1", "fact2"],
            confidence=Confidence.HIGH,
        )

        assert len(chain.steps) == 1
        assert chain.steps[0]["type"] == "understanding"
        assert chain.steps[0]["content"] == "Understood the problem"
        assert chain.steps[0]["evidence"] == ["fact1", "fact2"]
        assert chain.steps[0]["confidence"] == "high"

    def test_to_dict(self):
        """Test serialization to dictionary."""
        chain = ThoughtChain(
            id="chain-1",
            goal="Test goal",
            hypotheses=["hyp1"],
            conclusions=["conc1"],
        )
        chain.add_step(step_type="test", content="test content")

        result = chain.to_dict()

        assert result["id"] == "chain-1"
        assert result["goal"] == "Test goal"
        assert result["hypotheses"] == ["hyp1"]
        assert result["conclusions"] == ["conc1"]
        assert len(result["steps"]) == 1


class TestReflectionResult:
    """Tests for ReflectionResult dataclass."""

    def test_creation(self):
        """Test reflection result creation."""
        result = ReflectionResult(
            tool_name="test_tool",
            expected_outcome="success",
            actual_outcome="failure",
            success=False,
            insight="The tool failed due to missing input",
            should_retry=True,
            alternative_approach="Try different parameters",
            confidence_delta=-20,
        )

        assert result.tool_name == "test_tool"
        assert result.success is False
        assert result.insight == "The tool failed due to missing input"
        assert result.should_retry is True
        assert result.alternative_approach == "Try different parameters"
        assert result.confidence_delta == -20


class TestCognitiveState:
    """Tests for CognitiveState dataclass."""

    def test_default_state(self):
        """Test default cognitive state."""
        state = CognitiveState()

        assert state.current_goal is None
        assert state.sub_goals == []
        assert state.active_hypotheses == []
        assert state.confirmed_facts == []
        assert state.uncertainties == []
        assert state.current_thought_chain is None
        assert state.confidence == Confidence.MEDIUM
        assert state.thinking_mode == ThinkingMode.REACTIVE


class TestCognitiveEngine:
    """Tests for CognitiveEngine."""

    def test_initialization(self):
        """Test cognitive engine initialization."""
        engine = CognitiveEngine()

        assert engine.state is not None
        assert engine.state.confidence == Confidence.MEDIUM

    def test_reset(self):
        """Test resetting cognitive state."""
        engine = CognitiveEngine()
        engine.state.current_goal = "Test goal"
        engine.state.sub_goals = ["sub1", "sub2"]

        engine.reset()

        assert engine.state.current_goal is None
        assert engine.state.sub_goals == []

    def test_set_goal(self):
        """Test setting a goal."""
        engine = CognitiveEngine()
        engine.set_goal("Analyze the file structure")

        assert engine.state.current_goal == "Analyze the file structure"

    def test_determine_thinking_mode_simple(self):
        """Test thinking mode for simple goals."""
        engine = CognitiveEngine()
        engine.set_goal("Hello")

        assert engine.state.thinking_mode == ThinkingMode.REACTIVE

    def test_determine_thinking_mode_complex(self):
        """Test thinking mode for complex goals."""
        engine = CognitiveEngine()
        engine.set_goal("Analyze and evaluate multiple database designs")

        assert engine.state.thinking_mode == ThinkingMode.DELIBERATE

    def test_should_reason_first_reactive(self):
        """Test should_reason_first for reactive mode."""
        engine = CognitiveEngine()
        engine.state.thinking_mode = ThinkingMode.REACTIVE

        assert engine.should_reason_first() is False

    def test_should_reason_first_deliberate(self):
        """Test should_reason_first for deliberate mode."""
        engine = CognitiveEngine()
        engine.state.thinking_mode = ThinkingMode.DELIBERATE

        assert engine.should_reason_first() is True

    def test_generate_reasoning_prompt(self):
        """Test generating reasoning prompt."""
        engine = CognitiveEngine()
        prompt = engine.generate_reasoning_prompt("Test request", "Test context")

        assert "Test request" in prompt
        assert "Test context" in prompt
        assert "JSON" in prompt

    def test_process_reasoning_response(self):
        """Test processing reasoning response."""
        engine = CognitiveEngine()
        engine.set_goal("Test goal")

        response = json.dumps({
            "understanding": "Understood the problem",
            "sub_goals": ["goal1", "goal2"],
            "hypotheses": ["hyp1"],
            "information_needed": ["info1"],
            "approach": "Step by step",
            "potential_issues": ["issue1"],
            "confidence": "high",
        })

        result = engine.process_reasoning_response(response)

        assert result is not None
        assert engine.state.sub_goals == ["goal1", "goal2"]
        assert engine.state.active_hypotheses == ["hyp1"]
        assert engine.state.uncertainties == ["info1"]
        assert engine.state.confidence == Confidence.HIGH

    def test_process_reasoning_response_invalid_json(self):
        """Test processing invalid reasoning response."""
        engine = CognitiveEngine()
        result = engine.process_reasoning_response("invalid json")

        assert result is None

    def test_generate_reflection_prompt(self):
        """Test generating reflection prompt."""
        engine = CognitiveEngine()
        prompt = engine.generate_reflection_prompt(
            action="test action",
            expected="success",
            actual="failure",
        )

        assert "test action" in prompt
        assert "success" in prompt
        assert "failure" in prompt
        assert "JSON" in prompt

    def test_process_reflection_response(self):
        """Test processing reflection response."""
        engine = CognitiveEngine()

        response = json.dumps({
            "success": False,
            "insight": "Tool failed due to invalid input",
            "should_retry": True,
            "alternative_approach": "Try different format",
            "confidence_adjustment": -15,
            "pattern_learned": "Always validate input format",
        })

        result = engine.process_reflection_response(
            response=response,
            tool_name="test_tool",
            expected="success",
            actual="failure",
        )

        assert result.success is False
        assert result.insight == "Tool failed due to invalid input"
        assert result.should_retry is True
        assert result.alternative_approach == "Try different format"
        assert result.confidence_delta == -15

    def test_adjust_confidence_increase(self):
        """Test increasing confidence."""
        engine = CognitiveEngine()
        engine.state.confidence = Confidence.MEDIUM

        engine._adjust_confidence(30)

        assert engine.state.confidence == Confidence.HIGH

    def test_adjust_confidence_decrease(self):
        """Test decreasing confidence."""
        engine = CognitiveEngine()
        engine.state.confidence = Confidence.MEDIUM

        engine._adjust_confidence(-40)

        assert engine.state.confidence == Confidence.UNCERTAIN

    def test_confirm_hypothesis(self):
        """Test confirming a hypothesis."""
        engine = CognitiveEngine()
        engine.state.active_hypotheses = ["hyp1", "hyp2"]

        engine.confirm_hypothesis("hyp1")

        assert "hyp1" not in engine.state.active_hypotheses
        assert "hyp1" in engine.state.confirmed_facts

    def test_reject_hypothesis(self):
        """Test rejecting a hypothesis."""
        engine = CognitiveEngine()
        engine.state.active_hypotheses = ["hyp1", "hyp2"]

        engine.reject_hypothesis("hyp1", "evidence was wrong")

        assert "hyp1" not in engine.state.active_hypotheses
        assert any("Rejected: hyp1" in u for u in engine.state.uncertainties)

    def test_get_cognitive_summary(self):
        """Test getting cognitive summary."""
        engine = CognitiveEngine()
        engine.state.current_goal = "Test goal"
        engine.state.sub_goals = ["sub1"]
        engine.state.confirmed_facts = ["fact1"]
        engine.state.confidence = Confidence.HIGH

        summary = engine.get_cognitive_summary()

        assert "Test goal" in summary
        assert "sub1" in summary
        assert "fact1" in summary
        assert "high" in summary

    def test_should_reflect_on_result_error(self):
        """Test should_reflect_on_result for error results."""
        engine = CognitiveEngine()

        result = {"is_error": True, "content": "Error message"}

        assert engine.should_reflect_on_result(result) is True

    def test_should_reflect_on_result_low_confidence(self):
        """Test should_reflect_on_result with low confidence."""
        engine = CognitiveEngine()
        engine.state.confidence = Confidence.LOW

        result = {"is_error": False, "content": "Success"}

        assert engine.should_reflect_on_result(result) is True

    def test_should_reflect_on_result_deliberate_mode(self):
        """Test should_reflect_on_result in deliberate mode."""
        engine = CognitiveEngine()
        engine.state.thinking_mode = ThinkingMode.DELIBERATE

        result = {"is_error": False, "content": "Success"}

        assert engine.should_reflect_on_result(result) is True

    def test_get_state_dict(self):
        """Test getting state as dictionary."""
        engine = CognitiveEngine()
        engine.state.current_goal = "Test goal"
        engine.state.sub_goals = ["sub1"]
        engine.state.confidence = Confidence.HIGH

        state_dict = engine.get_state_dict()

        assert state_dict["current_goal"] == "Test goal"
        assert state_dict["sub_goals"] == ["sub1"]
        assert state_dict["confidence"] == "high"

    def test_restore_state(self):
        """Test restoring state from dictionary."""
        engine = CognitiveEngine()

        state_dict = {
            "current_goal": "Restored goal",
            "sub_goals": ["sub1", "sub2"],
            "active_hypotheses": ["hyp1"],
            "confirmed_facts": ["fact1"],
            "uncertainties": ["unc1"],
            "confidence": "low",
            "thinking_mode": "deliberate",
        }

        engine.restore_state(state_dict)

        assert engine.state.current_goal == "Restored goal"
        assert engine.state.sub_goals == ["sub1", "sub2"]
        assert engine.state.active_hypotheses == ["hyp1"]
        assert engine.state.confirmed_facts == ["fact1"]
        assert engine.state.uncertainties == ["unc1"]
        assert engine.state.confidence == Confidence.LOW
        assert engine.state.thinking_mode == ThinkingMode.DELIBERATE

    def test_learn_pattern(self):
        """Test learning patterns from experience."""
        engine = CognitiveEngine()

        engine._learn_pattern("test_tool", "Always validate input")

        assert len(engine._pattern_cache) == 1
        assert engine._pattern_cache[0]["pattern"] == "Always validate input"
        assert engine._pattern_cache[0]["tool"] == "test_tool"

    def test_get_relevant_patterns(self):
        """Test getting relevant patterns for a tool."""
        engine = CognitiveEngine()
        engine._learn_pattern("test_tool", "Pattern 1")
        engine._learn_pattern("other_tool", "Pattern 2")
        engine._learn_pattern("*", "Universal pattern")

        patterns = engine.get_relevant_patterns("test_tool")

        assert "Pattern 1" in patterns
        assert "Universal pattern" in patterns
        assert "Pattern 2" not in patterns
