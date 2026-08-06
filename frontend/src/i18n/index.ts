/**
 * Active UI locale helper until a full i18n stack is wired.
 * Email *content* locale is separate (stored on smtp email_templates.locale).
 */
import { messages as es } from "./es";
import { messages as en } from "./en";

export type UiLocale = "es" | "en";

const catalogs = { es, en } as const;

let activeLocale: UiLocale = "es";

export function setUiLocale(locale: UiLocale) {
  activeLocale = locale in catalogs ? locale : "es";
}

export function getUiLocale(): UiLocale {
  return activeLocale;
}

/** Return the message catalog for the active UI locale. */
export function t() {
  return catalogs[activeLocale];
}
