import { useEffect, useState } from "react";

/**
 * Subscribes to a CSS media query and returns whether it matches.
 * Shared by any component that needs to branch behavior (not just
 * styling) between mobile / tablet / desktop.
 */
export function useMediaQuery(query) {
  const getMatch = () => (typeof window !== "undefined" ? window.matchMedia(query).matches : false);
  const [matches, setMatches] = useState(getMatch);

  useEffect(() => {
    const mql = window.matchMedia(query);
    const listener = (e) => setMatches(e.matches);
    mql.addEventListener("change", listener);
    setMatches(mql.matches);
    return () => mql.removeEventListener("change", listener);
  }, [query]);

  return matches;
}

export const useIsMobile = () => useMediaQuery("(max-width: 767px)");
export const useIsTablet = () => useMediaQuery("(min-width: 768px) and (max-width: 1023px)");
export const useIsDesktop = () => useMediaQuery("(min-width: 1024px)");
