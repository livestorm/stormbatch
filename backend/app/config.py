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
