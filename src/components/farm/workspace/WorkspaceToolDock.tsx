"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ElementType } from "react";
import {
  Map, BrainCircuit, Satellite, RadioTower, Plane, Radio, Droplets,
  FilePlus2, MessageCircle, Library, FlaskConical,
} from "lucide-react";
import { TOOL_MANIFEST_COUNT } from "./tool-registry-p04.mjs";
import ToolLibraryP04 from "./ToolLibraryP04";

export type WorkspaceQuickAction =
  | "sensors" | "drone" | "mesia" | "irrigation" | "evidence" | "assistant";

interface DockItem {
  id: string;
  label: string;
  icon: ElementType;
  suffix?: string;
  action?: WorkspaceQuickAction;
}

const DOCK_ITEMS: readonly DockItem[] = [
  { id: "map", label: "Plot map", icon: Map, suffix: "" },
  { id: "asmae", label: "AgriBrain & ASMAE", icon: BrainCircuit, suffix: "analysis" },
  { id: "satellite", label: "Satellite & raw data", icon: Satellite, suffix: "raw-data" },
  { id: "sensors", label: "Sensor Network", icon: RadioTower, action: "sensors" },
  { id: "drone", label: "Drone Missions", icon: Plane, action: "drone" },
  { id: "mesia", label: "MESIA Observatory", icon: Radio, action: "mesia" },
  { id: "irrigation", label: "Irrigation workspace — simulation only", icon: Droplets, action: "irrigation" },
  { id: "experiments", label: "Research & what-if analysis", icon: FlaskConical, suffix: "analysis" },
  { id: "evidence", label: "Add field evidence", icon: FilePlus2, action: "evidence" },
  { id: "assistant", label: "AgriBrain assistant", icon: MessageCircle, action: "assistant" },
];

export default function WorkspaceToolDock({
  farmId, plotId, onOpenTool,
}: {
  farmId: string;
  plotId: string;
  onOpenTool: (tool: WorkspaceQuickAction) => void;
}) {
  const pathname = usePathname();
  const [libraryOpen, setLibraryOpen] = useState(false);
  const libraryButtonRef = useRef<HTMLButtonElement>(null);
  const base = `/farm/${encodeURIComponent(farmId)}/plot/${encodeURIComponent(plotId)}`;
  useEffect(() => {
    if (!libraryOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setLibraryOpen(false);
        libraryButtonRef.current?.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [libraryOpen]);


  return (
    <aside className="pw-tool-dock" aria-label="Plot instruments and tools">
      <div className="pw-dock-mark" aria-hidden="true">A</div>
      <nav className="pw-tool-nav" aria-label="Workspace tools">
        {DOCK_ITEMS.map(item => {
          const Icon = item.icon;
          const href = item.suffix !== undefined
            ? item.suffix ? `${base}/${item.suffix}` : base
            : null;
          const current = href != null && (
            item.suffix === "" ? pathname === base || pathname === base + "/" : pathname === href
          );
          const content = <><Icon size={19} aria-hidden="true" strokeWidth={1.8} /><span>{item.label}</span></>;
          return href ? (
            <Link key={item.id} className="pw-dock-item" title={item.label} aria-label={item.label}
              aria-current={current ? "page" : undefined}
              data-active={current ? "true" : undefined} href={href}>
              {content}
            </Link>
          ) : (
            <button type="button" key={item.id} className="pw-dock-item"
              title={item.label} aria-label={item.label}
              onClick={() => { if (item.action) onOpenTool(item.action); }}>
              {content}
            </button>
          );
        })}
      </nav>
      <button type="button" className="pw-dock-item pw-dock-library"
        aria-expanded={libraryOpen} aria-controls="pw-tool-library"
        aria-label={`Browse all ${TOOL_MANIFEST_COUNT} tool concepts`}
        ref={libraryButtonRef} title="Full tool concept library"
        onClick={() => setLibraryOpen(open => !open)}>
        <Library size={20} aria-hidden="true" />
        <span>All tools</span>
      </button>

      {libraryOpen && (
        <ToolLibraryP04 onClose={() => {
          setLibraryOpen(false);
          libraryButtonRef.current?.focus();
        }} />
      )}
    </aside>
  );
}
