"use client";

import { useState, useCallback, useMemo, useEffect } from "react";
import {
  ReactFlow,
  type Node,
  type Edge,
  Background,
  Controls,
  MarkerType,
  useNodesState,
  useEdgesState,
  Handle,
  Position,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dagre from "@dagrejs/dagre";

import type { KnowledgeGraph, KGNode, KGEdge } from "@/lib/types";

const NODE_W = 200;
const NODE_H = 60;

function layoutGraph(nodes: Node[], edges: Edge[]): Node[] {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", ranksep: 80, nodesep: 50 });
  nodes.forEach((n) => g.setNode(n.id, { width: NODE_W, height: NODE_H }));
  edges.forEach((e) => g.setEdge(e.source, e.target));
  dagre.layout(g);
  return nodes.map((n) => {
    const pos = g.node(n.id);
    return { ...n, position: { x: pos.x - NODE_W / 2, y: pos.y - NODE_H / 2 } };
  });
}

function EntityNode({ data }: { data: { label: string; description?: string; excluded: boolean; rowCount?: number; onClick: () => void } }) {
  return (
    <div
      onClick={data.onClick}
      title={data.description}
      className={`cursor-pointer rounded-md border px-3 py-2 text-xs shadow-sm transition-opacity ${
        data.excluded ? "border-dashed border-muted-foreground/40 bg-muted/30 opacity-50" : "border-border bg-card"
      }`}
      style={{ minWidth: NODE_W }}
    >
      <Handle type="target" position={Position.Top} className="!bg-muted-foreground !w-2 !h-2" />
      <div className="font-semibold text-sm">{data.label}</div>
      {data.rowCount !== undefined && (
        <div className="text-muted-foreground mt-0.5">{data.rowCount.toLocaleString()} rows</div>
      )}
      <Handle type="source" position={Position.Bottom} className="!bg-muted-foreground !w-2 !h-2" />
    </div>
  );
}

const nodeTypes = { entity: EntityNode };

interface KnowledgeGraphEditorProps {
  kg: KnowledgeGraph;
  onSave: (data: { name?: string; description?: string; content?: string; excluded_entities?: string[] }) => void;
  onRegenerate: () => void;
  isSaving: boolean;
  isRegenerating: boolean;
}

export function KnowledgeGraphEditor({ kg, onSave, onRegenerate, isSaving, isRegenerating }: KnowledgeGraphEditorProps) {
  const [tab, setTab] = useState<"graph" | "table" | "content">("graph");
  const [name, setName] = useState(kg.name);
  const [description, setDescription] = useState(kg.description ?? "");
  const [content, setContent] = useState(kg.content);
  const [excluded, setExcluded] = useState<Set<string>>(new Set(kg.excluded_entities ?? []));

  useEffect(() => {
    setName(kg.name);
    setDescription(kg.description ?? "");
    setContent(kg.content);
    setExcluded(new Set(kg.excluded_entities ?? []));
  }, [kg]);

  const toggleExclude = useCallback((entityId: string) => {
    setExcluded((prev) => {
      const next = new Set(prev);
      if (next.has(entityId)) next.delete(entityId);
      else next.add(entityId);
      return next;
    });
  }, []);

  const graphNodes = kg.graph_data?.nodes ?? [];
  const graphEdges = kg.graph_data?.edges ?? [];

  const { flowNodes, flowEdges } = useMemo(() => {
    const fNodes: Node[] = graphNodes.map((n: KGNode) => ({
      id: n.id,
      type: "entity",
      position: { x: 0, y: 0 },
      data: {
        label: n.label,
        description: n.description,
        excluded: excluded.has(n.id),
        rowCount: n.row_count,
        onClick: () => toggleExclude(n.id),
      },
    }));
    const fEdges: Edge[] = graphEdges
      .filter((e: KGEdge) => !excluded.has(e.source) && !excluded.has(e.target))
      .map((e: KGEdge) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        label: e.label,
        type: "default",
        animated: e.type === "m2m",
        markerEnd: { type: MarkerType.ArrowClosed, color: "#888" },
        style: { stroke: "#888", strokeWidth: 2 },
        labelStyle: { fontSize: 10, fill: "#888" },
      }));
    const laid = layoutGraph(fNodes, fEdges);
    return { flowNodes: laid, flowEdges: fEdges };
  }, [graphNodes, graphEdges, excluded, toggleExclude]);

  const [nodes, setNodes, onNodesChange] = useNodesState(flowNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(flowEdges);

  useEffect(() => {
    setNodes(flowNodes);
    setEdges(flowEdges);
  }, [flowNodes, flowEdges, setNodes, setEdges]);

  const handleSave = () => {
    onSave({
      name: name !== kg.name ? name : undefined,
      description: description !== (kg.description ?? "") ? description : undefined,
      content: content !== kg.content ? content : undefined,
      excluded_entities: [...excluded],
    });
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-sm font-medium">Name</label>
          <input
            className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div>
          <label className="text-sm font-medium">Mode</label>
          <input
            className="mt-1 w-full rounded-md border border-input bg-muted px-3 py-2 text-sm"
            value={kg.generation_mode.replace(/_/g, " ")}
            disabled
          />
        </div>
      </div>
      <div>
        <label className="text-sm font-medium">Description</label>
        <input
          className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Optional description"
        />
      </div>

      <div className="flex gap-1 border-b">
        {(["graph", "table", "content"] as const).map((t) => (
          <button
            key={t}
            className={`px-3 py-1.5 text-sm font-medium capitalize ${
              tab === t ? "border-b-2 border-primary text-primary" : "text-muted-foreground"
            }`}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "graph" && (
        <div className="h-[400px] rounded-md border bg-muted/20">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            proOptions={{ hideAttribution: true }}
          >
            <Background />
            <Controls />
          </ReactFlow>
        </div>
      )}

      {tab === "table" && (
        <div className="max-h-[400px] overflow-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="bg-muted sticky top-0 z-10 shadow-[0_1px_0_0_hsl(var(--border))]">
              <tr>
                <th className="p-2 text-left">Include</th>
                <th className="p-2 text-left">Entity</th>
                <th className="p-2 text-left">Description</th>
                <th className="p-2 text-left">Columns</th>
                <th className="p-2 text-left">Rows</th>
                <th className="p-2 text-left">Rels</th>
              </tr>
            </thead>
            <tbody>
              {graphNodes.map((n: KGNode) => {
                const relCount = graphEdges.filter(
                  (e: KGEdge) => e.source === n.id || e.target === n.id
                ).length;
                return (
                  <tr key={n.id} className={`border-t ${excluded.has(n.id) ? "opacity-40" : ""}`}>
                    <td className="p-2">
                      <input
                        type="checkbox"
                        checked={!excluded.has(n.id)}
                        onChange={() => toggleExclude(n.id)}
                      />
                    </td>
                    <td className="p-2 font-medium">{n.label}</td>
                    <td className="p-2 text-muted-foreground max-w-[300px] truncate" title={n.description}>{n.description ?? "—"}</td>
                    <td className="p-2">{n.columns?.length ?? "—"}</td>
                    <td className="p-2">{n.row_count !== undefined ? n.row_count.toLocaleString() : "—"}</td>
                    <td className="p-2">{relCount}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {tab === "content" && (
        <textarea
          className="h-[400px] w-full rounded-md border border-input bg-background p-3 font-mono text-xs"
          value={content}
          onChange={(e) => setContent(e.target.value)}
        />
      )}

      <div className="flex justify-between">
        <button
          onClick={onRegenerate}
          disabled={isRegenerating || kg.generation_mode === "manual"}
          className="rounded-md border border-input bg-background px-4 py-2 text-sm font-medium hover:bg-accent disabled:opacity-50"
        >
          {isRegenerating ? "Regenerating..." : "Regenerate"}
        </button>
        <button
          onClick={handleSave}
          disabled={isSaving}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {isSaving ? "Saving..." : "Save"}
        </button>
      </div>
    </div>
  );
}
