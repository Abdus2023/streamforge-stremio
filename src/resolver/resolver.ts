import type { CanonicalMedia } from "../domain/identity.js";
import type {
  AdapterExecution,
  Failure,
  ResolutionResult
} from "../domain/result.js";
import type { SourceCandidate } from "../domain/stream.js";
import type { SourceRegistry } from "../adapters/registry.js";
import type { ResolveContext } from "../adapters/source-adapter.js";
import { evaluatePolicy } from "./policy.js";

function canonicalizeUrl(input: string): string {
  const url = new URL(input);
  url.hash = "";
  return url.toString();
}

function candidateKey(candidate: SourceCandidate): string {
  return [
    candidate.media.type,
    candidate.media.id,
    candidate.media.season ?? "",
    candidate.media.episode ?? "",
    canonicalizeUrl(candidate.location.url)
  ].join("|");
}

function validateCandidate(candidate: SourceCandidate): boolean {
  if (!candidate.sourceId || !candidate.provenance.adapter) return false;
  try {
    const url = new URL(candidate.location.url);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

function deduplicate(candidates: readonly SourceCandidate[]): SourceCandidate[] {
  const unique = new Map<string, SourceCandidate>();
  for (const candidate of candidates) {
    const key = candidateKey(candidate);
    if (!unique.has(key)) unique.set(key, candidate);
  }
  return [...unique.values()];
}

function adapterExecution(
  adapterId: string,
  status: AdapterExecution["status"],
  durationMs: number,
  candidates: readonly SourceCandidate[],
  error?: string
): AdapterExecution {
  return { adapterId, status, durationMs, candidates, ...(error ? { error } : {}) };
}

export async function resolveCanonicalMedia(
  media: CanonicalMedia,
  registry: SourceRegistry,
  context: ResolveContext
): Promise<ResolutionResult> {
  const started = performance.now();
  const applicable = registry
    .applicableByMedia(media.media)
    .filter((adapter) => adapter.supportsIdentity(media.identities));

  const executions: AdapterExecution[] = await Promise.all(
    applicable.map(async (adapter): Promise<AdapterExecution> => {
      const adapterStarted = performance.now();
      try {
        const candidates = await adapter.resolve(media, context);
        return adapterExecution(
          adapter.id,
          candidates.length === 0 ? "empty" : "success",
          performance.now() - adapterStarted,
          candidates
        );
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        return adapterExecution(
          adapter.id,
          context.signal.aborted ? "aborted" : "error",
          performance.now() - adapterStarted,
          [],
          message
        );
      }
    })
  );

  const failures: Failure[] = [];
  const accepted: SourceCandidate[] = [];

  for (const execution of executions) {
    if (execution.status === "error" || execution.status === "aborted") {
      failures.push({
        code: execution.status === "aborted" ? "source_aborted" : "internal_error",
        sourceId: execution.adapterId,
        ...(execution.error ? { message: execution.error } : {})
      });
      continue;
    }

    for (const candidate of execution.candidates) {
      if (!validateCandidate(candidate)) {
        failures.push({
          code: "candidate_invalid",
          sourceId: execution.adapterId
        });
        continue;
      }

      const policy = evaluatePolicy(candidate);
      if (!policy.allowed) {
        failures.push({
          code: "candidate_not_authorized",
          sourceId: execution.adapterId,
          message: policy.reasons.join(",")
        });
        continue;
      }

      accepted.push(candidate);
    }
  }

  const candidates = deduplicate(accepted);
  const hadFailure = failures.length > 0;

  const status =
    candidates.length > 0
      ? hadFailure ? "partial" : "success"
      : hadFailure ? "failed" : "empty";

  return {
    media: media.media,
    status,
    candidates,
    failures,
    sourceCount: applicable.length,
    durationMs: performance.now() - started
  };
}
