import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { Badge } from "./badge";

describe("Badge", () => {
  it("renders children", () => {
    render(<Badge>Status</Badge>);
    expect(screen.getByText("Status")).toBeInTheDocument();
  });

  it("has data-slot='badge'", () => {
    render(<Badge>Test</Badge>);
    expect(screen.getByText("Test").closest("[data-slot='badge']")).not.toBeNull();
  });

  it("applies default variant", () => {
    render(<Badge>Default</Badge>);
    const el = screen.getByText("Default");
    expect(el.getAttribute("data-variant")).toBe("default");
  });

  it("applies secondary variant", () => {
    render(<Badge variant="secondary">Sec</Badge>);
    expect(screen.getByText("Sec").getAttribute("data-variant")).toBe("secondary");
  });

  it("applies destructive variant", () => {
    render(<Badge variant="destructive">Err</Badge>);
    expect(screen.getByText("Err").getAttribute("data-variant")).toBe("destructive");
  });

  it("merges custom className", () => {
    render(<Badge className="custom-class">C</Badge>);
    expect(screen.getByText("C").className).toContain("custom-class");
  });
});
