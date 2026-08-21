import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import en from "./en";
import ja from "./ja";
import ko from "./ko";
import es from "./es";
import zh from "./zh";
import zhTW from "./zh-TW";

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: { en: { translation: en }, ja: { translation: ja }, ko: { translation: ko }, es: { translation: es }, zh: { translation: zh }, "zh-TW": { translation: zhTW } },
    fallbackLng: "en",
    interpolation: { escapeValue: false },
    detection: {
      order: ["localStorage", "navigator"],
      caches: ["localStorage"],
    },
  });

export default i18n;
