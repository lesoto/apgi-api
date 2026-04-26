"""Test app/__init__.py module."""

import os
import tempfile

from app import APGISystem, MockSubSystem


class TestMockSubSystem:
    def test_mock_subsystem_init(self) -> None:
        """MockSubSystem initializes with name."""
        subsys = MockSubSystem("test")
        assert subsys.name == "test"
        assert subsys._state == {}

    def test_mock_subsystem_save_state(self) -> None:
        """save_state returns copy of state."""
        subsys = MockSubSystem("test")
        subsys._state = {"key": "value"}
        saved = subsys.save_state()
        assert saved == {"key": "value"}
        # Verify it's a copy
        saved["key"] = "modified"
        assert subsys._state["key"] == "value"

    def test_mock_subsystem_load_state(self) -> None:
        """load_state updates internal state."""
        subsys = MockSubSystem("test")
        new_state = {"key": "value"}
        subsys.load_state(new_state)
        assert subsys._state == {"key": "value"}


class TestAPGISystem:
    def test_apgi_system_init_with_dict(self) -> None:
        """APGISystem initializes with dict config."""
        config = {"param": "value"}
        system = APGISystem(config)
        assert system.config == config
        assert system.time == 0.0
        assert system.history == {}

    def test_apgi_system_init_with_none(self) -> None:
        """APGISystem initializes with None config."""
        system = APGISystem(None)
        assert system.config == {}
        assert system.time == 0.0

    def test_apgi_system_init_with_nonexistent_file(self) -> None:
        """APGISystem initializes with nonexistent file path."""
        system = APGISystem("/nonexistent/path/config.yaml")
        assert system.config == {}

    def test_apgi_system_init_with_yaml_file(self) -> None:
        """APGISystem initializes with YAML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("param: value\n")
            f.flush()
            temp_path = f.name

        try:
            system = APGISystem(temp_path)
            assert system.config == {"param": "value"}
        finally:
            os.unlink(temp_path)

    def test_apgi_system_init_with_invalid_yaml_file(self) -> None:
        """APGISystem initializes with invalid YAML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [")
            f.flush()
            temp_path = f.name

        try:
            system = APGISystem(temp_path)
            assert system.config == {}
        finally:
            os.unlink(temp_path)

    def test_apgi_system_subsystems_initialized(self) -> None:
        """APGISystem initializes all subsystems."""
        system = APGISystem()
        assert isinstance(system.allostasis, MockSubSystem)
        assert isinstance(system.body, MockSubSystem)
        assert isinstance(system.precision, MockSubSystem)
        assert isinstance(system.workspace, MockSubSystem)
        assert isinstance(system.self_model, MockSubSystem)
        assert isinstance(system.ignition, MockSubSystem)

    def test_apgi_system_get_state(self) -> None:
        """get_state returns system state."""
        config = {"param": "value"}
        system = APGISystem(config)
        state = system.get_state()
        assert state["time"] == 0.0
        assert state["history"] == {}
        assert state["config"] == config

    def test_apgi_system_step(self) -> None:
        """step increments time and returns state."""
        system = APGISystem()
        result = system.step()
        assert system.time == 1.0
        assert result["time"] == 1.0
        assert "ignition" in result
        assert result["ignition"]["total_signal"] == 0.0
        assert result["ignition"]["threshold"] == 2.0

    def test_apgi_system_step_multiple(self) -> None:
        """step can be called multiple times."""
        system = APGISystem()
        system.step()
        system.step()
        assert system.time == 2.0

    def test_apgi_system_step_with_input(self) -> None:
        """step accepts extero_input parameter."""
        system = APGISystem()
        result = system.step({"input": "data"})
        assert system.time == 1.0
        assert result["time"] == 1.0

    def test_apgi_system_reset(self) -> None:
        """reset clears system state."""
        system = APGISystem()
        system.step()
        system.step()
        system.history = {"key": "value"}
        system.allostasis._state = {"data": "value"}

        system.reset()
        assert system.time == 0.0
        assert system.history == {}
        assert system.allostasis._state == {}
        assert system.body._state == {}
        assert system.precision._state == {}
        assert system.workspace._state == {}
        assert system.self_model._state == {}
        assert system.ignition._state == {}
