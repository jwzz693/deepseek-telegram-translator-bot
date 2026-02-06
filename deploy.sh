#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  AI 翻译机器人 — Debian/Ubuntu 一键部署脚本
#  用法: bash deploy.sh
#  支持: Debian 10/11/12, Ubuntu 20.04/22.04/24.04
# ═══════════════════════════════════════════════════════════════

set -e

# ─── 颜色定义 ───
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# ─── 配置 ───
BOT_NAME="telegram-translator-bot"
BOT_DIR="/opt/${BOT_NAME}"
BOT_USER="botuser"
SERVICE_NAME="${BOT_NAME}"
PYTHON_MIN="3.10"
VENV_DIR="${BOT_DIR}/venv"
LOG_DIR="/var/log/${BOT_NAME}"

# ─── 函数 ───
info()    { echo -e "${GREEN}[✓]${NC} $1"; }
warn()    { echo -e "${YELLOW}[!]${NC} $1"; }
error()   { echo -e "${RED}[✗]${NC} $1"; exit 1; }
step()    { echo -e "\n${CYAN}══════ $1 ══════${NC}"; }

check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        error "请使用 root 权限运行: sudo bash deploy.sh"
    fi
}

# ═══════════════════════════════════════════
#  Step 1: 系统更新 + 依赖安装
# ═══════════════════════════════════════════
install_dependencies() {
    step "1/7 安装系统依赖"

    apt-get update -qq
    apt-get install -y -qq \
        python3 python3-venv python3-pip python3-dev \
        git curl wget unzip \
        build-essential libssl-dev libffi-dev \
        > /dev/null 2>&1

    info "系统依赖已安装"

    # 检查 Python 版本
    PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

    if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]); then
        error "Python >= 3.10 必需，当前: ${PY_VERSION}"
    fi
    info "Python ${PY_VERSION} ✓"
}

# ═══════════════════════════════════════════
#  Step 2: 创建专用用户
# ═══════════════════════════════════════════
create_user() {
    step "2/7 创建运行用户"

    if id "${BOT_USER}" &>/dev/null; then
        info "用户 ${BOT_USER} 已存在"
    else
        useradd -r -m -s /bin/bash "${BOT_USER}"
        info "已创建用户: ${BOT_USER}"
    fi
}

# ═══════════════════════════════════════════
#  Step 3: 部署代码
# ═══════════════════════════════════════════
deploy_code() {
    step "3/7 部署项目代码"

    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

    # 创建目录
    mkdir -p "${BOT_DIR}/src/providers"
    mkdir -p "${BOT_DIR}/data"
    mkdir -p "${LOG_DIR}"

    # 复制代码文件
    cp "${SCRIPT_DIR}/requirements.txt"              "${BOT_DIR}/"
    cp "${SCRIPT_DIR}/src/__init__.py"               "${BOT_DIR}/src/" 2>/dev/null || touch "${BOT_DIR}/src/__init__.py"
    cp "${SCRIPT_DIR}/src/config.py"                 "${BOT_DIR}/src/"
    cp "${SCRIPT_DIR}/src/main.py"                   "${BOT_DIR}/src/"
    cp "${SCRIPT_DIR}/src/store.py"                  "${BOT_DIR}/src/"
    cp "${SCRIPT_DIR}/src/translator.py"             "${BOT_DIR}/src/"
    cp "${SCRIPT_DIR}/src/handlers.py"               "${BOT_DIR}/src/"
    cp "${SCRIPT_DIR}/src/providers/__init__.py"      "${BOT_DIR}/src/providers/"
    cp "${SCRIPT_DIR}/src/providers/base.py"          "${BOT_DIR}/src/providers/"
    cp "${SCRIPT_DIR}/src/providers/openai_compatible.py" "${BOT_DIR}/src/providers/"
    cp "${SCRIPT_DIR}/src/providers/claude.py"        "${BOT_DIR}/src/providers/"
    cp "${SCRIPT_DIR}/src/providers/gemini.py"        "${BOT_DIR}/src/providers/"

    # 复制 .env（如果存在）
    if [ -f "${SCRIPT_DIR}/.env" ]; then
        cp "${SCRIPT_DIR}/.env" "${BOT_DIR}/.env"
        info ".env 配置已复制"
    fi

    # 复制已有数据
    if [ -f "${SCRIPT_DIR}/data/settings.json" ]; then
        cp "${SCRIPT_DIR}/data/settings.json" "${BOT_DIR}/data/"
    fi
    if [ -f "${SCRIPT_DIR}/data/stats.json" ]; then
        cp "${SCRIPT_DIR}/data/stats.json" "${BOT_DIR}/data/"
    fi

    info "代码已部署到 ${BOT_DIR}"
}

# ═══════════════════════════════════════════
#  Step 4: 配置环境变量
# ═══════════════════════════════════════════
configure_env() {
    step "4/7 配置环境变量"

    ENV_FILE="${BOT_DIR}/.env"

    if [ -f "${ENV_FILE}" ] && grep -q "TELEGRAM_BOT_TOKEN=.\+" "${ENV_FILE}"; then
        info ".env 已存在且已配置"
        return
    fi

    echo ""
    echo -e "${BLUE}═══ 请输入配置信息 ═══${NC}"
    echo ""

    # Telegram Token
    read -rp "📱 Telegram Bot Token: " BOT_TOKEN
    if [ -z "${BOT_TOKEN}" ]; then
        error "Bot Token 不能为空"
    fi

    # DeepSeek API Key
    read -rp "🤖 DeepSeek API Key (必填): " DEEPSEEK_KEY
    if [ -z "${DEEPSEEK_KEY}" ]; then
        error "DeepSeek API Key 不能为空"
    fi

    # 可选 API Keys
    read -rp "🔑 OpenAI API Key (可选，回车跳过): " OPENAI_KEY
    read -rp "🔑 Claude API Key (可选，回车跳过): " CLAUDE_KEY
    read -rp "🔑 Gemini API Key (可选，回车跳过): " GEMINI_KEY
    read -rp "🔑 Groq API Key (可选，回车跳过): " GROQ_KEY
    read -rp "🔑 Mistral API Key (可选，回车跳过): " MISTRAL_KEY

    # 管理员 ID
    read -rp "👤 管理员用户 ID (必填): " ADMIN_IDS
    if [ -z "${ADMIN_IDS}" ]; then
        error "管理员 ID 不能为空"
    fi

    # 默认设置
    read -rp "🤖 默认引擎 (默认 deepseek): " DEFAULT_PROVIDER
    DEFAULT_PROVIDER=${DEFAULT_PROVIDER:-deepseek}
    read -rp "🌍 默认语言 (默认 中文): " DEFAULT_LANG
    DEFAULT_LANG=${DEFAULT_LANG:-中文}

    cat > "${ENV_FILE}" << ENVEOF
# ========== Telegram 配置 ==========
TELEGRAM_BOT_TOKEN=${BOT_TOKEN}

# ========== AI 提供商 API Keys（填写你要用的即可）==========
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
ENVEOF

    chmod 600 "${ENV_FILE}"
    info ".env 配置已保存"
}

# ═══════════════════════════════════════════
#  Step 5: Python 虚拟环境 + 依赖
# ═══════════════════════════════════════════
setup_venv() {
    step "5/7 安装 Python 依赖"

    if [ ! -d "${VENV_DIR}" ]; then
        python3 -m venv "${VENV_DIR}"
        info "虚拟环境已创建"
    fi

    "${VENV_DIR}/bin/pip" install --upgrade pip -q
    "${VENV_DIR}/bin/pip" install -r "${BOT_DIR}/requirements.txt" -q

    info "Python 依赖已安装"

    # 验证导入
    cd "${BOT_DIR}"
    "${VENV_DIR}/bin/python" -c "
import src.config
import src.store
import src.translator
import src.providers
import src.handlers
print('✅ 所有模块导入成功')
" || error "模块导入失败"
}

# ═══════════════════════════════════════════
#  Step 6: systemd 服务
# ═══════════════════════════════════════════
setup_systemd() {
    step "6/7 配置 systemd 服务"

    cat > "/etc/systemd/system/${SERVICE_NAME}.service" << SVCEOF
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

# 环境
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
SVCEOF

    info "systemd 服务已创建"
}

# ═══════════════════════════════════════════
#  Step 7: 权限 + 启动
# ═══════════════════════════════════════════
finalize() {
    step "7/7 设置权限并启动"

    # 权限
    chown -R "${BOT_USER}:${BOT_USER}" "${BOT_DIR}"
    chown -R "${BOT_USER}:${BOT_USER}" "${LOG_DIR}"
    chmod 700 "${BOT_DIR}"
    chmod 600 "${BOT_DIR}/.env"

    # 安装管理脚本
    cp "${BOT_DIR}/bot.sh" "/usr/local/bin/bot" 2>/dev/null && chmod +x "/usr/local/bin/bot" || true

    # 重载并启动
    systemctl daemon-reload
    systemctl enable "${SERVICE_NAME}" --now

    sleep 3

    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        info "🎉 机器人已成功启动！"
    else
        warn "启动可能失败，查看日志: journalctl -u ${SERVICE_NAME} -f"
    fi
}

# ═══════════════════════════════════════════
#  打印结果
# ═══════════════════════════════════════════
print_summary() {
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ✅ 部署完成！${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════${NC}"
    echo ""
    echo -e "  📂 安装目录:  ${CYAN}${BOT_DIR}${NC}"
    echo -e "  🐍 虚拟环境:  ${CYAN}${VENV_DIR}${NC}"
    echo -e "  📄 配置文件:  ${CYAN}${BOT_DIR}/.env${NC}"
    echo -e "  📊 数据目录:  ${CYAN}${BOT_DIR}/data${NC}"
    echo -e "  📋 日志目录:  ${CYAN}${LOG_DIR}${NC}"
    echo ""
    echo -e "  ${BLUE}常用命令:${NC}"
    echo -e "  ─────────────────────────────────────"
    echo -e "  查看状态:  ${YELLOW}systemctl status ${SERVICE_NAME}${NC}"
    echo -e "  查看日志:  ${YELLOW}journalctl -u ${SERVICE_NAME} -f${NC}"
    echo -e "  重启服务:  ${YELLOW}systemctl restart ${SERVICE_NAME}${NC}"
    echo -e "  停止服务:  ${YELLOW}systemctl stop ${SERVICE_NAME}${NC}"
    echo -e "  启动服务:  ${YELLOW}systemctl start ${SERVICE_NAME}${NC}"
    echo ""
    echo -e "  ${BLUE}快捷管理 (如已安装 bot.sh):${NC}"
    echo -e "  ─────────────────────────────────────"
    echo -e "  ${YELLOW}bot status${NC}  — 查看状态"
    echo -e "  ${YELLOW}bot log${NC}     — 实时日志"
    echo -e "  ${YELLOW}bot restart${NC} — 重启"
    echo -e "  ${YELLOW}bot update${NC}  — 更新代码"
    echo ""
}

# ═══════════════════════════════════════════
#  主流程
# ═══════════════════════════════════════════
main() {
    echo ""
    echo -e "${CYAN}╔═══════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║   🌐 AI 翻译机器人 — Debian 一键部署      ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════╝${NC}"
    echo ""

    check_root
    install_dependencies
    create_user
    deploy_code
    configure_env
    setup_venv
    setup_systemd
    finalize
    print_summary
}

main "$@"
