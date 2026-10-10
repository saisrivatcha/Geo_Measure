import { validateSelection } from "./FileDropzone";

const LIMITS = { maxBytes: 1024, allowedExtensions: [".kml", ".zip"] };

describe("validateSelection", () => {
  it("accepts KML and ZIP files within the limit", () => {
    expect(validateSelection(new File(["<kml/>"], "a.KML"), LIMITS)).toBeNull();
    expect(validateSelection(new File(["PK"], "parcels.zip"), LIMITS)).toBeNull();
  });

  it.each([
    ["tour.kmz", "x", /KMZ files are not supported/],
    ["roads.geojson", "x", /not a supported file/],
    ["empty.kml", "", /is empty/],
    ["big.zip", "x".repeat(2048), /the limit is 1.0 KB/],
  ])("rejects %s", (name, content, message) => {
    expect(validateSelection(new File([content], name), LIMITS)).toMatch(message);
  });
});
