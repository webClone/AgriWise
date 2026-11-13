"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useRef, useState, type ElementType } from "react";
import {
  Map, BrainCircuit, Satellite, RadioTower, Plane, Radio, Droplets,
  FilePlus2, MessageCircle, Library, X, Search, FlaskConical,
} from "lucide-react";
import { TOOL_CONCEPT_COUNT, TOOL_CONCEPT_FAMILIES } from "./workspace-tool-concepts";

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
  const [query, setQuery] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);
  const libraryButtonRef = useRef<HTMLButtonElement>(null);
  const base = `/farm/${encodeURIComponent(farmId)}/plot/${encodeURIComponent(plotId)}`;
  const filteredFamilies = useMemo(() => {
    const search = query.toLowerCase().trim();
    if (!search) return TOOL_CONCEPT_FAMILIES;
    return TOOL_CONCEPT_FAMILIES
      .map(family => ({
        ...family,
        concepts: family.concepts.filter(concept =>
          concept.toLowerCase().includes(search)
          || family.label.toLowerCase().includes(search)),
      }))
      .filter(family => family.concepts.length > 0);
  }, [query]);

  useEffect(() => {
    if (!libraryOpen) return;
    searchRef.current?.focus();
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

  const openFamilyWorkspace = (entry: string) => {
    setLibraryOpen(false);
    if (entry === "sensors" || entry === "drone" || entry === "mesia") {
      onOpenTool(entry);
    }
  };

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
            <Link key={item.id} className="pw-dock-item" title={item.label}
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
        aria-label={`Browse all ${TOOL_CONCEPT_COUNT} tool concepts`}
        ref={libraryButtonRef} title="Full tool concept library"
        onClick={() => { setQuery(""); setLibraryOpen(open => !open); }}>
        <Library size={20} aria-hidden="true" />
        <span>All tools</span>
      </button>

      {libraryOpen && (
        <div className="pw-tool-library" id="pw-tool-library"
          role="dialog" aria-label="Tool concept library — P02 preview">
          <div className="pw-library-header">
            <div>
              <strong>Tool Library</strong>
              <p>{TOOL_CONCEPT_COUNT} product concepts · discoverability preview</p>
            </div>
            <button type="button" aria-label="Close Tool Library" className="pw-icon-button"
              onClick={() => { setLibraryOpen(false); libraryButtonRef.current?.focus(); }}>
              <X size={18} />
            </button>
          </div>
          <label className="pw-library-search">
            <Search size={16} aria-hidden="true" />
            <span className="sr-only">Search tool concepts</span>
            <input ref={searchRef} type="search" value={query}
              onChange={event => setQuery(event.target.value)}
              placeholder="Find a tool or capability…" />
          </label>
          <p className="pw-library-disclaimer">
            Catalog entries are design concepts, not evidence of operational
            availability. Full capability and permission qualification belongs to P04.
          </p>
          <div className="pw-library-groups">
            {filteredFamilies.map(family => (
              <section className="pw-library-group" key={family.id}>
                <div className="pw-library-group-heading">
                  <h3>{family.label}</h3>
                  <span>{family.concepts.length}</span>
                </div>
                <p>{family.description}</p>
                <div className="pw-library-concepts">
                  {family.concepts.map(concept => (
                    <span className="pw-library-concept" key={concept} title="Catalog concept; capability not verified">
                      {concept}
                    </span>
                  ))}
                </div>
                {["sensors","drone","mesia"].includes(family.relatedEntry) ? (
                  <button type="button" className="pw-library-related"
                    onClick={() => openFamilyWorkspace(family.relatedEntry)}>
                    Open existing related workspace
                  </button>
                ) : (
                  <Link className="pw-library-related"
                    href={`${base}/${family.relatedEntry}`}
                    onClick={() => setLibraryOpen(false)}>
                    Open related existing page
                  </Link>
                )}
              </section>
            ))}
            {filteredFamilies.length === 0 && <p>No tool concepts match your search.</p>}
          </div>
        </div>
      )}
    </aside>
  );
}
