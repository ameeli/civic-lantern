import type * as d3 from "d3";
import type {
  HierarchyRoot,
  RaceNode,
  CandidateNode,
  SpendingLeaf,
} from "@/utils/transformToHierarchy";
import type { OfficeCode } from "@/types/spending";

export type SpendingNode =
  HierarchyRoot | RaceNode | CandidateNode | SpendingLeaf;
export type PackNode = d3.HierarchyCircularNode<SpendingNode>;

/** A minimal leaf-only hierarchy used purely to size each office bubble by its
 * true total spending, decoupled from how many candidates are currently visible. */
export interface OfficeSizeDatum {
  name: string;
  code: OfficeCode;
  value: number;
  children?: OfficeSizeDatum[];
}
