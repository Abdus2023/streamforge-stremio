# Control Plane

[⇧ Architecture index](../architecture.md) · [⇆ Document map](./README.md)

> **Scope.** Configuration lifecycle: config → validation → policy → admission → generation → snapshot → publication. Covers configuration digests, secrets separation, the composition root, rollback, and the generation lifecycle (`PROPOSED → VALIDATED → ADMITTED → PUBLISHED → ACTIVE → SUPERSEDED → RETIRED`). This is distinct from the runtime execution machinery described in `06-runtime.md`.

> **Primary dependencies:** `06-runtime.md`, `05-policy.md`

> **Status.** Unless a section explicitly states otherwise with a concrete repository reference (file path, commit, or CI run), everything below is **DESIGNED** or **PROPOSED** architecture, not implemented code. This document was migrated from the original `docs/architecture.md` monolith; section order is preserved from that document, numbering has been dropped in favor of descriptive headings, and some very long single sections in the monolith may appear here still bearing internal editorial framing (e.g. first-person design narration) that predates the doc-split.

## Sections in this document

- [Configuration](#configuration)
- [Configuration must not alter the domain contract](#configuration-must-not-alter-the-domain-contract)
- [Configuration model](#configuration-model)
- [Configuration admission](#configuration-admission)
- [Application composition root](#application-composition-root)
- [`src/config/config.ts`](#srcconfigconfigts)
- [Configuration Is Not Policy](#configuration-is-not-policy)
- [Artifact Identity](#artifact-identity)
- [Environment secrets](#environment-secrets)
- [Catalog index storage](#catalog-index-storage)
- [SQLite boundary](#sqlite-boundary)
- [Control plane vs data plane](#control-plane-vs-data-plane)
- [Runtime registry](#runtime-registry)
- [Configuration generation](#configuration-generation)
- [Immutable runtime snapshot](#immutable-runtime-snapshot)
- [Atomic configuration replacement](#atomic-configuration-replacement)
- [Configuration transaction](#configuration-transaction)
- [Configuration is not policy](#configuration-is-not-policy)
- [Runtime policy](#runtime-policy)
- [Policy layering](#policy-layering)
- [Feature flags](#feature-flags)
- [Operator configuration](#operator-configuration)
- [Secret provider boundary](#secret-provider-boundary)
- [Secret references](#secret-references)
- [Secret redaction](#secret-redaction)
- [Signed URLs](#signed-urls)
- [URL fingerprint](#url-fingerprint)
- [ID generation](#id-generation)
- [Namespace discipline](#namespace-discipline)
- [The complete control/data architecture](#the-complete-controldata-architecture)
- [Operator API](#operator-api)
- [Configuration generation endpoint](#configuration-generation-endpoint)
- [Runtime generation provenance](#runtime-generation-provenance)
- [Configuration digest](#configuration-digest)
- [Artifact identity](#artifact-identity)
- [This is the point to introduce a platform manifest](#this-is-the-point-to-introduce-a-platform-manifest)
- [Composition root](#composition-root)
- [Composition root pseudocode](#composition-root-pseudocode)
- [No global provider singleton](#no-global-provider-singleton)
- [Hot reload](#hot-reload)
- [Generation lifecycle](#generation-lifecycle)

---

## Configuration

Environment:

```text
PORT=7000

LOG_LEVEL=info

REQUEST_TIMEOUT_MS=3500

SOURCE_A_ENABLED=true
SOURCE_B_ENABLED=true

CACHE_TTL_SECONDS=300

PREFERRED_LANGUAGE=en
```

User-facing Stremio configuration can control:

```text
Preferred language
Preferred subtitle language
Maximum resolution
Minimum resolution
Source categories
External-service credentials
```

Credentials should never be embedded in the manifest.

Stremio's manifest supports configurable user data and configuration
fields.

## Configuration must not alter the domain contract

For example:

```text
MAX_RESOLUTION=1080p
```

should mean:

```text
eligible candidates
        ↓
configuration filter
        ↓
ranking
```

not:

```text
adapter itself behaves differently
```

This makes configuration behavior testable.

## Configuration model

Use validated environment configuration.

```ts
import { z } from "zod";

const ConfigSchema = z.object({
  PORT: z.coerce.number().int().min(1).max(65535).default(7000),

  TOTAL_TIMEOUT_MS: z.coerce.number().int().positive().default(4000),

  SOURCE_TIMEOUT_MS: z.coerce.number().int().positive().default(2500),

  MAX_CONCURRENCY: z.coerce.number().int().positive().default(6)
});
```

Then:

```ts
export const config = ConfigSchema.parse(process.env);
```

Configuration errors should fail at startup.

Not halfway through a user request.

## Configuration admission

Use a startup gate:

```text
config
    ↓
validate
    ↓
policy admission
    ↓
construct adapter
```

not:

```text
construct adapter
    ↓
discover later that configuration is unsafe
```

So:

```text
INVALID CONFIGURATION
        ↓
startup failure
```

rather than:

```text
runtime surprises
```

## Application composition root

`src/index.ts` should be the place where dependencies become concrete.

Conceptually:

```ts
const config = loadConfig();

const registry = new SourceRegistry();

registry.register(new FixtureAdapter());

const resolver = new Resolver(registry, {
  timeoutMs: config.sourceTimeoutMs,
  preferredLanguages: config.preferredLanguages
});

const streamHandler = createStreamHandler(resolver);

const manifest = createManifest();

const addon = builder.defineAddon(manifest).defineStreamHandler(streamHandler);

serveHTTP(addon);
```

This is the **composition root**.

The domain does not instantiate infrastructure.

## `src/config/config.ts`

Configuration should be explicit and validated at startup.

```ts
import { z } from "zod";

const ConfigSchema = z.object({
  PORT: z.coerce.number().int().min(1).max(65535).default(7000),

  SOURCE_TIMEOUT_MS: z.coerce.number().int().positive().default(5000),

  PREFERRED_LANGUAGES: z.string().default("en")
});

export interface Config {
  port: number;
  sourceTimeoutMs: number;
  preferredLanguages: readonly string[];
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): Config {
  const parsed = ConfigSchema.parse(env);

  return {
    port: parsed.PORT,
    sourceTimeoutMs: parsed.SOURCE_TIMEOUT_MS,
    preferredLanguages: parsed.PREFERRED_LANGUAGES.split(",")
      .map(value => value.trim())
      .filter(Boolean)
  };
}
```

This gives:

```text
environment
    ↓
schema
    ↓
validated configuration
    ↓
application
```

rather than allowing arbitrary environment variables to leak throughout
the application.

## Configuration Is Not Policy

An important distinction:

```text
SOURCE_TIMEOUT_MS=5000
```

is configuration.

But:

```text
authorization.status === "authorized"
```

is policy.

Therefore:

```text
configuration
≠
authorization
```

Changing a timeout must never accidentally alter whether a source is
permitted.

## Artifact Identity

After the image is built:

```text
image
    ↓
digest
```

Example form:

```text
sha256:<digest>
```

The release record should bind:

```text
source commit
    + package lock
    + build
    + container digest
```

into one release identity.

Conceptually:

```text
Git commit
    + package-lock.json
    + CI run
    + container digest
    ↓
ARTIFACT IDENTITY
```

That is the beginning of:

```text
ARTIFACT_BOUND
```

## Environment secrets

Never place source credentials in:

```text
SourceCandidate
```

or logs.

Instead:

```ts
interface SourceCredentialProvider {
  get(sourceId: string, signal: AbortSignal): Promise<SourceCredential>;
}
```

The runtime can construct a scoped adapter context:

```text
sourceId
   │
   ▼
credential provider
   │
   ▼
short-lived credential
   │
   ▼
HTTP request
```

Credentials should never enter:

- candidate objects,
- resolution receipts,
- normal logs,
- Stremio responses.

## Catalog index storage

For v0.1, a deterministic JSON/SQLite-backed index is sufficient.

Possible evolution:

```text
v0.1 JSON index
v0.2 SQLite
v0.3 SQLite + FTS
v1.x optional external search index
```

Do not introduce Elasticsearch/OpenSearch merely because "search"
exists.

The storage engine should follow actual requirements.

## SQLite boundary

If SQLite becomes necessary, isolate it:

```text
CatalogRepository
      │
      ▼
SQLite
```

The application layer sees:

```ts
interface CatalogRepository {
  getPage(...): Promise<Page<CatalogEntry>>;
  search(...): Promise<readonly CatalogEntry[]>;
}
```

It should not see SQL statements.

## Control plane vs data plane

Separate the architecture into two planes.

```text
                    ADDON PLATFORM
                          │
              ┌───────────┴───────────┐
              │                       │
        CONTROL PLANE             DATA PLANE
              │                       │
        declarations              requests
        admission                 resolution
        configuration              providers
        policy                    candidates
        registry                  metadata
        lifecycle                 subtitles
        evidence                  catalog
        health
```

The distinction is fundamental.

### Control plane

Answers:

```text
What providers exist?
Which are admitted?
What capabilities do they declare?
What policies apply?
What configuration is active?
What version is running?
```

### Data plane

Answers:

```text
Given this request, what can the system return?
```

A stream request should not modify provider admission.

## Runtime registry

The registry becomes a snapshot of admitted configuration.

```ts
interface RuntimeRegistry {
  readonly generation: string;

  readonly sources: readonly SourceAdapter[];

  readonly metadata: readonly MetadataProvider[];

  readonly subtitles: readonly SubtitleProvider[];

  readonly catalogs: readonly CatalogProvider[];
}
```

The critical addition is:

```text
generation
```

## Configuration generation

Suppose the operator changes:

```text
source A enabled
```

to:

```text
source A disabled
```

Requests already executing should not unpredictably observe half of
the old configuration and half of the new one.

Instead:

```text
Generation 41
    │
    ├── request A
    ├── request B
    └── request C

configuration update

Generation 42
    │
    ├── request D
    └── request E
```

Each request gets a stable runtime snapshot.

## Immutable runtime snapshot

> **See the normative contract:** [`docs/contracts/runtime.md`](../contracts/runtime.md) defines `RuntimeSnapshot`, `ConfigurationTransaction`, and `RuntimePolicy` once, authoritatively.

```ts
interface RuntimeSnapshot {
  readonly generation: string;

  readonly createdAt: string;

  readonly sources: readonly AdmittedSource[];

  readonly metadata: readonly AdmittedMetadataProvider[];

  readonly subtitles: readonly AdmittedSubtitleProvider[];

  readonly catalogs: readonly AdmittedCatalogProvider[];

  readonly policy: RuntimePolicy;
}
```

Once published:

```text
RuntimeSnapshot
```

is immutable.

This makes request behavior much easier to reason about.

## Atomic configuration replacement

The control plane should produce:

```text
Candidate Configuration
        ↓
Schema validation
        ↓
Provider declaration validation
        ↓
Admission evaluation
        ↓
Policy validation
        ↓
RuntimeSnapshot
        ↓
ATOMIC PUBLISH
```

Never:

```text
modify provider A
modify provider B
modify provider C
...
```

incrementally in the live registry.

That creates mixed generations.

## Configuration transaction

Conceptually:

```ts
interface ConfigurationTransaction {
  readonly baseGeneration: string;

  readonly proposedGeneration: string;

  validate(): Promise<ConfigurationValidation>;

  commit(): Promise<RuntimeSnapshot>;
}
```

The commit operation should fail if:

```text
baseGeneration !== currentlyPublishedGeneration
```

This gives us optimistic concurrency control.

## Configuration is not policy

Keep:

```text
Configuration
```

separate from:

```text
Policy
```

For example:

```text
configuration:
  timeout = 5000ms

policy:
  unauthorized candidate = reject
```

Changing the timeout does not redefine authorization.

## Runtime policy

```ts
interface RuntimePolicy {
  readonly candidateAuthorization: "required";

  readonly allowUnknownAuthorization: false;

  readonly allowHttpPlayback: boolean;

  readonly maxCatalogPageSize: number;

  readonly maxCandidateCount: number;

  readonly maxRedirects: number;
}
```

Again, these values are illustrative.

The architecture should not hard-code them as universally correct
production settings.

## Policy layering

There should not be one giant policy function.

Use layers:

```text
Global policy
      ↓
Resource policy
      ↓
Provider policy
      ↓
Request policy
      ↓
Candidate policy
```

Example:

```text
global:
  unknown authorization rejected

source:
  HTTP forbidden

request:
  preferred language = fr

candidate:
  direct playback = true
```

Each layer has a defined responsibility.

## Feature flags

Feature flags should not silently bypass gates.

Bad:

```text
ENABLE_UNSAFE_SOURCE=true
```

Better:

```text
feature:
  subtitle-v1 = enabled

admission:
  provider must still satisfy authorization
```

A feature flag can enable a capability.

It should not manufacture authorization.

## Operator configuration

Separate secrets from ordinary configuration.

```text
config/
    public settings
    policy

secrets/
    API tokens
    credentials
```

Never put secrets into:

```text
manifest
logs
candidate provenance
receipts
catalog entries
error messages
```

## Secret provider boundary

```ts
interface SecretProvider {
  get(secretRef: string): Promise<string>;
}
```

Providers receive scoped access:

```text
SourceCredentialProvider
```

rather than:

```text
process.env
```

directly.

This prevents adapters from becoming configuration authorities.

## Secret references

Configuration contains:

```json
{
  "credentialRef": "secret://owned-media/token"
}
```

not:

```json
{
  "token": "actual-secret"
}
```

The runtime resolves the reference only when necessary.

## Secret redaction

Create one canonical redactor.

```ts
interface SecretRedactor {
  redact(value: unknown): unknown;
}
```

Redaction should apply to:

```text
logs
errors
receipts
diagnostics
metrics labels
HTTP headers
URLs
```

Especially:

```text
Authorization
Cookie
Set-Cookie
API keys
Bearer tokens
signed URLs
```

## Signed URLs

This creates an important distinction.

A playback URL may itself contain sensitive authorization material:

```text
https://media.example/path?token=...
```

Therefore:

```text
candidate.url
```

can be usable by Stremio but must not necessarily be persisted in
plaintext.

The system may need:

```ts
interface CandidateEvidence {
  readonly urlFingerprint: string;
  readonly urlStored: boolean;
}
```

rather than storing the raw URL in long-lived evidence.

## URL fingerprint

For evidence:

```text
sha256(canonicalPlaybackURL)
```

can identify that two observations refer to the same URL without
persisting the URL itself.

But this fingerprint is not reversible proof of ownership or
authorization.

It is merely an identifier.

## ID generation

Separate:

```text
identity
```

from:

```text
receipt ID
```

from:

```text
candidate ID
```

A candidate ID should be deterministic where possible:

```text
hash(
  canonical media key
  +
  canonical URL
  +
  provider
)
```

This improves deduplication and replay.

## Namespace discipline

A good identifier format:

```text
evidence:sha256:...
candidate:sha256:...
media:...
receipt:...
generation:...
```

This makes accidental cross-domain use easier to detect.

## The complete control/data architecture

```text
                         CONTROL PLANE
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
        Configuration        Policy          Admission
              │                │                │
              └────────────────┼────────────────┘
                               ▼
                        RuntimeSnapshot
                               │
 ══════════════════════════════╪══════════════════════════════
                               │
                           DATA PLANE
                               │
                             Request
                               │
                               ▼
                            Identity
                               │
                               ▼
                        CanonicalMedia
                               │
             ┌─────────────────┼─────────────────┐
             ▼                 ▼                 ▼
          Catalog           Metadata          Playback
                                                 │
                                           ┌─────┴─────┐
                                           ▼           ▼
                                        Streams     Subtitles
             │                 │                 │
             └─────────────────┼─────────────────┘
                               ▼
                           Observations
                               │
                               ▼
                        Functional Core
                               │
                               ▼
                          Derived Views
                               │
                               ▼
                            Stremio
```

## Operator API

The control plane can eventually expose:

```text
/internal/providers
/internal/providers/{id}
/internal/config
/internal/generations
/internal/evidence
/internal/replay
/internal/catalog/rebuild
```

These endpoints must be authenticated and preferably
network-isolated.

They should never be advertised in the Stremio manifest.

## Configuration generation endpoint

An operator could inspect:

```json
{
  "generation": "42",
  "createdAt": "...",
  "providers": 7,
  "sources": 2,
  "metadata": 3,
  "subtitles": 2
}
```

This is useful operationally.

But it should be treated as a **derived runtime view**.

The authoritative configuration remains the configuration artifact
that produced generation 42.

## Runtime generation provenance

Every receipt should reference:

```text
generation = "42"
```

Therefore:

```text
request
   ↓
generation 42
   ↓
provider set
   ↓
result
```

A later investigation can determine which provider configuration was
active.

## Configuration digest

Compute a digest over canonical configuration:

```ts
interface ConfigurationIdentity {
  readonly generation: string;

  readonly digest: string;

  readonly schemaVersion: string;
}
```

The digest should exclude secrets.

For example:

```text
provider declaration + capabilities + policy + limits
```

but not:

```text
actual API token
```

## Artifact identity

The release artifact itself should eventually have:

```text
source commit
package-lock digest
build metadata
container digest
configuration schema
```

This creates:

```text
CODE
  ↓
BUILD
  ↓
ARTIFACT
  ↓
CONFIGURATION
  ↓
GENERATION
  ↓
REQUEST
  ↓
RESULT
```

Now an observed stream can be traced back through the complete system
lineage.

## This is the point to introduce a platform manifest

There are now two different manifests:

### Stremio manifest

Protocol-facing:

```text
/manifest.json
```

### Platform manifest

System-facing:

```ts
interface PlatformManifest {
  readonly schemaVersion: string;

  readonly platformVersion: string;

  readonly capabilities: readonly string[];

  readonly providers: readonly string[];

  readonly configurationDigest: string;
}
```

Do not confuse them.

```text
Stremio manifest
    = client capability contract

Platform manifest
    = runtime composition identity
```

## Composition root

All of this finally converges at the composition root.

```text
src/index.ts

Config
   ↓
Policy
   ↓
SecretProvider
   ↓
HTTP runtime
   ↓
Provider declarations
   ↓
Admission
   ↓
Registries
   ↓
RuntimeSnapshot
   ↓
Application
   ↓
Protocol adapters
```

This is where dependencies are assembled.

No hidden global singleton should be necessary.

## Composition root pseudocode

```ts
const config = loadConfig();

const policy = createPolicy(config);

const secrets = createSecretProvider(config);

const runtime = createProviderRuntime({
  config,
  policy,
  secrets
});

const providers = loadProviders({
  runtime
});

const snapshot = buildRuntimeSnapshot({
  config,
  policy,
  providers
});

const application = createApplication({
  snapshot,
  runtime
});

const stremio = createStremioAdapter(application);

startStremio(stremio);
```

This is intentionally conceptual until the concrete dependency graph
is implemented and typechecked.

## No global provider singleton

Avoid:

```ts
export const providers = ...;
```

because that makes:

```text
tests
replay
multi-generation runtime
```

harder.

Instead:

```text
Application
   ↓
RuntimeSnapshot
```

makes dependencies explicit.

## Hot reload

If configuration reload is eventually supported:

```text
old snapshot
     │
     │ requests continue
     ▼
new snapshot published
     │
     ▼
new requests
```

Do not mutate the old snapshot.

Garbage collection can eventually reclaim it when no requests
reference it.

## Generation lifecycle

```text
PROPOSED
   ↓
VALIDATED
   ↓
ADMITTED
   ↓
PUBLISHED
   ↓
ACTIVE
   ↓
SUPERSEDED
   ↓
RETIRED
```

A failed configuration never reaches `PUBLISHED`.
