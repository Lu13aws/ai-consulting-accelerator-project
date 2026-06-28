"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Briefcase, Compass, LayoutDashboard, MessageSquare, Microscope, Rocket } from "lucide-react";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/chat", label: "Framework Q&A", icon: MessageSquare },
  { href: "/discovery", label: "Discovery", icon: Compass },
  { href: "/analysis", label: "Analysis", icon: Microscope },
  { href: "/delivery", label: "Delivery", icon: Rocket },
  { href: "/engagements", label: "Engagements", icon: Briefcase },
];

// trailingSlash: true makes /chat -> /chat/ — normalize before comparing.
function normalize(path: string): string {
  return path.endsWith("/") && path !== "/" ? path.slice(0, -1) : path;
}

export default function Sidebar() {
  const pathname = normalize(usePathname());

  return (
    <aside className="w-56 shrink-0 bg-slate-900 border-r border-slate-800 flex flex-col">
      <div className="px-4 py-5 border-b border-slate-800">
        <span className="text-xs font-semibold tracking-widest text-slate-500 uppercase">
          AI Consulting Accelerator
        </span>
      </div>

      <nav className="flex-1 py-4 space-y-0.5 px-2">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-colors ${
                active
                  ? "bg-blue-600/20 text-blue-400 font-medium"
                  : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
              }`}
            >
              <Icon size={16} />
              {label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
