"""Tests for synthetic_billing.actions.action_chain."""

import pytest

from synthetic_billing.actions.action_chain import apply_action_chain
from synthetic_billing.simulate.simulation_state import SimulationState


class TestApplyActionChainStub:
    """The ordered chain entry point is intentionally unimplemented (D38)."""

    def test_raises_not_implemented(self) -> None:
        """The function raises NotImplementedError immediately."""
        state = SimulationState.create_validated((), (), ())
        with pytest.raises(NotImplementedError):
            apply_action_chain(state, ())

    def test_message_names_the_function(self) -> None:
        """The exception message names the function and its status."""
        state = SimulationState.create_validated((), (), ())
        with pytest.raises(NotImplementedError) as exc_info:
            apply_action_chain(state, ())
        message = str(exc_info.value)
        assert "apply_action_chain" in message
        assert "not implemented" in message
