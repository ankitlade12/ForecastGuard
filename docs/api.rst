API reference
=============

The reference below is generated from the package's public signatures and
docstrings. Start with the :doc:`Python guide <PYTHON_API>` for runnable examples and
the :doc:`configuration reference <CONFIGURATION>` for field semantics.

Run checks
----------

.. autofunction:: forecastguard.run_checks

Input contracts
---------------

.. autoclass:: forecastguard.ForecastSpec

.. autoclass:: forecastguard.AvailabilitySpec

.. autoclass:: forecastguard.RevisionSpec

.. autoclass:: forecastguard.MLForecastAdapterSpec

Replay protocol
---------------

.. autoclass:: forecastguard.ReplayPipeline
   :members: predict
   :undoc-members:

Reports and results
-------------------

.. autoclass:: forecastguard.Report
   :members: exit_code, failed, has_skips

.. autoclass:: forecastguard.CheckResult
   :members: passed, failed, skipped, errored

.. autoclass:: forecastguard.Violation

.. autoclass:: forecastguard.CheckStatus
   :members:
   :undoc-members:

.. autoclass:: forecastguard.Severity
   :members:
   :undoc-members:

Pydantic contracts also support ``model_dump()``, ``model_dump_json()`` and
``model_validate_json()`` for structured serialization. The CLI's JSON and SARIF
formats are documented in the :doc:`CLI reference <CLI>`.
