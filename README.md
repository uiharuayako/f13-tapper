# F13 Tapper

Windows 桌面小工具：按设置的频率，重复按下并松开 F13。中文界面，便携单文件 EXE，使用时不需要安装 Python。

## 下载和使用

在 [GitHub Releases](https://github.com/uiharuayako/f13-tapper/releases/latest) 下载 `F13Tapper.exe`，双击打开。

1. 设置频率：**0.1～100 次/秒**，默认 **10 次/秒**。
2. 点击 **开始**；界面显示状态、次数和运行时间。
3. 点击 **停止** 结束发送。关闭窗口也会停止。

打开程序不会自动连按。运行期间频率输入框锁定，停止后可以更改，再次开始会重置本轮计数。
勾选 **测试模式** 可以检查频率和开始/停止行为，不发送任何按键。
按住 **Ctrl、Shift、Alt 或 Win** 时，实际发送自动暂停，松开后继续。

面向 Windows 10/11 x64。当前 Release 为未签名的便携程序。
`SHA256SUMS.txt` 提供 EXE 的 SHA-256，可用 PowerShell 核对：

```powershell
Get-FileHash .\F13Tapper.exe -Algorithm SHA256
```

## 对电脑功能的影响

F13 是独立功能键（`VK_F13 = 0x7C`），不会输入文本。程序使用正常等待，不忙等，10 次/秒时的循环开销预计很低；
每次按下和松开一起投递，卡顿后跳过过期周期，不集中补发。界面设置的是目标频率，系统调度、修饰键暂停和软件处理会影响实际频率。

- **快捷键：** 如果前台软件或全局宏绑定了 F13，可能按指定频率触发对应动作。修饰键保护可以降低组合键误触概率，但不能消除检查与发送之间的状态变化。
- **空闲计时：** 模拟输入可能影响离开判定、自动熄屏、屏保或睡眠；取决于系统策略，不能保证防锁屏或防休眠。
- **权限：** 普通权限可能无法向管理员窗口、锁屏、安全桌面或过滤模拟输入的软件发送按键。投递失败时停止并报告错误；投递成功也不代表目标应用已经执行动作。

程序不设置自启动，不修改电源或注册表，不访问网络，不保存使用记录。停止后不再产生后续输入；已经触发的软件动作不会自动撤销。

依据：[微软 SendInput](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput)、
[GetLastInputInfo](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getlastinputinfo)、
[System Sleep Criteria](https://learn.microsoft.com/en-us/windows/win32/power/system-sleep-criteria)。

## 从源码运行

需要 Windows 与 Python 3.12（含 tkinter）。运行不需要第三方依赖：

```powershell
python .\f13_gui.py
python -m unittest discover -s tests -v
```

## 构建 EXE

在 Windows x64 上运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

脚本创建独立 `.build-venv`，安装锁定版本的 PyInstaller，运行测试，打包无控制台的单文件 EXE，
再运行 EXE 自检（只使用测试模式，不发送按键）。输出：

- `dist/F13Tapper.exe`
- `dist/SHA256SUMS.txt`

自检报告在 `build/exe-smoke-test.json`。构建目录与本机报告不会提交到源码仓库。
如需指定 Python，可使用 `-Python C:\path\to\python.exe`。

已执行的验证及其边界见 [docs/verification.md](docs/verification.md)。

## 许可

[MIT](LICENSE)。Python、Tcl/Tk 与 PyInstaller 等打包组件仍受各自许可条款约束。
