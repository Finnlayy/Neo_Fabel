import { apiRequest } from "./client";
import type { NeuralInferenceState } from "../services/neuralOptimization";

export type OnnxStatus = {
  configured: boolean;
  runtime_available: boolean;
  netron_available: boolean;
  models_dir: string;
  model_count: number;
  active_model_id?: string | null;
  feature_set?: string;
};

export type OnnxModelMeta = {
  id: string;
  filename?: string;
  target?: string;
  target_formula?: string;
  test_mae?: number;
  trained_at?: string;
  created?: string;
  version?: string;
  checksum?: string;
  feature_set?: string;
  symbol?: string;
  timeframe?: string;
  source?: string;
  samples?: number;
  input_name?: string;
  input_shape?: number[];
  architecture?: string;
  file_mtime?: number;
  file_size?: number;
};

export type OnnxModelsResponse = {
  models: OnnxModelMeta[];
  active_model_id?: string | null;
};

export type OnnxGraphSummary = {
  id: string;
  ops: string[];
  op_counts: Record<string, number>;
  initializers: Array<{
    name: string;
    shape: number[];
    dtype: string;
    mean: number;
    std: number;
    l2: number;
    sha256_16: string;
  }>;
  weight_fingerprint: string;
  node_count: number;
  architecture_hint?: string;
};

export type OnnxInferResponse = NeuralInferenceState & {
  provider?: string;
  model_id?: string;
};

export type OnnxTrainResponse = {
  job_id: string;
  status: string;
  model_id?: string;
  test_mae?: number;
  checksum?: string;
  version?: string;
  message?: string;
};

export async function fetchOnnxStatus(): Promise<OnnxStatus> {
  return apiRequest<OnnxStatus>("/api/v1/onnx/status");
}

export async function fetchOnnxModels(): Promise<OnnxModelsResponse> {
  return apiRequest<OnnxModelsResponse>("/api/v1/onnx/models");
}

export async function fetchOnnxGraph(modelId: string): Promise<OnnxGraphSummary> {
  return apiRequest<OnnxGraphSummary>(`/api/v1/onnx/models/${encodeURIComponent(modelId)}/graph`);
}

export async function setOnnxActive(modelId: string): Promise<{ active_model_id: string; meta?: OnnxModelMeta }> {
  return apiRequest("/api/v1/onnx/models/active", {
    method: "POST",
    body: JSON.stringify({ model_id: modelId }),
  });
}

export async function uploadOnnxModel(opts: {
  file: File;
  modelId?: string;
  makeActive?: boolean;
}): Promise<{ status: string; meta: OnnxModelMeta; active_model_id?: string }> {
  const form = new FormData();
  form.append("file", opts.file);
  if (opts.modelId) form.append("model_id", opts.modelId);
  form.append("make_active", opts.makeActive ? "true" : "false");
  // Do not set Content-Type — browser sets multipart boundary
  return apiRequest("/api/v1/onnx/models/upload", {
    method: "POST",
    body: form,
    headers: { Accept: "application/json" },
  });
}

export async function inferOnnx(body: {
  model_id?: string;
  symbol: string;
  timeframe?: string;
  asset_class?: string;
  allow_fallback?: boolean;
}): Promise<OnnxInferResponse> {
  return apiRequest<OnnxInferResponse>("/api/v1/onnx/infer", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function startOnnxTrain(body: {
  model_id: string;
  symbol: string;
  timeframe?: string;
  asset_class?: string;
  limit?: number;
  seed?: number;
}): Promise<OnnxTrainResponse> {
  return apiRequest<OnnxTrainResponse>("/api/v1/onnx/train", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function fetchOnnxTrainJob(jobId: string): Promise<OnnxTrainResponse> {
  return apiRequest<OnnxTrainResponse>(`/api/v1/onnx/train/${encodeURIComponent(jobId)}`);
}

/** Same-origin Netron embed; model served from /static/onnx (no Bearer) for iframe fetch. */
export function netronEmbedUrl(modelId: string, cacheBust?: string | number): string {
  const id = modelId.replace(/\.onnx$/i, "");
  const bust = cacheBust != null && String(cacheBust) !== "" ? `?v=${encodeURIComponent(String(cacheBust))}` : "";
  const filePath = `/static/onnx/${encodeURIComponent(id)}.onnx${bust}`;
  const absolute =
    typeof window !== "undefined" ? `${window.location.origin}${filePath}` : filePath;
  return `/static/netron/index.html?url=${encodeURIComponent(absolute)}`;
}
