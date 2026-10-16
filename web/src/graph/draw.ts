import { displayName, KIND_STYLE } from "./kinds";
import type { LaidEdge, LaidNode } from "./layout";

export interface Highlight {
  focus: ReadonlySet<string>;
  alert: ReadonlySet<string>;
  tintOnly?: boolean;
}

export const NO_HIGHLIGHT: Highlight = { focus: new Set(), alert: new Set() };

const INK = "#1d1d1f";
const STEEL = "#86868b";
const HAIRLINE = "#d6d6d6";
const BLUE = "#0071e3";
const ORANGE = "#b64400";
const GROW_MS = 900;
const UNNAMED = new Set(["payment", "job", "claim"]);

interface Frame {
  context: CanvasRenderingContext2D;
  nodes: LaidNode[];
  edges: LaidEdge[];
  highlight: Highlight;
  hovered: string | null;
  scale: number;
  now: number;
  labels: boolean;
}

// The colour a node is drawn in once highlights are applied
function nodeColour(node: LaidNode, highlight: Highlight): string {
  if (highlight.alert.has(node.id)) return ORANGE;
  if (highlight.focus.has(node.id)) return BLUE;
  if (node.node.status === "refunded" || node.node.status === "defaulted") return ORANGE;
  if (node.kind === "job" || node.kind === "payment" || node.kind === "claim") return STEEL;
  return INK;
}

// How far a new node has grown in, from 0 to 1
function growth(node: LaidNode, now: number): number {
  const progress = Math.min(1, (now - node.bornAt) / GROW_MS);
  return 1 - Math.pow(1 - progress, 3);
}

// Draws every edge: hairlines, with the agent's path and the ring picked out
function drawEdges(frame: Frame, anyHighlight: boolean): void {
  const { context, edges, highlight } = frame;
  for (const edge of edges) {
    const { source, target } = edge;
    const focused = highlight.focus.has(source.id) && highlight.focus.has(target.id);
    const alerted = highlight.alert.has(source.id) && highlight.alert.has(target.id);
    context.globalAlpha = focused || alerted ? 0.95 : anyHighlight ? 0.25 : 0.7;
    context.strokeStyle = alerted ? ORANGE : focused ? BLUE : edge.type === "FUNDED_BY" ? STEEL : HAIRLINE;
    context.lineWidth = (focused || alerted ? 1.6 : 0.6) / frame.scale;
    context.setLineDash(edge.type === "IGNORED" || edge.type === "ABOUT" ? [3 / frame.scale, 3 / frame.scale] : []);
    context.beginPath();
    context.moveTo(source.x ?? 0, source.y ?? 0);
    context.lineTo(target.x ?? 0, target.y ?? 0);
    context.stroke();
  }
  context.setLineDash([]);
}

// Draws one node as a dot, or as a ring for wallets, claims and rings
function drawNode(frame: Frame, node: LaidNode, anyHighlight: boolean): void {
  const { context, highlight } = frame;
  const lit = highlight.focus.has(node.id) || highlight.alert.has(node.id);
  const grown = growth(node, frame.now);
  const radius = node.radius * (lit ? 1.25 : 1) * grown;
  const colour = nodeColour(node, highlight);
  context.globalAlpha = (anyHighlight && !lit ? 0.3 : 1) * grown;
  context.beginPath();
  context.arc(node.x ?? 0, node.y ?? 0, Math.max(radius, 0.1), 0, Math.PI * 2);
  if (KIND_STYLE[node.kind].hollow) {
    context.fillStyle = "#ffffff";
    context.fill();
    context.strokeStyle = colour;
    context.lineWidth = 1.4 / frame.scale;
    context.stroke();
  } else {
    context.fillStyle = colour;
    context.fill();
  }
  if (node.id === frame.hovered) {
    context.strokeStyle = BLUE;
    context.lineWidth = 2 / frame.scale;
    context.beginPath();
    context.arc(node.x ?? 0, node.y ?? 0, radius + 3 / frame.scale, 0, Math.PI * 2);
    context.stroke();
  }
}

// True when two label boxes overlap
function overlaps(a: number[], b: number[]): boolean {
  return a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3];
}

// The boxes of the nodes big enough that a label must not cover them
function nodeBoxes(nodes: LaidNode[]): number[][] {
  return nodes
    .filter((node) => node.radius >= 4)
    .map((node) => [
      (node.x ?? 0) - node.radius,
      (node.y ?? 0) - node.radius,
      (node.x ?? 0) + node.radius,
      (node.y ?? 0) + node.radius,
    ]);
}

// Writes names next to the nodes worth naming, highlighted ones first, skipping any that would collide
function drawLabels(frame: Frame, anyHighlight: boolean): void {
  const { context, nodes, highlight } = frame;
  const size = 11 / frame.scale;
  context.font = `500 ${size}px "SF Pro Text", -apple-system, "Inter Variable", sans-serif`;
  context.textBaseline = "middle";
  const isLit = (node: LaidNode) => highlight.focus.has(node.id) || highlight.alert.has(node.id);
  const named = (node: LaidNode) => KIND_STYLE[node.kind].label && (frame.labels || frame.scale > 1.4);
  const wanted = nodes.filter(
    (node) => node.id === frame.hovered || named(node) || (isLit(node) && !highlight.tintOnly && !UNNAMED.has(node.kind)),
  );
  wanted.sort((a, b) => Number(b.id === frame.hovered) - Number(a.id === frame.hovered) || Number(isLit(b)) - Number(isLit(a)));
  const placed = nodeBoxes(nodes);
  for (const node of wanted) {
    const text = displayName(node.node);
    const left = (node.x ?? 0) + node.radius * (isLit(node) ? 1.25 : 1) + 5 / frame.scale;
    const box = [left, (node.y ?? 0) - size * 0.7, left + context.measureText(text).width, (node.y ?? 0) + size * 0.7];
    if (placed.some((other) => overlaps(box, other))) continue;
    placed.push(box);
    context.globalAlpha = anyHighlight && !isLit(node) ? 0.35 : 1;
    context.fillStyle = isLit(node) ? nodeColour(node, highlight) : INK;
    context.fillText(text, left, node.y ?? 0);
  }
}

// Paints one frame of the graph
export function paint(frame: Frame): void {
  const anyHighlight = !frame.highlight.tintOnly && (frame.highlight.focus.size > 0 || frame.highlight.alert.size > 0);
  drawEdges(frame, anyHighlight);
  for (const node of frame.nodes) drawNode(frame, node, anyHighlight);
  drawLabels(frame, anyHighlight);
  frame.context.globalAlpha = 1;
}

// True while any node is still growing in, so the canvas keeps animating
export function stillGrowing(nodes: LaidNode[], now: number): boolean {
  return nodes.some((node) => now - node.bornAt < GROW_MS);
}
