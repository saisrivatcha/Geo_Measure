import { render, screen } from "@testing-library/react";

import type { FileStatus, MeasurementStatus } from "@/types/api";

import { MeasurementStatusBadge, StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it.each<[FileStatus, string]>([
    ["COMPLETED", "Completed"],
    ["PROCESSING", "Processing"],
    ["PENDING", "Pending"],
    ["FAILED", "Failed"],
  ])("labels %s as %s", (status, label) => {
    render(<StatusBadge status={status} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it("uses distinct tones for success, progress and failure", () => {
    const { container, rerender } = render(<StatusBadge status="COMPLETED" />);
    expect(container.firstElementChild).toHaveClass("success");
    rerender(<StatusBadge status="PROCESSING" />);
    expect(container.firstElementChild).toHaveClass("progress");
    rerender(<StatusBadge status="FAILED" />);
    expect(container.firstElementChild).toHaveClass("danger");
  });
});

describe("MeasurementStatusBadge", () => {
  it.each<[MeasurementStatus, string]>([
    ["COMPLETED", "Completed"],
    ["NOT_REQUIRED", "Not required"],
    ["NOT_SUPPORTED", "Not supported"],
    ["INVALID_GEOMETRY", "Invalid geometry"],
    ["CRS_UNAVAILABLE", "CRS unavailable"],
  ])("labels %s readably and explains it on hover", (status, label) => {
    render(<MeasurementStatusBadge status={status} />);
    const badge = screen.getByText(label).closest("span");
    expect(badge).toHaveAttribute("title");
  });
});
