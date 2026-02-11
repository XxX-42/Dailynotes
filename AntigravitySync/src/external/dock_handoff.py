#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Dock Handoff Observer & Auto-Trigger
--------------------------------------------------
通过 Accessibility API (AXObserver) 实现对 macOS Dock 栏
“接力 (Handoff)”图标的静默监听与自动触发。

依赖:
    pip install pyobjc-framework-ApplicationServices pyobjc-framework-Cocoa

机制:
    使用 AXObserver 监听 Dock 进程的 UI 布局变更事件 (kAXLayoutChangedNotification)。
    一旦检测到 Handoff 图标出现 (AXIsHandoff=True)，立即执行点击 (kAXPressAction)。
    全程无轮询，资源占用极低。
"""

import sys
import time
import signal
import threading
from typing import Optional

import objc
from AppKit import NSWorkspace, NSRunLoop
from Foundation import NSObject, NSLog, NSRunLoopCommonModes, NSDate
from ApplicationServices import (
    AXUIElementCreateApplication,
    AXObserverCreate,
    AXObserverAddNotification,
    AXObserverGetRunLoopSource,
    AXUIElementCopyAttributeValue,
    AXUIElementPerformAction,
    AXIsProcessTrusted,
    kAXLayoutChangedNotification,
    kAXCreatedNotification,
    kAXUIElementDestroyedNotification,
    kAXPressAction,
    kAXWindowsAttribute,
    kAXChildrenAttribute,
    kAXRoleAttribute,
    kAXSubroleAttribute,
    AXUIElementGetPid
)
from CoreFoundation import (
    CFRunLoopGetCurrent,
    CFRunLoopAddSource,
    CFRunLoopRun,
    CFRunLoopStop,
    kCFRunLoopDefaultMode
)

# 配置常量
TARGET_BUNDLE_ID = "com.apple.dock"
ATTR_AX_IS_HANDOFF = "AXIsHandoff"  # 这是一个非标准属性，仅 Dock 图标特有，但也可能需要检查 Subrole

class HandoffObserver:
    def __init__(self):
        self.dock_pid: Optional[int] = None
        self.dock_element = None
        self.observer = None
        self.loop = None
        self._setup_complete = False

    def check_permissions(self):
        """检查辅助功能权限"""
        if not AXIsProcessTrusted():
            print("❌ 错误: 缺少辅助功能权限 (Accessibility Permissions)。")
            print("请在 '系统设置 > 隐私与安全性 > 辅助功能' 中添加此终端/编辑器。")
            sys.exit(1)
        print("✅ 辅助功能权限已获取。")

    def get_dock_pid(self):
        """获取 Dock 进程的 PID"""
        workspace = NSWorkspace.sharedWorkspace()
        for app in workspace.runningApplications():
            if app.bundleIdentifier() == TARGET_BUNDLE_ID:
                self.dock_pid = app.processIdentifier()
                print(f"📍 已定位 Dock 进程 (PID: {self.dock_pid})")
                return
        
        print("❌ 错误: 未找到正在运行的 Dock 进程。")
        sys.exit(1)

    def scan_for_handoff_item(self, element, depth=0):
        """
        递归扫描 UI 元素树寻找 Handoff 图标
        注意: Handoff 图标通常是 Dock 的子元素，Role 为 AXDockItem (可能)
        但最可靠的是检查 attributes 中是否包含 AXIsHandoff 且为 True
        """
        if depth > 3: # 防止过深递归，Dock 结构通常很扁平
            return False

        # 1. 检查当前元素是否是 Handoff
        try:
            # 尝试获取 AXIsHandoff 属性
            # 注意: 这是一个私有/特殊属性，不一定在所有系统版本通过常规 CopyAttributeValue 获取
            # 但在 PyObjC 中可以直接尝试
            is_handoff, error = AXUIElementCopyAttributeValue(element, ATTR_AX_IS_HANDOFF, None)
            if error == 0 and is_handoff is True:
                print(f"🚀 发现 Handoff 图标! 准备触发...")
                self.trigger_action(element)
                return True
            
            # 备选策略: 检查 Subrole (如果是 'AXHandoffDockItem' 或类似)
            subrole, error = AXUIElementCopyAttributeValue(element, kAXSubroleAttribute, None)
            if error == 0 and subrole == "AXHandoffDockItem":
                print(f"🚀 通过 Subrole 发现 Handoff 图标! 准备触发...")
                self.trigger_action(element)
                return True

        except Exception as e:
            # 某些属性获取可能会失败，忽略
            pass

        # 2. 获取子元素继续搜索
        children, error = AXUIElementCopyAttributeValue(element, kAXChildrenAttribute, None)
        if error == 0 and children:
            for child in children:
                if self.scan_for_handoff_item(child, depth + 1):
                    return True
        
        return False

    def trigger_action(self, element):
        """执行点击动作"""
        error = AXUIElementPerformAction(element, kAXPressAction)
        if error == 0:
            print("✅ 成功执行点击 (AXPress)！Handoff 接力已激活。")
        else:
            print(f"⚠️ 点击失败 (Error Code: {error})。尝试 AXShowMenu...")
            # 备选: 有些图标可能不支持 Press，尝试弹出菜单
            AXUIElementPerformAction(element, "AXShowMenu")

    def observer_callback(self, observer, element, notification, refcon):
        """
        AXObserver 的回调函数
        注意: 这个回调是在 CFRunLoop 中执行的
        """
        # print(f"收到通知: {notification}") # 调试用，生产环境关闭以减少噪音
        
        if notification in [kAXLayoutChangedNotification, kAXCreatedNotification]:
            # 当 Dock 布局改变（例如新图标出现）时扫描
            threading.Thread(target=self.scan_dock, daemon=True).start()

    def scan_dock(self):
        """扫描整个 Dock 列表"""
        # 注意：这里需要要在主线程或者确保 AX 操作线程安全
        # 简单起见，我们在回调线程直接扫描，或者在此次扫描
        if not self.dock_element:
            self.dock_element = AXUIElementCreateApplication(self.dock_pid)
        
        # 获取 Dock 的主列表 (通常是 AXList)
        # Dock 的结构通常是: Application -> AXList (Role=AXList) -> AXSystemWide -> ...
        # 直接从 App 根节点扫子节点
        self.scan_for_handoff_item(self.dock_element)

    def start_observing(self):
        self.check_permissions()
        self.get_dock_pid()

        # 1. 创建 Dock 应用的 AX 元素引用
        self.dock_element = AXUIElementCreateApplication(self.dock_pid)

        # 2. 定义回调包装器
        def callback_wrapper(observer, element, notification, refcon):
            self.observer_callback(observer, element, notification, refcon)

        # 3. 创建观察者
        self.observer, error = AXObserverCreate(self.dock_pid, callback_wrapper, None)
        if error != 0:
            print(f"❌ 无法创建观察者 (Error: {error})")
            return

        # 4. 添加通知监听
        # 监视布局改变 (图标出现/消失)
        AXObserverAddNotification(self.observer, self.dock_element, kAXLayoutChangedNotification, None)
        # 监视UI元素创建 (作为备份)
        AXObserverAddNotification(self.observer, self.dock_element, kAXCreatedNotification, None)

        # 5. 将观察者添加到 RunLoop
        run_loop_source = AXObserverGetRunLoopSource(self.observer)
        CFRunLoopAddSource(CFRunLoopGetCurrent(), run_loop_source, kCFRunLoopDefaultMode)

        print("👀 Handoff 监听器已启动。等待 Dock 变化...")
        print("按 Ctrl+C 退出。")

        # 6. 初次扫描 (防止启动时 Handoff 已经存在)
        self.scan_dock()

        # 7. 启动 RunLoop
        self.loop = CFRunLoopGetCurrent()
        CFRunLoopRun()

    def stop(self):
        if self.loop:
            CFRunLoopStop(self.loop)

def main():
    observer = HandoffObserver()
    
    # 优雅退出处理
    def signal_handler(sig, frame):
        print("\n正在停止监听器...")
        observer.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        observer.start_observing()
    except Exception as e:
        print(f"发生异常: {e}")
        # 如果不是主线程异常，可能需要额外处理

if __name__ == "__main__":
    main()
