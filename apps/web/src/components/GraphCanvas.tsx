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

const levelColor = ["#0f2f63", "#155eef", "#6d55c4", "#c37b32"];

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
  const selectedIdRef = useRef(props.selectedId);
  const previousSelectedIdRef = useRef<string | undefined>(undefined);
  const visibleNodeIdsRef = useRef(new Set(props.payload.nodes.map((node) => node.id)));
  const callbacks = useRef({ node: props.onNodeSelect, edge: props.onEdgeSelect });
  callbacks.current = { node: props.onNodeSelect, edge: props.onEdgeSelect };
  selectedIdRef.current = props.selectedId;
  visibleNodeIdsRef.current = new Set(props.payload.nodes.map((node) => node.id));

  useImperativeHandle(ref, () => ({
    fit: () => { void graphRef.current?.fitView({ when: "always" }); },
    zoomIn: () => { void graphRef.current?.zoomBy(1.2); },
    zoomOut: () => { void graphRef.current?.zoomBy(0.82); },
  }), []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const isCapability = props.graphKind === "capability";
    const isCareerCommunity = !isCapability && props.mode === "community";
    const similarityScore = (datum: any) => Math.max(0, Math.min(1, Number(datum.data?.score ?? 0)));
    const data = {
      nodes: props.payload.nodes.map((node) => ({
        id: node.id,
        combo: isCareerCommunity ? undefined : node.comboId,
        data: { ...node.data, graphType: node.type },
      })),
      edges: props.payload.edges.map((edge) => ({ id: edge.id, source: edge.source, target: edge.target, data: { ...edge.data, edgeType: edge.type } })),
      combos: isCareerCommunity ? [] : props.payload.combos.map((combo) => ({ id: combo.id, combo: combo.parentId, data: combo.data })),
    };
    let disposed = false;
    let activeGraph: Graph | null = null;
    const frame = window.requestAnimationFrame(() => {
    if (disposed) return;
    const graph = new Graph({
      container,
      autoResize: true,
      data,
      animation: false,
      padding: 44,
      layout: isCapability
        ? { type: "dagre", rankdir: "LR", nodesep: 24, ranksep: 74, controlPoints: true }
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
        type: "circle",
        style: {
          size: (datum) => isCapability ? Math.max(24, 48 - Number(datum.data?.level ?? 3) * 6) : 24 + Math.min(18, Number(datum.data?.capabilityCount ?? 0) / 3),
          fill: (datum) => isCapability ? levelColor[Number(datum.data?.level ?? 3)] : String(datum.data?.color ?? "#155eef"),
          stroke: "#ffffff",
          lineWidth: 2,
          labelText: (datum) => String(datum.data?.label ?? ""),
          labelFill: "#172033",
          labelFontSize: isCapability ? 11 : 10,
          labelPlacement: "bottom",
          labelMaxWidth: isCapability ? 138 : 116,
          labelWordWrap: true,
          labelBackground: true,
          labelBackgroundFill: "rgba(255,255,255,.88)",
          labelBackgroundRadius: 3,
          cursor: "pointer",
        },
        state: { selected: { stroke: "#f59e0b", lineWidth: 4, shadowColor: "rgba(245,158,11,.35)", shadowBlur: 10 } },
      },
      edge: {
        type: isCapability ? "polyline" : "line",
        style: {
          stroke: (datum) => datum.data?.edgeType === "SIMILAR_TO" ? "#8fa4c7" : "#c8d2e3",
          lineWidth: (datum) => 1 + Number(datum.data?.score ?? datum.data?.weight ?? 0),
          opacity: (datum) => 0.35 + Number(datum.data?.score ?? 0.5) * 0.55,
          endArrow: false,
          cursor: "pointer",
        },
        state: { selected: { stroke: "#f59e0b", lineWidth: 3, opacity: 1 } },
      },
      combo: {
        type: "rect",
        style: {
          fill: "rgba(238,244,255,.35)", stroke: "#cbd7eb", lineWidth: 1,
          labelText: (datum) => String(datum.data?.label ?? ""), labelFill: "#334155", labelFontSize: 11,
          labelFontWeight: 600, radius: 12, padding: [24, 16, 16, 16],
        },
      },
      behaviors: ["drag-canvas", "zoom-canvas", isCareerCommunity ? "drag-element-force" : "drag-element", "click-select"],
    });
    activeGraph = graph;
    graphRef.current = graph;
    graph.on("node:click", (event: any) => callbacks.current.node(String(event.target.id)));
    graph.on("edge:click", (event: any) => {
      const edge = props.payload.edges.find((item) => item.id === String(event.target.id));
      if (edge) callbacks.current.edge(edge);
    });
    void graph.render().then(() => {
      if (disposed) return;
      const selectedId = selectedIdRef.current;
      if (selectedId && visibleNodeIdsRef.current.has(selectedId)) {
        void graph.setElementState(selectedId, "selected");
        previousSelectedIdRef.current = selectedId;
      }
      void graph.fitView({ when: "always" });
    });
    });
    return () => {
      disposed = true;
      window.cancelAnimationFrame(frame);
      if (activeGraph) activeGraph.destroy();
      if (graphRef.current === activeGraph) graphRef.current = null;
    };
  }, [props.graphKind, props.mode, props.payload]);

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
