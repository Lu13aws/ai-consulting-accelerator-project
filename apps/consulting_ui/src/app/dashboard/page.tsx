import Link from "next/link";
import {
  Briefcase,
  ClipboardCheck,
  ClipboardList,
  FileText,
  Gauge,
  HelpCircle,
  Lightbulb,
  ListChecks,
  Map,
  MessageSquare,
  Mic,
  Scale,
  ShieldAlert,
  ShieldCheck,
  TrendingUp,
  Users,
} from "lucide-react";

type Tool = {
  href: string;
  label: string;
  icon: React.ElementType;
  color: string;
  desc: string;
};

const LAYERS: { id: string; title: string; blurb: string; tools: Tool[] }[] = [
  {
    id: "discovery",
    title: "Discovery",
    blurb: "Understand the business situation — problem, stakeholders, risks, unknowns.",
    tools: [
      { href: "/chat", label: "Framework Q&A", icon: MessageSquare, color: "text-blue-400", desc: "Ask the indexed frameworks (IREB, BABOK, BPMN, PMBOK). Cited answers." },
      { href: "/discovery?tab=problem", label: "Business Problem", icon: FileText, color: "text-teal-400", desc: "Current/target state, pain points, goals, success metrics, root cause, scope." },
      { href: "/discovery?tab=stakeholders", label: "Stakeholder Analysis", icon: Users, color: "text-orange-400", desc: "Role categories, RACI skeleton, influence/interest, engagement & comms plan." },
      { href: "/discovery?tab=risks", label: "Risks", icon: ShieldAlert, color: "text-red-400", desc: "Risk · Impact · Probability · Recommendation." },
      { href: "/discovery?tab=assumptions", label: "Assumptions", icon: ClipboardList, color: "text-amber-400", desc: "Surface implicit assumptions to validate." },
      { href: "/discovery?tab=open-questions", label: "Open Questions", icon: HelpCircle, color: "text-sky-400", desc: "Clarification questions to ask before designing a solution." },
      { href: "/discovery?tab=hypotheses", label: "Hypotheses", icon: Lightbulb, color: "text-yellow-400", desc: "Root-cause hypotheses when the cause is not yet known." },
      { href: "/discovery?tab=interview-guide", label: "Interview Guide", icon: Mic, color: "text-purple-400", desc: "A stakeholder discovery interview guide." },
      { href: "/discovery?tab=ai-readiness", label: "AI Readiness", icon: ClipboardCheck, color: "text-cyan-400", desc: "Org readiness across Data · Technology · Talent · Process · Governance — blockers, first steps, overall signal." },
    ],
  },
  {
    id: "analysis",
    title: "Analysis",
    blurb: "Turn understanding into structured solution design.",
    tools: [
      { href: "/analysis?tab=requirements", label: "Requirements Structurer", icon: ListChecks, color: "text-green-400", desc: "Classify requirements (BR/FR/NFR/constraint/…), INVEST user stories, quality flags." },
      { href: "/analysis?tab=assessment", label: "Consultant Assessment", icon: Gauge, color: "text-pink-400", desc: "Initial assessment + prioritisation (risks, impact, quick wins) — preliminary, to validate." },
      { href: "/analysis?tab=compliance", label: "Compliance Maturity", icon: ShieldCheck, color: "text-emerald-400", desc: "Assess AI compliance maturity (NIST AI RMF, GDPR/DSG, AWS Well-Architected Security) — prioritized gap analysis + artifacts." },
      { href: "/analysis?tab=ai-governance", label: "AI Governance", icon: Scale, color: "text-violet-400", desc: "Governance readiness: EU AI Act risk class + NIST AI RMF (GOVERN/MAP/MEASURE/MANAGE) gaps — organisational, not technical." },
    ],
  },
  {
    id: "delivery",
    title: "Delivery",
    blurb: "Support project planning.",
    tools: [
      { href: "/delivery?tab=roadmap", label: "Roadmap Generator", icon: Map, color: "text-indigo-400", desc: "Now / Next / Later roadmap plus an agile backlog (Epic → Feature → User Story)." },
      { href: "/delivery?tab=articulate-value", label: "Value Articulation", icon: TrendingUp, color: "text-rose-400", desc: "Translate a technical initiative into an executive value narrative — transformation story, KPI mapping, headline." },
    ],
  },
];

export default function DashboardPage() {
  return (
    <div className="p-8 max-w-6xl">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-slate-100">Dashboard</h1>
        <p className="text-sm text-slate-500 mt-1">
          AI-assisted consulting workflow — Discovery → Analysis → Delivery. Every output is
          a draft for human review, grounded in cited frameworks.
        </p>
      </div>

      {/* Guided, cross-layer workflow (Discovery → Analysis) */}
      <Link
        href="/engagements"
        className="group mb-10 flex items-start gap-4 rounded-lg border border-blue-800/60 bg-blue-950/20 p-5 transition-colors hover:border-blue-600 hover:bg-blue-950/40"
      >
        <Briefcase size={22} className="mt-0.5 shrink-0 text-blue-400" />
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-slate-100 group-hover:text-blue-400 transition-colors">
              Guided Engagement
            </h2>
            <span className="rounded bg-blue-950 px-1.5 py-0.5 text-[10px] text-blue-300">
              Discovery → Analysis
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-400 leading-relaxed">
            A stateful, multi-step discovery: describe the situation → review analysis,
            hypotheses &amp; open questions → answer → refined analysis and requirements.
          </p>
        </div>
      </Link>

      <div className="flex flex-col gap-10">
        {LAYERS.map((layer) => (
          <section key={layer.id}>
            <div className="mb-3">
              <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                {layer.title}
              </h2>
              <p className="text-sm text-slate-600 mt-0.5">{layer.blurb}</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {layer.tools.map(({ href, label, icon: Icon, color, desc }) => (
                <Link
                  key={label}
                  href={href}
                  className="group bg-slate-900 border border-slate-800 rounded-lg p-5 transition-colors hover:border-blue-700 hover:bg-slate-800/50"
                >
                  <div className="flex items-center gap-3 mb-3">
                    <Icon size={20} className={color} />
                    <h3 className="text-sm font-semibold text-slate-100 group-hover:text-blue-400 transition-colors">
                      {label}
                    </h3>
                  </div>
                  <p className="text-sm text-slate-400 leading-relaxed">{desc}</p>
                </Link>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
