# tailscale_mirror_checker_async_safe.py
"""
异步镜像检测工具
功能：
1. 异步测试多个 GitHub 镜像代理
2. 校验文件 SHA-256
3. 过滤低速镜像（默认≥150KB/s）
4. 结果写入 proxies.txt 和 oc2proxies.txt
5. 输出 C# 和 WPF 格式代码
"""

import asyncio
import hashlib
import time
import re
from datetime import datetime
from typing import List, Tuple, Optional

import aiohttp

JS_URL = "https://update.greasyfork.org/scripts/412245/Github%20%E5%A2%9E%E5%BC%BA%20-%20%E9%AB%98%E9%80%9F%E4%B8%8B%E8%BD%BD.user.js"
OUTPUT_FILE = "proxies.txt"
OUTPUT_FILE_OC2 = "oc2proxies.txt"
LOG_FILE = "log.txt"

PROXIES = [
    "https://gh.monlor.com/https://github.com",
    "https://gh.jasonzeng.dev/https://github.com",
    "https://raw.ihtw.moe/github.com",
    "https://gh.zwy.one/https://github.com",
    "https://cdn.crashmc.com/https://github.com",
    "https://fastgit.cc/https://github.com",
    "https://gh.xx9527.cn/https://github.com",
    "https://xget.xi-xu.me/gh",
    "https://down.npee.cn/?https://github.com",
    "https://ghfile.geekertao.top/https://github.com",
    "https://ghp.keleyaa.com/https://github.com",
    "https://github.geekery.cn/https://github.com",
    "https://wget.la/https://github.com",
    "https://gh-proxy.com/https://github.com",
    "https://github.tbedu.top/https://github.com",
    "https://gh.llkk.cc/https://github.com",
    "https://hk.gh-proxy.com/https://github.com",
    "https://ghproxy.monkeyray.net/https://github.com",
    "https://ghproxy.net/https://github.com",
    "https://hub.glowp.xyz/https://github.com",
    "https://gh.xxooo.cf/https://github.com",
    "https://ghfast.top/https://github.com",
    "https://gitproxy.click/https://raw.githubusercontent.com",
    "https://gitproxy.click/https://github.com",
    "https://g.blfrp.cn/https://github.com",
    "https://github.ednovas.xyz/https://github.com",
    "https://gh.nxnow.top/https://github.com",
    "https://gh-proxy.net/https://github.com",
    "https://ghproxy.1888866.xyz/https://github.com",
    "https://proxy.yaoyaoling.net/https://github.com",
    "https://github.com",
]

ASSET_NAME = "tailscaled-linux-amd64"
ASSET_PATH = f"CH3NGYZ/small-tailscale-openwrt/releases/download/v1.78.0/{ASSET_NAME}"
SHA256_URL = "https://github.com/CH3NGYZ/small-tailscale-openwrt/releases/download/v1.78.0/SHA256SUMS.txt"

CONCURRENCY_LIMIT = 10
MIN_SPEED_KBPS = 150
TIMEOUT = int(7168 / MIN_SPEED_KBPS)


async def fetch_sha256() -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(SHA256_URL) as resp:
            if resp.status != 200:
                raise Exception(f"Failed to fetch SHA256SUMS.txt: {resp.status}")
            text = await resp.text()
            for line in text.splitlines():
                if ASSET_NAME in line and ASSET_NAME + ".build" not in line:
                    return line.split()[0].lower()
    raise Exception(f"{ASSET_NAME} not found in SHA256SUMS.txt")


async def fetch_and_extract_proxies(js_url: str) -> List[str]:
    print(f"[*] 下载代理列表: {js_url}")
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(js_url) as resp:
                js_text = await resp.text()
                pattern = re.compile(r"\['(https?://[^']+?)',\s*'[^']*?',\s*'[^']*?'\]")
                proxies = pattern.findall(js_text)
                return list(dict.fromkeys(proxies))
        except Exception as e:
            print(f"[!] 代理列表下载失败: {e}")
            return []


async def check_mirror(session, sem, base, expected_sha256):
    url = f"{base.rstrip('/')}/{ASSET_PATH}"
    async with sem:
        try:
            return await asyncio.wait_for(
                _check_mirror_core(session, url, base, expected_sha256), timeout=TIMEOUT
            )
        except asyncio.TimeoutError:
            print(f"[⏱️ 超时] {url}")
        except Exception as e:
            print(f"[❌错误] {url.ljust(60)} {type(e).__name__}")
        return None


async def _check_mirror_core(session, url, base, expected_sha256):
    start = time.time()
    async with session.get(url) as resp:
        resp.raise_for_status()
        h = hashlib.sha256()
        total = 0
        async for chunk in resp.content.iter_chunked(8192):
            h.update(chunk)
            total += len(chunk)

        digest = h.hexdigest()
        elapsed = time.time() - start
        speed = total / 1024 / elapsed if elapsed > 0 else 0

        if digest == expected_sha256:
            status = "✅成功" if speed >= MIN_SPEED_KBPS else "⚠️低速"
            print(f"[{status}] {url.ljust(60)} {speed:>7.2f} KB/s")
            return (base, speed) if speed >= MIN_SPEED_KBPS else None
        else:
            print(f"[❌校验] {url}")
    return None


def write_results_to_file(results: List[Tuple[str, float]], test_date: str):
    # proxies.txt
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for url, _ in results:
            f.write(f"{url}\n")
        f.write("https://gh.ch3ng.top\n")
        f.write("https://github.com\n")

    # oc2proxies.txt（使用 oc2gh.ch3ng.top）
    with open(OUTPUT_FILE_OC2, "w", encoding="utf-8") as f:
        for url, _ in results:
            f.write(f"{url}\n")
        f.write("https://oc2gh.ch3ng.top\n")
        f.write("https://github.com\n")

    # log
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(f"# GitHub镜像代理测速结果 ({test_date})\n")
        f.write(f"# 最低速度要求: {MIN_SPEED_KBPS} KB/s\n\n")
        f.write("# 原始代理列表 (按速度降序)\n")
        for url, speed in results:
            f.write(f"{url} # {speed:.2f} KB/s\n")
        f.write("https://oc2gh.ch3ng.top # 自建OC2代理\n")
        f.write("https://github.com # 直连\n")
        f.write("=" * 60)
        f.write("\n# C#格式\n")
        f.write("private static readonly string[] proxyList = [\n")
        for url, speed in results:
            f.write(f'    "{url}",  // {speed:.2f} KB/s\n')
        f.write('    "https://oc2gh.ch3ng.top", //OC2代理\n')
        f.write('    "https://github.com", //直连\n')
        f.write("];\n")
        f.write("=" * 60)
        f.write("\n# WPF格式\n")
        for url, _ in results:
            f.write(f'<ComboBoxItem Content="{url}"/>\n')
        f.write('<ComboBoxItem Content="https://oc2gh.ch3ng.top"/>\n')
        f.write('<ComboBoxItem Content="https://github.com"/>\n')
        f.write("=" * 60)


async def main():
    test_date = datetime.now().strftime("%Y.%m.%d")
    print(f"\n{' GitHub镜像测速工具 ':=^80}")
    print(f"开始时间: {test_date} | 最低速度: {MIN_SPEED_KBPS} KB/s | TIMEOUT: {TIMEOUT}s\n")

    expected_sha256 = await fetch_sha256()
    custom_proxies = await fetch_and_extract_proxies(JS_URL)
    proxies = custom_proxies if custom_proxies else PROXIES
    print(f"[*] 测试代理数量: {len(proxies)}")

    sem = asyncio.Semaphore(CONCURRENCY_LIMIT)
    async with aiohttp.ClientSession() as session:
        tasks = [check_mirror(session, sem, p, expected_sha256) for p in proxies]
        results = await asyncio.gather(*tasks)

    success_list = [res for res in results if isinstance(res, tuple) and res is not None]
    success_list.sort(key=lambda x: -x[1])

    if success_list:
        write_results_to_file(success_list, test_date)
        print(f"\n[+] 结果已保存到 {OUTPUT_FILE} 和 {OUTPUT_FILE_OC2}")
    else:
        print("\n[!] 没有找到符合条件的镜像")

    if success_list:
        print("\n" + "=" * 60)
        print(f"有效镜像: {len(success_list)}个 (共测试 {len(proxies)}个)")
        print(f"平均速度: {sum(s for _, s in success_list)/len(success_list):.2f} KB/s")
        print(f"最快镜像: {success_list[0][0]} ({success_list[0][1]:.2f} KB/s)")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
