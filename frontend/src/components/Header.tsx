import { useState } from "react";
import { useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import AppBar from "@mui/material/AppBar";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import Button from "@mui/material/Button";
import Box from "@mui/material/Box";
import IconButton from "@mui/material/IconButton";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import Divider from "@mui/material/Divider";
import Dialog from "@mui/material/Dialog";
import DialogTitle from "@mui/material/DialogTitle";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogActions from "@mui/material/DialogActions";
import RadioGroup from "@mui/material/RadioGroup";
import FormControlLabel from "@mui/material/FormControlLabel";
import Radio from "@mui/material/Radio";
import AccountCircleOutlined from "@mui/icons-material/AccountCircleOutlined";
import LogoutOutlined from "@mui/icons-material/LogoutOutlined";
import PersonRemoveOutlined from "@mui/icons-material/PersonRemoveOutlined";
import type { User } from "../types";

interface Props {
  user: User;
  onLogout: () => void;
  onDeleteAccount?: (deleteRecords: boolean) => void;
}

export default function Header({ user, onLogout, onDeleteAccount }: Props) {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleteRecords, setDeleteRecords] = useState(false);

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
    "/calendar": t("header.calendar"),
    "/profile": t("header.myProfile"),
  };

  const titles = user.role === "job_seeker" ? JOB_SEEKER_TITLES : PAGE_TITLES;
  const title =
    titles[pathname] ??
    PAGE_TITLES[pathname] ??
    (pathname.startsWith("/candidates/") ? t("header.candidateDetail") : t("common.appName"));

  return (
    <>
      <AppBar position="static" color="inherit" elevation={0} sx={{ borderBottom: 1, borderColor: "divider" }}>
        <Toolbar sx={{ minHeight: 56 }}>
          <Typography variant="h6" fontWeight={600} sx={{ flexGrow: 1 }}>
            {title}
          </Typography>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Typography variant="body2" color="text.secondary">
              {user.email}
            </Typography>
            <IconButton
              size="small"
              onClick={(e) => setAnchorEl(e.currentTarget)}
              sx={{ color: "text.secondary" }}
            >
              <AccountCircleOutlined />
            </IconButton>
            <Menu
              anchorEl={anchorEl}
              open={Boolean(anchorEl)}
              onClose={() => setAnchorEl(null)}
              anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
              transformOrigin={{ vertical: "top", horizontal: "right" }}
            >
              <MenuItem onClick={() => { setAnchorEl(null); onLogout(); }}>
                <ListItemIcon><LogoutOutlined fontSize="small" /></ListItemIcon>
                <ListItemText>{t("common.logout")}</ListItemText>
              </MenuItem>
              {onDeleteAccount && (
                <>
                  <Divider />
                  <MenuItem onClick={() => { setAnchorEl(null); setDeleteRecords(false); setConfirmDelete(true); }}>
                    <ListItemIcon><PersonRemoveOutlined fontSize="small" color="error" /></ListItemIcon>
                    <ListItemText sx={{ color: "error.main" }}>{t("common.deleteAccount")}</ListItemText>
                  </MenuItem>
                </>
              )}
            </Menu>
          </Box>
        </Toolbar>
      </AppBar>

      {/* Delete Account Confirmation Dialog */}
      <Dialog open={confirmDelete} onClose={() => setConfirmDelete(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{t("common.deleteAccount")}</DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ mb: 2 }}>
            {t("common.deleteAccountConfirm")}
          </DialogContentText>
          <RadioGroup
            value={deleteRecords ? "delete" : "keep"}
            onChange={(e) => setDeleteRecords(e.target.value === "delete")}
          >
            <FormControlLabel
              value="keep"
              control={<Radio />}
              label={t("common.deleteKeepRecords")}
            />
            <FormControlLabel
              value="delete"
              control={<Radio color="error" />}
              label={t("common.deleteAllRecords")}
            />
          </RadioGroup>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDelete(false)}>
            {t("common.cancel")}
          </Button>
          <Button
            color="error"
            variant="contained"
            onClick={() => {
              setConfirmDelete(false);
              onDeleteAccount?.(deleteRecords);
            }}
          >
            {t("common.delete")}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
