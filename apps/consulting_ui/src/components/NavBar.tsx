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

  return (
    <nav className="border-b border-zinc-200 dark:border-zinc-800">
      <div className="mx-auto flex w-full max-w-3xl items-center gap-4 px-4 py-3 text-sm">
        <span className="font-semibold">AI Consulting Accelerator</span>
        <div className="ml-auto flex items-center gap-4">
          <Link href="/" className="text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white">
            Q&amp;A
          </Link>
          <Link href="/structure" className="text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white">
            Structure
          </Link>
          {auth && (
            <>
              <span className="text-zinc-400">{auth.email}</span>
              <button onClick={onLogout} className="text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white">
                Sign out
              </button>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
