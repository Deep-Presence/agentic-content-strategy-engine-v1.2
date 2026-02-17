"use client";

import { Sidebar } from "./Sidebar";
import { ArtifactPanel } from "./ArtifactPanel";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-canvas">
      <Sidebar />
      <main className="flex-1 ml-[220px] p-8">{children}</main>
      <ArtifactPanel />
    </div>
  );
}
