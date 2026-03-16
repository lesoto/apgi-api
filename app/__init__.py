"""
Standalone APGI API Application

This package contains the standalone REST API for the APGI system.
"""

__version__ = "1.0.0"

from typing import Any, Dict, Optional


class MockSubSystem:
    """Mock subsystem with save/load state methods."""

    def __init__(self, name: str):
        self.name = name
        self._state: Dict[str, Any] = {}

    def save_state(self) -> Dict[str, Any]:
        """Save subsystem state."""
        return self._state.copy()

    def load_state(self, state: Dict[str, Any]) -> None:
        """Load subsystem state."""
        self._state = state


class APGISystem:
    """Mock APGI System implementation."""

    def __init__(self, config_path: Optional[Dict[str, Any]] = None):
        self.config: Dict[str, Any] = config_path or {}
        self.time = 0.0
        self.history: Dict[str, Any] = {}
        self.allostasis = MockSubSystem("allostasis")
        self.body = MockSubSystem("body")
        self.precision = MockSubSystem("precision")
        self.workspace = MockSubSystem("workspace")
        self.self_model = MockSubSystem("self_model")
        self.ignition = MockSubSystem("ignition")
        self._initialize_subsystems()

    def _initialize_subsystems(self) -> None:
        """Initialize all subsystems."""
        pass

    def get_state(self) -> Dict[str, Any]:
        """Get system state."""
        return {
            "time": self.time,
            "history": self.history,
            "config": self.config,
        }

    def step(self, extero_input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute one simulation step."""
        self.time += 1.0
        return {
            "time": self.time,
            "history": self.history,
            "config": self.config,
            "ignition": {"total_signal": 0.0, "threshold": 2.0},
        }

    def reset(self) -> None:
        """Reset the system."""
        self.time = 0.0
        self.history = {}
        self.allostasis._state = {}
        self.body._state = {}
        self.precision._state = {}
        self.workspace._state = {}
        self.self_model._state = {}
        self.ignition._state = {}
