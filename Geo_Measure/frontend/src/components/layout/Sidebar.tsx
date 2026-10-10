import { Files, LayoutDashboard, Settings, type LucideIcon } from "lucide-react";
import { Link, NavLink } from "react-router-dom";

import { ApiStatus } from "./ApiStatus";
import { LogoMark } from "./Logo";
import styles from "./Sidebar.module.css";

const NAV_ITEMS: { to: string; label: string; icon: LucideIcon; end?: boolean }[] = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/files", label: "Files", icon: Files },
];

interface SidebarProps {
  compact?: boolean;
  onNavigate?: () => void;
}

export function Sidebar({ compact = false, onNavigate }: SidebarProps) {
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `${styles.link} ${isActive ? styles.active : ""}`;

  return (
    <div className={`${styles.sidebar} ${compact ? styles.compact : ""}`}>
      <Link to="/" className={styles.brand} onClick={onNavigate} aria-label="GeoMeasure overview">
        <LogoMark />
        <span className={styles.brandText}>
          <span className={styles.name}>GeoMeasure</span>
          <span className={styles.tagline}>Geospatial measurement, without the manual work.</span>
        </span>
      </Link>

      <nav className={styles.nav} aria-label="Main">
        <ul className={styles.navList}>
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <li key={to}>
              <NavLink to={to} end={end} className={linkClass} onClick={onNavigate} title={compact ? label : undefined}>
                <Icon size={18} aria-hidden="true" />
                <span className={styles.label}>{label}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <div className={styles.footer}>
        <div className={styles.apiRow}>
          <ApiStatus compact={compact} />
        </div>
        <ul className={styles.footerList}>
          <li>
            <NavLink to="/settings" className={linkClass} onClick={onNavigate} title={compact ? "Settings" : undefined}>
              <Settings size={18} aria-hidden="true" />
              <span className={styles.label}>Settings</span>
            </NavLink>
          </li>
        </ul>
      </div>
    </div>
  );
}
