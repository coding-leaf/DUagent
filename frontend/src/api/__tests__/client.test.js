import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { toast } from 'sonner';
import apiClient from '../client';

vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
  },
}));

const originalLocation = window.location;

function setMockLocation() {
  delete window.location;
  window.location = { href: 'http://localhost/current' };
}

function restoreLocation() {
  window.location = originalLocation;
}

function mockResponse(status, data = {}, headers = {}) {
  apiClient.defaults.adapter = async (config) => ({
    status,
    statusText: String(status),
    data,
    headers,
    config,
  });
}

function mockRejectedResponse(status, data = {}) {
  apiClient.defaults.adapter = async (config) => {
    const error = new Error(`Request failed with status code ${status}`);
    error.config = config;
    error.response = {
      status,
      statusText: String(status),
      data,
      headers: {},
      config,
    };
    throw error;
  };
}

function mockNetworkError(message = 'Network Error') {
  apiClient.defaults.adapter = async (config) => {
    const error = new Error(message);
    error.config = config;
    throw error;
  };
}

describe('apiClient', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    apiClient.defaults.adapter = undefined;
    setMockLocation();
  });

  afterEach(() => {
    restoreLocation();
  });

  it('adds bearer token to outgoing requests when access token exists', async () => {
    localStorage.setItem('access_token', 'token-123');
    let observedAuthorization = '';
    apiClient.defaults.adapter = async (config) => {
      observedAuthorization = config.headers.Authorization;
      return {
        status: 200,
        statusText: '200',
        data: { code: 200 },
        headers: {},
        config,
      };
    };

    await apiClient.get('/profile');

    expect(observedAuthorization).toBe('Bearer token-123');
  });

  it('unwraps successful response data', async () => {
    mockResponse(200, { code: 200, data: { name: '课程' } });

    const response = await apiClient.get('/courses');

    expect(response).toEqual({ code: 200, data: { name: '课程' } });
  });

  it('clears token and redirects to login on 401 without showing toast', async () => {
    localStorage.setItem('access_token', 'expired-token');
    mockRejectedResponse(401, { detail: 'Unauthorized' });

    await expect(apiClient.get('/profile')).rejects.toThrow('401');

    expect(localStorage.getItem('access_token')).toBeNull();
    expect(window.location.href).toBe('/login');
    expect(toast.error).not.toHaveBeenCalled();
  });

  it('shows permission toast on 403', async () => {
    mockRejectedResponse(403, { detail: 'Forbidden' });

    await expect(apiClient.get('/admin')).rejects.toThrow('403');

    expect(toast.error).toHaveBeenCalledWith('权限不足');
  });

  it('shows server error toast on 5xx', async () => {
    mockRejectedResponse(500, { detail: 'Internal Server Error' });

    await expect(apiClient.get('/tasks')).rejects.toThrow('500');

    expect(toast.error).toHaveBeenCalledWith('服务器错误，请稍后重试');
  });

  it('shows network error toast when response is missing', async () => {
    mockNetworkError();

    await expect(apiClient.get('/courses')).rejects.toThrow('Network Error');

    expect(toast.error).toHaveBeenCalledWith('网络错误，请检查您的连接');
  });

  it('does not show global toast for other 4xx responses', async () => {
    mockRejectedResponse(422, { detail: 'Validation error' });

    await expect(apiClient.post('/auth/login')).rejects.toThrow('422');

    expect(toast.error).not.toHaveBeenCalled();
  });
});
