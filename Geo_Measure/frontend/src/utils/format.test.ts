import { formatArea, formatBytes, formatDecimal, formatExact, formatLength, formatMeasurement } from "./format";

describe("measurement formatting", () => {
  it("rounds areas to two decimals with grouping", () => {
    expect(formatMeasurement(15234.82731, "square_meters")).toBe("15,234.83 m²");
  });

  it("rounds lengths to two decimals with grouping", () => {
    expect(formatMeasurement(2841.1921, "meters")).toBe("2,841.19 m");
  });

  it("keeps full precision available for detail views", () => {
    const value = 15234.82731;
    expect(formatExact(value)).toBe("15,234.82731");
    expect(value).toBe(15234.82731); // formatting never mutates the source number
  });

  it("scales large totals to readable units", () => {
    expect(formatArea(9_999)).toBe("9,999.00 m²");
    expect(formatArea(25_000)).toBe("2.50 ha");
    expect(formatArea(1_523_482.731)).toBe("1.52 km²");
    expect(formatLength(999.5)).toBe("999.50 m");
    expect(formatLength(28_411.921)).toBe("28.41 km");
  });

  it("formats decimals and file sizes", () => {
    expect(formatDecimal(0.005)).toBe("0.01");
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(182_304)).toBe("178 KB");
    expect(formatBytes(52_428_800)).toBe("50 MB");
  });
});
