import { NavLink } from "react-router-dom";
import Drawer from "@mui/material/Drawer";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Divider from "@mui/material/Divider";
import DashboardOutlined from "@mui/icons-material/DashboardOutlined";
import WorkOutline from "@mui/icons-material/WorkOutline";
import PeopleOutline from "@mui/icons-material/PeopleOutline";
import MailOutline from "@mui/icons-material/MailOutline";
import ChatBubbleOutline from "@mui/icons-material/ChatBubbleOutline";
import SettingsOutlined from "@mui/icons-material/SettingsOutlined";
import SmartToyOutlined from "@mui/icons-material/SmartToyOutlined";

const DRAWER_WIDTH = 240;

const NAV_ITEMS = [
  { to: "/", icon: <DashboardOutlined />, label: "Dashboard" },
  { to: "/jobs", icon: <WorkOutline />, label: "Jobs" },
  { to: "/candidates", icon: <PeopleOutline />, label: "Candidates" },
  { to: "/outreach", icon: <MailOutline />, label: "Outreach" },
  { to: "/chat", icon: <ChatBubbleOutline />, label: "Chat" },
  { to: "/settings", icon: <SettingsOutlined />, label: "Settings" },
];

export default function Sidebar() {
  return (
    <Drawer
      variant="permanent"
      sx={{
        width: DRAWER_WIDTH,
        flexShrink: 0,
        "& .MuiDrawer-paper": {
          width: DRAWER_WIDTH,
          bgcolor: "#1e293b",
          color: "white",
          borderRight: "none",
        },
      }}
    >
      {/* Logo */}
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, px: 2.5, py: 2.5 }}>
        <SmartToyOutlined sx={{ color: "#60a5fa", fontSize: 28 }} />
        <Typography variant="subtitle1" fontWeight={600} letterSpacing="-0.02em">
          Open Recruiter
        </Typography>
      </Box>

      {/* Nav */}
      <List sx={{ mt: 1, px: 1.5, flexGrow: 1 }}>
        {NAV_ITEMS.map(({ to, icon, label }) => (
          <ListItem key={to} disablePadding sx={{ mb: 0.5 }}>
            <ListItemButton
              component={NavLink}
              to={to}
              end={to === "/" ? true : undefined}
              sx={{
                borderRadius: 2,
                "&.active": {
                  bgcolor: "primary.main",
                  color: "white",
                  "& .MuiListItemIcon-root": { color: "white" },
                },
                "&:hover:not(.active)": {
                  bgcolor: "#334155",
                },
              }}
            >
              <ListItemIcon sx={{ color: "grey.400", minWidth: 40 }}>
                {icon}
              </ListItemIcon>
              <ListItemText
                primary={label}
                primaryTypographyProps={{ fontSize: "0.875rem", fontWeight: 500 }}
              />
            </ListItemButton>
          </ListItem>
        ))}
      </List>

      {/* Footer */}
      <Divider sx={{ borderColor: "grey.700" }} />
      <Box sx={{ px: 2.5, py: 2 }}>
        <Typography variant="caption" color="grey.500">
          v0.1.0
        </Typography>
      </Box>
    </Drawer>
  );
}
