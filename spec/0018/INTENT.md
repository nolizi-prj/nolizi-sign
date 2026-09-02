# Worker-edge route rate limits

Feedback and standalone conversion terminate in `worker.ts`, before normal API
forwarding. They must share the durable limiter rather than use isolate memory
or remain outside the production abuse boundary.
