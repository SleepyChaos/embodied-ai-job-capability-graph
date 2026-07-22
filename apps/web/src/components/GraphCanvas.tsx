import { Graph } from "@antv/g6";
import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";

import type { GraphEdgeV2, GraphKind, GraphPayloadV2 } from "../types";

export type GraphCanvasHandle = { fit: () => void; zoomIn: () => void; zoomOut: () => void };

type Props = {
  payload: GraphPayloadV2;
  graphKind: GraphKind;
  selectedId?: string;
  mode: "taxonomy" | "community";
  onNodeSelect: (id: string) => void;
  onEdgeSelect: (edge: GraphEdgeV2) => void;
};

/** Lighten a hex color by a percentage (0-1) */
function lightenColor(hex: string, amount: number): string {
  const num = parseInt(hex.replace("#", ""), 16);
  const r = Math.min(255, ((num >> 16) & 0xff) + Math.round(255 * amount));
  const g = Math.min(255, ((num >> 8) & 0xff) + Math.round(255 * amount));
  const b = Math.min(255, (num & 0xff) + Math.round(255 * amount));
  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, "0")}`;
}

function createSeededRandom(seed = 0x6d2b79f5) {
  let state = seed >>> 0;
  return () => {
    state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
    return state / 4294967296;
  };
}

export const GraphCanvas = forwardRef<GraphCanvasHandle, Props>(function GraphCanvas(props, ref) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  const graphReadyRef = useRef(false);
  const selectedIdRef = useRef(props.selectedId);
  const previousSelectedIdRef = useRef<string | undefined>(undefined);
  const visibleNodeIdsRef = useRef(new Set(props.payload.nodes.map((node) => node.id)));
  const callbacks = useRef({ node: props.onNodeSelect, edge: props.onEdgeSelect });
  const layoutKeyRef = useRef(`${props.graphKind}-${props.mode}`);
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);
  const pendingDataRef = useRef<typeof props.payload | null>(null);

  callbacks.current = { node: props.onNodeSelect, edge: props.onEdgeSelect };
  selectedIdRef.current = props.selectedId;
  visibleNodeIdsRef.current = new Set(props.payload.nodes.map((node) => node.id));

  const clearTimers = () => {
    timersRef.current.forEach(clearTimeout);
    timersRef.current = [];
  };

  const addTimer = (fn: () => void, delay: number) => {
    timersRef.current.push(setTimeout(fn, delay));
  };

  useImperativeHandle(ref, () => ({
    fit: () => { void graphRef.current?.fitView({ when: "always" }); },
    zoomIn: () => { void graphRef.current?.zoomBy(1.2); },
    zoomOut: () => { void graphRef.current?.zoomBy(0.82); },
  }), []);

  // Effect 1: Create/destroy Graph instance only when layout type changes
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const isCapability = props.graphKind === "capability";
    const isCareerCommunity = !isCapability && props.mode === "community";
    const similarityScore = (datum: any) => Math.max(0, Math.min(1, Number(datum.data?.score ?? 0)));

    let disposed = false;
    let activeGraph: Graph | null = null;

    const frame = window.requestAnimationFrame(() => {
      if (disposed) return;

      const nodeSizes = { 0: [96, 40], 1: [80, 34], 2: [70, 28], 3: [60, 24] } as Record<number, [number, number]>;

      const graph = new Graph({
        container,
        autoResize: true,
        data: { nodes: [], edges: [], combos: [] },
        animation: false,
        padding: 44,
        layout: isCapability
          ? {
              type: "mindmap",
              direction: "LR",
              getHeight: (d: any) => {
                const l = Number(d?.data?.level ?? 2);
                return (nodeSizes[l] ?? nodeSizes[3]!)[1];
              },
              getWidth: (d: any) => {
                const l = Number(d?.data?.level ?? 2);
                return (nodeSizes[l] ?? nodeSizes[3]!)[0];
              },
              getHGap: () => 40,
              getVGap: () => 10,
            }
          : isCareerCommunity
            ? {
                type: "d3-force",
                nodeStrength: -120,
                linkDistance: (edge: any) => 170 - similarityScore(edge) * 105,
                edgeStrength: (edge: any) => 0.15 + similarityScore(edge) * 0.7,
                preventOverlap: true,
                collide: {
                  radius: (node: any) => 28 + Math.min(12, Number(node.data?.capabilityCount ?? 0) / 3),
                  strength: 0.9,
                  iterations: 2,
                },
                clustering: true,
                clusterBy: (node: any) => String(node.data?.categoryL1 ?? "其他"),
                clusterNodeStrength: -5,
                clusterEdgeStrength: 0.12,
                clusterEdgeDistance: 160,
                clusterNodeSize: 36,
                clusterFociStrength: 0.16,
                iterations: 360,
                alphaDecay: 0.035,
                velocityDecay: 0.35,
                randomSource: createSeededRandom(),
              }
            : { type: "combo-combined", preventOverlap: true, spacing: 30 },
        node: {
          type: isCapability ? "rect" : "circle",
          style: {
            ...(isCapability
              ? {
                  size: (datum: any) => {
                    const l = Number(datum.data?.level ?? 2);
                    return nodeSizes[l] ?? nodeSizes[3]!;
                  },
                  fill: (datum: any) => {
                    const l = Number(datum.data?.level ?? 2);
                    const baseColor = String(datum.data?.color ?? "#4b5c6e");
                    if (l === 0) return "#3a4a5c";
                    if (l === 1) return baseColor;
                    if (l === 2) return lightenColor(baseColor, 0.25);
                    return lightenColor(baseColor, 0.5);
                  },
                  radius: 8,
                  labelText: (datum: any) => String(datum.data?.label ?? ""),
                  labelFill: (datum: any) => {
                    const l = Number(datum.data?.level ?? 2);
                    return l <= 1 ? "#ffffff" : "#2d3748";
                  },
                  labelFontSize: (datum: any) => {
                    const l = Number(datum.data?.level ?? 2);
                    return Math.max(9, 13 - l);
                  },
                  labelPlacement: "center",
                  labelMaxWidth: (datum: any) => {
                    const l = Number(datum.data?.level ?? 2);
                    return ((nodeSizes[l] ?? nodeSizes[3]!)[0] - 8);
                  },
                  labelWordWrap: true,
                  stroke: "#ffffff",
                  lineWidth: 2,
                }
              : {
                  size: (datum: any) => 24 + Math.min(18, Number(datum.data?.capabilityCount ?? 0) / 3),
                  fill: (datum: any) => String(datum.data?.color ?? "#155eef"),
                  stroke: "#ffffff",
                  lineWidth: 2,
                  labelText: (datum: any) => String(datum.data?.label ?? ""),
                  labelFill: "#172033",
                  labelFontSize: 10,
                  labelPlacement: "bottom",
                  labelMaxWidth: 116,
                  labelWordWrap: true,
                  labelBackground: true,
                  labelBackgroundFill: "rgba(255,255,255,.88)",
                  labelBackgroundRadius: 3,
                }),
            cursor: "pointer",
          },
          state: { selected: { stroke: "#f59e0b", lineWidth: 4, shadowColor: "rgba(245,158,11,.35)", shadowBlur: 10 } },
        },
        edge: {
          type: isCapability ? "cubic-horizontal" : "line",
          style: {
            stroke: (datum: any) => datum.data?.edgeType === "SIMILAR_TO" ? "#8fa4c7" : "#c8d2e3",
            lineWidth: (datum: any) => 1 + Number(datum.data?.score ?? datum.data?.weight ?? 0),
            opacity: (datum: any) => 0.35 + Number(datum.data?.score ?? 0.5) * 0.55,
            endArrow: false,
            cursor: "pointer",
          },
          state: { selected: { stroke: "#f59e0b", lineWidth: 3, opacity: 1 } },
        },
        combo: {
          type: "rect",
          style: {
            fill: (datum: any) => {
              const color = String(datum.data?.color ?? "#cbd7eb");
              return color + "18";
            },
            stroke: (datum: any) => {
              const color = String(datum.data?.color ?? "#cbd7eb");
              return color + "60";
            },
            lineWidth: 1,
            labelText: (datum: any) => String(datum.data?.label ?? ""),
            labelFill: (datum: any) => String(datum.data?.color ?? "#334155"),
            labelFontSize: 11,
            labelFontWeight: 600,
            radius: 12,
            padding: [24, 16, 16, 16],
          },
        },
        behaviors: ["drag-canvas", "zoom-canvas", isCareerCommunity ? "drag-element-force" : "drag-element", "click-select"],
      });

      activeGraph = graph;
      graphRef.current = graph;
      graphReadyRef.current = true;
      graph.on("node:click", (event: any) => callbacks.current.node(String(event.target.id)));
      graph.on("edge:click", (event: any) => {
        const edge = props.payload.edges.find((item) => item.id === String(event.target.id));
        if (edge) callbacks.current.edge(edge);
      });

      // If there's pending data, apply it now
      if (pendingDataRef.current) {
        const pendingPayload = pendingDataRef.current;
        pendingDataRef.current = null;
        const isCapability = props.graphKind === "capability";
        const isCareerCommunity = !isCapability && props.mode === "community";
        const data = {
          nodes: pendingPayload.nodes.map((node) => ({
            id: node.id,
            combo: isCareerCommunity ? undefined : node.comboId,
            data: { ...node.data, graphType: node.type },
          })),
          edges: pendingPayload.edges.map((edge) => ({ id: edge.id, source: edge.source, target: edge.target, data: { ...edge.data, edgeType: edge.type } })),
          combos: isCareerCommunity ? [] : pendingPayload.combos.map((combo) => ({ id: combo.id, combo: combo.parentId, data: combo.data })),
        };
        void graph.setData(data);
        void graph.render();
      }
    });

    return () => {
      disposed = true;
      graphReadyRef.current = false;
      clearTimers();
      window.cancelAnimationFrame(frame);
      if (activeGraph) activeGraph.destroy();
      if (graphRef.current === activeGraph) graphRef.current = null;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.graphKind, props.mode]);

  // Effect 2: Update data when payload changes (without destroying the Graph)
  useEffect(() => {
    const graph = graphRef.current;
    const isCapability = props.graphKind === "capability";
    const isCareerCommunity = !isCapability && props.mode === "community";

    // If graph is not ready yet, store pending data
    if (!graph || !graphReadyRef.current) {
      pendingDataRef.current = props.payload;
      return;
    }

    const data = {
      nodes: props.payload.nodes.map((node) => ({
        id: node.id,
        combo: isCareerCommunity ? undefined : node.comboId,
        data: { ...node.data, graphType: node.type },
      })),
      edges: props.payload.edges.map((edge) => ({ id: edge.id, source: edge.source, target: edge.target, data: { ...edge.data, edgeType: edge.type } })),
      combos: isCareerCommunity ? [] : props.payload.combos.map((combo) => ({ id: combo.id, combo: combo.parentId, data: combo.data })),
    };

    clearTimers();

    void graph.setData(data);
    void graph.render();

    // Listen for afterlayout event
    const onAfterLayout = () => {
      if (graphRef.current) {
        void graphRef.current.fitView({ when: "always" });
        // Apply selected state after layout
        const selectedId = selectedIdRef.current;
        if (selectedId && visibleNodeIdsRef.current.has(selectedId)) {
          void graphRef.current.setElementState(selectedId, "selected");
          previousSelectedIdRef.current = selectedId;
        }
      }
    };
    graph.on("afterlayout", onAfterLayout);

    // Multi-stage fitView for layouts that don't emit afterlayout or take longer
    const delays = isCapability ? [100, 400, 800] : [200, 600, 1200, 2000, 3000];
    delays.forEach((delay) => {
      addTimer(() => {
        if (graphRef.current) void graphRef.current.fitView({ when: "always" });
      }, delay);
    });

    return () => {
      graph.off("afterlayout", onAfterLayout);
      clearTimers();
    };
  }, [props.payload, props.graphKind, props.mode]);

  // Effect 3: Handle selected state changes independently
  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;
    const previousId = previousSelectedIdRef.current;
    const selectedId = props.selectedId;
    if (previousId === selectedId) return;
    void (async () => {
      if (previousId && visibleNodeIdsRef.current.has(previousId)) {
        await graph.setElementState(previousId, []);
      }
      if (selectedId && visibleNodeIdsRef.current.has(selectedId)) {
        await graph.setElementState(selectedId, "selected");
      }
      previousSelectedIdRef.current = selectedId;
    })();
  }, [props.selectedId]);

  return <div className="graph-canvas" ref={containerRef} aria-label={props.graphKind === "capability" ? "能力层级图谱" : "职业关联图谱"} />;
});
