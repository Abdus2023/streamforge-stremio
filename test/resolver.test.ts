import assert from "node:assert/strict";
import test from "node:test";
import { SourceRegistry } from "../src/adapters/registry.js";
import type { SourceAdapter, ResolveContext } from "../src/adapters/source-adapter.js";
import type { CanonicalMedia } from "../src/domain/identity.js";
import type { SourceCandidate } from "../src/domain/stream.js";
import { evaluatePolicy } from "../src/resolver/policy.js";
import { resolveCanonicalMedia } from "../src/resolver/resolver.js";

const media: CanonicalMedia = {
  canonicalId: "media:test",
  media: { type: "movie", id: "tt1234567" },
  identities: [
    {
      kind: "imdb",
      value: "tt1234567",
      source: "fixture",
      observedAt: "2026-09-29T00:00:00Z"
    }
  ],
  resolvedAt: "2026-09-29T00:00:00Z"
};

const context: ResolveContext = {
  signal: new AbortController().signal,
  timeoutMs: 1000,
  preferredLanguages: ["en"]
};

function candidate(url: string, status: "authorized" | "unknown" | "denied" = "authorized"): SourceCandidate {
  return {
    sourceId: "fixture",
    media: media.media,
    location: { url },
    mediaInfo: { width: 1920, height: 1080, container: "mp4" },
    language: { audio: ["en"] },
    provenance: {
      adapter: "fixture",
      observedAt: "2026-09-29T00:00:00Z"
    },
    capabilities: { directPlayback: true },
    authorization: { status }
  };
}

function adapter(id: string, output: readonly SourceCandidate[]): SourceAdapter {
  return {
    id,
    supportsMedia: () => true,
    supportsIdentity: () => true,
    resolve: async () => output
  };
}

test("registry separates media and identity applicability", () => {
  const registry = new SourceRegistry();
  registry.register(adapter("fixture", []));

  assert.equal(registry.all().length, 1);
  assert.equal(registry.applicableByMedia(media.media).length, 1);
  assert.equal(registry.applicableByIdentity(media.identities).length, 1);
});

test("policy rejects unknown and denied authorization", () => {
  assert.equal(evaluatePolicy(candidate("https://example.test/a", "unknown")).allowed, false);
  assert.equal(evaluatePolicy(candidate("https://example.test/a", "denied")).allowed, false);
  assert.equal(evaluatePolicy(candidate("https://example.test/a")).allowed, true);
});

test("resolver preserves partial success", async () => {
  const registry = new SourceRegistry();
  registry.register(adapter("good", [candidate("https://example.test/a")]));
  registry.register({
    id: "broken",
    supportsMedia: () => true,
    supportsIdentity: () => true,
    resolve: async () => {
      throw new Error("fixture_failure");
    }
  });

  const result = await resolveCanonicalMedia(media, registry, context);

  assert.equal(result.status, "partial");
  assert.equal(result.candidates.length, 1);
  assert.equal(result.failures.length, 1);
});

test("resolver rejects unknown authorization before output", async () => {
  const registry = new SourceRegistry();
  registry.register(adapter("unknown", [candidate("https://example.test/a", "unknown")]));

  const result = await resolveCanonicalMedia(media, registry, context);

  assert.equal(result.status, "failed");
  assert.equal(result.candidates.length, 0);
  assert.equal(result.failures[0]?.code, "candidate_not_authorized");
});

test("resolver deduplicates equivalent URLs", async () => {
  const registry = new SourceRegistry();
  registry.register(
    adapter("a", [candidate("https://example.test/a#fragment")])
  );
  registry.register(
    adapter("b", [candidate("https://example.test/a")])
  );

  const result = await resolveCanonicalMedia(media, registry, context);

  assert.equal(result.status, "success");
  assert.equal(result.candidates.length, 1);
});
