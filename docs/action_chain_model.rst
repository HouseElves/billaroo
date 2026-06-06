Action Chain Model
==================

The action-chain model is the core design pattern of the simulator.

A behavior model chooses what happens to an account or subscriber.
That choice becomes a semantic intent.
The semantic intent expands into an ordered chain of actions.
The actions update simulation state and emit operational facts.

Flow
----

.. code-block:: text

    current simulation state
        -> behavior model chooses transition
            -> transition becomes semantic intent
                -> semantic intent builds action chain
                    -> action chain applies ordered actions
                        -> state updates
                        -> raw operational records
                        -> hidden truth updates

Example: Plan Upgrade
---------------------

.. code-block:: text

    subscriber has standard plan
        -> behavior chooses upgrade
            -> intent: upgrade_plan
                -> close_current_plan_subscription
                -> open_new_plan_subscription
                -> emit_subscription_event
                -> rate_prorated_charge
                -> update_hidden_truth

Action Responsibilities
-----------------------

Actions may:

- inspect current simulation state
- validate their required context
- produce state updates
- produce raw operational records
- produce hidden truth updates

Actions must not:

- call dbt
- call PostgreSQL
- write files directly
- create final gold metrics
- reach into unrelated simulator state
- call random functions directly

Action Context
--------------

An action receives explicit context.

The context should include:

- simulation month
- scenario config
- seeded random stream, when needed
- account id, when scoped to one account
- subscriber id, when scoped to one subscriber
- plan or feature codes, when relevant

Required values should be checked with explicit exceptions, not ``assert``.

Action Result
-------------

An action returns an explicit result.

The result should include:

- state updates
- emitted raw records
- hidden truth updates

The driver applies results in chain order.

Why Actions Exist
-----------------

The action layer prevents business meaning from being smeared across table
emitters.

A cancellation is not "write a row to this CSV."
A cancellation is a semantic event with operational consequences.

The table rows are evidence of the semantic action.
They are not the action itself.