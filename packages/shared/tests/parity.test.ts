import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it, expect } from "vitest";
import { SiteSchema, WorkspaceSchema } from "../src/index.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

function loadFixture(name: string): unknown {
  const path = resolve(__dirname, "fixtures", name);
  return JSON.parse(readFileSync(path, "utf8"));
}

describe("cross-language fixtures parse via Zod", () => {
  it("accepts the canonical Site fixture", () => {
    const data = loadFixture("site.valid.json");
    const parsed = SiteSchema.parse(data);
    expect(parsed.id).toBe("11111111-1111-4111-8111-111111111111");
    expect(parsed.workspace_id).toBe("22222222-2222-4222-8222-222222222222");
    expect(parsed.url).toBe("https://example.com");
    expect(parsed.default_language).toBe("tr");
    expect(parsed.sector).toBe("fashion");
  });

  it("accepts the canonical Workspace fixture", () => {
    const data = loadFixture("workspace.valid.json");
    const parsed = WorkspaceSchema.parse(data);
    expect(parsed.id).toBe("33333333-3333-4333-8333-333333333333");
    expect(parsed.org_id).toBe("44444444-4444-4444-8444-444444444444");
    expect(parsed.name).toBe("Acme Agency Client #1");
    expect(parsed.slug).toBe("acme-agency-client-1");
    expect(parsed.created_at).toBe("2026-05-15T12:34:56.000Z");
  });

  it("rejects unknown keys on Site (.strict())", () => {
    const data = {
      ...(loadFixture("site.valid.json") as Record<string, unknown>),
      injected_field: "should fail",
    };
    const result = SiteSchema.safeParse(data);
    expect(result.success).toBe(false);
  });
});
