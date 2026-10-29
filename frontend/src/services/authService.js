import { apiClient } from './api';

/**
 * Submits user registration payload to the FastAPI backend.
 * @param {Object} userData - Form values: full_name, email, phone, organization, password, role_request
 * @returns {Promise<{success: boolean, data?: any, error?: string, statusCode?: number}>}
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
          // Format validation error list nicely
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

