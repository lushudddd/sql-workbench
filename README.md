# SQL 工作台

面向 Windows 的 MySQL / Oracle 脚本客户端。左侧维护连接，右侧编辑 SQL，底部切换结果集。

## 界面与使用流程

```mermaid
flowchart LR
    A["数据库连接<br/>新建 · 编辑 · 测试"] --> B["SQL 编辑器<br/>粘贴 SQL 或打开脚本"]
    B --> C["执行选中或执行全部"]
    C --> D["执行结果<br/>数据表 · 影响行数 · 错误"]
```

## Windows 安装

在 GitHub 仓库的 **Releases** 下载 `SQLWorkbench-Setup-x64.exe`。双击安装后，从桌面或开始菜单打开「SQL 工作台」。安装包内置 Python 运行环境和两个数据库驱动，可在 Windows 的「已安装的应用」中卸载。当前安装包未签名。

## 从源码运行

需要带 Tkinter 的 Python 3.10 或更新版本。在项目目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

## 构建安装包

安装带简体中文语言文件的 Inno Setup 7。使用 64 位 Python，在项目目录执行：

```powershell
.\.venv\Scripts\python.exe -m pip install "pyinstaller>=6,<7"
.\build.ps1 -Python ".\.venv\Scripts\python.exe" -Compiler "C:\路径\ISCC.exe"
```

产物位于 `release/SQLWorkbench-Setup-x64.exe`，发布时作为 GitHub Release 附件上传。

## 连接与验证

1. 点击「新建」，填写连接名称、主机、端口和用户名。MySQL 默认端口为 3306，默认数据库可空。Oracle 默认端口为 1521，填写监听器提供的服务名，例如 `FREEPDB1`。
2. 点击「测试连接」并输入密码。连接配置保存在 `%LOCALAPPDATA%\SQLWorkbench\connections.json`，密码每次输入。
3. 粘贴下面对应的脚本，点击「执行全部」。结果区应出现两个查询结果集。也可以选中一条完整语句或一个完整 PL/SQL 块后点击「执行选中」。

MySQL

```sql
SELECT VERSION() AS server_version;
SELECT DATABASE() AS current_database;
```

Oracle

```sql
SELECT SYS_CONTEXT('USERENV', 'SERVICE_NAME') AS service_name FROM dual;
BEGIN
  NULL;
END;
/
SELECT 1 AS connected FROM dual;
```

## 执行规则

- MySQL 通过 Connector/Python 处理多语句与 `DELIMITER`。Oracle 使用 Thin 模式按服务名连接，普通 SQL 用分号分隔，多个 PL/SQL 块或混合脚本中的 PL/SQL 块用独占一行的 `/` 收尾。范围为 SQL 和 PL/SQL 脚本，SQL*Plus 指令如 `@文件`、`SET SERVEROUTPUT` 和变量替换暂未实现。
- 每次执行使用一个数据库会话。默认关闭自动提交，需要持久化的事务可在同一次脚本运行中显式 `COMMIT`，或勾选「自动提交」。会话关闭时回滚仍未提交的事务。数据库自带的隐式提交规则仍适用。
- 每个结果集最多展示前 500 行。「停止后续处理」在当前驱动操作返回后生效；MySQL 已发送给服务端的同批语句仍可能执行。
