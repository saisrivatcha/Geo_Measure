/**
 * Modal dialog and side drawer.
 *
 * Both are rendered in a portal with aria-modal, close on Escape and backdrop
 * click, keep Tab focus inside the panel, lock page scroll and return focus to
 * the element that opened them.
 */
import { X } from "lucide-react";
import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { Button } from "./Button";
import styles from "./Overlay.module.css";

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

interface OverlayProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  subtitle?: ReactNode;
  children: ReactNode;
}

function useOverlayBehaviour(open: boolean, onClose: () => void) {
  const panelRef = useRef<HTMLDivElement>(null);
  // Read the latest onClose without re-running the effect (which would steal focus).
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!open) return undefined;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panelRef.current?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab" || !panelRef.current) return;
      const focusable = Array.from(panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE));
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!first || !last) {
        event.preventDefault();
        return;
      }
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
      previouslyFocused?.focus?.();
    };
  }, [open]);

  return panelRef;
}

function Overlay({
  open,
  onClose,
  title,
  subtitle,
  children,
  panelClassName,
}: OverlayProps & { panelClassName: string }) {
  const panelRef = useOverlayBehaviour(open, onClose);
  const titleId = useId();
  if (!open) return null;

  return createPortal(
    <>
      <div className={styles.backdrop} onClick={onClose} aria-hidden="true" />
      <div
        ref={panelRef}
        className={`${styles.panel} ${panelClassName}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
      >
        <header className={styles.header}>
          <div>
            <h2 className={styles.title} id={titleId}>
              {title}
            </h2>
            {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
          </div>
          <Button variant="ghost" size="sm" icon={X} iconOnly onClick={onClose}>
            Close
          </Button>
        </header>
        <div className={styles.body}>{children}</div>
      </div>
    </>,
    document.body,
  );
}

export function Modal(props: OverlayProps) {
  return <Overlay {...props} panelClassName={styles.modal ?? ""} />;
}

export function Drawer({ side = "right", ...props }: OverlayProps & { side?: "left" | "right" }) {
  return <Overlay {...props} panelClassName={`${styles.drawer} ${styles[side]}`} />;
}
