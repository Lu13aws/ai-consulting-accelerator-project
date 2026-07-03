"use client";

import ToolTabs from "@/components/ToolTabs";
import { api } from "@/lib/api";

export default function DeliveryPage() {
  return (
    <ToolTabs
      title="Delivery"
      blurb="Support project planning. Drafts grounded in cited frameworks; follows your language (DE/EN)."
      tabs={[
        {
          id: "roadmap",
          label: "Roadmap",
          fields: [
            { key: "vision", label: "Product / project vision", placeholder: "What are you building, for whom, and why?", required: true, rows: 3 },
            { key: "goals", label: "Goals / outcomes", placeholder: "Target outcomes, ideally measurable", required: true, rows: 2 },
            { key: "known_scope", label: "Known scope / features", placeholder: "Known features or scope items (optional)", required: false, rows: 2 },
            { key: "constraints", label: "Constraints / timeline", placeholder: "Deadlines, team, budget, tech (optional)", required: false, rows: 2 },
            { key: "target_users", label: "Target users / stakeholders", placeholder: "Who are the users / stakeholders? (optional)", required: false, rows: 2 },
          ],
          submit: (f) =>
            api.structureRoadmap({
              vision: f.vision,
              goals: f.goals,
              known_scope: f.known_scope,
              constraints: f.constraints,
              target_users: f.target_users,
            }),
        },
        {
          id: "articulate-value",
          label: "Value Articulation",
          fields: [
            { key: "initiative_description", label: "Initiative", placeholder: "The technical initiative / project to translate into business value…", required: true, rows: 4 },
            { key: "target_stakeholders", label: "Target stakeholders", placeholder: "Who is this for? e.g. CFO, operations lead, engineering…", required: true, rows: 2 },
            { key: "current_state_pain", label: "Current-state pain", placeholder: "What hurts today that this addresses?", required: true, rows: 2 },
            { key: "quantitative_targets", label: "Quantitative targets", placeholder: "Only real figures — time, cost, volume (optional)", required: false, rows: 2 },
            { key: "qualitative_benefits", label: "Qualitative benefits", placeholder: "Risk, quality, trust… (optional)", required: false, rows: 2 },
            { key: "timeline", label: "Timeline", placeholder: "e.g. 2 quarters (optional)", required: false, rows: 1 },
            { key: "industry", label: "Industry", placeholder: "optional", required: false, rows: 1 },
          ],
          submit: (f) => api.runSkill("consulting.articulate-value", f),
        },
      ]}
    />
  );
}
