import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { StatCard } from "./stat-card";

vi.mock("@/components/charts/mini-sparkline", () => ({
  MiniSparkline: () => <div data-testid="sparkline" />,
}));

describe("StatCard", () => {
  it("renders title and string value", () => {
    render(<StatCard title="Commits" value="1,234" />);
    expect(screen.getByText("Commits")).toBeInTheDocument();
    expect(screen.getByText("1,234")).toBeInTheDocument();
  });

  it("formats numeric value with toLocaleString", () => {
    render(<StatCard title="Lines" value={5000} />);
    expect(screen.getByText("5,000")).toBeInTheDocument();
  });

  it("renders subtitle when provided", () => {
    render(<StatCard title="T" value="V" subtitle="last 30 days" />);
    expect(screen.getByText("last 30 days")).toBeInTheDocument();
  });

  it("renders trend badge when trend is provided", () => {
    render(<StatCard title="T" value="V" trend={10.5} />);
    expect(screen.getByText("10.5%")).toBeInTheDocument();
  });

  it("calls onClick when card is clicked", () => {
    const handler = vi.fn();
    render(<StatCard title="T" value="V" onClick={handler} />);
    fireEvent.click(screen.getByText("T"));
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("does not render subtitle when not provided", () => {
    const { container } = render(<StatCard title="T" value="V" />);
    expect(container.querySelector("p.text-xs")).toBeNull();
  });
});
