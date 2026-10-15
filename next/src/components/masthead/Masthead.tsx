/** Site header: brand, nav and the theme tools (src/components/picker). */
import Link from 'next/link';
import { ThemeTools } from '../picker/ThemeTools';
import { NavLink } from './NavLink';

export function Masthead() {
  return (
    <header className="masthead">
      <Link className="brand" href="/">
        Walldye
      </Link>
      <nav className="nav" aria-label="Site">
        <NavLink href="/">Index</NavLink>
        <NavLink href="/about">About</NavLink>
        <a className="sc" href="https://github.com/nickolaj-jepsen/walldye">
          GitHub
        </a>
      </nav>
      <div className="tools">
        <ThemeTools />
      </div>
    </header>
  );
}
