# Intent: document upload must not exhaust the browser or Worker

Opening or previewing an unusually large, scanned, or oddly sized document must
fail with an actionable message rather than consuming unbounded memory and
terminating the tab, browser, or production Worker.
