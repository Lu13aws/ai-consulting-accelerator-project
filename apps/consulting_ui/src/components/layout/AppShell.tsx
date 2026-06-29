"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import Sidebar from "./Sidebar";
import { AUTH_ENABLED, getAuth } from "@/lib/auth";

// Auth is enforced only in a deployed build (Cognito configured). Locally it runs without auth.
// The mount gate keeps server-prerender and first client render identical (both null) so there's
// no hydration mismatch; the real auth decision happens after mount (localStorage is client-only).
export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const isLogin = pathname?.startsWith("/login");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- client-only mount gate
    setMounted(true);
  }, []);

  useEffect(() => {
    if (mounted && AUTH_ENABLED && !isLogin && !getAuth()) router.replace("/login");
  }, [mounted, isLogin, router]);

  // Login page: full-screen, no sidebar.
  if (isLogin) return <main className="flex-1 overflow-y-auto bg-slate-950">{children}</main>;

  // Auth enabled: render nothing until mounted + a valid token exists (otherwise we're redirecting).
  if (AUTH_ENABLED && (!mounted || !getAuth())) return null;

  return (
    <>
      <Sidebar />
      <main className="flex-1 overflow-y-auto bg-slate-950">{children}</main>
    </>
  );
}
