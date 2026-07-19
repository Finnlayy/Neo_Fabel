/**
 * Phase 1 Qdrant vector API client (proxied via Vite /api → FastAPI).
 */

import {apiRequest} from "./client";

export type VectorBackendMode = "qdrant" | "memory";

export interface VectorHealthResponse {
  status: string;
  enabled: boolean;
  ready: boolean;
  url?: string;
  collection?: string;
  collection_exists?: boolean;
  vector_size?: number;
  backend?: string;
  feature?: string;
  error?: string;
}

export interface VectorPointPayload {
  id: string;
  vector: number[];
  title?: string;
  category?: string;
  metadata?: Record<string, unknown>;
}

export interface VectorSearchHit {
  id: string;
  score: number;
  title?: string | null;
  category?: string | null;
  metadata?: Record<string, unknown>;
  payload?: Record<string, unknown>;
}

export interface VectorSearchResponse {
  success: boolean;
  collection: string;
  metric: string;
  top_k: number;
  count: number;
  results: VectorSearchHit[];
}

export interface VectorListResponse {
  success: boolean;
  collection: string;
  count: number;
  points: Array<{
    id: string;
    title?: string | null;
    category?: string | null;
    vector: number[];
    metadata?: Record<string, unknown>;
  }>;
}

export async function fetchVectorHealth(): Promise<VectorHealthResponse> {
  return apiRequest<VectorHealthResponse>("/api/v1/vector/health");
}

export async function ensureVectorCollection(): Promise<{success: boolean; created?: boolean}> {
  return apiRequest("/api/v1/vector/collections/ensure", {method: "POST"});
}

export async function upsertVectorPoints(
  points: VectorPointPayload[],
): Promise<{success: boolean; upserted: number; ids: string[]}> {
  return apiRequest("/api/v1/vector/points", {
    method: "POST",
    body: JSON.stringify({points}),
  });
}

export async function searchVectors(
  vector: number[],
  topK = 4,
): Promise<VectorSearchResponse> {
  return apiRequest("/api/v1/vector/search", {
    method: "POST",
    body: JSON.stringify({vector, top_k: topK, metric: "cosine"}),
  });
}

export async function listVectorPoints(limit = 100): Promise<VectorListResponse> {
  return apiRequest(`/api/v1/vector/points?limit=${limit}`);
}

export async function deleteVectorPoint(id: string): Promise<{success: boolean}> {
  return apiRequest(`/api/v1/vector/points/${encodeURIComponent(id)}`, {method: "DELETE"});
}

/** Probe Qdrant; never pretends live when the probe fails. */
export async function probeVectorBackend(): Promise<{
  mode: VectorBackendMode;
  label: string;
  health: VectorHealthResponse | null;
}> {
  try {
    const health = await fetchVectorHealth();
    if (health.ready && health.enabled) {
      return {mode: "qdrant", label: "QDRANT LIVE", health};
    }
    if (!health.enabled) {
      return {mode: "memory", label: "RAM FALLBACK (QDRANT DISABLED)", health};
    }
    return {mode: "memory", label: "RAM FALLBACK (QDRANT DOWN)", health};
  } catch {
    return {mode: "memory", label: "RAM FALLBACK (QDRANT DOWN)", health: null};
  }
}
