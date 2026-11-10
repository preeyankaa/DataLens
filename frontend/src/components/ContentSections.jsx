import {
  Database,
  MessageSquareText,
  WandSparkles,
  BarChart3,
  Download,
  ShieldCheck,
  ArrowRight,
} from "lucide-react";

const features = [
  {
    icon: <Database />,
    title: "Data Quality Analysis",
    description: "Find missing values, duplicates, outliers and inconsistent formats.",
  },
  {
    icon: <MessageSquareText />,
    title: "Ask Questions with AI",
    description: "Understand your dataset by asking questions in plain English.",
  },
  {
    icon: <WandSparkles />,
    title: "Smart Data Cleaning",
    description: "Review suggested fixes and choose which changes to apply.",
  },
  {
    icon: <BarChart3 />,
    title: "Data Visualization",
    description: "Explore your data through charts and meaningful insights.",
  },
  {
    icon: <Download />,
    title: "Download Cleaned Data",
    description: "Export your cleaned dataset while keeping the original file safe.",
  },
  {
    icon: <ShieldCheck />,
    title: "Review Before Applying",
    description: "Preview cleaning changes before making any modifications.",
  },
];

const steps = [
  ["01", "Upload your CSV", "Choose a dataset from your computer."],
  ["02", "Analyze your data", "Check the quality and identify potential issues."],
  ["03", "Clean your dataset", "Select the issues you want to fix."],
  ["04", "Ask questions", "Explore your dataset using the AI assistant."],
  ["05", "View and export", "Explore charts and download your cleaned CSV."],
];

export function FeaturesSection() {
  return (
    <section className="features-section" id="features">
      <div className="section-heading">
        <span className="eyebrow">FEATURES</span>
        <h2>Everything you need to work with your data</h2>
        <p>From data quality checks to AI-powered analysis, all in one place.</p>
      </div>

      <div className="feature-grid">
        {features.map((feature) => (
          <article className="feature-card" key={feature.title}>
            <div className="feature-icon">{feature.icon}</div>
            <h3>{feature.title}</h3>
            <p>{feature.description}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

export function WorkflowSection() {
  return (
    <section className="workflow-section" id="how-it-works">
      <div className="section-heading">
        <span className="eyebrow">HOW IT WORKS</span>
        <h2>A simple workflow, from CSV to insights</h2>
        <p>Five straightforward steps to make your data more useful.</p>
      </div>

      <div className="workflow-grid">
        {steps.map(([number, title, description]) => (
          <article className="workflow-card" key={number}>
            <span className="step-number">{number}</span>
            <h3>{title}</h3>
            <p>{description}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

export function BottomCTA() {
  return (
    <section className="bottom-cta">
      <div>
        <span className="eyebrow">READY TO GET STARTED?</span>
        <h2>Make more sense of your data.</h2>
        <p>Upload your dataset and see what you can discover.</p>
      </div>

      <a href="#upload" className="primary-button">
        Try DataLens <ArrowRight size={18} />
      </a>
    </section>
  );
}

export function Footer() {
  return (
    <footer className="footer">
      <a href="#" className="brand">
        <span className="brand-icon"><BarChart3 size={19} /></span>
        <span>Data<span className="brand-accent">Lens</span></span>
      </a>

      <p>© 2026 DataLens. AI Data Quality & Analytics Copilot.</p>
      <span className="footer-note">Built for better data decisions.</span>
    </footer>
  );
}