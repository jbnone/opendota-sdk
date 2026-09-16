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
| [`TransportError`][opendota_sdk.TransportError] | A connection-level failure (DNS, timeout, refused connection). |
| [`HTTPStatusError`][opendota_sdk.HTTPStatusError] | The API responds with a non-2xx status. Carries `status_code`, `method`, `url`, `response_text`, and `headers`. |
| [`RateLimitError`][opendota_sdk.RateLimitError] | The API responds 429. Carries `retry_after` when the response provides it. |
| [`ResponseDecodeError`][opendota_sdk.ResponseDecodeError] | The response body isn't valid JSON. |

`HTTPStatusError` and `RateLimitError` are more specific than a generic `TransportError`
and can be caught separately when you need to branch on them:

```python
from opendota_sdk import HTTPStatusError, RateLimitError

try:
    items = await client.get_items()
except RateLimitError as exc:
    if exc.retry_after:
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
