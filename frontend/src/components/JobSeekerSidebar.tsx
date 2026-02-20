import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ChatBubbleOutline, AccountCircleOutlined, WorkOutline, SettingsOutlined } from "@mui/icons-material";
import clsx from "clsx";

export default function JobSeekerSidebar() {
  const { t } = useTranslation();

  const NAV_ITEMS = [
    { to: "/", icon: ChatBubbleOutline, label: t("jobSeekerSidebar.aiChan") },
    { to: "/jobs", icon: WorkOutline, label: t("jobSeekerSidebar.myJobs") },
    { to: "/profile", icon: AccountCircleOutlined, label: t("jobSeekerSidebar.myProfile") },
    { to: "/settings", icon: SettingsOutlined, label: t("sidebar.settings") },
  ];

  return (
    <aside className="flex w-60 flex-col bg-gradient-to-b from-rose-900 to-pink-900 text-white">
      {/* Logo */}
      <div className="flex items-center gap-2 px-5 py-5">
        <img
          src="/ai-chan-avatar.png"
          alt="Ai Chan"
          className="h-7 w-7 rounded-full object-cover"
        />
        <span className="text-lg font-semibold tracking-tight">
          {t("common.appName")}
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
            <Icon sx={{ fontSize: 20 }} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="border-t border-pink-800 px-5 py-4 text-xs text-pink-400">
        v{__APP_VERSION__}
      </div>
    </aside>
  );
}
