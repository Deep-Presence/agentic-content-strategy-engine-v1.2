"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Search,
  BarChart3,
  FileText,
  FolderOpen,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/research", label: "Research", icon: Search },
  { href: "/gap-analysis", label: "Gap Analysis", icon: BarChart3 },
  { href: "/content", label: "Content", icon: FileText },
  { href: "/artifacts", label: "Artifacts", icon: FolderOpen },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 bottom-0 w-[220px] border-r border-canvas-muted bg-canvas-subtle flex flex-col z-30">
      {/* Brand */}
      <div className="px-6 py-5 border-b border-canvas-muted">
        <h1 className="font-display text-[1.125rem] text-ink tracking-tight">
          Deep Presence
        </h1>
        <p className="font-mono text-[0.6875rem] text-ink-tertiary mt-0.5 tracking-wide uppercase">
          Content Engine
        </p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const isActive =
            href === "/" ? pathname === "/" : pathname.startsWith(href);

          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-[0.875rem] font-body transition-colors duration-150",
                isActive
                  ? "bg-terracotta-50 text-terracotta-700 border-l-2 border-terracotta-500"
                  : "text-ink-secondary hover:text-ink hover:bg-canvas"
              )}
            >
              <Icon
                size={18}
                className={cn(
                  isActive ? "text-terracotta-500" : "text-ink-tertiary"
                )}
              />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-6 py-4 border-t border-canvas-muted">
        <p className="font-mono text-[0.625rem] text-ink-tertiary">
          MVP Dashboard
        </p>
      </div>
    </aside>
  );
}
