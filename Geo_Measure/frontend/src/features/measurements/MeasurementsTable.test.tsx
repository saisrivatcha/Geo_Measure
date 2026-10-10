import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { feature } from "@/test/fixtures";

import { MeasurementsTable } from "./MeasurementsTable";

const FEATURES = [
  feature(),
  feature({
    feature_index: 12,
    geometry_type: "LineString",
    measurement: {
      type: "LENGTH",
      value: 2841.1921,
      unit: "meters",
      area_square_km: null,
      area_hectares: null,
      length_km: 2.8411921,
      display: "2.841 km",
    },
  }),
  feature({ feature_index: 13, geometry_type: "Point", measurement: null, measurement_status: "NOT_REQUIRED" }),
  feature({
    feature_index: 14,
    geometry_type: "GeometryCollection",
    measurement: null,
    measurement_status: "NOT_SUPPORTED",
  }),
];

function rowFor(index: number): HTMLElement {
  return screen.getByRole("row", { name: new RegExp(`^Feature ${index},`) });
}

describe("MeasurementsTable", () => {
  it("renders formatted measurements with units and CRS", () => {
    render(<MeasurementsTable features={FEATURES} isLoading={false} isFetching={false} selectedIndex={null} onSelect={() => {}} />);

    const polygon = within(rowFor(0));
    expect(polygon.getByText("15,234.83")).toHaveAttribute("value", "15234.82731"); // precision kept
    expect(polygon.getByText("m²")).toBeInTheDocument();
    expect(polygon.getByText("EPSG:4326")).toBeInTheDocument();
    expect(polygon.getByText("EPSG:32643")).toBeInTheDocument();
    expect(polygon.getByText("Completed")).toBeInTheDocument();

    const line = within(rowFor(12));
    expect(line.getByText("2,841.19")).toBeInTheDocument();
    expect(line.getByText("m")).toBeInTheDocument();

    expect(within(rowFor(13)).getByText("Not required")).toBeInTheDocument();
    expect(within(rowFor(14)).getByText("Not supported")).toBeInTheDocument();
  });

  it("opens a feature by click or keyboard", async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    render(<MeasurementsTable features={FEATURES} isLoading={false} isFetching={false} selectedIndex={null} onSelect={onSelect} />);

    await user.click(rowFor(12));
    expect(onSelect).toHaveBeenLastCalledWith(expect.objectContaining({ feature_index: 12 }));

    rowFor(13).focus();
    await user.keyboard("{Enter}");
    expect(onSelect).toHaveBeenLastCalledWith(expect.objectContaining({ feature_index: 13 }));
  });

  it("shows a table skeleton while loading", () => {
    render(<MeasurementsTable features={undefined} isLoading isFetching={false} selectedIndex={null} onSelect={() => {}} />);
    expect(screen.getByRole("status", { name: "Loading Feature measurements" })).toBeInTheDocument();
  });
});
