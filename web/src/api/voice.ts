import type { VoiceAction, VoiceInterpretation, VoiceResult } from "../types/api";
import { api } from "./client";

export type VoiceInput = "voice" | "typed";

export const voiceApi = {
  /** Whether to show the mic button. */
  config: () => api<{ enabled: boolean }>("/voice/config"),
  /** What they said (or typed) → cards to confirm. Changes nothing. */
  interpret: (
    householdId: string,
    text: string,
    input: VoiceInput,
    tab?: string,
    followUp?: { question: string; answer: string },
  ) =>
    api<VoiceInterpretation>(`/households/${householdId}/voice/interpret`, {
      method: "POST",
      body: { text, tab, input, follow_up: followUp ?? null },
    }),
  /** Runs confirmed actions, or (`undo`) the undos a previous run returned. Once per command. */
  execute: (householdId: string, commandId: string, actions: VoiceAction[], undo = false) =>
    api<{ results: VoiceResult[] }>(`/households/${householdId}/voice/execute`, {
      method: "POST",
      body: { actions, command_id: commandId, undo },
    }).then((r) => r.results),
};
