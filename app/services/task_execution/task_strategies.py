"""
Task Strategies Module

Defines strategy pattern for different experimental task types.
Each task type has its own parameter schema and validation logic.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ParameterSchema:
    """Schema definition for a task parameter."""

    name: str
    param_type: str
    default: Any
    description: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    allowed_values: Optional[List[Any]] = None


class TaskStrategy(ABC):
    """
    Abstract base class for task execution strategies.

    Each experimental task type (Iowa Gambling, Masking Paradigm, etc.)
    implements this interface to provide its specific parameter schema
    and validation logic.
    """

    def __init__(self, task_type: str, name: str, description: str):
        self.task_type = task_type
        self.name = name
        self.description = description
        self._parameter_schemas: Dict[str, ParameterSchema] = {}

    @abstractmethod
    def get_parameter_schemas(self) -> Dict[str, ParameterSchema]:
        """
        Return the parameter schemas for this task type.

        Returns:
            Dict mapping parameter names to their schemas
        """
        pass

    @abstractmethod
    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and normalize task parameters.

        Args:
            parameters: Raw parameters from user

        Returns:
            Validated and normalized parameters

        Raises:
            ValueError: If parameters are invalid
        """
        pass

    def get_task_info(self) -> Dict[str, Any]:
        """
        Get task metadata for API responses.

        Returns:
            Dict with task type info and parameter schemas
        """
        schemas = self.get_parameter_schemas()
        return {
            "task_type": self.task_type,
            "name": self.name,
            "description": self.description,
            "parameters": {
                name: {
                    "type": schema.param_type,
                    "default": schema.default,
                    "description": schema.description,
                    **({"min": schema.min_value} if schema.min_value is not None else {}),
                    **({"max": schema.max_value} if schema.max_value is not None else {}),
                    **({"allowed": schema.allowed_values} if schema.allowed_values else {}),
                }
                for name, schema in schemas.items()
            },
        }

    def _apply_defaults(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Apply default values for missing parameters."""
        schemas = self.get_parameter_schemas()
        result = dict(parameters)
        for name, schema in schemas.items():
            if name not in result:
                result[name] = schema.default
        return result


class IowaGamblingStrategy(TaskStrategy):
    """Strategy for Iowa Gambling Task."""

    def __init__(self) -> None:
        super().__init__(
            task_type="iowa_gambling",
            name="Iowa Gambling Task",
            description="Decision-making task with four decks of cards",
        )

    def get_parameter_schemas(self) -> Dict[str, ParameterSchema]:
        return {
            "num_trials": ParameterSchema(
                name="num_trials",
                param_type="integer",
                default=100,
                description="Number of trials",
                min_value=1,
                max_value=1000,
            ),
            "initial_balance": ParameterSchema(
                name="initial_balance",
                param_type="integer",
                default=2000,
                description="Starting balance",
                min_value=0,
            ),
            "deck_stimulus_strength": ParameterSchema(
                name="deck_stimulus_strength",
                param_type="float",
                default=1.5,
                description="Deck visual strength",
                min_value=0.1,
                max_value=10.0,
            ),
            "outcome_stimulus_strength": ParameterSchema(
                name="outcome_stimulus_strength",
                param_type="float",
                default=2.0,
                description="Outcome strength",
                min_value=0.1,
                max_value=10.0,
            ),
            "interoceptive_gain": ParameterSchema(
                name="interoceptive_gain",
                param_type="float",
                default=1.0,
                description="Interoceptive signal multiplier",
                min_value=0.0,
                max_value=10.0,
            ),
            "deck_selection_strategy": ParameterSchema(
                name="deck_selection_strategy",
                param_type="string",
                default="balanced",
                description="Selection strategy",
                allowed_values=["balanced", "random", "adaptive"],
            ),
        }

    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        result = self._apply_defaults(parameters)
        schemas = self.get_parameter_schemas()

        # Validate num_trials
        if not isinstance(result["num_trials"], int) or result["num_trials"] < 1:
            raise ValueError("num_trials must be a positive integer")

        # Validate deck_selection_strategy
        allowed = schemas["deck_selection_strategy"].allowed_values
        if allowed is not None and result["deck_selection_strategy"] not in allowed:
            raise ValueError(
                f"Invalid deck_selection_strategy: {result['deck_selection_strategy']}"
            )

        # Clamp float values to valid ranges
        for param in ["deck_stimulus_strength", "outcome_stimulus_strength", "interoceptive_gain"]:
            schema = schemas[param]
            value = float(result[param])
            if schema.min_value is not None:
                value = max(value, schema.min_value)
            if schema.max_value is not None:
                value = min(value, schema.max_value)
            result[param] = value

        return result


class MaskingParadigmStrategy(TaskStrategy):
    """Strategy for Masking Paradigm Task."""

    def __init__(self) -> None:
        super().__init__(
            task_type="masking_paradigm",
            name="Masking Paradigm Task",
            description="Visual masking experiment with varying SOAs",
        )

    def get_parameter_schemas(self) -> Dict[str, ParameterSchema]:
        return {
            "target_duration_ms": ParameterSchema(
                name="target_duration_ms",
                param_type="float",
                default=50.0,
                description="Target presentation duration",
                min_value=1.0,
                max_value=1000.0,
            ),
            "soas": ParameterSchema(
                name="soas",
                param_type="array",
                default=[0, 17, 33, 50, 67, 83, 100, 150, 200, 300],
                description="SOAs to test (stimulus onset asynchronies)",
            ),
            "mask_duration_ms": ParameterSchema(
                name="mask_duration_ms",
                param_type="float",
                default=100.0,
                description="Mask presentation duration",
                min_value=1.0,
                max_value=1000.0,
            ),
            "num_trials_per_condition": ParameterSchema(
                name="num_trials_per_condition",
                param_type="integer",
                default=20,
                description="Trials per SOA",
                min_value=1,
                max_value=100,
            ),
            "target_strength": ParameterSchema(
                name="target_strength",
                param_type="float",
                default=2.0,
                description="Target stimulus strength",
                min_value=0.1,
                max_value=10.0,
            ),
            "mask_strength": ParameterSchema(
                name="mask_strength",
                param_type="float",
                default=3.0,
                description="Mask stimulus strength",
                min_value=0.1,
                max_value=10.0,
            ),
        }

    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        result = self._apply_defaults(parameters)
        schemas = self.get_parameter_schemas()

        # Validate soas is a list of numbers
        if not isinstance(result["soas"], list):
            raise ValueError("soas must be a list")
        if not all(isinstance(x, (int, float)) for x in result["soas"]):
            raise ValueError("soas must contain only numbers")

        # Validate numeric ranges
        for param in ["target_duration_ms", "mask_duration_ms", "target_strength", "mask_strength"]:
            schema = schemas[param]
            value = float(result[param])
            if schema.min_value is not None:
                value = max(value, schema.min_value)
            if schema.max_value is not None:
                value = min(value, schema.max_value)
            result[param] = value

        return result


class AttentionalBlinkStrategy(TaskStrategy):
    """Strategy for Attentional Blink Task."""

    def __init__(self) -> None:
        super().__init__(
            task_type="attentional_blink",
            name="Attentional Blink Task",
            description="RSVP task measuring attentional blink effect",
        )

    def get_parameter_schemas(self) -> Dict[str, ParameterSchema]:
        return {
            "stream_length": ParameterSchema(
                name="stream_length",
                param_type="integer",
                default=15,
                description="Number of items in RSVP stream",
                min_value=5,
                max_value=50,
            ),
            "item_duration_ms": ParameterSchema(
                name="item_duration_ms",
                param_type="float",
                default=100.0,
                description="Duration of each item",
                min_value=10.0,
                max_value=500.0,
            ),
            "num_trials_per_lag": ParameterSchema(
                name="num_trials_per_lag",
                param_type="integer",
                default=20,
                description="Trials per lag condition",
                min_value=1,
                max_value=100,
            ),
            "lags": ParameterSchema(
                name="lags",
                param_type="array",
                default=[1, 2, 3, 4, 8],
                description="Lags to test",
            ),
            "target_salience": ParameterSchema(
                name="target_salience",
                param_type="float",
                default=2.0,
                description="Target salience boost",
                min_value=0.1,
                max_value=10.0,
            ),
        }

    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        result = self._apply_defaults(parameters)

        # Validate lags
        if not isinstance(result["lags"], list):
            raise ValueError("lags must be a list")
        if not all(isinstance(x, int) for x in result["lags"]):
            raise ValueError("lags must contain only integers")

        return result


class ChangeBlindnessStrategy(TaskStrategy):
    """Strategy for Change Blindness Task."""

    def __init__(self) -> None:
        super().__init__(
            task_type="change_blindness",
            name="Change Blindness Task",
            description="Flicker paradigm for change detection",
        )

    def get_parameter_schemas(self) -> Dict[str, ParameterSchema]:
        return {
            "image_size": ParameterSchema(
                name="image_size",
                param_type="array",
                default=[256, 256],
                description="Image dimensions",
            ),
            "change_magnitude": ParameterSchema(
                name="change_magnitude",
                param_type="float",
                default=0.3,
                description="Magnitude of change",
                min_value=0.0,
                max_value=1.0,
            ),
            "flicker_duration_ms": ParameterSchema(
                name="flicker_duration_ms",
                param_type="float",
                default=100.0,
                description="Flicker duration",
                min_value=10.0,
                max_value=1000.0,
            ),
            "num_trials": ParameterSchema(
                name="num_trials",
                param_type="integer",
                default=50,
                description="Number of trials",
                min_value=1,
                max_value=500,
            ),
        }

    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        result = self._apply_defaults(parameters)

        # Validate image_size
        if not isinstance(result["image_size"], list) or len(result["image_size"]) != 2:
            raise ValueError("image_size must be a list of two integers [width, height]")
        if not all(isinstance(x, int) and x > 0 for x in result["image_size"]):
            raise ValueError("image_size values must be positive integers")

        return result


class BinocularRivalryStrategy(TaskStrategy):
    """Strategy for Binocular Rivalry Task."""

    def __init__(self) -> None:
        super().__init__(
            task_type="binocular_rivalry",
            name="Binocular Rivalry Task",
            description="Binocular rivalry with competing patterns",
        )

    def get_parameter_schemas(self) -> Dict[str, ParameterSchema]:
        return {
            "pattern_size": ParameterSchema(
                name="pattern_size",
                param_type="array",
                default=[256, 256],
                description="Pattern dimensions",
            ),
            "contrast_left": ParameterSchema(
                name="contrast_left",
                param_type="float",
                default=1.0,
                description="Left eye contrast",
                min_value=0.0,
                max_value=1.0,
            ),
            "contrast_right": ParameterSchema(
                name="contrast_right",
                param_type="float",
                default=1.0,
                description="Right eye contrast",
                min_value=0.0,
                max_value=1.0,
            ),
            "duration_seconds": ParameterSchema(
                name="duration_seconds",
                param_type="float",
                default=60.0,
                description="Trial duration",
                min_value=1.0,
                max_value=600.0,
            ),
            "sampling_rate_hz": ParameterSchema(
                name="sampling_rate_hz",
                param_type="float",
                default=30.0,
                description="Sampling rate",
                min_value=1.0,
                max_value=120.0,
            ),
        }

    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        result = self._apply_defaults(parameters)

        # Validate pattern_size
        if not isinstance(result["pattern_size"], list) or len(result["pattern_size"]) != 2:
            raise ValueError("pattern_size must be a list of two integers [width, height]")
        if not all(isinstance(x, int) and x > 0 for x in result["pattern_size"]):
            raise ValueError("pattern_size values must be positive integers")

        # Clamp contrast values
        for param in ["contrast_left", "contrast_right"]:
            result[param] = max(0.0, min(1.0, float(result[param])))

        return result


class TaskStrategyRegistry:
    """
    Registry for task strategies.

    Provides centralized access to all available task execution strategies.
    """

    def __init__(self) -> None:
        self._strategies: Dict[str, TaskStrategy] = {}
        self._register_default_strategies()

    def _register_default_strategies(self) -> None:
        """Register all built-in task strategies."""
        strategies: List[TaskStrategy] = [
            IowaGamblingStrategy(),
            MaskingParadigmStrategy(),
            AttentionalBlinkStrategy(),
            ChangeBlindnessStrategy(),
            BinocularRivalryStrategy(),
        ]

        for strategy in strategies:
            self.register(strategy)

    def register(self, strategy: TaskStrategy) -> None:
        """
        Register a task strategy.

        Args:
            strategy: The strategy to register

        Raises:
            ValueError: If task_type is already registered
        """
        if strategy.task_type in self._strategies:
            raise ValueError(f"Task type '{strategy.task_type}' is already registered")
        self._strategies[strategy.task_type] = strategy

    def get(self, task_type: str) -> Optional[TaskStrategy]:
        """
        Get a task strategy by type.

        Args:
            task_type: The task type identifier

        Returns:
            The strategy if found, None otherwise
        """
        return self._strategies.get(task_type)

    def get_all(self) -> List[TaskStrategy]:
        """
        Get all registered strategies.

        Returns:
            List of all registered strategies
        """
        return list(self._strategies.values())

    def is_valid_task_type(self, task_type: str) -> bool:
        """
        Check if a task type is valid/registered.

        Args:
            task_type: The task type to check

        Returns:
            True if the task type is valid
        """
        return task_type in self._strategies

    def get_allowed_task_types(self) -> List[str]:
        """
        Get list of all allowed task types.

        Returns:
            List of task type identifiers
        """
        return list(self._strategies.keys())


# Global registry instance
_task_strategy_registry: Optional[TaskStrategyRegistry] = None


def get_task_strategy_registry() -> TaskStrategyRegistry:
    """Get the global task strategy registry (singleton)."""
    global _task_strategy_registry
    if _task_strategy_registry is None:
        _task_strategy_registry = TaskStrategyRegistry()
    return _task_strategy_registry
