# Logging

The SDK logs through Python's standard `logging` module, under the `opendota_sdk`
logger. It configures nothing itself — no handlers, no levels — so nothing changes until
your application opts in.

## Turning it on

```python
import logging

logging.basicConfig(format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("opendota_sdk").setLevel(logging.DEBUG)
```

Typical output:

```text
DEBUG opendota_sdk.http._transport: GET /constants/items -> 200 in 0.67s (attempt 1)
DEBUG opendota_sdk.client: Loaded 501 items in 0.69s; cached on client
INFO opendota_sdk.http._transport: Rate limited on GET /heroStats; holding all requests on this client for 16s
INFO opendota_sdk.http._transport: Retrying GET /heroStats after rate limit (HTTP 429) (attempt 1 of 3) once the limit clears
```

## What each level means

| Level | What you see |
|---|---|
| `DEBUG` | Every request attempt with its status and timing; every time a cache is filled. Cache hits are silent. |
| `INFO` | Anything that changes timing you will notice: retries, and rate-limit pauses with their length. |
| `WARNING` | Data problems you could not otherwise see, such as a hero missing from the constants. |

Set `INFO` to find out why a call was slow without the per-request detail.

Errors the SDK raises are **not** also logged as warnings or errors — they reach your code
as exceptions, and reporting them is up to you. See [Errors](errors.md).

## What is never logged

- your API key, in any form — query parameters named `api_key` are shown as `***`
- request or response headers
- response bodies, or exception text that could contain them

Log lines show the API-relative path (`/heroStats`), not the full URL.
