import client from "@/shared/api/client";

/**
 * Fetch all supplier quotes for an RFQ
 */
export const getQuotesByRFQ = async (rfqId) => {
  const response = await client.get(`/rfqs/${rfqId}/quotes`);
  return response.data;
};

/**
 * Create a supplier quote for an RFQ
 */
export const createQuote = async (rfqId, payload) => {
  const response = await client.post(`/rfqs/${rfqId}/quotes`, payload);
  return response.data;
};

/**
 * Update an existing supplier quote
 */
export const updateQuote = async (quoteId, payload) => {
  const response = await client.put(`/quotes/${quoteId}`, payload);
  return response.data;
};

/**
 * Delete a supplier quote
 */
export const deleteQuote = async (quoteId) => {
  const response = await client.delete(`/quotes/${quoteId}`);
  return response.data;
};

/**
 * Import supplier quotes from a CSV or PDF file
 */
export const importQuotes = async (rfqId, file) => {
  const formData = new FormData();

  formData.append("file", file);

  const response = await client.post(
    `/rfqs/${rfqId}/quotes/import`,
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    }
  );

  return response.data;
};
