import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { DateRangeFilter, defaultRange } from "./date-range-filter";

describe("DateRangeFilter", () => {
  const onChange = vi.fn();

  it("renders all preset buttons", () => {
    render(<DateRangeFilter value={defaultRange()} onChange={onChange} />);
    for (const label of ["7d", "30d", "90d", "1y", "All"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("renders Custom button", () => {
    render(<DateRangeFilter value={defaultRange()} onChange={onChange} />);
    expect(screen.getByText("Custom")).toBeInTheDocument();
  });

  it("calls onChange when a preset is clicked", () => {
    onChange.mockClear();
    render(<DateRangeFilter value={defaultRange()} onChange={onChange} />);
    fireEvent.click(screen.getByText("7d"));
    expect(onChange).toHaveBeenCalledTimes(1);
    const arg = onChange.mock.calls[0][0];
    expect(arg).toHaveProperty("from");
    expect(arg).toHaveProperty("to");
  });

  it("shows date inputs when Custom is clicked", () => {
    const { container } = render(
      <DateRangeFilter value={defaultRange()} onChange={onChange} />
    );
    expect(container.querySelectorAll("input[type='date']")).toHaveLength(0);
    fireEvent.click(screen.getByText("Custom"));
    expect(container.querySelectorAll("input[type='date']")).toHaveLength(2);
  });
});

describe("defaultRange", () => {
  it("returns object with from and to strings", () => {
    const range = defaultRange();
    expect(typeof range.from).toBe("string");
    expect(typeof range.to).toBe("string");
    expect(range.from.length).toBe(10); // YYYY-MM-DD
    expect(range.to.length).toBe(10);
  });
});
