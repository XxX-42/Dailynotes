import sys
import os
import time

try:
    import ApplicationServices
    from AppKit import NSWorkspace, NSApplicationActivateIgnoringOtherApps
    import EventKit
except ImportError as e:
    print(f"错误: 导入失败 ({e})。请确保已安装 pyobjc-framework-ApplicationServices, Cocoa, EventKit。")
    sys.exit(1)

def check_handoff():
    try:
        # 1. 初始化背景环境 (有些系统需要先初始化一次 EventKit 才能正确读取相关状态)
        store = EventKit.EKEventStore.alloc().init()

        # 2. 查找 Dock 进程并扫描 UI
        dock_apps = [app for app in NSWorkspace.sharedWorkspace().runningApplications() if app.bundleIdentifier() == 'com.apple.dock']
        if not dock_apps:
            return False
        
        dock_pid = dock_apps[0].processIdentifier()
        dock_element = ApplicationServices.AXUIElementCreateApplication(dock_pid)
        
        def scan_elements(element, depth=0):
            if depth > 4: return False
            
            result, children = ApplicationServices.AXUIElementCopyAttributeValue(element, 'AXChildren', None)
            if result != ApplicationServices.kAXErrorSuccess or not children:
                return False
            
            for child in children:
                _, desc = ApplicationServices.AXUIElementCopyAttributeValue(child, 'AXDescription', None)
                _, title = ApplicationServices.AXUIElementCopyAttributeValue(child, 'AXTitle', None)
                _, subrole = ApplicationServices.AXUIElementCopyAttributeValue(child, 'AXSubrole', None)
                
                desc_str = str(desc).lower() if desc else ""
                title_str = str(title).lower() if title else ""
                subrole_str = str(subrole).lower() if subrole else ""
                
                if any(x in s for x in ["handoff", "接力", "from"] for s in [desc_str, title_str, subrole_str]):
                    return {"element": child, "title": title, "desc": desc}
                
                res = scan_elements(child, depth + 1)
                if res: return res
            return False

        return scan_elements(dock_element)
        
    except Exception:
        return False

if __name__ == "__main__":
    print(">>> Handoff 持续监测已启动 (含自动静默点击) <<<", flush=True)
    last_found_state = False
    
    try:
        while True:
            result = check_handoff()
            
            if result:
                if not last_found_state:
                    is_memo = any(x in str(result['title']) for x in ["备忘录", "Notes"])
                    
                    if is_memo:
                        print(f"\n[{time.strftime('%H:%M:%S')}] 【发现备忘录接力 - 执行静默点击】")
                        
                        # 1. 记录当前前台应用 (为了不抢焦点)
                        current_app = NSWorkspace.sharedWorkspace().frontmostApplication()
                        
                        # 2. 点击接力图标
                        # 延迟微调，确保系统稳定
                        time.sleep(0.1)
                        error = ApplicationServices.AXUIElementPerformAction(result['element'], 'AXPress')
                        
                        if error == ApplicationServices.kAXErrorSuccess:
                            # 3. 极速夺回焦点 & 隐藏备忘录
                            # 立即恢复之前的应用，减少闪烁
                            if current_app:
                                current_app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
                            
                            # 尝试找到备忘录并隐藏 (给一点启动时间)
                            for _ in range(5): 
                                notes_apps = [app for app in NSWorkspace.sharedWorkspace().runningApplications() if app.bundleIdentifier() == 'com.apple.Notes']
                                if notes_apps:
                                    notes_apps[0].hide()
                                    break
                                time.sleep(0.1)
                                
                            print(f"[{time.strftime('%H:%M:%S')}] 已触发同步并请求后台运行")
                        else:
                            print(f"[{time.strftime('%H:%M:%S')}] 点击失败 (错误代码: {error})")
                    else:
                        print(f"\n[{time.strftime('%H:%M:%S')}] 【发现其他接力应用: {result['title']} - 已略过】")
                        print(f"  来源: {result['desc']}")
                        
                    last_found_state = True
            else:
                if last_found_state:
                    print(f"[{time.strftime('%H:%M:%S')}] Handoff 已从 Dock 消失")
                    last_found_state = False
            
            time.sleep(1) # 基准扫描频率
    except KeyboardInterrupt:
        print("\n>>> 监测已停止 <<<")
