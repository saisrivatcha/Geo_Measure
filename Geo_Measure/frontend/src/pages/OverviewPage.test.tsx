import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { stats } from "@/test/fixtures";
import { renderApp } from "@/test/render";
import { API, server } from "@/test/server";

describe("Overview page", () => {
  it("shows workspace statistics from the API", async () => {
    server.use(
      http.get(`${API}/api/stats`, () =>
        HttpResponse.json({ ...stats, files: { total: 12, completed: 9, in_progress: 1, failed: 2 } }),
      ),
    );
    renderApp("/");

    const list = screen.getByLabelText("Workspace statistics");
    expect(await within(list).findByText("9")).toBeInTheDocument(); // files processed
    expect(within(list).getByText("120")).toBeInTheDocument(); // features indexed
    expect(within(list).getByText("100")).toBeInTheDocument(); // features measured
    expect(within(list).getByText("2")).toBeInTheDocument(); // failed jobs
    expect(within(list).getByText("1 in progress")).toBeInTheDocument();
  });

  it("lists recent files and the measurement overview", async () => {
    renderApp("/");
    expect(await screen.findByRole("row", { name: "Open survey.kml" })).toBeInTheDocument();
    expect(await screen.findByText(/1.52 km² of polygon area and 28.41 km of line length measured/)).toBeInTheDocument();
  });
});
