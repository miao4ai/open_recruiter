import { useState } from "react";
import Box from "@mui/material/Box";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import Tabs from "@mui/material/Tabs";
import Tab from "@mui/material/Tab";
import TextField from "@mui/material/TextField";
import Button from "@mui/material/Button";
import Alert from "@mui/material/Alert";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import SmartToyOutlined from "@mui/icons-material/SmartToyOutlined";
import BusinessCenterOutlined from "@mui/icons-material/BusinessCenterOutlined";
import SearchOutlined from "@mui/icons-material/SearchOutlined";
import { login, register, setToken } from "../lib/api";
import type { User, UserRole } from "../types";

interface Props {
  onLogin: (user: User) => void;
}

export default function Login({ onLogin }: Props) {
  const [tab, setTab] = useState(0);
  const isRegister = tab === 1;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState<UserRole>("recruiter");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = isRegister
        ? await register(email, password, name, role)
        : await login(email, password, role);
      setToken(res.token);
      onLogin(res.user);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Something went wrong";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ display: "flex", minHeight: "100vh", alignItems: "center", justifyContent: "center", bgcolor: "background.default" }}>
      <Paper elevation={3} sx={{ width: "100%", maxWidth: 440, p: 4, borderRadius: 3 }}>
        {/* Logo */}
        <Box sx={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 1, mb: 4 }}>
          <SmartToyOutlined sx={{ fontSize: 32, color: "primary.main" }} />
          <Typography variant="h5" fontWeight={700} letterSpacing="-0.02em">
            Open Recruiter
          </Typography>
        </Box>

        {/* Tabs */}
        <Tabs
          value={tab}
          onChange={(_, v) => { setTab(v); setError(""); }}
          variant="fullWidth"
          sx={{ mb: 3 }}
        >
          <Tab label="Login" />
          <Tab label="Register" />
        </Tabs>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <Box component="form" onSubmit={handleSubmit} sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
          {/* Role selector */}
          <Box>
            <Typography variant="body2" fontWeight={500} sx={{ mb: 1 }}>
              I am a...
            </Typography>
            <ToggleButtonGroup
              value={role}
              exclusive
              onChange={(_, v) => { if (v) setRole(v); }}
              fullWidth
              size="small"
            >
              <ToggleButton value="recruiter" sx={{ py: 1.5, display: "flex", flexDirection: "column", gap: 0.5 }}>
                <BusinessCenterOutlined fontSize="small" />
                <Typography variant="caption">Recruiter</Typography>
              </ToggleButton>
              <ToggleButton value="job_seeker" sx={{ py: 1.5, display: "flex", flexDirection: "column", gap: 0.5 }}>
                <SearchOutlined fontSize="small" />
                <Typography variant="caption">Job Seeker</Typography>
              </ToggleButton>
            </ToggleButtonGroup>
          </Box>

          {isRegister && (
            <TextField
              label="Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Your name"
              fullWidth
            />
          )}
          <TextField
            label="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            placeholder="you@company.com"
            fullWidth
          />
          <TextField
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            inputProps={{ minLength: 6 }}
            placeholder="At least 6 characters"
            fullWidth
          />
          <Button
            type="submit"
            variant="contained"
            fullWidth
            disabled={loading}
            sx={{ py: 1.25, mt: 1 }}
          >
            {loading ? "Please wait..." : isRegister ? "Create Account" : "Sign In"}
          </Button>
        </Box>
      </Paper>
    </Box>
  );
}
