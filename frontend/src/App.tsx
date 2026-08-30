import { useCallback, useEffect, useMemo, useState } from "react";
import DealDetailModal from "./components/DealDetailModal";
import FilterBar, { type SignalFilter } from "./components/FilterBar";
import PipelineBoard from "./components/PipelineBoard";
import SummaryBar from "./components/SummaryBar";
import { fetchDeals, fetchStages, fetchSummary, triggerSync } from "./lib/api";
import type { Deal, Stage, Summary } from "./types/deal";

export default function App() {
  const [deals, setDeals] = useState<Deal[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [stages, setStages] = useState<Stage[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [signalFilter, setSignalFilter] = useState<SignalFilter>("all");
  const [selectedDeal, setSelectedDeal] = useState<Deal | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [dealsData, summaryData, stagesData] = await Promise.all([fetchDeals(), fetchSummary(), fetchStages()]);
      setDeals(dealsData);
      setSummary(summaryData);
      setStages(stagesData);
      setError(null);
    } catch {
      setError("Couldn't reach the backend. Is it running on the expected port?");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function handleSync() {
    setSyncing(true);
    try {
      await triggerSync();
      await loadData();
    } catch {
      setError("Sync failed. Check the backend logs for details.");
    } finally {
      setSyncing(false);
    }
  }

  const filteredDeals = useMemo(() => {
    const query = search.trim().toLowerCase();
    return deals.filter((deal) => {
      const matchesSearch = !query || deal.deal_name.toLowerCase().includes(query);
      const matchesSignal = signalFilter === "all" || deal.signal === signalFilter;
      return matchesSearch && matchesSignal;
    });
  }, [deals, search, signalFilter]);

  return (
    <div className="flex h-screen flex-col bg-[var(--color-bg)]">
      <header className="border-b border-[var(--color-border)] px-4 py-5 sm:px-8">
        <h1 className="text-lg font-semibold text-[var(--color-text)]">Sales Signal Intelligence</h1>
        <p className="text-sm text-[var(--color-text-muted)]">Pipeline health, powered by deal history + AI</p>
      </header>

      <SummaryBar summary={summary} onSync={handleSync} syncing={syncing} />

      {deals.length > 0 && (
        <FilterBar
          search={search}
          onSearchChange={setSearch}
          signalFilter={signalFilter}
          onSignalFilterChange={setSignalFilter}
          resultCount={filteredDeals.length}
        />
      )}

      {error && (
        <div className="mx-4 mt-4 rounded-lg border border-[var(--color-risk)]/30 bg-[var(--color-risk-soft)] px-4 py-3 text-sm text-[var(--color-risk)] sm:mx-8">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex flex-1 items-center justify-center text-sm text-[var(--color-text-muted)]">
          Loading pipeline...
        </div>
      ) : deals.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 text-center text-[var(--color-text-muted)]">
          <p className="text-sm">No deals yet.</p>
          <p className="text-xs">
            Run <code className="rounded bg-[var(--color-surface-raised)] px-1.5 py-0.5">python seed.py</code>, then hit
            Sync.
          </p>
        </div>
      ) : (
        <PipelineBoard stages={stages} deals={filteredDeals} onCardClick={setSelectedDeal} />
      )}

      <DealDetailModal deal={selectedDeal} onClose={() => setSelectedDeal(null)} />
    </div>
  );
}
