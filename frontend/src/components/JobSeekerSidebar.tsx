import { NavLink } from "react-router-dom";
import { MessageSquare, UserCircle, Heart, Search } from "lucide-react";
import clsx from "clsx";

const NAV_ITEMS = [
  { to: "/", icon: MessageSquare, label: "Ai Chan" },
  { to: "/jobs", icon: Search, label: "Job Search" },
  { to: "/profile", icon: UserCircle, label: "My Profile" },
];

export default function JobSeekerSidebar() {
  return (
    <aside className="flex w-60 flex-col bg-gradient-to-b from-rose-900 to-pink-900 text-white">
      {/* Logo */}
      <div className="flex items-center gap-2 px-5 py-5">
        <div className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-pink-400 to-rose-500">
          <Heart className="h-3.5 w-3.5 text-white" fill="white" />
        </div>
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
                  ? "bg-pink-600 text-white"
                  : "text-pink-200 hover:bg-pink-800 hover:text-white"
              )
            }
          >
            <Icon className="h-5 w-5" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="border-t border-pink-800 px-5 py-4 text-xs text-pink-400">
        v0.1.0
      </div>
    </aside>
  );
}
