import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { LayoutDashboard, User, Search, Library, Archive, Cloud, Bell } from "lucide-react";
import { useNovedades } from "../lib/NovedadesContext";

const TABS = [
  { to: "/perfil", key: "perfil", icon: User },
  { to: "/", key: "panel", icon: LayoutDashboard, end: true },
  { to: "/buscar", key: "buscar", icon: Search },
  { to: "/colecciones", key: "colecciones", icon: Library },
  { to: "/novedades", key: "novedades", icon: Bell },
  { to: "/ao3", key: "ao3", icon: Cloud },
  { to: "/archivo", key: "archivo", icon: Archive },
];

export function NavBar() {
  const { t } = useTranslation();
  const { lista } = useNovedades();
  const noLeidas = lista.length;

  return (
    <nav className="arv-scrollnav">
      {TABS.map(({ to, key, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) => `arv-tab${isActive ? " active" : ""}`}
        >
          <Icon size={15} />
          <span>{t(`nav.${key}`)}</span>
          {key === "novedades" && noLeidas > 0 && <span className="arv-tab-badge">{noLeidas}</span>}
        </NavLink>
      ))}
    </nav>
  );
}
