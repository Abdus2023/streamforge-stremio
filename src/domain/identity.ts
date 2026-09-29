export type MediaType = "movie" | "series";

export interface MediaRef {
  readonly type: MediaType;
  readonly id: string;
  readonly season?: number;
  readonly episode?: number;
}

export type IdentityKind = "imdb" | "tmdb" | "tvdb" | "internal";

export interface ExternalIdentity {
  readonly kind: IdentityKind;
  readonly value: string;
  readonly source: string;
  readonly observedAt: string;
}

export interface CanonicalMedia {
  readonly canonicalId: string;
  readonly media: MediaRef;
  readonly identities: readonly ExternalIdentity[];
  readonly resolvedAt: string;
}
