import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { Input } from "./input";

describe("Input", () => {
  it("renders with placeholder", () => {
    render(<Input placeholder="Enter value" />);
    expect(screen.getByPlaceholderText("Enter value")).toBeInTheDocument();
  });

  it("renders with value", () => {
    render(<Input value="test value" readOnly />);
    expect(screen.getByDisplayValue("test value")).toBeInTheDocument();
  });

  it("has data-slot for input", () => {
    const { container } = render(<Input />);
    expect(container.querySelector("[data-slot='input']")).toBeInTheDocument();
  });
});
