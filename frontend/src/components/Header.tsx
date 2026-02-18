import { useLocation } from "react-router-dom";
import AppBar from "@mui/material/AppBar";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import Button from "@mui/material/Button";
import Box from "@mui/material/Box";
import LogoutOutlined from "@mui/icons-material/LogoutOutlined";
import type { User } from "../types";

const PAGE_TITLES: Record<string, string> = {
  "/": "Dashboard",
  "/jobs": "Jobs",
  "/candidates": "Candidates",
  "/outreach": "Outreach",
  "/settings": "Settings",
};

interface Props {
  user: User;
  onLogout: () => void;
}

export default function Header({ user, onLogout }: Props) {
  const { pathname } = useLocation();
  const title =
    PAGE_TITLES[pathname] ??
    (pathname.startsWith("/candidates/") ? "Candidate Detail" : "Open Recruiter");

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
            Logout
          </Button>
        </Box>
      </Toolbar>
    </AppBar>
  );
}
