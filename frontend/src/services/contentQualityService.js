import api from './api';

/**
 * Trigger comprehensive content quality and compliance assessment.
 */
export async function evaluateContentQuality(assetId, payload = {}) {
  const response = await api.post(`/content/${assetId}/evaluate`, payload);
  return response.data;
}

/**
 * Retrieve latest quality assessment report for a content asset.
 */
export async function getLatestQualityAssessment(assetId) {
  const response = await api.get(`/content/${assetId}/quality`);
  return response.data;
}

/**
 * Retrieve audit assessment history for a content asset.
 */
export async function getQualityAssessmentHistory(assetId) {
  const response = await api.get(`/content/${assetId}/quality/history`);
  return response.data;
}

/**
 * Record human reviewer decision on an individual editorial finding.
 */
export async function updateFindingDecision(assetId, findingId, payload) {
  const response = await api.patch(
    `/content/${assetId}/quality/findings/${findingId}`,
    payload
  );
  return response.data;
}

/**
 * Get editorial readiness summary and approval blocker status.
 */
export async function getEditorialReadiness(assetId) {
  const response = await api.get(`/content/${assetId}/editorial-readiness`);
  return response.data;
}

