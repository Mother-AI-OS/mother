"""Mother Agent - FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .agent.core import MotherAgent
from .api.routes import init_dependencies, router
from .config.settings import get_settings
from .tools.registry import ToolRegistry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("mother")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    settings = get_settings()
    logger.info(f"Starting Mother Agent v{__version__}")

    # Initialize tool registry
    registry = ToolRegistry(settings=settings)
    logger.info(f"Loaded {len(registry.wrappers)} tools: {list(registry.wrappers.keys())}")

    # Initialize plugin system
    await registry.initialize_plugins()
    if registry.plugin_manager:
        plugin_count = len(registry.plugin_manager)
        logger.info(f"Plugin system: {plugin_count} capabilities loaded")

    # Initialize agent with memory
    agent = MotherAgent(
        tool_registry=registry,
        model=settings.claude_model,
        max_iterations=settings.max_iterations,
        api_key=settings.anthropic_api_key,
        openai_api_key=settings.openai_api_key,
        enable_memory=True,
    )
    logger.info(f"Agent initialized with model: {settings.claude_model}")
    if agent.memory:
        stats = agent.get_memory_stats()
        logger.info(f"Memory enabled: {stats.get('total_memories', 0)} memories stored")

    # Set up dependencies
    init_dependencies(registry, agent)

    yield

    # Shutdown
    logger.info("Shutting down Mother Agent")

    # Shutdown plugin system
    if registry.plugin_manager:
        try:
            await registry.plugin_manager.shutdown()
            logger.info("Plugin system shutdown complete")
        except Exception as e:
            logger.warning(f"Error during plugin shutdown: {e}")


# Create FastAPI app
app = FastAPI(
    title="Mother Agent",
    description="AI Agent that orchestrates CLI tools via natural language",
    version=__version__,
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:*", "http://127.0.0.1:*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router)


# Health check endpoint
@app.get("/health")
async def health():
    """Simple health check endpoint."""
    return {"status": "ok", "version": __version__}


def run():
    """Run the application (entry point for CLI)."""
    settings = get_settings()

    logger.info(f"Starting server on {settings.api_host}:{settings.api_port}")

    uvicorn.run(
        "mother.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()
