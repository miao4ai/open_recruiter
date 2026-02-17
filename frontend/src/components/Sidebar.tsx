import { NavLink } from "react-router-dom";
import {
  Briefcase,
  Users,
  MessageSquare,
  CalendarDays,
  Zap,
  Settings,
} from "lucide-react";
import clsx from "clsx";

const NAV_ITEMS = [
  { to: "/", icon: MessageSquare, label: "Erika Chan" },
  { to: "/jobs", icon: Briefcase, label: "Jobs" },
  { to: "/candidates", icon: Users, label: "Candidates" },
  { to: "/calendar", icon: CalendarDays, label: "Calendar" },
  { to: "/automations", icon: Zap, label: "Automations" },
  { to: "/settings", icon: Settings, label: "Settings" },
];

export default function Sidebar() {
  return (
    <aside className="flex w-60 flex-col bg-[var(--color-sidebar)] text-white">
      {/* Logo */}
      <div className="flex items-center gap-2 px-5 py-5">
        <img
          src="/ai-chan-avatar.png"
          alt="Open Recruiter"
          className="h-7 w-7 rounded-full object-cover"
        />
        <span className="text-lg font-semibold tracking-tight">
          Open Recruiter
        </span>
      </div>

      {/* Nav */}
      <nav className="mt-2 flex-1 space-y-1 px-3">
        {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              clsx(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                isActive
                  ? "bg-blue-600 text-white"
                  : "text-gray-300 hover:bg-[var(--color-sidebar-hover)] hover:text-white"
              )
            }
          >
            <Icon className="h-5 w-5" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="border-t border-gray-700 px-5 py-4 text-xs text-gray-500">
        v0.1.0
      </div>
    </aside>
  );
}
