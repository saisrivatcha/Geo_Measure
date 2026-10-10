/** Mirrors the breakpoints documented in tokens.css. */
export const breakpoints = {
  tablet: 768,
  desktop: 1200,
} as const;

export const mediaQueries = {
  mobile: `(max-width: ${breakpoints.tablet - 1}px)`,
  tablet: `(min-width: ${breakpoints.tablet}px) and (max-width: ${breakpoints.desktop - 1}px)`,
  desktop: `(min-width: ${breakpoints.desktop}px)`,
} as const;
