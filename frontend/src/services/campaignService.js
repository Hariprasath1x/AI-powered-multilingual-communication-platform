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

// =========================================================================
// Milestone 3, Task 15: Campaign Scheduling, Automations & Retries
// =========================================================================

/**
 * Schedule an approved campaign for immediate, future, or recurring broadcast.
 */
export async function scheduleCampaign(campaignId, data) {
  const response = await api.post(`/campaigns/${campaignId}/schedule`, data);
  return response.data;
}

/**
 * Get schedule details for a campaign.
 */
export async function getCampaignSchedule(campaignId) {
  const response = await api.get(`/campaigns/${campaignId}/schedule`);
  return response.data;
}

/**
 * List all scheduled campaigns across calendar lifecycle.
 */
export async function listScheduledCampaigns(params = {}) {
  const response = await api.get('/campaigns/scheduled', { params });
  return response.data;
}

/**
 * Pause active campaign schedule.
 */
export async function pauseCampaignSchedule(campaignId) {
  const response = await api.post(`/campaigns/${campaignId}/schedule/pause`);
  return response.data;
}

/**
 * Resume paused campaign schedule.
 */
export async function resumeCampaignSchedule(campaignId) {
  const response = await api.post(`/campaigns/${campaignId}/schedule/resume`);
  return response.data;
}

/**
 * Cancel and remove campaign schedule.
 */
export async function cancelCampaignSchedule(campaignId) {
  const response = await api.delete(`/campaigns/${campaignId}/schedule`);
  return response.data;
}

/**
 * Create automation rule for campaign.
 */
export async function createAutomationRule(campaignId, data) {
  const response = await api.post(`/campaigns/${campaignId}/automation-rules`, data);
  return response.data;
}

/**
 * List automation rules for campaign.
 */
export async function listAutomationRules(campaignId) {
  const response = await api.get(`/campaigns/${campaignId}/automation-rules`);
  return response.data;
}

/**
 * Update automation rule.
 */
export async function updateAutomationRule(campaignId, ruleId, data) {
  const response = await api.put(`/campaigns/${campaignId}/automation-rules/${ruleId}`, data);
  return response.data;
}

/**
 * Delete automation rule.
 */
export async function deleteAutomationRule(campaignId, ruleId) {
  const response = await api.delete(`/campaigns/${campaignId}/automation-rules/${ruleId}`);
  return response.data;
}

/**
 * Get execution history for campaign automation rules.
 */
export async function getAutomationHistory(campaignId) {
  const response = await api.get(`/campaigns/${campaignId}/automation-rules/history`);
  return response.data;
}

/**
 * Trigger immediate evaluation of campaign automation rules.
 */
export async function evaluateAutomationRules(campaignId) {
  const response = await api.post(`/campaigns/${campaignId}/automation-rules/evaluate`);
  return response.data;
}

/**
 * Get comprehensive delivery tracking summary for campaign.
 */
export async function getCampaignDeliverySummary(campaignId) {
  const response = await api.get(`/campaigns/${campaignId}/delivery`);
  return response.data;
}

/**
 * List failed messages for a specific campaign.
 */
export async function listCampaignFailedMessages(campaignId, params = {}) {
  const response = await api.get(`/campaigns/${campaignId}/failed-messages`, { params });
  return response.data;
}

/**
 * List all failed messages across campaigns.
 */
export async function listAllFailedMessages(params = {}) {
  const response = await api.get('/messages/failed', { params });
  return response.data;
}

/**
 * Retry an individual failed message.
 */
export async function retryMessage(messageId, force = true) {
  const response = await api.post(`/messages/${messageId}/retry`, null, { params: { force } });
  return response.data;
}

/**
 * Retry all eligible failed messages for a campaign.
 */
export async function retryCampaignFailedMessages(campaignId) {
  const response = await api.post(`/campaigns/${campaignId}/retry-failed`);
  return response.data;
}

/**
 * Retry all eligible failed messages across all campaigns.
 */
export async function retryAllFailedMessages() {
  const response = await api.post('/messages/retry-failed');
  return response.data;
}

/**
 * Fetch public feedback info by token (no auth required).
 */
export async function getPublicFeedbackInfo(token) {
  const response = await api.get(`/feedback/info/${token}`);
  return response.data;
}

/**
 * Submit public feedback (no auth required).
 */
export async function submitPublicFeedback(payload) {
  const response = await api.post('/feedback/submit', payload);
  return response.data;
}

/**
 * List feedback with filters (admin).
 */
export async function listFeedback(params = {}) {
  const response = await api.get('/feedback', { params });
  return response.data;
}

/**
 * Get feedback detail (admin).
 */
export async function getFeedbackDetail(feedbackId) {
  const response = await api.get(`/feedback/${feedbackId}`);
  return response.data;
}

/**
 * Mark feedback as resolved (admin).
 */
export async function resolveFeedback(feedbackId, resolutionNotes = null) {
  const response = await api.post(`/feedback/${feedbackId}/resolve`, {
    resolution_notes: resolutionNotes,
  });
  return response.data;
}

/**
 * Dispatch reply to feedback (admin).
 */
export async function replyToFeedback(feedbackId, replyText, channelOverride = null) {
  const response = await api.post(`/feedback/${feedbackId}/reply`, {
    reply_text: replyText,
    channel_override: channelOverride,
  });
  return response.data;
}

/**
 * Get feedback topics, keywords, questions and concerns (admin).
 */
export async function getFeedbackTopics(campaignId = null) {
  const params = campaignId ? { campaign_id: campaignId } : {};
  const response = await api.get('/feedback/topics', { params });
  return response.data;
}

/**
 * Get campaign engagement and sentiment metrics (admin).
 */
export async function getCampaignEngagement(campaignId) {
  const response = await api.get(`/campaigns/${campaignId}/engagement`);
  return response.data;
}
