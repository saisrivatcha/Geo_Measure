/** Wordmark: a survey traverse (three stations joined by measured legs). */
export function LogoMark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="7" fill="#1d3a57" />
      <path d="M8 23 L15 9 L24 20 Z" fill="none" stroke="#f3f5f7" strokeWidth="2.2" strokeLinejoin="round" />
      <circle cx="8" cy="23" r="2.2" fill="#d08c4a" />
      <circle cx="15" cy="9" r="2.2" fill="#d08c4a" />
      <circle cx="24" cy="20" r="2.2" fill="#d08c4a" />
    </svg>
  );
}
