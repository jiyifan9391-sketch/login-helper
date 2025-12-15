import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
import asyncio
import threading
import os
import sys
from playwright.async_api import async_playwright

# =================================================================
# 🔥【唯一规则】只监控这两个元素
# 只要网页里出现这两个中的任意一个，软件就会去读里面的字
# =================================================================
TARGET_SELECTOR = ".lastNewMsg, .visitorMsg"
# =================================================================

class AutoLoginMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Edge 客服监控助手 (精简版)")
        self.root.geometry("800x600")
        
        # 1. 顶部操作区
        self.frame_top = tk.Frame(root, pady=10)
        self.frame_top.pack(fill='x', padx=10)
        
        self.btn_select = tk.Button(self.frame_top, text="📂 选择账号文件 (accounts.txt)", command=self.select_file, font=("Arial", 10))
        self.btn_select.pack(side='left', padx=5)

        self.lbl_file = tk.Label(self.frame_top, text="未选择文件", fg="gray")
        self.lbl_file.pack(side='left', padx=5)

        # 2. 核心按钮
        self.btn_start = tk.Button(root, text="🚀 启动并开始监控", command=self.start_thread, 
                                   bg="#007AFF", fg="white", font=("Arial", 14, "bold"), height=2)
        self.btn_start.pack(fill='x', padx=20, pady=10)
        
        # 3. 日志区
        self.log_area = scrolledtext.ScrolledText(root, width=90, height=25, font=("Arial", 11))
        self.log_area.pack(padx=10, pady=10, expand=True, fill='both')
        
        self.file_path = ""
        self.try_find_default_file()

    def log(self, msg):
        def _update():
            self.log_area.insert(tk.END, f"{msg}\n")
            self.log_area.see(tk.END)
        self.root.after(0, _update)

    def try_find_default_file(self):
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        default_file = os.path.join(base_path, "accounts.txt")
        if os.path.exists(default_file):
            self.file_path = default_file
            self.lbl_file.config(text=default_file, fg="black")
            self.log(f"✅ 已自动加载: {default_file}")

    def select_file(self):
        filename = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
        if filename:
            self.file_path = filename
            self.lbl_file.config(text=filename, fg="black")
            self.log(f"📂 已选择文件: {filename}")

    def start_thread(self):
        if not self.file_path:
            messagebox.showwarning("提示", "请先选择 accounts.txt 文件！")
            return
        self.btn_start.config(state='disabled', text="正在运行中...")
        threading.Thread(target=self.run_async_loop, daemon=True).start()

    def run_async_loop(self):
        asyncio.run(self.main_logic())

    async def main_logic(self):
        self.log(">>> 正在启动 Edge 浏览器...")
        
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
        except Exception as e:
            self.log(f"❌ 读取文件失败: {e}")
            return

        async with async_playwright() as p:
            # 1. 启动浏览器 (优先 Edge)
            try:
                browser = await p.chromium.launch(
                    headless=False, 
                    channel="msedge", 
                    args=["--start-maximized", "--disable-blink-features=AutomationControlled"]
                )
            except:
                self.log("⚠️ 未找到 Edge，尝试使用 Chrome...")
                browser = await p.chromium.launch(headless=False, channel="chrome", args=["--start-maximized"])

            context = await browser.new_context(viewport=None, ignore_https_errors=True)

            self.log(f">>> 开始处理 {len(lines)} 个账号...")
            tasks = []
            pages_info = [] 

            for line in lines:
                if line.startswith("#"): continue
                parts = line.split("|")
                if len(parts) >= 2:
                    url = parts[0].strip()
                    acc = parts[1].strip()
                    pwd = parts[2].strip() if len(parts) > 2 else "NONE"
                    
                    page = await context.new_page()
                    
                    # 记录页面信息
                    pages_info.append({
                        "page": page,
                        "account": acc,
                        "last_msg": ""
                    })
                    
                    tasks.append(self.smart_login(page, url, acc, pwd))

            if tasks:
                await asyncio.gather(*tasks)
                self.log("\n✅ 登录完成，正在启动监控...")
                self.log(f">>> 🔥 监控目标: {TARGET_SELECTOR}")

                # 死循环监控
                while True:
                    for info in pages_info:
                        try:
                            page = info['page']
                            if page.is_closed(): continue
                            
                            # 直接找这两个元素
                            elements = await page.locator(TARGET_SELECTOR).all()
                            
                            if elements:
                                # 只读第一个匹配到的（通常是最新的那条）
                                new_text = await elements[0].text_content()
                                if new_text:
                                    new_text = new_text.strip()
                                    if new_text and new_text != info['last_msg']:
                                        # 发现新消息！
                                        self.log(f"🔔 [{info['account']}] 新消息: {new_text}")
                                        info['last_msg'] = new_text
                        except:
                            pass
                    
                    await asyncio.sleep(3) # 每3秒检查一次
            
            await asyncio.Future() 

    async def smart_login(self, page, url, account, password):
        try:
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
            # self.log(f"[{account}] 打开网页...") 
            try:
                await page.goto(url, timeout=60000, wait_until='domcontentloaded')
            except:
                pass

            await page.wait_for_timeout(2000)

            # 智能填账号
            try:
                inputs = await page.locator("input:visible").all()
                filled = False
                for inp in inputs:
                    type_attr = await inp.get_attribute("type") or "text"
                    if type_attr not in ["hidden", "submit", "button", "checkbox", "file"]:
                        await inp.fill(account)
                        filled = True
                        break
                if not filled and inputs: await inputs[0].fill(account)
            except: pass

            # 智能填密码
            if password.strip() != "NONE":
                try:
                    await page.fill("input[type='password']", password)
                except: pass

            # 智能点登录
            try:
                await page.click("button:has-text('登录'), button:has-text('Login'), input[value='登录']", timeout=3000)
                self.log(f"[{account}] ✅ 点击登录")
            except:
                await page.keyboard.press("Enter")

        except Exception as e:
            self.log(f"[{account}] ❌ 登录出错: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = AutoLoginMonitorApp(root)
    root.mainloop()
