import { messages as es, spanishName } from './locales/es';
import { messages as de } from './locales/de';
import { messages as en } from './locales/en';
import { messages as fr } from './locales/fr';
import { messages as it } from './locales/it';
import { messages as nl } from './locales/nl';
import { messages as pl } from './locales/pl';

export type Language = 'es' | 'en' | 'de' | 'fr' | 'it' | 'nl' | 'pl';

export const languages: Array<{ value: Language; label: string }> = [
  { value: 'es', label: spanishName },
  { value: 'en', label: 'English' },
  { value: 'de', label: 'Deutsch' },
  { value: 'fr', label: 'Français' },
  { value: 'it', label: 'Italiano' },
  { value: 'nl', label: 'Nederlands' },
  { value: 'pl', label: 'Polski' },
];

export const languageLocales: Record<Language, string> = {
  es: 'es-ES',
  en: 'en-GB',
  de: 'de-DE',
  fr: 'fr-FR',
  it: 'it-IT',
  nl: 'nl-NL',
  pl: 'pl-PL',
};

type Messages = Record<string, string>;

const messages: Record<Language, Messages> = {
  es,
  en,
  de,
  fr,
  it,
  nl,
  pl,
};

export function translate(language: Language, key: string): string {
  return messages[language][key] ?? messages.en[key] ?? key;
}

export function isLanguage(value: string): value is Language {
  return languages.some((item) => item.value === value);
}

