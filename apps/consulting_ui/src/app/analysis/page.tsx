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
        {
          id: "compliance",
          label: "Compliance Maturity",
          fields: [
            { key: "project_description", label: "Project description", placeholder: "What does the AI project do? Purpose, scope, data flow…", required: true, rows: 5 },
            { key: "data_categories", label: "Data categories", placeholder: "e.g. employee names, internal HR documents, health data…", required: true, rows: 2 },
            { key: "user_types", label: "User types", placeholder: "e.g. internal employees, external customers, the public…", required: true, rows: 2 },
            { key: "deployment_context", label: "Deployment context", placeholder: "e.g. AWS Lambda + pgvector, EU region, on-prem…", required: true, rows: 2 },
            { key: "existing_controls", label: "Existing controls", placeholder: "Controls already in place (access control, encryption, DPIA…)", required: false, rows: 3 },
            { key: "target_maturity_level", label: "Target maturity level", placeholder: "Demo-Ready / Customer-Ready / Production-Ready", required: false, rows: 1 },
          ],
          submit: (f) => api.runSkill("compliance.assess-maturity", f),
        },
      ]}
    />
  );
}
