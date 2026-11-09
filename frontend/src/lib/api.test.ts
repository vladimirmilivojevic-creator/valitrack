import { afterEach, vi } from "vitest";
import { ApiError, api, qs, setCsrfToken } from "./api";

function mockFetch(status: number, body: unknown) {
  const fn = vi.fn().mockResolvedValue({ ok: status < 400, status, json: async () => body });
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => vi.unstubAllGlobals());

describe("api", () => {
  it("sends the CSRF token on changing requests only", async () => {
    setCsrfToken("token-123");
    const fetchMock = mockFetch(200, {});
    await api.get("/applications");
    await api.post("/applications", { name: "x" });
    expect(fetchMock.mock.calls[0][1].headers["X-CSRF-Token"]).toBeUndefined();
    expect(fetchMock.mock.calls[1][1].headers["X-CSRF-Token"]).toBe("token-123");
  });

  it("turns a FastAPI validation list into one readable sentence", async () => {
    mockFetch(422, { detail: [{ loc: ["body", "severity"], msg: "Input should be less than or equal to 3" }] });
    await expect(api.post("/x", {})).rejects.toThrow("severity: Input should be less than or equal to 3");
  });

  it("shows the text of a business rule error", async () => {
    mockFetch(409, { detail: "The person who prepared the version cannot approve its requirements." });
    const error = await api.post("/x", {}).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(409);
    expect((error as ApiError).message).toContain("cannot approve");
  });

  it("builds query strings without empty values", () => {
    expect(qs({ a: 1, b: "", c: undefined, d: false, e: "x y" })).toBe("?a=1&d=false&e=x+y");
    expect(qs({})).toBe("");
  });
});
