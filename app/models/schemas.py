"""
Pydantic Request and Response Models

Defines the data schemas for API requests and responses.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class SessionCreateRequest(BaseModel):
    """Request to create new simulation session."""

    config_path: Optional[str] = Field(None, description="Path to YAML configuration file")
    custom_config: Optional[Dict[str, Any]] = Field(
        None, description="Custom configuration overrides"
    )
    description: Optional[str] = Field(
        None, description="Human-readable description of the session"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "config_path": "config/default.yaml",
                "description": "Baseline simulation experiment",
            }
        }
    )
