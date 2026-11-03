"""Pure profile application boundary.

Persistence orchestration lives in ``service.py``. Downstream capabilities
consume immutable domain snapshots instead of importing profile persistence.
"""
