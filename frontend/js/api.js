/**
 * frontend/js/api.js
 * ------------------
 * Centralized API client for all backend communication via /api/...
 * Uses relative paths and includes credentials for session cookies.
 */

const API_BASE = window.API_BASE_URL || '';

class ApiClient {
  constructor(baseUrl = '') {
    this.baseUrl = baseUrl;
    this.onUnauthorized = null;
  }

  setUnauthorizedHandler(callback) {
    this.onUnauthorized = callback;
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const defaultHeaders = {
      'Accept': 'application/json',
    };

    if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
      defaultHeaders['Content-Type'] = 'application/json';
      options.body = JSON.stringify(options.body);
    }

    const config = {
      ...options,
      headers: {
        ...defaultHeaders,
        ...(options.headers || {}),
      },
      credentials: 'include', // Ensure session cookie is sent and received
    };

    let response;
    try {
      response = await fetch(url, config);
    } catch (err) {
      if (err.name === 'AbortError') {
        throw err;
      }
      console.error(`Network error connecting to ${url}:`, err);
      throw new Error('Unable to connect to the server. Please check your network connection.');
    }

    // Handle 401 Unauthorized
    if (response.status === 401) {
      if (this.onUnauthorized && !endpoint.includes('/auth/login')) {
        this.onUnauthorized();
      }
      const data = await this._parseJson(response);
      throw new Error(data.detail || 'Authentication required.');
    }

    // Handle 429 Rate Limit
    if (response.status === 429) {
      const data = await this._parseJson(response);
      throw new Error(data.detail || 'Too many requests. Please wait a moment.');
    }

    // Handle 4xx / 5xx Errors
    if (!response.ok) {
      const data = await this._parseJson(response);
      const errorMsg = data.detail || `Server returned error (${response.status})`;
      throw new Error(errorMsg);
    }

    return this._parseJson(response);
  }

  async _parseJson(response) {
    try {
      return await response.json();
    } catch {
      return {};
    }
  }

  get(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: 'GET' });
  }

  post(endpoint, body, options = {}) {
    return this.request(endpoint, { ...options, method: 'POST', body });
  }

  put(endpoint, body, options = {}) {
    return this.request(endpoint, { ...options, method: 'PUT', body });
  }

  delete(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: 'DELETE' });
  }
}

export const api = new ApiClient(API_BASE);

