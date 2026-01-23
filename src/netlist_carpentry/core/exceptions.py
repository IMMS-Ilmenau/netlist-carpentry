"""A collection of custom exceptions for several error cases that may occur."""


class CircuitStructureError(Exception):
    """Base class for all exceptions related to circuit structure issues."""

    pass


class StructureMismatchError(CircuitStructureError):
    """Raised when two objects should have a matching structure but actually differ, e.g. in regards to their interface."""

    pass


class WidthMismatchError(StructureMismatchError):
    """Raised when a wire's width does not match the port's width or vice versa."""

    pass


class MultipleDriverError(CircuitStructureError):
    """Raised whenever two driver signals attempt to drive the same wire."""

    pass


class AlreadyConnectedError(CircuitStructureError):
    """Raised when attempting to connect a port that is already connected."""

    pass


class InvalidDirectionError(CircuitStructureError):
    """Raised when a port with an invalid direction is passed."""

    pass


class ObjectLockedError(CircuitStructureError):
    """Raised when attempting to modify a locked (temporarily immutable) object."""

    pass


class SingleOwnershipError(CircuitStructureError):
    """Raised when an object is already owned by a certain container and cannot be added to another container."""

    pass


class IdentifierConflictError(CircuitStructureError):
    """Raised when an object with a duplicate identifier (usually an already existing name) is created."""

    pass


class ObjectNotFoundError(CircuitStructureError, LookupError):
    """Raised when a requested object does not exist in the circuit."""


class ParentNotFoundError(ObjectNotFoundError):
    """Raised when the parent is requested for an object, but no parent exists."""


class PathResolutionError(ObjectNotFoundError):
    """Raised when a circuit path cannot be resolved."""


class DetachedSegmentError(CircuitStructureError):
    """Raised when a segment object is created without a parent element."""


class UnsupportedOperationError(ValueError):
    """Raised when an operation is not supported for a given instance type."""

    pass


class SplittingUnsupportedError(UnsupportedOperationError):
    """Raised when attempting to split an unsplittable instance."""

    pass


class SignalError(Exception):
    """Base class for all exceptions related to signal issues."""

    pass


class EvaluationError(SignalError):
    """Base class for all exceptions arising during signal evaluation."""

    pass


class InvalidSignalError(SignalError):
    """Raised when an invalid signal is provided."""

    pass


class NetTypeError(SignalError):
    """Raised when the wrong net type is provided, e.g. `wire` instead of `reg`."""

    pass


class SignalAssignmentError(SignalError):
    """Raised when a signal cannot be assigned due to various reasons."""

    pass


class VerilogSyntaxError(SyntaxError):
    """Raised whenever a Syntax Error with Verilog code occurs."""

    pass


class VcdLoadingError(Exception):
    """Raised whenever a VCD file could not be loaded."""

    pass


class MaxRetriesExceededError(RuntimeError):
    """Raised when the maximum number of retries has been exceeded."""

    pass
