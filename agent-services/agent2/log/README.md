# Agent2 logs

The service creates these files in this directory:

- `workflow.jsonl`: one JSON object per workflow event. Filter by `context.requestId`, `context.threadId` or `context.trajectoryId` to replay a request.

Logs rotate automatically. Payloads are truncated to 4000 characters by default and sensitive keys such as tokens and passwords are redacted. Configure `AGENT2_LOG_DIR`, `AGENT2_LOG_FULL_PAYLOADS` and `AGENT2_LOG_MAX_PAYLOAD_CHARS` in `.env`.
