"use client";

import React, { Suspense } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "./query-client";

const ReactQueryDevtools =
  process.env.NODE_ENV === "development"
    ? React.lazy(() =>
        import("@tanstack/react-query-devtools").then((mod) => ({
          default: mod.ReactQueryDevtools,
        }))
      )
    : () => null;

export function QueryProvider({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <Suspense fallback={null}>
        <ReactQueryDevtools
          initialIsOpen={false}
          buttonPosition="top-right"
        />
      </Suspense>
    </QueryClientProvider>
  );
}
