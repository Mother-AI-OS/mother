"""ContentCraft plugin for Mother AI OS.

Provides AI-powered content creation and publishing capabilities:
- Content generation (blog, LinkedIn, YouTube)
- Draft management and approval workflow
- Publishing to multiple platforms
- Content series and batch generation
- Analytics and portfolio tracking
- Source management and voice profiles
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
    """Create the contentcraft plugin manifest."""
    return PluginManifest(
        schema_version="1.0",
        plugin=PluginMetadata(
            name="contentcraft",
            version="1.0.0",
            description="AI-powered content creation and multi-platform publishing",
            author="Mother",
            license="MIT",
        ),
        capabilities=[
            # ── Status & Overview ───────────────────────────────────────
            CapabilitySpec(
                name="status",
                description="Show system status and configuration.",
                parameters=[],
            ),
            CapabilitySpec(
                name="published",
                description="List published content with live URLs.",
                parameters=[
                    ParameterSpec(
                        name="platform",
                        type=ParameterType.STRING,
                        description="Filter by platform: all, linkedin, twitter, youtube, blog",
                        required=False,
                    ),
                    ParameterSpec(
                        name="brand",
                        type=ParameterType.STRING,
                        description="Filter by brand: lawkraft, hucke_sanker, morpheus_mark, mother_ai, uapk, quantum_trading, personal",
                        required=False,
                    ),
                    ParameterSpec(
                        name="limit",
                        type=ParameterType.INTEGER,
                        description="Maximum items to show",
                        required=False,
                    ),
                ],
            ),
            CapabilitySpec(
                name="portfolio_stats",
                description="Show portfolio statistics computed from database.",
                parameters=[
                    ParameterSpec(
                        name="days",
                        type=ParameterType.INTEGER,
                        description="Days to look back for documentation",
                        required=False,
                    ),
                ],
            ),
            CapabilitySpec(
                name="portfolio_projects",
                description="List projects with statistics.",
                parameters=[
                    ParameterSpec(
                        name="tier",
                        type=ParameterType.INTEGER,
                        description="Filter by tier (1=high, 2=medium, 3=basic)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="category",
                        type=ParameterType.STRING,
                        description="Filter by category",
                        required=False,
                    ),
                ],
            ),
            # ── Drafts ──────────────────────────────────────────────────
            CapabilitySpec(
                name="drafts_list",
                description="List content drafts with filters.",
                parameters=[
                    ParameterSpec(
                        name="status",
                        type=ParameterType.STRING,
                        description="Filter: all, draft, pending_review, approved, rejected, published, scheduled",
                        required=False,
                    ),
                    ParameterSpec(
                        name="platform",
                        type=ParameterType.STRING,
                        description="Filter: all, linkedin, twitter, youtube, blog",
                        required=False,
                    ),
                    ParameterSpec(
                        name="brand",
                        type=ParameterType.STRING,
                        description="Filter by brand",
                        required=False,
                    ),
                    ParameterSpec(
                        name="limit",
                        type=ParameterType.INTEGER,
                        description="Max items per page",
                        required=False,
                    ),
                ],
            ),
            CapabilitySpec(
                name="drafts_show",
                description="Show draft content details.",
                parameters=[
                    ParameterSpec(
                        name="content_id",
                        type=ParameterType.STRING,
                        description="Content ID or row number from list",
                        required=True,
                    ),
                ],
            ),
            CapabilitySpec(
                name="drafts_approve",
                description="Approve a draft for publishing.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="content_id",
                        type=ParameterType.STRING,
                        description="Draft content ID",
                        required=True,
                    ),
                    ParameterSpec(
                        name="notes",
                        type=ParameterType.STRING,
                        description="Approval notes",
                        required=False,
                    ),
                ],
            ),
            CapabilitySpec(
                name="drafts_reject",
                description="Reject a draft with reason.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="content_id",
                        type=ParameterType.STRING,
                        description="Draft content ID",
                        required=True,
                    ),
                    ParameterSpec(
                        name="reason",
                        type=ParameterType.STRING,
                        description="Rejection reason",
                        required=True,
                    ),
                ],
            ),
            CapabilitySpec(
                name="drafts_submit",
                description="Submit draft for review.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="content_id",
                        type=ParameterType.STRING,
                        description="Draft content ID or row number",
                        required=True,
                    ),
                ],
            ),
            CapabilitySpec(
                name="drafts_sync",
                description="Sync draft status from Google Drive folders.",
                confirmation_required=True,
                parameters=[],
            ),
            CapabilitySpec(
                name="drafts_export",
                description="Export draft to Google Drive for review.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="content_id",
                        type=ParameterType.STRING,
                        description="Draft content ID",
                        required=True,
                    ),
                ],
            ),
            CapabilitySpec(
                name="drafts_import",
                description="Import draft from Google Drive markdown file.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="filepath",
                        type=ParameterType.STRING,
                        description="Path to markdown file",
                        required=True,
                    ),
                ],
            ),
            # ── Content Generation ──────────────────────────────────────
            CapabilitySpec(
                name="generate",
                description="Generate new content with AI.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="type",
                        type=ParameterType.STRING,
                        description="Content type: linkedin, tweet, thread, blog, youtube",
                        required=True,
                    ),
                    ParameterSpec(
                        name="topic",
                        type=ParameterType.STRING,
                        description="Topic to generate about",
                        required=True,
                    ),
                    ParameterSpec(
                        name="brand",
                        type=ParameterType.STRING,
                        description="Brand identity",
                        required=False,
                    ),
                    ParameterSpec(
                        name="language",
                        type=ParameterType.STRING,
                        description="Language code (en/de)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="source_id",
                        type=ParameterType.STRING,
                        description="Generate from specific source item",
                        required=False,
                    ),
                    ParameterSpec(
                        name="dry_run",
                        type=ParameterType.BOOLEAN,
                        description="Preview without saving",
                        required=False,
                        default=False,
                    ),
                ],
            ),
            CapabilitySpec(
                name="quick_post",
                description="Generate blog + LinkedIn variants from a single idea.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="topic",
                        type=ParameterType.STRING,
                        description="Topic or idea for the post",
                        required=True,
                    ),
                    ParameterSpec(
                        name="brand",
                        type=ParameterType.STRING,
                        description="Brand: lawkraft, uapk, mother_ai, hucke_sanker, morpheus_mark, quantum_trading",
                        required=True,
                    ),
                    ParameterSpec(
                        name="persona",
                        type=ParameterType.STRING,
                        description="Persona (default: david_sanker)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="dry_run",
                        type=ParameterType.BOOLEAN,
                        description="Preview without saving",
                        required=False,
                        default=False,
                    ),
                ],
            ),
            CapabilitySpec(
                name="generate_variants",
                description="Generate LinkedIn abstracts and teasers from a published blog post.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="blog_id",
                        type=ParameterType.STRING,
                        description="Published blog content ID",
                        required=True,
                    ),
                    ParameterSpec(
                        name="blog_url",
                        type=ParameterType.STRING,
                        description="Published blog URL (auto-detected if not provided)",
                        required=False,
                    ),
                ],
            ),
            CapabilitySpec(
                name="regenerate",
                description="Regenerate content with feedback adjustments.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="content_id",
                        type=ParameterType.STRING,
                        description="Content ID to regenerate",
                        required=True,
                    ),
                    ParameterSpec(
                        name="feedback",
                        type=ParameterType.STRING,
                        description="Feedback for improvement",
                        required=True,
                    ),
                    ParameterSpec(
                        name="dry_run",
                        type=ParameterType.BOOLEAN,
                        description="Preview without saving",
                        required=False,
                        default=False,
                    ),
                ],
            ),
            CapabilitySpec(
                name="render",
                description="Render content to platform-specific output format.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="content_id",
                        type=ParameterType.STRING,
                        description="Content ID to render",
                        required=True,
                    ),
                ],
            ),
            # ── Publishing ──────────────────────────────────────────────
            CapabilitySpec(
                name="publish",
                description="Publish content to a platform.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="content_id",
                        type=ParameterType.STRING,
                        description="Content ID to publish",
                        required=True,
                    ),
                    ParameterSpec(
                        name="platform",
                        type=ParameterType.STRING,
                        description="Target platform: linkedin, twitter, youtube, blog",
                        required=True,
                    ),
                    ParameterSpec(
                        name="dry_run",
                        type=ParameterType.BOOLEAN,
                        description="Preview without publishing",
                        required=False,
                        default=True,
                    ),
                    ParameterSpec(
                        name="execute",
                        type=ParameterType.BOOLEAN,
                        description="Actually publish (overrides dry-run)",
                        required=False,
                        default=False,
                    ),
                ],
            ),
            CapabilitySpec(
                name="publish_both",
                description="Publish blog and LinkedIn together atomically.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="linkedin_id",
                        type=ParameterType.STRING,
                        description="LinkedIn content ID",
                        required=True,
                    ),
                    ParameterSpec(
                        name="blog_id",
                        type=ParameterType.STRING,
                        description="Blog content ID",
                        required=True,
                    ),
                    ParameterSpec(
                        name="persona",
                        type=ParameterType.STRING,
                        description="Persona to publish as",
                        required=False,
                    ),
                    ParameterSpec(
                        name="dry_run",
                        type=ParameterType.BOOLEAN,
                        description="Preview without publishing",
                        required=False,
                        default=True,
                    ),
                    ParameterSpec(
                        name="execute",
                        type=ParameterType.BOOLEAN,
                        description="Actually publish (overrides dry-run)",
                        required=False,
                        default=False,
                    ),
                ],
            ),
            CapabilitySpec(
                name="deploy",
                description="Deploy rendered blog content to remote site.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="content_id",
                        type=ParameterType.STRING,
                        description="Content ID to deploy",
                        required=True,
                    ),
                    ParameterSpec(
                        name="dry_run",
                        type=ParameterType.BOOLEAN,
                        description="Preview without deploying",
                        required=False,
                        default=True,
                    ),
                    ParameterSpec(
                        name="force",
                        type=ParameterType.BOOLEAN,
                        description="Overwrite existing post with same slug",
                        required=False,
                        default=False,
                    ),
                ],
            ),
            # ── Queue ───────────────────────────────────────────────────
            CapabilitySpec(
                name="queue_list",
                description="Show scheduled content in the publishing queue.",
                parameters=[
                    ParameterSpec(
                        name="status",
                        type=ParameterType.STRING,
                        description="Filter: all, pending, published, failed",
                        required=False,
                    ),
                    ParameterSpec(
                        name="platform",
                        type=ParameterType.STRING,
                        description="Filter: all, linkedin, twitter, youtube, blog",
                        required=False,
                    ),
                ],
            ),
            CapabilitySpec(
                name="queue_schedule",
                description="Schedule content for publishing at a specific time.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="content_id",
                        type=ParameterType.STRING,
                        description="Content ID to schedule",
                        required=True,
                    ),
                    ParameterSpec(
                        name="platform",
                        type=ParameterType.STRING,
                        description="Target platform",
                        required=True,
                    ),
                    ParameterSpec(
                        name="time",
                        type=ParameterType.STRING,
                        description="Schedule time: YYYY-MM-DD HH:MM",
                        required=True,
                    ),
                    ParameterSpec(
                        name="priority",
                        type=ParameterType.INTEGER,
                        description="Priority level 1-10",
                        required=False,
                    ),
                ],
            ),
            CapabilitySpec(
                name="queue_process",
                description="Process pending queue items (publish scheduled content).",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="max",
                        type=ParameterType.INTEGER,
                        description="Maximum items to process",
                        required=False,
                    ),
                    ParameterSpec(
                        name="dry_run",
                        type=ParameterType.BOOLEAN,
                        description="Preview without publishing",
                        required=False,
                        default=False,
                    ),
                ],
            ),
            # ── Series ──────────────────────────────────────────────────
            CapabilitySpec(
                name="series_list",
                description="List all content series plans.",
                parameters=[
                    ParameterSpec(
                        name="project",
                        type=ParameterType.STRING,
                        description="Filter by project",
                        required=False,
                    ),
                    ParameterSpec(
                        name="brand",
                        type=ParameterType.STRING,
                        description="Filter by brand",
                        required=False,
                    ),
                    ParameterSpec(
                        name="status",
                        type=ParameterType.STRING,
                        description="Filter by status",
                        required=False,
                    ),
                ],
            ),
            CapabilitySpec(
                name="series_show",
                description="Show series plan details.",
                parameters=[
                    ParameterSpec(
                        name="series_id",
                        type=ParameterType.STRING,
                        description="Series ID",
                        required=True,
                    ),
                ],
            ),
            CapabilitySpec(
                name="series_progress",
                description="Show series progress statistics.",
                parameters=[
                    ParameterSpec(
                        name="series_id",
                        type=ParameterType.STRING,
                        description="Series ID",
                        required=True,
                    ),
                ],
            ),
            CapabilitySpec(
                name="series_create",
                description="Create a 25-post content series plan for a project.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="project",
                        type=ParameterType.STRING,
                        description="Project name",
                        required=True,
                    ),
                    ParameterSpec(
                        name="brand",
                        type=ParameterType.STRING,
                        description="Brand: lawkraft, hucke_sanker, morpheus_mark, personal",
                        required=True,
                    ),
                    ParameterSpec(
                        name="persona",
                        type=ParameterType.STRING,
                        description="Persona: david_sanker, marijan_hucke",
                        required=True,
                    ),
                    ParameterSpec(
                        name="dry_run",
                        type=ParameterType.BOOLEAN,
                        description="Preview without saving",
                        required=False,
                        default=False,
                    ),
                ],
            ),
            CapabilitySpec(
                name="series_generate",
                description="Generate content from a series plan.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="series_id",
                        type=ParameterType.STRING,
                        description="Series ID",
                        required=True,
                    ),
                    ParameterSpec(
                        name="post",
                        type=ParameterType.STRING,
                        description="Post position(s) to generate (0-24) or 'all'",
                        required=False,
                    ),
                    ParameterSpec(
                        name="limit",
                        type=ParameterType.INTEGER,
                        description="Max posts to generate in one run",
                        required=False,
                    ),
                    ParameterSpec(
                        name="dry_run",
                        type=ParameterType.BOOLEAN,
                        description="Preview without saving",
                        required=False,
                        default=False,
                    ),
                ],
            ),
            CapabilitySpec(
                name="series_publish",
                description="Generate and publish a post from a series plan.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="series_id",
                        type=ParameterType.STRING,
                        description="Series ID",
                        required=True,
                    ),
                    ParameterSpec(
                        name="post",
                        type=ParameterType.INTEGER,
                        description="Post position (0-24)",
                        required=True,
                    ),
                    ParameterSpec(
                        name="dry_run",
                        type=ParameterType.BOOLEAN,
                        description="Preview without publishing",
                        required=False,
                        default=True,
                    ),
                    ParameterSpec(
                        name="execute",
                        type=ParameterType.BOOLEAN,
                        description="Actually publish (overrides dry-run)",
                        required=False,
                        default=False,
                    ),
                ],
            ),
            # ── Sources ─────────────────────────────────────────────────
            CapabilitySpec(
                name="sources_list",
                description="List fetched content source items.",
                parameters=[
                    ParameterSpec(
                        name="type",
                        type=ParameterType.STRING,
                        description="Filter: all, legal_news, industry_news, case_file, trend, documentation",
                        required=False,
                    ),
                    ParameterSpec(
                        name="days",
                        type=ParameterType.INTEGER,
                        description="Days to look back",
                        required=False,
                    ),
                    ParameterSpec(
                        name="limit",
                        type=ParameterType.INTEGER,
                        description="Max items to show",
                        required=False,
                    ),
                ],
            ),
            CapabilitySpec(
                name="sources_fetch",
                description="Fetch fresh content from sources.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="source",
                        type=ParameterType.STRING,
                        description="Source category: all, legal, industry, documentation",
                        required=False,
                    ),
                    ParameterSpec(
                        name="keywords",
                        type=ParameterType.STRING,
                        description="Keywords to filter/score results",
                        required=False,
                    ),
                    ParameterSpec(
                        name="days",
                        type=ParameterType.INTEGER,
                        description="Days to look back",
                        required=False,
                    ),
                    ParameterSpec(
                        name="limit",
                        type=ParameterType.INTEGER,
                        description="Max items to fetch",
                        required=False,
                    ),
                    ParameterSpec(
                        name="save",
                        type=ParameterType.BOOLEAN,
                        description="Save results to database",
                        required=False,
                        default=False,
                    ),
                ],
            ),
            # ── Analytics ───────────────────────────────────────────────
            CapabilitySpec(
                name="analytics_summary",
                description="Show content performance summary.",
                parameters=[
                    ParameterSpec(
                        name="days",
                        type=ParameterType.INTEGER,
                        description="Days to look back",
                        required=False,
                    ),
                ],
            ),
            CapabilitySpec(
                name="analytics_post",
                description="Show analytics for a specific published post.",
                parameters=[
                    ParameterSpec(
                        name="content_id",
                        type=ParameterType.STRING,
                        description="Content ID",
                        required=True,
                    ),
                ],
            ),
            # ── Personas & Voice ────────────────────────────────────────
            CapabilitySpec(
                name="persona_list",
                description="List all LinkedIn personas and company pages.",
                parameters=[],
            ),
            CapabilitySpec(
                name="persona_show",
                description="Show persona details and constraints.",
                parameters=[
                    ParameterSpec(
                        name="persona_name",
                        type=ParameterType.STRING,
                        description="Persona name",
                        required=True,
                    ),
                ],
            ),
            CapabilitySpec(
                name="voice_list",
                description="List all brand voice profiles.",
                parameters=[],
            ),
            CapabilitySpec(
                name="voice_show",
                description="Show voice profile details for a brand.",
                parameters=[
                    ParameterSpec(
                        name="brand",
                        type=ParameterType.STRING,
                        description="Brand name",
                        required=True,
                    ),
                ],
            ),
            # ── Contracts ───────────────────────────────────────────────
            CapabilitySpec(
                name="contracts_show",
                description="Show details for a project contract.",
                parameters=[
                    ParameterSpec(
                        name="project_id",
                        type=ParameterType.STRING,
                        description="Project ID",
                        required=True,
                    ),
                ],
            ),
            CapabilitySpec(
                name="contracts_validate",
                description="Validate project contracts schema and coverage.",
                parameters=[],
            ),
            # ── Batch ───────────────────────────────────────────────────
            CapabilitySpec(
                name="batch_status",
                description="Show current batch generation progress.",
                parameters=[],
            ),
            CapabilitySpec(
                name="batch_run",
                description="Generate the next N items from the batch catalog.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="n",
                        type=ParameterType.INTEGER,
                        description="Number of items to generate (default: 5)",
                        required=False,
                        default=5,
                    ),
                ],
            ),
            # ── Remote ──────────────────────────────────────────────────
            CapabilitySpec(
                name="verify_remote",
                description="Verify connection to remote deployment VM.",
                parameters=[],
            ),
        ],
        execution=ExecutionSpec(
            type=ExecutionType.PYTHON,
            python=PythonExecutionSpec(
                module="mother.plugins.builtin.contentcraft",
                **{"class": "ContentcraftPlugin"},
            ),
        ),
        permissions=[
            "filesystem:read",
            "filesystem:write",
            "network:https",
        ],
    )


class ContentcraftPlugin(PluginBase):
    """AI-powered content creation and publishing plugin."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the contentcraft plugin."""
        super().__init__(_create_manifest(), config)
        self._bin = self._find_binary()
        self._config = config or {}

    def _find_binary(self) -> str | None:
        """Find contentcraft CLI binary."""
        locations = [
            Path.home() / ".local" / "bin" / "contentcraft",
            Path.home() / "projects" / "contentcraft" / ".venv" / "bin" / "contentcraft",
            shutil.which("contentcraft"),
        ]
        for loc in locations:
            if loc and Path(str(loc)).exists():
                return str(loc)
        return None

    def _is_configured(self) -> bool:
        """Check if contentcraft is configured."""
        return self._bin is not None

    async def execute(self, capability: str, params: dict[str, Any]) -> PluginResult:
        """Execute a contentcraft capability."""
        handlers = {
            "status": self._status,
            "published": self._published,
            "portfolio_stats": self._portfolio_stats,
            "portfolio_projects": self._portfolio_projects,
            "drafts_list": self._drafts_list,
            "drafts_show": self._drafts_show,
            "drafts_approve": self._drafts_approve,
            "drafts_reject": self._drafts_reject,
            "drafts_submit": self._drafts_submit,
            "drafts_sync": self._drafts_sync,
            "drafts_export": self._drafts_export,
            "drafts_import": self._drafts_import,
            "generate": self._generate,
            "quick_post": self._quick_post,
            "generate_variants": self._generate_variants,
            "regenerate": self._regenerate,
            "render": self._render,
            "publish": self._publish,
            "publish_both": self._publish_both,
            "deploy": self._deploy,
            "queue_list": self._queue_list,
            "queue_schedule": self._queue_schedule,
            "queue_process": self._queue_process,
            "series_list": self._series_list,
            "series_show": self._series_show,
            "series_progress": self._series_progress,
            "series_create": self._series_create,
            "series_generate": self._series_generate,
            "series_publish": self._series_publish,
            "sources_list": self._sources_list,
            "sources_fetch": self._sources_fetch,
            "analytics_summary": self._analytics_summary,
            "analytics_post": self._analytics_post,
            "persona_list": self._persona_list,
            "persona_show": self._persona_show,
            "voice_list": self._voice_list,
            "voice_show": self._voice_show,
            "contracts_show": self._contracts_show,
            "contracts_validate": self._contracts_validate,
            "batch_status": self._batch_status,
            "batch_run": self._batch_run,
            "verify_remote": self._verify_remote,
        }

        handler = handlers.get(capability)
        if not handler:
            return PluginResult.error_result(
                f"Unknown capability: {capability}",
                code="UNKNOWN_CAPABILITY",
            )

        if not self._is_configured():
            return PluginResult.error_result(
                "ContentCraft CLI is not installed. Install contentcraft or check path.",
                code="NOT_CONFIGURED",
            )

        try:
            return await handler(**params)
        except Exception as e:
            return PluginResult.error_result(
                f"ContentCraft operation failed: {e}",
                code="CONTENTCRAFT_ERROR",
            )

    async def _run_cli(self, *args: str, timeout: int = 120) -> tuple[str, str, int]:
        """Run contentcraft CLI command."""
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

    # ── Status & Overview ───────────────────────────────────────────────

    async def _status(self) -> PluginResult:
        """Show system status."""
        stdout, stderr, code = await self._run_cli("status")
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="STATUS_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="ContentCraft status",
        )

    async def _published(
        self,
        platform: str | None = None,
        brand: str | None = None,
        limit: int | None = None,
    ) -> PluginResult:
        """List published content."""
        args = ["published"]
        if platform:
            args.extend(["-p", platform])
        if brand:
            args.extend(["-b", brand])
        if limit is not None:
            args.extend(["-n", str(limit)])

        stdout, stderr, code = await self._run_cli(*args)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="PUBLISHED_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Published content",
        )

    async def _portfolio_stats(self, days: int | None = None) -> PluginResult:
        """Show portfolio statistics."""
        args = ["portfolio", "stats"]
        if days is not None:
            args.extend(["-d", str(days)])

        stdout, stderr, code = await self._run_cli(*args)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="PORTFOLIO_STATS_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Portfolio statistics",
        )

    async def _portfolio_projects(
        self,
        tier: int | None = None,
        category: str | None = None,
    ) -> PluginResult:
        """List projects."""
        args = ["portfolio", "projects"]
        if tier is not None:
            args.extend(["--tier", str(tier)])
        if category:
            args.extend(["--category", category])

        stdout, stderr, code = await self._run_cli(*args)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="PORTFOLIO_PROJECTS_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Projects",
        )

    # ── Drafts ──────────────────────────────────────────────────────────

    async def _drafts_list(
        self,
        status: str | None = None,
        platform: str | None = None,
        brand: str | None = None,
        limit: int | None = None,
    ) -> PluginResult:
        """List drafts."""
        args = ["drafts", "list"]
        if status:
            args.extend(["-s", status])
        if platform:
            args.extend(["-p", platform])
        if brand:
            args.extend(["-b", brand])
        if limit is not None:
            args.extend(["-n", str(limit)])

        stdout, stderr, code = await self._run_cli(*args)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="DRAFTS_LIST_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Content drafts",
        )

    async def _drafts_show(self, content_id: str) -> PluginResult:
        """Show draft details."""
        stdout, stderr, code = await self._run_cli("drafts", "show", content_id)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="DRAFTS_SHOW_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Draft: {content_id}",
        )

    async def _drafts_approve(
        self,
        content_id: str,
        notes: str | None = None,
    ) -> PluginResult:
        """Approve a draft."""
        args = ["drafts", "approve", content_id]
        if notes:
            args.extend(["-n", notes])

        stdout, stderr, code = await self._run_cli(*args)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="DRAFTS_APPROVE_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Approved draft: {content_id}",
        )

    async def _drafts_reject(self, content_id: str, reason: str) -> PluginResult:
        """Reject a draft."""
        stdout, stderr, code = await self._run_cli(
            "drafts", "reject", content_id, "-r", reason
        )
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="DRAFTS_REJECT_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Rejected draft: {content_id}",
        )

    async def _drafts_submit(self, content_id: str) -> PluginResult:
        """Submit draft for review."""
        stdout, stderr, code = await self._run_cli("drafts", "submit", content_id)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="DRAFTS_SUBMIT_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Submitted draft: {content_id}",
        )

    async def _drafts_sync(self) -> PluginResult:
        """Sync draft status from Google Drive."""
        stdout, stderr, code = await self._run_cli("drafts", "sync")
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="DRAFTS_SYNC_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Drafts synced from Google Drive",
        )

    async def _drafts_export(self, content_id: str) -> PluginResult:
        """Export draft to Google Drive."""
        stdout, stderr, code = await self._run_cli("drafts", "export", content_id)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="DRAFTS_EXPORT_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Exported draft: {content_id}",
        )

    async def _drafts_import(self, filepath: str) -> PluginResult:
        """Import draft from Google Drive."""
        stdout, stderr, code = await self._run_cli("drafts", "import", filepath)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="DRAFTS_IMPORT_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Imported draft from: {filepath}",
        )

    # ── Content Generation ──────────────────────────────────────────────

    async def _generate(
        self,
        type: str,
        topic: str,
        brand: str | None = None,
        language: str | None = None,
        source_id: str | None = None,
        dry_run: bool = False,
    ) -> PluginResult:
        """Generate new content."""
        args = ["generate", "-t", type, "--topic", topic]
        if brand:
            args.extend(["-b", brand])
        if language:
            args.extend(["-l", language])
        if source_id:
            args.extend(["--source-id", source_id])
        if dry_run:
            args.append("--dry-run")

        stdout, stderr, code = await self._run_cli(*args, timeout=180)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="GENERATE_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Generated {type} content about: {topic}",
        )

    async def _quick_post(
        self,
        topic: str,
        brand: str,
        persona: str | None = None,
        dry_run: bool = False,
    ) -> PluginResult:
        """Generate blog + LinkedIn variants from idea."""
        args = ["quick-post", "-t", topic, "-b", brand]
        if persona:
            args.extend(["--persona", persona])
        if dry_run:
            args.append("--dry-run")

        stdout, stderr, code = await self._run_cli(*args, timeout=300)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="QUICK_POST_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Generated quick post: {topic}",
        )

    async def _generate_variants(
        self,
        blog_id: str,
        blog_url: str | None = None,
    ) -> PluginResult:
        """Generate LinkedIn variants from blog post."""
        args = ["generate-variants", blog_id]
        if blog_url:
            args.extend(["--blog-url", blog_url])

        stdout, stderr, code = await self._run_cli(*args, timeout=180)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="GENERATE_VARIANTS_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Generated variants for blog: {blog_id}",
        )

    async def _regenerate(
        self,
        content_id: str,
        feedback: str,
        dry_run: bool = False,
    ) -> PluginResult:
        """Regenerate content with feedback."""
        args = ["regenerate", content_id, "-f", feedback]
        if dry_run:
            args.append("--dry-run")

        stdout, stderr, code = await self._run_cli(*args, timeout=180)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="REGENERATE_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Regenerated: {content_id}",
        )

    async def _render(self, content_id: str) -> PluginResult:
        """Render content to platform format."""
        stdout, stderr, code = await self._run_cli("render", content_id)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="RENDER_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Rendered: {content_id}",
        )

    # ── Publishing ──────────────────────────────────────────────────────

    async def _publish(
        self,
        content_id: str,
        platform: str,
        dry_run: bool = True,
        execute: bool = False,
    ) -> PluginResult:
        """Publish content."""
        args = ["publish", content_id, "-p", platform]
        if execute:
            args.append("--execute")
        elif dry_run:
            args.append("--dry-run")

        stdout, stderr, code = await self._run_cli(*args, timeout=120)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="PUBLISH_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"{'Published' if execute else 'Preview'}: {content_id} on {platform}",
        )

    async def _publish_both(
        self,
        linkedin_id: str,
        blog_id: str,
        persona: str | None = None,
        dry_run: bool = True,
        execute: bool = False,
    ) -> PluginResult:
        """Publish blog and LinkedIn together."""
        args = ["publish-both", linkedin_id, blog_id]
        if persona:
            args.extend(["--persona", persona])
        if execute:
            args.append("--execute")
        elif dry_run:
            args.append("--dry-run")

        stdout, stderr, code = await self._run_cli(*args, timeout=120)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="PUBLISH_BOTH_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"{'Published' if execute else 'Preview'} blog+LinkedIn",
        )

    async def _deploy(
        self,
        content_id: str,
        dry_run: bool = True,
        force: bool = False,
    ) -> PluginResult:
        """Deploy blog to remote site."""
        args = ["deploy", content_id]
        if not dry_run:
            # deploy defaults to dry-run, so only add flag explicitly if NOT dry-run
            pass
        else:
            args.append("--dry-run")
        if force:
            args.append("--force")

        stdout, stderr, code = await self._run_cli(*args, timeout=120)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="DEPLOY_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"{'Deployed' if not dry_run else 'Deploy preview'}: {content_id}",
        )

    # ── Queue ───────────────────────────────────────────────────────────

    async def _queue_list(
        self,
        status: str | None = None,
        platform: str | None = None,
    ) -> PluginResult:
        """Show publishing queue."""
        args = ["queue", "list"]
        if status:
            args.extend(["-s", status])
        if platform:
            args.extend(["-p", platform])

        stdout, stderr, code = await self._run_cli(*args)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="QUEUE_LIST_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Publishing queue",
        )

    async def _queue_schedule(
        self,
        content_id: str,
        platform: str,
        time: str,
        priority: int | None = None,
    ) -> PluginResult:
        """Schedule content for publishing."""
        args = ["queue", "schedule", content_id, "-p", platform, "-t", time]
        if priority is not None:
            args.extend(["--priority", str(priority)])

        stdout, stderr, code = await self._run_cli(*args)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="QUEUE_SCHEDULE_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Scheduled {content_id} for {time}",
        )

    async def _queue_process(
        self,
        max: int | None = None,
        dry_run: bool = False,
    ) -> PluginResult:
        """Process pending queue items."""
        args = ["queue", "process"]
        if max is not None:
            args.extend(["-n", str(max)])
        if dry_run:
            args.append("--dry-run")

        stdout, stderr, code = await self._run_cli(*args, timeout=300)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="QUEUE_PROCESS_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Queue processed",
        )

    # ── Series ──────────────────────────────────────────────────────────

    async def _series_list(
        self,
        project: str | None = None,
        brand: str | None = None,
        status: str | None = None,
    ) -> PluginResult:
        """List series plans."""
        args = ["series", "list"]
        if project:
            args.extend(["--project", project])
        if brand:
            args.extend(["--brand", brand])
        if status:
            args.extend(["--status", status])

        stdout, stderr, code = await self._run_cli(*args)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="SERIES_LIST_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Content series",
        )

    async def _series_show(self, series_id: str) -> PluginResult:
        """Show series details."""
        stdout, stderr, code = await self._run_cli("series", "show", series_id)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="SERIES_SHOW_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Series: {series_id}",
        )

    async def _series_progress(self, series_id: str) -> PluginResult:
        """Show series progress."""
        stdout, stderr, code = await self._run_cli("series", "progress", series_id)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="SERIES_PROGRESS_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Series progress: {series_id}",
        )

    async def _series_create(
        self,
        project: str,
        brand: str,
        persona: str,
        dry_run: bool = False,
    ) -> PluginResult:
        """Create a series plan."""
        args = ["series", "create", "--project", project, "--brand", brand, "--persona", persona]
        if dry_run:
            args.append("--dry-run")

        stdout, stderr, code = await self._run_cli(*args, timeout=180)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="SERIES_CREATE_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Created series for: {project}",
        )

    async def _series_generate(
        self,
        series_id: str,
        post: str | None = None,
        limit: int | None = None,
        dry_run: bool = False,
    ) -> PluginResult:
        """Generate content from series plan."""
        args = ["series", "generate", series_id]
        if post:
            args.extend(["--post", post])
        if limit is not None:
            args.extend(["--limit", str(limit)])
        if dry_run:
            args.append("--dry-run")

        stdout, stderr, code = await self._run_cli(*args, timeout=300)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="SERIES_GENERATE_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Generated from series: {series_id}",
        )

    async def _series_publish(
        self,
        series_id: str,
        post: int,
        dry_run: bool = True,
        execute: bool = False,
    ) -> PluginResult:
        """Publish from series."""
        args = ["series", "publish", series_id, "--post", str(post)]
        if execute:
            args.append("--execute")
        elif dry_run:
            args.append("--dry-run")

        stdout, stderr, code = await self._run_cli(*args, timeout=300)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="SERIES_PUBLISH_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"{'Published' if execute else 'Preview'} series {series_id} post {post}",
        )

    # ── Sources ─────────────────────────────────────────────────────────

    async def _sources_list(
        self,
        type: str | None = None,
        days: int | None = None,
        limit: int | None = None,
    ) -> PluginResult:
        """List source items."""
        args = ["sources", "list"]
        if type:
            args.extend(["-t", type])
        if days is not None:
            args.extend(["-d", str(days)])
        if limit is not None:
            args.extend(["-n", str(limit)])

        stdout, stderr, code = await self._run_cli(*args)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="SOURCES_LIST_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Content sources",
        )

    async def _sources_fetch(
        self,
        source: str | None = None,
        keywords: str | None = None,
        days: int | None = None,
        limit: int | None = None,
        save: bool = False,
    ) -> PluginResult:
        """Fetch fresh sources."""
        args = ["sources", "fetch"]
        if source:
            args.extend(["-s", source])
        if keywords:
            args.extend(["-k", keywords])
        if days is not None:
            args.extend(["-d", str(days)])
        if limit is not None:
            args.extend(["-n", str(limit)])
        if save:
            args.append("--save")

        stdout, stderr, code = await self._run_cli(*args, timeout=180)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="SOURCES_FETCH_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Fetched sources",
        )

    # ── Analytics ───────────────────────────────────────────────────────

    async def _analytics_summary(self, days: int | None = None) -> PluginResult:
        """Show analytics summary."""
        args = ["analytics", "summary"]
        if days is not None:
            args.extend(["-d", str(days)])

        stdout, stderr, code = await self._run_cli(*args)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="ANALYTICS_SUMMARY_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Analytics summary",
        )

    async def _analytics_post(self, content_id: str) -> PluginResult:
        """Show post analytics."""
        stdout, stderr, code = await self._run_cli("analytics", "post", content_id)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="ANALYTICS_POST_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Analytics: {content_id}",
        )

    # ── Personas & Voice ────────────────────────────────────────────────

    async def _persona_list(self) -> PluginResult:
        """List personas."""
        stdout, stderr, code = await self._run_cli("persona", "list")
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="PERSONA_LIST_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Personas",
        )

    async def _persona_show(self, persona_name: str) -> PluginResult:
        """Show persona details."""
        stdout, stderr, code = await self._run_cli("persona", "show", persona_name)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="PERSONA_SHOW_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Persona: {persona_name}",
        )

    async def _voice_list(self) -> PluginResult:
        """List voice profiles."""
        stdout, stderr, code = await self._run_cli("voice", "list")
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="VOICE_LIST_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Voice profiles",
        )

    async def _voice_show(self, brand: str) -> PluginResult:
        """Show voice profile."""
        stdout, stderr, code = await self._run_cli("voice", "show", brand)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="VOICE_SHOW_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Voice: {brand}",
        )

    # ── Contracts ───────────────────────────────────────────────────────

    async def _contracts_show(self, project_id: str) -> PluginResult:
        """Show project contract."""
        stdout, stderr, code = await self._run_cli("contracts", "show", project_id)
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="CONTRACTS_SHOW_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Contract: {project_id}",
        )

    async def _contracts_validate(self) -> PluginResult:
        """Validate contracts."""
        stdout, stderr, code = await self._run_cli("contracts", "validate")
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="CONTRACTS_VALIDATE_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Contracts validation",
        )

    # ── Batch ───────────────────────────────────────────────────────────

    async def _batch_status(self) -> PluginResult:
        """Show batch generation progress."""
        stdout, stderr, code = await self._run_cli("batch", "status")
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="BATCH_STATUS_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Batch status",
        )

    async def _batch_run(self, n: int = 5) -> PluginResult:
        """Run batch generation."""
        stdout, stderr, code = await self._run_cli(
            "batch", "run", "--n", str(n), timeout=600
        )
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="BATCH_RUN_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message=f"Batch generated {n} items",
        )

    # ── Remote ──────────────────────────────────────────────────────────

    async def _verify_remote(self) -> PluginResult:
        """Verify remote connection."""
        stdout, stderr, code = await self._run_cli("verify-remote")
        if code != 0:
            return PluginResult.error_result(stderr or stdout, code="VERIFY_REMOTE_FAILED")
        return PluginResult.success_result(
            data={"output": stdout.strip()},
            message="Remote verification",
        )


__all__ = ["ContentcraftPlugin"]
