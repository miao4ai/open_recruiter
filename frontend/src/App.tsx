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
import JobSeekerHome from "./pages/JobSeekerHome";
import JobSeekerSidebar from "./components/JobSeekerSidebar";
import JobSeekerProfile from "./pages/JobSeekerProfile";
import JobSeekerJobs from "./pages/JobSeekerJobs";
import { clearToken, getMe, getToken } from "./lib/api";
import type { User } from "./types";

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      setChecking(false);
      return;
    }
    getMe()
      .then((u) => setUser(u))
      .catch(() => clearToken())
      .finally(() => setChecking(false));
  }, []);

  const handleLogout = () => {
    clearToken();
    setUser(null);
  };

  if (checking) {
    return (
      <Box sx={{ display: "flex", height: "100vh", alignItems: "center", justifyContent: "center" }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!user) {
    return <Login onLogin={(u) => setUser(u)} />;
  }

  // Job seeker layout
  if (user.role === "job_seeker") {
    return (
      <Box sx={{ display: "flex", height: "100vh", overflow: "hidden" }}>
        <JobSeekerSidebar />
        <Box sx={{ display: "flex", flexDirection: "column", flexGrow: 1, overflow: "hidden" }}>
          <Header user={user} onLogout={handleLogout} />
          <Box component="main" sx={{ flexGrow: 1, overflowY: "auto", bgcolor: "background.default" }}>
            <Routes>
              <Route path="/" element={<Box sx={{ height: "100%", overflow: "hidden" }}><JobSeekerHome /></Box>} />
              <Route path="/jobs" element={<JobSeekerJobs />} />
              <Route path="/profile" element={<JobSeekerProfile />} />
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
        <Header user={user} onLogout={handleLogout} />
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
