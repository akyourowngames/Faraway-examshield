"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  Search,
  TrendingUp,
  Star,
  Clock,
  Sparkles,
  MessageSquare,
  BookOpen,
  ChevronRight,
  Filter,
} from "lucide-react";
import { MOCK_AGENTS, CATEGORY_META } from "@/lib/agent-mock-data";
import type { Agent, AgentCategory } from "@/lib/agent-types";

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.06 } },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { type: "spring" as const, stiffness: 300, damping: 24 } },
};

const CATEGORY_COLORS: Record<AgentCategory, string> = {
  security: "bg-white/10 text-white/70",
  forensics: "bg-white/10 text-white/70",
  compliance: "bg-white/10 text-white/70",
  investigation: "bg-white/10 text-white/70",
  monitoring: "bg-white/10 text-white/70",
  general: "bg-white/10 text-white/70",
};

function AgentCard({ agent }: { agent: Agent }) {
  return (
    <motion.div
      variants={itemVariants}
      className="group relative"
    >
      <Link href={`/dashboard/community-agents/my-agents?selected=${agent.id}`}>
        <div className="relative border border-white/10 bg-white/[0.02] p-5 transition-all duration-300 hover:border-white/25 hover:bg-white/[0.04] overflow-hidden">
          {/* Ambient glow on hover */}
          <div
            className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
            style={{
              background: "radial-gradient(ellipse at 50% 0%, rgba(255,255,255,0.04) 0%, transparent 70%)",
            }}
          />

          {/* Featured badge */}
          {agent.isFeatured && (
            <div className="absolute top-0 right-0 px-2 py-0.5 bg-white text-black text-[9px] font-bold uppercase tracking-widest">
              <Sparkles className="w-2.5 h-2.5 inline mr-0.5 -mt-0.5" />
              Featured
            </div>
          )}

          {/* Header */}
          <div className="flex items-start gap-3 mb-4 relative z-10">
            <div className="w-10 h-10 bg-white/10 border border-white/10 flex items-center justify-center shrink-0 group-hover:border-white/25 transition-colors">
              <span className="text-xs font-bold font-heading text-white">{agent.avatar}</span>
            </div>
            <div className="min-w-0 flex-1">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider truncate group-hover:text-white transition-colors">
                {agent.name}
              </h3>
              <p className="text-[10px] text-white/40 uppercase tracking-widest mt-0.5">
                by {agent.author}
              </p>
            </div>
          </div>

          {/* Description */}
          <p className="text-xs text-white/50 leading-relaxed mb-4 line-clamp-2 relative z-10">
            {agent.description}
          </p>

          {/* Tags */}
          <div className="flex flex-wrap gap-1.5 mb-4 relative z-10">
            <span className={`text-[9px] uppercase tracking-widest px-2 py-0.5 ${CATEGORY_COLORS[agent.category]}`}>
              {agent.category}
            </span>
            {agent.tags.slice(0, 2).map((tag) => (
              <span key={tag} className="text-[9px] uppercase tracking-widest px-2 py-0.5 bg-white/5 text-white/40">
                {tag}
              </span>
            ))}
          </div>

          {/* Metrics */}
          <div className="flex items-center gap-4 pt-3 border-t border-white/5 relative z-10">
            <div className="flex items-center gap-1.5">
              <Star className="w-3 h-3 text-white/30" />
              <span className="text-[10px] text-white/50 font-mono">
                {agent.rating > 0 ? agent.rating.toFixed(1) : "—"}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <MessageSquare className="w-3 h-3 text-white/30" />
              <span className="text-[10px] text-white/50 font-mono">{agent.conversationCount}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <BookOpen className="w-3 h-3 text-white/30" />
              <span className="text-[10px] text-white/50 font-mono">{agent.knowledgeCount}</span>
            </div>
            <div className="ml-auto flex items-center gap-1 text-white/20 group-hover:text-white/50 transition-colors">
              <span className="text-[9px] uppercase tracking-widest">View</span>
              <ChevronRight className="w-3 h-3" />
            </div>
          </div>
        </div>
      </Link>
    </motion.div>
  );
}

export default function DiscoverPage() {
  const [search, setSearch] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<"featured" | "trending" | "recent" | "rating">("featured");

  const filtered = useMemo(() => {
    let agents = [...MOCK_AGENTS];

    if (search) {
      const q = search.toLowerCase();
      agents = agents.filter(
        (a) =>
          a.name.toLowerCase().includes(q) ||
          a.description.toLowerCase().includes(q) ||
          a.tags.some((t) => t.includes(q))
      );
    }

    if (selectedCategory) {
      agents = agents.filter((a) => a.category === selectedCategory);
    }

    switch (sortBy) {
      case "featured":
        agents.sort((a, b) => (b.isFeatured ? 1 : 0) - (a.isFeatured ? 1 : 0));
        break;
      case "trending":
        agents.sort((a, b) => b.conversationCount - a.conversationCount);
        break;
      case "recent":
        agents.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
        break;
      case "rating":
        agents.sort((a, b) => b.rating - a.rating);
        break;
    }

    return agents;
  }, [search, selectedCategory, sortBy]);

  const featured = filtered.filter((a) => a.isFeatured);
  const trending = filtered.filter((a) => a.isTrending);
  const recent = filtered.filter((a) => !a.isFeatured && !a.isTrending);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-end justify-between border-b border-white/10 pb-6">
        <div>
          <h1 className="text-4xl font-heading font-bold tracking-widest text-white uppercase">
            Agent Marketplace
          </h1>
          <p className="text-white/50 text-xs font-mono uppercase tracking-widest mt-2">
            Discover and deploy AI agents for examination security.
          </p>
        </div>
        <Link href="/dashboard/community-agents/create">
          <div className="flex items-center gap-2 px-4 py-2 bg-white text-black text-xs font-bold uppercase tracking-widest hover:bg-white/90 transition-colors cursor-pointer">
            <Sparkles className="w-3.5 h-3.5" />
            Create Agent
          </div>
        </Link>
      </div>

      {/* Search + Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
          <input
            type="text"
            placeholder="Search agents..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-white/[0.03] border border-white/10 text-white text-xs placeholder:text-white/30 focus:outline-none focus:border-white/30 transition-colors"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="w-3.5 h-3.5 text-white/30" />
          {(["featured", "trending", "recent", "rating"] as const).map((s) => (
            <button
              key={s}
              onClick={() => setSortBy(s)}
              className={`px-3 py-2 text-[10px] font-bold uppercase tracking-widest border transition-colors ${
                sortBy === s
                  ? "border-white/30 bg-white/10 text-white"
                  : "border-transparent text-white/40 hover:text-white/60"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Categories */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setSelectedCategory(null)}
          className={`px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest border transition-colors ${
            !selectedCategory
              ? "border-white/30 bg-white/10 text-white"
              : "border-white/10 text-white/40 hover:text-white/60 hover:border-white/20"
          }`}
        >
          All ({MOCK_AGENTS.length})
        </button>
        {Object.entries(CATEGORY_META).map(([key, meta]) => (
          <button
            key={key}
            onClick={() => setSelectedCategory(selectedCategory === key ? null : key)}
            className={`px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest border transition-colors ${
              selectedCategory === key
                ? "border-white/30 bg-white/10 text-white"
                : "border-white/10 text-white/40 hover:text-white/60 hover:border-white/20"
            }`}
          >
            {meta.label} ({meta.count})
          </button>
        ))}
      </div>

      {/* Featured Agents */}
      {featured.length > 0 && (
        <section>
          <div className="flex items-center gap-3 mb-4">
            <Star className="w-4 h-4 text-white/50" />
            <h2 className="text-xs font-semibold uppercase tracking-[0.15em] text-white/50">Featured Agents</h2>
          </div>
          <motion.div
            variants={containerVariants}
            initial="hidden"
            animate="show"
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
          >
              {featured.map((agent) => (
                <AgentCard key={agent.id} agent={agent} />
              ))}
          </motion.div>
        </section>
      )}

      {/* Trending Agents */}
      {trending.length > 0 && (
        <section>
          <div className="flex items-center gap-3 mb-4">
            <TrendingUp className="w-4 h-4 text-white/50" />
            <h2 className="text-xs font-semibold uppercase tracking-[0.15em] text-white/50">Trending Now</h2>
          </div>
          <motion.div
            variants={containerVariants}
            initial="hidden"
            animate="show"
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
          >
              {trending.map((agent) => (
                <AgentCard key={agent.id} agent={agent} />
              ))}
          </motion.div>
        </section>
      )}

      {/* Recent Agents */}
      {recent.length > 0 && (
        <section>
          <div className="flex items-center gap-3 mb-4">
            <Clock className="w-4 h-4 text-white/50" />
            <h2 className="text-xs font-semibold uppercase tracking-[0.15em] text-white/50">Recent Additions</h2>
          </div>
          <motion.div
            variants={containerVariants}
            initial="hidden"
            animate="show"
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
          >
              {recent.map((agent) => (
                <AgentCard key={agent.id} agent={agent} />
              ))}
          </motion.div>
        </section>
      )}

      {/* Empty state */}
      {filtered.length === 0 && (
        <div className="border border-dashed border-white/10 bg-white/[0.02] flex flex-col items-center justify-center text-center py-20">
          <Search className="w-8 h-8 text-white/25 mb-4" />
          <div className="text-xl font-heading uppercase tracking-widest text-white">No Agents Found</div>
          <p className="text-sm text-white/45 mt-3 max-w-sm">
            Try adjusting your search or filters to find what you&apos;re looking for.
          </p>
        </div>
      )}
    </div>
  );
}
