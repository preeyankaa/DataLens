
import { NavLink, Outlet } from "react-router-dom";
import {
  LayoutDashboard,
  Broom,
  Bot,
  ChartNoAxesCombined,
  Database,
} from "lucide-react";

import "./Workspace.css";

function WorkspaceLayout({ dataset }) {
  const navigation = [
    {
      name: "Overview",
      path: "/workspace",
      icon: LayoutDashboard,
      end: true,
    },
    {
      name: "Data Cleaning",
      path: "/workspace/cleaning",
      icon: Broom,
    },
    {
      name: "AI Questions",
      path: "/workspace/ai-questions",
      icon: Bot,
    },
    {
      name: "Charts",
      path: "/workspace/charts",
      icon: ChartNoAxesCombined,
    },
  ];

  return (
    <div className="workspace">
      <aside className="workspace-sidebar">
        <div className="workspace-brand">
          <Database size={25} />
          <h2>DataLens</h2>
        </div>

        <div className="sidebar-section">
          <p className="sidebar-label">WORKSPACE</p>

          <nav className="sidebar-nav">
            {navigation.map((item) => {
              const Icon = item.icon;

              return (
                <NavLink
                  key={item.name}
                  to={item.path}
                  end={item.end}
                  className={({ isActive }) =>
                    isActive ? "nav-item active" : "nav-item"
                  }
                >
                  <Icon size={19} />
                  <span>{item.name}</span>
                </NavLink>
              );
            })}
          </nav>
        </div>

        <div className="sidebar-footer">
          <p>AI Data Quality & Analytics Copilot</p>
          <span>DataLens v1.0</span>
        </div>
      </aside>

      <main className="workspace-main">
        <header className="workspace-header">
          <div>
            <span className="header-label">CURRENT DATASET</span>
            <h3>{dataset.filename}</h3>
          </div>

          <span className="dataset-status">
            Analysis complete
          </span>
        </header>

        <div className="workspace-content">
          <Outlet context={dataset} />
        </div>
      </main>
    </div>
  );
}

export default WorkspaceLayout;
