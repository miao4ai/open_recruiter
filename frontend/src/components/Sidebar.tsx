import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Briefcase,
  Users,
  Mail,
  MessageSquare,
  Settings,
  Bot,
} from "lucide-react";
import clsx from "clsx";

const NAV_ITEMS = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/jobs", icon: Briefcase, label: "Jobs" },
  { to: "/candidates", icon: Users, label: "Candidates" },
  { to: "/outreach", icon: Mail, label: "Outreach" },
  { to: "/chat", icon: MessageSquare, label: "Chat" },
  { to: "/settings", icon: Settings, label: "Settings" },
];

export default function Sidebar() {
  return (
    <aside className="flex w-60 flex-col bg-[var(--color-sidebar)] text-white">
      {/* Logo */}
      <div className="flex items-center gap-2 px-5 py-5">
        <Bot className="h-7 w-7 text-blue-400" />
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
