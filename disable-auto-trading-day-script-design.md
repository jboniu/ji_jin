# 停用交易日自动执行脚本设计概要

## 核心功能
1. 去掉项目内“交易日自动执行日报脚本”的触发入口。
2. 保留手动执行能力，不删除 `run_daily_report.bat` 和报告生成主脚本。
3. 停用后，只有用户手动运行脚本或通过页面主动生成报告时才会执行。

## 主要文件
- [register_daily_task.ps1](D:/Project/ZJ-MY-PROJECT/ji_jin/register_daily_task.ps1) - Windows 任务计划注册脚本
- [README.md](D:/Project/ZJ-MY-PROJECT/ji_jin/README.md) - 当前自动执行说明
- [run_daily_report.bat](D:/Project/ZJ-MY-PROJECT/ji_jin/run_daily_report.bat) - 手动执行入口，保留

## 修复步骤
1. 先排查当前项目里所有自动执行入口，确认是否只有 Windows 任务计划脚本。
2. 注释或移除自动注册/自动触发逻辑，但保留手动运行脚本。
3. 同步更新 README，避免后续再按旧说明注册自动任务。

## 验证方式
1. 项目内不再保留“默认每个工作日自动执行”的说明或自动注册入口。
2. 手动运行 [run_daily_report.bat](D:/Project/ZJ-MY-PROJECT/ji_jin/run_daily_report.bat) 仍然可用。
3. 电脑在交易日不会再因为项目脚本自动触发日报生成。
