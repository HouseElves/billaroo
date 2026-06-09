"""In-memory simulation state.

A SimulationState is the frozen snapshot of all domain objects produced
by a single simulation run (or a single population-build step).  It
uses the shared ``_Validated`` mix-in (D30) so that structural checks
— element types, ID uniqueness, cross-referential integrity — are
collected into one ``InvalidRequestError`` per constitution rule 23.

SimulationState is **not** a contract module.  It lives under
``simulate/`` because it is owned by the simulation engine, not by the
domain vocabulary.  It imports contract types to declare its fields but
does not perform semantic catalog validation — that responsibility
stays in the model builders.
"""

from __future__ import annotations

import dataclasses
from typing import ClassVar

from synthetic_billing._validation import CheckSpec, CheckTuple, _Validated
from synthetic_billing.contracts.account_contracts import Account
from synthetic_billing.contracts.subscriber_contracts import Subscriber
from synthetic_billing.contracts.subscription_contracts import Subscription

__all__ = ["SimulationState"]


@dataclasses.dataclass(frozen=True)
class SimulationState(_Validated):
    """Frozen snapshot of accounts, subscribers, and subscriptions.

    Structural validation checks:

    - Each element of ``accounts`` is an ``Account`` instance.
    - Each element of ``subscribers`` is a ``Subscriber`` instance.
    - Each element of ``subscriptions`` is a ``Subscription`` instance.
    - Account IDs are unique within the tuple.
    - Subscriber IDs are unique within the tuple.
    - Subscription IDs are unique within the tuple.
    - Every ``Subscriber.account_id`` resolves to an account.
    - Every ``Subscription.subscriber_id`` resolves to a subscriber.
    """

    accounts: tuple[Account, ...]
    subscribers: tuple[Subscriber, ...]
    subscriptions: tuple[Subscription, ...]

    _type_check_specs: ClassVar[tuple[CheckSpec, ...]] = (
        ("accounts", tuple),
        ("subscribers", tuple),
        ("subscriptions", tuple),
    )

    # The structural-checks body holds several local references — the
    # safely-iterable tuples, the valid-typed subsets, the ID lists, and
    # the ID sets used for cross-reference lookup.  Each name documents
    # a stage of the check pipeline; collapsing them would obscure the
    # "filter then check" structure that constitution rule 23 requires.
    def _structural_checks(self) -> tuple[CheckTuple, ...]:  # pylint: disable=too-many-locals
        """Return structural validation checks for this simulation state.

        Top-level tuple-ness is checked here as well as by
        ``_type_check_specs`` so that direct-construction instances
        (which bypass ``create_validated`` and therefore the constructor
        type checks) are reported as invalid rather than silently
        passing.  Per constitution rule 23, dependent checks (element
        types, uniqueness, cross-references) are skipped only for the
        top-level fields that are not safely iterable; correctly-typed
        fields still surface their own violations.
        """
        checks: list[CheckTuple] = [
            (
                isinstance(self.accounts, tuple),
                "accounts",
                self.accounts,
            ),
            (
                isinstance(self.subscribers, tuple),
                "subscribers",
                self.subscribers,
            ),
            (
                isinstance(self.subscriptions, tuple),
                "subscriptions",
                self.subscriptions,
            ),
        ]

        accounts = self.accounts if isinstance(self.accounts, tuple) else ()
        subscribers = (
            self.subscribers if isinstance(self.subscribers, tuple) else ()
        )
        subscriptions = (
            self.subscriptions if isinstance(self.subscriptions, tuple) else ()
        )

        # --- element type checks ---
        for index, account in enumerate(accounts):
            checks.append(
                (
                    isinstance(account, Account),
                    f"accounts[{index}]",
                    account,
                )
            )
        for index, subscriber in enumerate(subscribers):
            checks.append(
                (
                    isinstance(subscriber, Subscriber),
                    f"subscribers[{index}]",
                    subscriber,
                )
            )
        for index, subscription in enumerate(subscriptions):
            checks.append(
                (
                    isinstance(subscription, Subscription),
                    f"subscriptions[{index}]",
                    subscription,
                )
            )

        # --- code-level checks run over the valid-typed subsets ---
        valid_accounts = [
            a for a in accounts if isinstance(a, Account)
        ]
        valid_subscribers = [
            s for s in subscribers if isinstance(s, Subscriber)
        ]
        valid_subscriptions = [
            s for s in subscriptions if isinstance(s, Subscription)
        ]

        # ID uniqueness
        account_ids = [a.account_id for a in valid_accounts]
        checks.append(
            (
                len(account_ids) == len(set(account_ids)),
                "accounts",
                account_ids,
            )
        )

        subscriber_ids = [s.subscriber_id for s in valid_subscribers]
        checks.append(
            (
                len(subscriber_ids) == len(set(subscriber_ids)),
                "subscribers",
                subscriber_ids,
            )
        )

        subscription_ids = [s.subscription_id for s in valid_subscriptions]
        checks.append(
            (
                len(subscription_ids) == len(set(subscription_ids)),
                "subscriptions",
                subscription_ids,
            )
        )

        # Cross-referential integrity
        account_id_set = set(account_ids)
        for subscriber in valid_subscribers:
            checks.append(
                (
                    subscriber.account_id in account_id_set,
                    f"subscribers.{subscriber.subscriber_id}.account_id",
                    subscriber.account_id,
                )
            )

        subscriber_id_set = set(subscriber_ids)
        for subscription in valid_subscriptions:
            checks.append(
                (
                    subscription.subscriber_id in subscriber_id_set,
                    f"subscriptions.{subscription.subscription_id}"
                    f".subscriber_id",
                    subscription.subscriber_id,
                )
            )

        return tuple(checks)
