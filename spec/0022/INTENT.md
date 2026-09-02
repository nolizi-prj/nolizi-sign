# Intent: make provider-specific OAuth verification work in staging

Google rejects an unregistered callback before authentication. Microsoft Entra
accepts the callback but its UserInfo response generally omits Google's
`email_verified` claim. Provider validation must follow each provider's actual
contract without returning every Microsoft user silently to the login page.

