import { ChevronRight } from "lucide-react";
import { useEffect, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { ApiStatus } from "./ApiStatus";
import styles from "./PageHeader.module.css";

export interface Crumb {
  label: string;
  to?: string;
}

export function Breadcrumb({ items }: { items: Crumb[] }) {
  return (
    <nav aria-label="Breadcrumb" className={styles.breadcrumb}>
      <ol>
        {items.map((item, index) => {
          const last = index === items.length - 1;
          return (
            <li key={`${item.label}-${index}`} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
              {item.to && !last ? (
                <Link to={item.to}>{item.label}</Link>
              ) : (
                <span aria-current={last ? "page" : undefined}>{item.label}</span>
              )}
              {!last && <ChevronRight size={13} className={styles.separator} aria-hidden="true" />}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

interface PageHeaderProps {
  title: ReactNode;
  /** Plain-text title for the browser tab when ``title`` is not a string. */
  documentTitle?: string;
  description?: ReactNode;
  breadcrumb: Crumb[];
  actions?: ReactNode;
  /** Shown next to the title (e.g. a status badge). */
  meta?: ReactNode;
}

export function PageHeader({ title, documentTitle, description, breadcrumb, actions, meta }: PageHeaderProps) {
  const tabTitle = documentTitle ?? (typeof title === "string" ? title : undefined);
  useEffect(() => {
    document.title = tabTitle ? `${tabTitle} – GeoMeasure` : "GeoMeasure";
  }, [tabTitle]);

  return (
    <header className={styles.header}>
      <div className={styles.topRow}>
        <Breadcrumb items={breadcrumb} />
        <span className={styles.headerStatus}>
          <ApiStatus />
        </span>
      </div>
      <div className={styles.titleRow}>
        <div className={styles.titleBlock}>
          <div className={styles.titleLine}>
            <h1 className={styles.title}>{title}</h1>
            {meta}
          </div>
          {description && <p className={styles.description}>{description}</p>}
        </div>
        {actions && <div className={styles.actions}>{actions}</div>}
      </div>
    </header>
  );
}

export function PageContainer({ children }: { children: ReactNode }) {
  return <div className={styles.container}>{children}</div>;
}
