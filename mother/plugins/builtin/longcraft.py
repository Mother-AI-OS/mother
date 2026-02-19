"""LongCraft (Persona Creator Machine) plugin for Mother AI OS.

Provides persona-driven content generation capabilities:
- Persona (Voice Pack) management
- Content generation at SHORT/MEDIUM/LONG regimes
- Book-length orchestration (outline, chapters, lint)
- Content export (Markdown, DOCX)
- Fine-tuning pipeline (ingest, build datasets, train)
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..base import PluginBase, PluginResult
from ..manifest import (
    CapabilitySpec,
    ExecutionSpec,
    ExecutionType,
    ParameterSpec,
    ParameterType,
    PluginManifest,
    PluginMetadata,
    PythonExecutionSpec,
)


def _create_manifest() -> PluginManifest:
    """Create the longcraft plugin manifest."""
    return PluginManifest(
        schema_version="1.0",
        plugin=PluginMetadata(
            name="longcraft",
            version="1.0.0",
            description="Persona-driven content generation at multiple length regimes with fine-tuning",
            author="Mother",
            license="MIT",
        ),
        capabilities=[
            # ── Persona Management ──────────────────────────────────────
            CapabilitySpec(
                name="persona_list",
                description="List all available personas (Voice Packs).",
                parameters=[],
            ),
            CapabilitySpec(
                name="persona_show",
                description="Show persona details and voice configuration.",
                parameters=[
                    ParameterSpec(
                        name="persona_id",
                        type=ParameterType.STRING,
                        description="Persona ID",
                        required=True,
                    ),
                ],
            ),
            CapabilitySpec(
                name="persona_init",
                description="Create a new persona (Voice Pack).",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="persona_id",
                        type=ParameterType.STRING,
                        description="Unique slug for the persona",
                        required=True,
                    ),
                    ParameterSpec(
                        name="name",
                        type=ParameterType.STRING,
                        description="Display name",
                        required=True,
                    ),
                    ParameterSpec(
                        name="tone",
                        type=ParameterType.STRING,
                        description="Comma-separated tone adjectives (default: professional, clear)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="language",
                        type=ParameterType.STRING,
                        description="Primary language (default: en)",
                        required=False,
                    ),
                ],
            ),
            # ── Content Generation ──────────────────────────────────────
            CapabilitySpec(
                name="write",
                description="Generate content in SHORT (~200 words), MEDIUM (~1500 words), or LONG (~5000 words) regimes.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="persona",
                        type=ParameterType.STRING,
                        description="Persona ID to write as",
                        required=True,
                    ),
                    ParameterSpec(
                        name="topic",
                        type=ParameterType.STRING,
                        description="Topic or prompt",
                        required=True,
                    ),
                    ParameterSpec(
                        name="regime",
                        type=ParameterType.STRING,
                        description="Length regime: SHORT, MEDIUM, or LONG (default: MEDIUM)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="words",
                        type=ParameterType.STRING,
                        description="Custom word range, e.g. '180:220'",
                        required=False,
                    ),
                    ParameterSpec(
                        name="audience",
                        type=ParameterType.STRING,
                        description="Target audience (default: general)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="purpose",
                        type=ParameterType.STRING,
                        description="Content purpose (default: inform)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="channel",
                        type=ParameterType.STRING,
                        description="Distribution channel",
                        required=False,
                    ),
                    ParameterSpec(
                        name="language",
                        type=ParameterType.STRING,
                        description="Output language (default: en)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="backend",
                        type=ParameterType.STRING,
                        description="Generation backend (default: openai)",
                        required=False,
                    ),
                ],
            ),
            # ── Book Orchestration ──────────────────────────────────────
            CapabilitySpec(
                name="book_init",
                description="Create a new book project.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="persona",
                        type=ParameterType.STRING,
                        description="Persona ID",
                        required=True,
                    ),
                    ParameterSpec(
                        name="title",
                        type=ParameterType.STRING,
                        description="Book title",
                        required=True,
                    ),
                    ParameterSpec(
                        name="out",
                        type=ParameterType.STRING,
                        description="Book project directory (default: out/book)",
                        required=False,
                    ),
                ],
            ),
            CapabilitySpec(
                name="book_outline",
                description="Generate a book outline from a premise.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="prompt",
                        type=ParameterType.STRING,
                        description="Premise or outline prompt",
                        required=True,
                    ),
                    ParameterSpec(
                        name="bible",
                        type=ParameterType.STRING,
                        description="Path to bible.json",
                        required=True,
                    ),
                    ParameterSpec(
                        name="out",
                        type=ParameterType.STRING,
                        description="Output path for outline",
                        required=False,
                    ),
                    ParameterSpec(
                        name="backend",
                        type=ParameterType.STRING,
                        description="Generation backend (default: openai)",
                        required=False,
                    ),
                ],
            ),
            CapabilitySpec(
                name="book_write",
                description="Generate chapter drafts from a book outline.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="outline",
                        type=ParameterType.STRING,
                        description="Path to outline.json",
                        required=True,
                    ),
                    ParameterSpec(
                        name="bible",
                        type=ParameterType.STRING,
                        description="Path to bible.json",
                        required=True,
                    ),
                    ParameterSpec(
                        name="out",
                        type=ParameterType.STRING,
                        description="Output directory for chapter drafts (default: out/book/draft)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="backend",
                        type=ParameterType.STRING,
                        description="Generation backend (default: openai)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="chapter",
                        type=ParameterType.INTEGER,
                        description="Generate only this chapter number",
                        required=False,
                    ),
                ],
            ),
            CapabilitySpec(
                name="book_lint",
                description="Analyze book quality and continuity.",
                parameters=[
                    ParameterSpec(
                        name="book",
                        type=ParameterType.STRING,
                        description="Directory with chapter draft files",
                        required=True,
                    ),
                    ParameterSpec(
                        name="bible",
                        type=ParameterType.STRING,
                        description="Path to bible.json for continuity checks",
                        required=False,
                    ),
                ],
            ),
            # ── Export ──────────────────────────────────────────────────
            CapabilitySpec(
                name="export",
                description="Export generated content to Markdown or DOCX format.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="input_dir",
                        type=ParameterType.STRING,
                        description="Input directory with draft files",
                        required=True,
                    ),
                    ParameterSpec(
                        name="format",
                        type=ParameterType.STRING,
                        description="Export format: md or docx (default: md)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="out",
                        type=ParameterType.STRING,
                        description="Output file path",
                        required=False,
                    ),
                ],
            ),
            # ── Training Pipeline ───────────────────────────────────────
            CapabilitySpec(
                name="train_ingest",
                description="Ingest PDF source material for training data preparation.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="source",
                        type=ParameterType.STRING,
                        description="PDF file or directory of PDFs to ingest",
                        required=True,
                    ),
                    ParameterSpec(
                        name="out",
                        type=ParameterType.STRING,
                        description="Output directory for cleaned text (default: data/raw)",
                        required=False,
                    ),
                ],
            ),
            CapabilitySpec(
                name="train_build_sft",
                description="Build supervised fine-tuning dataset from ingested text.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="persona",
                        type=ParameterType.STRING,
                        description="Persona ID",
                        required=True,
                    ),
                    ParameterSpec(
                        name="input_dir",
                        type=ParameterType.STRING,
                        description="Directory with chunk JSONL files (default: data/raw)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="out",
                        type=ParameterType.STRING,
                        description="Output SFT JSONL path (default: data/sft.jsonl)",
                        required=False,
                    ),
                ],
            ),
            CapabilitySpec(
                name="train_build_dpo",
                description="Build DPO preference pairs from SFT dataset.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="persona",
                        type=ParameterType.STRING,
                        description="Persona ID",
                        required=True,
                    ),
                    ParameterSpec(
                        name="sft",
                        type=ParameterType.STRING,
                        description="SFT JSONL to derive DPO from (default: data/sft.jsonl)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="out",
                        type=ParameterType.STRING,
                        description="Output DPO JSONL path (default: data/dpo.jsonl)",
                        required=False,
                    ),
                ],
            ),
            CapabilitySpec(
                name="train_sft",
                description="Launch supervised fine-tuning job on OpenAI.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="backend",
                        type=ParameterType.STRING,
                        description="Training backend: openai or local (default: openai)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="dataset",
                        type=ParameterType.STRING,
                        description="SFT JSONL dataset path (default: data/sft.jsonl)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="base_model",
                        type=ParameterType.STRING,
                        description="Base model to fine-tune (default: gpt-4o-mini)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="suffix",
                        type=ParameterType.STRING,
                        description="Model suffix (default: persona-v1)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="epochs",
                        type=ParameterType.INTEGER,
                        description="Number of training epochs (default: 3)",
                        required=False,
                    ),
                ],
            ),
        ],
        execution=ExecutionSpec(
            type=ExecutionType.PYTHON,
            python=PythonExecutionSpec(
                module="mother.plugins.builtin.longcraft",
                **{"class": "LongcraftPlugin"},
            ),
        ),
        permissions=[
            "filesystem:read",
            "filesystem:write",
            "network:https",
        ],
    )


class LongcraftPlugin(PluginBase):
    """Persona-driven content generation plugin."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the longcraft plugin."""
        super().__init__(_create_manifest(), config)
        self._bin = self._find_binary()
        self._config = config or {}

    def _find_binary(self) -> str | None:
        """Find persona-cli binary."""
        locations = [
            Path.home() / ".local" / "bin" / "persona-cli",
            Path.home() / "projects" / "longcraft" / ".venv" / "bin" / "persona-cli",
            shutil.which("persona-cli"),
        ]
        for loc in locations:
            if loc and Path(str(loc)).exists():
                return str(loc)
        return None

    def _is_configured(self) -> bool:
        """Check if persona-cli is configured."""
        return self._bin is not None

    async def execute(self, capability: str, params: dict[str, Any]) -> PluginResult:
        """Execute a longcraft capability."""
        handlers = {
            "persona_list": self._persona_list,
            "persona_show": self._persona_show,
            "persona_init": self._persona_init,
            "write": self._write,
            "book_init": self._book_init,
            "book_outline": self._book_outline,
            "book_write": self._book_write,
            "book_lint": self._book_lint,
            "export": self._export,
            "train_ingest": self._train_ingest,
            "train_build_sft": self._train_build_sft,
            "train_build_dpo": self._train_build_dpo,
            "train_sft": self._train_sft,
        }

        handler = handlers.get(capability)
        if not handler:
            return PluginResult.error_result(
                f"Unknown capability: {capability}",
                code="UNKNOWN_CAPABILITY",
            )

        if not self._is_configured():
            return PluginResult.error_result(
                "persona-cli is not installed. Install longcraft or check path.",
                code="NOT_CONFIGURED",
            )

        try:
            return await handler(**params)
        except Exception as e:
            return PluginResult.error_result(
                f"LongCraft operation failed: {e}",
                code="LONGCRAFT_ERROR",
            )

    async def _run_cli(self, *args: str, timeout: int = 120) -> tuple[str, str, int]:
        """Run persona-cli command."""
        cmd = [self._bin, *args]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
            return (
                stdout.decode("utf-8", errors="replace"),
                stderr.decode("utf-8", errors="replace"),
                proc.returncode or 0,
            )
        except TimeoutError:
            return "", "Operation timed out", 1

    # ── Persona Management ──────────────────────────────────────────────

    async def _persona_list(self) -> PluginResult:
        """List personas."""
        stdout, stderr, code = await self._run_cli("persona", "list")
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="PERSONA_LIST_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Personas",
        )

    async def _persona_show(self, persona_id: str) -> PluginResult:
        """Show persona details."""
        stdout, stderr, code = await self._run_cli("persona", "show", persona_id)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="PERSONA_SHOW_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Persona: {persona_id}",
        )

    async def _persona_init(
        self,
        persona_id: str,
        name: str,
        tone: str | None = None,
        language: str | None = None,
    ) -> PluginResult:
        """Create a new persona."""
        args = ["persona", "init", persona_id, "--name", name]
        if tone:
            args.extend(["--tone", tone])
        if language:
            args.extend(["--language", language])

        stdout, stderr, code = await self._run_cli(*args)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="PERSONA_INIT_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Created persona: {persona_id}",
        )

    # ── Content Generation ──────────────────────────────────────────────

    async def _write(
        self,
        persona: str,
        topic: str,
        regime: str | None = None,
        words: str | None = None,
        audience: str | None = None,
        purpose: str | None = None,
        channel: str | None = None,
        language: str | None = None,
        backend: str | None = None,
    ) -> PluginResult:
        """Generate content."""
        args = ["write", "--persona", persona, "--topic", topic]
        if regime:
            args.extend(["--regime", regime])
        if words:
            args.extend(["--words", words])
        if audience:
            args.extend(["--audience", audience])
        if purpose:
            args.extend(["--purpose", purpose])
        if channel:
            args.extend(["--channel", channel])
        if language:
            args.extend(["--language", language])
        if backend:
            args.extend(["--backend", backend])

        stdout, stderr, code = await self._run_cli(*args, timeout=300)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="WRITE_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Generated {regime or 'MEDIUM'} content: {topic}",
        )

    # ── Book Orchestration ──────────────────────────────────────────────

    async def _book_init(
        self,
        persona: str,
        title: str,
        out: str | None = None,
    ) -> PluginResult:
        """Create book project."""
        args = ["book", "init", "--persona", persona, "--title", title]
        if out:
            args.extend(["--out", out])

        stdout, stderr, code = await self._run_cli(*args)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="BOOK_INIT_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Created book project: {title}",
        )

    async def _book_outline(
        self,
        prompt: str,
        bible: str,
        out: str | None = None,
        backend: str | None = None,
    ) -> PluginResult:
        """Generate book outline."""
        args = ["book", "outline", "--prompt", prompt, "--bible", bible]
        if out:
            args.extend(["--out", out])
        if backend:
            args.extend(["--backend", backend])

        stdout, stderr, code = await self._run_cli(*args, timeout=300)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="BOOK_OUTLINE_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Generated book outline",
        )

    async def _book_write(
        self,
        outline: str,
        bible: str,
        out: str | None = None,
        backend: str | None = None,
        chapter: int | None = None,
    ) -> PluginResult:
        """Generate chapter drafts."""
        args = ["book", "write", "--outline", outline, "--bible", bible]
        if out:
            args.extend(["--out", out])
        if backend:
            args.extend(["--backend", backend])
        if chapter is not None:
            args.extend(["--chapter", str(chapter)])

        stdout, stderr, code = await self._run_cli(*args, timeout=600)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="BOOK_WRITE_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Generated chapter{'s' if chapter is None else f' {chapter}'}",
        )

    async def _book_lint(
        self,
        book: str,
        bible: str | None = None,
    ) -> PluginResult:
        """Lint book quality."""
        args = ["book", "lint", "--book", book]
        if bible:
            args.extend(["--bible", bible])

        stdout, stderr, code = await self._run_cli(*args, timeout=180)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="BOOK_LINT_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Book lint report",
        )

    # ── Export ──────────────────────────────────────────────────────────

    async def _export(
        self,
        input_dir: str,
        format: str | None = None,
        out: str | None = None,
    ) -> PluginResult:
        """Export content."""
        args = ["export", "--in", input_dir]
        if format:
            args.extend(["--format", format])
        if out:
            args.extend(["--out", out])

        stdout, stderr, code = await self._run_cli(*args)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="EXPORT_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Exported to {format or 'md'}",
        )

    # ── Training Pipeline ───────────────────────────────────────────────

    async def _train_ingest(
        self,
        source: str,
        out: str | None = None,
    ) -> PluginResult:
        """Ingest PDFs for training."""
        args = ["train", "ingest", source]
        if out:
            args.extend(["--out", out])

        stdout, stderr, code = await self._run_cli(*args, timeout=300)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="TRAIN_INGEST_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Ingested training data",
        )

    async def _train_build_sft(
        self,
        persona: str,
        input_dir: str | None = None,
        out: str | None = None,
    ) -> PluginResult:
        """Build SFT dataset."""
        args = ["train", "build-sft", "--persona", persona]
        if input_dir:
            args.extend(["--in", input_dir])
        if out:
            args.extend(["--out", out])

        stdout, stderr, code = await self._run_cli(*args, timeout=300)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="TRAIN_BUILD_SFT_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Built SFT dataset",
        )

    async def _train_build_dpo(
        self,
        persona: str,
        sft: str | None = None,
        out: str | None = None,
    ) -> PluginResult:
        """Build DPO preference pairs."""
        args = ["train", "build-dpo", "--persona", persona]
        if sft:
            args.extend(["--sft", sft])
        if out:
            args.extend(["--out", out])

        stdout, stderr, code = await self._run_cli(*args, timeout=300)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="TRAIN_BUILD_DPO_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Built DPO dataset",
        )

    async def _train_sft(
        self,
        backend: str | None = None,
        dataset: str | None = None,
        base_model: str | None = None,
        suffix: str | None = None,
        epochs: int | None = None,
    ) -> PluginResult:
        """Launch fine-tuning job."""
        args = ["train", "sft"]
        if backend:
            args.extend(["--backend", backend])
        if dataset:
            args.extend(["--dataset", dataset])
        if base_model:
            args.extend(["--base-model", base_model])
        if suffix:
            args.extend(["--suffix", suffix])
        if epochs is not None:
            args.extend(["--epochs", str(epochs)])

        stdout, stderr, code = await self._run_cli(*args, timeout=120)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="TRAIN_SFT_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Fine-tuning job launched",
        )


__all__ = ["LongcraftPlugin"]
