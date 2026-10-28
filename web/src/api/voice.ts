import type { VoiceAction, VoiceInterpretation, VoiceResult } from "../types/api";
import { api } from "./client";

export const voiceApi = {
  /** Whether to show the mic button (the server needs a Claude API key). */
  config: () => api<{ enabled: boolean }>("/voice/config"),
  /** What they said → cards to confirm. Changes nothing. */
  interpret: (householdId: string, text: string, tab?: string, followUp?: { question: string; answer: string }) =>
    api<VoiceInterpretation>(`/households/${householdId}/voice/interpret`, {
      method: "POST",
      body: { text, tab, follow_up: followUp ?? null },
    }),
  /** Runs confirmed actions, or the undos a previous run returned. */
  execute: (householdId: string, actions: VoiceAction[]) =>
    api<{ results: VoiceResult[] }>(`/households/${householdId}/voice/execute`, { method: "POST", body: { actions } }).then(
      (r) => r.results,
    ),
};
