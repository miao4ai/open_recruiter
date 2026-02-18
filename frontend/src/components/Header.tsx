import { useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import AppBar from "@mui/material/AppBar";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import Button from "@mui/material/Button";
import Box from "@mui/material/Box";
import LogoutOutlined from "@mui/icons-material/LogoutOutlined";
import type { User } from "../types";

interface Props {
  user: User;
  onLogout: () => void;
}

export default function Header({ user, onLogout }: Props) {
  const { t } = useTranslation();
  const { pathname } = useLocation();

  const PAGE_TITLES: Record<string, string> = {
    "/": t("header.erikaChan"),
    "/dashboard": t("header.dashboard"),
    "/jobs": t("header.jobs"),
    "/candidates": t("header.candidates"),
    "/calendar": t("header.calendar"),
    "/settings": t("header.settings"),
    "/profile": t("header.myProfile"),
  };

  const JOB_SEEKER_TITLES: Record<string, string> = {
    "/": t("header.aiChan"),
    "/jobs": t("header.myJobs"),
    "/profile": t("header.myProfile"),
  };

  const titles = user.role === "job_seeker" ? JOB_SEEKER_TITLES : PAGE_TITLES;
  const title =
    titles[pathname] ??
    PAGE_TITLES[pathname] ??
    (pathname.startsWith("/candidates/") ? t("header.candidateDetail") : t("common.appName"));

  return (
    <AppBar position="static" color="inherit" elevation={0} sx={{ borderBottom: 1, borderColor: "divider" }}>
      <Toolbar sx={{ minHeight: 56 }}>
        <Typography variant="h6" fontWeight={600} sx={{ flexGrow: 1 }}>
          {title}
        </Typography>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
          <Typography variant="body2" color="text.secondary">
            {user.email}
          </Typography>
          <Button
            size="small"
            color="inherit"
            startIcon={<LogoutOutlined fontSize="small" />}
            onClick={onLogout}
            sx={{ color: "text.secondary" }}
          >
            {t("common.logout")}
          </Button>
        </Box>
      </Toolbar>
    </AppBar>
  );
}
