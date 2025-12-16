import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
import asyncio
import threading
import os
import sys
from playwright.async_api import async_playwright

# ================= 配置区域 =================
# 消息选择器
TARGET_SELECTOR = ".lastNewMsg, .visitorMsg"
# ===========================================

class AutoLoginMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Edge 客服助手 (防白屏增强版)")
        self.root.geometry("800x600")
        
        self.frame_top = tk.Frame(root, pady=10)
        self.frame_top.pack(fill='x', padx=10)
        
        self.btn_select = tk.Button(self.frame_top, text="📂 选择账号文件 (accounts.txt)", command=self.select_file, font=("Arial", 10))
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
            # === 补丁1：增强启动参数 ===
            # 这些参数能屏蔽更多“我是机器人”的特征
            launch_args = [
                "--start-maximized", 
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars",
                "--exclude-switches=enable-automation"
            ]
            
            try:
                browser = await p.chromium.launch(
                    headless=False, 
                    channel="msedge", 
                    args=launch_args,
                    ignore_default_args=["--enable-automation"] # 移除自动化提示条
                )
            except:
                self.log("⚠️ 未找到 Edge，尝试使用 Chrome...")
                browser = await p.chromium.launch(headless=False, channel="chrome", args=launch_args)

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
                    
                    pages_info.append({
                        "page": page,
                        "account": acc,
                        "last_msg": ""
                    })
                    
                    tasks.append(self.smart_login(page, url, acc, pwd))

            if tasks:
                await asyncio.gather(*tasks)
                self.log("\n✅ 登录流程结束，启动监控...")
                self.log(f">>> 🔥 监控目标: {TARGET_SELECTOR}")

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

    async def smart_login(self, page, url, account, password):
        try:
            # 注入反检测脚本
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
            
            try:
                # 等待页面加载，这里不用 networkidle，防止首页加载太久卡住
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

            # === 补丁2：模拟真人点击登录（关键修改）===
            try:
                # 寻找按钮
                btn = page.locator("button:has-text('登录'), button:has-text('Login'), input[value='登录']").first
                
                if await btn.count() > 0:
                    # 1. 鼠标悬停
                    await btn.hover()
                    # 2. 稍微犹豫一下（真人特征）
                    await page.wait_for_timeout(500)
                    # 3. 点击
                    await btn.click()
                    self.log(f"[{account}] ✅ 点击登录 (模拟真人)")
                    
                    # === 补丁3：等待跳转后的网络静止 ===
                    # 点击后，强制等待网络请求变少，确保新页面加载出来了
                    try:
                        await page.wait_for_load_state("networkidle", timeout=10000)
                    except:
                        pass # 如果超时就不等了，反正已经点过了
                else:
                    await page.keyboard.press("Enter")
                    self.log(f"[{account}] ⚠️ 没找到按钮，尝试回车登录")

            except Exception as e:
                self.log(f"[{account}] 点击出错: {e}")

        except Exception as e:
            self.log(f"[{account}] ❌ 流程出错: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = AutoLoginMonitorApp(root)
    root.mainloop()
