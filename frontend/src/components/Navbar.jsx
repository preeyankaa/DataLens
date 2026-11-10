import { useState } from "react";
import { BarChart3, Menu, X, ArrowRight } from "lucide-react";

function Navbar() {
  const [menuOpen, setMenuOpen] = useState(false);

  const closeMenu = () => setMenuOpen(false);

  return (
    <header className="navbar">
      <a href="#" className="brand">
        <span className="brand-icon"><BarChart3 size={21} /></span>
        <span>Data<span className="brand-accent">Lens</span></span>
      </a>

      <button
        className="mobile-menu-button"
        onClick={() => setMenuOpen(!menuOpen)}
        aria-label="Toggle menu"
      >
        {menuOpen ? <X /> : <Menu />}
      </button>

      <nav className={menuOpen ? "nav-links open" : "nav-links"}>
        <a href="#features" onClick={closeMenu}>Features</a>
        <a href="#how-it-works" onClick={closeMenu}>How it works</a>
        <a href="#upload" onClick={closeMenu}>Get started</a>
      </nav>

      <a href="#upload" className="nav-cta">
        Analyze your data <ArrowRight size={16} />
      </a>
    </header>
  );
}

export default Navbar;