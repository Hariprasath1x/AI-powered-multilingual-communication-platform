import api from './api';

/**
 * Fetch field metadata and supported operators for segment building.
 */
export async function getSupportedFields() {
  const response = await api.get('/segments/fields');
  return response.data;
}

/**
 * Fetch paginated segments with live audience count.
 */
export async function listSegments(params = {}) {
  const response = await api.get('/segments', { params });
  return response.data;
}

/**
 * Fetch a single segment by ID.
 */
export async function getSegment(segmentId) {
  const response = await api.get(`/segments/${segmentId}`);
  return response.data;
}

/**
 * Create a new audience segment.
 */
export async function createSegment(data) {
  const response = await api.post('/segments', data);
  return response.data;
}

/**
 * Update an existing audience segment.
 */
export async function updateSegment(segmentId, data) {
  const response = await api.put(`/segments/${segmentId}`, data);
  return response.data;
}

/**
 * Delete an audience segment by ID.
 */
export async function deleteSegment(segmentId) {
  const response = await api.delete(`/segments/${segmentId}`);
  return response.data;
}

/**
 * Preview matching audience members for arbitrary rule set (live builder).
 */
export async function previewRules(filterRules, limit = 10, offset = 0) {
  const response = await api.post(
    '/segments/preview',
    { filter_rules: filterRules },
    { params: { limit, offset } }
  );
  return response.data;
}

/**
 * Preview matching audience members for a saved segment by ID.
 */
export async function previewSavedSegment(segmentId, limit = 10, offset = 0) {
  const response = await api.get(`/segments/${segmentId}/preview`, {
    params: { limit, offset },
  });
  return response.data;
}

