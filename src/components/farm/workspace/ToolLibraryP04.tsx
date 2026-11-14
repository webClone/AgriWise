"use client";

import { useMemo, useState } from "react";
import { Search, X, ArrowLeft, Layers3, LockKeyhole } from "lucide-react";
import { TOOL_FAMILIES, TOOL_MANIFEST, searchToolConcepts, describeToolAvailability } from "./tool-registry-p04.mjs";
import "./tool-library-p04.css";

type Concept = (typeof TOOL_MANIFEST)[number];

export default function ToolLibraryP04({ onClose }: { onClose: () => void }) {
  const [query, setQuery] = useState("");
  const [family, setFamily] = useState("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const results = useMemo(() => searchToolConcepts(query, family), [query, family]);
  const selected = useMemo<Concept | null>(
    () => TOOL_MANIFEST.find((t: Concept) => t.id === selectedId) ?? null,
    [selectedId]
  );
  const capability = selected ? describeToolAvailability(selected.id) : null;
  return (
    <section className="p04-library" id="pw-tool-library" role="dialog"
      aria-modal="false" aria-label="Akaloris Tool Library" data-testid="p04-tool-library">
      <header className="p04-library-header">
        <div>
          <span className="p04-eyebrow">AKALORIS / INSTRUMENTS</span>
          <h2>Tool Library</h2>
          <p>{TOOL_MANIFEST.length} planned tool concepts · Discover, inspect, and prepare</p>
        </div>
        <button className="p04-icon-button" aria-label="Close Tool Library" type="button" onClick={onClose}><X size={19} /></button>
      </header>
      <div className="p04-library-search">
        <Search size={18} aria-hidden="true" />
        <input aria-label="Search tools" autoFocus type="search" value={query}
          placeholder="Find instruments, analyses, methods…" onChange={e => setQuery(e.target.value)} />
        <span>{results.length}</span>
      </div>
      <nav aria-label="Tool families" className="p04-family-tabs">
        <button type="button" aria-pressed={family === "all"} onClick={() => { setFamily("all"); setSelectedId(null); }}>All · {TOOL_MANIFEST.length}</button>
        {TOOL_FAMILIES.map(f => (
          <button type="button" key={f.id} aria-pressed={family === f.id}
            onClick={() => { setFamily(f.id); setSelectedId(null); }}>{f.label} · {f.count}</button>
        ))}
      </nav>
      <div className="p04-library-body">
        <div className="p04-tool-results" aria-label="Matching tools">
          {results.length === 0 && <div className="p04-empty">No matching tools. Try another term or family.</div>}
          {results.map((tool: Concept) => (
            <button className="p04-tool-result" type="button" key={tool.id}
              aria-pressed={selectedId === tool.id} onClick={() => setSelectedId(tool.id)}>
              <Layers3 size={17} aria-hidden="true" />
              <span className="p04-tool-result-copy">
                <strong>{tool.title.en}</strong>
                <small>{TOOL_FAMILIES.find(f => f.id === tool.family)?.label} · Design concept</small>
              </span>
              <ArrowLeft size={15} className="p04-tool-arrow" aria-hidden="true" />
            </button>
          ))}
        </div>
        <aside className="p04-tool-detail" aria-label="Selected tool details">
          {selected ? (
            <>
              <span className="p04-eyebrow">INSTRUMENT PROFILE</span>
              <h3>{selected.title.en}</h3>
              <p className="p04-code">{selected.id}</p>
              <div className="p04-capability"><LockKeyhole size={17} aria-hidden="true" />
                <strong>Read-only concept · Not yet qualified</strong></div>
              <p>{capability?.reason}</p>
              <p>The tool is discoverable, but cannot claim scientific evidence, issue a physical command, or perform a simulated action until its actual runtime capability is verified.</p>
              <button type="button" className="p04-detail-clear" onClick={() => setSelectedId(null)}>Back to library</button>
            </>
          ) : (
            <div className="p04-detail-empty">
              <Layers3 size={27} aria-hidden="true" />
              <h3>Select an instrument</h3>
              <p>Browse planned capabilities and inspect their prerequisites. Your current plot and map remain open behind this library.</p>
            </div>
          )}
        </aside>
      </div>
      <footer className="p04-library-footer">Design catalog only. Availability and permissions will come from validated services, not this client registry.</footer>
    </section>
  );
}
