import api from './api';

/**
 * Fetch supported Indian languages for content generation and translation.
 */
export async function getSupportedLanguages() {
  const response = await api.get('/content/languages');
  return response.data;
}

/**
 * Fetch supported tones.
 */
export async function getSupportedTones() {
  const response = await api.get('/content/tones');
  return response.data;
}

/**
 * Fetch supported distribution channels.
 */
export async function getSupportedChannels() {
  const response = await api.get('/content/channels');
  return response.data;
}

/**
 * Generate public awareness content from a structured brief via AI.
 */
export async function generateContent(payload) {
  const response = await api.post('/content/generate', payload);
  return response.data;
}

/**
 * Create a manual draft content asset without AI.
 */
export async function createManualContent(payload) {
  const response = await api.post('/content/manual', payload);
  return response.data;
}

/**
 * Translate an existing content asset into a target Indian language.
 */
export async function translateContent(assetId, payload) {
  const response = await api.post(`/content/${assetId}/translate`, payload);
  return response.data;
}

/**
 * Batch translate a content asset into multiple target Indian languages with failure isolation.
 */
export async function translateContentBatch(assetId, payload) {
  const response = await api.post(`/content/${assetId}/translate/batch`, payload);
  return response.data;
}

/**
 * Retrieve chronological translation review audit history for an asset.
 */
export async function getTranslationReviewHistory(assetId) {
  const response = await api.get(`/content/${assetId}/review-history`);
  return response.data;
}

/**
 * List content assets with search, filters, and pagination.
 */
export async function listContentAssets(params = {}) {
  const response = await api.get('/content', { params });
  return response.data;
}

/**
 * Retrieve single content asset by ID.
 */
export async function getContentAsset(assetId) {
  const response = await api.get(`/content/${assetId}`);
  return response.data;
}

/**
 * Update editable draft content asset.
 */
export async function updateContentAsset(assetId, payload) {
  const response = await api.put(`/content/${assetId}`, payload);
  return response.data;
}

/**
 * Retrieve language variants and revision lineage for an asset.
 */
export async function getContentVariants(assetId) {
  const response = await api.get(`/content/${assetId}/variants`);
  return response.data;
}

/**
 * Update human review status (Draft, In Review, Approved, Rejected).
 */
export async function updateReviewStatus(assetId, payload) {
  const response = await api.patch(`/content/${assetId}/review`, payload);
  return response.data;
}

/**
 * Associate content asset with an existing campaign or save as reusable template.
 */
export async function attachToCampaignOrTemplate(assetId, payload) {
  const response = await api.post(`/content/${assetId}/attach`, payload);
  return response.data;
}

/**
 * Delete a draft content asset.
 */
export async function deleteContentAsset(assetId) {
  const response = await api.delete(`/content/${assetId}`);
  return response.data;
}

/**
 * Stateless channel constraint simulation for real-time live preview.
 * Debounced and abort-controlled during user editing without database writes.
 */
export async function previewChannelMetrics(payload, signal) {
  const response = await api.post('/content/preview-metrics', payload, { signal });
  return response.data;
}

/**
 * Task 10: Analyze content sentiment polarity, readability, clarity, and five-way tone.
 */
export async function analyzeTone(assetId, payload = {}) {
  const response = await api.post(`/content/${assetId}/tone/analyze`, payload);
  return response.data;
}

/**
 * Task 10: Generate revised copy adhering to requested tone while preserving facts.
 */
export async function improveTone(assetId, payload) {
  const response = await api.post(`/content/${assetId}/tone/improve`, payload);
  return response.data;
}

/**
 * Task 9.A: Generate demographic-tailored content variants for selected audience segments.
 */
export async function personalizeContent(assetId, payload) {
  const response = await api.post(`/content/${assetId}/personalize`, payload);
  return response.data;
}

/**
 * Task 9.A: Retrieve demographic variants created under a source content asset.
 */
export async function getPersonalizedVariants(assetId) {
  const response = await api.get(`/content/${assetId}/personalize/variants`);
  return response.data;
}

/**
 * Task 9.A: Update a demographic variant's copy or review status.
 */
export async function updatePersonalizedVariant(variantId, payload) {
  const response = await api.patch(`/content/variants/${variantId}`, payload);
  return response.data;
}

/**
 * Task 9.A: Delete a demographic variant.
 */
export async function deletePersonalizedVariant(variantId) {
  const response = await api.delete(`/content/variants/${variantId}`);
  return response.data;
}

/**
 * Task 9.A: Simulate recipient message preview with resolved variant and dynamic placeholders.
 */
export async function previewRecipientSimulation(assetId, payload) {
  const response = await api.post(`/content/${assetId}/personalize/preview-recipient`, payload);
  return response.data;
}



