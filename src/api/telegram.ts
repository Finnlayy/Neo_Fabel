import {apiRequest} from "./client";
import type {TelegramSignal} from "../types";

export type TelegramConfig = {chatId: string; botUsername: string};

export type TelegramDaemonStatus = {
  status: "ACTIVE" | "THROTTLED" | "STOPPED" | string;
  currentIntervalMs: number;
  lastPollTime: string | null;
  lastMessageReceivedTime: string | null;
  nextPollTime: string | null;
  totalPollsCount: number;
  totalMessagesProcessed: number;
  isThrottled: boolean;
  timeSinceLastMessageSec: number | null;
};

export async function fetchTelegramConfig(): Promise<TelegramConfig> {
  return apiRequest<TelegramConfig>("/api/telegram/config");
}

export async function fetchTelegramMessages(): Promise<TelegramSignal[]> {
  return apiRequest<TelegramSignal[]>("/api/telegram/messages");
}

export async function fetchTelegramDaemonStatus(): Promise<TelegramDaemonStatus> {
  return apiRequest<TelegramDaemonStatus>("/api/telegram/daemon-status");
}

export async function sendTelegramMessage(message: string): Promise<{ok: boolean}> {
  return apiRequest<{ok: boolean}>("/api/telegram/send", {
    method: "POST",
    body: JSON.stringify({message}),
  });
}
