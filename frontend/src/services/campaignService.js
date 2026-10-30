import api from './api';

/**
 * Fetch supported campaign metadata (types, priorities, statuses, channels).
 */
export async function getCampaignMeta() {
  const response = await api.get('/campaigns/meta');
  return response.data;
}

/**
 * Fetch paginated campaigns with search, status, type, and priority filters.
 */
export async function listCampaigns(params = {}) {
  const response = await api.get('/campaigns', { params });
  return response.data;
}

/**
 * Fetch a single campaign by ID with attached segments and live reach metrics.
 */
export async function getCampaign(campaignId) {
  const response = await api.get(`/campaigns/${campaignId}`);
  return response.data;
}

/**
 * Create a new campaign in Draft status.
 */
export async function createCampaign(data) {
  const response = await api.post('/campaigns', data);
  return response.data;
}

/**
 * Update an existing campaign (only Draft or In Review).
 */
export async function updateCampaign(campaignId, data) {
  const response = await api.put(`/campaigns/${campaignId}`, data);
  return response.data;
}

/**
 * Transition campaign lifecycle state (Draft -> In Review/Approved/Archived, etc.).
 */
export async function transitionCampaignStatus(campaignId, status) {
  const response = await api.patch(`/campaigns/${campaignId}/status`, { status });
  return response.data;
}

/**
 * Permanently delete a campaign (only Draft or Archived).
 */
export async function deleteCampaign(campaignId) {
  const response = await api.delete(`/campaigns/${campaignId}`);
  return response.data;
}

/**
 * Generate simulated multi-channel previews with default or specific recipient.
 */
export async function previewCampaign(campaignId, audienceMemberId = null) {
  const params = {};
  if (audienceMemberId) params.audience_member_id = audienceMemberId;
  const response = await api.get(`/campaigns/${campaignId}/preview`, { params });
  return response.data;
}

/**
 * Generate simulated multi-channel previews with custom placeholder overrides.
 */
export async function previewCampaignCustom(campaignId, payload = {}) {
  const response = await api.post(`/campaigns/${campaignId}/preview`, payload);
  return response.data;
}

