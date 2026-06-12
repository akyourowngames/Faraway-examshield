export type AgentStatus = "active" | "draft" | "paused" | "archived";

export type AgentCategory =
  | "security"
  | "compliance"
  | "investigation"
  | "monitoring"
  | "forensics"
  | "general";

export type KnowledgeSource = {
  id: string;
  name: string;
  type: "document" | "url" | "api" | "database";
  status: "active" | "processing" | "error";
  itemCount: number;
  lastSynced: string;
};

export type Agent = {
  id: string;
  name: string;
  description: string;
  category: AgentCategory;
  status: AgentStatus;
  avatar: string;
  author: string;
  authorAvatar: string;
  knowledgeCount: number;
  conversationCount: number;
  rating: number;
  ratingCount: number;
  isFeatured: boolean;
  isTrending: boolean;
  tags: string[];
  createdAt: string;
  lastActivity: string;
  model: string;
};

export type AgentMetric = {
  label: string;
  value: string | number;
  change: number;
  changeLabel: string;
};

export type AgentConversation = {
  id: string;
  agentId: string;
  agentName: string;
  preview: string;
  messageCount: number;
  createdAt: string;
};
