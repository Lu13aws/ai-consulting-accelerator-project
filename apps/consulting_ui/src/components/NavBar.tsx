"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { logout, useAuth } from "@/lib/auth";

export default function NavBar() {
  const pathname = usePathname();
  const router = useRouter();
  const auth = useAuth();

  function onLogout() {
    logout();
    router.replace("/login");
  }

  if (pathname === "/login") return null;

  const linkClass = (href: string) =>
    `transition hover:text-blue-400 ${
      pathname === href ? "text-blue-400 font-medium" : "text-slate-400"
    }`;

  return (
    <nav className="border-b border-slate-800 bg-slate-900">
      <div className="mx-auto flex w-full max-w-3xl items-center gap-4 px-4 py-3 text-sm">
        <span className="font-semibold text-slate-100">AI Consulting Accelerator</span>
        <div className="ml-auto flex items-center gap-4">
          <Link href="/" className={linkClass("/")}>
            Q&amp;A
          </Link>
          <Link href="/structure" className={linkClass("/structure")}>
            Structure
          </Link>
          {auth && (
            <>
              <span className="text-slate-500">{auth.email}</span>
              <button onClick={onLogout} className="text-slate-400 transition hover:text-blue-400">
                Sign out
              </button>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
