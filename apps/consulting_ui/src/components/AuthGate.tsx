"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/lib/auth";

const PUBLIC_PATHS = ["/login"];

// Client-side route guard. Auth state lives in localStorage (read via useAuth, an
// SSR-safe external store); unauthenticated users are redirected to /login.
export default function AuthGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const auth = useAuth();

  const allowed = PUBLIC_PATHS.includes(pathname) || auth !== null;

  useEffect(() => {
    if (!allowed) router.replace("/login");
  }, [allowed, router]);

  if (!allowed) return null;
  return <>{children}</>;
}
