"""Plugin configuration and management API endpoints."""

import logging
from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status

from src.api.models import (
    PluginInfo,
    PluginConfigUpdate,
    PluginTestResult,
    ErrorResponse
)
from src.api.deps import get_plugin_registry, get_current_user
from plugins.registry import PluginRegistry
from plugins.config import load_plugin_config, save_plugin_config

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/plugins",
    tags=["plugins"],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"},
    }
)


@router.get(
    "",
    response_model=List[PluginInfo],
    summary="List all plugins",
    description="Retrieve information about all available messaging plugins.",
)
async def list_plugins(
    registry: PluginRegistry = Depends(get_plugin_registry),
    user: dict = Depends(get_current_user),
):
    """List all available messaging plugins.

    Returns information about each plugin including:
    - Name and display name
    - Version
    - Description
    - Configuration schema
    - Configuration status
    - Health status

    Returns:
        List[PluginInfo]: List of plugin information

    Example:
        ```bash
        curl http://localhost:8000/api/v1/plugins
        ```
    """
    try:
        plugins_info = registry.get_all_plugins_info()
        result = []

        for plugin_meta in plugins_info:
            plugin_name = plugin_meta["name"]

            # Check if plugin is configured
            try:
                config = load_plugin_config(plugin_name)
                is_configured = bool(config)

                # Get instance if configured
                if is_configured:
                    instance = registry.get_instance(plugin_name)
                    if instance:
                        health = instance.get_health_status()
                        is_healthy = health.get("healthy")
                    else:
                        is_healthy = None
                else:
                    is_healthy = None

            except Exception as e:
                logger.warning(f"Error checking config for {plugin_name}: {e}")
                is_configured = False
                is_healthy = None

            result.append(PluginInfo(
                name=plugin_meta["name"],
                display_name=plugin_meta["display_name"],
                version=plugin_meta["version"],
                description=plugin_meta["description"],
                config_schema=plugin_meta["config_schema"],
                is_configured=is_configured,
                is_healthy=is_healthy
            ))

        logger.info(f"Retrieved information for {len(result)} plugins")
        return result

    except Exception as e:
        logger.error(f"Error listing plugins: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list plugins: {str(e)}"
        )


@router.get(
    "/{plugin_name}",
    response_model=PluginInfo,
    summary="Get plugin details",
    description="Retrieve detailed information about a specific plugin.",
)
async def get_plugin(
    plugin_name: str,
    registry: PluginRegistry = Depends(get_plugin_registry),
    user: dict = Depends(get_current_user),
):
    """Get detailed information about a specific plugin.

    Args:
        plugin_name: Name of the plugin (e.g., 'slack', 'email')

    Returns:
        PluginInfo: Plugin information

    Raises:
        HTTPException: If plugin is not found

    Example:
        ```bash
        curl http://localhost:8000/api/v1/plugins/slack
        ```
    """
    try:
        plugin_meta = registry.get_plugin_info(plugin_name)

        # Check configuration status
        try:
            config = load_plugin_config(plugin_name)
            is_configured = bool(config)

            if is_configured:
                instance = registry.get_instance(plugin_name)
                if instance:
                    health = instance.get_health_status()
                    is_healthy = health.get("healthy")
                else:
                    is_healthy = None
            else:
                is_healthy = None

        except Exception:
            is_configured = False
            is_healthy = None

        return PluginInfo(
            name=plugin_meta["name"],
            display_name=plugin_meta["display_name"],
            version=plugin_meta["version"],
            description=plugin_meta["description"],
            config_schema=plugin_meta["config_schema"],
            is_configured=is_configured,
            is_healthy=is_healthy
        )

    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin '{plugin_name}' not found"
        )
    except Exception as e:
        logger.error(f"Error retrieving plugin {plugin_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve plugin: {str(e)}"
        )


@router.put(
    "/{plugin_name}/config",
    summary="Update plugin configuration",
    description="Update the configuration for a specific plugin.",
)
async def update_plugin_config(
    plugin_name: str,
    config_update: PluginConfigUpdate,
    registry: PluginRegistry = Depends(get_plugin_registry),
    user: dict = Depends(get_current_user),
):
    """Update plugin configuration.

    This will save the configuration and attempt to create/refresh
    the plugin instance with the new settings.

    Args:
        plugin_name: Name of the plugin
        config_update: New configuration data

    Returns:
        dict: Success message

    Raises:
        HTTPException: If plugin not found or configuration is invalid

    Example:
        ```bash
        curl -X PUT http://localhost:8000/api/v1/plugins/slack/config \\
             -H "Content-Type: application/json" \\
             -d '{"config": {"api_token": "xoxb-...", "channel": "#general"}}'
        ```
    """
    try:
        # Verify plugin exists
        _ = registry.get_plugin_info(plugin_name)

        # Save configuration
        save_plugin_config(plugin_name, config_update.config)

        # Clear cached instance to force recreation with new config
        registry.clear_cache()

        # Try to create instance with new config to validate
        try:
            instance = registry.create_instance(plugin_name, config_update.config)
            logger.info(f"Successfully configured plugin: {plugin_name}")

            return {
                "message": f"Plugin '{plugin_name}' configured successfully",
                "plugin": plugin_name,
                "config_valid": True
            }
        except Exception as e:
            logger.warning(f"Configuration saved but validation failed: {e}")
            return {
                "message": f"Configuration saved but validation failed: {str(e)}",
                "plugin": plugin_name,
                "config_valid": False,
                "error": str(e)
            }

    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin '{plugin_name}' not found"
        )
    except Exception as e:
        logger.error(f"Error updating plugin config: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update configuration: {str(e)}"
        )


@router.post(
    "/{plugin_name}/test",
    response_model=PluginTestResult,
    summary="Test plugin connection",
    description="Test if the plugin can connect to its service.",
)
async def test_plugin_connection(
    plugin_name: str,
    registry: PluginRegistry = Depends(get_plugin_registry),
    user: dict = Depends(get_current_user),
):
    """Test plugin connection and configuration.

    This will attempt to connect to the plugin's service and verify
    that it's properly configured.

    Args:
        plugin_name: Name of the plugin to test

    Returns:
        PluginTestResult: Test result with success status and message

    Raises:
        HTTPException: If plugin is not found or not configured

    Example:
        ```bash
        curl -X POST http://localhost:8000/api/v1/plugins/slack/test
        ```
    """
    try:
        # Load configuration
        config = load_plugin_config(plugin_name)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Plugin '{plugin_name}' is not configured"
            )

        # Create or get instance
        instance = registry.create_instance(plugin_name, config, cache=True)

        # Run connection test
        success = instance.test_connection()
        instance.record_test_result(success)

        message = "Connection test successful" if success else "Connection test failed"

        logger.info(f"Plugin {plugin_name} test: {'success' if success else 'failure'}")

        return PluginTestResult(
            success=success,
            message=message,
            timestamp=datetime.now().isoformat()
        )

    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin '{plugin_name}' not found"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing plugin {plugin_name}: {e}")
        return PluginTestResult(
            success=False,
            message=f"Test failed: {str(e)}",
            timestamp=datetime.now().isoformat()
        )


@router.post(
    "/{plugin_name}/notify",
    summary="Send test notification",
    description="Send a test notification using the plugin.",
)
async def send_test_notification(
    plugin_name: str,
    message: str = "This is a test notification from Scholar Slack Bot API",
    target: str = None,
    registry: PluginRegistry = Depends(get_plugin_registry),
    user: dict = Depends(get_current_user),
):
    """Send a test notification using the plugin.

    Args:
        plugin_name: Name of the plugin to use
        message: Custom test message (optional)
        target: Target destination (channel, email, etc.) - uses default if not specified

    Returns:
        dict: Success status and message

    Raises:
        HTTPException: If plugin is not found or not configured

    Example:
        ```bash
        curl -X POST "http://localhost:8000/api/v1/plugins/slack/notify?message=Hello%20World"
        ```
    """
    try:
        # Load configuration
        config = load_plugin_config(plugin_name)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Plugin '{plugin_name}' is not configured"
            )

        # Create or get instance
        instance = registry.create_instance(plugin_name, config, cache=True)

        # Use default target from config if not specified
        if target is None:
            target = config.get("channel") or config.get("default_target", "")

        # Format test message
        formatted_message = instance.format_test_message(message)

        # Send notification
        success = instance.send_message(formatted_message, target)

        if success:
            logger.info(f"Test notification sent via {plugin_name}")
            return {
                "success": True,
                "message": f"Test notification sent successfully via {plugin_name}",
                "plugin": plugin_name,
                "target": target
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send notification"
            )

    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin '{plugin_name}' not found"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending test notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send notification: {str(e)}"
        )
