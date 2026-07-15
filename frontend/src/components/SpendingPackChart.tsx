"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useChartDimensions } from "@/hooks/useChartDimensions";
import { transformToHierarchy } from "@/utils/transformToHierarchy";
import ChartBreadcrumb from "./ChartBreadcrumb";
import type { CandidateSpending } from "@/types/spending";

const THRESHOLD = 1_000_000;

interface SpendingPackChartProps {
  data: CandidateSpending[];
}

export default function SpendingPackChart({ data }: SpendingPackChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [zoomedNode, setZoomedNode] = useState<any>(null);
  const [breadcrumbPath, setBreadcrumbPath] = useState<string[]>([]);

  const { width, height } = useChartDimensions(containerRef);
  const hierarchy = useMemo(
    () => transformToHierarchy(data, THRESHOLD),
    [data],
  );

  // D3 pack layout + circle rendering — wired up when D3 is installed
  useEffect(() => {
    if (!width || !svgRef.current) return;
    // TODO: d3.hierarchy → d3.pack → draw circles
  }, [hierarchy, width, height]);

  // D3 zoom transition — wired up when D3 is installed
  useEffect(() => {
    if (!zoomedNode) return;
    // TODO: d3.interpolateZoom transition + sync breadcrumbPath
  }, [zoomedNode]);

  function handleNavigate(depth: number) {
    // TODO: walk zoomedNode.ancestors() to target depth
    void depth;
  }

  return (
    <div className="w-full mx-auto" style={{ maxWidth: "800px" }}>
      <ChartBreadcrumb path={breadcrumbPath} onNavigate={handleNavigate} />
      <div
        ref={containerRef}
        className="w-full"
        style={{ aspectRatio: "1 / 1" }}
      >
        <svg ref={svgRef} width={width} height={height} />
      </div>
    </div>
  );
}
