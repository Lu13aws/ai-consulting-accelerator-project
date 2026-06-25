import Sidebar from "./Sidebar";

// Phase 1 is a public portfolio demo — no auth, no login redirect.
export default function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Sidebar />
      <main className="flex-1 overflow-y-auto bg-slate-950">{children}</main>
    </>
  );
}
