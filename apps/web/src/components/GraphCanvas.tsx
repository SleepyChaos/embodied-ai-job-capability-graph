import { Graph } from "@antv/g6";
import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef } from "react";

import type { GraphEdgeV2, GraphKind, GraphPayloadV2 } from "../types";

export type GraphCanvasHandle = {
  fit: () => void;
  focus: (id: string) => void;
  zoomIn: () => void;
  zoomOut: () => void;
};

type Props = {
  payload: GraphPayloadV2;
  graphKind: GraphKind;
  selectedId?: string;
  mode: "taxonomy" | "community";
  onNodeSelect: (id: string) => void;
  onEdgeSelect: (edge: GraphEdgeV2) => void;
};

type Point = { x: number; y: number };

function lightenColor(hex: string, amount: number): string {
  const num = parseInt(hex.replace("#", ""), 16);
  const r = Math.min(255, ((num >> 16) & 0xff) + Math.round(255 * amount));
  const g = Math.min(255, ((num >> 8) & 0xff) + Math.round(255 * amount));
  const b = Math.min(255, (num & 0xff) + Math.round(255 * amount));
  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, "0")}`;
}

function radialPositions(payload: GraphPayloadV2): Map<string, Point> {
  const points = new Map<string, Point>([["capability-root", { x: 0, y: 0 }]]);
  const nodes = new Map(payload.nodes.map((node) => [node.id, node]));
  const children = new Map<string, string[]>();
  payload.edges.filter((edge) => edge.type === "PARENT_OF").forEach((edge) => {
    children.set(edge.source, [...(children.get(edge.source) ?? []), edge.target]);
  });
  const sortIds = (ids: string[]) => [...ids].sort((left, right) => {
    const a = Number(nodes.get(left)?.data.sortOrder ?? 0);
    const b = Number(nodes.get(right)?.data.sortOrder ?? 0);
    return a - b || String(nodes.get(left)?.data.label).localeCompare(String(nodes.get(right)?.data.label), "zh-CN");
  });
  const directions = sortIds(children.get("capability-root") ?? []);
  const sector = (Math.PI * 2) / Math.max(1, directions.length);

  directions.forEach((directionId, directionIndex) => {
    const centerAngle = -Math.PI / 2 + directionIndex * sector;
    points.set(directionId, { x: Math.cos(centerAngle) * 175, y: Math.sin(centerAngle) * 175 });
    const categories = sortIds(children.get(directionId) ?? []);
    const categorySpan = sector * 0.62;
    categories.forEach((categoryId, categoryIndex) => {
      const categoryAngle = categories.length === 1
        ? centerAngle
        : centerAngle - categorySpan / 2 + categorySpan * (categoryIndex / (categories.length - 1));
      points.set(categoryId, { x: Math.cos(categoryAngle) * 325, y: Math.sin(categoryAngle) * 325 });

      const capabilities = sortIds(children.get(categoryId) ?? []);
      const ringSize = 6;
      capabilities.forEach((capabilityId, capabilityIndex) => {
        const ring = Math.floor(capabilityIndex / ringSize);
        const ringItems = capabilities.slice(ring * ringSize, (ring + 1) * ringSize);
        const indexInRing = capabilityIndex % ringSize;
        const leafSpan = Math.min(sector * 0.24, 0.055 * Math.max(1, ringItems.length - 1));
        const leafAngle = ringItems.length === 1
          ? categoryAngle
          : categoryAngle - leafSpan / 2 + leafSpan * (indexInRing / (ringItems.length - 1));
        const radius = 510 + ring * 125;
        points.set(capabilityId, { x: Math.cos(leafAngle) * radius, y: Math.sin(leafAngle) * radius });
      });
    });
  });
  return points;
}

export const GraphCanvas = forwardRef<GraphCanvasHandle, Props>(function GraphCanvas(props, ref) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  const callbacks = useRef({ node: props.onNodeSelect, edge: props.onEdgeSelect });
  const previousSelectedId = useRef<string | undefined>(undefined);
  callbacks.current = { node: props.onNodeSelect, edge: props.onEdgeSelect };

  const positions = useMemo(() => radialPositions(props.payload), [props.payload]);

  useImperativeHandle(ref, () => ({
    fit: () => { void graphRef.current?.fitView({ when: "always" }); },
    focus: (id) => { void graphRef.current?.focusElement(id, { duration: 350, easing: "ease-in-out" }); },
    zoomIn: () => { void graphRef.current?.zoomBy(1.2); },
    zoomOut: () => { void graphRef.current?.zoomBy(0.82); },
  }), []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const nodeSizes = { 0: [118, 44], 1: [106, 38], 2: [96, 34], 3: [104, 32] } as Record<number, [number, number]>;
    const graph = new Graph({
      container,
      autoResize: true,
      animation: false,
      padding: 70,
      data: { nodes: [], edges: [], combos: [] },
      layout: { type: "preset" },
      node: {
        type: "rect",
        style: {
          size: (datum: any) => nodeSizes[Number(datum.data?.level ?? 3)] ?? nodeSizes[3]!,
          x: (datum: any) => Number(datum.style?.x ?? datum.data?.x ?? 0),
          y: (datum: any) => Number(datum.style?.y ?? datum.data?.y ?? 0),
          fill: (datum: any) => {
            const level = Number(datum.data?.level ?? 3);
            const base = String(datum.data?.color ?? "#4b5c6e");
            if (level === 0) return "#26364d";
            if (level === 1) return base;
            if (level === 2) return lightenColor(base, 0.25);
            return lightenColor(base, 0.54);
          },
          stroke: "#ffffff",
          lineWidth: 2,
          radius: 8,
          labelText: (datum: any) => String(datum.data?.label ?? ""),
          labelFill: (datum: any) => Number(datum.data?.level ?? 3) <= 1 ? "#ffffff" : "#26364d",
          labelFontSize: (datum: any) => Number(datum.data?.level ?? 3) <= 1 ? 11 : 9,
          labelFontWeight: (datum: any) => Number(datum.data?.level ?? 3) <= 1 ? 650 : 500,
          labelPlacement: "center",
          labelMaxWidth: (datum: any) => (nodeSizes[Number(datum.data?.level ?? 3)] ?? nodeSizes[3]!)[0] - 10,
          labelWordWrap: true,
          cursor: "pointer",
        },
        state: {
          selected: {
            stroke: "#f59e0b",
            lineWidth: 4,
            shadowColor: "rgba(245,158,11,.35)",
            shadowBlur: 12,
          },
        },
      },
      edge: {
        type: "cubic-radial",
        style: {
          stroke: "#aebbd0",
          lineWidth: 1.2,
          opacity: 0.7,
          endArrow: false,
        },
      },
      behaviors: ["drag-canvas", "zoom-canvas", "click-select"],
    });
    graphRef.current = graph;
    graph.on("node:click", (event: any) => callbacks.current.node(String(event.target.id)));
    graph.on("edge:click", (event: any) => {
      const edge = props.payload.edges.find((item) => item.id === String(event.target.id));
      if (edge) callbacks.current.edge(edge);
    });
    return () => {
      graph.destroy();
      if (graphRef.current === graph) graphRef.current = null;
    };
  // Graph instance deliberately survives data refreshes.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;
    const data = {
      nodes: props.payload.nodes.map((node) => {
        const point = positions.get(node.id) ?? { x: 0, y: 0 };
        return {
          id: node.id,
          data: { ...node.data, graphType: node.type, x: point.x, y: point.y },
          style: point,
        };
      }),
      edges: props.payload.edges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        data: { ...edge.data, edgeType: edge.type },
      })),
      combos: [],
    };
    void graph.setData(data);
    void graph.render();
    [180, 650, 1200].forEach((delay) => window.setTimeout(() => {
      if (graphRef.current === graph) void graph.fitView({ when: "always" });
    }, delay));
    window.setTimeout(() => {
      if (graphRef.current !== graph) return;
      if (props.selectedId) void graph.setElementState(props.selectedId, "selected");
      previousSelectedId.current = props.selectedId;
    }, 200);
  }, [positions, props.payload]);

  useEffect(() => {
    const graph = graphRef.current;
    if (!graph || previousSelectedId.current === props.selectedId) return;
    void (async () => {
      if (previousSelectedId.current) await graph.setElementState(previousSelectedId.current, []);
      if (props.selectedId) await graph.setElementState(props.selectedId, "selected");
      previousSelectedId.current = props.selectedId;
    })();
  }, [props.selectedId]);

  return <div className="graph-canvas" ref={containerRef} aria-label="能力径向层级图谱" />;
});
