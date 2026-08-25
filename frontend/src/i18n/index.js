import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import es from "./es.json";
import en from "./en.json";

const idiomaGuardado = localStorage.getItem("archivum_idioma");

i18n.use(initReactI18next).init({
  resources: { es: { translation: es }, en: { translation: en } },
  lng: idiomaGuardado || "es",
  fallbackLng: "es",
  interpolation: { escapeValue: false },
});

export function cambiarIdioma(idioma) {
  i18n.changeLanguage(idioma);
  localStorage.setItem("archivum_idioma", idioma);
}

export default i18n;
