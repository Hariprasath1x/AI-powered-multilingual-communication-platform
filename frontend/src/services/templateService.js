import api from './api';

/**
 * Fetch supported template categories and permitted placeholder tokens.
 */
export async function getTemplateCategories() {
  const response = await api.get('/templates/categories');
  return response.data;
}

/**
 * Fetch paginated templates with search, category, and language filters.
 */
export async function listTemplates(params = {}) {
  const response = await api.get('/templates', { params });
  return response.data;
}

/**
 * Fetch a single template by ID.
 */
export async function getTemplate(templateId) {
  const response = await api.get(`/templates/${templateId}`);
  return response.data;
}

/**
 * Create a new communication template.
 */
export async function createTemplate(data) {
  const response = await api.post('/templates', data);
  return response.data;
}

/**
 * Update an existing communication template.
 */
export async function updateTemplate(templateId, data) {
  const response = await api.put(`/templates/${templateId}`, data);
  return response.data;
}

/**
 * Delete a communication template.
 */
export async function deleteTemplate(templateId) {
  const response = await api.delete(`/templates/${templateId}`);
  return response.data;
}

