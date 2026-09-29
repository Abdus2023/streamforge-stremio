import type { MediaRef } from "./identity.js";
import type { SourceCandidate } from "./stream.js";

export type ResolutionStatus = "success" | "empty" | "partial" | "failed";

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

export interface Failure {
  readonly code: FailureCode;
  readonly sourceId?: string;
  readonly message?: string;
}

export interface ResolutionResult {
  readonly media: MediaRef;
  readonly status: ResolutionStatus;
  readonly candidates: readonly SourceCandidate[];
  readonly failures: readonly Failure[];
  readonly sourceCount: number;
  readonly durationMs: number;
}

export type AdapterStatus =
  | "success"
  | "empty"
  | "timeout"
  | "aborted"
  | "rate_limited"
  | "circuit_open"
  | "invalid_response"
  | "network_error"
  | "error";

export interface AdapterExecution {
  readonly adapterId: string;
  readonly status: AdapterStatus;
  readonly durationMs: number;
  readonly candidates: readonly SourceCandidate[];
  readonly error?: string;
}
