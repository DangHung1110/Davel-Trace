# Identity capability

Owns accounts, roles, sessions, email verification, password recovery,
account export and deletion lifecycle. Other business modules receive a
`Principal`; they must not query identity tables or handle credential hashes.

The development outbox is available only in demo/test mode when explicitly
enabled. It is not an email-provider implementation.
