"use client";

import * as d3 from "d3";
import { useEffect, useMemo, useRef, useState } from "react";
import { useChartDimensions } from "@/hooks/useChartDimensions";
import {
  transformToHierarchy,
  getPositiveSortedSpenders,
  getOfficeBounds,
  getDefaultRange,
  type RaceNode,
  type CandidateNode,
  type SpendingLeaf,
  type CandidatesByOffice,
  type DollarRange,
} from "@/utils/transformToHierarchy";
import ChartBreadcrumb from "./ChartBreadcrumb";
import CandidateRangeSlider from "./CandidateRangeSlider";
import type { OfficeCode } from "@/types/spending";
import type {
  SpendingNode,
  PackNode,
  OfficeSizeDatum,
} from "./SpendingPackChart.types";
import {
  partyClass,
  officeClass,
  spendingClass,
  setNodeValue,
  wrapLabel,
} from "./SpendingPackChart.utils";

interface SpendingPackChartProps {
  data: CandidatesByOffice;
}

export default function SpendingPackChart({ data }: SpendingPackChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const [breadcrumbPath, setBreadcrumbPath] = useState<string[]>(["All Races"]);
  const [activeRange, setActiveRange] = useState<{
    office: OfficeCode;
    range: DollarRange;
  } | null>(null);
  const [focusDepth, setFocusDepth] = useState(0);

  // Refs let handleNavigate reach into the live D3 state.
  const packRootRef = useRef<PackNode | null>(null);
  const focusRef = useRef<PackNode | null>(null);
  const zoomFnRef = useRef<
    ((target: PackNode, opts?: { animate?: boolean }) => void) | null
  >(null);

  const { width, height } = useChartDimensions(containerRef);

  const hierarchy = useMemo(
    () => transformToHierarchy(data, activeRange ?? undefined),
    [data, activeRange],
  );

  useEffect(() => {
    if (!width || !height || !svgRef.current) return;

    // Capture the user's current focus path before tearing down.
    const priorPath = focusRef.current
      ? focusRef.current
          .ancestors()
          .reverse()
          .map((n) => n.data.name)
      : ["root"];

    const svg = d3.select(svgRef.current);
    svg.interrupt("chart-zoom");
    svg.selectAll("*").remove();

    const root = d3
      .hierarchy<SpendingNode>(hierarchy)
      .sum((d) => ("value" in d ? d.value : 0))
      .sort((a, b) => (b.value ?? 0) - (a.value ?? 0));

    // Size each office bubble purely by its true total spending, like a single leaf.
    const sizingRoot = d3
      .hierarchy<OfficeSizeDatum>({
        name: "root",
        code: "P",
        value: 0,
        children: (hierarchy.children as RaceNode[]).map((r) => ({
          name: r.name,
          code: r.code,
          value: r.trueTotal,
        })),
      })
      .sum((d) => d.value)
      .sort((a, b) => (b.value ?? 0) - (a.value ?? 0));

    d3
      .pack<OfficeSizeDatum>()
      .size([width, height] as [number, number])
      .padding(3)(sizingRoot);
    const sizedOffices =
      sizingRoot as d3.HierarchyCircularNode<OfficeSizeDatum>;

    const packRoot = root as PackNode;
    packRoot.x = sizedOffices.x;
    packRoot.y = sizedOffices.y;
    packRoot.r = sizedOffices.r;

    // For each office, pack only its currently visible candidates so the reclaimed
    // space is not left empty.
    packRoot.children?.forEach((officeNodeRaw) => {
      const officeNode = officeNodeRaw as PackNode;
      const officeData = officeNode.data as RaceNode;
      const sized = sizedOffices.children?.find(
        (c) => c.data.code === officeData.code,
      );
      if (!sized) return;

      officeNode.x = sized.x;
      officeNode.y = sized.y;
      officeNode.r = sized.r;
      setNodeValue(officeNode, officeData.trueTotal); // display value only

      if (!officeNode.children || officeNode.children.length === 0) return;

      const subRoot = d3
        .hierarchy<SpendingNode>(officeData)
        .sum((d) => ("value" in d ? d.value : 0))
        .sort((a, b) => (b.value ?? 0) - (a.value ?? 0));

      const diameter = officeNode.r * 2;
      d3.pack<SpendingNode>().size([diameter, diameter]).padding(3)(subRoot);
      const packedSub = subRoot as PackNode;

      const dx = officeNode.x - packedSub.x;
      const dy = officeNode.y - packedSub.y;

      const byData = new Map<SpendingNode, PackNode>();
      officeNode
        .descendants()
        .forEach((d) => byData.set(d.data, d as PackNode));

      packedSub.descendants().forEach((d) => {
        if (d === packedSub) return; // office node itself — already positioned above
        const target = byData.get(d.data);
        if (!target) return;
        target.x = d.x + dx;
        target.y = d.y + dy;
        target.r = d.r;
      });
    });

    packRootRef.current = packRoot;

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
      .attr("class", (d) => {
        if (d.depth === 1) return officeClass((d.data as RaceNode).name);
        if (d.depth === 2) return partyClass((d.data as CandidateNode).party);
        if (d.depth === 3) return spendingClass((d.data as SpendingLeaf).name);
        return null;
      })
      .attr("stroke", "none")
      .attr("cursor", (d) => (d.children ? "pointer" : "default"))
      .on("click", (event, d) => {
        if (d.children) {
          zoomTo(d);
          event.stopPropagation();
        }
      });

    const label = svg
      .append("g")
      .selectAll<SVGTextElement, PackNode>("text")
      .data(
        packRoot
          .descendants()
          .filter((d) => d.depth === 1 || d.depth === 2 || d.depth === 3),
      )
      .join("text")
      .attr("text-anchor", "middle")
      .attr("pointer-events", "none")
      .attr("fill", "var(--color-ink)");

    wrapLabel(label);

    // Click background to go up one level
    svg.on("click", () => {
      const focused = focusRef.current;
      if (focused?.parent) zoomTo(focused.parent as PackNode);
    });

    function setView(v: [number, number, number]) {
      view = v;
      const k = Math.min(width, height) / v[2];
      const translate = (d: PackNode) =>
        `translate(${(d.x - v[0]) * k + width / 2},${(d.y - v[1]) * k + height / 2})`;

      // Only update visible layer
      const activeDepth = (focusRef.current?.depth ?? -1) + 1;
      const visibleNode = node.filter((d) => d.depth === activeDepth);
      const visibleLabel = label.filter((d) => d.depth === activeDepth);

      visibleNode.attr("transform", translate).attr("r", (d) => d.r * k);
      visibleLabel
        .attr("transform", translate)
        .attr("font-size", (d) => Math.max(0, Math.min(d.r * k * 0.25, 16)));
    }

    function isVisibleUnder(d: PackNode, target: PackNode): boolean {
      let cur: PackNode | null = d;
      while (cur) {
        if (cur === target) return true;
        cur = cur.parent as PackNode | null;
      }
      return false;
    }

    function updateVisibility(target: PackNode) {
      const activeDepth = target.depth + 1;
      const isActive = (d: PackNode) =>
        d.depth === activeDepth && isVisibleUnder(d, target);
      node
        .attr("opacity", (d) => (isActive(d) ? 0.7 : 0))
        .attr("pointer-events", (d) => {
          if (!isActive(d)) return "none";
          if (d.children) return "all";
          return "visiblePainted";
        });
      label.attr("opacity", (d) => (isActive(d) ? 1 : 0));
    }

    function zoomTo(target: PackNode, opts: { animate?: boolean } = {}) {
      focusRef.current = target;
      updateVisibility(target);
      setFocusDepth(target.depth);

      const rawPath = target
        .ancestors()
        .reverse()
        .map((n) => n.data.name);
      const displayPath = rawPath.map((n) => (n === "root" ? "All Races" : n));
      setBreadcrumbPath(displayPath);

      // Only clear a customized range when navigating away from its office.
      const targetOffice =
        target.depth === 0
          ? undefined
          : (
              target.ancestors().find((n) => n.depth === 1)?.data as
                | RaceNode
                | undefined
            )?.code;
      const clearRangeIfLeavingOffice = () =>
        setActiveRange((prev) =>
          prev && prev.office === targetOffice ? prev : null,
        );

      const targetView: [number, number, number] = [
        target.x,
        target.y,
        target.r * 2,
      ];

      if (opts.animate === false) {
        setView(targetView);
        clearRangeIfLeavingOffice();
        return;
      }

      const from = [...view] as [number, number, number];
      d3.select(svgRef.current)
        .transition("chart-zoom")
        .duration(750)
        .ease(d3.easeCubicInOut)
        .tween("zoom", () => {
          const i = d3.interpolate(from, targetView);
          return (t: number) => setView(i(t) as [number, number, number]);
        })
        .on("end", clearRangeIfLeavingOffice);
    }

    zoomFnRef.current = zoomTo;

    // Walk the prior focus path down the freshly-built tree, falling back to
    // the deepest ancestor that still exists (e.g. root, or the office level).
    let matched: PackNode = packRoot;
    for (let depth = 1; depth < priorPath.length; depth++) {
      const next = matched.children?.find(
        (c) => c.data.name === priorPath[depth],
      ) as PackNode | undefined;
      if (!next) break;
      matched = next;
    }
    zoomTo(matched, { animate: false });
  }, [hierarchy, width, height, data]);

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

  const focusedOfficeCode =
    focusDepth === 1
      ? (focusRef.current?.data as RaceNode | undefined)?.code
      : undefined;
  const officeSpends = useMemo(
    () =>
      focusedOfficeCode
        ? getPositiveSortedSpenders(data[focusedOfficeCode] ?? []).map(
            (c) => c.total_spending ?? 0,
          )
        : [],
    [data, focusedOfficeCode],
  );
  const officeBounds = useMemo(
    () =>
      focusedOfficeCode
        ? getOfficeBounds(
            getPositiveSortedSpenders(data[focusedOfficeCode] ?? []),
          )
        : null,
    [data, focusedOfficeCode],
  );
  const currentRange = useMemo(() => {
    if (!focusedOfficeCode) return null;
    if (activeRange && activeRange.office === focusedOfficeCode) {
      return activeRange.range;
    }
    return getDefaultRange(
      getPositiveSortedSpenders(data[focusedOfficeCode] ?? []),
    );
  }, [data, focusedOfficeCode, activeRange]);

  const showSlider = Boolean(
    focusDepth === 1 && focusedOfficeCode && officeBounds && currentRange,
  );

  return (
    <div className="w-full mx-auto max-w-200 py-4">
      <ChartBreadcrumb path={breadcrumbPath} onNavigate={handleNavigate} />
      <div
        ref={containerRef}
        className="w-[88%] mx-auto"
        style={{ aspectRatio: "1 / 1" }}
      >
        <svg ref={svgRef} width={width} height={height} />
      </div>
      {showSlider && focusedOfficeCode && officeBounds && currentRange && (
        <div className="flex justify-center w-full mt-3">
          <div className="w-[45%] max-w-65">
            <CandidateRangeSlider
              key={focusedOfficeCode}
              bounds={officeBounds}
              value={currentRange}
              candidateSpends={officeSpends}
              onCommit={(range) =>
                setActiveRange({ office: focusedOfficeCode, range })
              }
            />
          </div>
        </div>
      )}
    </div>
  );
}
