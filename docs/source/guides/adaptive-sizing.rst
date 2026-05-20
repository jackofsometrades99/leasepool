Adaptive sizing
===============

Adaptive sizing lets the manager grow and shrink idle executor pools based on a
runtime signal.

Example
-------

.. literalinclude:: ../../../examples/04_adaptive_sizing.py
   :language: python
   :caption: examples/04_adaptive_sizing.py

Sizing rule
-----------

The desired executor count is:

.. code-block:: text

   max(min_pools, ceil(size_provider() / units_per_pool))

capped by ``max_pools``.

If ``size_provider`` is omitted, the unit count is treated as zero, so the target
is ``min_pools``.

Notify changes
--------------

When your signal changes, call:

.. code-block:: python

   manager.notify_scale_changed()

This wakes the checker immediately instead of waiting for ``check_interval``.

Shrinking behavior
------------------

Idle executors above the target are shut down.

Non-expired leased executors are not revoked just because the target shrinks.
They are returned or shut down when released depending on the new target.

Failure behavior
----------------

If ``size_provider`` raises, the manager logs a debug message and treats the unit
count as zero for that check. This prevents a broken signal from crashing the
checker loop.
