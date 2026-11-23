/**
 * Route transition.
 *
 * A template remounts on every navigation, so this gives each page a short
 * rise as it arrives. It is deliberately 260ms and 6px: long enough to feel
 * like a transition, short enough that nobody is waiting on it to read a
 * figure. Reduced-motion collapses it to nothing via the global rule in
 * globals.css.
 */
export default function Template({ children }: { children: React.ReactNode }) {
  return <div className="animate-fade-rise">{children}</div>;
}
