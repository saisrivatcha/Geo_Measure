import { Search } from "lucide-react";
import { useId, type InputHTMLAttributes, type SelectHTMLAttributes } from "react";

import styles from "./Field.module.css";

interface SelectFieldProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  hideLabel?: boolean;
  options: { value: string; label: string }[];
}

export function SelectField({ label, hideLabel = false, options, className, ...rest }: SelectFieldProps) {
  const id = useId();
  return (
    <div className={`${styles.field} ${className ?? ""}`}>
      <label htmlFor={id} className={hideLabel ? "visually-hidden" : styles.label}>
        {label}
      </label>
      <select id={id} className={`${styles.control} ${styles.select}`} {...rest}>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}

interface SearchFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label: string;
  hideLabel?: boolean;
}

export function SearchField({ label, hideLabel = false, className, ...rest }: SearchFieldProps) {
  const id = useId();
  return (
    <div className={`${styles.field} ${className ?? ""}`}>
      <label htmlFor={id} className={hideLabel ? "visually-hidden" : styles.label}>
        {label}
      </label>
      <div className={styles.search}>
        <Search size={15} className={styles.searchIcon} aria-hidden="true" />
        <input id={id} type="search" className={`${styles.control} ${styles.searchInput}`} {...rest} />
      </div>
    </div>
  );
}
