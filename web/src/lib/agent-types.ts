export type AgentStatus = "draft" | "processing" | "deploying" | "active" | "paused" | "failed";

export type AgentCategory =
  | "education"
  | "school-assistant"
  | "university-assistant"
  | "coaching-assistant"
  | "security-assistant"
  | "general";

export type AgentVisibility = "private" | "public";

export type ResponseStyle = "short" | "balanced" | "detailed";

export type LLMProvider =
  | "openrouter"
  | "groq"
  | "google"
  | "openai"
  | "anthropic"
  | "nvidia-nim"
  | "custom";

export type TelegramDeploymentStatus =
  | "disconnected"
  | "connected"
  | "invalid-token"
  | "network-error"
  | "deployed";

export type KnowledgeSourceStatus = "queued" | "processing" | "embedding" | "indexing" | "ready" | "failed";

export type LLMProviderInfo = {
  id: LLMProvider;
  name: string;
  models: string[];
  requiresKey: boolean;
  requiresEndpoint: boolean;
};

export type LLMConfig = {
  provider: LLMProvider;
  model: string;
  apiKey?: string;
  endpointUrl?: string;
  extraHeaders?: Record<string, string>;
};

export type TelegramConfig = {
  botToken: string;
  botUsername: string;
  botVerified: boolean;
  privacyModeDisabled: boolean;
  addedToGroup: boolean;
  promotedAdmin: boolean;
  messageReadingEnabled: boolean;
  webhookUrl: string;
  deploymentStatus: TelegramDeploymentStatus;
};

export type KnowledgeSource = {
  id: string;
  name: string;
  sourceType: "document" | "url" | "api" | "database";
  status: KnowledgeSourceStatus;
  fileCount: number;
  chunkCount: number;
  totalChars: number;
  errorMessage?: string | null;
  createdAt: string;
  updatedAt: string;
};

export type Agent = {
  id: string;
  name: string;
  description: string;
  category: AgentCategory;
  visibility: AgentVisibility;
  status: AgentStatus;
  avatar: string;
  author: string;
  model: string;
  systemPrompt: string;
  responseStyle: ResponseStyle;
  citationMode: boolean;
  tags: string[];
  knowledgeCount: number;
  conversationCount: number;
  rating: number;
  ratingCount: number;
  createdAt: string;
  updatedAt: string;
};

export type AgentDetail = {
  agent: Agent;
  llmConfig: {
    provider: LLMProvider;
    model: string;
  } | null;
  telegramConfig: TelegramConfig | null;
  knowledgeSources: KnowledgeSource[];
  stats: AgentStats;
};

export type AgentStats = {
  totalConversations: number;
  totalKnowledgeSources: number;
  totalChunks: number;
  avgLatencyMs: number;
  status: string;
};

export type AgentConversation = {
  id: string;
  agentId: string;
  userMessage: string;
  agentResponse: string;
  sources: Array<{ content: string; similarity: number }>;
  latencyMs: number;
  status: string;
  createdAt: string;
};

export type AgentTestResult = {
  response: string;
  sources: Array<{ content: string; similarity: number }>;
  latencyMs: number;
  model: string;
  provider: string;
};

export type AgentMetric = {
  label: string;
  value: string | number;
  change: number;
  changeLabel: string;
};
