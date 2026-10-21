# Lowercase. Aliases and generated codes are compared case-insensitively against this set,
# so a short link can never shadow an application route.
RESERVED_CODES = frozenset({
    "auth", "shorten", "health", "docs", "redoc", "openapi",
    "app", "api", "static", "admin", "login", "register", "me", "urls",
})