import asyncio
import os
import sys
from playwright.async_api import async_playwright

# 获取正确的文件路径
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

ACCOUNT_FILE = os.path.join(application_path, "accounts.txt")

async def smart_login(page, url, account, password):
    # 注入反检测脚本
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
    """)

    try:
        print(f"[{account}] 正在打开: {url} ...")
        try:
            await page.goto(url, timeout=60000, wait_until='domcontentloaded')
        except:
            print(f"[{account}] ⚠️ 网页加载较慢，尝试继续...")

        await page.wait_for_timeout(2000)

        # 填账号
        try:
            inputs = await page.locator("input:visible").all()
            filled = False
            for inp in inputs:
                type_attr = await inp.get_attribute("type") or "text"
                if type_attr not in ["hidden", "submit", "button", "checkbox", "radio", "file"]:
                    await inp.fill(account)
                    filled = True
                    break
            if not filled and inputs: await inputs[0].fill(account)
            print(f"[{account}] ✅ 已填账号")
        except:
            print(f"[{account}] ❌ 找不到输入框")

        # 填密码
        if password.strip() != "NONE":
            try:
                await page.fill("input[type='password']", password)
                print(f"[{account}] ✅ 已填密码")
            except: pass

        # 点登录
        try:
            await page.click("button:has-text('登录'), button:has-text('Login'), input[value='登录']", timeout=3000)
            print(f"[{account}] ✅ 点击登录")
        except:
            await page.keyboard.press("Enter")

    except Exception as e:
        print(f"[{account}] 出错: {e}")

async def main():
    print(">>> 正在启动 Windows 批量登录助手 (Edge版)...")
    
    if not os.path.exists(ACCOUNT_FILE):
        print(f"❌ 错误：找不到 accounts.txt")
        print(f"请确保 accounts.txt 文件位于：{application_path}")
        input("按回车键退出...")
        return

    try:
        with open(ACCOUNT_FILE, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        input("按回车键退出...")
        return

    async with async_playwright() as p:
        # === 核心修改区域 ===
        browser = None
        
        # 1. 优先尝试启动 Microsoft Edge (Windows 标配)
        try:
            print(">>> 正在呼叫 Microsoft Edge 浏览器...")
            browser = await p.chromium.launch(
                headless=False, 
                channel="msedge",  # 这里指定 Edge
                args=["--start-maximized", "--disable-blink-features=AutomationControlled"]
            )
        except Exception as e:
            print(f"⚠️ 没找到 Edge ({e})，尝试 Chrome...")
            
            # 2. 如果没 Edge，尝试 Chrome
            try:
                browser = await p.chromium.launch(
                    headless=False, 
                    channel="chrome", 
                    args=["--start-maximized", "--disable-blink-features=AutomationControlled"]
                )
            except Exception as e2:
                print(f"❌ 既没找到 Edge 也没找到 Chrome。程序无法运行。")
                print("请安装 Microsoft Edge 或 Google Chrome 浏览器。")
                input("按回车键退出...")
                return
        
        # 创建 Windows 上下文
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
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
                page = await context.new_page()
                tasks.append(smart_login(page, url, acc, pwd))

        if tasks:
            print(f">>> 正在执行 {len(tasks)} 个任务...")
            await asyncio.gather(*tasks)
            print("\n✅ 所有任务已完成！请勿关闭窗口。")
            await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"程序崩溃: {e}")
        input("按回车键退出...")