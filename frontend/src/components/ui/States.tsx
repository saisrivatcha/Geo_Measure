import { FileQuestion, Inbox, RefreshCw, TriangleAlert, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { ApiError } from "@/services/api";

import { Button } from "./Button";
import styles from "./States.module.css";

interface StateProps {
  icon?: LucideIcon;
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  centered?: boolean;
}

function StateFrame({
  icon: Icon,
  title,
  description,
  actions,
  centered = true,
  tone,
  role,
  footnote,
}: StateProps & { tone?: "danger"; role?: string; footnote?: ReactNode }) {
  return (
    <div
      className={[styles.state, centered ? styles.centered : "", tone ? styles[tone] : ""].join(" ")}
      role={role}
    >
      {Icon && (
        <span className={styles.icon} aria-hidden="true">
          <Icon size={20} />
        </span>
      )}
      <h2 className={styles.title}>{title}</h2>
      {description && <p className={styles.description}>{description}</p>}
      {footnote}
      {actions && <div className={styles.actions}>{actions}</div>}
    </div>
  );
}

/** Nothing to show yet; the actions say how to change that. */
export function EmptyState({ icon = Inbox, ...props }: StateProps) {
  return <StateFrame icon={icon} {...props} />;
}

interface ErrorStateProps extends Omit<StateProps, "description"> {
  error?: unknown;
  /** Shown when the error is not an API error with its own message. */
  description?: ReactNode;
  onRetry?: () => void;
}

/** Explains what failed (using the API's message when it has one) and offers a retry. */
export function ErrorState({ error, title, description, onRetry, actions, ...props }: ErrorStateProps) {
  const apiError = error instanceof ApiError ? error : null;
  const message = apiError?.isNetworkError
    ? "The API is unavailable. Check that the backend is running, then retry."
    : (apiError?.message ?? description);

  return (
    <StateFrame
      icon={TriangleAlert}
      tone="danger"
      role="alert"
      title={title}
      description={message}
      footnote={apiError && !apiError.isNetworkError ? <p className={styles.code}>Error code {apiError.code}</p> : null}
      actions={
        <>
          {onRetry && (
            <Button icon={RefreshCw} onClick={onRetry}>
              Retry
            </Button>
          )}
          {actions}
        </>
      }
      {...props}
    />
  );
}

export function NotFoundState({ title = "Not found", description, actions }: Partial<StateProps>) {
  return <StateFrame icon={FileQuestion} title={title} description={description} actions={actions} />;
}
