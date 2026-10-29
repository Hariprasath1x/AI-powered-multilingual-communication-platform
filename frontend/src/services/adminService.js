import { apiClient } from './api';

/**
 * Admin Service for managing platform users, roles, and account statuses.
 */
export const adminService = {
  /**
   * Fetch paginated list of registered users.
   */
  async listUsers({ page = 1, pageSize = 10, search = '', role = '' } = {}) {
    const params = new URLSearchParams();
    params.append('page', page);
    params.append('page_size', pageSize);
    if (search.trim()) params.append('search', search.trim());
    if (role.trim()) params.append('role', role.trim());

    try {
      const response = await apiClient.get(`/admin/users?${params.toString()}`);
      return {
        success: true,
        data: response.data,
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Failed to load user directory.',
        statusCode: error.response?.status,
      };
    }
  },

  /**
   * Update a user's role.
   */
  async updateUserRole(userId, roleName) {
    try {
      const response = await apiClient.put(`/admin/users/${userId}/role`, {
        role_name: roleName,
      });
      return {
        success: true,
        data: response.data,
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Failed to update user role.',
        statusCode: error.response?.status,
      };
    }
  },

  /**
   * Toggle a user's active status.
   */
  async updateUserStatus(userId, isActive) {
    try {
      const response = await apiClient.patch(`/admin/users/${userId}/status`, {
        is_active: isActive,
      });
      return {
        success: true,
        data: response.data,
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Failed to update account status.',
        statusCode: error.response?.status,
      };
    }
  },
};

export default adminService;

