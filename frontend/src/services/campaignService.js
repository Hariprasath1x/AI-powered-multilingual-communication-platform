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
 * Clone an existing campaign into a new Draft campaign.
 */
export async function cloneCampaign(campaignId) {
  const response = await api.post(`/campaigns/${campaignId}/clone`);
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

/**
 * Task 12: Trigger end-to-end 5-stage content pipeline (Generate -> Translate -> Personalize -> Tone Optimize -> Review).
 */
export async function runContentPipeline(campaignId, payload) {
  const response = await api.post(`/campaigns/${campaignId}/content/pipeline`, payload);
  return response.data;
}

/**
 * Task 12: Fetch live status and stage progress of a content pipeline run.
 */
export async function getPipelineRun(campaignId, runId) {
  const response = await api.get(`/campaigns/${campaignId}/content/pipeline/${runId}`);
  return response.data;
}

/**
 * Task 12: List all historical content pipeline runs for a campaign.
 */
export async function listPipelineRuns(campaignId) {
  const response = await api.get(`/campaigns/${campaignId}/content/pipeline`);
  return response.data;
}

/**
 * Task 12: Resume a failed or partially completed pipeline run from its interruption point.
 */
export async function resumePipelineRun(campaignId, runId, payload = {}) {
  const response = await api.post(`/campaigns/${campaignId}/content/pipeline/${runId}/resume`, payload);
  return response.data;
}


