import { apiClient } from './api';

/**
 * Submits user registration payload to the FastAPI backend.
 */
export const registerUser = async (userData) => {
  try {
    const payload = {
      full_name: userData.full_name?.trim(),
      email: userData.email?.trim().toLowerCase(),
      phone: userData.phone?.trim() || null,
      organization: userData.organization?.trim() || null,
      password: userData.password,
      role_request: 'Communication Team',
    };

    const response = await apiClient.post('/auth/register', payload);
    return {
      success: true,
      data: response.data,
    };
  } catch (error) {
    let errorMessage = 'Registration could not be completed. Please try again.';

    if (error.response) {
      const { status, data } = error.response;
      if (status === 409) {
        errorMessage = data?.detail || 'An account with this email address already exists.';
      } else if (status === 422) {
        if (Array.isArray(data?.detail)) {
          errorMessage = data.detail.map((err) => err.msg.replace('Value error, ', '')).join('. ');
        } else {
          errorMessage = data?.detail || 'Invalid registration data provided.';
        }
      } else if (data?.detail && typeof data.detail === 'string') {
        errorMessage = data.detail;
      }
      return {
        success: false,
        error: errorMessage,
        statusCode: status,
      };
    } else if (error.request) {
      return {
        success: false,
        error: 'Unable to connect to the backend server. Please verify the API is running.',
        statusCode: 0,
      };
    }

    return {
      success: false,
      error: error.message || errorMessage,
      statusCode: 500,
    };
  }
};

/**
 * Authenticates user credentials and retrieves JWT access token.
 */
export const loginUser = async ({ email, password }) => {
  try {
    const response = await apiClient.post('/auth/login', {
      email: email.trim().toLowerCase(),
      password,
    });
    return {
      success: true,
      data: response.data,
    };
  } catch (error) {
    let errorMessage = 'Login failed. Please verify your credentials.';
    if (error.response) {
      const { status, data } = error.response;
      if (status === 401) {
        errorMessage = data?.detail || 'Invalid email or password.';
      } else if (status === 422) {
        errorMessage = 'Please enter a valid email address and password.';
      } else if (data?.detail) {
        errorMessage = typeof data.detail === 'string' ? data.detail : 'Invalid login credentials.';
      }
      return {
        success: false,
        error: errorMessage,
        statusCode: status,
      };
    } else if (error.request) {
      return {
        success: false,
        error: 'Unable to connect to authentication service. Please check your connection.',
        statusCode: 0,
      };
    }
    return {
      success: false,
      error: error.message || errorMessage,
      statusCode: 500,
    };
  }
};

/**
 * Fetches current authenticated user profile using Bearer token.
 */
export const getCurrentUser = async () => {
  try {
    const response = await apiClient.get('/auth/me');
    return {
      success: true,
      data: response.data,
    };
  } catch (error) {
    return {
      success: false,
      error: error.response?.data?.detail || 'Session expired or invalid.',
      statusCode: error.response?.status || 500,
    };
  }
};
