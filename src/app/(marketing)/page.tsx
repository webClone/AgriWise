import Link from "next/link";
import Image from "next/image";
import type { Metadata } from "next";
import "./akaloris-home.css";

export const metadata: Metadata = {
 title: "Akaloris | Intelligence for the living world",
 description: "Integrated environmental observation, scientific reasoning and evidence-led decisions for agriculture and the living world.",
 openGraph: { title: "Akaloris | Intelligence for the living world", description: "Observe more. Decide with evidence.", siteName: "Akaloris", type: "website" },
};

const stages = [
 ["01","Observe","Combine satellite, weather, soil, field and instrumental evidence with provenance, coverage and time."],
 ["02","Reconstruct","Estimate what cannot be seen directly. Preserve uncertainty and the limits of observation."],
 ["03","Interpret","Compare plausible drivers of crop and environmental change rather than presenting one unsupported answer."],
 ["04","Simulate","Investigate conditional futures, alternative actions and their trade-offs. Predictions are not guarantees."],
 ["05","Decide","Translate sufficiently supported evidence into constrained next steps—or request a better measurement."],
 ["06","Communicate","Present maps, explanations and reports without hiding where a conclusion comes from."],
 ["07","Learn","Connect interventions and outcomes over time to improve candidate models and local knowledge."],
];
const systems = [
 ["AgriBrain","Scientific intelligence","The integrated reasoning system: multimodal representations, hypotheses, evidence, conditional scenarios and decisions."],
 ["ASMAE","Physical state reconstruction","Inverse modelling and assimilation of crop–soil–water states under spatial and observational constraints."],
 ["MESIA","Electromagnetic perception","A research program for instrumented, spatially anchored observations and conditional inference."],
 ["World Model","Conditional futures","A target capability for learning trajectories and modelling possible changes under interventions."],
 ["Omega","Scientific discovery","A research direction for falsifiable explanations, experiments and learning across evidence."],
];
const audiences = [
 ["FIELD / AGRICULTURE","People working the land","What changed in my field, and what should I do next?","Parcel monitoring, crop cycles, field evidence, assessments and practical tasks.","/farm","Explore field platform"],
 ["SCIENCE / RESEARCH","Agronomists and researchers","Which evidence supports this explanation?","Inspect uncertainty, scientific provenance, hypotheses, models and gaps in knowledge.","/agribrain","Explore AgriBrain"],
 ["INSTITUTIONS / POLICY","Decision makers","Where are our environmental and agricultural risks?","A target experience for regional observation, water, food security and comparative decisions.","#contact","Explore institutional direction"],
];
export default function Home() {
 return <div className="aka">
  <a className="aka-skip" href="#content">Skip to content</a>
  <header className="aka-header"><nav className="aka-shell aka-nav" aria-label="Main navigation">
    <Link className="aka-brand" href="/" aria-label="Akaloris home"><Image src="/brand/akaloris/akaloris_selected_wordmark.png" alt="Akaloris" width={192} height={41} priority /></Link>
    <div className="aka-navlinks"><a href="#approach">Our approach</a><a href="#science">Science</a><a href="#people">Who it's for</a></div>
    <Link className="aka-nav-button" href="/farm/new">Explore the platform <span aria-hidden="true">↗</span></Link>
  </nav></header>
  <main id="content">
   <section className="aka-hero aka-shell">
    <div className="aka-hero-text"><p className="aka-label">LAND / INTELLIGENCE / DECISION</p>
      <h1>Intelligence for <em>the living world.</em></h1>
      <p className="aka-lead">The world is interconnected. Our intelligence should be too.</p>
      <p className="aka-muted">Akaloris connects observation, scientific reasoning and useful decisions across land, crops, water and the environment—starting with agriculture.</p>
      <div className="aka-actions"><Link className="aka-primary" href="/farm/new">Explore the platform <span aria-hidden="true">↗</span></Link><a className="aka-secondary" href="#approach">Understand our approach <span aria-hidden="true">↓</span></a></div>
      <p className="aka-fine">Designed as a long-term scientific platform. Capabilities under research are not represented as deployed or validated.</p>
    </div>
    <div className="aka-hero-visual" role="img" aria-label="Conceptual illustration connecting agricultural land, observation, inference and decisions">
      <div className="aka-visual-header">LAND / OBSERVATION / INFERENCE</div>
      <svg viewBox="0 0 560 400" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
      <rect width="560" height="400" fill="#eef1e9"/><path d="M0 64L172 5 249 116 31 201Z" fill="#a8b99b"/><path d="M225 12L559 1 560 168 328 185Z" fill="#cad7c1"/><path d="M4 258L248 160 350 358 71 400Z" fill="#718b6a"/><path d="M371 225L560 182 560 400 438 400Z" fill="#aebfa0"/>
      <g stroke="#faf9f5" strokeWidth="8" fill="none"><path d="M35 3L264 393M-10 223L560 69M0 369L560 207"/></g>
      <g stroke="#f7f8f3" strokeWidth="2" fill="none" opacity=".92"><path d="M36 278L241 194M45 300L253 217M56 325L263 241M65 347L275 262M75 371L288 287M304 44L548 30M313 67L551 54M323 88L554 79M333 111L558 106"/></g>
      <path d="M166 85Q250 101 307 180T460 316" fill="none" stroke="#b47b47" strokeWidth="3" strokeDasharray="7 7"/>
      <circle cx="166" cy="85" r="7" fill="#b47b47" stroke="#faf9f5" strokeWidth="3"/><circle cx="307" cy="180" r="7" fill="#102820" stroke="#faf9f5" strokeWidth="3"/><circle cx="460" cy="316" r="7" fill="#b47b47" stroke="#faf9f5" strokeWidth="3"/>
      <g fontFamily="Inter,system-ui,sans-serif" fontSize="12" fontWeight="700" fill="#102820"><rect x="104" y="48" width="113" height="27" rx="4" fill="#faf9f5"/><text x="116" y="66">OBSERVATION</text><rect x="320" y="143" width="96" height="27" rx="4" fill="#faf9f5"/><text x="331" y="161">INFERENCE</text><rect x="395" y="335" width="90" height="27" rx="4" fill="#faf9f5"/><text x="408" y="353">DECISION</text></g></svg>
      <div className="aka-visual-footer">CONCEPTUAL TERRAIN SYSTEM · NOT LIVE FIELD DATA</div>
    </div>
   </section>
   <section className="aka-mission" id="approach"><div className="aka-shell"><p className="aka-label">OUR CENTRAL CONVICTION</p><h2>Agriculture is a living system.<br/><em>Understanding it takes more than a map.</em></h2><p>Evidence arrives from different places, at different times and resolutions. The goal is to bring those signals together while preserving what is measured, what is inferred and what remains unknown.</p></div></section>
   <section className="aka-section aka-shell"><div className="aka-section-heading"><div><p className="aka-label">THE SEVEN CAPABILITIES</p><h2>From evidence to<br/><em>informed action.</em></h2></div><p>The R3 target describes seven connected capabilities—not seven isolated dashboard features.</p></div>
     <div className="aka-stage-grid">{stages.map(([num,title,desc])=><article key={num} className="aka-stage"><div className="aka-stage-num">{num} <span aria-hidden="true">↗</span></div><h3>{title}</h3><p>{desc}</p></article>)}</div>
     <div className="aka-principle"><strong>Evidence before aesthetics.</strong><p>A source observation, a modeled estimate and a hypothetical simulation should never look like the same kind of fact.</p></div>
   </section>
   <section className="aka-dark" id="science"><div className="aka-shell"><div className="aka-section-heading"><div><p className="aka-label">SCIENTIFIC SYSTEMS</p><h2>One intelligence ecosystem.<br/><em>Distinct scientific responsibilities.</em></h2></div><p>AgriBrain coordinates specialized systems through a shared scientific history. The architecture contains implemented components and longer-term research directions.</p></div>
     <div className="aka-systems">{systems.map(([name,role,desc],idx)=><article key={name} className="aka-system"><span className="aka-system-number">0{idx+1}</span><h3>{name}</h3><div><strong>{role}</strong><p>{desc}</p></div></article>)}</div><p className="aka-note-dark">Architecture is a product and research target. Model claims require appropriate calibration, validation and operational qualification.</p>
   </div></section>
   <section className="aka-section aka-shell" id="people"><div className="aka-section-heading"><div><p className="aka-label">ONE FOUNDATION / THREE SCALES</p><h2>Intelligence shaped<br/><em>around the decision.</em></h2></div><p>A farmer needs the next useful step. An expert needs to inspect the reasoning. An institution needs the broader decision context.</p></div>
     <div className="aka-audiences">{audiences.map(([tag,name,question,desc,href,cta])=><article className="aka-audience" key={name}><p className="aka-label">{tag}</p><h3>{name}</h3><blockquote>{question}</blockquote><p>{desc}</p><Link href={href}>{cta} <span aria-hidden="true">↗</span></Link></article>)}</div>
   </section>
   <section className="aka-closing"><div className="aka-shell aka-closing-grid"><div><p className="aka-label">BUILT FOR THE LONG VIEW</p><h2>Observe more.<br/>Decide with evidence.</h2></div><div><p>We are building toward connected environmental intelligence: transparent about provenance, explicit about uncertainty and practical about decisions.</p><Link href="/agribrain" className="aka-secondary aka-white">Explore the scientific direction ↗</Link></div></div></section>
   <section className="aka-last aka-shell" id="contact"><p className="aka-label">EXPLORE AKALORIS</p><h2>Understand the land.<br/><em>Make the next decision clearer.</em></h2><div className="aka-actions"><Link href="/farm/new" className="aka-primary">Open the field platform ↗</Link><Link href="/agribrain" className="aka-secondary">Discover AgriBrain ↗</Link></div></section>
  </main>
  <footer className="aka-footer"><div className="aka-shell aka-footer-row"><div><strong>Akaloris</strong><p>Intelligence for the living world.</p></div><div className="aka-footer-links"><Link href="/farm">Platform</Link><Link href="/agribrain">Science</Link><a href="#content">Back to top ↑</a></div><small>© {new Date().getFullYear()} Akaloris · Built in Algeria</small></div></footer>
 </div>;
}