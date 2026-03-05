"use client";

import { useState, useRef, useEffect } from "react";
import { ChevronDown, Search, X, Check, GitBranch } from "lucide-react";

interface Props {
  branches: { id: string; name: string; is_default?: boolean }[];
  selected: string[];
  onChange: (selected: string[]) => void;
}

export function BranchMultiSelect({ branches, selected, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const filtered = branches.filter((b) =>
    b.name.toLowerCase().includes(search.toLowerCase())
  );

  function toggle(name: string) {
    onChange(
      selected.includes(name) ? selected.filter((s) => s !== name) : [...selected, name]
    );
  }

  const label =
    selected.length === 0
      ? "All branches"
      : selected.length === 1
        ? selected[0]
        : `${selected.length} branches`;

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-md border border-border bg-background px-3 py-1.5 text-sm font-medium hover:bg-accent transition-colors min-w-[200px]"
      >
        <GitBranch className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
        <span className="truncate flex-1 text-left">{label}</span>
        {selected.length > 0 && (
          <button
            onClick={(e) => { e.stopPropagation(); onChange([]); }}
            className="shrink-0 rounded-sm p-0.5 hover:bg-muted"
          >
            <X className="h-3 w-3 text-muted-foreground" />
          </button>
        )}
        <ChevronDown className={`h-3.5 w-3.5 text-muted-foreground shrink-0 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute top-full left-0 z-50 mt-1 w-72 rounded-lg border border-border bg-popover shadow-lg">
          <div className="flex items-center gap-2 border-b border-border px-3 py-2">
            <Search className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            <input
              autoFocus
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search branches..."
              className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            />
            {search && (
              <button onClick={() => setSearch("")} className="shrink-0">
                <X className="h-3 w-3 text-muted-foreground" />
              </button>
            )}
          </div>
          <div className="max-h-64 overflow-y-auto py-1">
            {filtered.length === 0 ? (
              <div className="px-3 py-4 text-center text-sm text-muted-foreground">
                No branches match &quot;{search}&quot;
              </div>
            ) : (
              filtered.map((b) => {
                const isSelected = selected.includes(b.name);
                return (
                  <button
                    key={b.id}
                    onClick={() => toggle(b.name)}
                    className={`flex w-full items-center gap-2 px-3 py-1.5 text-sm transition-colors hover:bg-accent ${
                      isSelected ? "text-foreground" : "text-muted-foreground"
                    }`}
                  >
                    <div className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-sm border ${
                      isSelected ? "border-primary bg-primary text-primary-foreground" : "border-border"
                    }`}>
                      {isSelected && <Check className="h-3 w-3" />}
                    </div>
                    <span className="truncate">{b.name}</span>
                    {b.is_default && (
                      <span className="ml-auto shrink-0 rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                        default
                      </span>
                    )}
                  </button>
                );
              })
            )}
          </div>
          {selected.length > 0 && (
            <div className="border-t border-border px-3 py-2">
              <button
                onClick={() => onChange([])}
                className="text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                Clear selection ({selected.length})
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
