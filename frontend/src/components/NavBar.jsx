import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { LayoutDashboard, User, Search, Library, Archive, Cloud, Bell, Share2 } from "lucide-react";
import { useNovedades } from "../lib/NovedadesContext";

const TABS = [
  { to: "/", key: "perfil", icon: User, end: true },
  { to: "/panel", key: "panel", icon: LayoutDashboard },
  { to: "/buscar", key: "buscar", icon: Search },
  { to: "/colecciones", key: "colecciones", icon: Library },
  { to: "/recomendar", key: "recomendar", icon: Share2 },
  { to: "/novedades", key: "novedades", icon: Bell },
  { to: "/ao3", key: "ao3", icon: Cloud },
  { to: "/archivo", key: "archivo", icon: Archive },
];

export function NavBar({ className = "", minimal = false }) {
  const { t } = useTranslation();
  const { lista } = useNovedades();
  const noLeidas = lista.length;
  // En Perfil la barra de abajo solo muestra volver a Perfil (ya estás acá,
  // pero sirve de referencia) y saltar al Panel, desde donde se accede al
  // resto de las pestañas con la barra normal de arriba.
  const tabs = minimal ? TABS.filter((tab) => tab.key === "perfil" || tab.key === "panel") : TABS;

  return (
    <nav
      className={`arv-scrollnav${minimal ? " arv-scrollnav-minimal" : ""}${className ? ` ${className}` : ""}`}
    >
      {tabs.map(({ to, key, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) => `arv-tab${isActive ? " active" : ""}`}
          aria-label={minimal ? t(`nav.${key}`) : undefined}
        >
          <Icon size={minimal ? 20 : 15} />
          {!minimal && <span>{t(`nav.${key}`)}</span>}
          {key === "novedades" && noLeidas > 0 && <span className="arv-tab-badge">{noLeidas}</span>}
        </NavLink>
      ))}
    </nav>
  );
}
