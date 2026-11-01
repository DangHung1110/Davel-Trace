# Authorization Contract

## Roles

| Capability | Guest | Traveler | Data curator | Administrator | Suspended/deletion pending |
|------------|-------|----------|--------------|---------------|----------------------------|
| Register, verify, recover | Allowed | N/A | N/A | N/A | Recovery/cancel only when eligible |
| View own account/sessions | No | Own only | Own only | Own only | No |
| Revoke own sessions | No | Own only | Own only | Own only | No |
| Request own export/deletion | No | Own only | Own only | Own only | Cancel deletion only |
| Traveler-owned future data | No | Own only | Own only | Own only unless later spec grants audit scope | No |
| Catalog curation (future) | No | No | Allowed | Allowed | No |
| User-status administration (future) | No | No | No | Allowed | No |

## Enforcement rules

1. The backend derives account, session, and roles from the current credential; it ignores role/account identifiers supplied by the client for authorization.
2. Every protected use case declares required roles and ownership scope. Missing declarations deny by default.
3. Current account status and active role assignments are read during authorization; stale credential claims cannot preserve removed access.
4. Cross-account private identifiers yield the same public not-found behavior as unknown identifiers unless the caller has an explicitly specified administrative capability.
5. Denied privileged attempts create safe audit evidence; normal unknown-resource probes do not reveal ownership.
6. AI output, planner input, demo profile identifiers, and client state never grant identity permission.

## Reusable principal

Downstream modules receive a small immutable principal containing account UUID, session UUID, active roles, and correlation identifier. They do not receive password hashes, credential hashes, action records, or identity repository access.
