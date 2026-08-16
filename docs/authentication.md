# Authentication

Authentication is delegated to an OpenID Connect provider. A component never
issues or verifies a local password; it reads an access token and maps the
claims it carries onto Django's `User` and `Group` model.

## The claims contract

Which claims carry that information is **configuration, not code**, so a
component can be pointed at any IdP's taxonomy without a change to the source.
Four environment variables hold it:

| Variable | What it names |
| --- | --- |
| `COMPONENT_IDENTITY_CLAIM` | The claim holding the IdP subject — the stable identity key |
| `COMPONENT_GROUP_CLAIM` | The claim holding the caller's groups |
| `COMPONENT_STAFF_GROUP` | The group that confers `is_staff` |
| `COMPONENT_SUPERUSER_GROUP` | The group that confers `is_superuser` |

Each variable holds a **name**, never a value. `COMPONENT_GROUP_CLAIM` is the
name of the claim that carries groups, not a group; `COMPONENT_STAFF_GROUP` is
the name of the group that confers staff, not a boolean.

The two claim variables accept a dotted path, which is what lets one component
read `groups`, another read `roles`, and a third read `realm_access.roles` with
no code change between them. A claim name is tried as a literal key before it is
split on dots, so a namespaced name that contains dots of its own —
`https://example.com/roles`, or an Azure AD schema URI — is read as written.

A value that is blank, or blank after stripping, is treated as unset rather than
as a name. A group claim whose value is not a name or a list of names — an
object, a null, a boolean — is read as absent, so a malformed claim denies
rather than admitting a caller with a nonsense group.

No value is shown here on purpose. **Nothing is defaulted** — not `sub`, not
`groups`, not `roles`. An unset variable means the contract is unconfigured, and
a deployed component will refuse to start on an unconfigured contract once the
startup checks land. Defaulting a conventional name would turn a missing
configuration into a plausible-looking wrong one, which presents as a
permissions bug rather than as a misconfiguration.

No pixi task sets these variables yet: today a component with an unconfigured
contract starts normally and the contract is inert. When local values arrive
they belong in a task's own `env` table in `pixi.toml` — never in
`[activation.env]`, where a local convenience would leak into every environment.

The contract is read once, in `config/settings/base.py`, into the
`CLAIMS_CONTRACT` setting; `config/authorization/claims.py` holds the reader.
