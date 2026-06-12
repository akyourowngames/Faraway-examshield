import type { Agent, KnowledgeSource, AgentConversation } from "@/lib/agent-types";

const HOUR_AGO = new Date(Date.now() - 3600000).toISOString();
const DAY_AGO = new Date(Date.now() - 86400000).toISOString();
const WEEK_AGO = new Date(Date.now() - 604800000).toISOString();

export const MOCK_AGENTS: Agent[] = [
  {
    id: "agt_01", name: "Threat Scanner", description: "Automated threat detection agent that monitors channels for suspicious exam-related activity.",
    category: "security-assistant", visibility: "public", status: "active", avatar: "TS", author: "ExamShield Team",
    model: "gpt-4o", systemPrompt: "", responseStyle: "balanced", citationMode: true,
    tags: ["threat-detection", "real-time"], knowledgeCount: 12, conversationCount: 847,
    rating: 4.8, ratingCount: 124, createdAt: WEEK_AGO, updatedAt: HOUR_AGO,
  },
  {
    id: "agt_02", name: "School Assistant", description: "Helps school staff manage examination security protocols and answer queries.",
    category: "school-assistant", visibility: "public", status: "active", avatar: "SA", author: "ExamShield Team",
    model: "gpt-4o", systemPrompt: "", responseStyle: "balanced", citationMode: true,
    tags: ["school", "assistant"], knowledgeCount: 8, conversationCount: 312,
    rating: 4.6, ratingCount: 89, createdAt: WEEK_AGO, updatedAt: DAY_AGO,
  },
  {
    id: "agt_03", name: "University Guide", description: "Answers university-level queries about exam security and compliance.",
    category: "university-assistant", visibility: "public", status: "active", avatar: "UG", author: "Security Lab",
    model: "gpt-4o", systemPrompt: "", responseStyle: "detailed", citationMode: true,
    tags: ["university", "compliance"], knowledgeCount: 15, conversationCount: 156,
    rating: 4.3, ratingCount: 67, createdAt: DAY_AGO, updatedAt: HOUR_AGO,
  },
  {
    id: "agt_04", name: "Coaching Hub", description: "Assists coaching centers with exam monitoring and student support.",
    category: "coaching-assistant", visibility: "public", status: "active", avatar: "CH", author: "Intel Division",
    model: "gpt-4o-mini", systemPrompt: "", responseStyle: "short", citationMode: false,
    tags: ["coaching", "support"], knowledgeCount: 6, conversationCount: 534,
    rating: 4.7, ratingCount: 201, createdAt: WEEK_AGO, updatedAt: HOUR_AGO,
  },
  {
    id: "agt_05", name: "Education Bot", description: "General education assistant for exam-related queries.",
    category: "education", visibility: "public", status: "paused", avatar: "EB", author: "Ops Team",
    model: "gpt-4o-mini", systemPrompt: "", responseStyle: "balanced", citationMode: true,
    tags: ["education", "general"], knowledgeCount: 4, conversationCount: 89,
    rating: 4.1, ratingCount: 34, createdAt: DAY_AGO, updatedAt: DAY_AGO,
  },
  {
    id: "agt_06", name: "Draft Agent", description: "A work-in-progress agent for testing new detection patterns.",
    category: "general", visibility: "private", status: "draft", avatar: "DA", author: "You",
    model: "gpt-4o-mini", systemPrompt: "", responseStyle: "balanced", citationMode: false,
    tags: ["draft", "experimental"], knowledgeCount: 0, conversationCount: 0,
    rating: 0, ratingCount: 0, createdAt: DAY_AGO, updatedAt: DAY_AGO,
  },
];

export const MOCK_KNOWLEDGE_SOURCES: KnowledgeSource[] = [
  { id: "ks_01", name: "Exam Security Protocols", sourceType: "document", status: "ready", fileCount: 3, chunkCount: 245, totalChars: 120000, createdAt: HOUR_AGO, updatedAt: HOUR_AGO },
  { id: "ks_02", name: "NEET Case Files", sourceType: "document", status: "ready", fileCount: 12, chunkCount: 1823, totalChars: 890000, createdAt: DAY_AGO, updatedAt: DAY_AGO },
  { id: "ks_03", name: "Threat Feed", sourceType: "url", status: "processing", fileCount: 0, chunkCount: 0, totalChars: 0, createdAt: HOUR_AGO, updatedAt: HOUR_AGO },
];

export const MOCK_CONVERSATIONS: AgentConversation[] = [
  { id: "conv_01", agentId: "agt_01", userMessage: "What are the latest threats?", agentResponse: "Analyzed 3 new suspicious messages...", sources: [], latencyMs: 1200, status: "completed", createdAt: HOUR_AGO },
  { id: "conv_02", agentId: "agt_01", userMessage: "Show me alerts for Delhi", agentResponse: "Found 2 critical alerts in Delhi region...", sources: [], latencyMs: 890, status: "completed", createdAt: HOUR_AGO },
];

export const CATEGORY_META: Record<string, { label: string; count: number }> = {
  education: { label: "Education", count: 1 },
  "school-assistant": { label: "School Assistant", count: 1 },
  "university-assistant": { label: "University Assistant", count: 1 },
  "coaching-assistant": { label: "Coaching Assistant", count: 1 },
  "security-assistant": { label: "Security Assistant", count: 1 },
  general: { label: "General", count: 1 },
};
