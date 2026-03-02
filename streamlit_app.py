import streamlit as st
import asyncio
import os
from playwright.async_api import async_playwright

# 페이지 설정
st.set_page_config(page_title="Telegram Capture", layout="centered")

# 1. Playwright 브라우저 설치 (최초 1회만 실행되도록 캐싱)
@st.cache_resource
def install_playwright_browser():
    print("🚀 Playwright 브라우저 설치 확인 중...")
    os.system("playwright install chromium")
    print("✅ Playwright 브라우저 설치 완료")

# 앱 시작 시 설치 함수 실행
install_playwright_browser()

async def capture_telegram_light_font(url):
    output_filename = "telegram_screenshot.png"
    
    # 상태 메시지 표시를 위한 placeholder
    status_text = st.empty()
    status_text.info("🚀 스크린샷 캡처를 준비하고 있습니다...")

    async with async_playwright() as p:
        # Streamlit Cloud 환경(Container)에 최적화된 런칭 옵션
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox", 
                "--disable-dev-shm-usage",
                "--disable-gpu"
            ]
        )

        # 고해상도 설정 (3배율)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=3
        )
        page = await context.new_page()

        status_text.text(f"🌐 페이지 이동 중: {url}")
        try:
            await page.goto(url, wait_until="domcontentloaded") # 속도를 위해 domcontentloaded 사용

            # ✅ 핵심: 웹 폰트(CDN) 로드 및 CSS 강제 주입
            # Pretendard를 기본으로 유지하되 CJK 폴백을 추가해 한자 깨짐을 방지합니다.
            await page.add_style_tag(content="""
                @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
                @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&family=Noto+Sans+SC:wght@400;500;700&family=Noto+Sans+JP:wght@400;500;700&display=swap');

                body,
                .tgme_page,
                .tgme_channel_info_header_title,
                .tgme_widget_message_author,
                .tgme_widget_message_link,
                .tgme_widget_message_text,
                .tgme_widget_message_wrap,
                .tgme_widget_message_wrap * {
                    font-family: 'Pretendard', 'Noto Sans TC', 'Noto Sans SC', 'Noto Sans JP', 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif !important;
                    font-weight: 300 !important; /* Light */
                    letter-spacing: -0.3px !important;
                    line-height: 1.6 !important;
                }
            """)
            status_text.text("💉 CSS 주입 완료: Pretendard + CJK fallback 적용")

            # 선택자 로직
            post_identifier = "/".join(url.split("/")[-2:]) # 예: insidertracking/35271
            selector = f'[data-post="{post_identifier}"]'

            # 요소 대기
            await page.wait_for_selector(selector, timeout=15000)

            # document.fonts.ready 우선 대기, 실패 시 기존 sleep fallback 유지
            fonts_ready = False
            try:
                fonts_ready = await page.evaluate("""
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
                """)
            except Exception:
                fonts_ready = False

            if fonts_ready:
                await asyncio.sleep(1)
            else:
                await asyncio.sleep(5)

            # 스크린샷 캡처
            element = page.locator(selector)

            # 요소의 전체 크기 계산
            bounding_box = await element.bounding_box()

            # 요소의 크기가 유효한지 확인
            if bounding_box is None or bounding_box['height'] == 0:
                # 기본 값 설정
                element_height = 2000  # 기본 높이
            else:
                element_height = int(bounding_box['height'])

            # 뷰포트 크기 조정 (요소의 전체 높이 + 여백)
            await page.set_viewport_size({
                "width": 1920,
                "height": element_height + 200  # 여백 추가 (100 → 200)
            })

            # 요소 스크롤하여 보이도록 설정
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

            # 스크롤 후 대기
            await asyncio.sleep(2)

            # 요소 전체 캡처
            await element.screenshot(path=output_filename)
            
            status_text.success("✅ 캡처 완료!")
            return output_filename

        except Exception as e:
            status_text.error(f"❌ 오류 발생: {e}")
            return None

        finally:
            await browser.close()

# --- Streamlit UI ---
st.title("📸 Telegram 캡처")
st.markdown("텔레그램 게시물 링크를 입력하면 **Pretendard Light** 폰트를 적용해 캡처합니다.")

target_url = st.text_input("텔레그램 링크 입력", value="", placeholder="https://t.me/s/banjang9/3895")

if st.button("캡처 시작"):
    if target_url:
        # URL 형식 변환: t.me/채널/글번호 → t.me/s/채널/글번호
        if "t.me/" in target_url and "/s/" not in target_url:
            # URL에 "/s" 추가
            parts = target_url.split("t.me/")
            if len(parts) == 2:
                target_url = f"https://t.me/s/{parts[1]}"

        # 비동기 함수 실행을 위한 루프 처리
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result_image = loop.run_until_complete(capture_telegram_light_font(target_url))
        
        if result_image:
            st.image(result_image, caption="적용 결과", use_container_width=True)
            
            # 다운로드 버튼 제공
            with open(result_image, "rb") as file:
                btn = st.download_button(
                    label="이미지 다운로드",
                    data=file,
                    file_name="telegram_capture.png",
                    mime="image/png"
                )
    else:
        st.warning("링크를 입력해주세요.")
