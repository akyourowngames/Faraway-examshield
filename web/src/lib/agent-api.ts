import type {
  Agent,
  AgentDetail,
  AgentStats,
  AgentConversation,
  AgentTestResult,
  LLMProviderInfo,
  KnowledgeSource,
  LLMConfig,
  TelegramConfig,
} from "@/lib/agent-types";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data?.error || `Request failed (${res.status})`);
  }
  return data as T;
}

// ── Agents ──

export async function listAgents(status?: string): Promise<{ agents: Agent[]; total: number }> {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return apiFetch(`/agents${query}`);
}

export async function getAgent(agentId: string): Promise<AgentDetail> {
  return apiFetch(`/agents/${agentId}`);
}

export async function createAgent(data: {
  name: string;
  description: string;
  category: string;
  visibility: string;
  model: string;
  systemPrompt: string;
  responseStyle: string;
  citationMode: boolean;
  tags: string[];
}): Promise<{ agent: Agent }> {
  return apiFetch("/agents", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateAgent(
  agentId: string,
  data: Partial<Agent>
): Promise<{ agent: Agent }> {
  return apiFetch(`/agents/${agentId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteAgent(agentId: string): Promise<void> {
  await apiFetch(`/agents/${agentId}`, { method: "DELETE" });
}

// ── LLM Config ──

export async function listLLMProviders(): Promise<{ providers: LLMProviderInfo[] }> {
  return apiFetch("/llm/providers");
}

export async function validateLLMKey(data: {
  provider: string;
  apiKey: string;
  model: string;
  endpointUrl?: string;
}): Promise<{ valid: boolean; error?: string; model?: string; provider?: string }> {
  return apiFetch("/llm/validate", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function upsertLLMConfig(
  agentId: string,
  data: LLMConfig
): Promise<{ config: LLMConfig }> {
  return apiFetch(`/agents/${agentId}/llm`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ── Telegram Config ──

export async function upsertTelegramConfig(
  agentId: string,
  data: TelegramConfig
): Promise<{ config: TelegramConfig }> {
  return apiFetch(`/agents/${agentId}/telegram`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ── Knowledge Sources ──

export async function listKnowledgeSources(
  agentId: string
): Promise<{ sources: KnowledgeSource[]; total: number }> {
  return apiFetch(`/agents/${agentId}/knowledge`);
}

export async function createKnowledgeSource(
  agentId: string,
  data: { name: string; sourceType: string; fileCount: number }
): Promise<{ source: KnowledgeSource }> {
  return apiFetch(`/agents/${agentId}/knowledge`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function uploadKnowledgeFiles(
  agentId: string,
  sourceId: string,
  files: File[]
): Promise<{ status: string; chunksStored?: number; totalChars?: number; error?: string }> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }

  const res = await fetch(`/api/agents/${agentId}/knowledge/${sourceId}/upload`, {
    method: "POST",
    body: formData,
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data?.error || "Upload failed");
  }
  return data;
}

// ── Agent Test ──

export async function testAgent(
  agentId: string,
  question: string
): Promise<AgentTestResult> {
  return apiFetch(`/agents/${agentId}/test`, {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}

// ── Conversations & Stats ──

export async function listConversations(
  agentId: string
): Promise<{ conversations: AgentConversation[]; total: number }> {
  return apiFetch(`/agents/${agentId}/conversations`);
}

export async function getAgentStats(agentId: string): Promise<AgentStats> {
  return apiFetch(`/agents/${agentId}/stats`);
}
