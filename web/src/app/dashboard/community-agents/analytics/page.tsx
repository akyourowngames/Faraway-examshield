"use client";

import { motion } from "framer-motion";
import { BarChart3, TrendingUp, MessageSquare, BookOpen, Clock, Users, ArrowUpRight, ArrowDownRight } from "lucide-react";

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { type: "spring" as const, stiffness: 300, damping: 24 } },
};

const METRICS = [
  { label: "Total Conversations", value: "2,847", change: 12.5, up: true, icon: MessageSquare },
  { label: "Active Agents", value: "8", change: 2, up: true, icon: Users },
  { label: "Knowledge Items", value: "12,456", change: 8.3, up: true, icon: BookOpen },
  { label: "Avg Response Time", value: "1.2s", change: -5.1, up: true, icon: Clock },
];

const AGENT_PERFORMANCE = [
  { name: "Threat Scanner", conversations: 847, rating: 4.8, trend: 15 },
  { name: "Chat Intelligence", conversations: 534, rating: 4.7, trend: 22 },
  { name: "Report Generator", conversations: 423, rating: 4.4, trend: -3 },
  { name: "Paper Forensics", conversations: 312, rating: 4.6, trend: 8 },
  { name: "OCR Enhancement", conversations: 267, rating: 4.2, trend: 5 },
];

const WEEKLY_DATA = [
  { day: "Mon", conversations: 145, messages: 1230 },
  { day: "Tue", conversations: 189, messages: 1567 },
  { day: "Wed", conversations: 234, messages: 1890 },
  { day: "Thu", conversations: 198, messages: 1456 },
  { day: "Fri", conversations: 267, messages: 2100 },
  { day: "Sat", conversations: 156, messages: 980 },
  { day: "Sun", conversations: 112, messages: 720 },
];

const MAX_MESSAGES = Math.max(...WEEKLY_DATA.map((d) => d.messages));

export default function AnalyticsPage() {
  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="show"
      className="space-y-8"
    >
      {/* Header */}
      <div className="flex items-end justify-between border-b border-white/10 pb-6">
        <div>
          <h1 className="text-4xl font-heading font-bold tracking-widest text-white uppercase">
            Analytics
          </h1>
          <p className="text-white/50 text-xs font-mono uppercase tracking-widest mt-2">
            Performance metrics across all agents.
          </p>
        </div>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {METRICS.map((metric) => {
          const Icon = metric.icon;
          return (
            <motion.div
              key={metric.label}
              variants={itemVariants}
              className="border border-white/10 bg-white/[0.02] p-5 relative overflow-hidden group hover:border-white/20 transition-colors"
            >
              <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
                style={{ background: "radial-gradient(ellipse at 50% 0%, rgba(255,255,255,0.03) 0%, transparent 70%)" }}
              />
              <div className="flex items-center justify-between mb-4 relative z-10">
                <Icon className="w-4 h-4 text-white/30" />
                <div className={`flex items-center gap-1 text-[10px] font-bold ${metric.up ? "text-emerald-400/80" : "text-red-400/80"}`}>
                  {metric.up ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                  {Math.abs(metric.change)}%
                </div>
              </div>
              <div className="text-3xl font-heading font-bold text-white relative z-10">{metric.value}</div>
              <div className="text-[10px] uppercase tracking-widest text-white/40 mt-1 relative z-10">{metric.label}</div>
            </motion.div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Activity chart */}
        <motion.div
          variants={itemVariants}
          className="border border-white/10 bg-white/[0.02] p-6"
        >
          <div className="flex items-center gap-3 mb-6">
            <BarChart3 className="w-4 h-4 text-white/50" />
            <h2 className="text-xs font-semibold uppercase tracking-[0.15em] text-white/50">Weekly Activity</h2>
          </div>
          <div className="flex items-end gap-2 h-48">
            {WEEKLY_DATA.map((d) => (
              <div key={d.day} className="flex-1 flex flex-col items-center gap-2">
                <div className="w-full relative" style={{ height: `${(d.messages / MAX_MESSAGES) * 100}%` }}>
                  <div className="absolute inset-0 bg-white/10 group-hover:bg-white/20 transition-colors" />
                  <div
                    className="absolute bottom-0 left-0 right-0 bg-white/30 transition-all duration-500"
                    style={{ height: `${(d.conversations / d.messages) * 100}%` }}
                  />
                </div>
                <span className="text-[9px] uppercase tracking-widest text-white/30">{d.day}</span>
              </div>
            ))}
          </div>
          <div className="flex items-center gap-4 mt-4 text-[9px] uppercase tracking-widest text-white/30">
            <span className="flex items-center gap-1.5"><span className="w-2 h-2 bg-white/30" /> Conversations</span>
            <span className="flex items-center gap-1.5"><span className="w-2 h-2 bg-white/10" /> Messages</span>
          </div>
        </motion.div>

        {/* Agent performance */}
        <motion.div
          variants={itemVariants}
          className="border border-white/10 bg-white/[0.02] p-6"
        >
          <div className="flex items-center gap-3 mb-6">
            <TrendingUp className="w-4 h-4 text-white/50" />
            <h2 className="text-xs font-semibold uppercase tracking-[0.15em] text-white/50">Top Agents</h2>
          </div>
          <div className="space-y-3">
            {AGENT_PERFORMANCE.map((agent, i) => (
              <div key={agent.name} className="flex items-center gap-3 p-3 border border-white/5 hover:border-white/15 transition-colors">
                <div className="text-[10px] font-bold text-white/30 w-4">{i + 1}</div>
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-bold text-white uppercase tracking-wider truncate">{agent.name}</div>
                  <div className="text-[10px] text-white/40 mt-0.5">
                    {agent.conversations} conversations &middot; {agent.rating} rating
                  </div>
                </div>
                <div className={`text-[10px] font-bold ${agent.trend > 0 ? "text-emerald-400/80" : "text-red-400/80"}`}>
                  {agent.trend > 0 ? "+" : ""}{agent.trend}%
                </div>
                <div className="w-20 h-1 bg-white/10 hidden sm:block">
                  <div
                    className="h-full bg-white/40"
                    style={{ width: `${(agent.conversations / AGENT_PERFORMANCE[0].conversations) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </motion.div>
  );
}
