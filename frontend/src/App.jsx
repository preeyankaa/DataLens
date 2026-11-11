
import { useState } from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useNavigate,
} from "react-router-dom";

import Navbar from "./components/Navbar";
import Hero from "./components/Hero";
import UploadSection from "./components/UploadSection";

import {
  FeaturesSection,
  WorkflowSection,
  BottomCTA,
  Footer,
} from "./components/ContentSections";

import WorkspaceLayout from "./components/WorkspaceLayout";

import OverviewPage from "./pages/OverviewPage";
import CleaningPage from "./pages/CleaningPage";
import AIQuestionsPage from "./pages/AIQuestionsPage";
import ChartsPage from "./pages/ChartsPage";

import "./App.css";

function LandingPage({ onUploadSuccess }) {
  return (
    <div className="app">
      <Navbar />

      <main>
        <Hero />
        <UploadSection onUploadSuccess={onUploadSuccess} />
        <FeaturesSection />
        <WorkflowSection />
        <BottomCTA />
      </main>

      <Footer />
    </div>
  );
}

function AppContent() {
  const [dataset, setDataset] = useState(null);
  const navigate = useNavigate();

  const handleUploadSuccess = (data) => {
    setDataset(data);
    navigate("/workspace");
  };

  return (
    <Routes>
      <Route
        path="/"
        element={
          <LandingPage onUploadSuccess={handleUploadSuccess} />
        }
      />

      <Route
        path="/workspace"
        element={
          dataset ? (
            <WorkspaceLayout dataset={dataset} />
          ) : (
            <Navigate to="/" replace />
          )
        }
      >
        <Route index element={<OverviewPage />} />
        <Route path="cleaning" element={<CleaningPage />} />
        <Route path="ai-questions" element={<AIQuestionsPage dataset={dataset} />}/>
        <Route path="charts" element={<ChartsPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}

export default App;
