import axios from 'axios';

// Resolve API base URL from Vite environment or default to local FastAPI host
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

/**
 * Shared Axios instance configured for MassCommAI backend services.
 */
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
});

/**
 * Performs a health-check request to verify backend and database status.
 * @returns {Promise<{healthy: boolean, status: string, database: string, version: string, error?: string}>}
 */
export const checkHealth = async () => {
  try {
    const response = await apiClient.get('/health');
    return {
      healthy: response.status === 200 && response.data.status === 'healthy',
      status: response.data.status,
      database: response.data.database,
      version: response.data.version,
    };
  } catch (error) {
    if (error.response) {
      // Server responded with an error code (e.g., 503 degraded)
      return {
        healthy: false,
        status: error.response.data?.status || 'degraded',
        database: error.response.data?.database || 'disconnected',
        version: error.response.data?.version || 'unknown',
        error: `HTTP ${error.response.status}`,
      };
    } else if (error.request) {
      // Network failure or backend server offline
      return {
        healthy: false,
        status: 'unreachable',
        database: 'unknown',
        version: 'unknown',
        error: 'Backend service unreachable at ' + API_BASE_URL,
      };
    } else {
      return {
        healthy: false,
        status: 'error',
        database: 'unknown',
        version: 'unknown',
        error: error.message,
      };
    }
  }
};

// Guard flag to prevent repeated health-check requests in React StrictMode development
let hasLoggedDiagnostic = false;

/**
 * Diagnostic logger to verify connectivity during application boot.
 */
export const logDiagnosticHealth = async () => {
  if (hasLoggedDiagnostic) return;
  hasLoggedDiagnostic = true;

  try {
    const result = await checkHealth();
    if (result.healthy) {
      console.log(
        `%c[MassCommAI]%c Backend connection established: status=${result.status}, database=${result.database}, version=${result.version}`,
        'color: #4f46e5; font-weight: bold;',
        'color: #10b981;'
      );
    } else {
      console.warn(
        `%c[MassCommAI]%c Backend health check reported degraded/disconnected state: status=${result.status}, database=${result.database} (${result.error || 'degraded'})`,
        'color: #4f46e5; font-weight: bold;',
        'color: #f59e0b;'
      );
    }
    return result;
  } catch (err) {
    console.error(
      `%c[MassCommAI]%c Health check probe failed: ${err.message}`,
      'color: #4f46e5; font-weight: bold;',
      'color: #ef4444;'
    );
  }
};

export default apiClient;
