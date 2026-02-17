import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
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
      <div className="flex h-screen items-center justify-center text-gray-400">
        Loading...
      </div>
    );
  }

  if (!user) {
    return <Login onLogin={(u) => setUser(u)} />;
  }

  // Job seeker layout — sidebar + pages
  if (user.role === "job_seeker") {
    return (
      <div className="flex h-screen overflow-hidden">
        <JobSeekerSidebar />
        <div className="flex flex-1 flex-col overflow-hidden">
          <Header user={user} onLogout={handleLogout} />
          <main className="flex-1 overflow-y-auto bg-gray-50">
            <Routes>
              <Route path="/" element={<div className="h-full overflow-hidden"><JobSeekerHome /></div>} />
              <Route path="/jobs" element={<JobSeekerJobs />} />
              <Route path="/profile" element={<JobSeekerProfile />} />
            </Routes>
          </main>
        </div>
      </div>
    );
  }

  // Recruiter layout — full app
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header user={user} onLogout={handleLogout} />
        <main className="flex-1 overflow-y-auto bg-gray-50 p-6">
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
        </main>
      </div>
    </div>
  );
}
