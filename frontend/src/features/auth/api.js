import client from "@/shared/api/client";

/**
 * Auth feature — buyer identity.
 *
 * The token itself is owned by `shared/api/client.js` (it reads it from
 * localStorage for every request); this module only talks to the four auth
 * endpoints and returns their payloads:
 *
 *   TokenResponse = { access_token, token_type: "bearer", expires_in, user }
 *   UserResponse  = { id, email, full_name, company_name, contact_email,
 *                     contact_phone, is_active, created_at }
 */

/** Create a buyer account and return its `TokenResponse`. */
export const register = async (payload) => {
  const response = await client.post("/auth/register", payload);
  return response.data;
};

/** Exchange credentials for a `TokenResponse`. */
export const login = async (credentials) => {
  const response = await client.post("/auth/login", credentials);
  return response.data;
};

/** Current buyer profile — also the token validity check on app boot. */
export const getMe = async () => {
  const response = await client.get("/auth/me");
  return response.data;
};

/** Update the buyer's own profile (company name, contact details, …). */
export const updateMe = async (payload) => {
  const response = await client.patch("/auth/me", payload);
  return response.data;
};
