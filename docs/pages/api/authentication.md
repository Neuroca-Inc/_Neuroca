# Authentication Model (Design-Partner Phase)

> Status: This document specifies the interim authentication model for early, design-partner deployments. It describes how headers, tokens, and roles are interpreted by the current Neuroca backend without promising a final public SaaS contract.

## Goals

- Provide a **single place** that explains how requests are authenticated today.
- Align the HTTP API surface in [`endpoints.md`](docs/pages/api/endpoints.md) with the underlying middleware and helpers in [`authentication.py`](src/neuroca/api/middleware/authentication.py:1).
- Define the semantics of API keys and JWT bearer tokens for early paying customers.
- Prepare the ground work for multi-tenancy and quota enforcement (Tasks B2–C2) without locking in an incompatible model.

## Mechanisms at a Glance

The codebase currently exposes three relevant constructs in [`authentication.py`](src/neuroca/api/middleware/authentication.py:1):

- [`JWTAuth`](src/neuroca/api/middleware/authentication.py:89): validates `Authorization: Bearer <jwt>` headers and decodes them into [`JWTPayload`](src/neuroca/api/middleware/authentication.py:70).
- [`APIKeyAuth`](src/neuroca/api/middleware/authentication.py:143): validates `X-API-Key` headers against `settings.api_keys` via [`validate_api_key()`](src/neuroca/api/middleware/authentication.py:318).
- [`authenticate_request()`](src/neuroca/api/middleware/authentication.py:336): FastAPI dependency that turns a valid JWT into a [`User`](src/neuroca/core/models/user.py:97) loaded from the user repository and attaches `request.state.user_id` / `request.state.roles`.

For design-partner deployments the supported patterns are:

1. **End-user / operator calls via JWT bearer tokens**
   - A reverse proxy or auth service issues JWTs that the API validates using [`decode_jwt_token()`](src/neuroca/api/middleware/authentication.py:257).
   - Routes that depend on `user: User = Depends(authenticate_request)` require this header.

2. **Service-to-service calls via static API keys**
   - Requests include `X-API-Key` and are validated by [`APIKeyAuth`](src/neuroca/api/middleware/authentication.py:143) and [`validate_api_key()`](src/neuroca/api/middleware/authentication.py:318).
   - Health-manipulation endpoints and future billing exporters are expected to rely on this model.

3. **Unauthenticated access (development-only)**
   - Some routes (for example basic liveness and readiness checks) deliberately avoid auth for ease of deployment.
   - Additional routes may currently be reachable without auth until Tasks B2–B3 finish wiring dependencies; production deployments must compensate via a gateway or ingress rules.

## JWT Bearer Tokens

### JWT payload schema

JWT bearer tokens are decoded into [`JWTPayload`](src/neuroca/api/middleware/authentication.py:70):

```json
{
  "sub": "<user-id>",
  "exp": 1728000000,
  "iat": 1727910000,
  "type": "access",
  "roles": ["user"],
  "session_id": "optional-session-id",
  "jti": "<unique-token-id>"
}
```

- `sub` — subject; the user identifier used by [`authenticate_request()`](src/neuroca/api/middleware/authentication.py:336) to look up a [`User`](src/neuroca/core/models/user.py:97).
- `exp` — expiry (UNIX timestamp). Tokens with `exp < now()` are rejected.
- `iat` — issued-at time (UNIX timestamp).
- `type` — token type. Access tokens must use `"access"`; refresh tokens use `"refresh"`; API-key style JWTs may use `"api_key"`.
- `roles` — list of string role identifiers (for example `"user"`, `"admin"`). These feed into [`require_roles()`](src/neuroca/api/middleware/authentication.py:398).
- `session_id` — optional session correlation identifier.
- `jti` — unique token identifier; used for potential revocation checks via [`is_token_revoked()`](src/neuroca/api/middleware/authentication.py:303).

### Headers

Clients send JWTs using the standard `Authorization` header:

```http
Authorization: Bearer <encoded-jwt-token>
```

### Issuance and rotation (design-partner phase)

During the design-partner phase, Neuroca treats JWTs as **opaque tokens issued by your own identity provider**. The backend only validates them; it does not currently issue production-grade tokens itself.

- Token signing algorithm and secret are configured via `settings.jwt_algorithm` and `settings.jwt_secret_key`.
- Your IdP (for example Auth0, Keycloak, or a custom service) must mint tokens that conform to the payload schema above.
- Rotation and revocation are handled at your IdP; Neuroca will respect short expiries and can consult revocation state via [`is_token_revoked()`](src/neuroca/api/middleware/authentication.py:303) once wired to a backing store.

For internal testing only, the helper [`generate_jwt_token()`](src/neuroca/api/middleware/authentication.py:195) can be used to mint access and refresh tokens from scripts.

## API Keys

### Header and validation

Static API keys are presented via the `X-API-Key` header and validated by [`APIKeyAuth`](src/neuroca/api/middleware/authentication.py:143):

```http
X-API-Key: <api-key-value>
```

The validator [`validate_api_key()`](src/neuroca/api/middleware/authentication.py:318) compares the presented key against `settings.api_keys` using `hmac.compare_digest` to avoid timing leaks. The mapping has the conceptual shape:

```python
settings.api_keys = {
    "design-partner-acme": "<random-32+ character secret>",
    "internal-ops": "<random-32+ character secret>",
}
```

On success `APIKeyAuth` returns the **service name** (for example `"design-partner-acme"`), which can be interpreted as a preliminary tenant or account identifier in later tasks.

### Key lifecycle (manual)

For the initial monetization step, API keys are managed manually by operators:

1. **Generate** a high-entropy random value per client (for example `openssl rand -hex 32`).
2. **Assign** a stable service name (for example `design-partner-acme`) and add an entry to `settings.api_keys` in the deployment configuration.
3. **Distribute** the resulting key to the customer via a secure channel (password manager share, one-time secret link, etc.).
4. **Rotate** keys by:
   - Adding a new key under the same logical tenant/service name and updating the deployment.
   - Communicating the new key to the customer.
   - Removing the old key after a defined overlap period.
5. **Revoke** keys by deleting the mapping entry and redeploying; subsequent requests with that key will receive `401 Unauthorized`.

Future work in Tasks B2–B3 will introduce a persistent API-key store with metadata (owner, created_at, last_used_at, status) and self-service rotation flows; this document reflects the interim manual process.

## Mapping to Endpoint Groups

The `auth` annotations in [`endpoints.md`](docs/pages/api/endpoints.md) correspond to the following expectations in the design-partner phase:

| Endpoint group | Base path | Auth column in `endpoints.md` | Recommended mechanism | Notes |
|----------------|----------|-------------------------------|------------------------|-------|
| Memory API v1 | `/api/v1/memory` | `required` | `Authorization: Bearer <jwt>` resolving to a `User` via [`authenticate_request()`](src/neuroca/api/middleware/authentication.py:336). | Routes should eventually declare `user: User = Depends(authenticate_request)`; until fully wired, protect the prefix at the gateway. |
| LLM API | `/api/llm` | `none` | Optional `X-API-Key` or JWT enforced by gateway. | Code currently does not enforce auth; production deployments **must** gate usage to avoid unbounded LLM spend. |
| Health & Readiness | `/api/health` | mixed | Basic health/readiness: unauthenticated; detailed & mutating endpoints may require API key in production (see [`health.py`](src/neuroca/api/routes/health.py:148)). | Keep basic probes public for load-balancers; lock down detailed and mutating routes. |
| Metrics API | `/api/metrics` | `required` / `admin` | JWT bearer with roles and/or scopes; alternative API key for automated exporters. | Future work will attach tenant labels using the JWT or API-key identity. |
| System / Admin API | `/api/system` | `admin` | JWT bearer tokens for operators or dedicated API keys restricted to ops tooling. | Intended for operators only; never expose publicly without strict auth. |

Until Task B3 wires these dependencies uniformly into each router, the safe default for any paid environment is:

- Mount the FastAPI app **behind** an API gateway or ingress controller.
- Require either `X-API-Key` or `Authorization: Bearer` on all `/api/*` paths at the gateway level, except for explicitly public health/readiness probes.
- Pass validated identity information through headers so that `authentication.py` can progressively assume more responsibility over time.

## Local Development vs. Monetized Environments

### Local development

- You may run the API without configuring JWT or API keys; most routes will accept unauthenticated requests in this mode.
- Use this only on a loopback interface or isolated network.
- Example from [`examples.md`](docs/pages/api/examples.md:1) assumes unauthenticated local calls to keep the quickstart simple.

### Design-partner / paying tenants

- All customer traffic **must** be authenticated using either JWT or API keys as described above.
- Memory, metrics, and system routes should be considered **sensitive** and must not be exposed without auth.
- Health routes should be split between public liveness/readiness and authenticated, detailed diagnostics.
- LLM routes must be gated to avoid abuse and unbounded resource consumption.

## Tenant and Account Model (Task B2 Baseline)

Task B2 introduces a minimal tenant/account concept used by downstream services without fully standardizing how identity providers encode tenants. The key invariants are:

- The [`User`](src/neuroca/core/models/user.py:97) model now exposes an optional `tenant_id: str | None`.
- [`authenticate_request()`](src/neuroca/api/middleware/authentication.py:336) is responsible for populating `User.tenant_id` based on your deployment's identity source (for example, a `tenant_id` or `org` claim in the JWT payload or an internal mapping from API-key service name to tenant).
- Memory operations invoked via the v1 HTTP API propagate `tenant_id` into the memory service:
  - New memories are tagged with the caller's `tenant_id` in their metadata when it is present.
  - Listing and searching memories automatically filter by both `user_id` and `tenant_id` where a tenant is set.
  - Update and delete operations enforce **cross-tenant isolation**: if both the stored record and the caller have non-null tenant IDs and they differ, the request fails with a domain-specific access error.
- When either side lacks an explicit tenant (for example, legacy single-tenant deployments), access control falls back to user-based checks only. This preserves backwards compatibility while still providing strict isolation once tenants are in use.

During the design-partner phase you are expected to:

- Decide how tenant or account identifiers are represented in your IdP or API-key configuration.
- Extend or configure [`authenticate_request()`](src/neuroca/api/middleware/authentication.py:336) so that `User.tenant_id` reflects that identifier.
- Treat `tenant_id` as the unit of isolation for metering, quota enforcement, and billing in Tasks C1–C3.

## Future Extensions (Preview)

The following items are out of scope for this document but inform the design:

- Task B2 may be extended with a persistent tenant registry, self-service provisioning, and stronger validation of `tenant_id` values at the boundary.
- Task B3 will harden role/permission checks across metrics and system routes and centralize admin vs. tenant access.
- Tasks C1–C2 will use the authenticated identity (JWT subject or API-key service name) and `tenant_id` to attribute usage metrics and enforce soft quotas.

These extensions will not change the basic header formats described here but may add required claims or labels.
