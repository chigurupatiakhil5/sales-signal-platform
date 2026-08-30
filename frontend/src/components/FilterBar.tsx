import { Search } from "lucide-react";
import type { Signal } from "../types/deal";

export type SignalFilter = Signal | "all";

interface FilterBarProps {
  search: string;
  onSearchChange: (value: string) => void;
  signalFilter: SignalFilter;
  onSignalFilterChange: (value: SignalFilter) => void;
  resultCount: number;
}

const FILTERS: { value: SignalFilter; label: string; activeClass: string }[] = [
  { value: "all", label: "All", activeClass: "bg-[var(--color-accent)] text-white" },
  { value: "at_risk", label: "At Risk", activeClass: "bg-[var(--color-risk)] text-white" },
  { value: "stalling", label: "Stalling", activeClass: "bg-[var(--color-stalling)] text-black" },
  { value: "on_track", label: "On Track", activeClass: "bg-[var(--color-on-track)] text-black" },
];

export default function FilterBar({ search, onSearchChange, signalFilter, onSignalFilterChange, resultCount }: FilterBarProps) {
  return (
    <div className="flex flex-col gap-3 border-b border-[var(--color-border)] bg-[var(--color-surface)]/60 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-8">
      <div className="relative w-full sm:w-72">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-text-muted)]" />
        <input
          type="text"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search deals..."
          className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-raised)] py-2 pl-9 pr-3 text-sm text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:border-[var(--color-accent)] focus:outline-none"
        />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            type="button"
            onClick={() => onSignalFilterChange(f.value)}
            className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
              signalFilter === f.value
                ? f.activeClass
                : "bg-[var(--color-surface-raised)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            }`}
          >
            {f.label}
          </button>
        ))}
        <span className="ml-1 text-xs tabular-nums text-[var(--color-text-muted)]">{resultCount} shown</span>
      </div>
    </div>
  );
}
