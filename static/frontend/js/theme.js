/**
 * PingNest Light / Dark Mode Manager
 *
 * Reads and writes the saved theme in localStorage, applies the matching
 * class to <html>, and keeps every theme toggle button in sync.
 */

const THEME_KEY = 'pingnest-theme';
const DARK_MODE = 'dark';
const LIGHT_MODE = 'light';

function getSavedTheme() {
    return localStorage.getItem(THEME_KEY) || DARK_MODE;
}

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

    document.querySelectorAll('[data-theme-btn]').forEach(function (btn) {
        syncToggleButton(btn, theme);
    });
}

function toggleTheme() {
    const current = getSavedTheme();
    applyTheme(current === DARK_MODE ? LIGHT_MODE : DARK_MODE);
}

function syncToggleButton(btn, theme) {
    if (!btn) return;

    if (theme === DARK_MODE) {
        btn.setAttribute('aria-label', 'Switch to light mode');
        btn.setAttribute('title', 'Switch to light mode');
    } else {
        btn.setAttribute('aria-label', 'Switch to dark mode');
        btn.setAttribute('title', 'Switch to dark mode');
    }
}

document.addEventListener('DOMContentLoaded', function () {
    const theme = getSavedTheme();
    applyTheme(theme);

    document.querySelectorAll('[data-theme-btn]').forEach(function (btn) {
        btn.addEventListener('click', toggleTheme);
        syncToggleButton(btn, theme);
    });
});