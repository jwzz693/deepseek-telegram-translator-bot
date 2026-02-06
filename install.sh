#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
#  AI 翻译机器人 — 从 GitHub 仓库一键部署
#  
#  用法 (任选一种):
#    curl -sL https://raw.githubusercontent.com/jwzz693/deepseek-telegram-translator-bot/main/install.sh | sudo bash
#    wget -qO- https://raw.githubusercontent.com/jwzz693/deepseek-telegram-translator-bot/main/install.sh | sudo bash
#    或下载后: sudo bash install.sh
#
#  支持: Debian 10/11/12, Ubuntu 20.04/22.04/24.04
# ═══════════════════════════════════════════════════════════════════

set -e

# ─── 仓库配置 ───
REPO_URL="https://github.com/jwzz693/deepseek-telegram-translator-bot.git"
REPO_BRANCH="main"

# ─── 部署配置 ───
BOT_NAME="telegram-translator-bot"
BOT_DIR="/opt/${BOT_NAME}"
BOT_USER="botuser"
SERVICE_NAME="${BOT_NAME}"
VENV_DIR="${BOT_DIR}/venv"
LOG_DIR="/var/log/${BOT_NAME}"

# ─── 颜色 ───
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ─── 工具函数 ───
info()  { echo -e "  ${GREEN}✓${NC} $1"; }
warn()  { echo -e "  ${YELLOW}!${NC} $1"; }
fail()  { echo -e "  ${RED}✗${NC} $1"; exit 1; }
step()  { echo -e "\n${CYAN}[$1/7]${NC} ${BOLD}$2${NC}"; }
line()  { echo -e "${BLUE}─────────────────────────────────────────────${NC}"; }

# ═══════════════════════════════════════════
#  入口检查
# ═══════════════════════════════════════════
banner() {
    echo ""
    echo -e "${CYAN}╔═════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                                                 ║${NC}"
    echo -e "${CYAN}║   🌐  AI 翻译机器人 — 一键部署                  ║${NC}"
    echo -e "${CYAN}║                                                 ║${NC}"
    echo -e "${CYAN}║   DeepSeek · OpenAI · Claude · Gemini           ║${NC}"
    echo -e "${CYAN}║   Groq · Mistral  全引擎支持                    ║${NC}"
    echo -e "${CYAN}║                                                 ║${NC}"
    echo -e "${CYAN}╚═════════════════════════════════════════════════╝${NC}"
    echo ""
}

check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        fail "请使用 root 权限运行:\n    sudo bash install.sh"
    fi
}

check_os() {
    if [ ! -f /etc/debian_version ] && [ ! -f /etc/lsb-release ]; then
        fail "仅支持 Debian / Ubuntu 系统"
    fi
    OS_NAME=$(. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME" || echo "Debian/Ubuntu")
    info "系统: ${OS_NAME}"
}

# ═══════════════════════════════════════════
#  Step 1: 系统依赖
# ═══════════════════════════════════════════
install_deps() {
    step 1 "安装系统依赖"

    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq > /dev/null 2>&1
    apt-get install -y -qq \
        python3 python3-venv python3-pip python3-dev \
        git curl wget \
        build-essential libssl-dev libffi-dev \
        > /dev/null 2>&1

    # Python 版本检查
    PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
    if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
        fail "需要 Python >= 3.10，当前: ${PY_VER}"
    fi

    info "Python ${PY_VER} ✓"
    info "git $(git --version | awk '{print $3}') ✓"
}

# ═══════════════════════════════════════════
#  Step 2: 创建用户
# ═══════════════════════════════════════════
create_user() {
    step 2 "创建运行用户"

    if id "${BOT_USER}" &>/dev/null; then
        info "用户 ${BOT_USER} 已存在"
    else
        useradd -r -m -s /bin/bash "${BOT_USER}"
        info "已创建用户: ${BOT_USER}"
    fi

    mkdir -p "${LOG_DIR}"
    chown "${BOT_USER}:${BOT_USER}" "${LOG_DIR}"
}

# ═══════════════════════════════════════════
#  Step 3: 克隆仓库
# ═══════════════════════════════════════════
clone_repo() {
    step 3 "从 GitHub 拉取代码"

    if [ -d "${BOT_DIR}/.git" ]; then
        warn "目录已存在，正在更新..."
        cd "${BOT_DIR}"
        # 保留 .env 和 data
        git stash --include-untracked 2>/dev/null || true
        git pull origin "${REPO_BRANCH}" --force
        git stash pop 2>/dev/null || true
        info "代码已更新"
    else
        # 如果目录存在但不是 git 仓库，备份 .env 和 data
        if [ -d "${BOT_DIR}" ]; then
            [ -f "${BOT_DIR}/.env" ] && cp "${BOT_DIR}/.env" /tmp/.env.bak
            [ -d "${BOT_DIR}/data" ] && cp -r "${BOT_DIR}/data" /tmp/data.bak
            rm -rf "${BOT_DIR}"
        fi

        git clone --depth 1 -b "${REPO_BRANCH}" "${REPO_URL}" "${BOT_DIR}"

        # 恢复备份的配置和数据
        [ -f /tmp/.env.bak ] && mv /tmp/.env.bak "${BOT_DIR}/.env" && info "已恢复 .env"
        [ -d /tmp/data.bak ] && rm -rf "${BOT_DIR}/data" && mv /tmp/data.bak "${BOT_DIR}/data" && info "已恢复 data/"

        info "代码已克隆到 ${BOT_DIR}"
    fi

    # 确保 data 目录存在
    mkdir -p "${BOT_DIR}/data"
}

# ═══════════════════════════════════════════
#  Step 4: 配置 .env
# ═══════════════════════════════════════════
configure_env() {
    step 4 "配置环境变量"

    ENV_FILE="${BOT_DIR}/.env"

    # 如果 .env 已存在且已配置，跳过
    if [ -f "${ENV_FILE}" ] && grep -q "TELEGRAM_BOT_TOKEN=.\+" "${ENV_FILE}"; then
        info ".env 已存在，跳过配置"
        # 显示当前配置概要（隐藏敏感信息）
        TOKEN=$(grep "TELEGRAM_BOT_TOKEN=" "${ENV_FILE}" | cut -d= -f2)
        ADMIN=$(grep "ADMIN_USER_IDS=" "${ENV_FILE}" | cut -d= -f2)
        if [ -n "$TOKEN" ]; then
            TOKEN_MASKED="${TOKEN:0:6}...${TOKEN: -4}"
            info "  Token: ${TOKEN_MASKED}"
        fi
        [ -n "$ADMIN" ] && info "  管理员: ${ADMIN}"
        return
    fi

    echo ""
    line
    echo -e "  ${BOLD}请输入配置信息${NC}"
    line
    echo ""

    # Telegram Token
    while true; do
        read -rp "  📱 Telegram Bot Token: " BOT_TOKEN
        if [ -n "${BOT_TOKEN}" ]; then break; fi
        echo -e "  ${RED}Token 不能为空${NC}"
    done

    # DeepSeek API Key
    while true; do
        read -rp "  🤖 DeepSeek API Key: " DEEPSEEK_KEY
        if [ -n "${DEEPSEEK_KEY}" ]; then break; fi
        echo -e "  ${RED}DeepSeek API Key 不能为空${NC}"
    done

    # 可选 Keys
    echo ""
    echo -e "  ${BLUE}以下为可选 API Key（回车跳过）:${NC}"
    read -rp "  🔑 OpenAI API Key: "   OPENAI_KEY
    read -rp "  🔑 Claude API Key: "   CLAUDE_KEY
    read -rp "  🔑 Gemini API Key: "   GEMINI_KEY
    read -rp "  🔑 Groq API Key: "     GROQ_KEY
    read -rp "  🔑 Mistral API Key: "  MISTRAL_KEY

    # 管理员 ID
    echo ""
    while true; do
        read -rp "  👤 管理员用户 ID: " ADMIN_IDS
        if [ -n "${ADMIN_IDS}" ]; then break; fi
        echo -e "  ${RED}管理员 ID 不能为空${NC}"
    done

    # 默认设置
    read -rp "  🤖 默认引擎 [deepseek]: " DEFAULT_PROVIDER
    DEFAULT_PROVIDER=${DEFAULT_PROVIDER:-deepseek}
    read -rp "  🌍 默认语言 [中文]: " DEFAULT_LANG
    DEFAULT_LANG=${DEFAULT_LANG:-中文}

    # 写入 .env
    cat > "${ENV_FILE}" << EOF
# ========== Telegram 配置 ==========
TELEGRAM_BOT_TOKEN=${BOT_TOKEN}

# ========== AI 提供商 API Keys ==========
DEEPSEEK_API_KEY=${DEEPSEEK_KEY}
OPENAI_API_KEY=${OPENAI_KEY}
CLAUDE_API_KEY=${CLAUDE_KEY}
GEMINI_API_KEY=${GEMINI_KEY}
GROQ_API_KEY=${GROQ_KEY}
MISTRAL_API_KEY=${MISTRAL_KEY}

# ========== 默认设置 ==========
DEFAULT_PROVIDER=${DEFAULT_PROVIDER}
DEFAULT_TARGET_LANG=${DEFAULT_LANG}

# 管理员用户 ID（多个用逗号分隔）
ADMIN_USER_IDS=${ADMIN_IDS}
EOF

    chmod 600 "${ENV_FILE}"
    info ".env 配置已保存"
}

# ═══════════════════════════════════════════
#  Step 5: Python 虚拟环境
# ═══════════════════════════════════════════
setup_python() {
    step 5 "安装 Python 依赖"

    cd "${BOT_DIR}"

    if [ ! -d "${VENV_DIR}" ]; then
        python3 -m venv "${VENV_DIR}"
        info "虚拟环境已创建"
    fi

    "${VENV_DIR}/bin/pip" install --upgrade pip -q 2>/dev/null
    "${VENV_DIR}/bin/pip" install -r requirements.txt -q 2>/dev/null
    info "依赖已安装"

    # 验证模块
    "${VENV_DIR}/bin/python" -c "
import src.config
import src.store
import src.translator
import src.providers
import src.handlers
print('  ✓ 所有模块验证通过')
" || fail "模块导入失败，请检查代码"
}

# ═══════════════════════════════════════════
#  Step 6: systemd 服务
# ═══════════════════════════════════════════
setup_service() {
    step 6 "配置 systemd 服务"

    cat > "/etc/systemd/system/${SERVICE_NAME}.service" << EOF
[Unit]
Description=AI Telegram Translator Bot
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${BOT_USER}
Group=${BOT_USER}
WorkingDirectory=${BOT_DIR}
ExecStart=${VENV_DIR}/bin/python src/main.py
Restart=always
RestartSec=10
StartLimitIntervalSec=300
StartLimitBurst=5

# 环境变量
EnvironmentFile=${BOT_DIR}/.env

# 日志
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${BOT_NAME}

# 安全加固
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=${BOT_DIR}/data ${LOG_DIR}
PrivateTmp=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true

[Install]
WantedBy=multi-user.target
EOF

    info "systemd 服务已配置"

    # 安装管理脚本
    if [ -f "${BOT_DIR}/bot.sh" ]; then
        cp "${BOT_DIR}/bot.sh" /usr/local/bin/bot
        chmod +x /usr/local/bin/bot
        info "管理命令 'bot' 已安装"
    fi
}

# ═══════════════════════════════════════════
#  Step 7: 启动
# ═══════════════════════════════════════════
start_bot() {
    step 7 "启动机器人"

    # 设置权限
    chown -R "${BOT_USER}:${BOT_USER}" "${BOT_DIR}"
    chown -R "${BOT_USER}:${BOT_USER}" "${LOG_DIR}"
    chmod 700 "${BOT_DIR}"
    chmod 600 "${BOT_DIR}/.env"

    # 停止旧实例
    systemctl stop "${SERVICE_NAME}" 2>/dev/null || true

    # 重载 + 启动 + 开机自启
    systemctl daemon-reload
    systemctl enable "${SERVICE_NAME}" --quiet
    systemctl start "${SERVICE_NAME}"

    sleep 3

    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        info "机器人启动成功 🎉"
    else
        warn "启动异常，查看日志:"
        journalctl -u "${SERVICE_NAME}" -n 20 --no-pager
        echo ""
        fail "请根据上方日志排查问题"
    fi
}

# ═══════════════════════════════════════════
#  完成
# ═══════════════════════════════════════════
print_done() {
    echo ""
    echo -e "${GREEN}╔═════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║          ✅  部署完成！机器人已运行             ║${NC}"
    echo -e "${GREEN}╚═════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${BOLD}📂 安装目录${NC}    ${BOT_DIR}"
    echo -e "  ${BOLD}📄 配置文件${NC}    ${BOT_DIR}/.env"
    echo -e "  ${BOLD}📊 数据目录${NC}    ${BOT_DIR}/data"
    echo -e "  ${BOLD}🐍 虚拟环境${NC}    ${VENV_DIR}"
    echo ""
    line
    echo -e "  ${BOLD}常用命令:${NC}"
    line
    echo -e "  ${YELLOW}bot status${NC}       查看状态"
    echo -e "  ${YELLOW}bot log${NC}          实时日志"
    echo -e "  ${YELLOW}bot restart${NC}      重启机器人"
    echo -e "  ${YELLOW}bot config${NC}       编辑配置"
    echo -e "  ${YELLOW}bot health${NC}       健康检查"
    echo -e "  ${YELLOW}bot backup${NC}       备份数据"
    echo -e "  ${YELLOW}bot update${NC}       从仓库更新"
    echo -e "  ${YELLOW}bot uninstall${NC}    完全卸载"
    echo ""
    line
    echo -e "  ${BOLD}systemctl 命令:${NC}"
    line
    echo -e "  ${YELLOW}systemctl status ${SERVICE_NAME}${NC}"
    echo -e "  ${YELLOW}journalctl -u ${SERVICE_NAME} -f${NC}"
    echo ""
}

# ═══════════════════════════════════════════
#  主流程
# ═══════════════════════════════════════════
main() {
    banner
    check_root
    check_os
    install_deps
    create_user
    clone_repo
    configure_env
    setup_python
    setup_service
    start_bot
    print_done
}

main "$@"
