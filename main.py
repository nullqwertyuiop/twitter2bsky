#!python3.10

# 半夜写的，不知道写了什么，反正就是这样吧
# 别骂了，想骂就发 PR 我 merge
# 人和代码只要一个能跑就行

import asyncio
import json
import re
import signal
from asyncio.log import logger
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Final, Set

from aiohttp import ClientResponseError, ClientSession
from atproto import AsyncClient
from atproto.exceptions import BadRequestError
from atproto_client import models as atproto_models
from creart import it
from launart import Launart, Service
from launart.status import Phase
from loguru import logger
from playwright._impl._driver import compute_driver_executable  # noqa
from playwright.async_api import BrowserContext, Playwright, async_playwright
from tweet_crawler import TwitterFollowingCrawler, TwitterUser

PERSISTENT: Final[Path] = Path(__file__).parent / "persistent"
BSKY_SEARCH: Final[str] = (
    "https://public.api.bsky.app/xrpc/"
    "app.bsky.actor.searchActorsTypeahead"
    "?q={handle}&limit={limit}"
)
HANDLE_PATTERN: Final[re.Pattern[str]] = re.compile(r"@\w+(\.\w+)+")
PROFILE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?:https?://)?bsky\.app/profile/(\w+(?:\.\w+)+)"
)


class PlaywrightLifecycle(Service):
    id = "web.service/playwright"
    playwright: Playwright
    context: BrowserContext
    headless: bool

    def __init__(self, headless: bool = True):
        super().__init__()
        self.headless = headless

    @property
    def required(self) -> Set[str]:
        return set()

    @property
    def stages(self) -> Set[Phase]:
        return {"preparing", "blocking", "cleanup"}

    @asynccontextmanager
    async def page(self):
        page = await self.context.new_page()
        try:
            yield page
        finally:
            await page.close()

    async def launch_pw(self, headless: bool):
        if hasattr(self, "playwright"):
            await self.playwright.stop()
            logger.success("已关闭先前的 Playwright")
        self.playwright = await async_playwright().start()
        self.context = await self.playwright.chromium.launch_persistent_context(
            PERSISTENT, headless=headless
        )
        logger.success("已启动 Playwright")

    async def launch(self, manager: Launart):
        async with self.stage("preparing"):
            command = list(compute_driver_executable()) + ["install", "chromium"]
            shell = await asyncio.create_subprocess_exec(
                *command, stdout=asyncio.subprocess.PIPE
            )
            assert shell.stdout
            while line := (await shell.stdout.readline()).decode("utf-8"):
                logger.info(line)
            await self.launch_pw(self.headless)

        async with self.stage("blocking"):
            await manager.status.wait_for_sigexit()

        async with self.stage("cleanup"):
            await self.playwright.stop()


class Twitter2BskyLifecycle(Service):
    id = "misc.service/t2b"
    client: AsyncClient
    aiohttp_session: ClientSession
    storage: dict[str, str]
    twitter_following: list[TwitterUser]

    def load_storage(self):
        try:
            self.storage = json.loads(
                Path(__file__).with_name("runtime.json").read_text(encoding="utf-8")
            )
        except FileNotFoundError:
            logger.warning("未找到运行时数据，将创建新文件")
            self.storage = {}
        except json.JSONDecodeError:
            logger.error("运行时数据文件损坏，将创建新文件")
            self.storage = {}

    def save_storage(self):
        Path(__file__).with_name("runtime.json").write_text(
            json.dumps(self.storage, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @property
    def required(self) -> Set[str]:
        return {"web.service/playwright"}

    @property
    def stages(self) -> Set[Phase]:
        return {"preparing", "blocking", "cleanup"}

    @staticmethod
    async def get_twitter_cookies():
        pw_service = Launart.current().get_component(PlaywrightLifecycle)
        cookies = await pw_service.context.cookies("https://x.com")
        if list(
            filter(
                lambda c: c.get("name", "").startswith("auth_token"),
                cookies,
            )
        ) and list(filter(lambda c: c.get("name", "").startswith("ct0"), cookies)):
            logger.success("Twitter cookies 有效")
            return

        logger.warning("Twitter cookies 无效，尝试重新登录")
        await pw_service.launch_pw(headless=False)
        async with pw_service.page() as page:
            await page.goto("https://x.com/i/flow/login")
            await page.wait_for_url("https://x.com/home", timeout=0)
            logger.success("已登录 Twitter")
        await pw_service.launch_pw(headless=True)

    @staticmethod
    async def fetch_following() -> list[TwitterUser]:
        pw_service = Launart.current().get_component(PlaywrightLifecycle)
        async with pw_service.page() as page:
            await page.goto("https://x.com/home")
            await page.wait_for_selector('//a[@data-testid="AppTabBar_Profile_Link"]')
            xpath_expression = '//a[@data-testid="AppTabBar_Profile_Link"]'
            profile_link_element = await page.query_selector(xpath_expression)
            if profile_link_element and (
                href := await profile_link_element.get_attribute("href")
            ):
                screen_name = href.split("/")[-1]
                logger.success(f"已找到用户名: {screen_name!r}")
            else:
                logger.error("未能找到用户名")
                await asyncio.sleep(1)  # ensure logger output is printed
                screen_name = input("请输入推特用户名: ")
            crawler = TwitterFollowingCrawler(page, screen_name)
            result = await crawler.run()
        return result

    async def bsky_login(self):
        self.client = AsyncClient()
        await asyncio.sleep(1)
        bsky_handle = input("请输入 Bsky 用户名: ")
        bsky_password = input("请输入 Bsky 密码: ")
        me = await self.client.login(bsky_handle, bsky_password)
        logger.success(f"已以 {me.display_name!r} ({me.handle}) 登录 Bsky")

    async def _attempt_handling(self, handle: str) -> str | None:
        with suppress(BadRequestError):
            did = (await self.client.resolve_handle(handle)).did
            return did

    async def _search_actor(self, screen_name: str) -> str | None:
        with suppress(ClientResponseError):
            url = BSKY_SEARCH.format(handle=screen_name, limit=10)
            async with self.aiohttp_session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                actors = data.get("actors", [])
                if len(actors) == 1:
                    user = actors[0]
                    return user["did"]
                if len(actors) > 1:
                    logger.warning(f"找到多个 Bsky 用户: {screen_name}, 放弃")

    async def find_bsky_user(self, user: TwitterUser) -> str | None:
        # Method 1: Handle pattern in user profile
        for match in HANDLE_PATTERN.finditer(user.description):
            result = await self._attempt_handling(match.group(0)[1:])
            if result:
                return result
        for user_url in user.entities.description.urls:
            if match := PROFILE_PATTERN.match(user_url.expanded_url):
                result = await self._attempt_handling(match.group(1))
                if result:
                    return result
        for user_url in user.entities.url.urls:
            if match := PROFILE_PATTERN.match(user_url.expanded_url):
                result = await self._attempt_handling(match.group(1))
                if result:
                    return result

        # Method 2: screen_name.bsky.social
        if result := await self._attempt_handling(f"{user.screen_name}.bsky.social"):
            return result

        no_special_chars = re.sub(r"[^a-zA-Z0-9-]", "", user.screen_name)
        if result := await self._attempt_handling(f"{no_special_chars}.bsky.social"):
            return result

        dash_only = re.sub(r"[^a-zA-Z0-9-]", "", user.screen_name.replace("_", "-"))
        if result := await self._attempt_handling(f"{dash_only}.bsky.social"):
            return result

        # Method 3: Search actor by screen_name
        if result := await self._search_actor(user.screen_name):
            return result

        # Method 4: Search actor by name
        if result := await self._search_actor(user.name):
            return result

    async def find_and_follow(
        self, user: TwitterUser
    ) -> "atproto_models.AppBskyActorDefs.ProfileViewDetailed":
        if bsky_did := await self.find_bsky_user(user):
            bsky_user = await self.client.get_profile(bsky_did)
            self.storage[user.screen_name] = bsky_user.handle
            await self.client.follow(bsky_did)
            self.save_storage()
            return bsky_user
        raise ValueError("未找到 Bsky 用户")

    async def launch(self, manager: Launart):
        self.aiohttp_session = ClientSession()
        self.load_storage()
        self.twitter_following = []

        async with self.stage("preparing"):
            await self.get_twitter_cookies()

        async with self.stage("blocking"):
            self.twitter_following = await self.fetch_following()
            total = len(self.twitter_following)
            self.twitter_following = [
                user
                for user in self.twitter_following
                if user.screen_name not in self.storage
            ]
            followed = total - len(self.twitter_following)
            logger.success(f"已找到 {total} 个关注的用户，其中 " f"{followed} 个已关注")
            await self.bsky_login()
            failed = 0
            while not manager.status.exiting and self.twitter_following:
                user = self.twitter_following.pop()
                progress = f"[{total - len(self.twitter_following)}/{total}]"
                try:
                    bsky_user = await self.find_and_follow(user)
                    logger.success(
                        f"{progress} 已关注 {user.name!r} ({user.screen_name}) "
                        f"在 Bsky 上的账号: {bsky_user.display_name!r} "
                        f"({bsky_user.handle})"
                    )
                except Exception as e:
                    logger.error(
                        f"{progress} 未能处理用户 {user.name!r} "
                        f"({user.screen_name}): {e}"
                    )
                    failed += 1
            signal.raise_signal(signal.SIGINT)

        async with self.stage("cleanup"):
            self.save_storage()
            logger.success(
                f"已关注 {total - failed} 个用户，{followed} 个已在运行时数据中"
            )
            if failed:
                logger.error(f"未能关注 {failed} 个用户")
            await self.aiohttp_session.close()


if __name__ == "__main__":
    mgr: Launart = it(Launart)
    mgr.add_component(Twitter2BskyLifecycle())
    mgr.add_component(PlaywrightLifecycle())
    mgr.launch_blocking()
