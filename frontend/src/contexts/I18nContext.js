import { createContext, useContext, useState, useCallback } from 'react';
import en from '@/i18n/en.json';
import ru from '@/i18n/ru.json';
import tk from '@/i18n/tk.json';

const translations = { en, ru, tk };
const I18nContext = createContext(null);

export function I18nProvider({ children }) {
  const [lang, setLang] = useState(() => localStorage.getItem('lightline_lang') || 'en');

  const changeLang = useCallback((newLang) => {
    setLang(newLang);
    localStorage.setItem('lightline_lang', newLang);
  }, []);

  const t = useCallback((key) => {
    const keys = key.split('.');
    let value = translations[lang];
    for (const k of keys) {
      value = value?.[k];
    }
    return value || key;
  }, [lang]);

  return (
    <I18nContext.Provider value={{ lang, setLang: changeLang, t }}>
      {children}
    </I18nContext.Provider>
  );
}

export const useI18n = () => {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error('useI18n must be used within I18nProvider');
  return ctx;
};
