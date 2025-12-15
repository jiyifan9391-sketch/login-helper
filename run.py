import asyncio
from playwright.async_api import async_playwright

# ================= 配置区域 =================
ACCOUNT_FILE = "accounts.txt"
# ===========================================

async def smart_login(page, url, account, password):
    # 注入反检测脚本 (防止白屏)
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
    """)

    try:
        print(f"[{account}] 正在标签页中打开: {url} ...")
        
        # 1. 打开网页
        try:
            # 60秒超时
            await page.goto(url, timeout=60000, wait_until='domcontentloaded')
        except Exception:
            print(f"[{account}] ⚠️ 网页加载较慢，尝试继续...")

        # 稍微等待
        await page.wait_for_timeout(2000)

        # 2. 智能填账号
        try:
            # 寻找输入框
            inputs = await page.locator("input:visible").all()
            filled = False
            for inp in inputs:
                type_attr = await inp.get_attribute("type") or "text"
                if type_attr not in ["hidden", "submit", "button", "checkbox", "radio", "file"]:
                    await inp.fill(account)
                    print(f"[{account}] ✅ 填入账号")
                    filled = True
                    break
            
            if not filled and inputs:
                await inputs[0].fill(account)

        except Exception:
            print(f"[{account}] ❌ 找不到输入框")
            return

        # 3. 智能填密码
        if password.strip() != "NONE":
            try:
                await page.fill("input[type='password']", password)
                print(f"[{account}] ✅ 填入密码")
            except:
                pass

        # 4. 智能点登录
        try:
            await page.click("button:has-text('登录'), button:has-text('Login'), input[value='登录']", timeout=3000)
            print(f"[{account}] ✅ 点击登录")
        except:
            await page.keyboard.press("Enter")

    except Exception as e:
        print(f"[{account}] 出错: {e}")

async def main():
    try:
        with open(ACCOUNT_FILE, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print("❌ 找不到 accounts.txt，请确保文件和脚本在同一个文件夹里。")
        return

    async with async_playwright() as p:
        print(">>> 正在启动 Windows 批量登录助手 (单窗口模式)...")
        
        # 启动浏览器
        browser = await p.chromium.launch(
            headless=False, 
            channel="chrome", # 尝试调用本机安装的 Chrome，更稳定
            args=["--start-maximized", "--disable-blink-features=AutomationControlled"]
        )
        
        # === 创建唯一的浏览器窗口 ===
        # 这里改成了 Windows 的 User-Agent
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport=None, 
            ignore_https_errors=True
        )

        tasks = []
        
        for line in lines:
            if line.startswith("#"): continue
            parts = line.split("|")
            
            if len(parts) >= 2:
                url = parts[0].strip()
                acc = parts[1].strip()
                pwd = parts[2].strip() if len(parts) > 2 else "NONE"
                
                # 在同一个窗口里，新建标签页
                page = await context.new_page()
                
                tasks.append(smart_login(page, url, acc, pwd))

        if tasks:
            print(f">>> 正在同时打开 {len(tasks)} 个标签页...")
            await asyncio.gather(*tasks)
            print("\n所有标签页已就绪。不要关闭此黑框，按 Ctrl+C 可以结束。")
            await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())