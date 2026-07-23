import { useState } from "react";

import { CapabilityGraphExplorer } from "./CapabilityGraphExplorer";
import { CareerGraphExplorer } from "./CareerGraphExplorer";
import { CareerSpectrumExplorer } from "./CareerSpectrumExplorer";

export function GraphExplorer() {
  const initial = new URLSearchParams(location.search);
  const [kind, setKind] = useState<"capability" | "career" | "spectrum">(
    initial.get("graph") === "career"
      ? "career"
      : initial.get("graph") === "spectrum"
        ? "spectrum"
        : "capability",
  );

  const switchTo = (next: "capability" | "career" | "spectrum", jobId?: number) => {
    const params = new URLSearchParams(location.search);
    params.set("section", "graph");
    params.set("graph", next);
    for (const key of ["node", "job", "q"]) params.delete(key);
    if (jobId) {
      if (next === "career") params.set("node", `job:${jobId}`);
      if (next === "spectrum") params.set("job", String(jobId));
    }
    history.replaceState(null, "", `${location.pathname}?${params}`);
    setKind(next);
  };

  if (kind === "career") {
    return <CareerGraphExplorer onSwitch={() => switchTo("capability")} onSpectrum={() => switchTo("spectrum")} />;
  }
  if (kind === "spectrum") {
    return (
      <CareerSpectrumExplorer
        onCapability={() => switchTo("capability")}
        onCareer={() => switchTo("career")}
        onOpenCareer={(jobId) => switchTo("career", jobId)}
      />
    );
  }
  return <CapabilityGraphExplorer onSwitch={() => switchTo("career")} onSpectrum={() => switchTo("spectrum")} />;
}
