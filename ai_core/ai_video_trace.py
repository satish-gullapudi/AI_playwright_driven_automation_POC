# Optional tracing helper for Playwright (since browser-use doesn’t yet fully persist videos).

import os

async def start_tracing(page, video_dir):
    trace_path = os.path.join(video_dir, "trace.zip")
    context = page.context
    await context.tracing.start(screenshots=True, snapshots=True, sources=True)
    return trace_path

async def stop_tracing(page, trace_path):
    context = page.context
    await context.tracing.stop(path=trace_path)
