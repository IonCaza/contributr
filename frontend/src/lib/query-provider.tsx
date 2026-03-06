"use client";

import { QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools/production";
import { queryClient } from "./query-client";

export function QueryProvider({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <ReactQueryDevtools
        initialIsOpen={false}
        buttonPosition="bottom-right"
        toggleButtonProps={{
          style: { transform: "scale(0.5)", transformOrigin: "bottom right" },
        }}
      />
    </QueryClientProvider>
  );
}
