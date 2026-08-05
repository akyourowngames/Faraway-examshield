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
  | "openai"
  | "anthropic"
  | "grok"
  | "groq"
  | "opencode";

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
  groupedModels?: Record<string, string[]> | null;
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
  botToken?: string;
  botTokenSet?: boolean;
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

// ── Question Registry ──

export type PaperType = "question-paper" | "answer-key" | "internal-draft";

export type PaperStatus = "registered" | "received" | "in_transit" | "investigating" | "compromised";

export type RiskLevel = "low" | "medium" | "high" | "critical";

export type FingerprintStatus = "pending" | "processing" | "ready" | "failed";

export type RegistryPaper = {
  paperId: string;
  exam: string;
  year: number;
  paperSet: string;
  paperType: PaperType;
  description: string;
  watermarkId: string;
  questionFingerprint: string;
  centerCode: string;
  centerName: string;
  city: string;
  state: string;
  printBatch: string;
  printerId: string;
  printedAt: string;
  distributedAt: string;
  riskLevel: RiskLevel;
  status: PaperStatus;
  uploadedAt: string;
  fingerprintStatus: FingerprintStatus;
  ocrConfidence: number;
  totalQuestions: number;
  protected: boolean;
  fileType: string;
  originalFilename: string;
};

export type RegistryStats = {
  totalPapers: number;
  protectedPapers: number;
  compromisedPapers: number;
  investigatingPapers: number;
  byExam: Record<string, number>;
};

export type MatchResult = {
  matchedPaperId: string;
  matchedExam: string;
  matchedSet: string;
  similarityScore: number;
  confidence: "high" | "medium" | "low";
  status: "likely-leak" | "possible-match" | "weak-match";
  centerCode: string;
  centerName: string;
  city: string;
  state: string;
  riskLevel: string;
  matchedWatermarkId: string;
};
