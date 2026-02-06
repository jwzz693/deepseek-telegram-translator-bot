#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
#  AI 翻译机器人 — 一键远程升级脚本
#
#  从 GitHub 拉取最新代码、更新依赖、重启服务，全程零交互。
#  自动检测已有部署，保留 .env 配置和 data/ 数据。
#
#  已部署用户升级:
#    curl -sL https://raw.githubusercontent.com/jwzz693/deepseek-telegram-translator-bot/main/upgrade.sh | sudo bash
#
#  本地执行:
#    sudo bash upgrade.sh
#
#  支持: Debian 10+, Ubuntu 20.04+
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

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
step()  { echo -e "\n${CYAN}[$1/$TOTAL_STEPS]${NC} ${BOLD}$2${NC}"; }
line()  { echo -e "${BLUE}─────────────────────────────────────────────${NC}"; }

TOTAL_STEPS=6

# ═══════════════════════════════════════════
#  Banner
# ═══════════════════════════════════════════
banner() {
    echo ""
    echo -e "${CYAN}╔═════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                                                 ║${NC}"
    echo -e "${CYAN}║   🌐  AI 翻译机器人 — 一键升级                  ║${NC}"
    echo -e "${CYAN}║                                                 ║${NC}"
    echo -e "${CYAN}║   自动拉取 · 更新依赖 · 重启服务                ║${NC}"
    echo -e "${CYAN}║   保留配置 · 保留数据 · 零停机                  ║${NC}"
    echo -e "${CYAN}╚═════════════════════════════════════════════════╝${NC}"
    echo ""
}

# ═══════════════════════════════════════════
#  Step 1: 环境检查
# ═══════════════════════════════════════════
preflight_check() {
    step 1 "环境检查"

    # Root 检查
    if [ "$(id -u)" -ne 0 ]; then
        fail "请使用 root 权限运行:\n    curl -sL ... | sudo bash\n    或 sudo bash upgrade.sh"
    fi
    info "root 权限 ✓"

    # 系统检查
    if [ ! -f /etc/debian_version ] && [ ! -f /etc/lsb-release ]; then
        fail "仅支持 Debian / Ubuntu 系统"
    fi
    OS_NAME=$(. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME" || echo "Debian/Ubuntu")
    info "系统: ${OS_NAME}"

    # 检查是否已部署
    if [ ! -d "${BOT_DIR}" ]; then
        echo ""
        warn "未检测到已有部署 (${BOT_DIR} 不存在)"
        echo -e "  ${YELLOW}首次安装请使用:${NC}"
        echo -e "  ${GREEN}curl -sL https://raw.githubusercontent.com/jwzz693/deepseek-telegram-translator-bot/main/install.sh | sudo bash${NC}"
        echo ""
        fail "升级脚本仅适用于已部署的机器人"
    fi
    info "已有部署: ${BOT_DIR}"

    # 检查 .env
    if [ ! -f "${BOT_DIR}/.env" ]; then
        fail ".env 配置文件不存在，请先完成初始部署"
    fi
    info ".env 配置存在 ✓"

    # 读取旧版本号
    OLD_VERSION="未知"
    if [ -f "${BOT_DIR}/src/config.py" ]; then
        OLD_VERSION=$(grep -oP 'VERSION\s*=\s*"\K[^"]+' "${BOT_DIR}/src/config.py" 2>/dev/null || echo "未知")
    fi
    info "当前版本: v${OLD_VERSION}"

    # 检查 git
    if ! command -v git &>/dev/null; then
        warn "git 未安装，正在安装..."
        apt-get update -qq > /dev/null 2>&1
        apt-get install -y -qq git > /dev/null 2>&1
    fi
    info "git $(git --version | awk '{print $3}') ✓"
}

# ═══════════════════════════════════════════
#  Step 2: 备份当前部署
# ═══════════════════════════════════════════
backup_current() {
    step 2 "备份当前部署"

    BACKUP_DIR="/tmp/${BOT_NAME}-upgrade-$(date +%Y%m%d_%H%M%S)"
    mkdir -p "${BACKUP_DIR}"

    # 备份 .env
    cp "${BOT_DIR}/.env" "${BACKUP_DIR}/.env"
    info "已备份 .env"

    # 备份 data/
    if [ -d "${BOT_DIR}/data" ]; then
        cp -r "${BOT_DIR}/data" "${BACKUP_DIR}/data"
        info "已备份 data/"
    fi

    # 备份 venv 信息（仅记录包列表）
    if [ -f "${VENV_DIR}/bin/pip" ]; then
        "${VENV_DIR}/bin/pip" freeze > "${BACKUP_DIR}/requirements-old.txt" 2>/dev/null || true
        info "已记录旧依赖列表"
    fi

    info "备份目录: ${BACKUP_DIR}"
}

# ═══════════════════════════════════════════
#  Step 3: 停止服务
# ═══════════════════════════════════════════
stop_service() {
    step 3 "停止服务"

    if systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null; then
        systemctl stop "${SERVICE_NAME}"
        # 等待完全停止
        for i in $(seq 1 10); do
            if ! systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null; then
                break
            fi
            sleep 1
        done
        info "服务已停止"
    else
        info "服务未运行，跳过"
    fi
}

# ═══════════════════════════════════════════
#  Step 4: 拉取最新代码
# ═══════════════════════════════════════════
pull_code() {
    step 4 "拉取最新代码"

    cd "${BOT_DIR}"

    if [ -d "${BOT_DIR}/.git" ]; then
        # 已有 git 仓库 → 直接 pull
        echo -e "  ${BLUE}从 ${REPO_URL} 拉取...${NC}"

        # 保存本地修改
        git stash --include-untracked 2>/dev/null || true

        # 确保 remote 正确
        CURRENT_REMOTE=$(git remote get-url origin 2>/dev/null || echo "")
        if [ "${CURRENT_REMOTE}" != "${REPO_URL}" ]; then
            git remote set-url origin "${REPO_URL}" 2>/dev/null || git remote add origin "${REPO_URL}" 2>/dev/null
            info "远程仓库已更新为 ${REPO_URL}"
        fi

        # 拉取
        git fetch origin "${REPO_BRANCH}" --force
        git reset --hard "origin/${REPO_BRANCH}"
        info "代码已更新 (git pull)"

        # 尝试恢复本地修改（冲突时丢弃）
        git stash pop 2>/dev/null || true
    else
        # 非 git 目录 → 重新克隆
        warn "非 git 仓库，将重新克隆"

        # 临时移走
        TEMP_OLD="${BOT_DIR}.old.$$"
        mv "${BOT_DIR}" "${TEMP_OLD}"

        git clone --depth 1 -b "${REPO_BRANCH}" "${REPO_URL}" "${BOT_DIR}"
        info "代码已克隆"

        # 删除临时目录（.env 和 data 已在 Step 2 备份）
        rm -rf "${TEMP_OLD}"
    fi

    # 恢复 .env 和 data（从备份）
    if [ ! -f "${BOT_DIR}/.env" ] && [ -f "${BACKUP_DIR}/.env" ]; then
        cp "${BACKUP_DIR}/.env" "${BOT_DIR}/.env"
        info "已恢复 .env"
    fi
    if [ ! -d "${BOT_DIR}/data" ] && [ -d "${BACKUP_DIR}/data" ]; then
        cp -r "${BACKUP_DIR}/data" "${BOT_DIR}/data"
        info "已恢复 data/"
    fi

    # 确保 data 目录存在
    mkdir -p "${BOT_DIR}/data"

    # 检查新 .env 字段（自动补全缺失项）
    merge_env_fields

    # 读取新版本号
    NEW_VERSION="未知"
    if [ -f "${BOT_DIR}/src/config.py" ]; then
        NEW_VERSION=$(grep -oP 'VERSION\s*=\s*"\K[^"]+' "${BOT_DIR}/src/config.py" 2>/dev/null || echo "未知")
    fi
    info "新版本: v${NEW_VERSION}"
}

# ─── 自动合并 .env 新字段 ───
merge_env_fields() {
    ENV_FILE="${BOT_DIR}/.env"
    [ ! -f "${ENV_FILE}" ] && return

    CHANGED=0

    # MAX_TEXT_LENGTH
    if ! grep -q "^MAX_TEXT_LENGTH=" "${ENV_FILE}" 2>/dev/null; then
        echo "" >> "${ENV_FILE}"
        echo "# ========== 限制设置 ==========" >> "${ENV_FILE}"
        echo "MAX_TEXT_LENGTH=5000" >> "${ENV_FILE}"
        CHANGED=1
    fi

    # RATE_LIMIT_PER_MIN
    if ! grep -q "^RATE_LIMIT_PER_MIN=" "${ENV_FILE}" 2>/dev/null; then
        echo "RATE_LIMIT_PER_MIN=30" >> "${ENV_FILE}"
        CHANGED=1
    fi

    if [ "$CHANGED" -eq 1 ]; then
        info "已自动补全 .env 新字段 (MAX_TEXT_LENGTH, RATE_LIMIT_PER_MIN)"
    fi
}

# ═══════════════════════════════════════════
#  Step 5: 更新 Python 依赖
# ═══════════════════════════════════════════
update_deps() {
    step 5 "更新 Python 依赖"

    cd "${BOT_DIR}"

    # 如果虚拟环境不存在，创建
    if [ ! -d "${VENV_DIR}" ]; then
        warn "虚拟环境不存在，正在创建..."
        python3 -m venv "${VENV_DIR}"
        info "虚拟环境已创建"
    fi

    # 升级 pip
    "${VENV_DIR}/bin/pip" install --upgrade pip -q 2>/dev/null
    info "pip 已升级"

    # 安装/更新依赖
    "${VENV_DIR}/bin/pip" install -r requirements.txt --upgrade -q 2>/dev/null
    info "依赖已更新"

    # 验证模块
    "${VENV_DIR}/bin/python" -c "
import src.config
import src.store
import src.translator
import src.providers
import src.handlers
print('  ✓ 所有模块验证通过')
" || fail "模块导入失败！请检查代码兼容性\n  备份目录: ${BACKUP_DIR}"
}

# ═══════════════════════════════════════════
#  Step 6: 重启服务
# ═══════════════════════════════════════════
restart_service() {
    step 6 "重启服务"

    # 更新 bot.sh 管理脚本
    if [ -f "${BOT_DIR}/bot.sh" ]; then
        cp "${BOT_DIR}/bot.sh" /usr/local/bin/bot
        chmod +x /usr/local/bin/bot
        info "管理命令 'bot' 已更新"
    fi

    # 设置权限
    chown -R "${BOT_USER}:${BOT_USER}" "${BOT_DIR}"
    chown -R "${BOT_USER}:${BOT_USER}" "${LOG_DIR}" 2>/dev/null || true
    chmod 700 "${BOT_DIR}"
    chmod 600 "${BOT_DIR}/.env"
    info "权限已设置"

    # 重载 systemd（如果 service 文件有更新）
    if [ -f "${BOT_DIR}/install.sh" ] || [ -f "${BOT_DIR}/deploy.sh" ]; then
        # 重新生成 service 文件以获取最新配置
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

EnvironmentFile=${BOT_DIR}/.env

StandardOutput=journal
StandardError=journal
SyslogIdentifier=${BOT_NAME}

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
        info "systemd 服务文件已更新"
    fi

    systemctl daemon-reload
    systemctl start "${SERVICE_NAME}"

    # 等待启动
    echo -ne "  等待启动"
    for i in $(seq 1 8); do
        sleep 1
        echo -ne "."
        if systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null; then
            break
        fi
    done
    echo ""

    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        info "服务已启动 🎉"
    else
        echo -e "  ${RED}❌ 启动失败${NC}"
        echo ""
        journalctl -u "${SERVICE_NAME}" -n 30 --no-pager
        echo ""
        warn "备份目录: ${BACKUP_DIR}"
        echo -e "  ${YELLOW}恢复方法: cp ${BACKUP_DIR}/.env ${BOT_DIR}/.env && cp -r ${BACKUP_DIR}/data ${BOT_DIR}/data${NC}"
        fail "请根据上方日志排查问题"
    fi
}

# ═══════════════════════════════════════════
#  打印结果
# ═══════════════════════════════════════════
print_result() {
    echo ""
    echo -e "${GREEN}╔═════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║          ✅  升级完成！机器人已重启运行          ║${NC}"
    echo -e "${GREEN}╚═════════════════════════════════════════════════╝${NC}"
    echo ""

    # 版本对比
    if [ "${OLD_VERSION}" != "${NEW_VERSION}" ]; then
        echo -e "  ${BOLD}📦 版本${NC}    ${RED}v${OLD_VERSION}${NC} → ${GREEN}v${NEW_VERSION}${NC}"
    else
        echo -e "  ${BOLD}📦 版本${NC}    ${GREEN}v${NEW_VERSION}${NC} (最新)"
    fi

    echo -e "  ${BOLD}📂 目录${NC}    ${BOT_DIR}"
    echo -e "  ${BOLD}💾 备份${NC}    ${BACKUP_DIR}"
    echo ""
    line
    echo -e "  ${BOLD}验证:${NC}"
    line
    echo -e "  ${YELLOW}bot status${NC}       查看状态"
    echo -e "  ${YELLOW}bot version${NC}      查看版本"
    echo -e "  ${YELLOW}bot log${NC}          实时日志"
    echo -e "  ${YELLOW}bot health${NC}       健康检查"
    echo ""

    # 变更摘要
    if [ -f "${BACKUP_DIR}/requirements-old.txt" ]; then
        NEW_DEPS=$("${VENV_DIR}/bin/pip" freeze 2>/dev/null | wc -l)
        OLD_DEPS=$(wc -l < "${BACKUP_DIR}/requirements-old.txt" 2>/dev/null || echo 0)
        if [ "${NEW_DEPS}" != "${OLD_DEPS}" ]; then
            echo -e "  ${BLUE}依赖变化: ${OLD_DEPS} → ${NEW_DEPS} 个包${NC}"
        fi
    fi

    # 如果代码有 git，显示最新 commit
    if [ -d "${BOT_DIR}/.git" ]; then
        COMMIT=$(cd "${BOT_DIR}" && git log -1 --format="%h %s" 2>/dev/null || echo "")
        if [ -n "${COMMIT}" ]; then
            echo -e "  ${BLUE}最新提交: ${COMMIT}${NC}"
        fi
    fi
    echo ""
}

# ═══════════════════════════════════════════
#  主流程
# ═══════════════════════════════════════════
main() {
    banner
    preflight_check
    backup_current
    stop_service
    pull_code
    update_deps
    restart_service
    print_result
}

main "$@"
