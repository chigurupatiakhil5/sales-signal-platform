export type Signal = "at_risk" | "stalling" | "on_track";

export interface Deal {
  id: string;
  deal_name: string;
  stage: string;
  stage_label: string;
  amount: number | null;
  days_in_stage: number;
  days_since_contact: number | null;
  signal: Signal | null;
  reason: string | null;
}

export interface Summary {
  total_deals: number;
  at_risk: number;
  stalling: number;
  on_track: number;
  unclassified: number;
  last_synced_at: string | null;
}

export interface Stage {
  id: string;
  label: string;
}

export interface SyncResult {
  synced_deals: number;
  created: number;
  updated: number;
  signals_generated: number;
  synced_at: string;
}
