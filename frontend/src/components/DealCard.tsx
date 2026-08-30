import { motion } from "framer-motion";
import { AlertTriangle, Clock, MessageCircleOff, TrendingUp } from "lucide-react";
import type { Deal } from "../types/deal";

const SIGNAL_META = {
  at_risk: { label: "At Risk", icon: AlertTriangle, color: "var(--color-risk)", bg: "var(--color-risk-soft)" },
  stalling: { label: "Stalling", icon: Clock, color: "var(--color-stalling)", bg: "var(--color-stalling-soft)" },
  on_track: { label: "On Track", icon: TrendingUp, color: "var(--color-on-track)", bg: "var(--color-on-track-soft)" },
} as const;

function formatAmount(amount: number | null): string {
  if (amount === null) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(amount);
}

export default function DealCard({ deal, onClick }: { deal: Deal; onClick?: () => void }) {
  const meta = deal.signal ? SIGNAL_META[deal.signal] : null;
  const Icon = meta?.icon ?? MessageCircleOff;

  return (
    <motion.button
      type="button"
      onClick={onClick}
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      whileHover={{ y: -3 }}
      whileTap={{ scale: 0.98 }}
      transition={{ duration: 0.18 }}
      className="flex w-full flex-col gap-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-4 text-left transition-colors hover:border-[var(--color-accent)]/50 hover:shadow-lg hover:shadow-black/20"
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium leading-snug text-[var(--color-text)]">{deal.deal_name}</p>
        {meta && (
          <span
            className="flex shrink-0 items-center gap-1 rounded-full px-2 py-1 text-[11px] font-semibold"
            style={{ color: meta.color, backgroundColor: meta.bg }}
          >
            <Icon className="h-3 w-3" />
            {meta.label}
          </span>
        )}
      </div>

      <p className="text-lg font-semibold tabular-nums text-[var(--color-text)]">{formatAmount(deal.amount)}</p>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[var(--color-text-muted)]">
        <span>{deal.days_in_stage}d in stage</span>
        <span className="h-1 w-1 rounded-full bg-[var(--color-border)]" />
        <span>{deal.days_since_contact !== null ? `${deal.days_since_contact}d since contact` : "No contact logged"}</span>
      </div>

      {deal.reason && (
        <p className="line-clamp-2 border-t border-[var(--color-border)] pt-3 text-xs leading-relaxed text-[var(--color-text-muted)]">
          {deal.reason}
        </p>
      )}
    </motion.button>
  );
}
