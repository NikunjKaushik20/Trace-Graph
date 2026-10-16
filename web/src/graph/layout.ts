import {
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
  type Simulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from "d3-force";
import type { GraphNode, Snapshot } from "../api/types";
import { KIND_STYLE, kindOf, type NodeKind } from "./kinds";

export interface LaidNode extends SimulationNodeDatum {
  id: string;
  node: GraphNode;
  kind: NodeKind;
  radius: number;
  bornAt: number;
}

export interface LaidEdge extends SimulationLinkDatum<LaidNode> {
  type: string;
  source: LaidNode;
  target: LaidNode;
}

const LINK_DISTANCE: Record<string, number> = {
  FUNDED_BY: 26,
  OWNS: 30,
  MADE: 14,
  FOR: 22,
  FOR_JOB: 6,
  REPORTED: 40,
  WROTE: 10,
  ABOUT: 18,
  MEMBER: 24,
  COVERS: 20,
};

export class GraphLayout {
  readonly simulation: Simulation<LaidNode, LaidEdge>;
  nodes: LaidNode[] = [];
  edges: LaidEdge[] = [];
  private byId = new Map<string, LaidNode>();

  // Builds an idle simulation; nodes arrive through update. Stretch above 1 spreads the graph wider than tall
  constructor(onTick: () => void, stretch = 1) {
    this.simulation = forceSimulation<LaidNode, LaidEdge>()
      .force("charge", forceManyBody<LaidNode>().strength((d) => -14 - d.radius * 6))
      .force("collide", forceCollide<LaidNode>().radius((d) => d.radius + (KIND_STYLE[d.kind].label ? 12 : 1.5)))
      .force("x", forceX<LaidNode>(0).strength(0.035 / stretch))
      .force("y", forceY<LaidNode>(0).strength(0.05 * stretch))
      .alphaDecay(0.03)
      .on("tick", onTick);
  }

  // Merges a new snapshot in, keeping every known node where it already is
  update(snapshot: Snapshot): string[] {
    const now = performance.now();
    const fresh: string[] = [];
    const next = new Map<string, LaidNode>();
    for (const node of snapshot.nodes) {
      const known = this.byId.get(node.id);
      if (known) {
        known.node = node;
        next.set(node.id, known);
        continue;
      }
      const kind = kindOf(node);
      const born: LaidNode = { id: node.id, node, kind, radius: KIND_STYLE[kind].radius, bornAt: now };
      fresh.push(node.id);
      next.set(node.id, born);
    }
    this.byId = next;
    this.nodes = [...next.values()];
    this.edges = snapshot.edges.flatMap((edge) => {
      const source = next.get(edge.source);
      const target = next.get(edge.target);
      return source && target ? [{ source, target, type: edge.type }] : [];
    });
    this.placeNewcomers(fresh);
    this.simulation.nodes(this.nodes);
    this.simulation.force(
      "link",
      forceLink<LaidNode, LaidEdge>(this.edges)
        .distance((edge) => LINK_DISTANCE[edge.type] ?? 30)
        .strength(0.35),
    );
    this.simulation.alpha(fresh.length === this.nodes.length ? 1 : 0.35).restart();
    return fresh;
  }

  // Starts a new node next to a node it is linked to, so growth looks like growth
  private placeNewcomers(fresh: string[]): void {
    const freshSet = new Set(fresh);
    for (const edge of this.edges) {
      const [newcomer, anchor] = freshSet.has(edge.source.id)
        ? [edge.source, edge.target]
        : [edge.target, edge.source];
      if (!freshSet.has(newcomer.id) || freshSet.has(anchor.id) || newcomer.x !== undefined) continue;
      newcomer.x = (anchor.x ?? 0) + (Math.random() - 0.5) * 20;
      newcomer.y = (anchor.y ?? 0) + (Math.random() - 0.5) * 20;
    }
  }

  // The node under a point in layout coordinates, if any
  find(x: number, y: number): LaidNode | undefined {
    let best: LaidNode | undefined;
    let bestDistance = Infinity;
    for (const node of this.nodes) {
      const distance = Math.hypot((node.x ?? 0) - x, (node.y ?? 0) - y);
      if (distance < node.radius + 6 && distance < bestDistance) {
        best = node;
        bestDistance = distance;
      }
    }
    return best;
  }

  // A node by id
  get(id: string): LaidNode | undefined {
    return this.byId.get(id);
  }

  // Stops the simulation for good
  stop(): void {
    this.simulation.stop();
  }
}
