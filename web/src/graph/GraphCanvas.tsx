import { select } from "d3-selection";
import { zoom, zoomIdentity, type ZoomTransform } from "d3-zoom";
import { useEffect, useRef, useState } from "react";
import type { GraphNode, Snapshot } from "../api/types";
import { NO_HIGHLIGHT, paint, stillGrowing, type Highlight } from "./draw";
import { displayName, KIND_NAMES } from "./kinds";
import { GraphLayout, type LaidNode } from "./layout";
import "./graph.css";

interface Props {
  snapshot: Snapshot | null;
  highlight?: Highlight;
  interactive?: boolean;
  labels?: boolean;
  onSelect?: (node: GraphNode) => void;
  className?: string;
  ariaLabel: string;
  reserveBottom?: number;
  stretch?: number;
}

interface Hover {
  node: LaidNode;
  left: number;
  top: number;
}

// The range that holds all but the farthest 2% of values on each side, so stragglers do not shrink the view
function spread(values: number[]): [number, number] {
  const sorted = [...values].sort((a, b) => a - b);
  const cut = Math.floor(sorted.length * 0.02);
  return [sorted[cut], sorted[sorted.length - 1 - cut]];
}

// The transform that fits every node inside the canvas with some air around it
function fitTransform(nodes: LaidNode[], width: number, fullHeight: number, reserveBottom: number): ZoomTransform {
  const height = Math.max(120, fullHeight - reserveBottom);
  if (nodes.length === 0) return zoomIdentity.translate(width / 2, height / 2);
  const [minX, maxX] = spread(nodes.map((node) => node.x ?? 0));
  const [minY, maxY] = spread(nodes.map((node) => node.y ?? 0));
  const scale = Math.min(3.5, 0.9 * Math.min(width / (maxX - minX + 40), height / (maxY - minY + 40)));
  return zoomIdentity
    .translate(width / 2, height / 2)
    .scale(scale)
    .translate(-(minX + maxX) / 2, -(minY + maxY) / 2);
}

// A live FalkorDB graph on a canvas: grows as snapshots arrive, lights up what the agent touched
export function GraphCanvas(props: Props) {
  const { snapshot, highlight = NO_HIGHLIGHT, interactive = false, labels = false } = props;
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const layoutRef = useRef<GraphLayout | null>(null);
  const viewRef = useRef({ transform: zoomIdentity, manual: false, width: 0, height: 0, reserveBottom: props.reserveBottom ?? 0 });
  const stateRef = useRef({ highlight, hovered: null as string | null, labels });
  const frameRef = useRef(0);
  const [hover, setHover] = useState<Hover | null>(null);

  // Schedules one repaint on the next animation frame
  const requestDraw = useRef(() => {
    if (frameRef.current) return;
    frameRef.current = requestAnimationFrame(() => {
      frameRef.current = 0;
      draw();
    });
  }).current;

  // Paints the current layout with the current view
  function draw(): void {
    const canvas = canvasRef.current;
    const layout = layoutRef.current;
    if (!canvas || !layout) return;
    const context = canvas.getContext("2d");
    if (!context) return;
    const view = viewRef.current;
    if (!view.manual) view.transform = fitTransform(layout.nodes, view.width, view.height, view.reserveBottom);
    const ratio = window.devicePixelRatio || 1;
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, view.width, view.height);
    context.translate(view.transform.x, view.transform.y);
    context.scale(view.transform.k, view.transform.k);
    const now = performance.now();
    const { highlight: lit, hovered, labels: named } = stateRef.current;
    paint({ context, nodes: layout.nodes, edges: layout.edges, highlight: lit, hovered, scale: view.transform.k, now, labels: named });
    if (stillGrowing(layout.nodes, now)) requestDraw();
  }

  useEffect(() => {
    layoutRef.current = new GraphLayout(requestDraw, props.stretch);
    return () => layoutRef.current?.stop();
  }, [requestDraw, props.stretch]);

  useEffect(() => {
    if (snapshot) layoutRef.current?.update(snapshot);
    requestDraw();
  }, [snapshot, requestDraw]);

  useEffect(() => {
    stateRef.current = { ...stateRef.current, highlight, labels };
    requestDraw();
  }, [highlight, labels, requestDraw]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      const ratio = window.devicePixelRatio || 1;
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
      viewRef.current = { ...viewRef.current, width, height };
      requestDraw();
    });
    observer.observe(canvas);
    return () => observer.disconnect();
  }, [requestDraw]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !interactive) return;
    const behaviour = zoom<HTMLCanvasElement, unknown>()
      .scaleExtent([0.2, 8])
      .on("zoom", (event) => {
        if (event.sourceEvent) viewRef.current.manual = true;
        viewRef.current.transform = event.transform;
        requestDraw();
      });
    const selection = select(canvas);
    selection.call(behaviour).on("dblclick.zoom", () => {
      viewRef.current.manual = false;
      requestDraw();
    });
    behaviour.transform(selection, viewRef.current.transform);
    return () => {
      selection.on(".zoom", null);
    };
  }, [interactive, requestDraw]);

  // The node under the pointer, in layout coordinates
  function nodeAt(event: React.PointerEvent<HTMLCanvasElement>): LaidNode | undefined {
    const rect = event.currentTarget.getBoundingClientRect();
    const [x, y] = viewRef.current.transform.invert([event.clientX - rect.left, event.clientY - rect.top]);
    return layoutRef.current?.find(x, y);
  }

  // Shows the card for the node under the pointer
  function onPointerMove(event: React.PointerEvent<HTMLCanvasElement>): void {
    if (!interactive) return;
    const node = nodeAt(event);
    stateRef.current.hovered = node?.id ?? null;
    const rect = event.currentTarget.getBoundingClientRect();
    setHover(node ? { node, left: event.clientX - rect.left, top: event.clientY - rect.top } : null);
    requestDraw();
  }

  // Hands the clicked node to the parent
  function onClick(event: React.PointerEvent<HTMLCanvasElement>): void {
    const node = interactive ? nodeAt(event) : undefined;
    if (node && props.onSelect) props.onSelect(node.node);
  }

  return (
    <div className={`graph ${props.className ?? ""}`}>
      <canvas
        ref={canvasRef}
        role="img"
        aria-label={props.ariaLabel}
        className={interactive ? "graph-canvas is-interactive" : "graph-canvas"}
        onPointerMove={onPointerMove}
        onPointerLeave={() => {
          stateRef.current.hovered = null;
          setHover(null);
          requestDraw();
        }}
        onClick={onClick}
      />
      {hover && (
        <div className="graph-card" style={{ left: hover.left, top: hover.top }}>
          <strong>{displayName(hover.node.node)}</strong>
          <span>
            {KIND_NAMES[hover.node.kind]}
            {hover.node.node.status ? ` · ${hover.node.node.status}` : ""}
          </span>
          <code>{hover.node.id}</code>
        </div>
      )}
    </div>
  );
}
