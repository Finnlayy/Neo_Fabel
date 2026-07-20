import { apiRequest } from "../../api/client";

export type IntegrationItem = {
  key: string;
  label: string;
  group: string;
  secret: boolean;
  configured: boolean;
  masked: string | null;
  source: "vault" | "env" | null;
};

export type IntegrationsResponse = {
  updated_at: string | null;
  store_path: string;
  items: IntegrationItem[];
  password_count: number;
};

export type PasswordItem = {
  id: string;
  label: string;
  username: string | null;
  notes: string | null;
  updated_at: string | null;
  configured: boolean;
  masked: string | null;
};

export function fetchIntegrations(): Promise<IntegrationsResponse> {
  return apiRequest<IntegrationsResponse>("/api/v1/settings/integrations");
}

export function upsertIntegration(key: string, value: string | null): Promise<{ ok: boolean }> {
  return apiRequest(`/api/v1/settings/integrations/${encodeURIComponent(key)}`, {
    method: "PUT",
    body: JSON.stringify({ value }),
  });
}

export function deleteIntegration(key: string): Promise<{ ok: boolean }> {
  return apiRequest(`/api/v1/settings/integrations/${encodeURIComponent(key)}`, {
    method: "DELETE",
  });
}

export function revealIntegration(key: string): Promise<{ key: string; value: string }> {
  return apiRequest(`/api/v1/settings/integrations/${encodeURIComponent(key)}/reveal`);
}

export function fetchPasswords(): Promise<{ items: PasswordItem[] }> {
  return apiRequest("/api/v1/settings/passwords");
}

export function upsertPassword(body: {
  id?: string | null;
  label: string;
  username?: string | null;
  secret?: string | null;
  notes?: string | null;
}): Promise<{ ok: boolean; item: PasswordItem }> {
  return apiRequest("/api/v1/settings/passwords", {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function deletePassword(id: string): Promise<{ ok: boolean }> {
  return apiRequest(`/api/v1/settings/passwords/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

export function revealPassword(id: string): Promise<{
  id: string;
  label: string;
  username: string | null;
  notes: string | null;
  secret: string;
  updated_at: string | null;
}> {
  return apiRequest(`/api/v1/settings/passwords/${encodeURIComponent(id)}/reveal`);
}
