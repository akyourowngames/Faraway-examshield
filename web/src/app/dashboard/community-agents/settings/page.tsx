"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Save, Bell, Lock, Globe, Trash2, AlertTriangle } from "lucide-react";

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { type: "spring" as const, stiffness: 300, damping: 24 } },
};

export default function SettingsPage() {
  const [orgName, setOrgName] = useState("ExamShield Security");
  const [allowPublicAgents, setAllowPublicAgents] = useState(true);
  const [defaultModel, setDefaultModel] = useState("gpt-4o");
  const [maxAgents, setMaxAgents] = useState("25");
  const [notifications, setNotifications] = useState(true);

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
            Settings
          </h1>
          <p className="text-white/50 text-xs font-mono uppercase tracking-widest mt-2">
            Configure your community agents platform.
          </p>
        </div>
      </div>

      {/* Organization */}
      <motion.div variants={itemVariants} className="border border-white/10 bg-white/[0.02] p-6">
        <div className="flex items-center gap-3 mb-6">
          <Globe className="w-4 h-4 text-white/50" />
          <h2 className="text-xs font-semibold uppercase tracking-[0.15em] text-white/50">Organization</h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
          <div>
            <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">Organization Name</label>
            <input
              type="text"
              value={orgName}
              onChange={(e) => setOrgName(e.target.value)}
              className="w-full px-4 py-3 bg-white/[0.03] border border-white/10 text-white text-sm focus:outline-none focus:border-white/30 transition-colors"
            />
          </div>
          <div>
            <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">Max Agents</label>
            <input
              type="number"
              value={maxAgents}
              onChange={(e) => setMaxAgents(e.target.value)}
              className="w-full px-4 py-3 bg-white/[0.03] border border-white/10 text-white text-sm focus:outline-none focus:border-white/30 transition-colors"
            />
          </div>
        </div>
      </motion.div>

      {/* Agent Defaults */}
      <motion.div variants={itemVariants} className="border border-white/10 bg-white/[0.02] p-6">
        <div className="flex items-center gap-3 mb-6">
          <Lock className="w-4 h-4 text-white/50" />
          <h2 className="text-xs font-semibold uppercase tracking-[0.15em] text-white/50">Agent Defaults</h2>
        </div>
        <div className="space-y-4">
          <div>
            <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-2 font-bold">Default Model</label>
            <div className="grid grid-cols-2 gap-2">
              {["gpt-4o", "gpt-4o-mini"].map((m) => (
                <button
                  key={m}
                  onClick={() => setDefaultModel(m)}
                  className={`px-4 py-3 text-xs font-bold uppercase tracking-widest border transition-colors ${
                    defaultModel === m
                      ? "border-white/30 bg-white/10 text-white"
                      : "border-white/10 text-white/40 hover:border-white/20"
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center justify-between py-3 border-b border-white/5">
            <div>
              <div className="text-xs font-bold text-white uppercase tracking-wider">Allow Public Agents</div>
              <div className="text-[10px] text-white/40 mt-0.5">Let agents be discovered in the marketplace</div>
            </div>
            <button
              onClick={() => setAllowPublicAgents(!allowPublicAgents)}
              className={`w-10 h-5 rounded-full transition-colors relative ${
                allowPublicAgents ? "bg-white" : "bg-white/20"
              }`}
            >
              <div
                className={`absolute top-0.5 w-4 h-4 rounded-full transition-transform ${
                  allowPublicAgents ? "left-5 bg-black" : "left-0.5 bg-white/60"
                }`}
              />
            </button>
          </div>
        </div>
      </motion.div>

      {/* Notifications */}
      <motion.div variants={itemVariants} className="border border-white/10 bg-white/[0.02] p-6">
        <div className="flex items-center gap-3 mb-6">
          <Bell className="w-4 h-4 text-white/50" />
          <h2 className="text-xs font-semibold uppercase tracking-[0.15em] text-white/50">Notifications</h2>
        </div>
        <div className="flex items-center justify-between py-3">
          <div>
            <div className="text-xs font-bold text-white uppercase tracking-wider">Agent Activity Alerts</div>
            <div className="text-[10px] text-white/40 mt-0.5">Get notified about agent errors and milestones</div>
          </div>
          <button
            onClick={() => setNotifications(!notifications)}
            className={`w-10 h-5 rounded-full transition-colors relative ${
              notifications ? "bg-white" : "bg-white/20"
            }`}
          >
            <div
              className={`absolute top-0.5 w-4 h-4 rounded-full transition-transform ${
                notifications ? "left-5 bg-black" : "left-0.5 bg-white/60"
              }`}
            />
          </button>
        </div>
      </motion.div>

      {/* Danger Zone */}
      <motion.div variants={itemVariants} className="border border-red-500/20 bg-red-500/[0.02] p-6">
        <div className="flex items-center gap-3 mb-4">
          <AlertTriangle className="w-4 h-4 text-red-400/60" />
          <h2 className="text-xs font-semibold uppercase tracking-[0.15em] text-red-400/60">Danger Zone</h2>
        </div>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs font-bold text-white/60 uppercase tracking-wider">Delete All Agents</div>
            <div className="text-[10px] text-white/30 mt-0.5">Permanently remove all agents and their data</div>
          </div>
          <button className="flex items-center gap-2 px-4 py-2 border border-red-500/30 text-red-400/60 text-[10px] font-bold uppercase tracking-widest hover:bg-red-500/10 transition-colors">
            <Trash2 className="w-3 h-3" />
            Delete All
          </button>
        </div>
      </motion.div>

      {/* Save */}
      <div className="flex justify-end">
        <button className="flex items-center gap-2 px-6 py-2.5 bg-white text-black text-xs font-bold uppercase tracking-widest hover:bg-white/90 transition-colors">
          <Save className="w-3.5 h-3.5" />
          Save Changes
        </button>
      </div>
    </motion.div>
  );
}
