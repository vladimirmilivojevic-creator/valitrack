import { daysFromToday, fileSize, fmtDate, riskOf, shortHash, titleCase } from "./format";

describe("riskOf", () => {
  it("uses the same limits as the backend", () => {
    expect(riskOf(1, 1, 1)).toEqual({ rpn: 1, level: "low" });
    expect(riskOf(2, 2, 1)).toEqual({ rpn: 4, level: "low" });
    expect(riskOf(2, 3, 1)).toEqual({ rpn: 6, level: "medium" });
    expect(riskOf(2, 2, 2)).toEqual({ rpn: 8, level: "medium" });
    expect(riskOf(3, 2, 2)).toEqual({ rpn: 12, level: "high" });
    expect(riskOf(3, 3, 3)).toEqual({ rpn: 27, level: "high" });
  });

  it("gives nothing until all three ratings exist", () => {
    expect(riskOf(null, 2, 2)).toBeNull();
    expect(riskOf(3, null, 2)).toBeNull();
    expect(riskOf(3, 2, null)).toBeNull();
  });
});

describe("formatting helpers", () => {
  it("formats plain dates without a time zone shift", () => {
    expect(fmtDate("2026-11-09")).toBe("2026-11-09");
    expect(fmtDate(null)).toBe("-");
  });

  it("shortens hashes and sizes", () => {
    expect(shortHash("abcdef0123456789", 6)).toBe("abcdef");
    expect(shortHash(null)).toBe("-");
    expect(fileSize(512)).toBe("512 B");
    expect(fileSize(2048)).toBe("2.0 KB");
  });

  it("turns snake case into a sentence", () => {
    expect(titleCase("impact_assessment")).toBe("Impact assessment");
  });

  it("counts days from today", () => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const iso = `${tomorrow.getFullYear()}-${String(tomorrow.getMonth() + 1).padStart(2, "0")}-${String(tomorrow.getDate()).padStart(2, "0")}`;
    expect(daysFromToday(iso)).toBe(1);
    expect(daysFromToday(null)).toBeNull();
  });
});
