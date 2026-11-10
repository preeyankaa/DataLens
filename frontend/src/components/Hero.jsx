import { ArrowRight, ShieldCheck, Sparkles } from "lucide-react";
import DatasetPreview from "./DatasetPreview";

function Hero() {
  return (
    <section className="hero">
      <div className="hero-content">
        <div className="eyebrow">
          <Sparkles size={15} />
          AI-POWERED DATA QUALITY PLATFORM
        </div>

        <h1>
          Your Data. Cleaner,
          <br />
          Smarter, <span>Ready for Insights.</span>
        </h1>

        <p className="hero-description">
          Upload your CSV, discover data-quality issues, clean your
          dataset, and explore insights with AI — all in one place.
        </p>

        <div className="hero-actions">
          <a href="#upload" className="primary-button">
            Analyze your data <ArrowRight size={18} />
          </a>

          <a href="#features" className="secondary-button">
            Explore features
          </a>
        </div>

        <div className="trust-note">
          <ShieldCheck size={17} />
          Your original data is never modified
        </div>
      </div>

      <DatasetPreview />
    </section>
  );
}

export default Hero;