"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { Search, Bot, Plus, BookOpen, BarChart3, Settings } from "lucide-react";
import { cn } from "@/lib/utils";

const SUB_NAV = [
  { name: "Discover", href: "/dashboard/community-agents/discover", icon: Search },
  { name: "My Agents", href: "/dashboard/community-agents/my-agents", icon: Bot },
  { name: "Create", href: "/dashboard/community-agents/create", icon: Plus },
  { name: "Knowledge", href: "/dashboard/community-agents/knowledge", icon: BookOpen },
  { name: "Analytics", href: "/dashboard/community-agents/analytics", icon: BarChart3 },
  { name: "Settings", href: "/dashboard/community-agents/settings", icon: Settings },
];

export default function CommunityAgentsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="space-y-6">
      {/* Sub-navigation */}
      <div className="flex items-center gap-1 border-b border-white/10 pb-0 overflow-x-auto">
        {SUB_NAV.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link key={item.name} href={item.href}>
              <div className={cn(
                "relative flex items-center gap-2 px-4 py-3 text-xs font-semibold uppercase tracking-widest transition-colors whitespace-nowrap",
                isActive
                  ? "text-white"
                  : "text-white/40 hover:text-white/70"
              )}>
                <Icon className="w-3.5 h-3.5" />
                {item.name}
                {isActive && (
                  <motion.div
                    layoutId="community-agents-tab"
                    className="absolute bottom-0 left-0 right-0 h-[2px] bg-white"
                    transition={{ type: "spring", stiffness: 400, damping: 30 }}
                  />
                )}
              </div>
            </Link>
          );
        })}
      </div>

      {/* Page content */}
      <motion.div
        key={pathname}
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: "easeOut" }}
      >
        {children}
      </motion.div>
    </div>
  );
}
