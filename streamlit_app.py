import asyncio
import os
import subprocess
import sys

import streamlit as st
from playwright.async_api import async_playwright


st.set_page_config(page_title="Telegram Capture", layout="centered")

PLAYWRIGHT_BROWSERS_PATH = "/tmp/playwright"
OUTPUT_FILENAME = "telegram_screenshot.png"
DARK_NAVY_BACKGROUND = "#0b1630"
LAUNCH_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
]


@st.cache_resource
def install_playwright_browser():
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", PLAYWRIGHT_BROWSERS_PATH)
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "ok": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


async def launch_browser(playwright):
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", PLAYWRIGHT_BROWSERS_PATH)
    return await playwright.chromium.launch(headless=True, args=LAUNCH_ARGS)


async def capture_telegram_light_font(url):
    status_text = st.empty()
    status_text.info("스크린샷 캡처를 준비하고 있습니다...")

    install_result = install_playwright_browser()
    if not install_result["ok"]:
        status_text.error(
            "Playwright Chromium 설치에 실패했습니다.\n\n"
            f"{install_result['stderr'] or install_result['stdout']}"
        )
        return None

    browser = None

    async with async_playwright() as playwright:
        try:
            try:
                browser = await launch_browser(playwright)
            except Exception:
                retry_result = install_playwright_browser()
                if not retry_result["ok"]:
                    raise RuntimeError(
                        "Chromium 재설치에 실패했습니다.\n"
                        f"{retry_result['stderr'] or retry_result['stdout']}"
                    )
                browser = await launch_browser(playwright)

            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=3,
            )
            page = await context.new_page()

            status_text.text(f"페이지로 이동 중: {url}")
            await page.goto(url, wait_until="domcontentloaded")

            await page.add_style_tag(
                content="""
                    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
                    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&family=Noto+Sans+SC:wght@400;500;700&family=Noto+Sans+JP:wght@400;500;700&display=swap');

                    html,
                    body,
                    .tgme_page,
                    .tgme_background_wrap,
                    .tgme_container,
                    .tgme_channel_history,
                    .tgme_channel_history_wrap,
                    .tgme_widget_message_wrap {
                        background: #0b1630 !important;
                        background-image: none !important;
                    }

                    body,
                    .tgme_page,
                    .tgme_channel_info_header_title,
                    .tgme_widget_message_author,
                    .tgme_widget_message_link,
                    .tgme_widget_message_text,
                    .tgme_widget_message_wrap,
                    .tgme_widget_message_wrap * {
                        font-family: 'Pretendard', 'Noto Sans TC', 'Noto Sans SC', 'Noto Sans JP', 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif !important;
                        font-weight: 300 !important;
                        letter-spacing: -0.3px !important;
                        line-height: 1.6 !important;
                    }
                """
            )
            status_text.text("스타일 적용 완료")

            post_identifier = "/".join(url.split("/")[-2:])
            selector = f'[data-post="{post_identifier}"]'

            await page.wait_for_selector(selector, timeout=15000)
            await page.locator(selector).evaluate(
                """(element, backgroundColor) => {
                    element.style.background = backgroundColor;
                    element.style.backgroundImage = "none";
                }""",
                DARK_NAVY_BACKGROUND,
            )

            fonts_ready = False
            try:
                fonts_ready = await page.evaluate(
                    """
                        async () => {
                            if (!document.fonts || !document.fonts.ready) return false;
                            try {
                                await Promise.race([
                                    document.fonts.ready,
                                    new Promise((resolve) => setTimeout(resolve, 4000))
                                ]);
                                return true;
                            } catch (e) {
                                return false;
                            }
                        }
                    """
                )
            except Exception:
                fonts_ready = False

            await asyncio.sleep(1 if fonts_ready else 5)

            element = page.locator(selector)
            bounding_box = await element.bounding_box()
            element_height = 2000 if not bounding_box or bounding_box["height"] == 0 else int(bounding_box["height"])

            await page.set_viewport_size(
                {
                    "width": 1920,
                    "height": element_height + 200,
                }
            )

            await element.evaluate(
                """(element) => {
                    const safetyMargin = 8;
                    const header = document.querySelector('.tgme_header');
                    const headerHeight = header ? header.getBoundingClientRect().height : 0;
                    const elementTop = element.getBoundingClientRect().top + window.scrollY;
                    const targetTop = Math.max(0, elementTop - headerHeight - safetyMargin);

                    window.scrollTo({
                        top: targetTop,
                        behavior: "auto"
                    });
                }"""
            )

            await asyncio.sleep(2)
            await element.screenshot(path=OUTPUT_FILENAME)

            status_text.success("캡처가 완료되었습니다.")
            return OUTPUT_FILENAME
        except Exception as error:
            status_text.error(f"오류가 발생했습니다: {error}")
            return None
        finally:
            if browser is not None:
                await browser.close()


st.title("Telegram 캡처")
st.markdown("텔레그램 게시물 링크를 입력하면 Pretendard Light 폰트와 단색 배경으로 캡처합니다.")

target_url = st.text_input(
    "텔레그램 링크 입력",
    value="",
    placeholder="https://t.me/s/banjang9/3895",
)

if st.button("캡처 시작"):
    if target_url:
        if "t.me/" in target_url and "/s/" not in target_url:
            parts = target_url.split("t.me/")
            if len(parts) == 2:
                target_url = f"https://t.me/s/{parts[1]}"

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result_image = loop.run_until_complete(capture_telegram_light_font(target_url))

        if result_image:
            st.image(result_image, caption="적용 결과", use_container_width=True)

            with open(result_image, "rb") as file:
                st.download_button(
                    label="이미지 다운로드",
                    data=file,
                    file_name="telegram_capture.png",
                    mime="image/png",
                )
    else:
        st.warning("링크를 입력해주세요.")
