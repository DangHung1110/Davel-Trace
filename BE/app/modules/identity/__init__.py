"""Identity and access capability.

Only this package may read or write identity persistence models directly.
Other capabilities consume ``Principal`` and application-level guards.
"""

from BE.app.modules.identity.domain import Principal

__all__ = ["Principal"]
