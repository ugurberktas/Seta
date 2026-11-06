/**
 * frontend/js/auth.js
 * -------------------
 * Authentication service handling login, session verification, and logout.
 * Never stores credentials in localStorage or sessionStorage.
 */

import { api } from './api.js';
import { state, t } from './state.js';

export async function checkAuth() {
  try {
    const user = await api.get('/api/auth/me');
    if (user && user.authenticated) {
      state.setUser(user.username);
      return true;
    }
  } catch {
    state.setUser(null);
  }
  return false;
}

export async function login(username, password) {
  if (!username || !password) {
    throw new Error(t('invalid_credentials') || 'Please enter both username and password.');
  }

  const response = await api.post('/api/auth/login', {
    username: username.trim(),
    password,
  });

  if (response && response.authenticated) {
    state.setUser(response.username);
    return response;
  }
  throw new Error('Authentication failed.');
}

export async function logout() {
  try {
    await api.post('/api/auth/logout');
  } catch (err) {
    console.warn('Logout request failed:', err);
  } finally {
    state.resetOnLogout();
  }
}

