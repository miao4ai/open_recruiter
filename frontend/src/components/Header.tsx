import { useLocation } from "react-router-dom";
import { LogOut } from "lucide-react";
import type { User } from "../types";

const PAGE_TITLES: Record<string, string> = {
  "/": "Erika Chan",
  "/dashboard": "Dashboard",
  "/jobs": "Jobs",
  "/candidates": "Candidates",
  "/calendar": "Calendar",
  "/settings": "Settings",
  "/profile": "My Profile",
};

const JOB_SEEKER_TITLES: Record<string, string> = {
  "/": "Ai Chan",
  "/profile": "My Profile",
};

interface Props {
  user: User;
  onLogout: () => void;
}

export default function Header({ user, onLogout }: Props) {
  const { pathname } = useLocation();
  const titles = user.role === "job_seeker" ? JOB_SEEKER_TITLES : PAGE_TITLES;
  const title =
    titles[pathname] ??
    PAGE_TITLES[pathname] ??
    (pathname.startsWith("/candidates/") ? "Candidate Detail" : "Open Recruiter");

  return (
    <header className="flex h-14 items-center justify-between border-b border-gray-200 bg-white px-6">
      <h1 className="text-lg font-semibold text-gray-900">{title}</h1>
      <div className="flex items-center gap-3">
        <span className="text-sm text-gray-500">{user.email}</span>
        <button
          onClick={onLogout}
          className="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-sm text-gray-500 hover:bg-gray-100 hover:text-gray-700"
        >
          <LogOut className="h-4 w-4" />
          Logout
        </button>
      </div>
    </header>
  );
}
