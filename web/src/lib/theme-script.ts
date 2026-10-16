export const THEME_STORAGE_KEY = "automata-theme";

// Roda no <head> antes da hidratação: aplica a classe certa sem piscar o tema errado.
// Fica fora do módulo "use client" para o layout (server component) receber a string.
export const THEME_SCRIPT = `(function(){try{var t=localStorage.getItem("${THEME_STORAGE_KEY}");var d=t==="dark"||((!t||t==="system")&&matchMedia("(prefers-color-scheme: dark)").matches);document.documentElement.classList.toggle("dark",d);}catch(e){}})();`;
