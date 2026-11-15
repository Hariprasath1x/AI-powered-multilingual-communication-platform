// API service for Multichannel Distribution Jobs and Delivery Tracking.

import api from './api';

export const getCampaignReadiness = async (campaignId, channel = 'Email') => {
  const response = await api.get(`/distribution/readiness/${campaignId}`, {
    params: { channel },
  });
  return response.data;
};

export const createDistributionJob = async (campaignId, channel) => {
  const response = await api.post('/distribution/jobs', {
    campaign_id: campaignId,
    channel,
  });
  return response.data;
};

export const listDistributionJobs = async (params = {}) => {
  const response = await api.get('/distribution/jobs', { params });
  return response.data;
};

export const getDistributionJob = async (jobId) => {
  const response = await api.get(`/distribution/jobs/${jobId}`);
  return response.data;
};

export const listJobDeliveries = async (jobId, params = {}) => {
  const response = await api.get(`/distribution/jobs/${jobId}/deliveries`, { params });
  return response.data;
};

export const processDistributionJob = async (jobId) => {
  const response = await api.post(`/distribution/jobs/${jobId}/process`);
  return response.data;
};

export const retryDistributionJob = async (jobId) => {
  const response = await api.post(`/distribution/jobs/${jobId}/retry`);
  return response.data;
};

export const cancelDistributionJob = async (jobId) => {
  const response = await api.post(`/distribution/jobs/${jobId}/cancel`);
  return response.data;
};

export const getDistributionMetrics = async () => {
  const response = await api.get('/distribution/metrics');
  return response.data;
};
