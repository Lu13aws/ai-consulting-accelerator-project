import Link from "next/link";
import { FileText, ListChecks, Map, MessageSquare, Users } from "lucide-react";

const TOOLS = [
  {
    href: "/chat",
    label: "Framework Q&A",
    icon: MessageSquare,
    color: "text-blue-400",
    desc: "Ask questions about IREB, BABOK, BPMN and PMBOK. Answers are grounded in the indexed frameworks and cite their sources.",
  },
  {
    href: "/structure?tab=problem",
    label: "Business Problem Structurer",
    icon: FileText,
    color: "text-teal-400",
    desc: "Turn a free-text business problem into an IREB/BABOK-aligned problem statement: root cause, stakeholders, impact and scope.",
  },
  {
    href: "/structure?tab=requirements",
    label: "Requirements Structurer",
    icon: ListChecks,
    color: "text-green-400",
    desc: "Reformat raw requirements into INVEST-compliant user stories with acceptance criteria, flagging ambiguous or conflicting items.",
  },
  {
    href: "/structure?tab=roadmap",
    label: "Roadmap Generator",
    icon: Map,
    color: "text-purple-400",
    desc: "Turn a product vision into a Now / Next / Later roadmap plus an agile backlog (Epic → Feature → User Story).",
  },
  {
    href: "/stakeholders",
    label: "Stakeholder Analysis",
    icon: Users,
    color: "text-orange-400",
    desc: "Generate a RACI matrix skeleton, suggested stakeholder categories and engagement levels from a project description.",
  },
];

export default function DashboardPage() {
  return (
    <div className="p-8 max-w-6xl">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-slate-100">Dashboard</h1>
        <p className="text-sm text-slate-500 mt-1">
          AI-assisted consulting tools — grounded in cited frameworks. Every output is a
          draft for human review.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {TOOLS.map(({ href, label, icon: Icon, color, desc }) => (
          <Link
            key={label}
            href={href}
            className="group bg-slate-900 border border-slate-800 rounded-lg p-5 transition-colors hover:border-blue-700 hover:bg-slate-800/50"
          >
            <div className="flex items-center gap-3 mb-3">
              <Icon size={20} className={color} />
              <h2 className="text-sm font-semibold text-slate-100 group-hover:text-blue-400 transition-colors">
                {label}
              </h2>
            </div>
            <p className="text-sm text-slate-400 leading-relaxed">{desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
