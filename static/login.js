/**
 * login.js — Authentication SPA for Ziply.
 *
 * Handles:
 *   - Tab switching (Sign In ↔ Create Account)
 *   - Client-side validation
 *   - POST /api/auth/login and POST /api/auth/register
 *   - JWT storage in localStorage
 *   - Redirect to dashboard on success
 *   - Password show/toggle
 *   - Dark mode init
 */

'use strict';

// ── Constants ─────────────────────────────────────────────────────────────────

const TOKEN_KEY = 'ziply_token';
const USERNAME_KEY = 'ziply_username';

// ── Redirect if already logged in ─────────────────────────────────────────────

if (localStorage.getItem(TOKEN_KEY)) {
  window.location.replace('/');
}

// ── Dark mode (persisted) ────────────────────────────────────────────────────

(function applyTheme() {
  if (localStorage.getItem('ziply_theme') === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
})();

// ── Helpers ───────────────────────────────────────────────────────────────────

function showError(elementId, msgId, message) {
  const el = document.getElementById(elementId);
  const msg = document.getElementById(msgId);
  if (el && msg) {
    msg.textContent = message;
    el.hidden = false;
    el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}

function hideError(elementId) {
  const el = document.getElementById(elementId);
  if (el) el.hidden = true;
}

function setLoading(btnId, spinnerId, loading) {
  const btn = document.getElementById(btnId);
  const spinner = document.getElementById(spinnerId);
  if (btn) btn.disabled = loading;
  if (spinner) spinner.hidden = !loading;
  const text = btn ? btn.querySelector('.btn-text') : null;
  if (text) text.style.opacity = loading ? '0.4' : '1';
}

function showToast(message, type = 'success') {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = message;
  toast.className = `toast toast--${type}`;
  toast.hidden = false;
  setTimeout(() => { toast.hidden = true; }, 3000);
}

// ── Tab switching ─────────────────────────────────────────────────────────────

function activateTab(tab) {
  const isLogin = tab === 'login';
  document.getElementById('tab-login').classList.toggle('auth-tab--active', isLogin);
  document.getElementById('tab-register').classList.toggle('auth-tab--active', !isLogin);
  document.getElementById('tab-login').setAttribute('aria-selected', isLogin ? 'true' : 'false');
  document.getElementById('tab-register').setAttribute('aria-selected', isLogin ? 'false' : 'true');
  document.getElementById('panel-login').hidden = !isLogin;
  document.getElementById('panel-register').hidden = isLogin;
  hideError('login-error');
  hideError('reg-error');
}

document.getElementById('tab-login').addEventListener('click', () => activateTab('login'));
document.getElementById('tab-register').addEventListener('click', () => activateTab('register'));
document.getElementById('go-register').addEventListener('click', () => activateTab('register'));
document.getElementById('go-login').addEventListener('click', () => activateTab('login'));

// ── Password visibility toggle ────────────────────────────────────────────────

document.querySelectorAll('.pwd-toggle').forEach(btn => {
  btn.addEventListener('click', () => {
    const target = document.getElementById(btn.dataset.target);
    if (!target) return;
    const isText = target.type === 'text';
    target.type = isText ? 'password' : 'text';
    btn.textContent = isText ? '👁' : '🙈';
    btn.setAttribute('aria-label', isText ? 'Show password' : 'Hide password');
  });
});

// ── Login form ────────────────────────────────────────────────────────────────

document.getElementById('login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  hideError('login-error');

  const username = document.getElementById('login-username').value.trim();
  const password = document.getElementById('login-password').value;

  if (!username) {
    showError('login-error', 'login-error-msg', 'Username is required.');
    return;
  }
  if (!password) {
    showError('login-error', 'login-error-msg', 'Password is required.');
    return;
  }

  setLoading('login-btn', null, true);
  const btn = document.getElementById('login-btn');
  const spinner = btn.querySelector('.btn-spinner');
  if (spinner) spinner.hidden = false;

  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json();

    if (!res.ok) {
      showError('login-error', 'login-error-msg', data.detail || 'Login failed. Please try again.');
      return;
    }

    localStorage.setItem(TOKEN_KEY, data.access_token);
    localStorage.setItem(USERNAME_KEY, username);
    showToast('Welcome back, ' + username + '! 🎉');
    setTimeout(() => { window.location.replace('/'); }, 600);

  } catch (err) {
    showError('login-error', 'login-error-msg', 'Network error. Please check your connection.');
  } finally {
    setLoading('login-btn', null, false);
    if (spinner) spinner.hidden = true;
  }
});

// ── Register form ─────────────────────────────────────────────────────────────

document.getElementById('register-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  hideError('reg-error');

  const username = document.getElementById('reg-username').value.trim();
  const password = document.getElementById('reg-password').value;
  const confirm = document.getElementById('reg-confirm').value;

  if (!username || username.length < 3) {
    showError('reg-error', 'reg-error-msg', 'Username must be at least 3 characters.');
    return;
  }
  if (!/^[A-Za-z0-9_-]{3,30}$/.test(username)) {
    showError('reg-error', 'reg-error-msg', 'Username may only contain letters, digits, - or _.');
    return;
  }
  if (!password || password.length < 6) {
    showError('reg-error', 'reg-error-msg', 'Password must be at least 6 characters.');
    return;
  }
  if (password !== confirm) {
    showError('reg-error', 'reg-error-msg', 'Passwords do not match.');
    return;
  }

  const btn = document.getElementById('register-btn');
  const spinner = btn.querySelector('.btn-spinner');
  btn.disabled = true;
  if (spinner) spinner.hidden = false;

  try {
    const res = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json();

    if (!res.ok) {
      showError('reg-error', 'reg-error-msg', data.detail || 'Registration failed.');
      return;
    }

    localStorage.setItem(TOKEN_KEY, data.access_token);
    localStorage.setItem(USERNAME_KEY, username);
    showToast('Account created! Welcome to Ziply 🚀');
    setTimeout(() => { window.location.replace('/'); }, 700);

  } catch (err) {
    showError('reg-error', 'reg-error-msg', 'Network error. Please check your connection.');
  } finally {
    btn.disabled = false;
    if (spinner) spinner.hidden = true;
  }
});
