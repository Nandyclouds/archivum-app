import { NavLink } from "react-router-dom";
import { LayoutDashboard, User, Search, Library, Archive, Cloud } from "lucide-react";

const TABS = [
  { to: "/", label: "Panel", icon: LayoutDashboard, end: true },
  { to: "/perfil", label: "Perfil", icon: User },
  { to: "/buscar", label: "Buscar", icon: Search },
  { to: "/colecciones", label: "Colecciones", icon: Library },
  { to: "/ao3", label: "AO3", icon: Cloud },
  { to: "/archivo", label: "Archivo", icon: Archive },
];

export function NavBar() {
  return (
    <nav className="arv-scrollnav">
      {TABS.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) => `arv-tab${isActive ? " active" : ""}`}
        >
          <Icon size={15} />
          <span>{label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
