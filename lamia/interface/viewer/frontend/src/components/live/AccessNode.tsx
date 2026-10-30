"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";

export interface AccessNodeData {
  label: string;
  assetType: string;
  inScope: boolean;
  findingId: string | null;
  [key: string]: unknown;
}

const TYPE_LABEL: Record<string, string> = {
  host: "Host",
  service: "Service",
  app: "App",
  role: "Role",
  data_store: "Data store",
};

function AccessNodeComponent({ data, selected }: NodeProps) {
  const asset = data as AccessNodeData;
  const kind = TYPE_LABEL[asset.assetType] ?? "Asset";

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={`${kind} ${asset.label}`}
      className={`w-[220px] rounded-lg border px-3 py-2.5 transition-colors ${
        selected
          ? "border-white/40 bg-[#1a0a0a]"
          : "border-[#ef4444]/45 bg-black hover:border-[#ef4444]"
      }`}
    >
      <Handle
        type="target"
        position={Position.Left}
        isConnectable={false}
        className="!h-1.5 !w-1.5 !border-0 !bg-[#ef4444]"
      />
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-medium uppercase tracking-wide text-[#fca5a5]">
          {kind}
        </span>
        {!asset.inScope && (
          <span className="text-[10px] text-[#fca5a5]/70">Discovered</span>
        )}
      </div>
      <div className="mt-1 line-clamp-2 text-sm font-semibold leading-snug text-white">
        {asset.label}
      </div>
      <Handle
        type="source"
        position={Position.Right}
        isConnectable={false}
        className="!h-1.5 !w-1.5 !border-0 !bg-[#ef4444]"
      />
    </div>
  );
}

export default memo(AccessNodeComponent);
