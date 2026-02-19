import sys
from AppKit import NSWorkspace
import ApplicationServices

print("Python 路径:", sys.executable)
print("环境变量集已就绪...")

try:
    dock_apps = [app for app in NSWorkspace.sharedWorkspace().runningApplications() if app.bundleIdentifier() == 'com.apple.dock']
    print(f"找到 Dock 进程: {len(dock_apps) > 0}")
    
    trusted = ApplicationServices.AXIsProcessTrusted()
    print(f"辅助功能权限状态: {trusted}")
    
except Exception as e:
    print(f"发生错误: {e}")
