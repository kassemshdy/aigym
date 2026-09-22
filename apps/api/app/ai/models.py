"""Model-id constants, not settings — bumping a model is a code change
reviewed like any other, not an env var someone can flip in production
without a deploy. See docs/DECISIONS.md, decision 29."""

HAIKU_MODEL = "claude-haiku-4-5"
SONNET_MODEL = "claude-sonnet-5"
