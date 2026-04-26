"""
Unit tests for TaskStrategies covering parameter schemas, validation, and strategy registry.
Requirements: 4.7, 5.1
"""

import pytest

from app.services.task_execution.task_strategies import (
    AttentionalBlinkStrategy,
    BinocularRivalryStrategy,
    ChangeBlindnessStrategy,
    IowaGamblingStrategy,
    MaskingParadigmStrategy,
    ParameterSchema,
    TaskStrategyRegistry,
    get_task_strategy_registry,
)


class TestParameterSchema:
    """Test ParameterSchema dataclass."""

    def test_parameter_schema_creation(self) -> None:
        """Test creating ParameterSchema instance."""
        schema = ParameterSchema(
            name="test_param",
            param_type="integer",
            default=10,
            description="Test parameter",
            min_value=1,
            max_value=100,
        )

        assert schema.name == "test_param"
        assert schema.param_type == "integer"
        assert schema.default == 10
        assert schema.min_value == 1
        assert schema.max_value == 100


class TestTaskStrategy:
    """Test TaskStrategy abstract base using concrete implementation."""

    def test_task_strategy_init(self) -> None:
        """Test TaskStrategy initialization via concrete class."""
        strategy = IowaGamblingStrategy()
        assert strategy.task_type == "iowa_gambling"
        assert strategy.name == "Iowa Gambling Task"

    def test_task_strategy_get_task_info(self) -> None:
        """Test get_task_info returns structure."""
        strategy = IowaGamblingStrategy()
        info = strategy.get_task_info()
        assert info["task_type"] == "iowa_gambling"
        assert info["name"] == "Iowa Gambling Task"

    def test_task_strategy_apply_defaults(self) -> None:
        """Test applying default values."""
        strategy = IowaGamblingStrategy()
        result = strategy._apply_defaults({})
        assert result["num_trials"] == 100

    def test_task_strategy_apply_defaults_existing(self) -> None:
        """Test defaults not applied when value exists."""
        strategy = IowaGamblingStrategy()
        result = strategy._apply_defaults({"num_trials": 50})
        assert result["num_trials"] == 50


class TestIowaGamblingStrategy:
    """Test IowaGamblingStrategy."""

    def test_strategy_initialization(self) -> None:
        """Strategy initializes with correct metadata."""
        strategy = IowaGamblingStrategy()
        assert strategy.task_type == "iowa_gambling"
        assert strategy.name == "Iowa Gambling Task"

    def test_get_parameter_schemas(self) -> None:
        """Returns all expected parameter schemas."""
        strategy = IowaGamblingStrategy()
        schemas = strategy.get_parameter_schemas()
        assert "num_trials" in schemas
        assert "initial_balance" in schemas
        assert "deck_selection_strategy" in schemas

    def test_validate_parameters_defaults(self) -> None:
        """Applies default values."""
        strategy = IowaGamblingStrategy()
        result = strategy.validate_parameters({})
        assert result["num_trials"] == 100
        assert result["initial_balance"] == 2000

    def test_validate_parameters_invalid_num_trials(self) -> None:
        """Raises error for invalid num_trials."""
        strategy = IowaGamblingStrategy()
        with pytest.raises(ValueError, match="num_trials must be a positive integer"):
            strategy.validate_parameters({"num_trials": -1})

    def test_validate_parameters_invalid_strategy(self) -> None:
        """Raises error for invalid deck_selection_strategy."""
        strategy = IowaGamblingStrategy()
        with pytest.raises(ValueError, match="Invalid deck_selection_strategy"):
            strategy.validate_parameters({"deck_selection_strategy": "invalid"})

    def test_validate_parameters_clamps_floats(self) -> None:
        """Clamps float values to valid ranges."""
        strategy = IowaGamblingStrategy()
        result = strategy.validate_parameters(
            {"deck_stimulus_strength": 100.0, "outcome_stimulus_strength": 0.0}
        )
        assert result["deck_stimulus_strength"] == 10.0
        assert result["outcome_stimulus_strength"] == 0.1

    def test_validate_parameters_clamps_interoceptive_gain(self) -> None:
        """Clamps interoceptive_gain to valid range."""
        strategy = IowaGamblingStrategy()
        result = strategy.validate_parameters({"interoceptive_gain": 15.0})
        assert result["interoceptive_gain"] == 10.0

    def test_validate_parameters_valid_strategy(self) -> None:
        """Valid deck_selection_strategy passes."""
        strategy = IowaGamblingStrategy()
        result = strategy.validate_parameters({"deck_selection_strategy": "random"})
        assert result["deck_selection_strategy"] == "random"

    def test_validate_parameters_all_allowed_strategies(self) -> None:
        """All allowed deck_selection_strategy values pass."""
        strategy = IowaGamblingStrategy()
        for strategy_name in ["balanced", "random", "adaptive"]:
            result = strategy.validate_parameters({"deck_selection_strategy": strategy_name})
            assert result["deck_selection_strategy"] == strategy_name

    def test_validate_parameters_clamps_deck_strength(self) -> None:
        """Clamps deck_stimulus_strength to valid range."""
        strategy = IowaGamblingStrategy()
        result = strategy.validate_parameters({"deck_stimulus_strength": 100.0})
        assert result["deck_stimulus_strength"] == 10.0

    def test_validate_parameters_clamps_outcome_strength(self) -> None:
        """Clamps outcome_stimulus_strength to valid range."""
        strategy = IowaGamblingStrategy()
        result = strategy.validate_parameters({"outcome_stimulus_strength": 0.0})
        assert result["outcome_stimulus_strength"] == 0.1

    def test_validate_parameters_valid_initial_balance(self) -> None:
        """Valid initial_balance passes."""
        strategy = IowaGamblingStrategy()
        result = strategy.validate_parameters({"initial_balance": 5000})
        assert result["initial_balance"] == 5000

    def test_validate_parameters_clamps_floats_all(self) -> None:
        """Clamps all float parameters to valid ranges."""
        strategy = IowaGamblingStrategy()
        result = strategy.validate_parameters(
            {
                "deck_stimulus_strength": 100.0,
                "outcome_stimulus_strength": 0.0,
                "interoceptive_gain": 20.0,
            }
        )
        assert result["deck_stimulus_strength"] == 10.0
        assert result["outcome_stimulus_strength"] == 0.1
        assert result["interoceptive_gain"] == 10.0

    def test_validate_parameters_clamps_interoceptive_gain_min(self) -> None:
        """Clamps interoceptive_gain to min value."""
        strategy = IowaGamblingStrategy()
        result = strategy.validate_parameters({"interoceptive_gain": -5.0})
        assert result["interoceptive_gain"] == 0.0


class TestMaskingParadigmStrategy:
    """Test MaskingParadigmStrategy."""

    def test_strategy_initialization(self) -> None:
        """Strategy initializes with correct metadata."""
        strategy = MaskingParadigmStrategy()
        assert strategy.task_type == "masking_paradigm"
        assert strategy.name == "Masking Paradigm Task"

    def test_get_parameter_schemas(self) -> None:
        """Returns all expected parameter schemas."""
        strategy = MaskingParadigmStrategy()
        schemas = strategy.get_parameter_schemas()
        assert "target_duration_ms" in schemas
        assert "soas" in schemas
        assert "mask_duration_ms" in schemas

    def test_validate_parameters_invalid_soas(self) -> None:
        """Raises error for invalid soas."""
        strategy = MaskingParadigmStrategy()
        with pytest.raises(ValueError, match="soas must be a list"):
            strategy.validate_parameters({"soas": "not a list"})

    def test_validate_parameters_invalid_soas_content(self) -> None:
        """Raises error for non-numeric soas."""
        strategy = MaskingParadigmStrategy()
        with pytest.raises(ValueError, match="soas must contain only numbers"):
            strategy.validate_parameters({"soas": ["a", "b", "c"]})

    def test_validate_parameters_clamps_strengths(self) -> None:
        """Clamps strength parameters to valid ranges."""
        strategy = MaskingParadigmStrategy()
        result = strategy.validate_parameters({"target_strength": 20.0, "mask_strength": 0.0})
        assert result["target_strength"] == 10.0
        assert result["mask_strength"] == 0.1

    def test_validate_parameters_clamps_durations(self) -> None:
        """Clamps duration parameters to valid ranges."""
        strategy = MaskingParadigmStrategy()
        result = strategy.validate_parameters(
            {"target_duration_ms": 2000.0, "mask_duration_ms": 0.0}
        )
        assert result["target_duration_ms"] == 1000.0
        assert result["mask_duration_ms"] == 1.0

    def test_validate_parameters_valid_num_trials(self) -> None:
        """Valid num_trials_per_condition passes."""
        strategy = MaskingParadigmStrategy()
        result = strategy.validate_parameters({"num_trials_per_condition": 50})
        assert result["num_trials_per_condition"] == 50

    def test_validate_parameters_valid_soas(self) -> None:
        """Valid soas array passes."""
        strategy = MaskingParadigmStrategy()
        result = strategy.validate_parameters({"soas": [50, 100, 150]})
        assert result["soas"] == [50, 100, 150]

    def test_validate_parameters_applies_defaults(self) -> None:
        """Applies default values for missing parameters."""
        strategy = MaskingParadigmStrategy()
        result = strategy.validate_parameters({})
        assert result["target_duration_ms"] == 50.0
        assert result["mask_duration_ms"] == 100.0
        assert result["num_trials_per_condition"] == 20


class TestAttentionalBlinkStrategy:
    """Test AttentionalBlinkStrategy."""

    def test_strategy_initialization(self) -> None:
        """Strategy initializes with correct metadata."""
        strategy = AttentionalBlinkStrategy()
        assert strategy.task_type == "attentional_blink"
        assert strategy.name == "Attentional Blink Task"

    def test_get_parameter_schemas(self) -> None:
        """Returns all expected parameter schemas."""
        strategy = AttentionalBlinkStrategy()
        schemas = strategy.get_parameter_schemas()
        assert "stream_length" in schemas
        assert "lags" in schemas
        assert "item_duration_ms" in schemas

    def test_validate_parameters_invalid_lags(self) -> None:
        """Raises error for invalid lags."""
        strategy = AttentionalBlinkStrategy()
        with pytest.raises(ValueError, match="lags must be a list"):
            strategy.validate_parameters({"lags": "not a list"})

    def test_validate_parameters_invalid_lags_content(self) -> None:
        """Raises error for non-integer lags."""
        strategy = AttentionalBlinkStrategy()
        with pytest.raises(ValueError, match="lags must contain only integers"):
            strategy.validate_parameters({"lags": [1.5, 2.5]})

    def test_validate_parameters_valid_salience(self) -> None:
        """Valid target salience passes (no clamping in implementation)."""
        strategy = AttentionalBlinkStrategy()
        result = strategy.validate_parameters({"target_salience": 5.0})
        assert result["target_salience"] == 5.0

    def test_validate_parameters_applies_defaults(self) -> None:
        """Applies default values for missing parameters."""
        strategy = AttentionalBlinkStrategy()
        result = strategy.validate_parameters({})
        assert result["stream_length"] == 15
        assert result["item_duration_ms"] == 100.0
        assert result["lags"] == [1, 2, 3, 4, 8]

    def test_validate_parameters_valid_lags(self) -> None:
        """Valid lags array passes."""
        strategy = AttentionalBlinkStrategy()
        result = strategy.validate_parameters({"lags": [1, 2, 3, 4, 8]})
        assert result["lags"] == [1, 2, 3, 4, 8]

    def test_validate_parameters_valid_stream_length(self) -> None:
        """Valid stream_length passes."""
        strategy = AttentionalBlinkStrategy()
        result = strategy.validate_parameters({"stream_length": 20})
        assert result["stream_length"] == 20

    def test_validate_parameters_valid_item_duration(self) -> None:
        """Valid item_duration_ms passes."""
        strategy = AttentionalBlinkStrategy()
        result = strategy.validate_parameters({"item_duration_ms": 100.0})
        assert result["item_duration_ms"] == 100.0

    def test_validate_parameters_valid_isi(self) -> None:
        """Valid isi_ms passes."""
        strategy = AttentionalBlinkStrategy()
        result = strategy.validate_parameters({"isi_ms": 100.0})
        assert result["isi_ms"] == 100.0


class TestChangeBlindnessStrategy:
    """Test ChangeBlindnessStrategy."""

    def test_strategy_initialization(self) -> None:
        """Strategy initializes with correct metadata."""
        strategy = ChangeBlindnessStrategy()
        assert strategy.task_type == "change_blindness"
        assert strategy.name == "Change Blindness Task"

    def test_get_parameter_schemas(self) -> None:
        """Returns all expected parameter schemas."""
        strategy = ChangeBlindnessStrategy()
        schemas = strategy.get_parameter_schemas()
        assert "image_size" in schemas
        assert "change_magnitude" in schemas
        assert "flicker_duration_ms" in schemas

    def test_validate_parameters_invalid_image_size(self) -> None:
        """Raises error for invalid image_size."""
        strategy = ChangeBlindnessStrategy()
        with pytest.raises(ValueError, match="image_size must be a list"):
            strategy.validate_parameters({"image_size": "not a list"})

    def test_validate_parameters_invalid_image_size_length(self) -> None:
        """Raises error for wrong image_size length."""
        strategy = ChangeBlindnessStrategy()
        with pytest.raises(ValueError, match="image_size must be a list of two integers"):
            strategy.validate_parameters({"image_size": [256]})

    def test_validate_parameters_invalid_image_size_values(self) -> None:
        """Raises error for non-positive image_size values."""
        strategy = ChangeBlindnessStrategy()
        with pytest.raises(ValueError, match="image_size values must be positive integers"):
            strategy.validate_parameters({"image_size": [-1, 256]})

    def test_validate_parameters_valid_change_magnitude(self) -> None:
        """Valid change magnitude passes."""
        strategy = ChangeBlindnessStrategy()
        result = strategy.validate_parameters({"change_magnitude": 0.5})
        assert result["change_magnitude"] == 0.5

    def test_validate_parameters_valid_flicker_duration(self) -> None:
        """Valid flicker duration passes."""
        strategy = ChangeBlindnessStrategy()
        result = strategy.validate_parameters({"flicker_duration_ms": 500.0})
        assert result["flicker_duration_ms"] == 500.0

    def test_validate_parameters_applies_defaults(self) -> None:
        """Applies default values for missing parameters."""
        strategy = ChangeBlindnessStrategy()
        result = strategy.validate_parameters({})
        assert result["image_size"] == [256, 256]
        assert result["change_magnitude"] == 0.3
        assert result["num_trials"] == 50

    def test_validate_parameters_valid_image_size(self) -> None:
        """Valid image_size passes."""
        strategy = ChangeBlindnessStrategy()
        result = strategy.validate_parameters({"image_size": [512, 512]})
        assert result["image_size"] == [512, 512]

    def test_validate_parameters_valid_flicker_interval(self) -> None:
        """Valid flicker_interval_ms passes."""
        strategy = ChangeBlindnessStrategy()
        result = strategy.validate_parameters({"flicker_interval_ms": 100.0})
        assert result["flicker_interval_ms"] == 100.0


class TestBinocularRivalryStrategy:
    """Test BinocularRivalryStrategy."""

    def test_strategy_initialization(self) -> None:
        """Strategy initializes with correct metadata."""
        strategy = BinocularRivalryStrategy()
        assert strategy.task_type == "binocular_rivalry"
        assert strategy.name == "Binocular Rivalry Task"

    def test_get_parameter_schemas(self) -> None:
        """Returns all expected parameter schemas."""
        strategy = BinocularRivalryStrategy()
        schemas = strategy.get_parameter_schemas()
        assert "pattern_size" in schemas
        assert "contrast_left" in schemas
        assert "contrast_right" in schemas

    def test_validate_parameters_invalid_pattern_size(self) -> None:
        """Raises error for invalid pattern_size."""
        strategy = BinocularRivalryStrategy()
        with pytest.raises(ValueError, match="pattern_size must be a list"):
            strategy.validate_parameters({"pattern_size": "not a list"})

    def test_validate_parameters_clamps_contrast(self) -> None:
        """Clamps contrast values to 0-1 range."""
        strategy = BinocularRivalryStrategy()
        result = strategy.validate_parameters({"contrast_left": 2.0, "contrast_right": -0.5})
        assert result["contrast_left"] == 1.0
        assert result["contrast_right"] == 0.0

    def test_validate_parameters_valid_duration(self) -> None:
        """Valid duration passes."""
        strategy = BinocularRivalryStrategy()
        result = strategy.validate_parameters({"duration_seconds": 300.0})
        assert result["duration_seconds"] == 300.0

    def test_validate_parameters_valid_sampling_rate(self) -> None:
        """Valid sampling rate passes."""
        strategy = BinocularRivalryStrategy()
        result = strategy.validate_parameters({"sampling_rate_hz": 60.0})
        assert result["sampling_rate_hz"] == 60.0

    def test_validate_parameters_applies_defaults(self) -> None:
        """Applies default values for missing parameters."""
        strategy = BinocularRivalryStrategy()
        result = strategy.validate_parameters({})
        assert result["pattern_size"] == [256, 256]
        assert result["contrast_left"] == 1.0
        assert result["contrast_right"] == 1.0

    def test_validate_parameters_valid_pattern_size(self) -> None:
        """Valid pattern_size passes."""
        strategy = BinocularRivalryStrategy()
        result = strategy.validate_parameters({"pattern_size": [256, 256]})
        assert result["pattern_size"] == [256, 256]

    def test_validate_parameters_valid_phase_shift(self) -> None:
        """Valid phase_shift_degrees passes."""
        strategy = BinocularRivalryStrategy()
        result = strategy.validate_parameters({"phase_shift_degrees": 180.0})
        assert result["phase_shift_degrees"] == 180.0


class TestTaskStrategyRegistry:
    """Test TaskStrategyRegistry."""

    def test_registry_initialization(self) -> None:
        """Registry initializes with default strategies."""
        registry = TaskStrategyRegistry()
        assert len(registry._strategies) == 5

    def test_register_strategy(self) -> None:
        """Register a new strategy."""
        registry = TaskStrategyRegistry()
        strategy = IowaGamblingStrategy()
        strategy.task_type = "custom"  # Modify for testing
        registry.register(strategy)
        assert "custom" in registry._strategies

    def test_register_duplicate_raises_error(self) -> None:
        """Registering duplicate raises error."""
        registry = TaskStrategyRegistry()
        strategy = IowaGamblingStrategy()
        with pytest.raises(ValueError, match="already registered"):
            registry.register(strategy)

    def test_get_strategy(self) -> None:
        """Get registered strategy."""
        registry = TaskStrategyRegistry()
        strategy = registry.get("iowa_gambling")
        assert strategy is not None
        assert strategy.task_type == "iowa_gambling"

    def test_get_strategy_unknown(self) -> None:
        """Return None for unknown strategy."""
        registry = TaskStrategyRegistry()
        strategy = registry.get("unknown")
        assert strategy is None

    def test_get_all_strategies(self) -> None:
        """Get all registered strategies."""
        registry = TaskStrategyRegistry()
        strategies = registry.get_all()
        assert len(strategies) == 5

    def test_is_valid_task_type(self) -> None:
        """Check if task type is valid."""
        registry = TaskStrategyRegistry()
        assert registry.is_valid_task_type("iowa_gambling") is True
        assert registry.is_valid_task_type("unknown") is False

    def test_get_allowed_task_types(self) -> None:
        """Get list of allowed task types."""
        registry = TaskStrategyRegistry()
        types = registry.get_allowed_task_types()
        assert "iowa_gambling" in types
        assert "masking_paradigm" in types


class TestGetTaskStrategyRegistry:
    """Test global registry getter."""

    def test_get_registry_singleton(self) -> None:
        """Returns singleton instance."""
        registry1 = get_task_strategy_registry()
        registry2 = get_task_strategy_registry()
        assert registry1 is registry2

    def test_get_registry_initialized(self) -> None:
        """Registry is initialized with strategies."""
        registry = get_task_strategy_registry()
        assert len(registry._strategies) > 0
