# Specification: provider-specific OAuth verification

1. Google UserInfo must return a syntactically valid email and literal
   `email_verified: true`.
2. Microsoft UserInfo must return a syntactically valid `email` or
   `preferred_username`; it is authenticated by the access token obtained from
   the authorization-code exchange and does not require Google's claim.
3. Both providers retain single-use state, safe local redirects, and the
   authenticated UserInfo lookup.
4. Staging provider registrations must include their exact HTTPS callback URL.

A-502 verifies Google fails closed without the claim. A-506 verifies Microsoft
accepts its normal claim shape without it.
