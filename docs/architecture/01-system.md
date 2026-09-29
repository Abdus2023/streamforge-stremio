# System Overview

[⇧ Architecture index](../architecture.md) · [⇆ Document map](./README.md)

> **Scope.** System boundaries and topology: what StreamForge is, what it explicitly is not, the high-level component map, and the dependency direction between components. Defines the top-level distinction between **discovery**, **authorization**, **resolution**, **ranking**, and **playback** as separate, non-overlapping concerns. Does not duplicate provider contracts (see `04-providers.md`) or runtime mechanics (see `06-runtime.md`) — it only shows where they sit in the overall shape of the system.

> **Primary dependencies:** `02-domain.md`, `04-providers.md`, `05-policy.md`

> **Status.** Unless a section explicitly states otherwise with a concrete repository reference (file path, commit, or CI run), everything below is **DESIGNED** or **PROPOSED** architecture, not implemented code. This document was migrated from the original `docs/architecture.md` monolith; section order is preserved from that document, numbering has been dropped in favor of descriptive headings, and some very long single sections in the monolith may appear here still bearing internal editorial framing (e.g. first-person design narration) that predates the doc-split.

## Sections in this document

- [Target architecture](#target-architecture)
- [What I would explicitly NOT build](#what-i-would-explicitly-not-build)
- [Don't build a media proxy into v0.1](#don't-build-a-media-proxy-into-v01)
- [What this means for the Popcorn-Time-style experience](#what-this-means-for-the-popcorn-time-style-experience)
- [Catalog is not source discovery](#catalog-is-not-source-discovery)
- [Do not proxy streams by default](#do-not-proxy-streams-by-default)
- [Catalog is a different problem](#catalog-is-a-different-problem)
- [The resulting system is no longer "a scraper"](#the-resulting-system-is-no-longer-"a-scraper")
- [Dependency direction](#dependency-direction)
- [No Torrent/Piracy Layer](#no-torrentpiracy-layer)
- [Catalog Must Be a Separate System](#catalog-must-be-a-separate-system)
- [Do not confuse metadata retrieval with media transfer](#do-not-confuse-metadata-retrieval-with-media-transfer)
- [Catalog + Discovery: separate browsing from playback](#catalog-+-discovery-separate-browsing-from-playback)
- [Search is not arbitrary web search](#search-is-not-arbitrary-web-search)
- [The unified application layer](#the-unified-application-layer)

---

## Target architecture

```text
                         ┌─────────────────────┐
                         │       Stremio        │
                         └──────────┬──────────┘
                                    │
                             /manifest.json
                                    │
                ┌───────────────────▼───────────────────┐
                │           Popcorn-style Addon          │
                │                                         │
                │  catalog / meta / stream / subtitles   │
                └───────────────────┬───────────────────┘
                                    │
                           Resolve(title ID)
                                    │
                     ┌──────────────▼──────────────┐
                     │       Source Orchestrator    │
                     │                              │
                     │ normalize → query → merge    │
                     │ score → dedupe → emit        │
                     └──────────────┬──────────────┘
                                    │
          ┌─────────────────────────┼────────────────────────┐
          │                         │                        │
          ▼                         ▼                        ▼
 ┌────────────────┐       ┌────────────────┐       ┌────────────────┐
 │ Public-domain   │       │ Licensed API   │       │ User-provided  │
 │ adapter         │       │ adapter        │       │ source adapter │
 └───────┬────────┘       └───────┬────────┘       └───────┬────────┘
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                   │
                          normalized sources
                                   │
                         ┌────────▼─────────┐
                         │  Source Registry  │
                         └────────┬─────────┘
                                   │
                         ┌────────▼─────────┐
                         │ Ranking / Policy  │
                         └────────┬─────────┘
                                   │
                    ┌─────────────▼─────────────┐
                    │  Stremio Stream Objects    │
                    └───────────────────────────┘
```

The important architectural distinction is:

```text
Source discovery
      ≠ Source authorization
      ≠ Stream resolution
      ≠ Stream ranking
      ≠ Playback
```

The addon should **not become a downloader/proxy** unless there is a
legitimate reason to proxy an authorized source.

## What I would explicitly NOT build

To keep the project legitimate and technically maintainable, don't make
the core architecture depend on:

```text
✗ scraping unauthorized streaming sites
✗ circumventing paywalls
✗ bypassing DRM
✗ credential theft
✗ hidden APIs
✗ torrent-index scraping for copyrighted releases
✗ automatic downloading of copyrighted movies
✗ proxying arbitrary third-party URLs without authorization
```

Instead:

```text
✓ public-domain repositories
✓ licensed content APIs
✓ user-owned media servers
✓ authorized streaming services
✓ explicitly permitted source APIs
✓ local files / NAS
✓ legitimate subtitle APIs
```

The Stremio protocol itself is neutral: it is designed to aggregate
multimedia sources, and an addon can return multiple streams for a
title.

## Don't build a media proxy into v0.1

A common temptation is:

```text
Stremio
   ↓
Addon
   ↓
your server
   ↓
source
```

But if Stremio can play:

```text
Stremio
   ↓
source
```

prefer the latter.

The addon becomes:

```text
control plane
```

rather than:

```text
media data plane
```

This reduces:

- bandwidth cost
- server CPU
- privacy exposure
- legal complexity
- failure modes
- SSRF surface

## What this means for the Popcorn-Time-style experience

The UX can still be:

```text
Movie
    ↓
play
    ↓
multiple sources
    ↓
quality/language choices
```

But the backend semantics are cleaner:

```text
Popcorn-Time-style UX
        ≠
Popcorn-Time-style acquisition mechanism
```

The aggregator can support authorized/public-domain/user-owned sources
without embedding unauthorized scraping or bypass mechanisms.

## Catalog is not source discovery

This distinction is critical.

```text
Catalog: "What titles should Stremio display?"

Source discovery: "What eligible playback resources exist for this title?"
```

They may use related providers but they are not the same operation.

A title can appear in a catalog while currently having:

```text
0 eligible sources
```

and a source can exist for a title that is not part of your catalog.

## Do not proxy streams by default

A Popcorn-Time-like architecture can be tempted to do:

```text
Stremio
    ↓
addon
    ↓
download/relay
    ↓
user
```

That introduces:

```text
bandwidth
memory
connection lifecycle
range requests
TLS content handling
abuse surface
privacy
legal obligations
```

The first implementation should instead return eligible direct-playback
URLs:

```text
addon
    ↓
Stremio
    ↓
authorized source
```

A media proxy should be a separate subsystem requiring an independent
threat and resource model.

## Catalog is a different problem

A catalog is potentially huge.

Do not make:

```text
/catalog
```

execute:

```text
every source adapter
```

Catalog should have its own authority:

```text
CatalogIndex
    │
    ├── title
    ├── canonical ID
    ├── type
    ├── year
    └── metadata
```

Then source availability is queried only after the user selects an
item.

That produces:

```text
browse
    ↓
catalog
    ↓
select
    ↓
resolve streams
```

rather than:

```text
browse
    ↓
resolve thousands of streams
```

## The resulting system is no longer "a scraper"

Its architecture is now closer to:

```text
             MEDIA RESOLUTION PLATFORM

┌──────────────────────────────────────────────┐
│                Stremio API                    │
└──────────────────────┬───────────────────────┘
                        │
┌──────────────────────▼───────────────────────┐
│             Application Layer                 │
│ identity / routing / orchestration            │
└───────────┬───────────────┬──────────────────┘
            │               │
      ┌─────▼─────┐   ┌────▼────────┐
      │   Domain  │   │   Runtime   │
      │ semantics │   │ reliability │
      └─────┬─────┘   └────┬────────┘
            │               │
            └───────┬───────┘
                     ▼
           ┌────────────────────┐
           │  Adapter Registry  │
           └─────────┬──────────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
    Metadata      Streams     Subtitles
    adapters      adapters     adapters
        │            │            │
        └────────────┼────────────┘
                     ▼
               External world
```

The external sources are deliberately kept at the edge.

## Dependency direction

The resulting dependency graph should be enforced:

```text
                    ┌──────────────┐
                     │   Stremio    │
                     │   Protocol   │
                     └──────┬───────┘
                            │
                            ▼
                     ┌──────────────┐
                     │     addon    │
                     └──────┬───────┘
                            │
                            ▼
                     ┌──────────────┐
                     │ application  │
                     └───┬──────┬───┘
                         │      │
              ┌──────────┘      └──────────┐
              ▼                            ▼
        ┌──────────┐                ┌──────────┐
        │  domain  │                │ runtime  │
        └──────────┘                └──────────┘
              ▲                            ▲
              │                            │
        ┌─────┴────────────────────────────┴─────┐
        │                adapters                 │
        └────────────────────────────────────────┘
```

The forbidden direction is:

```text
domain → Stremio SDK
domain → HTTP
domain → filesystem
domain → database
domain → logger implementation
```

## No Torrent/Piracy Layer

The multi-source architecture remains deliberately source-neutral but
authorization-bound.

Permitted adapter classes include:

```text
user-owned media server
licensed provider API
public-domain repository
explicitly authorized HTTP source
local filesystem/media server
organization-controlled storage
```

The architecture does not include:

```text
torrent index aggregation
pirated-content scraping
DRM bypass
paywall bypass
unauthorized provider extraction
credential theft
hidden/private APIs
```

This isn't merely a legal disclaimer; it is an architectural invariant:

```text
unknown authorization
      ↓
REJECT
```

## Catalog Must Be a Separate System

A catalog is not:

```text
run every stream adapter
```

Instead:

```text
CatalogIndex
    │
    ├── canonical media
    ├── title
    ├── type
    ├── identities
    ├── availability facts
    └── provenance
```

Then:

```text
/catalog
   ↓
CatalogIndex
```

while:

```text
/stream
   ↓
Resolver
   ↓
SourceAdapters
```

This avoids turning a simple catalog request into an expensive fan-out
across every provider.

## Do not confuse metadata retrieval with media transfer

The addon should normally return a playback URL:

```text
source
  ↓
metadata / manifest / lookup
  ↓
playback URL
  ↓
Stremio
  ↓
media server
```

It should **not** become:

```text
source
  ↓
addon
  ↓
download entire movie
  ↓
addon
  ↓
Stremio
```

The latter transforms the addon into a media relay.

That introduces:

- bandwidth multiplication,
- memory/disk pressure,
- connection management,
- abuse exposure,
- legal and authorization complexity,
- much more difficult cancellation semantics.

Therefore v0.1 should keep:

```text
addon = resolver
```

rather than:

```text
addon = media proxy
```

## Catalog + Discovery: separate browsing from playback

The next boundary is important enough to make explicit:

```text
CATALOG/DISCOVERY
    answers:
    "What media can I browse?"

STREAM RESOLUTION
    answers:
    "What authorized playback candidates exist for this media?"

METADATA
    answers:
    "What descriptive information is currently observed?"

IDENTITY
    answers:
    "Which canonical media entity does this identifier refer to?"
```

These are related questions, but they are **not the same operation**.

A source that can play a movie does not automatically become a
catalog provider.

## Search is not arbitrary web search

Search should be explicitly scoped.

```text
Search
   ↓
registered CatalogProvider(s)
   ↓
bounded query
   ↓
observations
   ↓
identity reconciliation
   ↓
dedupe
   ↓
rank
   ↓
results
```

Do not interpret:

```text
search("matrix")
```

as:

```text
crawl the Internet for anything containing "matrix"
```

That would destroy the provider boundary.

## The unified application layer

We now have enough subsystems to introduce a common application
façade:

```ts
interface MediaApplication {
  resolveStreams(
    request: StreamRequest,
    context: ResolutionRequestContext
  ): Promise<ResolutionResult>;

  getMetadata(
    request: MetadataRequest,
    context: ResolutionRequestContext
  ): Promise<MetadataResult>;

  getSubtitles(
    request: SubtitleRequest,
    context: ResolutionRequestContext
  ): Promise<SubtitleResult>;

  getCatalog(
    request: CatalogRequest,
    context: ResolutionRequestContext
  ): Promise<Page<CatalogEntry>>;

  search(
    request: SearchRequest,
    context: ResolutionRequestContext
  ): Promise<readonly SearchResult[]>;
}
```

This is not necessarily the final public API.

It is an architectural boundary.
