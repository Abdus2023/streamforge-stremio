import type { ExternalIdentity, MediaRef } from "../domain/identity.js";
import type { SourceAdapter } from "./source-adapter.js";

export class SourceRegistry {
  private readonly adapters = new Map<string, SourceAdapter>();

  register(adapter: SourceAdapter): void {
    if (this.adapters.has(adapter.id)) {
      throw new Error(`duplicate_source_adapter:${adapter.id}`);
    }
    this.adapters.set(adapter.id, adapter);
  }

  all(): readonly SourceAdapter[] {
    return [...this.adapters.values()];
  }

  applicableByMedia(media: MediaRef): readonly SourceAdapter[] {
    return this.all().filter((adapter) => adapter.supportsMedia(media));
  }

  applicableByIdentity(
    identities: readonly ExternalIdentity[]
  ): readonly SourceAdapter[] {
    return this.all().filter((adapter) => adapter.supportsIdentity(identities));
  }
}
