import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Sidebar from "./components/Sidebar";
import Header from "./components/Header";
import Jobs from "./pages/Jobs";
import Candidates from "./pages/Candidates";
import CandidateDetail from "./pages/CandidateDetail";
import Chat from "./pages/Chat";
import Calendar from "./pages/Calendar";
import Automations from "./pages/Automations";
import Settings from "./pages/Settings";
import Login from "./pages/Login";
import Onboarding from "./pages/Onboarding";
import JobSeekerHome from "./pages/JobSeekerHome";
import JobSeekerSidebar from "./components/JobSeekerSidebar";
import JobSeekerProfile from "./pages/JobSeekerProfile";
import JobSeekerJobs from "./pages/JobSeekerJobs";
import { clearToken, deleteAccount, getMe, getSetupStatus, getToken } from "./lib/api";
import type { User } from "./types";

// Electron IPC types
declare global {
  interface Window {
    electronAPI?: {
      platform: string;
      onLogout?: (callback: () => void) => void;
      onDeleteAccount?: (callback: () => void) => void;
    };
  }
}

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(true);
  const [needsOnboarding, setNeedsOnboarding] = useState(false);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      setChecking(false);
      return;
    }
    getMe()
      .then((u) => {
        setUser(u);
        // Check LLM setup status for both recruiters and job seekers
        return getSetupStatus().then((status) => {
          if (!status.llm_configured) setNeedsOnboarding(true);
        }).catch(() => { /* ignore — settings check is non-critical */ });
      })
      .catch(() => clearToken())
      .finally(() => setChecking(false));
  }, []);

  const handleLogin = (u: User) => {
    setUser(u);
    // Check if LLM needs onboarding (both roles need LLM configured)
    getSetupStatus().then((status) => {
      if (!status.llm_configured) setNeedsOnboarding(true);
    }).catch(() => {});
  };

  const handleLogout = () => {
    clearToken();
    setUser(null);
    setNeedsOnboarding(false);
  };

  const handleDeleteAccount = async (deleteRecords = false) => {
    try {
      await deleteAccount(deleteRecords);
    } catch {
      // Account may already be deleted or token expired — proceed with logout
    }
    clearToken();
    setUser(null);
    setNeedsOnboarding(false);
  };

  // Listen for Electron IPC events (menu actions)
  useEffect(() => {
    const api = window.electronAPI;
    if (!api) return;
    api.onLogout?.(() => handleLogout());
    api.onDeleteAccount?.(() => handleDeleteAccount());
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (checking) {
    return (
      <Box sx={{ display: "flex", height: "100vh", alignItems: "center", justifyContent: "center" }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!user) {
    return <Login onLogin={handleLogin} />;
  }

  // Show onboarding wizard if LLM hasn't been configured (both roles need it)
  if (needsOnboarding) {
    return <Onboarding onComplete={() => setNeedsOnboarding(false)} role={user.role} />;
  }

  // Job seeker layout
  if (user.role === "job_seeker") {
    return (
      <Box sx={{ display: "flex", height: "100vh", overflow: "hidden" }}>
        <JobSeekerSidebar />
        <Box sx={{ display: "flex", flexDirection: "column", flexGrow: 1, overflow: "hidden" }}>
          <Header user={user} onLogout={handleLogout} onDeleteAccount={handleDeleteAccount} />
          <Box component="main" sx={{ flexGrow: 1, overflowY: "auto", bgcolor: "background.default" }}>
            <Routes>
              <Route path="/" element={<Box sx={{ height: "100%", overflow: "hidden" }}><JobSeekerHome /></Box>} />
              <Route path="/jobs" element={<JobSeekerJobs />} />
              <Route path="/profile" element={<JobSeekerProfile />} />
              <Route path="/settings" element={<Box sx={{ p: 3 }}><Settings /></Box>} />
            </Routes>
          </Box>
        </Box>
      </Box>
    );
  }

  // Recruiter layout
  return (
    <Box sx={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      <Sidebar />
      <Box sx={{ display: "flex", flexDirection: "column", flexGrow: 1, overflow: "hidden" }}>
        <Header user={user} onLogout={handleLogout} onDeleteAccount={handleDeleteAccount} />
        <Box component="main" sx={{ flexGrow: 1, overflowY: "auto", bgcolor: "background.default", p: 3 }}>
          <Routes>
            <Route path="/" element={<Chat />} />
            <Route path="/dashboard" element={<Navigate to="/" replace />} />
            <Route path="/jobs" element={<Jobs />} />
            <Route path="/candidates" element={<Candidates />} />
            <Route path="/candidates/:id" element={<CandidateDetail />} />
            <Route path="/calendar" element={<Calendar />} />
            <Route path="/automations" element={<Automations />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </Box>
      </Box>
    </Box>
  );
}
