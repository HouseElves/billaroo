"""Tests for synthetic_billing.model.lifecycle_model."""

import pytest

from synthetic_billing.actions.lifecycle_actions import CancelSubscriberIntent
from synthetic_billing.model.lifecycle_model import (
    build_subscriber_cancelled_event,
)
from synthetic_billing.simulate.simulation_state import SimulationState


class TestBuildSubscriberCancelledEventStub:
    """The lifecycle event builder is intentionally unimplemented (D38)."""

    def test_raises_not_implemented(self) -> None:
        """The function raises NotImplementedError immediately."""
        state = SimulationState.create_validated((), (), ())
        intent = CancelSubscriberIntent.create_validated(2, "subscriber-001")
        with pytest.raises(NotImplementedError):
            build_subscriber_cancelled_event(state, intent)

    def test_message_names_the_function(self) -> None:
        """The exception message names the function and its status."""
        state = SimulationState.create_validated((), (), ())
        intent = CancelSubscriberIntent.create_validated(2, "subscriber-001")
        with pytest.raises(NotImplementedError) as exc_info:
            build_subscriber_cancelled_event(state, intent)
        message = str(exc_info.value)
        assert "build_subscriber_cancelled_event" in message
        assert "not implemented" in message
