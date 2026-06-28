"use client";

import ToolTabs, { contextField } from "@/components/ToolTabs";
import { api } from "@/lib/api";

export default function DiscoveryPage() {
  return (
    <ToolTabs
      title="Discovery"
      blurb="Understand the business situation — problem, stakeholders, risks, unknowns. Drafts grounded in cited frameworks; follows your language (DE/EN)."
      tabs={[
        {
          id: "problem",
          label: "Business Problem",
          fields: [{ key: "problem_description", label: "Business problem", placeholder: "Describe your business problem…", required: true, rows: 6 }],
          submit: (f) => api.structureProblem(f.problem_description),
        },
        {
          id: "stakeholders",
          label: "Stakeholder Analysis",
          fields: [{ key: "input", label: "Project & known stakeholders", placeholder: "Describe the project and any known stakeholders…", required: true, rows: 6 }],
          submit: (f) => api.stakeholders(f.input),
        },
        {
          id: "risks",
          label: "Risks",
          fields: [contextField("Describe the project / situation to assess for risks…")],
          submit: (f) => api.runSkill("consulting.identify-risks", { context: f.context }),
        },
        {
          id: "assumptions",
          label: "Assumptions",
          fields: [contextField("Describe the project to surface implicit assumptions…")],
          submit: (f) => api.runSkill("consulting.detect-assumptions", { context: f.context }),
        },
        {
          id: "open-questions",
          label: "Open Questions",
          fields: [contextField("Describe what you know so far — we'll list what's still open…")],
          submit: (f) => api.runSkill("consulting.open-questions", { context: f.context }),
        },
        {
          id: "hypotheses",
          label: "Hypotheses",
          fields: [contextField("Describe the problem whose root cause is unclear…")],
          submit: (f) => api.runSkill("consulting.generate-hypotheses", { context: f.context }),
        },
        {
          id: "interview-guide",
          label: "Interview Guide",
          fields: [contextField("Describe the project to build a discovery interview guide…")],
          submit: (f) => api.runSkill("consulting.interview-guide", { context: f.context }),
        },
      ]}
    />
  );
}
