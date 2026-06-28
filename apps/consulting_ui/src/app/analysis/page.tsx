"use client";

import ToolTabs, { contextField } from "@/components/ToolTabs";
import { api } from "@/lib/api";

export default function AnalysisPage() {
  return (
    <ToolTabs
      title="Analysis"
      blurb="Turn understanding into structured solution design. Drafts grounded in cited frameworks; follows your language (DE/EN)."
      tabs={[
        {
          id: "requirements",
          label: "Requirements",
          fields: [{ key: "requirements", label: "Raw requirements", placeholder: "Paste your raw requirements here…", required: true, rows: 6 }],
          submit: (f) => api.structureRequirements(f.requirements),
        },
        {
          id: "assessment",
          label: "Consultant Assessment",
          fields: [contextField("Describe the situation for an initial assessment + prioritisation…")],
          submit: (f) => api.runSkill("consulting.consultant-assessment", { context: f.context }),
        },
      ]}
    />
  );
}
