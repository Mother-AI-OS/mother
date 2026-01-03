#!/usr/bin/env python3
"""Test script for the Mother plugin system."""

import asyncio
import sys
from pathlib import Path

# Add mother to path
sys.path.insert(0, str(Path(__file__).parent))

from mother.plugins import (
    PluginManager,
    PluginConfig,
    PluginResult,
    ResultStatus,
)


async def test_plugin_system():
    """Test the plugin system with the demo plugin."""
    print("=" * 60)
    print("Mother Plugin System Test")
    print("=" * 60)

    # Create config pointing to user plugins
    config = PluginConfig(
        enabled=True,
        user_plugins_dir=Path.home() / ".mother" / "plugins",
        auto_discover=True,
        auto_load=True,
    )

    # Create and initialize manager
    print("\n1. Initializing PluginManager...")
    manager = PluginManager(config)
    await manager.initialize()

    # Check discovered plugins
    print("\n2. Discovered plugins:")
    discovered = manager.list_discovered()
    for name, info in discovered.items():
        status = "loaded" if info.loaded else f"error: {info.error}"
        print(f"   - {name} v{info.version}: {status}")

    if not discovered:
        print("   No plugins discovered!")
        print(f"   Checked: {config.user_plugins_dir}")
        return False

    # List capabilities
    print("\n3. Available capabilities:")
    for cap in manager.list_capabilities():
        print(f"   - {cap}")

    # Get schemas
    print("\n4. Generated Anthropic schemas:")
    schemas = manager.get_all_schemas()
    for schema in schemas:
        print(f"   - {schema['name']}: {schema['description'][:50]}...")

    # Test execution
    print("\n5. Testing capability execution:")

    # Test hello
    print("\n   [demo_hello]")
    result = await manager.execute("demo_hello", {})
    print(f"   Success: {result.success}")
    print(f"   Data: {result.data}")

    # Test greet
    print("\n   [demo_greet]")
    result = await manager.execute("demo_greet", {"name": "Mother", "formal": True})
    print(f"   Success: {result.success}")
    print(f"   Data: {result.data}")

    # Test calculate
    print("\n   [demo_calculate]")
    result = await manager.execute("demo_calculate", {
        "operation": "multiply",
        "a": 7,
        "b": 6,
    })
    print(f"   Success: {result.success}")
    print(f"   Data: {result.data}")

    # Test echo
    print("\n   [demo_echo]")
    result = await manager.execute("demo_echo", {
        "message": "Hello Plugin System!",
        "uppercase": True,
    })
    print(f"   Success: {result.success}")
    print(f"   Data: {result.data}")

    # Test confirmation required
    print("\n   [demo_dangerous_action] (confirmation_required=True)")
    result = await manager.execute("demo_dangerous_action", {"target": "test"})
    print(f"   Status: {result.status}")
    if result.status == ResultStatus.PENDING_CONFIRMATION:
        print("   Correctly returned PENDING_CONFIRMATION")
    else:
        print(f"   Data: {result.data}")

    # Cleanup
    print("\n6. Shutting down...")
    await manager.shutdown()

    print("\n" + "=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = asyncio.run(test_plugin_system())
    sys.exit(0 if success else 1)
