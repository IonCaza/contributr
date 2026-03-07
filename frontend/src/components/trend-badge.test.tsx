import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { TrendBadge } from "./trend-badge";

describe("TrendBadge", () => {
  it("renders positive value with percentage", () => {
    render(<TrendBadge value={12.3} />);
    expect(screen.getByText("12.3%")).toBeInTheDocument();
  });

  it("renders negative value with absolute percentage", () => {
    render(<TrendBadge value={-5.67} />);
    expect(screen.getByText("5.7%")).toBeInTheDocument();
  });

  it("renders zero value", () => {
    render(<TrendBadge value={0} />);
    expect(screen.getByText("0.0%")).toBeInTheDocument();
  });

  it("applies emerald classes for positive values", () => {
    const { container } = render(<TrendBadge value={1} />);
    const badge = container.querySelector("[data-slot='badge']");
    expect(badge?.className).toContain("emerald");
  });

  it("applies red classes for negative values", () => {
    const { container } = render(<TrendBadge value={-1} />);
    const badge = container.querySelector("[data-slot='badge']");
    expect(badge?.className).toContain("red");
  });
});
