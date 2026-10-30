"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  MarkerType,
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  useNodesState,
  useEdgesState,
  useReactFlow,
  useStoreApi,
  type Node,
  type Edge,
  type EdgeProps,
} from "@xyflow/react";
import dagre from "@dagrejs/dagre";
import AccessNodeComponent, { type AccessNodeData } from "./AccessNode";
import type { AccessMapData, AccessEdgeRecord, AccessNodeRecord } from "@/data/serverSource";

import "@xyflow/react/dist/style.css";

const NODE_WIDTH = 220;
const NODE_HEIGHT = 78;
const ZOOM_DURATION = 300;

const nodeTypes = { accessNode: AccessNodeComponent };

function AccessEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style,
  markerEnd,
  label,
  data,
  interactionWidth,
}: EdgeProps) {
  const [path, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  });
  const findingId = (data as { findingId?: string | null } | undefined)?.findingId ?? null;
  const openFinding = (data as { openFinding?: (id: string) => void } | undefined)?.openFinding;

  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        markerEnd={markerEnd}
        style={style}
        interactionWidth={interactionWidth}
      />
      {label ? (
        <EdgeLabelRenderer>
          <button
            type="button"
            className="nodrag nopan pointer-events-auto absolute rounded border border-[#3f1515] bg-[#140606] px-1.5 py-0.5 text-[11px] font-medium text-[#fff1f2]"
            style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
            onClick={(event) => {
              event.stopPropagation();
              if (findingId && openFinding) openFinding(findingId);
            }}
          >
            {label}
          </button>
        </EdgeLabelRenderer>
      ) : null}
    </>
  );
}

const edgeTypes = { accessEdge: AccessEdge };

function findingIdOf(node: AccessNodeRecord): string | null {
  const sources = Array.isArray(node.sources) ? node.sources : [];
  const source = sources.find((item) => item.kind === "finding" && item.id);
  return source?.id ?? null;
}

function edgeCaption(edge: AccessEdgeRecord): string {
  const id = edge.finding_id || edge.coverage_id || "";
  return id ? `${edge.label} · ${id}` : edge.label;
}

const ORPHAN_GAP = 16;
const ORPHAN_COLUMN_GAP = 96;

function nodeFrom(asset: AccessNodeRecord): Node {
  const data: AccessNodeData = {
    label: asset.label,
    assetType: asset.type,
    inScope: asset.in_scope,
    findingId: findingIdOf(asset),
  };
  return {
    id: asset.id,
    type: "accessNode",
    position: { x: 0, y: 0 },
    data,
  };
}

function accessEdge(link: AccessEdgeRecord, openFinding: (id: string) => void): Edge {
  if (link.type === "contains") {
    return {
      id: link.id,
      source: link.source,
      target: link.target,
      focusable: false,
      interactionWidth: 0,
      style: { stroke: "#9a8a8a", strokeWidth: 1 },
    };
  }
  const proofGap = link.type === "proof_gap";
  const stroke = proofGap ? "#fca5a5" : "#ef4444";
  return {
    id: link.id,
    type: "accessEdge",
    source: link.source,
    target: link.target,
    label: edgeCaption(link),
    interactionWidth: 24,
    data: { findingId: link.finding_id, openFinding },
    style: {
      stroke,
      strokeWidth: 1.75,
      strokeDasharray: proofGap ? "6 4" : undefined,
    },
    labelStyle: { fill: "#fff1f2", fontSize: 11, fontWeight: 500 },
    labelBgStyle: { fill: "#140606", fillOpacity: 0.94 },
    labelBgPadding: [6, 3],
    labelBgBorderRadius: 4,
    markerEnd: { type: MarkerType.ArrowClosed, color: stroke, width: 18, height: 18 },
  };
}

function layoutMap(
  map: AccessMapData,
  openFinding: (id: string) => void
): { nodes: Node[]; edges: Edge[] } {
  const present = new Set(map.nodes.map((node) => node.id));
  const links = map.edges.filter((link) => present.has(link.source) && present.has(link.target));
  const linked = new Set<string>();
  for (const link of links) {
    linked.add(link.source);
    linked.add(link.target);
  }
  const connected = map.nodes.filter((node) => linked.has(node.id));
  const orphans = map.nodes.filter((node) => !linked.has(node.id));

  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "LR", nodesep: 48, ranksep: 96 });

  const nodes: Node[] = connected.map((asset) => nodeFrom(asset));
  const edges: Edge[] = links.map((link) => accessEdge(link, openFinding));

  for (const asset of connected) {
    g.setNode(asset.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }
  for (const link of links) {
    g.setEdge(link.source, link.target);
  }
  if (connected.length > 0) {
    dagre.layout(g);
  }

  let maxRight = 0;
  for (const node of nodes) {
    const pos = g.node(node.id);
    if (!pos) continue;
    node.position = {
      x: pos.x - NODE_WIDTH / 2,
      y: pos.y - NODE_HEIGHT / 2,
    };
    maxRight = Math.max(maxRight, node.position.x + NODE_WIDTH);
  }

  const orphanX = connected.length > 0 ? maxRight + ORPHAN_COLUMN_GAP : 0;
  orphans.forEach((asset, index) => {
    const node = nodeFrom(asset);
    node.position = { x: orphanX, y: index * (NODE_HEIGHT + ORPHAN_GAP) };
    nodes.push(node);
  });

  return { nodes, edges };
}

function MeasureNodes({ ids }: { ids: string }) {
  const store = useStoreApi();
  useEffect(() => {
    if (!ids) return undefined;
    const measure = () => {
      const { domNode, updateNodeInternals } = store.getState();
      if (!domNode) return;
      const updates = new Map<string, { id: string; nodeElement: HTMLDivElement; force: true }>();
      for (const id of ids.split("\n")) {
        if (!id) continue;
        const nodeElement = domNode.querySelector<HTMLDivElement>(
          `.react-flow__node[data-id="${id}"]`
        );
        if (nodeElement) updates.set(id, { id, nodeElement, force: true });
      }
      if (updates.size > 0) updateNodeInternals(updates);
    };
    const frame = requestAnimationFrame(measure);
    const timer = window.setTimeout(measure, 50);
    return () => {
      cancelAnimationFrame(frame);
      window.clearTimeout(timer);
    };
  }, [ids, store]);
  return null;
}

function FitAccess({ count }: { count: number }) {
  const { fitView } = useReactFlow();
  const fitted = useRef(false);
  useEffect(() => {
    if (count > 0 && !fitted.current) {
      fitted.current = true;
      const timer = setTimeout(() => fitView({ padding: 0.28, duration: 400 }), 60);
      return () => clearTimeout(timer);
    }
    return undefined;
  }, [count, fitView]);
  return null;
}

function SmoothControls() {
  const { zoomIn, zoomOut, fitView } = useReactFlow();
  return (
    <Controls
      position="bottom-right"
      showZoom={false}
      showFitView={false}
      showInteractive={false}
      className="!border-none !bg-transparent !shadow-none"
    >
      <div className="flex flex-col overflow-hidden rounded-lg border border-[#3f1515]">
        <button
          onClick={() => zoomIn({ duration: ZOOM_DURATION })}
          className="flex h-7 w-7 items-center justify-center bg-[#140606] text-white transition-colors hover:bg-[#2a1212]"
          title="Zoom in"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-3.5 w-3.5">
            <path d="M12 5v14M5 12h14" />
          </svg>
        </button>
        <button
          onClick={() => zoomOut({ duration: ZOOM_DURATION })}
          className="flex h-7 w-7 items-center justify-center border-y border-[#3f1515] bg-[#140606] text-white transition-colors hover:bg-[#2a1212]"
          title="Zoom out"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-3.5 w-3.5">
            <path d="M5 12h14" />
          </svg>
        </button>
        <button
          onClick={() => fitView({ padding: 0.28, duration: ZOOM_DURATION })}
          className="flex h-7 w-7 items-center justify-center bg-[#140606] text-white transition-colors hover:bg-[#2a1212]"
          title="Fit view"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-3.5 w-3.5">
            <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
          </svg>
        </button>
      </div>
    </Controls>
  );
}

interface AccessMapProps {
  map: AccessMapData;
  onOpenFinding: (id: string) => void;
}

export default function AccessMap({ map, onOpenFinding }: AccessMapProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const openFindingRef = useRef(onOpenFinding);
  openFindingRef.current = onOpenFinding;
  const openFinding = useCallback((id: string) => {
    openFindingRef.current(id);
  }, []);
  const signature = useMemo(
    () =>
      JSON.stringify({
        nodes: map.nodes.map((node) => [node.id, node.label, node.type, node.in_scope]),
        edges: map.edges.map((edge) => [
          edge.id,
          edge.type,
          edge.label,
          edge.finding_id,
          edge.source,
          edge.target,
        ]),
      }),
    [map]
  );

  useEffect(() => {
    if (map.nodes.length === 0) {
      setNodes([]);
      setEdges([]);
      return;
    }
    const laid = layoutMap(map, openFinding);
    setNodes(laid.nodes);
    setEdges(laid.edges);
    // `signature` already covers the map fields that change the layout.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature, openFinding, setNodes, setEdges]);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      const findingId = (node.data as AccessNodeData).findingId;
      if (findingId) onOpenFinding(findingId);
    },
    [onOpenFinding]
  );

  const onEdgeClick = useCallback(
    (_: React.MouseEvent, edge: Edge) => {
      const findingId = (edge.data as { findingId?: string | null } | undefined)?.findingId;
      if (findingId) onOpenFinding(findingId);
    },
    [onOpenFinding]
  );

  if (map.nodes.length === 0 && map.edges.length === 0) {
    return (
      <div className="flex h-full items-center justify-center px-6 text-center">
        <p className="text-sm text-[#888]">No devices or access paths recorded for this run yet.</p>
      </div>
    );
  }

  return (
    <div className="h-full" aria-label="Access map">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        onEdgeClick={onEdgeClick}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        nodesConnectable={false}
        edgesFocusable
        edgesReconnectable={false}
        minZoom={0.2}
        maxZoom={1.6}
        proOptions={{ hideAttribution: true }}
        className="bg-[#140606]"
      >
        <Background color="#3f1515" gap={20} />
        <MeasureNodes ids={nodes.map((node) => node.id).join("\n")} />
        <FitAccess count={nodes.length} />
        <SmoothControls />
        <MiniMap
          position="bottom-left"
          nodeColor={() => "#ef4444"}
          maskColor="rgba(20,6,6,0.82)"
          style={{ width: 80, height: 50 }}
          className="!border-[#3f1515] !bg-[#140606]"
        />
      </ReactFlow>
    </div>
  );
}
