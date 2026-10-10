import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { fileRecord, geojsonCollection, measurementsPage } from "@/test/fixtures";
import { renderApp } from "@/test/render";
import { API, errorEnvelope, server } from "@/test/server";

const FILE = fileRecord();
const ROUTE = `/files/${FILE.id}`;

function serveCompletedFile() {
  server.use(
    http.get(`${API}/api/files/:id/`, () => HttpResponse.json(FILE)),
    http.get(`${API}/api/files/:id/geojson`, () => HttpResponse.json(geojsonCollection())),
    http.get(`${API}/api/files/:id/measurements/`, () => HttpResponse.json(measurementsPage([]))),
  );
}

describe("File details page", () => {
  it("shows the file summary and CRS exactly as reported by the API", async () => {
    serveCompletedFile();
    renderApp(ROUTE);

    expect(await screen.findByRole("heading", { level: 1, name: "survey.kml" })).toBeInTheDocument();
    const summary = screen.getByLabelText("File summary");
    expect(within(summary).getByText("120")).toBeInTheDocument();
    expect(within(summary).getByText("EPSG:32643")).toBeInTheDocument();
    expect(within(summary).getByText("WGS 84 / UTM zone 43N")).toBeInTheDocument();

    const crs = screen.getByRole("region", { name: "Coordinate reference systems" });
    expect(within(crs).getByText("EPSG:4326")).toBeInTheDocument();
    expect(within(crs).getByText(/avoid using latitude\/longitude degrees/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Measurements" })).toHaveAttribute("href", `${ROUTE}/measurements`);
  });

  it("draws the GeoJSON features on the map with one layer per geometry type", async () => {
    serveCompletedFile();
    renderApp(ROUTE);

    const layers = await screen.findByRole("group", { name: "Layers" });
    expect(within(layers).getByRole("checkbox", { name: /Polygons/ })).toBeChecked();
    expect(within(layers).getByRole("checkbox", { name: /Lines/ })).toBeInTheDocument();
    expect(within(layers).getByRole("checkbox", { name: /Points/ })).toBeInTheDocument();
    expect(document.querySelectorAll("path.leaflet-interactive").length).toBeGreaterThanOrEqual(3);
  });

  it("shows the feature breakdown from the measurement summary", async () => {
    serveCompletedFile();
    renderApp(ROUTE);
    const breakdown = await screen.findByRole("region", { name: "Feature breakdown" });
    const polygons = await within(breakdown).findByRole("row", { name: /Polygons/ });
    expect(within(polygons).getByText("70")).toBeInTheDocument();
    expect(within(polygons).getByText("68")).toBeInTheDocument();
  });

  it("explains a failed file instead of showing a map", async () => {
    server.use(
      http.get(`${API}/api/files/:id/`, () =>
        HttpResponse.json(
          fileRecord({
            status: "FAILED",
            feature_count: null,
            source_crs: null,
            measurement_crs: null,
            processing_error: "The uploaded file is not a valid ZIP archive.",
          }),
        ),
      ),
    );
    renderApp(ROUTE);
    expect(await screen.findByText("Processing failed.")).toBeInTheDocument();
    expect(screen.getByText("The uploaded file is not a valid ZIP archive.")).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Layers" })).not.toBeInTheDocument();
  });

  it("shows a not-found state for an unknown file", async () => {
    server.use(
      http.get(`${API}/api/files/:id/`, () =>
        HttpResponse.json(errorEnvelope("FILE_NOT_FOUND", "File not found."), { status: 404 }),
      ),
    );
    renderApp(ROUTE);
    expect(await screen.findByRole("heading", { name: "This file does not exist." })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to Files" })).toHaveAttribute("href", "/files");
  });

  it("shows a loading skeleton, then a retryable error when the API fails", async () => {
    server.use(
      http.get(`${API}/api/files/:id/`, () =>
        HttpResponse.json(errorEnvelope("INTERNAL_ERROR", "An unexpected error occurred."), { status: 500 }),
      ),
    );
    renderApp(ROUTE);
    expect(await screen.findByRole("status", { name: "Loading map" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Unable to load this dataset." })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
