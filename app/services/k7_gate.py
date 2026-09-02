"""
K7 identifiability gate (governing doc §3.6).

The seven-dimensional latent APGI state vector
x_t = [S_t, theta_t, Pi_e, Pi_i, |eps_e|, |eps_i|, beta]
(ignition state, ignition threshold, exteroceptive/interoceptive precision,
exteroceptive/interoceptive prediction error, somatic bias) — and the raw
interoceptive telemetry it is derived from — is gated behind the K7
identifiability test. As of this writing K7 has not passed for any of these
parameters, so every one of them defaults to withheld.

This module is the single allow-list: a parameter is only exposed once it is
named in `settings.k7_cleared_parameters` (env-configured), which should only
ever be updated once the identifiability test has actually passed for that
specific parameter — never globally, and never as a blanket bypass.
"""

from enum import Enum

from app.config import settings


class K7Parameter(str, Enum):
    """Individually-gated members of the latent APGI state vector."""

    IGNITION_THRESHOLD = "ignition_threshold"  # theta_t
    PRECISION_EXTEROCEPTIVE = "precision_exteroceptive"  # Pi_e
    PRECISION_INTEROCEPTIVE = "precision_interoceptive"  # Pi_i
    PREDICTION_ERROR_EXTEROCEPTIVE = "prediction_error_exteroceptive"  # |eps_e|
    PREDICTION_ERROR_INTEROCEPTIVE = "prediction_error_interoceptive"  # |eps_i|
    SOMATIC_BIAS = "somatic_bias"  # beta
    INTEROCEPTIVE_BODY_STATE = (
        "interoceptive_body_state"  # raw substrate (heart rate, cortisol, temperature)
    )


def is_cleared(parameter: K7Parameter) -> bool:
    """Whether `parameter` has cleared the K7 identifiability test.

    Defaults to False for every parameter. Only an explicit, per-parameter
    entry in `settings.k7_cleared_parameters` can flip this to True.
    """
    return parameter.value in settings.k7_cleared_parameters
