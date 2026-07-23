import asyncio
import argparse

from pathlib import Path

from app.fetcher import Fetcher, FetchError
from app.config import _load_proxies_from_env
from app.proxy import ProxyPool

URLS_FILE = "links.txt"
OUTPUT_DIR = Path("output")

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--concurrency', type=int, default=5)
    parser.add_argument('--file', type=str, default='links.txt')

    args = parser.parse_args()

    with open(args.file, encoding="utf-8") as file:
        urls = []

        for line in file:
            url = line.strip()

            if url:
                urls.append(url)

    urls = urls[:args.limit]

    proxies = _load_proxies_from_env()
    proxy_pool = ProxyPool(proxies)

    semaphore = asyncio.Semaphore(args.concurrency)
    fetcher = Fetcher(proxy_pool=proxy_pool)

    tasks = [
        asyncio.create_task(get_data(i, url, fetcher, semaphore))
        for i, url in enumerate(urls)
    ]

    results = await asyncio.gather(*tasks)

    ok_count = sum(1 for status in results if status == 200)

    print(f"[{ok_count}/{args.limit}] of requests are successful")


async def get_data(index: int, url: str, fetcher: Fetcher, semaphore: asyncio.Semaphore):
    async with semaphore:
        try:
            result = await fetcher.get(url)

            file_path = OUTPUT_DIR / f"{index:04d}.html"
            file_path.write_text(result.text, encoding="utf-8")

            print(f"[{index}] {result.status_code} {result.latency_ms} ms {url}")

            return result.status_code

        except FetchError as e:
            print(f"[{index}] FAILED {url}")
            print(e)

            return None

        except Exception as e:
            print(f"[{index}] ERROR {url}")
            print(e)

            return None


if __name__ == "__main__":
    asyncio.run(main())