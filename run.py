import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
import asyncio
import threading
import os
import sys
import random
from playwright.async_api import async_playwright

# ================= 配置区域 =================
TARGET_SELECTOR = ".lastNewMsg, .visitorMsg"
# ===========================================

class AutoLoginMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Edge 客服助手 (按钮调试版)")
        self.root.geometry("800x600")
        
        self.frame_top = tk.Frame(root, pady=10)
        self.frame_top.pack(fill='x', padx=10)
        
        self.btn_select = tk.Button(self.frame_top, text="📂 选择账号文件", command=self.select_file, font=("Arial", 10))
        self.btn_select.pack(side='left', padx=5)

        self.lbl_file = tk.Label(self.frame_top, text="未选择文件", fg="gray")
        self.lbl_file.pack(side='left', padx=5)

        self.btn_start = tk.Button(root, text="🚀 启动并开始监控", command=self.start_thread, 
                                   bg="#007AFF", fg="white", font=("Arial", 14, "bold"), height=2)
        self.btn_start.pack(fill='x', padx=20, pady=10)
        
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
            self.base_path = os.path.dirname(sys.executable)
        else:
            self.base_path = os.path.dirname(os.path.abspath(__file__))
            
        default_file = os.path.join(self.base_path, "accounts.txt")
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
        self.log(">>> 正在启动 (调试模式)...")
        
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
        except Exception as e:
            self.log(f"❌ 读取文件失败: {e}")
            return

        user_data_dir = os.path.join(self.base_path, "Edge_UserData")
        if not os.path.exists(user_data_dir):
            os.makedirs(user_data_dir)

        async with async_playwright() as p:
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-first-run",
            ]
            
            try:
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    channel="msedge", 
                    headless=False,
                    args=launch_args,
                    viewport={"width": 1920, "height": 1080},
                    ignore_https_errors=True,
                    ignore_default_args=["--enable-automation"]
                )
            except Exception as e:
                self.log(f"❌ 启动失败: {e}")
                self.log("💡 请关闭所有 Edge 窗口！")
                return

            # 注入 stealth 补丁
            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")

            self.log(f">>> 开始处理 {len(lines)} 个账号...")
            tasks = []
            pages_info = [] 

            first_page = context.pages[0] if context.pages else await context.new_page()
            first_page_used = False

            for line in lines:
                if line.startswith("#"): continue
                parts = line.split("|")
                if len(parts) >= 2:
                    url = parts[0].strip()
                    acc = parts[1].strip()
                    pwd = parts[2].strip() if len(parts) > 2 else "NONE"
                    
                    # 读取第4列：如果填了，就是自定义的登录按钮
                    custom_login_btn = parts[3].strip() if len(parts) > 3 else None

                    if not first_page_used:
                        page = first_page
                        first_page_used = True
                    else:
                        page = await context.new_page()
                    
                    pages_info.append({
                        "page": page,
                        "account": acc,
                        "last_msg": ""
                    })
                    
                    tasks.append(self.smart_login(page, url, acc, pwd, custom_login_btn))

            if tasks:
                await asyncio.gather(*tasks)
                self.log("\n✅ 登录流程结束，监控中...")
                
                while True:
                    for info in pages_info:
                        try:
                            page = info['page']
                            if page.is_closed(): continue
                            
                            elements = await page.locator(TARGET_SELECTOR).all()
                            if elements:
                                new_text = await elements[0].text_content()
                                if new_text:
                                    new_text = new_text.strip()
                                    if new_text and new_text != info['last_msg']:
                                        self.log(f"🔔 [{info['account']}] 新消息: {new_text}")
                                        info['last_msg'] = new_text
                        except:
                            pass
                    await asyncio.sleep(3)
            
            await asyncio.Future() 

    async def smart_login(self, page, url, account, password, custom_btn_selector):
        try:
            self.log(f"[{account}] 打开网页...")
            try:
                await page.goto(url, timeout=60000, wait_until='domcontentloaded')
            except: pass

            await page.wait_for_timeout(random.randint(1500, 2500))

            # === 1. 确定登录按钮是谁 ===
            if custom_btn_selector:
                # 如果 txt 里指定了，就用指定的
                login_btn = page.locator(custom_btn_selector).first
                self.log(f"[{account}] 使用自定义按钮规则: {custom_btn_selector}")
            else:
                # 否则用默认规则（尝试匹配 登录, Login, 确定 等）
                # 注意：这里增加了一些常见的非 button 标签的按钮
                login_btn = page.locator("button:has-text('登录'), button:has-text('Login'), input[value='登录'], a:has-text('登录'), div[role='button']:has-text('登录')").first
            
            # === 2. 检查是否已登录 ===
            # 如果找不到登录按钮，且没填密码，可能就是已登录
            if await login_btn.count() == 0 and password == "NONE":
                self.log(f"[{account}] ✅ 未找到登录按钮，假设已登录")
                return

            self.log(f"[{account}] 正在输入...")
            
            # 填账号
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

            # 填密码
            if password.strip() != "NONE":
                try:
                    await page.click("input[type='password']")
                    await page.type("input[type='password']", password, delay=100)
                except: pass

            # === 3. 关键：高亮并点击 ===
            try:
                if await login_btn.count() > 0:
                    # 🔥 高亮显示（画个红框给用户看）
                    await login_btn.highlight()
                    self.log(f"[{account}] 🔴 已高亮即将点击的按钮，请观察！")
                    await page.wait_for_timeout(2000) # 停2秒给你看

                    # 点击
                    # force=True 可以强行点击被遮挡的按钮
                    await login_btn.click(force=True)
                    self.log(f"[{account}] ✅ 点击动作已执行")
                    
                    # 等待页面反应
                    await page.wait_for_timeout(5000)
                    
                    # 检查是否弹出了新标签页 (针对某些跳转逻辑)
                    all_pages = page.context.pages
                    if len(all_pages) > 1 and all_pages[-1] != page:
                        self.log(f"[{account}] ⚠️ 检测到新弹窗，自动切换到新页面")
                        # 如果有新页面，就把 info 里的 page 换成新的
                        # (这里代码逻辑比较简单，主要为了提示用户)
                else:
                    self.log(f"[{account}] ⚠️ 找不到登录按钮，尝试回车")
                    await page.keyboard.press("Enter")

            except Exception as e:
                self.log(f"[{account}] 点击失败: {e}")

        except Exception as e:
            self.log(f"[{account}] 流程提示: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = AutoLoginMonitorApp(root)
    root.mainloop()
