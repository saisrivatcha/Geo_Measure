import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderApp } from "@/test/render";

describe("routing", () => {
  it.each([
    ["/", "Geospatial workspace"],
    ["/files", "Files"],
    ["/files/upload", "Upload dataset"],
    ["/settings", "Settings"],
  ])("renders %s", async (route, title) => {
    renderApp(route);
    expect(await screen.findByRole("heading", { level: 1, name: title })).toBeInTheDocument();
  });

  it("shows a not-found page for unknown routes", async () => {
    renderApp("/does/not/exist");
    expect(await screen.findByRole("heading", { name: "There is no page at this address." })).toBeInTheDocument();
  });

  it("navigates with the sidebar and marks the current page", async () => {
    const user = userEvent.setup();
    const { router } = renderApp("/");
    const nav = screen.getAllByRole("navigation", { name: "Main" })[0]!;

    await user.click(within(nav).getByRole("link", { name: "Files" }));
    expect(router.state.location.pathname).toBe("/files");
    expect(within(nav).getByRole("link", { name: "Files" })).toHaveAttribute("aria-current", "page");

    await user.click(screen.getAllByRole("link", { name: "Settings" })[0]!);
    expect(router.state.location.pathname).toBe("/settings");
  });

  it("links the overview call to action to the uploader", async () => {
    const user = userEvent.setup();
    const { router } = renderApp("/");
    await user.click(screen.getByRole("link", { name: "Upload dataset" }));
    expect(router.state.location.pathname).toBe("/files/upload");
  });
});
