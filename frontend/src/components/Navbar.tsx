"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ShieldAlert, Radar, Bell, Settings } from "lucide-react";

export function Navbar() {
  const pathname = usePathname();

  const navItems = [
    { href: "/", label: "Live Scanner", icon: Radar },
    { href: "/watchlist", label: "Watchlist & Alert", icon: Bell },
    { href: "/settings", label: "Pengaturan", icon: Settings },
  ];

  return (
    <header className="border-b border-slate-800 bg-slate-950/90 backdrop-blur sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-lg bg-indigo-600/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div>
            <span className="font-bold text-slate-100 tracking-tight">
              MEMECOIN AUDIT AGENT
            </span>
            <span className="ml-2 text-xs px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800">
              GMGN Scout + 9router AI
            </span>
          </div>
        </Link>

        <nav className="flex items-center gap-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active =
              item.href === "/"
                ? pathname === "/" || pathname.startsWith("/tokens")
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-colors ${
                  active
                    ? "bg-indigo-600 text-white"
                    : "text-slate-300 hover:bg-slate-800/70 hover:text-white"
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
