"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useSyncExternalStore } from "react";
import { THEME_STORAGE_KEY as STORAGE_KEY } from "@/lib/theme-script";

export type ThemeChoice = "light" | "dark" | "system";

const EVENT = "automata-theme-change";

function readChoice(): ThemeChoice {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return value === "light" || value === "dark" ? value : "system";
  } catch {
    return "system";
  }
}

function darkQuery(): MediaQueryList | null {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-color-scheme: dark)")
    : null;
}

function systemDark(): boolean {
  return darkQuery()?.matches ?? false;
}

function apply(choice: ThemeChoice) {
  const dark = choice === "dark" || (choice === "system" && systemDark());
  document.documentElement.classList.toggle("dark", dark);
}

function subscribe(onChange: () => void) {
  const media = darkQuery();
  const onSystem = () => {
    if (readChoice() === "system") apply("system");
    onChange();
  };
  media?.addEventListener("change", onSystem);
  window.addEventListener(EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    media?.removeEventListener("change", onSystem);
    window.removeEventListener(EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

export function setTheme(choice: ThemeChoice) {
  try {
    if (choice === "system") localStorage.removeItem(STORAGE_KEY);
    else localStorage.setItem(STORAGE_KEY, choice);
  } catch {
    // sem storage (modo privado): vale só nesta aba
  }
  apply(choice);
  window.dispatchEvent(new Event(EVENT));
}

export function useTheme(): { choice: ThemeChoice; resolved: "light" | "dark" } {
  const choice = useSyncExternalStore(subscribe, readChoice, () => "system" as const);
  const dark = useSyncExternalStore(
    subscribe,
    () => document.documentElement.classList.contains("dark"),
    () => false,
  );
  return { choice, resolved: dark ? "dark" : "light" };
}

const NEXT: Record<ThemeChoice, ThemeChoice> = { system: "light", light: "dark", dark: "system" };
const LABEL: Record<ThemeChoice, string> = {
  light: "Tema claro",
  dark: "Tema escuro",
  system: "Tema do sistema",
};

export function ThemeToggle() {
  const { choice } = useTheme();
  const Icon = choice === "light" ? Sun : choice === "dark" ? Moon : Monitor;
  return (
    <button
      type="button"
      onClick={() => setTheme(NEXT[choice])}
      aria-label={`${LABEL[choice]}. Trocar para ${LABEL[NEXT[choice]].toLowerCase()}`}
      title={LABEL[choice]}
      className="text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:ring-ring/50 flex h-7 w-7 items-center justify-center rounded-md transition-colors focus-visible:ring-2 focus-visible:outline-none"
    >
      <Icon className="h-4 w-4" />
    </button>
  );
}
