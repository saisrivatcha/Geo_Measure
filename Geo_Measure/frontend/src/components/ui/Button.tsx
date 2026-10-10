import type { LucideIcon } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Link, type LinkProps } from "react-router-dom";

import styles from "./Button.module.css";

type Variant = "primary" | "secondary" | "ghost";
type Size = "md" | "sm";

interface CommonProps {
  variant?: Variant;
  size?: Size;
  icon?: LucideIcon;
  /** Render only the icon; ``label`` becomes the accessible name. */
  iconOnly?: boolean;
  children?: ReactNode;
}

function classes(variant: Variant, size: Size, iconOnly: boolean, extra?: string): string {
  return [
    styles.button,
    styles[variant],
    size === "sm" ? styles.sm : "",
    iconOnly ? styles.iconOnly : "",
    extra ?? "",
  ]
    .filter(Boolean)
    .join(" ");
}

export interface ButtonProps extends CommonProps, ButtonHTMLAttributes<HTMLButtonElement> {}

export function Button({
  variant = "secondary",
  size = "md",
  icon: Icon,
  iconOnly = false,
  className,
  children,
  type = "button",
  ...rest
}: ButtonProps) {
  return (
    <button type={type} className={classes(variant, size, iconOnly, className)} {...rest}>
      {Icon && <Icon className={styles.icon} size={size === "sm" ? 15 : 16} aria-hidden="true" />}
      {iconOnly ? <span className="visually-hidden">{children}</span> : children}
    </button>
  );
}

export interface ButtonLinkProps extends CommonProps, Omit<LinkProps, "children"> {}

export function ButtonLink({
  variant = "secondary",
  size = "md",
  icon: Icon,
  iconOnly = false,
  className,
  children,
  ...rest
}: ButtonLinkProps) {
  return (
    <Link className={classes(variant, size, iconOnly, className)} {...rest}>
      {Icon && <Icon className={styles.icon} size={size === "sm" ? 15 : 16} aria-hidden="true" />}
      {iconOnly ? <span className="visually-hidden">{children}</span> : children}
    </Link>
  );
}
