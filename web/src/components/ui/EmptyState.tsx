import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

type EmptyStateProps = {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
};

export function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 px-6 py-12 text-center">
      {Icon && <Icon className="h-8 w-8 text-white/25" aria-hidden="true" />}
      <div>
        <div className="text-xl font-heading uppercase tracking-[0.2em] text-white">{title}</div>
        {description && <p className="mt-3 max-w-xs text-sm text-white/45">{description}</p>}
      </div>
      {action}
    </div>
  );
}
