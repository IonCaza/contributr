import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "./tabs";

describe("Tabs", () => {
  it("renders triggers and shows active content", () => {
    render(
      <Tabs defaultValue="a">
        <TabsList>
          <TabsTrigger value="a">Tab A</TabsTrigger>
          <TabsTrigger value="b">Tab B</TabsTrigger>
        </TabsList>
        <TabsContent value="a">Content A</TabsContent>
        <TabsContent value="b">Content B</TabsContent>
      </Tabs>
    );

    expect(screen.getByText("Tab A")).toBeInTheDocument();
    expect(screen.getByText("Tab B")).toBeInTheDocument();
    expect(screen.getByText("Content A")).toBeInTheDocument();
  });

  it("marks default tab trigger as active", () => {
    const { container } = render(
      <Tabs defaultValue="a">
        <TabsList>
          <TabsTrigger value="a">Tab A</TabsTrigger>
          <TabsTrigger value="b">Tab B</TabsTrigger>
        </TabsList>
        <TabsContent value="a">Content A</TabsContent>
        <TabsContent value="b">Content B</TabsContent>
      </Tabs>
    );

    const triggers = container.querySelectorAll("[data-slot='tabs-trigger']");
    const triggerA = Array.from(triggers).find((t) => t.textContent === "Tab A");
    expect(triggerA?.getAttribute("data-state")).toBe("active");
    const triggerB = Array.from(triggers).find((t) => t.textContent === "Tab B");
    expect(triggerB?.getAttribute("data-state")).toBe("inactive");
  });

  it("renders with data-slot attributes", () => {
    const { container } = render(
      <Tabs defaultValue="a">
        <TabsList>
          <TabsTrigger value="a">T</TabsTrigger>
        </TabsList>
        <TabsContent value="a">C</TabsContent>
      </Tabs>
    );

    expect(container.querySelector("[data-slot='tabs']")).not.toBeNull();
    expect(container.querySelector("[data-slot='tabs-list']")).not.toBeNull();
    expect(container.querySelector("[data-slot='tabs-trigger']")).not.toBeNull();
    expect(container.querySelector("[data-slot='tabs-content']")).not.toBeNull();
  });
});
