import { useLocation } from "react-router-dom";

const PAGE_TITLES: Record<string, string> = {
  "/": "Dashboard",
  "/jobs": "Jobs",
  "/candidates": "Candidates",
  "/outreach": "Outreach",
  "/settings": "Settings",
};

export default function Header() {
  const { pathname } = useLocation();
  const title =
    PAGE_TITLES[pathname] ??
    (pathname.startsWith("/candidates/") ? "Candidate Detail" : "Open Recruiter");

  return (
    <header className="flex h-14 items-center border-b border-gray-200 bg-white px-6">
      <h1 className="text-lg font-semibold text-gray-900">{title}</h1>
    </header>
  );
}
