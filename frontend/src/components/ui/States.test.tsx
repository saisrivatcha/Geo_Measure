import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ApiError } from "@/services/api";

import { EmptyState, ErrorState } from "./States";

describe("EmptyState", () => {
  it("shows the title, explanation and call to action", () => {
    render(
      <EmptyState
        title="No geospatial files yet."
        description="Upload a dataset to begin."
        actions={<button type="button">Upload your first dataset</button>}
      />,
    );
    expect(screen.getByRole("heading", { name: "No geospatial files yet." })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload your first dataset" })).toBeInTheDocument();
  });
});

describe("ErrorState", () => {
  it("shows the API's human-readable message and code, and retries", async () => {
    const onRetry = vi.fn();
    render(
      <ErrorState
        title="Unable to load this dataset."
        description="The dataset may have been removed or the API is unavailable."
        error={new ApiError(409, "FILE_NOT_PROCESSED", "The file is FAILED; results are only available once COMPLETED.")}
        onRetry={onRetry}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Unable to load this dataset.");
    expect(screen.getByText(/results are only available once COMPLETED/)).toBeInTheDocument();
    expect(screen.getByText("Error code FILE_NOT_PROCESSED")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("explains network failures without leaking internals", () => {
    render(<ErrorState title="Unable to load files." error={new ApiError(0, "NETWORK_ERROR", "x")} />);
    expect(screen.getByText(/API is unavailable/)).toBeInTheDocument();
    expect(screen.queryByText(/Error code/)).not.toBeInTheDocument();
  });

  it("falls back to the description for non-API errors", () => {
    render(<ErrorState title="Unable to load." description="Try again later." error={new Error("boom")} />);
    expect(screen.getByText("Try again later.")).toBeInTheDocument();
    expect(screen.queryByText("boom")).not.toBeInTheDocument();
  });
});
