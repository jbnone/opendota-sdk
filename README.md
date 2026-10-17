<div align="center">

<h1>Open Dota SDK</h1>

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![prek](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/j178/prek/master/docs/assets/badge-v0.json)](https://github.com/j178/prek)
[![Docs](https://img.shields.io/badge/docs-jbnone.github.io-blue)](https://jbnone.github.io/opendota-sdk/)

</div>

Build better Dota 2 tools with the OpenDota SDK, providing enhanced access to [OpenDota API](https://docs.opendota.com/) data.

```bash
pip install opendota-sdk
```

```python
import asyncio
from opendota_sdk import HeroName, OpenDotaAsyncClient


async def main():
    async with OpenDotaAsyncClient() as client:
        hero = await client.get_hero(HeroName.ANTI_MAGE)
        stats = await hero.get_stats()
        matchups = await hero.get_matchups()
        print(hero.localized_name, f"{stats.pub_win_rate:.1%}")
        print(matchups.matchups[0].hero.localized_name)


asyncio.run(main())
```

Output (live data, so the numbers drift with the patch):

```text
Anti-Mage 51.1%
Storm Spirit
```

Docs: **https://jbnone.github.io/opendota-sdk/**
