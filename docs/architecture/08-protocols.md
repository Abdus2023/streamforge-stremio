# Protocol Adapters

[⇧ Architecture index](../architecture.md) · [⇆ Document map](./README.md)

> **Scope.** How Stremio, HTTP, and CLI protocol surfaces are kept separate from the core application: `/manifest`, `/stream` today, `/catalog`/`/meta`/`/subtitles` in the future, the `ProtocolAdapter` pattern, the API error algebra, and partial-success semantics at the protocol boundary. The core application (`03-resolution.md`, `04-providers.md`) must never depend on Stremio-specific types.

> **Primary dependencies:** `02-domain.md`, `03-resolution.md`

> **Status.** Unless a section explicitly states otherwise with a concrete repository reference (file path, commit, or CI run), everything below is **DESIGNED** or **PROPOSED** architecture, not implemented code. This document was migrated from the original `docs/architecture.md` monolith; section order is preserved from that document, numbering has been dropped in favor of descriptive headings, and some very long single sections in the monolith may appear here still bearing internal editorial framing (e.g. first-person design narration) that predates the doc-split.

## Sections in this document

- [Stremio manifest](#stremio-manifest)
- [Stremio addon server](#stremio-addon-server)
- [Convert internal sources to Stremio streams](#convert-internal-sources-to-stremio-streams)
- [Series IDs](#series-ids)
- [Stremio should be an output adapter](#stremio-should-be-an-output-adapter)
- [Stremio response boundary](#stremio-response-boundary)
- [Stremio adapter](#stremio-adapter)
- [Manifest](#manifest)
- [Stremio ID parser](#stremio-id-parser)
- [Assemble the addon](#assemble-the-addon)
- [Stremio protocol boundary](#stremio-protocol-boundary)
- [Series parsing](#series-parsing)
- [Stremio handler](#stremio-handler)
- [Stremio protocol surface](#stremio-protocol-surface)
- [Manifest is a contract](#manifest-is-a-contract)
- [Manifest generation should be pure](#manifest-generation-should-be-pure)
- [Version semantics](#version-semantics)
- [Request parsing boundary](#request-parsing-boundary)
- [Separate protocol ID from domain ID](#separate-protocol-id-from-domain-id)
- [Domain parser](#domain-parser)
- [Error taxonomy at the protocol edge](#error-taxonomy-at-the-protocol-edge)
- [Stream handler](#stream-handler)
- [Why the handler must stay boring](#why-the-handler-must-stay-boring)
- [Catalog handler](#catalog-handler)
- [Meta handler](#meta-handler)
- [Series request](#series-request)
- [Failure taxonomy for the whole addon](#failure-taxonomy-for-the-whole-addon)
- [Result envelope](#result-envelope)
- [Example](#example)
- [Stremio mapping](#stremio-mapping)
- [Protocol parser](#protocol-parser)
- [Manifest](#manifest)
- [Addon assembly](#addon-assembly)
- [`src/addon/parser.ts`](#srcaddonparserts)
- [Protocol handler](#protocol-handler)
- [SDK Contract Correction — Verified Against Current Stremio Documentation](#sdk-contract-correction-—-verified-against-current-stremio-documentation)
- [Manifest — Actual SDK Shape](#manifest-—-actual-sdk-shape)
- [Protocol Surface v0.1](#protocol-surface-v01)
- [Series Identity](#series-identity)
- [Stream Response Contract](#stream-response-contract)
- [JSON schema](#json-schema)
- [Error boundary](#error-boundary)
- [Metadata API surface](#metadata-api-surface)
- [Stremio metadata mapping](#stremio-metadata-mapping)
- [Subtitle Stremio mapping](#subtitle-stremio-mapping)
- [`/subtitles` handler](#subtitles-handler)
- [Dynamic manifest generation remains prohibited](#dynamic-manifest-generation-remains-prohibited)
- [Catalog request](#catalog-request)
- [Pagination contract](#pagination-contract)
- [Stable pagination](#stable-pagination)
- [Stremio catalog mapping](#stremio-catalog-mapping)
- [Manifest evolution](#manifest-evolution)
- [Public vs internal result](#public-vs-internal-result)
- [Protocol-Neutral Media API](#protocol-neutral-media-api)
- [The API resource model](#the-api-resource-model)
- [API operations](#api-operations)
- [Commands vs queries](#commands-vs-queries)
- [Public API vs control API](#public-api-vs-control-api)
- [Request envelope](#request-envelope)
- [Caller identity](#caller-identity)
- [Error algebra](#error-algebra)
- [Error envelope](#error-envelope)
- [Do not leak provider internals](#do-not-leak-provider-internals)
- [HTTP status mapping](#http-status-mapping)
- [Partial success](#partial-success)
- [Stable result envelope](#stable-result-envelope)
- [Pagination response](#pagination-response)
- [Cursor pagination later](#cursor-pagination-later)
- [Media lookup](#media-lookup)
- [Canonical media API representation](#canonical-media-api-representation)
- [API versioning](#api-versioning)
- [Schema version ≠ API version](#schema-version-≠-api-version)
- [Compatibility contract](#compatibility-contract)
- [JSON schema](#json-schema)
- [Protocol adapter interface](#protocol-adapter-interface)
- [Stremio adapter](#stremio-adapter)
- [Native HTTP API adapter](#native-http-api-adapter)
- [CLI adapter](#cli-adapter)

---

## Stremio manifest

A minimal production-oriented manifest:

```ts
export const manifest = {
  id: "org.example.multisource",
  version: "1.0.0",

  name: "MultiSource",
  description:
    "Multi-source media resolver for authorized and public-domain sources.",

  resources: ["catalog", "meta", "stream", "subtitles"],

  types: ["movie", "series"],

  idPrefixes: ["tt"],

  catalogs: [
    {
      type: "movie",
      id: "multisource-movies",
      name: "MultiSource Movies",
      extra: [
        {
          name: "search",
          isRequired: false
        }
      ]
    }
  ],

  behaviorHints: {
    configurable: true,
    p2p: false
  },

  config: [
    {
      key: "language",
      type: "select",
      title: "Preferred language",
      options: ["en", "fr", "ar"],
      default: "en"
    }
  ]
};
```

The `resources`, `types`, `idPrefixes`, catalogs and configuration fields
follow the Stremio manifest model.

## Stremio addon server

```ts
import { addonBuilder, serveHTTP } from "stremio-addon-sdk";

import { manifest } from "./addon/manifest.js";
import { resolve } from "./orchestrator/resolver.js";

const builder = new addonBuilder(manifest);

builder.defineStreamHandler(async args => {
  const media = parseStremioId(args);

  const streams = await resolve(media);

  return {
    streams,
    cacheMaxAge: 300,
    staleRevalidate: 60,
    staleError: 600
  };
});

serveHTTP(builder.getInterface(), {
  port: Number(process.env.PORT ?? 7000)
});
```

Stremio supports cache-related properties such as `cacheMaxAge`,
`staleRevalidate`, and `staleError` on stream responses.

## Convert internal sources to Stremio streams

Keep this conversion at the boundary.

```ts
function toStremioStream(candidate: SourceCandidate) {
  const quality = candidate.quality?.label ?? "Unknown";

  const languages = candidate.language?.join(", ") ?? "";

  return {
    name: `${candidate.sourceId} • ${quality}`,

    description: [languages, candidate.codec, candidate.container]
      .filter(Boolean)
      .join(" • "),

    url: candidate.url,

    behaviorHints: {
      bingeGroup: `${candidate.sourceId}-${quality}`
    }
  };
}
```

So the architecture becomes:

```text
External API
     ↓
Adapter-specific JSON
     ↓
SourceCandidate
     ↓
validation
     ↓
dedupe
     ↓
ranking
     ↓
Stremio Stream
```

## Series IDs

This is an easy place to introduce bugs.

A series request may look conceptually like:

```text
tt1234567:2:7
     │    │ │
     │    │ └─ episode
     │    └─── season
     └──────── series
```

Parser:

```ts
export function parseStremioId(args: { type: string; id: string }): MediaRef {
  const parts = args.id.split(":");

  if (args.type === "movie") {
    return {
      type: "movie",
      id: parts[0],
      imdbId: parts[0]
    };
  }

  if (args.type === "series") {
    return {
      type: "series",
      id: parts[0],
      imdbId: parts[0],
      season: Number(parts[1]),
      episode: Number(parts[2])
    };
  }

  throw new Error("unsupported_media_type");
}
```

## Stremio should be an output adapter

This is a useful abstraction:

```text
                   Aggregation Kernel
                           │
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
           Stremio       JSON API       CLI
           Adapter
```

The Stremio-specific code becomes tiny:

```ts
export function toStremio(candidates: SourceCandidate[]) {
  return candidates.map(candidate => ({
    name: buildName(candidate),

    description: buildDescription(candidate),

    url: candidate.location.url,

    behaviorHints: buildHints(candidate)
  }));
}
```

This makes the underlying system reusable.

## Stremio response boundary

Only here should the external protocol shape appear.

```ts
builder.defineStreamHandler(async args => {
  const media = parseStremioMedia(args);

  const result = await resolveMedia(media, registry, createContext());

  return {
    streams: result.candidates.map(toStremioStream)
  };
});
```

Everything below this layer remains Stremio-independent.

## Stremio adapter

Now the kernel is ready.

```ts
// src/addon/stream-handler.ts

import type { SourceCandidate } from "../domain/candidate.js";

function formatQuality(candidate: SourceCandidate): string {
  const { width, height } = candidate.mediaInfo;

  if (!width || !height) {
    return "Unknown";
  }

  return `${width}x${height}`;
}

export function toStremioStream(candidate: SourceCandidate) {
  return {
    name: candidate.sourceId,

    description: formatQuality(candidate),

    url: candidate.location.url
  };
}
```

Notice how stupid this function is.

That's desirable.

## Manifest

Keep it equally boring:

```ts
export const manifest = {
  id: "org.example.multisource",

  version: "0.1.0",

  name: "MultiSource",

  description: "Authorized multi-source media aggregation.",

  resources: ["stream"],

  types: ["movie", "series"],

  idPrefixes: ["tt"]
};
```

Don't add catalog functionality until metadata semantics are actually
defined.

## Stremio ID parser

```ts
export function parseMediaId(type: string, id: string): MediaRef {
  if (type === "movie") {
    return {
      type: "movie",
      id,
      imdbId: id
    };
  }

  if (type === "series") {
    const [imdbId, seasonRaw, episodeRaw] = id.split(":");

    const season = Number(seasonRaw);

    const episode = Number(episodeRaw);

    if (!imdbId || !Number.isInteger(season) || !Number.isInteger(episode)) {
      throw new Error("invalid_series_id");
    }

    return {
      type: "series",
      id: imdbId,
      imdbId,
      season,
      episode
    };
  }

  throw new Error(`unsupported_type:${type}`);
}
```

## Assemble the addon

```ts
import { addonBuilder, serveHTTP } from "stremio-addon-sdk";

import { manifest } from "./addon/manifest.js";

import { SourceRegistry } from "./adapters/registry.js";

import { resolveMedia } from "./resolver/resolver.js";

const registry = new SourceRegistry();

// register adapters here

const builder = new addonBuilder(manifest);

builder.defineStreamHandler(async args => {
  const media = parseMediaId(args.type, args.id);

  const result = await resolveMedia(media, registry, createResolveContext());

  return {
    streams: result.candidates.map(toStremioStream)
  };
});

serveHTTP(builder.getInterface(), {
  port: Number(process.env.PORT ?? 7000)
});
```

## Stremio protocol boundary

Now freeze the protocol boundary.

The resolver returns:

```text
readonly SourceCandidate[]
```

The Stremio adapter converts only:

```text
SourceCandidate
        ↓
StremioStream
```

Example:

```ts
interface StremioStream {
  readonly name?: string;
  readonly title?: string;
  readonly url: string;
  readonly behaviorHints?: {
    readonly notWebReady?: boolean;
  };
}
```

The mapper should not perform:

```text
HTTP
policy
deduplication
ranking
authorization
metadata lookup
```

It should be boring.

That's intentional.

## Series parsing

Freeze the ID grammar explicitly.

For example:

```text
movie: tt1234567

series: tt1234567:1:4
```

Parser:

```ts
export interface ParsedStremioId {
  readonly imdbId: string;
  readonly season?: number;
  readonly episode?: number;
}

export function parseId(type: MediaType, id: string): ParsedStremioId {
  if (type === "movie") {
    if (!/^tt\d+$/.test(id)) {
      throw new Error("invalid_movie_id");
    }

    return {
      imdbId: id
    };
  }

  const match = /^(tt\d+):(\d+):(\d+)$/.exec(id);

  if (!match) {
    throw new Error("invalid_series_id");
  }

  return {
    imdbId: match[1],
    season: Number(match[2]),
    episode: Number(match[3])
  };
}
```

The grammar should have tests before adding more accepted formats.

## Stremio handler

Conceptually:

```ts
export async function handleStream(type: MediaType, id: string) {
  const media = parseStremioMedia(type, id);

  const result = await resolver.resolve(media);

  return {
    streams: result.candidates.map(toStremioStream)
  };
}
```

That's nearly all it should contain.

## Stremio protocol surface

Now we cross the final architectural boundary: the internal
aggregation kernel must become a real Stremio addon without allowing
the protocol layer to contaminate the domain.

The target is:

```text
                    HTTP
                     │
                     ▼
               /manifest.json
                     │
         ┌───────────┼───────────┐
         ▼           ▼           ▼
      /catalog     /meta       /stream
                                   │
                                   ▼
                               Resolver
                                   │
                                   ▼
                           SourceCandidate[]
                                   │
                                   ▼
                            Stremio streams
```

And later:

```text
/stream
/subtitles
```

## Manifest is a contract

The manifest should describe only capabilities actually implemented.

Do not advertise:

```text
catalog
meta
stream
subtitle
```

because they are planned.

Advertise only what is currently executable.

Conceptually:

```ts
export const manifest = {
  id: "com.example.authorized-aggregator",
  version: "0.1.0",
  name: "Authorized Source Aggregator",
  description: "Aggregates eligible playback sources.",
  resources: ["stream"],
  types: ["movie", "series"],
  idPrefixes: ["tt"]
};
```

The exact SDK typing should be validated against the installed
`stremio-addon-sdk` version during implementation rather than assuming
a remembered SDK type definition is current.

That distinction matters because:

```text
architecture contract
    ≠
third-party SDK API contract
```

## Manifest generation should be pure

Don't construct it dynamically from runtime state.

Bad:

```text
source A unavailable
    ↓
remove stream capability
```

The manifest describes **what the addon implements**, not today's
source health.

Therefore:

```text
manifest
    = static capability declaration
```

while:

```text
health
    = current runtime state
```

## Version semantics

Use:

```text
addon version
```

for the addon contract.

Use separate versions for:

```text
candidate schema
identity schema
cache schema
```

For example:

```text
addon:       0.3.0
candidate:   v2
identity:    v1
cache:       candidate-v2
```

Do not use one version number to imply all schemas are identical.

## Request parsing boundary

The HTTP layer gives you strings.

The domain requires typed values.

Therefore:

```text
HTTP string
    ↓
Stremio parser
    ↓
validated protocol request
    ↓
domain MediaRef
```

Define:

```ts
export interface StreamRequest {
  readonly type: "movie" | "series";
  readonly id: string;
}
```

Then:

```ts
export function parseStreamRequest(type: string, id: string): StreamRequest {
  if (type !== "movie" && type !== "series") {
    throw new Error("unsupported_media_type");
  }

  if (!id) {
    throw new Error("missing_media_id");
  }

  return {
    type,
    id
  };
}
```

The parser should reject malformed input before invoking identity
resolution.

## Separate protocol ID from domain ID

This is subtle but important.

Stremio might provide:

```text
tt1234567:1:4
```

The domain should receive:

```json
{
  "type": "series",
  "id": "tt1234567",
  "season": 1,
  "episode": 4
}
```

Don't pass the raw string through the entire system.

That would make every internal layer understand Stremio syntax.

## Domain parser

```ts
export function toMediaRef(request: StreamRequest): MediaRef {
  if (request.type === "movie") {
    return {
      type: "movie",
      id: request.id
    };
  }

  const parts = request.id.split(":");

  if (parts.length !== 3) {
    throw new Error("invalid_series_id");
  }

  const [seriesId, seasonRaw, episodeRaw] = parts;

  const season = Number(seasonRaw);

  const episode = Number(episodeRaw);

  if (
    !Number.isInteger(season) ||
    season < 1 ||
    !Number.isInteger(episode) ||
    episode < 1
  ) {
    throw new Error("invalid_episode_coordinates");
  }

  return {
    type: "series",
    id: seriesId,
    season,
    episode
  };
}
```

Now the rest of the application doesn't care that the original request
came from Stremio.

## Error taxonomy at the protocol edge

Don't turn everything into HTTP 500.

Distinguish:

```text
400
invalid request

404
unsupported resource / not found

200 + empty streams
valid request, no eligible sources

500
internal failure
```

The exact behavior should follow the SDK's expected resource-handler
semantics.

The important principle is:

**A valid media request with zero eligible streams is not necessarily
an application failure.**

## Stream handler

The stream handler should be tiny.

```ts
export async function handleStream(request: StreamRequest) {
  const media = toMediaRef(request);

  const result = await resolver.resolve(media);

  return {
    streams: result.candidates.map(toStremioStream)
  };
}
```

Notice what isn't here:

```text
HTTP
ranking
dedup
authorization
source selection
retry
cache
```

All of those already belong elsewhere.

## Why the handler must stay boring

A protocol handler that grows into:

```text
500-line stream handler
```

is an architectural warning.

It usually means:

```text
domain logic + runtime logic + protocol logic
```

have become coupled.

The desired shape is:

```text
handler
    = parse
    + delegate
    + map
```

## Catalog handler

Catalog is different.

It should not ask every source:

```text
"What movies do you have?"
```

on every request.

That creates:

```text
Stremio
    ↓
catalog
    ↓
all providers
    ↓
expensive discovery
```

Instead use a defined catalog authority.

For example:

```text
CatalogProvider
```

```ts
export interface CatalogProvider {
  list(request: CatalogRequest): Promise<readonly CatalogItem[]>;
}
```

This provider could represent:

- a curated public-domain catalog
- a user's authorized library
- a metadata-backed catalog

but the contract remains the same.

## Meta handler

Meta should return descriptive information.

```ts
export interface MetaProvider {
  get(media: CanonicalMedia): Promise<Meta>;
}
```

For example:

```ts
export interface Meta {
  readonly id: string;
  readonly type: "movie" | "series";
  readonly name: string;
  readonly poster?: string;
  readonly description?: string;
  readonly year?: number;
}
```

Again:

```text
metadata ≠ playback authorization
```

## Series request

For:

```text
tt1234567:2:7
```

the pipeline becomes:

```text
series request
     │
     ▼
series identity
     │
     ▼
episode coordinate
     │
     ▼
SourceQuery {
    series,
    season: 2,
    episode: 7
}
     │
     ▼
source adapters
```

An adapter must not accidentally query:

```text
tt1234567
```

without preserving:

```text
season = 2
episode = 7
```

That deserves an explicit test.

## Failure taxonomy for the whole addon

We can now unify errors.

```ts
export type FailureCode =
  | "invalid_request"
  | "identity_not_found"
  | "identity_ambiguous"
  | "source_empty"
  | "source_timeout"
  | "source_aborted"
  | "source_rate_limited"
  | "source_circuit_open"
  | "source_invalid_response"
  | "source_network_error"
  | "candidate_invalid"
  | "candidate_not_authorized"
  | "internal_error";
```

Do not expose all of these directly to Stremio.

They are internal diagnostic semantics.

## Result envelope

Instead of returning only arrays internally:

```ts
export interface ResolverResult<T> {
  readonly status: "success" | "empty" | "partial" | "failed";

  readonly value: readonly T[];

  readonly failures: readonly Failure[];

  readonly sourceCount: number;

  readonly durationMs: number;
}
```

This lets the system distinguish:

```text
zero sources because none exist
```

from:

```text
zero sources because every provider failed
```

That distinction is operationally crucial.

## Example

Case A:

```text
source A → empty
source B → empty
source C → empty
```

Result:

```text
status = empty
```

Case B:

```text
source A → timeout
source B → network error
source C → circuit open
```

Result:

```text
status = failed
```

Case C:

```text
source A → success
source B → timeout
source C → empty
```

Result:

```text
status = partial
```

All three could produce:

```json
{
  "streams": []
}
```

at the Stremio boundary, but they are **not the same internal event**.

## Stremio mapping

```ts
export interface StremioStream {
  readonly name?: string;
  readonly title?: string;
  readonly url: string;
}

export function toStremioStream(candidate: SourceCandidate): StremioStream {
  const quality =
    candidate.mediaInfo.width && candidate.mediaInfo.height
      ? `${candidate.mediaInfo.width}x${candidate.mediaInfo.height}`
      : undefined;

  return {
    name: candidate.sourceId,

    title: [quality, candidate.mediaInfo.videoCodec, candidate.mediaInfo.audioCodec]
      .filter(value => value !== undefined)
      .join(" • "),

    url: candidate.location.url
  };
}
```

The mapper remains pure.

## Protocol parser

```ts
import type { MediaType, MediaRef } from "../domain/media.js";

export function parseMediaRef(type: string, id: string): MediaRef {
  if (type !== "movie" && type !== "series") {
    throw new Error("unsupported_media_type");
  }

  if (!id) {
    throw new Error("missing_media_id");
  }

  if (type === "movie") {
    return {
      type: "movie",
      id
    };
  }

  const parts = id.split(":");

  if (parts.length !== 3) {
    throw new Error("invalid_series_id");
  }

  const [seriesId, seasonRaw, episodeRaw] = parts;

  const season = Number(seasonRaw);

  const episode = Number(episodeRaw);

  if (
    !Number.isInteger(season) ||
    season < 1 ||
    !Number.isInteger(episode) ||
    episode < 1
  ) {
    throw new Error("invalid_episode_coordinates");
  }

  return {
    type: "series",
    id: seriesId,
    season,
    episode
  };
}
```

## Manifest

Keep it isolated:

```ts
export const manifest = {
  id: "com.example.authorized-aggregator",

  version: "0.1.0",

  name: "Authorized Source Aggregator",

  description: "Aggregates eligible playback sources.",

  resources: ["stream"],

  types: ["movie", "series"],

  idPrefixes: ["tt"]
} as const;
```

The actual SDK's accepted manifest shape must be checked by the
compiler against the installed package before release.

## Addon assembly

The application composition root should be explicit.

Conceptually:

```ts
const registry = new SourceRegistry();

registry.register(new FixtureAdapter([fixtureCandidate]));

const resolver = new Resolver(registry.all(), {
  totalTimeoutMs: 4000,
  sourceTimeoutMs: 2500,
  concurrency: 6,
  preferredLanguages: ["en"]
});
```

Then the Stremio layer gets only:

```text
manifest + resolver
```

## `src/addon/parser.ts`

The protocol parser should terminate at the domain boundary.

```ts
import type { MediaRef, MediaType } from "../domain/media.js";

export interface ParsedStreamRequest {
  media: MediaRef;
}

export class RequestParseError extends Error {
  readonly code = "invalid_request";

  constructor(message: string) {
    super(message);
    this.name = "RequestParseError";
  }
}

export function parseStreamRequest(
  type: string,
  rawId: string
): ParsedStreamRequest {
  if (type !== "movie" && type !== "series") {
    throw new RequestParseError(`Unsupported media type: ${type}`);
  }

  if (!rawId) {
    throw new RequestParseError("Missing media ID");
  }

  if (type === "movie") {
    return {
      media: {
        type: "movie",
        id: rawId
      }
    };
  }

  const parts = rawId.split(":");

  if (parts.length !== 3) {
    throw new RequestParseError(
      "Series ID must use <id>:<season>:<episode>"
    );
  }

  const [id, seasonRaw, episodeRaw] = parts;

  const season = Number(seasonRaw);
  const episode = Number(episodeRaw);

  if (
    !id ||
    !Number.isInteger(season) ||
    !Number.isInteger(episode) ||
    season < 1 ||
    episode < 1
  ) {
    throw new RequestParseError("Invalid series episode identifier");
  }

  return {
    media: {
      type: "series",
      id,
      season,
      episode
    }
  };
}
```

The important property is that the rest of the application never needs
to understand:

```text
tt1234567:2:7
```

It receives:

```json
{
  "type": "series",
  "id": "tt1234567",
  "season": 2,
  "episode": 7
}
```

That is the protocol/domain separation boundary.

## Protocol handler

`src/addon/stream-handler.ts`:

```ts
import type { Resolver } from "../application/resolver.js";
import { parseStreamRequest } from "./parser.js";

export function createStreamHandler(resolver: Resolver) {
  return async (args: { type: string; id: string }) => {
    const { media } = parseStreamRequest(args.type, args.id);

    const controller = new AbortController();

    try {
      const result = await resolver.resolve(media, controller.signal);

      return {
        streams: result.candidates.map(candidate => ({
          name: candidate.sourceId,
          title: buildStreamTitle(candidate),
          url: candidate.url
        }))
      };
    } finally {
      controller.abort();
    }
  };
}

function buildStreamTitle(candidate: {
  mediaInfo?: {
    resolution?: string;
    container?: string;
  };
}): string {
  const parts = [];

  if (candidate.mediaInfo?.resolution) {
    parts.push(candidate.mediaInfo.resolution);
  }

  if (candidate.mediaInfo?.container) {
    parts.push(candidate.mediaInfo.container);
  }

  return parts.join(" · ");
}
```

Notice that `ResolutionResult` does **not** escape directly into the
Stremio API.

The mapper controls that boundary.

## SDK Contract Correction — Verified Against Current Stremio Documentation

There is one important correction to the previous blueprint.

The current Stremio Node SDK uses:

```text
addonBuilder(...)
builder.defineStreamHandler(...)
builder.getInterface()
serveHTTP(...)
```

— not the hypothetical `builder.defineAddon()` / `serveHTTP(addon)`
composition shown earlier. The official SDK documentation confirms this
interface.

So the executable composition root should use the actual SDK boundary.

## Manifest — Actual SDK Shape

The official protocol requires a manifest containing at least `id`,
`version`, `name`, `description`, `resources`, and `types`. Resources
may be strings or detailed objects.

For our first stream-only slice:

```ts
export function createManifest() {
  return {
    id: "org.authorized.sourceaggregator",
    version: "0.1.0",

    name: "Authorized Source Aggregator",

    description: "Aggregates playback streams from explicitly authorized sources.",

    resources: [
      {
        name: "stream",
        types: ["movie", "series"],
        idPrefixes: ["tt"]
      }
    ],

    types: ["movie", "series"],

    idPrefixes: ["tt"],

    catalogs: []
  };
}
```

This is significant because:

```text
idPrefixes: ["tt"]
```

means the first implementation integrates naturally with IMDb/Cinemeta
IDs rather than inventing a second identity namespace. The Stremio
documentation explicitly describes this pattern for stream-only
addons.

## Protocol Surface v0.1

The actual initial surface is therefore:

```text
GET /manifest.json

GET /stream/movie/tt1234567.json

GET /stream/series/tt1234567:2:7.json
```

No:

```text
/catalog
/meta
/subtitles
```

yet.

This is intentional.

The protocol itself supports all four resource classes — catalog, meta,
stream, and subtitles — but an addon only needs at least one resource.

## Series Identity

For IMDb series, the SDK documents the video ID format:

```text
tt0898266:9:17
```

meaning:

```text
series:
  id      = tt0898266
  season  = 9
  episode = 17
```

Our parser therefore has a direct protocol mapping:

```text
tt0898266:9:17
       │
       ▼
{
    type: "series",
    id: "tt0898266",
    season: 9,
    episode: 17
}
```

No adapter should receive the raw string.

## Stream Response Contract

The external response remains extremely small:

```json
{
  "streams": [
    {
      "name": "authorized-fixture",
      "title": "1080p · mp4",
      "url": "https://media.example.test/movie.mp4"
    }
  ]
}
```

The Stremio protocol defines `streams` as the stream-result collection
and `url` as a stream location.

Internally, however, we retain much more information:

```text
SourceCandidate
 ├── sourceId
 ├── media
 ├── url
 ├── mediaInfo
 ├── language
 ├── provenance
 ├── capabilities
 └── authorization
```

Therefore:

```text
internal evidence model
        ≠
Stremio presentation model
```

This is exactly the semantic boundary we want.

## JSON schema

Do not deserialize arbitrary JSON directly into domain objects.

Create an input schema.

Using Zod:

```ts
const LibraryAssetSchema = z.object({
  assetId: z.string().min(1),
  canonicalId: z.string().min(1),
  playbackUrl: z.string().url(),

  mediaInfo: z
    .object({
      container: z.string().optional(),
      codecs: z.array(z.string()).optional(),
      resolution: z.number().int().positive().optional(),
      bitrate: z.number().positive().optional(),
      sizeBytes: z.number().int().nonnegative().optional(),
      durationMs: z.number().int().nonnegative().optional()
    })
    .optional(),

  language: z.string().optional(),

  authorization: z.object({
    status: z.enum(["authorized", "unauthorized", "unknown"]),
    evidenceIds: z.array(z.string())
  })
});
```

Then:

```ts
const LibrarySchema = z.object({
  assets: z.array(LibraryAssetSchema)
});
```

The parser boundary becomes:

```text
JSON
 │
 ▼
schema validation
 │
 ▼
LibraryAsset
```

not:

```text
JSON → trust
```

## Error boundary

Adapter exceptions should not escape directly into the Stremio
handler.

```text
Adapter exception
      │
      ▼
SourceExecutor
      │
      ▼
Failure classification
      │
      ▼
ResolutionFailure
      │
      ▼
Resolver
      │
      ▼
partial / failed / empty
```

For example:

```ts
interface SourceFailure {
  readonly sourceId: string;

  readonly code:
    | "source_timeout"
    | "source_aborted"
    | "source_rate_limited"
    | "source_circuit_open"
    | "source_network_error"
    | "source_invalid_response"
    | "internal_error";

  readonly retryable: boolean;
}
```

## Metadata API surface

Once implemented, the Stremio surface can expand:

```text
GET /meta/movie/:id.json
GET /meta/series/:id.json
```

But this should not happen merely because the handler exists.

Manifest capability must be updated only after:

```text
metadata implementation
+ tests
+ HTTP integration
+ release gate
```

pass.

This follows:

**Capability declaration follows verified implementation.**

## Stremio metadata mapping

Internally:

```ts
interface MetadataRecord {
  readonly canonicalId: string;
  readonly fields: ...;
}
```

Externally:

```ts
interface StremioMeta {
  readonly id: string;
  readonly type: "movie" | "series";

  readonly name?: string;
  readonly poster?: string;
  readonly background?: string;
  readonly description?: string;
  readonly releaseInfo?: string;
  readonly genres?: readonly string[];
  readonly runtime?: string;

  readonly videos?: readonly StremioVideo[];
}
```

The mapper is responsible for representation only:

```text
MetadataRecord
      ↓
StremioMeta
```

It must not perform identity resolution.

## Subtitle Stremio mapping

Keep the protocol mapper isolated.

Conceptually:

```ts
function toStremioSubtitle(candidate: SubtitleCandidate): StremioSubtitle {
  return {
    id: candidate.id,
    url: candidate.url,
    lang: candidate.language
  };
}
```

Additional fields should be mapped only if the current Stremio
protocol contract supports them.

The domain model should not be distorted merely to match the
protocol.

## `/subtitles` handler

The handler should remain thin:

```text
HTTP
 │
 ▼
parse
 │
 ▼
MediaRef
 │
 ▼
identity
 │
 ▼
CanonicalMedia
 │
 ▼
subtitle resolver
 │
 ▼
SubtitleCandidate[]
 │
 ▼
Stremio mapper
 │
 ▼
HTTP
```

No provider logic belongs in the HTTP handler.

## Dynamic manifest generation remains prohibited

Do not automatically turn that matrix into:

```text
/manifest.json
```

on every request.

The manifest is a stable protocol declaration.

Instead:

```text
provider registry
      ↓
build-time/config-time validation
      ↓
manifest capability set
```

Then release the declared capability set.

This prevents runtime provider fluctuations from producing an
unstable protocol contract.

## Catalog request

```ts
interface CatalogRequest {
  readonly catalogId: string;

  readonly type: MediaType;

  readonly skip: number;

  readonly limit: number;

  readonly extra?: Readonly<Record<string, string>>;
}
```

For search:

```ts
interface SearchRequest {
  readonly type?: MediaType;

  readonly query: string;

  readonly skip: number;

  readonly limit: number;
}
```

The application layer owns these concepts.

The Stremio protocol layer merely translates them.

## Pagination contract

Stremio catalog pagination commonly uses a `skip` mechanism.

Internally, make pagination explicit:

```ts
interface Page<T> {
  readonly items: readonly T[];

  readonly skip: number;

  readonly limit: number;

  readonly hasMore: boolean;
}
```

Invariant:

```text
items.length <= limit
```

And:

```text
skip >= 0
limit > 0
```

with a configured maximum:

```text
limit <= MAX_CATALOG_PAGE_SIZE
```

Never let a client request an arbitrarily large page.

## Stable pagination

A subtle problem appears when the underlying catalog changes while
the client paginates.

Suppose:

```text
request 1: skip=0

catalog changes

request 2: skip=100
```

Items can move between pages.

For an initial implementation, use deterministic ordering:

```text
ORDER BY canonicalId
```

or another stable declared key.

Avoid:

```text
ORDER BY random()
```

and unstable provider response ordering.

## Stremio catalog mapping

The mapper remains protocol-specific:

```ts
function toStremioCatalogItem(entry: CatalogEntry): StremioCatalogItem {
  return {
    id: entry.media.id,
    type: entry.media.type,
    name: entry.title,
    year: entry.year,
    poster: entry.poster,
    background: entry.background
  };
}
```

For series/episode representations, the exact protocol DTO should be
verified against the SDK/protocol version actually installed before
claiming compatibility.

That verification belongs to the release gate.

## Manifest evolution

Only after catalog implementation exists should the manifest evolve
from:

```text
resources:
  stream
```

to something like:

```text
resources:
  stream
  catalog
```

And only after metadata:

```text
resources:
  stream
  catalog
  meta
```

And subtitles:

```text
resources:
  stream
  catalog
  meta
  subtitle
```

The manifest therefore becomes a **release artifact**, not a wish
list.

## Public vs internal result

Internally:

```text
accepted
rejected
failures
evidence
ranking
```

Externally:

```json
{
  "streams": [
    {
      "name": "authorized-source",
      "title": "1080p · mp4",
      "url": "..."
    }
  ]
}
```

The protocol response should remain deliberately small.

## Protocol-Neutral Media API

The system should now stop treating Stremio as the primary
architectural boundary.

Stremio becomes an **adapter** over a protocol-neutral application
API.

```text
                    MEDIA PLATFORM
                          │
                  Application API
                          │
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
      Stremio          HTTP/JSON          CLI
       adapter           API             tools
```

This is the point where the project can evolve beyond a Stremio addon
without rewriting the core.

## The API resource model

The public application model should expose a small number of stable
concepts:

```text
Media
Identity
Catalog
Metadata
Stream
Subtitle
Search
```

But these should not become seven unrelated APIs.

They all operate around:

```text
CanonicalMedia
```

Conceptually:

```text
Media
├── identities
├── metadata
├── catalog projections
├── stream candidates
└── subtitle candidates
```

## API operations

The initial protocol-neutral API:

```text
GET /v1/media/{id}
GET /v1/media/{id}/metadata
GET /v1/media/{id}/streams
GET /v1/media/{id}/subtitles

GET /v1/catalog/{catalogId}
GET /v1/search
```

These are **application API routes**, not necessarily the final HTTP
implementation.

The important boundary is:

```text
HTTP route
   ↓
request DTO
   ↓
application command/query
```

## Commands vs queries

Use CQRS terminology carefully.

### Queries

```text
get media
get metadata
get streams
get subtitles
catalog
search
```

They should not mutate authoritative state.

### Commands

```text
refresh catalog
reload configuration
enable provider
disable provider
rebuild index
```

These belong to an operator/control API, not the public playback API.

## Public API vs control API

Separate them physically:

```text
PUBLIC
/v1/media
/v1/catalog
/v1/search

CONTROL
/internal/config
/internal/providers
/internal/catalog
/internal/evidence
/internal/health
```

Never expose control-plane operations through the public
Stremio-facing surface.

## Request envelope

Every application request gets a correlation ID:

```ts
interface RequestContext {
  readonly requestId: string;

  readonly deadline: Deadline;

  readonly signal: AbortSignal;

  readonly preferredLanguages: readonly string[];
}
```

The HTTP adapter creates it.

The application does not parse HTTP headers.

## Caller identity

Eventually the API may support authentication.

Keep that separate from media authorization:

```ts
interface CallerContext {
  readonly callerId?: string;

  readonly scopes: readonly string[];
}
```

Then:

```text
Caller authorization
        ≠ Media authorization
```

A user being authorized to call the API does not prove that a
playback candidate is authorized for distribution.

## Error algebra

Do not make every failure:

```json
{
  "error": "something went wrong"
}
```

Define machine-readable errors:

```ts
type ApiErrorCode =
  | "invalid_request"
  | "unsupported_media"
  | "identity_not_found"
  | "identity_not_resolved"
  | "identity_ambiguous"
  | "resource_not_found"
  | "provider_unavailable"
  | "deadline_exceeded"
  | "rate_limited"
  | "not_authorized"
  | "internal_error";
```

## Error envelope

```ts
interface ApiError {
  readonly code: ApiErrorCode;

  readonly message: string;

  readonly requestId: string;

  readonly retryable: boolean;
}
```

Example:

```json
{
  "code": "deadline_exceeded",
  "message": "The resolution deadline expired.",
  "requestId": "req_01...",
  "retryable": true
}
```

The message is human-readable.

The code is machine-readable.

## Do not leak provider internals

Bad:

```json
{
  "error": "TMDBAdapterFetchError: ECONNRESET at..."
}
```

Better:

```json
{
  "code": "provider_unavailable",
  "requestId": "req_..."
}
```

Detailed provider diagnostics belong in controlled observability
channels.

## HTTP status mapping

The application error and HTTP status remain separate concepts.

For example:

```text
invalid_request
      ↓
400

rate_limited
      ↓
429

not_authorized
      ↓
403

resource_not_found
      ↓
404

deadline_exceeded
      ↓
504
```

But:

```text
stream resolver returned zero candidates
```

does **not necessarily** mean HTTP 404.

A valid media request can have:

```json
{
  "streams": []
}
```

## Partial success

This is particularly important for aggregation.

Suppose:

```text
source A → success
source B → timeout
source C → success
```

The application result:

```text
status = partial
```

should not become:

```text
HTTP 500
```

The public API can return:

```json
{
  "status": "partial",
  "streams": ["..."]
}
```

while omitting internal failure details unless the API contract
explicitly exposes them.

## Stable result envelope

Use:

```ts
interface ResourceResult<T> {
  readonly status: "success" | "empty" | "partial";

  readonly items: readonly T[];

  readonly requestId: string;
}
```

For streams:

```text
items = SourceCandidate[]
```

For subtitles:

```text
items = SubtitleCandidate[]
```

For catalog:

```text
items = CatalogEntry[]
```

But don't force all resource-specific metadata into a generic envelope
if it makes the type less precise.

## Pagination response

```ts
interface PageResult<T> {
  readonly items: readonly T[];

  readonly page: {
    readonly skip: number;
    readonly limit: number;
    readonly hasMore: boolean;
  };

  readonly requestId: string;
}
```

Again:

```text
skip >= 0
1 <= limit <= configured maximum
```

must be validated before reaching the application.

## Cursor pagination later

Offset pagination is sufficient initially.

But the abstraction should avoid assuming it is eternal.

Future:

```text
skip/limit
```

could evolve toward:

```text
cursor
```

without changing the domain.

This is another reason pagination belongs to the protocol/application
boundary rather than the media domain.

## Media lookup

A protocol-neutral request:

```ts
interface MediaLookupRequest {
  readonly identity: ExternalIdentity;
}
```

Application flow:

```text
ExternalIdentity
      ↓
Identity Resolver
      ↓
CanonicalMedia
```

Response:

```ts
interface MediaLookupResult {
  readonly status: "resolved" | "not_found" | "not_resolved" | "ambiguous";

  readonly media?: CanonicalMedia;
}
```

No `null` ambiguity.

## Canonical media API representation

The public API should be cautious about exposing internal identity
details.

Potential representation:

```json
{
  "id": "media:abc123",
  "type": "movie",
  "title": "Example Movie",
  "identities": [
    {
      "kind": "imdb",
      "value": "tt1234567"
    }
  ]
}
```

But:

```text
media:abc123
```

should not be interpreted as a globally meaningful identifier.

It is an identifier inside this platform's canonical namespace.

## API versioning

Start with:

```text
/v1/
```

Do not version every resource independently.

Prefer:

```text
/v1/media
/v1/search
/v1/catalog
```

Then introduce:

```text
/v2/
```

only for incompatible contract changes.

## Schema version ≠ API version

These are different:

```text
API version: v1

Evidence schema: evidence/1
Receipt schema: receipt/1
Provider declaration: provider/1
```

Changing an internal evidence schema does not necessarily require
changing the public API.

## Compatibility contract

For `/v1`:

Allowed:

```text
add optional response field
add new provider
improve internal ranking
```

Potentially breaking:

```text
rename required field
change field meaning
remove field
change identity semantics
change authorization semantics
```

Compatibility should be tested rather than assumed.

## JSON schema

The API should eventually have machine-readable schemas:

```text
schemas/
├── media.schema.json
├── stream.schema.json
├── subtitle.schema.json
├── metadata.schema.json
├── catalog.schema.json
├── search.schema.json
└── error.schema.json
```

These schemas become protocol artifacts.

## Protocol adapter interface

```ts
interface ProtocolAdapter {
  readonly id: string;

  handle(request: unknown, context: RequestContext): Promise<unknown>;
}
```

But don't make the entire application depend on this generic
interface.

Concrete adapters should be strongly typed internally.

## Stremio adapter

Conceptually:

```ts
class StremioProtocolAdapter {
  constructor(private readonly app: MediaApplication) {}

  async stream(args: StremioStreamArgs) {
    const request = parseStremioStream(args);

    const result = await this.app.resolveStreams(request, context);

    return mapToStremioStreams(result);
  }
}
```

The Stremio SDK stays at this boundary.

## Native HTTP API adapter

Similarly:

```ts
class MediaHttpController {
  constructor(private readonly app: MediaApplication) {}

  async getStreams(request: HttpRequest) {
    const command = parseHttpStreamRequest(request);

    const result = await this.app.resolveStreams(command, context);

    return mapToApiStreams(result);
  }
}
```

Two protocols.

One application.

## CLI adapter

This becomes useful for diagnostics:

```text
media-platform resolve-stream tt1234567
```

or:

```text
media-platform inspect-identity tt1234567
```

The CLI should call the same application contracts.

Not:

```text
CLI → private database
```
