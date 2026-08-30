import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, Clock, Layers, RefreshCw, TrendingUp } from "lucide-react";
import type { Summary } from "../types/deal";

interface SummaryBarProps {
  summary: Summary | null;
  onSync: () => void;
  syncing: boolean;
}

const TONE_CLASSES: Record<string, string> = {
  neutral: "text-[var(--color-text)]",
  risk: "text-[var(--color-risk)]",
  stalling: "text-[var(--color-stalling)]",
  on_track: "text-[var(--color-on-track)]",
};

function formatSyncedAt(value: string | null): string {
  if (!value) return "Never synced";
  const date = new Date(value);
  return `Synced ${date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  })}`;
}

export default function SummaryBar({ summary, onSync, syncing }: SummaryBarProps) {
  const stats = [
    { label: "Total Deals", value: summary?.total_deals ?? 0, icon: Layers, tone: "neutral" },
    { label: "At Risk", value: summary?.at_risk ?? 0, icon: AlertTriangle, tone: "risk" },
    { label: "Stalling", value: summary?.stalling ?? 0, icon: Clock, tone: "stalling" },
    { label: "On Track", value: summary?.on_track ?? 0, icon: TrendingUp, tone: "on_track" },
  ];

  return (
    <div className="flex flex-col gap-4 border-b border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-8">
      <div className="grid grid-cols-2 gap-4 sm:flex sm:flex-wrap sm:items-center sm:gap-8">
        {stats.map(({ label, value, icon: Icon, tone }) => (
          <div key={label} className="flex items-center gap-3">
            <Icon className={`h-5 w-5 ${TONE_CLASSES[tone]}`} strokeWidth={2} />
            <div className="overflow-hidden">
              <AnimatePresence mode="popLayout" initial={false}>
                <motion.p
                  key={value}
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 10 }}
                  transition={{ duration: 0.2 }}
                  className={`text-2xl font-semibold leading-none tabular-nums ${TONE_CLASSES[tone]}`}
                >
                  {value}
                </motion.p>
              </AnimatePresence>
              <p className="mt-1 text-xs uppercase tracking-wide text-[var(--color-text-muted)]">{label}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-4">
        <span className="hidden text-xs text-[var(--color-text-muted)] sm:inline">
          {formatSyncedAt(summary?.last_synced_at ?? null)}
        </span>
        <button
          type="button"
          onClick={onSync}
          disabled={syncing}
          className="flex items-center gap-2 rounded-lg bg-[var(--color-accent)] px-4 py-2 text-sm font-medium text-white transition-all hover:opacity-90 hover:shadow-lg hover:shadow-[var(--color-accent)]/20 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${syncing ? "animate-spin" : ""}`} />
          {syncing ? "Syncing..." : "Sync from HubSpot"}
        </button>
      </div>
    </div>
  );
}
