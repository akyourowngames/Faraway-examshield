"use client";

import { useI18n, type Locale } from "@/lib/i18n";

const LOCALES: { code: Locale; label: string }[] = [
  { code: "en", label: "EN" },
  { code: "hi", label: "हिंदी" },
];

export function LanguageSwitcher() {
  const { locale, setLocale } = useI18n();
  return (
    <div
      role="group"
      aria-label="Select language"
      className="flex items-center gap-1"
    >
      {LOCALES.map((l) => (
        <button
          key={l.code}
          type="button"
          aria-pressed={locale === l.code}
          onClick={() => setLocale(l.code)}
          className={`px-2 py-1 text-[10px] font-bold uppercase tracking-[0.2em] ${
            locale === l.code ? "bg-white text-black" : "text-white/50 hover:text-white"
          }`}
        >
          {l.label}
        </button>
      ))}
    </div>
  );
}
