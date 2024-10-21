# Twitter 2 Bsky

[//]: # (第一次写中文 README，饶了我吧)

本项目旨在帮助用户自动化从推特到 Bluesky 的关注过程。请严格按照以下步骤配置您的开发环境，并阅读项目说明以确保安全和正确使用。

如果本项目对您有所帮助，请考虑为该项目点个 Star。谢谢！

## 项目说明

本项目的功能是从您已经登录的推特账号中抓取关注列表，并在 Bluesky 平台上自动搜索对应的用户并进行关注。特别适用于有大量关注列表的用户。

### 使用须知

1. **推特账号登录**：
    - 项目运行期间，您需要在浏览器中登录您的推特账号。需要特别注意的是，项目目录中的 `persistent` 文件夹保存了会话信息。为了保障账户安全，避免将该文件夹泄露给他人。

2. **Bluesky 账号信息**：
    - 项目会要求您输入 Bluesky 的用户名和密码。这些登陆凭证仅在程序运行过程中使用，不会以任何形式保存在本地。

## 环境设置步骤

### 1. 检查并安装 Git

1. 在您的计算机上，打开“命令提示符”或“PowerShell”。
2. 输入 `git --version`：
    - 如果返回版本号，Git 已安装。
    - 如果命令不能识别，请从 [Git 官网](https://git-scm.com/) 下载并安装。

### 2. 检查并安装合适的 Python 版本

1. 输入 `py -0p` 检查已安装的 Python 版本：
    - 查找 3.10 或 3.11 开头的版本。
    - 如果没有合适的版本，访问 [Python 官网](https://www.python.org/downloads/) 安装 Python 3.10。

### 3. 创建 Python 虚拟环境

1. 在项目目录内打开“命令提示符”或“PowerShell”。
2. 输入以下命令（根据 Python 版本修改 `-3.10`）：
   ```
   py -3.10 -m venv env
   ```
3. 输入以下命令激活虚拟环境：
   ```
   .\env\Scripts\Activate
   ```

### 4. 安装项目依赖

1. 确保虚拟环境被激活（提示符显示 `(env)`）。
2. 在项目目录中找到 `requirements.txt`。
3. 输入以下命令安装依赖：
   ```
   pip install -r requirements.txt
   ```

### 5. 运行主脚本

1. 激活虚拟环境状态下，输入：
   ```
   python main.py
   ```
2. 按提示在程序中输入 Bluesky 的账号信息。

## 注意事项

- 隐私保护：确保 `persistent` 文件夹不被他人获取。
- 凭证安全：Bluesky 凭证仅供运行时使用，不会保存。
- 请确保执行时已满足系统权限要求。

## 问题反馈

如有问题或建议，请在 [GitHub Issues](https://github.com/nullqwertyuiop/twitter2bsky/issues) 中提出。

## 许可证

本项目使用 MIT 许可证。详细信息请参阅 [LICENSE](LICENSE) 文件。

## Works on My Machine

![Works on My Machine](assets/works-on-my-machine.png)
