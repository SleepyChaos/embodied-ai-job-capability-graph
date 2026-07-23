import { useMemo, useState } from "react";

import type { CareerSpectrumDirection, CareerSpectrumJob } from "../types";

type Props = {
  directions: CareerSpectrumDirection[];
  jobs: CareerSpectrumJob[];
  selectedId?: number;
  onSelect: (jobId: number) => void;
  onOpenCareer: (jobId: number) => void;
};

type PositionedJob = CareerSpectrumJob & {
  x: number;
  y: number;
  radius: number;
};

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, value));
}

function truncate(value: string, length: number) {
  return value.length > length ? `${value.slice(0, length)}…` : value;
}

function buildPositions(directions: CareerSpectrumDirection[], jobs: CareerSpectrumJob[]) {
  const positioned: PositionedJob[] = [];
  directions.forEach((direction) => {
    const group = jobs.filter((job) => job.directionId === direction.id);
    const radius = clamp(33 - Math.sqrt(group.length) * 2.7, 13, 30);
    const spacing = radius * 2 + 13;
    const angle = -Math.PI / 2 + (direction.sortOrder - 1) * Math.PI / 3;
    const radialX = Math.cos(angle);
    const radialY = Math.sin(angle);
    const tangentX = -radialY;
    const tangentY = radialX;
    let jobIndex = 0;
    for (let row = 0; jobIndex < group.length; row += 1) {
      const rowCount = row + 1;
      for (let column = 0; column < rowCount && jobIndex < group.length; column += 1) {
        const radialDistance = 86 + radius + row * spacing * 0.86;
        const lateralDistance = (column - row / 2) * spacing * 0.96;
        positioned.push({
          ...group[jobIndex]!,
          radius,
          x: radialX * radialDistance + tangentX * lateralDistance,
          y: radialY * radialDistance + tangentY * lateralDistance,
        });
        jobIndex += 1;
      }
    }
  });

  // Resolve rare cross-sector collisions while preserving the deterministic seed positions.
  for (let iteration = 0; iteration < 28; iteration += 1) {
    for (let left = 0; left < positioned.length; left += 1) {
      for (let right = left + 1; right < positioned.length; right += 1) {
        const a = positioned[left]!;
        const b = positioned[right]!;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const distance = Math.max(0.001, Math.hypot(dx, dy));
        const minimum = a.radius + b.radius + 7;
        if (distance >= minimum) continue;
        const push = (minimum - distance) / 2;
        const unitX = dx / distance;
        const unitY = dy / distance;
        a.x -= unitX * push;
        a.y -= unitY * push;
        b.x += unitX * push;
        b.y += unitY * push;
      }
    }
  }
  return positioned;
}

export function CareerSpectrumCanvas(props: Props) {
  const [hoveredId, setHoveredId] = useState<number | undefined>(undefined);
  const positions = useMemo(
    () => buildPositions(props.directions, props.jobs),
    [props.directions, props.jobs],
  );
  const focusId = hoveredId ?? props.selectedId;
  const focused = positions.find((job) => job.id === focusId);
  const extent = Math.max(
    420,
    ...positions.map((job) => Math.hypot(job.x, job.y) + job.radius + 120),
  );
  const ordered = [...positions].sort((left, right) => {
    if (left.id === focusId) return 1;
    if (right.id === focusId) return -1;
    return left.id - right.id;
  });

  const displayPoint = (job: PositionedJob) => {
    if (!focused || job.id === focused.id) return { x: job.x, y: job.y };
    const dx = job.x - focused.x;
    const dy = job.y - focused.y;
    const distance = Math.max(0.001, Math.hypot(dx, dy));
    const influence = Math.max(150, focused.radius * 5.4);
    if (distance >= influence) return { x: job.x, y: job.y };
    const push = (influence - distance) * 0.48;
    return {
      x: job.x + dx / distance * push,
      y: job.y + dy / distance * push,
    };
  };

  return (
    <svg
      className="career-spectrum-canvas"
      viewBox={`${-extent} ${-extent} ${extent * 2} ${extent * 2}`}
      role="img"
      aria-label="职业色系谱六方向蜂窝分布"
    >
      <defs>
        <filter id="spectrum-glow" x="-80%" y="-80%" width="260%" height="260%">
          <feGaussianBlur stdDeviation="8" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>
      <g className="spectrum-sectors" aria-hidden="true">
        {props.directions.map((direction) => {
          const angle = -Math.PI / 2 + (direction.sortOrder - 1) * Math.PI / 3;
          const leftAngle = angle - Math.PI / 6;
          const rightAngle = angle + Math.PI / 6;
          const outer = extent * 0.72;
          const labelRadius = extent * 0.82;
          return (
            <g key={direction.id}>
              <path
                d={`M 0 0 L ${Math.cos(leftAngle) * outer} ${Math.sin(leftAngle) * outer} L ${Math.cos(rightAngle) * outer} ${Math.sin(rightAngle) * outer} Z`}
                fill={direction.color}
                stroke={direction.color}
              />
              <text
                x={Math.cos(angle) * labelRadius}
                y={Math.sin(angle) * labelRadius}
                fill={direction.color}
                textAnchor="middle"
                dominantBaseline="middle"
              >
                <tspan>{direction.name}</tspan>
                <tspan x={Math.cos(angle) * labelRadius} dy="15">{direction.count} 条 JD</tspan>
              </text>
            </g>
          );
        })}
        <polygon points="-28,-16 0,-32 28,-16 28,16 0,32 -28,16" className="spectrum-center-hex" />
      </g>
      <g className="spectrum-jobs">
        {ordered.map((job) => {
          const point = displayPoint(job);
          const active = job.id === focusId;
          const selected = job.id === props.selectedId;
          const displayRadius = active ? job.radius * 1.56 : job.radius;
          return (
            <g
              key={job.id}
              className={`spectrum-job${active ? " active" : ""}${selected ? " selected" : ""}`}
              style={{ transform: `translate(${point.x}px, ${point.y}px)` }}
              role="button"
              tabIndex={0}
              aria-label={`${job.title}，${job.company ?? "企业待补充"}，${job.subDirectionName}`}
              onMouseEnter={() => setHoveredId(job.id)}
              onMouseLeave={() => setHoveredId(undefined)}
              onFocus={() => setHoveredId(job.id)}
              onBlur={() => setHoveredId(undefined)}
              onClick={() => props.onSelect(job.id)}
              onDoubleClick={(event) => {
                event.preventDefault();
                props.onOpenCareer(job.id);
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter") props.onSelect(job.id);
              }}
            >
              {active ? <circle r={displayRadius * 1.28} fill={job.color} opacity=".12" filter="url(#spectrum-glow)" /> : null}
              <circle
                className="spectrum-job-disc"
                r={displayRadius}
                fill={job.color}
                fillOpacity={active ? 0.76 : 0.92}
                stroke={selected ? "#f59e0b" : "#ffffff"}
                strokeWidth={selected ? 4 : 2}
              />
              <text className="spectrum-job-label" textAnchor="middle" dominantBaseline="middle">
                <tspan className="job-title" x="0" dy={active ? "-11" : "0"}>
                  {truncate(job.title, active ? 14 : job.radius < 18 ? 3 : 7)}
                </tspan>
                {active ? (
                  <>
                    <tspan className="job-company" x="0" dy="15">{truncate(job.company ?? "企业待补充", 15)}</tspan>
                    <tspan className="job-category" x="0" dy="13">{job.subDirectionName}</tspan>
                  </>
                ) : null}
              </text>
            </g>
          );
        })}
      </g>
    </svg>
  );
}
