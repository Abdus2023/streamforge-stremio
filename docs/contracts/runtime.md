# Contract: Runtime & Control-Plane Primitives

[⇧ Architecture index](../architecture.md) · [⇆ Document map](../architecture/README.md)

> **Normative.** The single authoritative definition of `RuntimeSnapshot`,
> `ConfigurationTransaction`, and `RuntimePolicy`. `docs/architecture/06-runtime.md`
> explains request-scoped execution mechanics that consume a
> `RuntimeSnapshot`; `docs/architecture/09-control-plane.md` explains the
> configuration lifecycle that produces one. Neither redefines the shapes
> below.
>
> **Status:** DESIGNED. No implementation exists in the repository as of
> this revision. Field values shown (timeouts, limits) are illustrative,
> not production-recommended defaults.

## `RuntimeSnapshot`

An immutable, generation-stamped view of everything the runtime needs to
serve requests: admitted sources, metadata providers, subtitle providers,
catalog providers, and the active policy.

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

Once published, a `RuntimeSnapshot` is immutable. There is no in-place
mutation of a live snapshot's provider list or policy — a new snapshot is
built and atomically swapped in (see
`docs/architecture/09-control-plane.md`, "Atomic configuration
replacement").

## `ConfigurationTransaction`

```ts
interface ConfigurationTransaction {
  readonly baseGeneration: string;
  readonly proposedGeneration: string;

  validate(): Promise<ConfigurationValidation>;
  commit(): Promise<RuntimeSnapshot>;
}
```

`commit()` MUST fail if `baseGeneration !== currentlyPublishedGeneration`
— this is optimistic concurrency control, and it is what prevents two
concurrent configuration changes from silently clobbering each other.

## `RuntimePolicy`

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

`RuntimePolicy` is configuration-shaped but is not interchangeable with
generic configuration — see `docs/architecture/05-policy.md` and
`docs/architecture/09-control-plane.md` ("Configuration is not policy")
for why changing a timeout must never be able to redefine authorization.

## Generation lifecycle

Every `RuntimeSnapshot` generation moves through an explicit, one-directional
lifecycle (see `docs/architecture/09-control-plane.md` for the full state
machine and gates at each transition):

```text
PROPOSED → VALIDATED → ADMITTED → PUBLISHED → ACTIVE → SUPERSEDED → RETIRED
```

## Binding invariants

- Configuration changes are atomic and generation-scoped only — never an
  incremental mutation of a live registry.
- A request is always served against exactly one `RuntimeSnapshot`
  generation; the runtime never mixes providers/policy from two
  generations within a single request (see `docs/architecture/06-runtime.md`).
- `RuntimePolicy` is validated and admitted through the same pipeline as
  provider declarations, not bolted on afterward.

## Related contracts

- Request-scoped execution context built from a snapshot: `docs/contracts/source-adapter.md` (`ResolveContext`)
- Evidence/receipts produced during a request: `docs/contracts/evidence.md`
