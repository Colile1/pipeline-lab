# Error types shared across the app and surfaced verbatim to the UI.


class ConfigValidationError(ValueError):
    """Raised when a wizard form cannot become a valid engine config.

    Purpose: carry a specific, actionable reason (naming the offending
    field and the allowed values) that an API layer can show to a
    non-technical user instead of a bare 500.
    Inputs: message - the reason, phrased for a UI reader.
    Output: an exception instance.
    """


class UploadValidationError(ValueError):
    """Raised when an uploaded CSV cannot be registered as a dataset.

    Purpose: carry a specific, actionable reason (naming the offending
    column or value) that the upload route can show to a non-technical
    user instead of a bare 500.
    Inputs: message - the reason, phrased for a UI reader.
    Output: an exception instance.
    """


class DatasetRegistrationError(RuntimeError):
    """Raised when an engine's own registration step fails.

    Purpose: carry the engine's own error line when its registration
    script exits non-zero, so the failure is reported, never hidden.
    Inputs: message - the engine's error text.
    Output: an exception instance.
    """


class RunLaunchError(RuntimeError):
    """Raised when a run cannot be launched at all.

    Purpose: distinguish "never started" (bad config path, interpreter
    missing) from a run that started and later failed mid-flight, which
    is reported by run_status instead.
    Inputs: message - the reason, phrased for a UI reader.
    Output: an exception instance.
    """


class ConfigNameConflictError(ValueError):
    """Raised when a config filename would overwrite an existing file.

    Purpose: a slugged experiment name can collide with an existing
    config in the same directory — including a pre-registered one, such
    as scaling_arm.yaml — so writing must never silently replace it.
    Inputs: message - the reason, naming the path that already exists.
    Output: an exception instance.
    """


class ResultsExtractionError(RuntimeError):
    """Raised when an engine's own results-extraction step fails.

    Purpose: carry the engine's own error line when extracting a run's
    results from that engine's store (e.g. b2's MLflow db) fails, so the
    failure is reported rather than silently returning no results.
    Inputs: message - the engine's error text.
    Output: an exception instance.
    """
