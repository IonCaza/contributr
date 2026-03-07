import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "./card";

describe("Card", () => {
  it("renders card with title and content", () => {
    render(
      <Card>
        <CardHeader>
          <CardTitle>Card Title</CardTitle>
          <CardDescription>Card description text</CardDescription>
        </CardHeader>
        <CardContent>Card body content</CardContent>
      </Card>
    );
    expect(screen.getByText("Card Title")).toBeInTheDocument();
    expect(screen.getByText("Card description text")).toBeInTheDocument();
    expect(screen.getByText("Card body content")).toBeInTheDocument();
  });

  it("renders with data-slot attributes", () => {
    const { container } = render(
      <Card>
        <CardContent>Content</CardContent>
      </Card>
    );
    expect(container.querySelector("[data-slot='card']")).toBeInTheDocument();
    expect(container.querySelector("[data-slot='card-content']")).toBeInTheDocument();
  });
});
