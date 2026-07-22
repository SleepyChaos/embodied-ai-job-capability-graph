import { useState } from "react";

import { DataOverview } from "./components/DataOverview";
import { DataImport } from "./components/DataImport";
import type { AppSection } from "./types";

export default function App() {
  const [section, setSection] = useState<AppSection>("overview");

  return (
    <div className="min-h-screen bg-background text-on-surface">
      {/* Header */}
      <header className="border-b border-outline-variant bg-surface">
        <div className="mx-auto max-w-7xl px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-semibold text-on-surface">岗位智能分析图谱</h1>
              <p className="mt-1 text-sm text-on-surface-variant">数据管理平台</p>
            </div>
            <nav className="flex gap-1">
              <button
                onClick={() => setSection("overview")}
                className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                  section === "overview"
                    ? "bg-primary text-on-primary"
                    : "text-on-surface-variant hover:bg-surface-container hover:text-on-surface"
                }`}
              >
                数据总览
              </button>
              <button
                onClick={() => setSection("import")}
                className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                  section === "import"
                    ? "bg-primary text-on-primary"
                    : "text-on-surface-variant hover:bg-surface-container hover:text-on-surface"
                }`}
              >
                数据导入
              </button>
            </nav>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="mx-auto max-w-7xl px-6 py-8">
        {section === "overview" && <DataOverview />}
        {section === "import" && <DataImport />}
      </main>
    </div>
  );
}
