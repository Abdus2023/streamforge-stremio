import type { MediaRef } from "./identity.js";

export interface SourceCandidate {
  readonly sourceId: string;
  readonly media: MediaRef;
  readonly location: {
    readonly url: string;
  };
  readonly mediaInfo: {
    readonly container?: string;
    readonly videoCodec?: string;
    readonly audioCodec?: string;
    readonly width?: number;
    readonly height?: number;
    readonly bitrate?: number;
    readonly sizeBytes?: number;
    readonly durationSeconds?: number;
  };
  readonly language: {
    readonly audio?: readonly string[];
    readonly subtitle?: readonly string[];
  };
  readonly provenance: {
    readonly adapter: string;
    readonly sourceRecordId?: string;
    readonly observedAt: string;
  };
  readonly capabilities: {
    readonly directPlayback: boolean;
    readonly seekable?: boolean;
    readonly live?: boolean;
  };
  readonly authorization: {
    readonly status: "authorized" | "unknown" | "denied";
    readonly basis?: string;
  };
}
