"use client";

import * as d3 from "d3";
import { useEffect, useMemo, useRef, useState } from "react";
import { useChartDimensions } from "@/hooks/useChartDimensions";
import {
  transformToHierarchy,
  type HierarchyRoot,
  type RaceNode,
  type CandidateNode,
  type SpendingLeaf,
} from "@/utils/transformToHierarchy";
import ChartBreadcrumb from "./ChartBreadcrumb";
import type { CandidateSpending } from "@/types/spending";

const THRESHOLD = 1_000_000;

type SpendingNode = HierarchyRoot | RaceNode | CandidateNode | SpendingLeaf;
type PackNode = d3.HierarchyCircularNode<SpendingNode>;

interface SpendingPackChartProps {
  data: CandidateSpending[];
}

export default function SpendingPackChart({ data }: SpendingPackChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const [breadcrumbPath, setBreadcrumbPath] = useState<string[]>(["All Races"]);

  // Refs let handleNavigate reach into the live D3 state
  const packRootRef = useRef<PackNode | null>(null);
  const focusRef = useRef<PackNode | null>(null);
  const zoomFnRef = useRef<((target: PackNode) => void) | null>(null);

  const { width, height } = useChartDimensions(containerRef);

  const hierarchy = useMemo(
    () => transformToHierarchy(data, THRESHOLD),
    [data],
  );

  useEffect(() => {
    if (!width || !height || !svgRef.current) return;

    setBreadcrumbPath(["All Races"]);

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const root = d3
      .hierarchy<SpendingNode>(hierarchy)
      .sum((d) => ("value" in d ? d.value : 0))
      .sort((a, b) => (b.value ?? 0) - (a.value ?? 0));

    d3
      .pack<SpendingNode>()
      .size([width, height] as [number, number])
      .padding(3)(root);

    const packRoot = root as PackNode;
    packRootRef.current = packRoot;
    focusRef.current = packRoot;

    let view: [number, number, number] = [
      packRoot.x,
      packRoot.y,
      packRoot.r * 2,
    ];

    const node = svg
      .append("g")
      .selectAll<SVGCircleElement, PackNode>("circle")
      .data(packRoot.descendants())
      .join("circle")
      .attr("fill", (d) => (d.children ? "none" : "currentColor"))
      .attr("stroke", (d) => (d.children ? "currentColor" : "none"))
      .attr("stroke-width", 1)
      .attr("opacity", (d) => (d.depth === 0 ? 0 : 0.7))
      .attr("cursor", (d) => (d.children ? "pointer" : "default"))
      .attr("pointer-events", (d) => {
        if (d.depth === 0) return "none";
        if (d.children) return "all";
        return "visiblePainted";
      })
      .on("click", (event, d) => {
        if (d.children) {
          zoomTo(d);
          event.stopPropagation();
        }
      });

    const label = svg
      .append("g")
      .selectAll<SVGTextElement, PackNode>("text")
      .data(packRoot.descendants().filter((d) => d.depth === 1 || d.depth === 2))
      .join("text")
      .attr("text-anchor", "middle")
      .attr("dominant-baseline", "middle")
      .attr("pointer-events", "none")
      .text((d) => d.data.name);

    // Click background to go up one level
    svg.on("click", () => {
      const focused = focusRef.current;
      if (focused?.parent) zoomTo(focused.parent as PackNode);
    });

    function setView(v: [number, number, number]) {
      view = v;
      const k = width / v[2];
      const translate = (d: PackNode) =>
        `translate(${(d.x - v[0]) * k + width / 2},${(d.y - v[1]) * k + height / 2})`;
      node
        .attr("transform", translate)
        .attr("r", (d) => d.r * k);
      label
        .attr("transform", translate)
        .attr("font-size", (d) => Math.max(0, Math.min(d.r * k * 0.25, 16)))
        .attr("opacity", (d) => (d.r * k < 20 ? 0 : 1));
    }

    function zoomTo(target: PackNode) {
      focusRef.current = target;

      const rawPath = target
        .ancestors()
        .reverse()
        .map((n) => n.data.name);
      const displayPath = rawPath.map((n) => (n === "root" ? "All Races" : n));
      setBreadcrumbPath(displayPath);

      const targetView: [number, number, number] = [
        target.x,
        target.y,
        target.r * 2,
      ];
      const from = [...view] as [number, number, number];

      d3.select(svgRef.current)
        .transition("chart-zoom")
        .duration(750)
        .ease(d3.easeCubicInOut)
        .tween("zoom", () => {
          const i = d3.interpolate(from, targetView);
          return (t: number) => setView(i(t) as [number, number, number]);
        });
    }

    zoomFnRef.current = zoomTo;
    setView(view);
  }, [hierarchy, width, height]);

  function handleNavigate(depth: number) {
    const focused = focusRef.current;
    const packRoot = packRootRef.current;
    const zoomTo = zoomFnRef.current;
    if (!focused || !packRoot || !zoomTo) return;

    if (depth === 0) {
      zoomTo(packRoot);
      return;
    }
    const ancestors = focused.ancestors().reverse();
    const target = ancestors[depth] as PackNode | undefined;
    if (target) zoomTo(target);
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
