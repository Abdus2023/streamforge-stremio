# Policy & Authorization

[⇧ Architecture index](../architecture.md) · [⇆ Document map](./README.md)

> **Scope.** The distinctions between caller authorization, media authorization, provider admission, and playback eligibility — four separate concerns that must never be collapsed into one. Establishes that `unknown` is never treated as `authorized`, and that policy exclusion happens *before* ranking, not merely as a lower rank. Owns admission, trust boundaries, and the orthogonality of catalog membership vs. identity vs. authorization vs. playback.

> **Primary dependencies:** `02-domain.md`, `03-resolution.md`

> **Status.** Unless a section explicitly states otherwise with a concrete repository reference (file path, commit, or CI run), everything below is **DESIGNED** or **PROPOSED** architecture, not implemented code. This document was migrated from the original `docs/architecture.md` monolith; section order is preserved from that document, numbering has been dropped in favor of descriptive headings, and some very long single sections in the monolith may appear here still bearing internal editorial framing (e.g. first-person design narration) that predates the doc-split.

## Sections in this document

- [Security boundary](#security-boundary)
- [Eligibility is a separate theorem](#eligibility-is-a-separate-theorem)
- [Add a policy engine](#add-a-policy-engine)
- [Policy](#policy)
- [Policy invariant](#policy-invariant)
- [Authorization boundary](#authorization-boundary)
- [Metadata provider policy](#metadata-provider-policy)
- [Security boundary map](#security-boundary-map)
- [Policy](#policy)
- [Policy invariant](#policy-invariant)
- [Admission becomes explicit](#admission-becomes-explicit)
- [Source selection policy](#source-selection-policy)
- [Identity Routing Policy](#identity-routing-policy)
- [A Critical New Invariant](#a-critical-new-invariant)
- [Source Admission: turn an adapter into an executable capability](#source-admission-turn-an-adapter-into-an-executable-capability)
- [Authorization must be evidence-bearing](#authorization-must-be-evidence-bearing)
- [Admission status](#admission-status)
- [Admission is not health](#admission-is-not-health)
- [Required identity policy](#required-identity-policy)
- [Admission engine](#admission-engine)
- [Admission algorithm](#admission-algorithm)
- [Asset authorization](#asset-authorization)
- [Multiple authorized assets](#multiple-authorized-assets)
- [Subtitle authorization](#subtitle-authorization)
- [Subtitle provider admission](#subtitle-provider-admission)
- [Catalog authorization](#catalog-authorization)
- [Catalog does not imply stream availability](#catalog-does-not-imply-stream-availability)
- [Policy evaluation](#policy-evaluation)
- [Policy precedence](#policy-precedence)
- [Security boundary](#security-boundary)
- [Threat model](#threat-model)
- [Trusted vs untrusted providers](#trusted-vs-untrusted-providers)

---

## Security boundary

Treat every source adapter as hostile input.

```text
                Internet
                    │
                    ▼
           ┌─────────────────┐
           │ Source Adapter   │
           └────────┬────────┘
                    │
              untrusted data
                    │
                    ▼
           ┌─────────────────┐
           │ Validator        │
           └────────┬────────┘
                    │
             normalized data
                    │
                    ▼
           ┌─────────────────┐
           │ Policy Engine    │
           └────────┬────────┘
                    │
                    ▼
              Stremio output
```

Validate:

- URL scheme
- hostname
- content type
- redirects
- maximum response size
- JSON structure
- timeout
- malformed metadata
- unexpected protocols

For a public deployment, also consider SSRF protection if adapters are
allowed to accept arbitrary user-configured URLs.

## Eligibility is a separate theorem

Define:

```ts
export interface EligibilityResult {
  eligible: boolean;

  reasons: string[];
}
```

Then:

```ts
export function evaluateEligibility(
  candidate: SourceCandidate
): EligibilityResult {
  const reasons: string[] = [];

  if (candidate.authorization.status !== "authorized") {
    reasons.push("source_not_authorized");
  }

  if (!candidate.capabilities.directPlayback) {
    reasons.push("direct_playback_unavailable");
  }

  if (!isHttpUrl(candidate.location.url)) {
    reasons.push("unsupported_url");
  }

  return {
    eligible: reasons.length === 0,
    reasons
  };
}
```

This gives you:

```text
OBSERVED
    ↓
NORMALIZED
    ↓
VALID
    ↓
ELIGIBLE
    ↓
RANKABLE
    ↓
EMITTABLE
```

rather than one boolean called `ready`.

## Add a policy engine

This is where deployment-specific behavior belongs.

```ts
export interface SourcePolicy {
  allow(candidate: SourceCandidate): PolicyDecision;
}
```

```ts
export interface PolicyDecision {
  allowed: boolean;
  reasons: string[];
}
```

Example:

```ts
class DefaultPolicy implements SourcePolicy {
  allow(candidate: SourceCandidate): PolicyDecision {
    const reasons: string[] = [];

    if (candidate.authorization.status !== "authorized") {
      reasons.push("authorization_not_verified");
    }

    if (!candidate.capabilities.directPlayback) {
      reasons.push("not_direct_playback");
    }

    return {
      allowed: reasons.length === 0,

      reasons
    };
  }
}
```

Now a self-hosted installation can have:

```text
StrictPolicy
UserLibraryPolicy
PublicDomainPolicy
EnterprisePolicy
```

without changing the resolver.

## Policy

```ts
// src/resolver/policy.ts

import type { SourceCandidate } from "../domain/candidate.js";

export interface PolicyDecision {
  readonly allowed: boolean;
  readonly reasons: readonly string[];
}

export function evaluatePolicy(candidate: SourceCandidate): PolicyDecision {
  const reasons: string[] = [];

  if (candidate.authorization.status !== "authorized") {
    reasons.push("authorization_not_verified");
  }

  if (!candidate.capabilities.directPlayback) {
    reasons.push("direct_playback_unavailable");
  }

  return {
    allowed: reasons.length === 0,

    reasons
  };
}
```

This is intentionally conservative.

## Policy invariant

```ts
it("never emits unknown-authorization candidates", async () => {
  const candidate = makeCandidate({
    authorization: {
      status: "unknown"
    }
  });

  const result = await resolveWith(candidate);

  expect(result.candidates).toHaveLength(0);
});
```

This should be treated as a security invariant, not merely a unit
test.

## Authorization boundary

The complete chain should now be:

```text
External source
      │
      ▼
Observation
      │
      ▼
Candidate
      │
      ▼
Authorization evidence
      │
      ▼
Policy decision
      │
      ▼
Eligible candidate
      │
      ▼
Ranking
      │
      ▼
Stremio
```

Never:

```text
URL found
    ↓
therefore authorized
```

## Metadata provider policy

Metadata sources can be treated differently from stream sources.

For example:

```text
Metadata: possibly public metadata API

Streams: only explicitly eligible/authorized sources
```

This is a useful architectural separation.

## Security boundary map

At this point:

```text
                    UNTRUSTED
                        │
              ┌─────────┴─────────┐
              │                   │
       Stremio request       Provider response
              │                   │
              ▼                   ▼
        parser/validator     schema validation
              │                   │
              └─────────┬─────────┘
                        ▼
                   domain types
                        │
                        ▼
                     policy
                        │
                        ▼
                   eligible data
                        │
                        ▼
                   presentation
```

Every boundary transforms untrusted representation into a constrained
internal representation.

## Policy

```ts
import type { SourceCandidate } from "../domain/candidate.js";

export interface PolicyDecision {
  readonly allowed: boolean;
  readonly reasons: readonly string[];
}

export function evaluatePolicy(candidate: SourceCandidate): PolicyDecision {
  const reasons: string[] = [];

  if (candidate.authorization.status !== "authorized") {
    reasons.push("authorization_not_verified");
  }

  if (!candidate.capabilities.directPlayback) {
    reasons.push("direct_playback_unavailable");
  }

  return {
    allowed: reasons.length === 0,

    reasons
  };
}
```

This is intentionally strict.

`unknown` does not become `authorized`.

## Policy invariant

```ts
it("rejects unknown authorization", async () => {
  const candidate = structuredClone(fixtureCandidate);

  candidate.authorization = {
    status: "unknown"
  };

  const adapter = new FixtureAdapter([candidate]);

  const resolver = new Resolver([adapter], config);

  const result = await resolver.resolve(candidate.media);

  expect(result.candidates).toHaveLength(0);

  expect(
    result.failures.some(failure => failure.code === "candidate_not_authorized")
  ).toBe(true);
});
```

This is one of the most important tests in the entire repository.

## Admission becomes explicit

Introduce:

```ts
export interface AdapterAdmission {
  readonly admitted: boolean;

  readonly reasons: readonly string[];

  readonly admittedAt: string;
}
```

Then:

```ts
export function admitAdapter(adapter: SourceAdapter): AdapterAdmission {
  const reasons: string[] = [];

  try {
    validateCapabilities(adapter.capabilities);
  } catch (error) {
    reasons.push(error instanceof Error ? error.message : String(error));
  }

  if (adapter.capabilities.authorizationMode === "unknown") {
    reasons.push("authorization_mode_unknown");
  }

  return {
    admitted: reasons.length === 0,

    reasons,

    admittedAt: new Date().toISOString()
  };
}
```

Notice that this is **configuration admission**, not runtime source
verification.

## Source selection policy

Routing should be deterministic.

A useful first policy:

```text
1. admitted
2. capability-compatible
3. identity-compatible
4. not circuit-open
5. within concurrency budget
6. execute
```

Don't rank sources by subjective quality yet.

First establish **eligibility**.

Then rank returned candidates.

This preserves:

```text
source selection ≠ candidate ranking
```

## Identity Routing Policy

Suppose an adapter declares:

```text
identityKinds: ["tmdb"]
```

and the request contains:

```text
IMDb: tt1234567
```

The router should ask:

```text
Do we possess a sufficiently authoritative IMDb → TMDB mapping?
```

If:

```text
YES
```

then:

```text
tt1234567
   ↓
tmdb:550
   ↓
adapter
```

If:

```text
NO
```

then:

```text
adapter not eligible
```

Not:

```text
adapter → guess title → search
```

This prevents identity guessing from silently becoming source
authorization.

## A Critical New Invariant

We can now formally state:

**A source adapter must never manufacture an identity solely to make
itself executable.**

Therefore prohibited behavior:

```text
request:
  tt1234567

adapter:
  "I don't know the IMDb mapping,
   but I'll search by title anyway."
```

unless that behavior is explicitly declared as an identity-resolution
capability and governed by its own evidence policy.

Otherwise source adapters become hidden identity resolvers.

That would violate the architecture.

## Source Admission: turn an adapter into an executable capability

The identity layer answers:

**"What media is this?"**

The next boundary must answer:

**"Is this source allowed to participate, and under what exact
conditions?"**

These are different questions.

A source can be:

- correctly identified,
- reachable,
- technically capable,
- and still **not admitted**.

The source-admission layer therefore sits **before execution**, not
after it.

```text
CanonicalMedia
      │
      ▼
Capability match
      │
      ▼
Identity requirement
      │
      ▼
Authorization admission
      │
      ▼
Network/policy admission
      │
      ▼
Health / circuit state
      │
      ▼
EXECUTE
```

The critical invariant is:

**No adapter execution occurs before admission succeeds.**

## Authorization must be evidence-bearing

Avoid:

```text
authorized: true
```

as the entire trust model.

That is merely an assertion.

Instead:

```ts
interface AuthorizationDeclaration {
  readonly mode: "configured_owned" | "public_domain" | "licensed";

  readonly evidence: readonly AuthorizationEvidence[];
}
```

with:

```ts
interface AuthorizationEvidence {
  readonly evidenceId: string;

  readonly kind:
    | "configuration"
    | "license"
    | "ownership"
    | "public_domain_status"
    | "operator_attestation";

  readonly subject: string;

  readonly observedAt: string;

  readonly expiresAt?: string;

  readonly reference?: string;
}
```

The distinction is important:

```text
claim
  ≠ evidence
  ≠ verification
  ≠ authorization
```

A declaration can contain evidence without that evidence necessarily
being independently verified.

Therefore admission should retain its status.

## Admission status

Use an explicit state rather than a Boolean.

```ts
type AdmissionStatus = "admitted" | "rejected" | "pending_review" | "expired";
```

And:

```ts
interface AdmissionDecision {
  readonly status: AdmissionStatus;

  readonly adapterId: string;

  readonly reasons: readonly AdmissionReason[];

  readonly evidenceIds: readonly string[];

  readonly evaluatedAt: string;
}
```

Reasons should be machine-readable:

```ts
type AdmissionReason =
  | "missing_authorization_evidence"
  | "unsupported_authorization_mode"
  | "expired_authorization"
  | "missing_required_identity"
  | "unsupported_media_type"
  | "stream_capability_missing"
  | "network_policy_violation"
  | "invalid_declaration"
  | "duplicate_adapter_id"
  | "operator_disabled";
```

This gives us:

```text
REJECTED
```

without losing **why**.

## Admission is not health

This distinction should become a hard invariant.

| State | Meaning |
| --- | --- |
| admitted | source is permitted to participate |
| healthy | source currently appears operational |
| circuit closed | requests may currently execute |
| identity available | media mapping is sufficient |
| candidate valid | returned stream has valid structure |
| authorized candidate | particular playback candidate is permitted |

These are independent dimensions.

For example:

```text
Adapter A

admission     = admitted
identity      = resolved
health        = unhealthy
circuit       = open
```

Result:

```text
DO NOT EXECUTE
```

But not:

```text
SOURCE IS UNAUTHORIZED
```

Conversely:

```text
admission     = rejected
health        = healthy
circuit       = closed
```

Result:

```text
DO NOT EXECUTE
```

The source being reachable cannot grant authority.

## Required identity policy

An adapter should explicitly declare what identity it requires.

Example:

```ts
const declaration: SourceDeclaration = {
  id: "authorized-library",
  name: "Authorized Media Library",

  capabilities: {
    mediaTypes: ["movie", "series"],
    supportsMovies: true,
    supportsSeries: true,
    supportsEpisodes: true,
    providesStreams: true,
    providesSubtitles: false,
    providesMetadata: false,
    identityKinds: ["internal"],
    authorizationMode: "configured_owned"
  },

  requiredIdentityKinds: ["internal"]

  // ...
};
```

Now routing can explain:

```text
Request: IMDb tt1234567

Available: IMDb
Required: internal

Decision: identity_missing
```

The router must **not** silently invent:

```text
IMDb → internal
```

because a title happened to look similar.

## Admission engine

The engine should be pure wherever possible.

```ts
function evaluateAdmission(
  declaration: SourceDeclaration,
  context: AdmissionContext
): AdmissionDecision;
```

Input:

```ts
interface AdmissionContext {
  readonly now: string;

  readonly enabledAdapters: ReadonlySet<string>;

  readonly verifiedEvidenceIds: ReadonlySet<string>;
}
```

The engine does not perform HTTP.

It does not access the database.

It does not invoke the adapter.

It evaluates facts.

Conceptually:

```text
Declaration
     + Evidence
     + Operator configuration
     + Current time
     │
     ▼
AdmissionDecision
```

That makes it deterministic and testable.

## Admission algorithm

```ts
function evaluateAdmission(
  declaration: SourceDeclaration,
  context: AdmissionContext
): AdmissionDecision {
  const reasons: AdmissionReason[] = [];

  if (!context.enabledAdapters.has(declaration.id)) {
    reasons.push("operator_disabled");
  }

  if (declaration.capabilities.authorizationMode === "unknown") {
    reasons.push("unsupported_authorization_mode");
  }

  if (declaration.authorization.evidence.length === 0) {
    reasons.push("missing_authorization_evidence");
  }

  for (const evidence of declaration.authorization.evidence) {
    if (evidence.expiresAt !== undefined && evidence.expiresAt <= context.now) {
      reasons.push("expired_authorization");
    }
  }

  if (!declaration.capabilities.providesStreams) {
    reasons.push("stream_capability_missing");
  }

  if (reasons.length > 0) {
    return {
      status: "rejected",
      adapterId: declaration.id,
      reasons,
      evidenceIds: declaration.authorization.evidence.map(
        evidence => evidence.evidenceId
      ),
      evaluatedAt: context.now
    };
  }

  return {
    status: "admitted",
    adapterId: declaration.id,
    reasons: [],
    evidenceIds: declaration.authorization.evidence.map(
      evidence => evidence.evidenceId
    ),
    evaluatedAt: context.now
  };
}
```

This is deliberately conservative.

## Asset authorization

Even inside an authorized library, candidate authorization should
remain explicit.

```ts
interface AssetAuthorization {
  readonly status: "authorized" | "unauthorized" | "unknown";

  readonly evidenceIds: readonly string[];
}
```

Then:

```ts
interface LibraryAsset {
  readonly assetId: string;
  readonly canonicalId: string;
  readonly url: string;

  readonly authorization: AssetAuthorization;
}
```

This may look redundant.

It is intentionally redundant because:

```text
source authorization
```

does not necessarily prove:

```text
asset authorization
```

The architecture preserves the distinction.

## Multiple authorized assets

Suppose the library contains:

```text
movie-001 / 720p
movie-001 / 1080p
movie-001 / 2160p
```

The adapter returns all structurally valid authorized candidates.

It should **not rank them**.

That remains the resolver's responsibility.

```text
Adapter
  ↓
candidate A
candidate B
candidate C
  ↓
Resolver
  ↓
ranking
```

This preserves the separation:

```text
source discovery ≠ global preference
```

## Subtitle authorization

The candidate should carry authorization evidence:

```text
authorization: {
  status: "authorized",
  evidenceIds: [
    "subtitle:asset-123"
  ]
}
```

The central policy remains:

```text
unknown
   ↓
REJECT
```

This prevents a provider from implicitly upgrading:

```text
"I found a URL"
```

into:

```text
"you may distribute this URL."
```

## Subtitle provider admission

Subtitle providers should use the same admission machinery.

```text
Provider Declaration
        │
        ▼
Capability Validation
        │
        ▼
Authorization Evidence
        │
        ▼
Network Policy
        │
        ▼
Admission Decision
```

We should not create:

```text
special subtitle trust rules
```

just because subtitles are "secondary."

## Catalog authorization

Catalog visibility itself can require policy.

For example:

```ts
interface CatalogVisibilityPolicy {
  canExpose(entry: CatalogEntry, context: VisibilityContext): boolean;
}
```

But don't confuse:

```text
catalog visibility
```

with:

```text
playback authorization
```

A title can legitimately appear in a catalog while no authorized
playback candidate currently exists.

## Catalog does not imply stream availability

This is worth making an invariant:

```text
CatalogEntry
    ─X→ PlayableCandidate
```

There is no automatic implication.

Instead:

```text
CatalogEntry
    │
    ▼
CanonicalMedia
    │
    ▼
StreamResolver
    │
    ▼
PlayableCandidate[]
```

The stream resolver performs a fresh eligibility check.

## Policy evaluation

Policy should ideally be pure:

```ts
evaluateCandidatePolicy(candidate, policy): PolicyDecision;
```

Result:

```ts
interface PolicyDecision {
  readonly allowed: boolean;

  readonly reasons: readonly string[];
}
```

Therefore:

```text
same candidate + same policy = same decision
```

This becomes testable.

## Policy precedence

Conflicts must be deterministic.

For security-sensitive rules:

```text
DENY
  overrides ALLOW
```

For preference rules:

```text
specific preference
  overrides default preference
```

Do not use an implicit "last configuration wins" model for security
decisions.

## Security boundary

We can now identify the principal trust boundaries:

```text
Stremio client
      │
      │ untrusted request
      ▼
Protocol parser
      │
      ▼
Application
      │
      │ controlled
      ▼
Provider runtime
      │
      │ untrusted provider data
      ▼
Validation / policy
      │
      ▼
Derived result
```

Provider responses should be treated as hostile input.

## Threat model

At minimum, consider:

| Threat | Boundary |
| --- | --- |
| malformed Stremio request | protocol |
| provider response injection | adapter |
| SSRF | network runtime |
| redirect abuse | HTTP runtime |
| secret leakage | credential/logging |
| malicious subtitle file | auxiliary runtime |
| excessive catalog page | protocol |
| provider amplification | rate/concurrency |
| stale authorization | admission |
| cache poisoning | cache |
| identity collision | identity |
| ranking manipulation | reconciliation/ranking |
| replay inconsistency | evidence/core |

## Trusted vs untrusted providers

Define:

```ts
type ProviderTrust = "operator_trusted" | "reviewed" | "untrusted";
```

Then admission can require:

```text
untrusted provider
   + in-process execution
   = rejected
```

if the deployment policy requires isolation.
