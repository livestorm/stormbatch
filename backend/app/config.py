import os

# Render sets RENDER=true on its services; STORMBATCH_ENV=production marks
# production on any other host.
IS_PRODUCTION = os.environ.get("RENDER") == "true" or os.environ.get("STORMBATCH_ENV") == "production"

_DEV_SESSION_SECRET = "dev-secret-change-in-production"

# Signs the session cookie and derives the key that encrypts the Livestorm
# token inside it. A known value would let anyone forge sessions or read tokens.
SESSION_SECRET = os.environ.get("SESSION_SECRET_KEY", "")
if IS_PRODUCTION and SESSION_SECRET in ("", _DEV_SESSION_SECRET):
    raise RuntimeError("SESSION_SECRET_KEY must be set to a private random value in production.")
SESSION_SECRET = SESSION_SECRET or _DEV_SESSION_SECRET

# Render pull request previews get their own URL but copy the base service's
# environment, so their OAuth callback is built from RENDER_EXTERNAL_URL. The
# Livestorm OAuth app must list that callback as an allowed redirect URI.
_PREVIEW_URL = os.environ.get("RENDER_EXTERNAL_URL", "") if os.environ.get("IS_PULL_REQUEST") == "true" else ""
OAUTH_REDIRECT_URI = (
    f"{_PREVIEW_URL.rstrip('/')}/api/auth/livestorm/callback"
    if _PREVIEW_URL
    else os.environ.get("LIVESTORM_OAUTH_REDIRECT_URI", "")
)
