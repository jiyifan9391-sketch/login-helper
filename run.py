import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
import asyncio
import threading
import os
import sys
from playwright.async_api import async_playwright

# ================= 配置区域 =================
# 消息选择器 (根据你的网页实际情况修改)
UNIVERSAL_SELECTOR = ".lastNewMsg, .visitorMsg, .el-badge__content"
# ===========================================

class AutoLoginMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Edge 批量登录 & 消息监控助手")
        self.root.geometry("800x600")
        
        # 1. 顶部操作区
        self.frame_top = tk.Frame(root, pady=10)
        self.frame_top.pack(fill='x', padx=10)
        
        self.btn_select = tk.Button(self.frame_top, text="📂 选择账号文件 (accounts.txt)", command=self.select_file, font=("Arial", 10))
        self.btn_select.pack(side='left', padx=5)

        self.lbl_file = tk.Label(self.frame_top, text="未选择文件", fg="gray")
        self.lbl_file.pack(side='left', padx=5)

        # 2. 核心按钮
        self.btn_start = tk.Button(root, text="🚀 启动 Edge 并开始监控", command=self.start_thread, 
                                   bg="#007AFF", fg="white", font=("Arial", 14, "bold"), height=2)
        self.btn_start.pack(fill='x', padx=20, pady=10)
        
        # 3. 日志/消息显示区
        self.log_area = scrolledtext.ScrolledText(root, width=90, height=25, font=("Arial", 11))
        self.log_area.pack(padx=10, pady=10, expand=True, fill='both')
        
        self.file_path = ""
        
        # 自动尝试寻找同目录下的 accounts.txt
        self.try_find_default_file()

    def log(self, msg):
        """往界面上打印日志"""
        def _update():
            self.log_area.insert(tk.END, f"{msg}\n")
            self.log_area.see(tk.END)
        self.root.after(0, _update)

    def try_find_default_file(self):
        # 获取当前运行目录
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
        """在子线程中运行 asyncio"""
        asyncio.run(self.main_logic())

    async def main_logic(self):
        self.log(">>> 正在启动 Edge 浏览器...")
        
        # 读取账号
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
        except Exception as e:
            self.log(f"❌ 读取文件失败: {e}")
            return

        async with async_playwright() as p:
            # 1. 启动浏览器
            try:
                browser = await p.chromium.launch(
                    headless=False, 
                    channel="msedge",  # 强制使用 Edge
                    args=["--start-maximized", "--disable-blink-features=AutomationControlled"]
                )
            except Exception:
                self.log("⚠️ 未找到 Edge，尝试使用 Chrome...")
                browser = await p.chromium.launch(headless=False, channel="chrome", args=["--start-maximized"])

            # 2. 创建上下文 (单窗口)
            context = await browser.new_context(
                viewport=None, 
                ignore_https_errors=True
            )

            # 3. 批量登录阶段
            self.log(f">>> 开始批量登录 {len(lines)} 个账号...")
            tasks = []
            pages_info = [] # 存储页面信息用于后续监控

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
                self.log("\n✅ 所有账号登录操作已完成！")
                self.log(">>> 🔥 正在切换进入 [消息监控模式] ...")
                self.log(f">>> 正在监听 {len(pages_info)} 个标签页的 {MSG_SELECTOR} 元素\n")

                # 4. 进入死循环监控阶段
                while True:
                    for info in pages_info:
                        try:
                            page = info['page']
                            if page.is_closed(): continue
                            
                            # 尝试获取最新消息
                            # timeout=100 意味着只花0.1秒检查，不卡顿
                            elements = await page.locator(MSG_SELECTOR).all()
                            
                            if elements:
                                # 获取文本
                                new_text = await elements[0].text_content()
                                if new_text:
                                    new_text = new_text.strip()
                                    # 如果有新消息，且跟上次不一样
                                    if new_text and new_text != info['last_msg']:
                                        current_time = asyncio.get_event_loop().time()
                                        self.log(f"🔔 [{info['account']}] 新消息: {new_text}")
                                        info['last_msg'] = new_text
                        except Exception as e:
                            # 页面可能被手动关闭了，忽略错误
                            pass
                    
                    # 每隔 3 秒轮询一次
                    await asyncio.sleep(3)
            
            # 保持浏览器不关闭 (逻辑上上面是死循环，这里其实走不到，除非出错)
            await asyncio.Future() 

    async def smart_login(self, page, url, account, password):
        try:
            # 防检测
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
            
            self.log(f"[{account}] 打开网页...")
            try:
                await page.goto(url, timeout=60000, wait_until='domcontentloaded')
            except:
                self.log(f"[{account}] ⚠️ 加载较慢")

            await page.wait_for_timeout(2000)

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
            except:
                pass

            # 填密码
            if password.strip() != "NONE":
                try:
                    await page.fill("input[type='password']", password)
                except: pass

            # 点登录
            try:
                await page.click("button:has-text('登录'), button:has-text('Login'), input[value='登录']", timeout=3000)
                self.log(f"[{account}] ✅ 点击登录")
            except:
                await page.keyboard.press("Enter")

        except Exception as e:
            self.log(f"[{account}] ❌ 出错: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = AutoLoginMonitorApp(root)
    root.mainloop()
