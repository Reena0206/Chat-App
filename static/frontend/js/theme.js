/**
 * theme.js — ChatApp Light / Dark Mode Manager
 * ─────────────────────────────────────────────
 * Strategy:
 *   • Reads / writes 'chatapp-theme' in localStorage ('dark' | 'light')
 *   • Adds/removes the 'dark' and 'light' class on <html>
 *   • Updates the theme toggle button icon (Sun ↔ Moon)
 *   • Called from base.html BEFORE other scripts so it is always available
 *   • The flash-prevention snippet in base.html <head> runs BEFORE this
 *     file loads, so there is never a white/dark flash on page load.
 */

// ─── Constants ────────────────────────────────────────────────────────────────
const THEME_KEY  = 'chatapp-theme';
const DARK_MODE  = 'dark';
const LIGHT_MODE = 'light';

// ─── Read the currently stored theme (default: dark) ─────────────────────────
function getSavedTheme() {
    return localStorage.getItem(THEME_KEY) || DARK_MODE;
}

// ─── Apply a theme to <html> and update all toggle buttons ───────────────────
function applyTheme(theme) {
    const html = document.documentElement;

    if (theme === LIGHT_MODE) {
        html.classList.remove(DARK_MODE);
        html.classList.add(LIGHT_MODE);
    } else {
        html.classList.remove(LIGHT_MODE);
        html.classList.add(DARK_MODE);
    }

    localStorage.setItem(THEME_KEY, theme);

    // Update every theme-btn on the page (navbar + any sidebar copy)
    document.querySelectorAll('[data-theme-btn]').forEach(function (btn) {
        _syncToggleButton(btn, theme);
    });
}

// ─── Toggle between light and dark ───────────────────────────────────────────
function toggleTheme() {
    var current = getSavedTheme();
    applyTheme(current === DARK_MODE ? LIGHT_MODE : DARK_MODE);
}

// ─── Sync a single toggle button's aria-label & title ────────────────────────
function _syncToggleButton(btn, theme) {
    if (!btn) return;
    if (theme === DARK_MODE) {
        btn.setAttribute('aria-label', 'Switch to light mode');
        btn.setAttribute('title',      'Switch to light mode');
    } else {
        btn.setAttribute('aria-label', 'Switch to dark mode');
        btn.setAttribute('title',      'Switch to dark mode');
    }
}

// ─── On DOM ready: wire up all toggle buttons ─────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
    var theme = getSavedTheme();

    // Ensure classes are correct (flash-prevention already set them,
    // but this keeps them in sync if the DOM rehydrates)
    applyTheme(theme);

    // Wire click handlers for every [data-theme-btn]
    document.querySelectorAll('[data-theme-btn]').forEach(function (btn) {
        btn.addEventListener('click', toggleTheme);
        _syncToggleButton(btn, theme);
    });
});
