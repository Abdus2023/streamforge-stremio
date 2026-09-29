import type {
  CanonicalMedia,
  ExternalIdentity,
  MediaRef
} from "../domain/identity.js";
import type { SourceCandidate } from "../domain/stream.js";

export interface ResolveContext {
  readonly signal: AbortSignal;
  readonly timeoutMs: number;
  readonly preferredLanguages: readonly string[];
}

export interface HealthResult {
  readonly healthy: boolean;
  readonly checkedAt: string;
  readonly detail?: string;
}

export interface SourceAdapter {
  readonly id: string;
  supportsMedia(media: MediaRef): boolean;
  supportsIdentity(identities: readonly ExternalIdentity[]): boolean;
  resolve(
    media: CanonicalMedia,
    context: ResolveContext
  ): Promise<readonly SourceCandidate[]>;
}

export interface Named {
  readonly name: string;
}

export interface HealthCheckable {
  health(): Promise<HealthResult>;
}

export interface CapabilityDeclaring {
  readonly capabilities: unknown;
}
