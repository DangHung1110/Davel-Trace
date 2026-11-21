"""Transport- and persistence-free identity application contracts."""

from __future__ import annotations

from dataclasses import dataclass

from BE.app.modules.identity.domain import Principal


@dataclass(frozen=True)
class AuthorizationPolicy:
    roles: frozenset[str]

    def allows(self, principal: Principal) -> bool:
        return bool(self.roles.intersection(principal.roles))


TRAVELER_POLICY = AuthorizationPolicy(
    frozenset({"traveler", "data_curator", "administrator"})
)
