import { Menu } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";

import { Button } from "@/components/ui/Button";
import { Drawer } from "@/components/ui/Overlay";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { mediaQueries } from "@/styles/breakpoints";

import { ApiStatus } from "./ApiStatus";
import styles from "./AppShell.module.css";
import { LogoMark } from "./Logo";
import { Sidebar } from "./Sidebar";

/**
 * Persistent sidebar on desktop, icon rail on tablet, drawer navigation on mobile.
 */
export function AppShell() {
  const isTablet = useMediaQuery(mediaQueries.tablet);
  const [menuOpen, setMenuOpen] = useState(false);
  const closeMenu = useCallback(() => setMenuOpen(false), []);
  const location = useLocation();

  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  return (
    <div className={styles.shell}>
      <a href="#main-content" className={styles.skipLink}>
        Skip to content
      </a>
      <aside className={styles.aside}>
        <Sidebar compact={isTablet} />
      </aside>

      <div className={styles.main}>
        <div className={styles.mobileBar}>
          <Button variant="ghost" icon={Menu} iconOnly onClick={() => setMenuOpen(true)} aria-expanded={menuOpen}>
            Open navigation
          </Button>
          <Link to="/" className={styles.mobileBrand}>
            <LogoMark size={24} />
            GeoMeasure
          </Link>
          <ApiStatus compact />
        </div>
        <main id="main-content" tabIndex={-1}>
          <Outlet />
        </main>
      </div>

      <Drawer open={menuOpen} onClose={closeMenu} side="left" title="Navigation">
        <Sidebar onNavigate={closeMenu} />
      </Drawer>
    </div>
  );
}
