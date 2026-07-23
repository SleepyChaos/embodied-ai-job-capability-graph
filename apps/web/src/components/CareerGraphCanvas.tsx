import { Graph } from "@antv/g6";
import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef } from "react";

import type { GraphPayloadV2 } from "../types";

export type CareerGraphCanvasHandle = {
  fit: () => void;
  focus: (id: string) => void;
  zoomIn: () => void;
  zoomOut: () => void;
};

type Props = {
  payload: GraphPayloadV2;
  selectedId?: string;
  onNodeSelect: (id: string) => void;
};

type Point = { x: number; y: number };

function neighborhoodPositions(payload: GraphPayloadV2): Map<string, Point> {
  const positions = new Map<string, Point>();
  const kindOrder = { company: 0, canonical: 1, job: 2 } as Record<string, number>;
  const sortNodes = (nodes: typeof payload.nodes) => [...nodes].sort((left, right) =>
    (kindOrder[String(left.data.kind)] ?? 3) - (kindOrder[String(right.data.kind)] ?? 3)
    || left.data.label.localeCompare(right.data.label, "zh-CN"));
  const center = payload.nodes.find((node) => Number(node.data.distance ?? 0) === 0)
    ?? payload.nodes[0];
  if (!center) return positions;
  positions.set(center.id, { x: 0, y: 0 });

  const firstRing = sortNodes(payload.nodes.filter((node) => Number(node.data.distance) === 1));
  firstRing.forEach((node, index) => {
    const angle = -Math.PI / 2 + (Math.PI * 2 * index) / Math.max(1, firstRing.length);
    positions.set(node.id, { x: Math.cos(angle) * 235, y: Math.sin(angle) * 235 });
  });

  const outerNodes = sortNodes(payload.nodes.filter((node) => Number(node.data.distance) >= 2));
  const groups = new Map<string, typeof payload.nodes>();
  outerNodes.forEach((node) => {
    const anchorId = String(node.data.anchorId ?? center.id);
    groups.set(anchorId, [...(groups.get(anchorId) ?? []), node]);
  });
  let fallbackIndex = 0;
  groups.forEach((nodes, anchorId) => {
    const anchorPoint = positions.get(anchorId);
    const baseAngle = anchorPoint
      ? Math.atan2(anchorPoint.y, anchorPoint.x)
      : -Math.PI / 2 + (Math.PI * 2 * fallbackIndex++) / Math.max(1, groups.size);
    const ringSize = 7;
    nodes.forEach((node, index) => {
      const ring = Math.floor(index / ringSize);
      const ringNodes = nodes.slice(ring * ringSize, (ring + 1) * ringSize);
      const indexInRing = index % ringSize;
      const span = Math.min(0.85, 0.16 * Math.max(1, ringNodes.length - 1));
      const angle = ringNodes.length === 1
        ? baseAngle
        : baseAngle - span / 2 + span * indexInRing / (ringNodes.length - 1);
      const radius = 455 + ring * 115;
      positions.set(node.id, { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius });
    });
  });
  return positions;
}

export const CareerGraphCanvas = forwardRef<CareerGraphCanvasHandle, Props>(
  function CareerGraphCanvas(props, ref) {
    const containerRef = useRef<HTMLDivElement>(null);
    const graphRef = useRef<Graph | null>(null);
    const callbackRef = useRef(props.onNodeSelect);
    const previousSelectedId = useRef<string | undefined>(undefined);
    callbackRef.current = props.onNodeSelect;
    const positions = useMemo(() => neighborhoodPositions(props.payload), [props.payload]);

    useImperativeHandle(ref, () => ({
      fit: () => { void graphRef.current?.fitView({ when: "always" }); },
      focus: (id) => { void graphRef.current?.focusElement(id, { duration: 350, easing: "ease-in-out" }); },
      zoomIn: () => { void graphRef.current?.zoomBy(1.2); },
      zoomOut: () => { void graphRef.current?.zoomBy(0.82); },
    }), []);

    useEffect(() => {
      const container = containerRef.current;
      if (!container) return;
      const graph = new Graph({
        container,
        autoResize: true,
        animation: true,
        padding: 64,
        data: { nodes: [], edges: [], combos: [] },
        node: {
          type: "rect",
          style: {
            size: (datum: any) => {
              const kind = String(datum.data?.kind ?? "");
              if (kind === "company") return [126, 44];
              if (kind === "job") return [142, 40];
              return [112, 34];
            },
            x: (datum: any) => Number(datum.style?.x ?? datum.data?.x ?? 0),
            y: (datum: any) => Number(datum.style?.y ?? datum.data?.y ?? 0),
            fill: (datum: any) => {
              if (datum.data?.kind === "company") return "#fff1e8";
              if (datum.data?.kind === "job") return datum.data?.processed ? "#eaf2ff" : "#f1f4f8";
              return `${String(datum.data?.color ?? "#7155bd")}22`;
            },
            stroke: (datum: any) => String(datum.data?.color ?? "#64748b"),
            lineWidth: (datum: any) => datum.data?.focused ? 3.5 : 1.5,
            radius: (datum: any) => datum.data?.kind === "job" ? 10 : 7,
            labelText: (datum: any) => String(datum.data?.label ?? ""),
            labelFill: "#26364d",
            labelFontSize: (datum: any) => datum.data?.kind === "job" ? 10 : 9,
            labelFontWeight: (datum: any) => datum.data?.kind === "company" ? 700 : 550,
            labelPlacement: "center",
            labelMaxWidth: (datum: any) => datum.data?.kind === "job" ? 130 : 112,
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
          type: "line",
          style: {
            stroke: (datum: any) => datum.data?.edgeType === "POSTED_BY" ? "#e8a278" : "#9bafd0",
            lineWidth: (datum: any) => datum.data?.edgeType === "POSTED_BY" ? 1.8 : 1.1,
            opacity: (datum: any) => datum.data?.edgeType === "POSTED_BY" ? 0.8 : 0.55,
            lineDash: (datum: any) => datum.data?.edgeType === "POSTED_BY" ? [5, 4] : undefined,
            endArrow: false,
          },
        },
        behaviors: ["drag-canvas", "zoom-canvas", "drag-element", "click-select"],
      });
      graphRef.current = graph;
      graph.on("node:click", (event: any) => callbackRef.current(String(event.target.id)));
      return () => {
        graph.destroy();
        if (graphRef.current === graph) graphRef.current = null;
      };
    }, []);

    useEffect(() => {
      const graph = graphRef.current;
      if (!graph) return;
      let cancelled = false;
      const timers: number[] = [];
      const frame = window.requestAnimationFrame(() => {
        if (cancelled || graphRef.current !== graph) return;
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
        graph.setData(data);
        void graph.render();
        [160, 520, 950].forEach((delay) => {
          timers.push(window.setTimeout(() => {
            if (!cancelled && graphRef.current === graph) void graph.fitView({ when: "always" });
          }, delay));
        });
        timers.push(window.setTimeout(() => {
          if (cancelled || graphRef.current !== graph) return;
          const visibleIds = new Set(props.payload.nodes.map((node) => node.id));
          const previousId = previousSelectedId.current;
          if (previousId && previousId !== props.selectedId && visibleIds.has(previousId)) {
            void graph.setElementState(previousId, []);
          }
          if (props.selectedId && visibleIds.has(props.selectedId)) {
            void graph.setElementState(props.selectedId, "selected");
          }
          previousSelectedId.current = props.selectedId;
        }, 220));
      });
      return () => {
        cancelled = true;
        window.cancelAnimationFrame(frame);
        timers.forEach((timer) => window.clearTimeout(timer));
      };
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

    return <div className="graph-canvas" ref={containerRef} aria-label="职业属性关联图谱" />;
  },
);
