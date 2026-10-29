import api from './api';

/**
 * Fetch paginated audience members with search and filter parameters.
 */
export async function listAudience(params = {}) {
  const response = await api.get('/audience', { params });
  return response.data;
}

/**
 * Fetch a single audience member by ID.
 */
export async function getAudienceMember(memberId) {
  const response = await api.get(`/audience/${memberId}`);
  return response.data;
}

/**
 * Create a new audience member.
 */
export async function createAudienceMember(data) {
  const response = await api.post('/audience', data);
  return response.data;
}

/**
 * Update an existing audience member.
 */
export async function updateAudienceMember(memberId, data) {
  const response = await api.put(`/audience/${memberId}`, data);
  return response.data;
}

/**
 * Delete an audience member by ID.
 */
export async function deleteAudienceMember(memberId) {
  const response = await api.delete(`/audience/${memberId}`);
  return response.data;
}

/**
 * Fetch aggregated audience distribution statistics.
 */
export async function getAudienceStats() {
  const response = await api.get('/audience/stats');
  return response.data;
}

/**
 * Bulk import audience records from CSV or Excel file.
 */
export async function importAudienceFile(file) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await api.post('/audience/import', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
}

