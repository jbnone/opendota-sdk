# Errors

Every SDK-raised exception subclasses [`OpenDotaError`][opendota_sdk.OpenDotaError], so
catching it covers everything the SDK itself can raise:

```python
from opendota_sdk import OpenDotaAsyncClient, OpenDotaError

async with OpenDotaAsyncClient() as client:
    try:
        item = await client.get_item(item_name="does-not-exist")
    except OpenDotaError as exc:
        ...
```

Note that a lookup that simply finds nothing (`get_item()`, `get_hero()`,
`get_hero_stat()` with no match) returns `None` rather than raising — these errors are
for failures, not absent data.

## Error types

| Type | Raised when |
|---|---|
| [`TransportError`][opendota_sdk.TransportError] | A connection-level failure (DNS, timeout, refused connection). Carries `is_timeout`, `True` when the request timed out rather than failing another way. |
| [`HTTPStatusError`][opendota_sdk.HTTPStatusError] | The API responds with a non-2xx status. Carries `status_code`, `method`, `url`, `response_text`, and `headers`. |
| [`InvalidAPIKeyError`][opendota_sdk.InvalidAPIKeyError] | OpenDota rejects your API key as malformed, unknown, or cancelled. A subclass of `HTTPStatusError` (status 400), so existing handlers still catch it; `reason` holds OpenDota's explanation. Never retried — see [Configuration → API key](configuration.md#api-key). |
| [`RateLimitError`][opendota_sdk.RateLimitError] | The API responds 429 and the client could not, or should not, wait it out. Carries `retry_after` (seconds, or `None` if unknown) and `is_daily_limit`. |
| [`ResponseDecodeError`][opendota_sdk.ResponseDecodeError] | The response body isn't valid JSON. |

`HTTPStatusError` and `RateLimitError` are more specific than a generic `TransportError`
and can be caught separately when you need to branch on them:

```python
from opendota_sdk import HTTPStatusError, InvalidAPIKeyError, RateLimitError

try:
    items = await client.get_items()
except InvalidAPIKeyError as exc:
    logger.error("Fix the OpenDota API key: %s", exc.reason)
except RateLimitError as exc:
    if exc.is_daily_limit:
        ...  # waiting won't help today
    elif exc.retry_after:
        ...
except HTTPStatusError as exc:
    logger.error("OpenDota returned %s for %s %s", exc.status_code, exc.method, exc.url)
```

## Retries

Transient failures (network errors, and the status codes configured in
`OpenDotaClientConfig.retry_on_status` — 429, 500, 502, 503, 504 by default) are retried
automatically before an error ever reaches your code, using exponential backoff
controlled by `max_retries` and `backoff_factor`. See
[Configuration](configuration.md) to tune this.

## Rate limits

OpenDota allows 60 requests a minute without an API key (300 with one), and 3,000 a day
without a key. It does **not** send a `Retry-After` header when you exceed them, so the
client works out the wait itself:

- **Per-minute limit.** OpenDota's counter resets at the start of every minute, so the
  client waits until then, measured on the server's clock from the response's `Date`
  header. The wait applies to **every request on that client**, not just the one that
  was rejected — the limit is counted per key or IP, so anything sent meanwhile would
  be rejected too.
- **Daily limit.** It cannot be waited out, so the `RateLimitError` is raised right away
  with `is_daily_limit=True`.
- **`Retry-After`**, if a proxy in front of the API sends one, is honored as-is.

Each rate-limited retry still counts against `max_retries`. A wait longer than
`max_retry_after` is never taken: the error is raised instead, with `retry_after` set so
you can decide what to do.
