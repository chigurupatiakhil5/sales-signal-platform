import { AnimatePresence } from "framer-motion";
import type { Deal, Stage } from "../types/deal";
import DealCard from "./DealCard";

interface PipelineBoardProps {
  stages: Stage[];
  deals: Deal[];
  onCardClick: (deal: Deal) => void;
}

const compactCurrency = new Intl.NumberFormat("en-US", {
  notation: "compact",
  style: "currency",
  currency: "USD",
});

export default function PipelineBoard({ stages, deals, onCardClick }: PipelineBoardProps) {
  const dealsByStage = new Map<string, Deal[]>();
  for (const stage of stages) dealsByStage.set(stage.id, []);
  for (const deal of deals) {
    if (!dealsByStage.has(deal.stage)) dealsByStage.set(deal.stage, []);
    dealsByStage.get(deal.stage)!.push(deal);
  }

  return (
    <div className="flex flex-1 snap-x snap-mandatory gap-4 overflow-x-auto px-4 py-6 sm:px-8">
      {stages.map((stage) => {
        const stageDeals = dealsByStage.get(stage.id) ?? [];
        const stageTotal = stageDeals.reduce((sum, deal) => sum + (deal.amount ?? 0), 0);

        return (
          <div
            key={stage.id}
            className="flex w-[85vw] shrink-0 snap-start flex-col rounded-xl bg-[var(--color-surface)] sm:w-80"
          >
            <div className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-3">
              <div>
                <p className="text-sm font-semibold text-[var(--color-text)]">{stage.label}</p>
                <p className="text-xs text-[var(--color-text-muted)]">
                  {stageDeals.length} deal{stageDeals.length === 1 ? "" : "s"}
                </p>
              </div>
              <span className="rounded-full bg-[var(--color-surface-raised)] px-2 py-1 text-xs tabular-nums text-[var(--color-text-muted)]">
                {compactCurrency.format(stageTotal)}
              </span>
            </div>

            <div className="flex flex-1 flex-col gap-3 overflow-y-auto p-3">
              <AnimatePresence initial={false}>
                {stageDeals.length === 0 ? (
                  <p className="mt-6 text-center text-xs text-[var(--color-text-muted)]">No deals in this stage</p>
                ) : (
                  stageDeals.map((deal) => <DealCard key={deal.id} deal={deal} onClick={() => onCardClick(deal)} />)
                )}
              </AnimatePresence>
            </div>
          </div>
        );
      })}
    </div>
  );
}
