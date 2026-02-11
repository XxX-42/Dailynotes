#!/bin/bash
export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8

git add .
git commit -m "feat: 完善备忘录同步逻辑 (账单分类与排序/启动扫描/时间精简)"
git push origin HEAD
