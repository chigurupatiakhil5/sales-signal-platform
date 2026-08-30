import axios from "axios";
import type { Deal, Stage, Summary, SyncResult } from "../types/deal";

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8010";

const client = axios.create({ baseURL: API_BASE_URL });

export async function fetchDeals(): Promise<Deal[]> {
  const { data } = await client.get<Deal[]>("/deals");
  return data;
}

export async function fetchSummary(): Promise<Summary> {
  const { data } = await client.get<Summary>("/summary");
  return data;
}

export async function fetchStages(): Promise<Stage[]> {
  const { data } = await client.get<Stage[]>("/stages");
  return data;
}

export async function triggerSync(): Promise<SyncResult> {
  const { data } = await client.post<SyncResult>("/sync");
  return data;
}
