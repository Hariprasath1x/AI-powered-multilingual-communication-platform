import api from './api';

/**
 * List all channel configurations (Email, SMS) with masked credentials.
 */
export async function listChannelConfigs() {
  const response = await api.get('/admin/channels');
  return response.data;
}

/**
 * Get single channel configuration by name.
 */
export async function getChannelConfig(channel) {
  const response = await api.get(`/admin/channels/${channel}`);
  return response.data;
}

/**
 * Update channel configuration (enabled toggle, provider, sender, credentials).
 */
export async function updateChannelConfig(channel, payload) {
  const response = await api.put(`/admin/channels/${channel}`, payload);
  return response.data;
}

/**
 * Execute isolated channel connectivity test message.
 */
export async function testChannel(channel, payload) {
  const response = await api.post(`/admin/channels/${channel}/test`, payload);
  return response.data;
}

/**
 * Launch distribution of an approved campaign.
 */
export async function sendCampaign(campaignId, payload = {}) {
  const response = await api.post(`/campaigns/${campaignId}/send`, payload);
  return response.data;
}

/**
 * Retrieve live sending progress and message history for a campaign.
 */
export async function getCampaignSendSummary(campaignId) {
  const response = await api.get(`/campaigns/${campaignId}/send/summary`);
  return response.data;
}

