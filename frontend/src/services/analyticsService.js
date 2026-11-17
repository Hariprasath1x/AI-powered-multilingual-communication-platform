import api from './api';

/**
 * Clean and build query parameters object by dropping null/undefined/empty string values.
 */
function buildQueryParams(params = {}) {
  const query = {};
  Object.keys(params).forEach((key) => {
    const val = params[key];
    if (val !== null && val !== undefined && val !== '' && val !== 'all') {
      query[key] = val;
    }
  });
  return query;
}

/**
 * Fetch global or filtered analytics KPIs.
 */
export async function getAnalyticsKPIs(params = {}) {
  const response = await api.get('/analytics/kpis', {
    params: buildQueryParams(params),
  });
  return response.data;
}

/**
 * Fetch engagement trends time-series data.
 */
export async function getAnalyticsTrends(params = {}) {
  const response = await api.get('/analytics/trends', {
    params: buildQueryParams(params),
  });
  return response.data;
}

/**
 * Fetch performance breakdowns across channels, languages, segments, and campaigns.
 */
export async function getAnalyticsBreakdowns(params = {}) {
  const response = await api.get('/analytics/breakdowns', {
    params: buildQueryParams(params),
  });
  return response.data;
}

/**
 * Fetch campaign conversion funnel metrics.
 */
export async function getAnalyticsFunnel(params = {}) {
  const response = await api.get('/analytics/funnel', {
    params: buildQueryParams(params),
  });
  return response.data;
}

/**
 * Fetch AI and rules-based plain English insights.
 */
export async function getAnalyticsInsights(params = {}) {
  const response = await api.get('/analytics/insights', {
    params: buildQueryParams(params),
  });
  return response.data;
}

/**
 * Fetch unified single-campaign analytics report.
 */
export async function getCampaignReport(campaignId) {
  const response = await api.get(`/analytics/campaign-report/${campaignId}`);
  return response.data;
}

/**
 * Helper to trigger a browser file download from a Blob.
 */
function triggerBlobDownload(blob, filename) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.style.display = 'none';
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

/**
 * Download structured CSV analytics report.
 */
export async function downloadAnalyticsCSV(params = {}) {
  const response = await api.get('/analytics/export/csv', {
    params: buildQueryParams(params),
    responseType: 'blob',
  });
  const filename = `analytics_report_${new Date().toISOString().split('T')[0]}.csv`;
  triggerBlobDownload(response.data, filename);
  return true;
}

/**
 * Download executive PDF analytics report.
 */
export async function downloadAnalyticsPDF(params = {}) {
  const response = await api.get('/analytics/export/pdf', {
    params: buildQueryParams(params),
    responseType: 'blob',
  });
  const filename = `analytics_executive_report_${new Date().toISOString().split('T')[0]}.pdf`;
  triggerBlobDownload(response.data, filename);
  return true;
}

export default {
  getAnalyticsKPIs,
  getAnalyticsTrends,
  getAnalyticsBreakdowns,
  getAnalyticsFunnel,
  getAnalyticsInsights,
  getCampaignReport,
  downloadAnalyticsCSV,
  downloadAnalyticsPDF,
};
