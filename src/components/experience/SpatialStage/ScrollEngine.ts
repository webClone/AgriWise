/* ═══ AgriWise R2 Pass 3D — ScrollEngine ════════════════════════
   Pure DOM-measuring scroll engine.
   
   Architecture:
   - Discovers [data-r2-chapter] elements on the page
   - Measures exact page-space boundaries (top, bottom, height)
   - Tracks scrollY and viewport dimensions
   - Exposes clean ScrollSnapshot ref to the spatial render loop
   - Does NOT trigger React state updates or re-renders
   ═══════════════════════════════════════════════════════════════ */

export interface ChapterMeasurement {
  id: string;
  element: HTMLElement;
  top: number;
  bottom: number;
  height: number;
}

export interface ScrollSnapshot {
  scrollY: number;
  viewportWidth: number;
  viewportHeight: number;
  docHeight: number;
  globalProgress: number;

  // Chapter Positions
  heroTop: number;
  heroBottom: number;
  scaleTop: number;
  scaleBottom: number;
  evidenceTop: number;
  evidenceBottom: number;

  activeChapterId: string;
  chapterMeasurements: Map<string, ChapterMeasurement>;
}

export class ScrollEngine {
  private chapters: Map<string, ChapterMeasurement> = new Map();
  private chapterOrder: string[] = [];
  private snapshot: ScrollSnapshot;
  private resizeObserver: ResizeObserver | null = null;
  private scrollBound: (() => void) | null = null;
  private disposed = false;

  constructor() {
    this.snapshot = {
      scrollY: 0,
      viewportWidth: typeof window !== "undefined" ? window.innerWidth : 1280,
      viewportHeight: typeof window !== "undefined" ? window.innerHeight : 800,
      docHeight: 5000,
      globalProgress: 0,
      heroTop: 0,
      heroBottom: 800,
      scaleTop: 800,
      scaleBottom: 3600,
      evidenceTop: 3600,
      evidenceBottom: 4400,
      activeChapterId: "hero",
      chapterMeasurements: this.chapters,
    };
  }

  /** Discover [data-r2-chapter] elements and begin measurement */
  start(): void {
    if (typeof window === "undefined") return;

    this.discoverChapters();
    this.measureAll();

    // Scroll listener (passive)
    this.scrollBound = () => this.onScroll();
    window.addEventListener("scroll", this.scrollBound, { passive: true });

    // ResizeObserver on all chapter elements
    this.resizeObserver = new ResizeObserver(() => {
      this.measureAll();
      this.onScroll();
    });

    this.chapters.forEach(({ element }) => {
      this.resizeObserver!.observe(element);
    });

    // Window resize listener
    window.addEventListener("resize", () => {
      this.measureAll();
      this.onScroll();
    });

    this.onScroll();
  }

  /** Clean up listeners */
  dispose(): void {
    this.disposed = true;
    if (this.scrollBound && typeof window !== "undefined") {
      window.removeEventListener("scroll", this.scrollBound);
    }
    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
    }
  }

  /** Get snapshot (called by dirty renderer) */
  getSnapshot(): ScrollSnapshot {
    return this.snapshot;
  }

  /** Discover [data-r2-chapter] elements in DOM order */
  private discoverChapters(): void {
    const elements = document.querySelectorAll<HTMLElement>("[data-r2-chapter]");
    this.chapters.clear();
    this.chapterOrder = [];

    elements.forEach((el) => {
      const id = el.getAttribute("data-r2-chapter");
      if (id) {
        this.chapters.set(id, {
          id,
          element: el,
          top: 0,
          bottom: 0,
          height: 0,
        });
        this.chapterOrder.push(id);
      }
    });
  }

  /** Measure all chapter positions in absolute page space */
  private measureAll(): void {
    if (typeof window === "undefined") return;

    const scrollY = window.scrollY || window.pageYOffset;
    const vh = window.innerHeight;
    const vw = window.innerWidth;

    this.snapshot.viewportWidth = vw;
    this.snapshot.viewportHeight = vh;

    this.chapters.forEach((chapter) => {
      const rect = chapter.element.getBoundingClientRect();
      chapter.top = rect.top + scrollY;
      chapter.height = rect.height;
      chapter.bottom = chapter.top + rect.height;
    });

    // Update key chapter boundaries
    const hero = this.chapters.get("hero");
    if (hero) {
      this.snapshot.heroTop = hero.top;
      this.snapshot.heroBottom = hero.bottom;
    }

    const scale = this.chapters.get("scale");
    if (scale) {
      this.snapshot.scaleTop = scale.top;
      this.snapshot.scaleBottom = scale.bottom;
    }

    const evidence = this.chapters.get("evidence");
    if (evidence) {
      this.snapshot.evidenceTop = evidence.top;
      this.snapshot.evidenceBottom = evidence.bottom;
    }
  }

  /** Compute active chapter and scroll positions */
  private onScroll(): void {
    if (this.disposed || typeof window === "undefined") return;

    const scrollY = window.scrollY || window.pageYOffset;
    const vh = window.innerHeight;
    const docHeight = Math.max(
      document.body.scrollHeight,
      document.documentElement.scrollHeight
    ) - vh;

    this.snapshot.scrollY = scrollY;
    this.snapshot.docHeight = docHeight;
    this.snapshot.globalProgress = docHeight > 0
      ? Math.max(0, Math.min(1, scrollY / docHeight))
      : 0;

    // Determine active chapter by viewport center
    const viewportCenter = scrollY + vh * 0.4;
    let currentActive = this.chapterOrder[0] || "hero";

    for (const id of this.chapterOrder) {
      const ch = this.chapters.get(id)!;
      if (viewportCenter >= ch.top && viewportCenter <= ch.bottom) {
        currentActive = id;
        break;
      }
    }

    this.snapshot.activeChapterId = currentActive;
  }
}
