import client from "@/shared/api/client";

/**
 * Fetch all RFQs
 */
export const getRFQs = async () => {
  const response = await client.get("/rfqs");
  return response.data;
};

/**
 * Fetch a single RFQ by ID
 */
export const getRFQById = async (rfqId) => {
  const response = await client.get(`/rfqs/${rfqId}`);
  return response.data;
};

/**
 * Create a new RFQ
 */
export const createRFQ = async (payload) => {
  const response = await client.post("/rfqs", payload);
  return response.data;
};

/**
 * Update an existing RFQ
 */
export const updateRFQ = async (rfqId, payload) => {
  const response = await client.put(`/rfqs/${rfqId}`, payload);
  return response.data;
};

/**
 * Delete an RFQ
 */
export const deleteRFQ = async (rfqId) => {
  const response = await client.delete(`/rfqs/${rfqId}`);
  return response.data;
};
