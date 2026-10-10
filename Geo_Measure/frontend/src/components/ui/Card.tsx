import { useId, type ReactNode } from "react";

import styles from "./Card.module.css";

interface CardProps {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  /** Remove body padding so tables/maps can run edge to edge. */
  flush?: boolean;
  className?: string;
  children: ReactNode;
}

/** A titled panel. Renders a <section> labelled by its title. */
export function Card({ title, description, actions, flush = false, className, children }: CardProps) {
  const titleId = useId();
  return (
    <section className={`${styles.card} ${className ?? ""}`} aria-labelledby={title ? titleId : undefined}>
      {(title || actions) && (
        <header className={styles.header}>
          <div>
            {title && (
              <h2 className={styles.title} id={titleId}>
                {title}
              </h2>
            )}
            {description && <p className={styles.description}>{description}</p>}
          </div>
          {actions}
        </header>
      )}
      <div className={flush ? styles.flush : styles.body}>{children}</div>
    </section>
  );
}
