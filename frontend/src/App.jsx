
import Navbar from "./components/Navbar";
import Hero from "./components/Hero";
import UploadSection from "./components/UploadSection";

import {
  FeaturesSection,
  WorkflowSection,
  BottomCTA,
  Footer,
} from "./components/ContentSections";

import "./App.css";

function App() {
  return (
    <div className="app">
      <Navbar />

      <main>
        <Hero />
        <UploadSection />
        <FeaturesSection />
        <WorkflowSection />
        <BottomCTA />
      </main>

      <Footer />
    </div>
  );
}

export default App;
