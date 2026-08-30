import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, Clock, MessageCircleOff, TrendingUp, X } from "lucide-react";
import { useEffect } from "react";
import type { Deal } from "../types/deal";

const SIGNAL_META = {
  at_risk: { label: "At Risk", icon: AlertTriangle, color: "var(--color-risk)", bg: "var(--color-risk-soft)" },
  stalling: { label: "Stalling", icon: Clock, color: "var(--color-stalling)", bg: "var(--color-stalling-soft)" },
  on_track: { label: "On Track", icon: TrendingUp, color: "var(--color-on-track)", bg: "var(--color-on-track-soft)" },
} as const;

function formatAmount(amount: number | null): string {
  if (amount === null) return "Unknown";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(amount);
}

export default function DealDetailModal({ deal, onClose }: { deal: Deal | null; onClose: () => void }) {
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  const meta = deal?.signal ? SIGNAL_META[deal.signal] : null;
  const Icon = meta?.icon ?? MessageCircleOff;

  return (
    <AnimatePresence>
      {deal && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            className="w-full max-w-md rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-6 shadow-2xl"
            initial={{ opacity: 0, scale: 0.95, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 12 }}
            transition={{ type: "spring", stiffness: 300, damping: 28 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3">
              <h2 className="text-lg font-semibold leading-snug text-[var(--color-text)]">{deal.deal_name}</h2>
              <button
                type="button"
                onClick={onClose}
                className="shrink-0 rounded-full p-1 text-[var(--color-text-muted)] hover:bg-[var(--color-border)] hover:text-[var(--color-text)]"
                aria-label="Close"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {meta && (
              <span
                className="mt-3 inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold"
                style={{ color: meta.color, backgroundColor: meta.bg }}
              >
                <Icon className="h-3.5 w-3.5" />
                {meta.label}
              </span>
            )}

            <dl className="mt-5 grid grid-cols-2 gap-4">
              <div>
                <dt className="text-xs uppercase tracking-wide text-[var(--color-text-muted)]">Amount</dt>
                <dd className="mt-1 text-lg font-semibold tabular-nums text-[var(--color-text)]">{formatAmount(deal.amount)}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-[var(--color-text-muted)]">Stage</dt>
                <dd className="mt-1 text-sm text-[var(--color-text)]">{deal.stage_label}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-[var(--color-text-muted)]">Days in stage</dt>
                <dd className="mt-1 text-sm tabular-nums text-[var(--color-text)]">{deal.days_in_stage}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-[var(--color-text-muted)]">Last contact</dt>
                <dd className="mt-1 text-sm tabular-nums text-[var(--color-text)]">
                  {deal.days_since_contact !== null ? `${deal.days_since_contact}d ago` : "None logged"}
                </dd>
              </div>
            </dl>

            {deal.reason && (
              <div className="mt-5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
                <p className="text-xs uppercase tracking-wide text-[var(--color-text-muted)]">AI Signal Reason</p>
                <p className="mt-2 text-sm leading-relaxed text-[var(--color-text)]">{deal.reason}</p>
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
