import * as d3 from "d3";
import { formatDollars } from "@/utils/formatDollars";
import type { PackNode, SpendingNode } from "./SpendingPackChart.types";

export function partyClass(party: string | null): string {
  if (party === "DEM" || party === "DFL") return "fill-party-dem";
  if (party === "REP") return "fill-party-rep";
  return "fill-party-neutral";
}

export function officeClass(office: string): string {
  if (office === "House") return "fill-office-house";
  if (office === "Senate") return "fill-office-senate";
  if (office === "Presidential") return "fill-office-president";
  return "fill-party-neutral";
}

export function spendingClass(name: string): string {
  if (name === "Inside") return "fill-office-president";
  if (name === "Outside Oppose") return "fill-party-rep";
  if (name === "Outside Support") return "fill-office-house";
  return "fill-party-neutral";
}

export function spendingLabel(name: string): string {
  if (name === "Inside") return "Direct Campaign Spending";
  if (name === "Outside Support") return "Independent Support";
  if (name === "Outside Oppose") return "Independent Opposition";
  return name;
}

// Bypasses d3's HierarchyNode.value read-only restriction so office nodes can
// display their true total spending, independent of the pack-sizing pass.
export function setNodeValue(
  node: d3.HierarchyNode<SpendingNode>,
  value: number | undefined,
): void {
  (node as { value?: number }).value = value;
}

export function wrapWords(
  el: d3.Selection<SVGTextElement, unknown, null, undefined>,
  words: string[],
  maxWidth: number,
  virtualFontSize: number,
): string[] {
  const scratch = el.append("tspan").attr("font-size", virtualFontSize);
  const lines: string[] = [];
  let currentWords: string[] = [];
  for (const word of words) {
    const candidate = [...currentWords, word].join(" ");
    scratch.text(candidate);
    const width = scratch.node()?.getComputedTextLength() ?? 0;
    if (width > maxWidth && currentWords.length > 0) {
      lines.push(currentWords.join(" "));
      currentWords = [word];
    } else {
      currentWords.push(word);
    }
  }
  if (currentWords.length > 0) lines.push(currentWords.join(" "));
  scratch.remove();
  return lines;
}

export function wrapLabel(
  selection: d3.Selection<SVGTextElement, PackNode, SVGGElement, unknown>,
): void {
  selection.each(function (d) {
    const el = d3.select(this);
    el.text(null);

    const virtualFontSize = d.r * 0.25;
    const maxWidth = d.r * 1.6;

    const displayName =
      d.depth === 3 ? spendingLabel(d.data.name) : d.data.name;
    const nameLines = wrapWords(
      el,
      displayName.split(/\s+/).filter(Boolean),
      maxWidth,
      virtualFontSize,
    );

    const allLines = [
      {
        text: formatDollars(d.value ?? 0),
        class: "font-sans font-medium",
        sizeEm: 1.25,
      },
      ...nameLines.map((text) => ({
        text,
        class: "font-headline font-medium font-semibold",
        sizeEm: 1,
      })),
    ];
    const lineHeight = 1.1;
    const groupGap = 0.4;
    const totalSpan = (allLines.length - 1) * lineHeight + groupGap;
    const startDy = -totalSpan / 2;

    allLines.forEach((line, i) => {
      let dy = lineHeight;
      if (i === 0) dy = startDy;
      else if (i === 1) dy = lineHeight + groupGap;

      el.append("tspan")
        .attr("x", 0)
        .attr("dy", `${dy}em`)
        .attr("class", line.class)
        .attr("font-size", `${line.sizeEm}em`)
        .text(line.text);
    });
  });
}
