#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  AI 翻译机器人 v2.1 — 快捷管理脚本
#  用法: bot <命令>
#  安装后可用: bot status / bot log / bot restart 等
# ═══════════════════════════════════════════════════════════════

SERVICE="telegram-translator-bot"
BOT_DIR="/opt/${SERVICE}"
VENV="${BOT_DIR}/venv"
REPO_URL="https://github.com/jwzz693/deepseek-telegram-translator-bot.git"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

case "$1" in

    # ─── 版本 ───
    version|ver|-v|--version)
        echo -e "${CYAN}═══ AI 翻译机器人 ═══${NC}"
        if [ -f "${BOT_DIR}/src/config.py" ]; then
            VER=$(grep -oP 'VERSION\s*=\s*"\K[^"]+' "${BOT_DIR}/src/config.py" 2>/dev/null || echo "未知")
            echo -e "  版本: ${GREEN}v${VER}${NC}"
        fi
        PY_VER=$("${VENV}/bin/python" --version 2>&1 || echo "未安装")
        echo -e "  Python: ${GREEN}${PY_VER}${NC}"
        if systemctl is-active --quiet "${SERVICE}"; then
            echo -e "  状态: ${GREEN}运行中${NC}"
            UPTIME=$(systemctl show -p ActiveEnterTimestamp "${SERVICE}" --value 2>/dev/null)
            [ -n "$UPTIME" ] && echo -e "  启动: ${CYAN}${UPTIME}${NC}"
        else
            echo -e "  状态: ${RED}已停止${NC}"
        fi
        ;;

    # ─── 状态 ───
    status)
        echo -e "${CYAN}═══ 机器人状态 ═══${NC}"
        systemctl status "${SERVICE}" --no-pager
        echo ""
        echo -e "${CYAN}═══ 最近日志 ═══${NC}"
        journalctl -u "${SERVICE}" -n 15 --no-pager
        ;;

    # ─── 启动 ───
    start)
        echo -e "${GREEN}▶ 启动机器人...${NC}"
        systemctl start "${SERVICE}"
        sleep 2
        systemctl status "${SERVICE}" --no-pager -l
        ;;

    # ─── 停止 ───
    stop)
        echo -e "${YELLOW}⏹ 停止机器人...${NC}"
        systemctl stop "${SERVICE}"
        echo -e "${GREEN}已停止${NC}"
        ;;

    # ─── 重启 ───
    restart)
        echo -e "${YELLOW}🔄 重启机器人...${NC}"
        systemctl restart "${SERVICE}"
        sleep 2
        if systemctl is-active --quiet "${SERVICE}"; then
            echo -e "${GREEN}✅ 重启成功${NC}"
        else
            echo -e "${RED}❌ 重启失败${NC}"
            journalctl -u "${SERVICE}" -n 20 --no-pager
        fi
        ;;

    # ─── 实时日志 ───
    log|logs)
        echo -e "${CYAN}═══ 实时日志 (Ctrl+C 退出) ═══${NC}"
        journalctl -u "${SERVICE}" -f
        ;;

    # ─── 历史日志 ───
    log-all)
        journalctl -u "${SERVICE}" --no-pager | less
        ;;

    # ─── 编辑配置 ───
    config|edit)
        if command -v nano &>/dev/null; then
            nano "${BOT_DIR}/.env"
        else
            vi "${BOT_DIR}/.env"
        fi
        echo -e "${YELLOW}配置已修改，是否重启？(y/N)${NC}"
        read -rn1 ans
        echo
        if [[ "$ans" =~ ^[Yy]$ ]]; then
            systemctl restart "${SERVICE}"
            echo -e "${GREEN}✅ 已重启${NC}"
        fi
        ;;

    # ─── 更新代码 ───
    update)
        echo -e "${CYAN}═══ 更新代码 ═══${NC}"

        # 如果有 git
        if [ -d "${BOT_DIR}/.git" ]; then
            cd "${BOT_DIR}"
            echo -e "${YELLOW}从 GitHub 拉取最新代码...${NC}"
            git stash --include-untracked 2>/dev/null || true
            git pull origin main --force
            git stash pop 2>/dev/null || true
            echo -e "${GREEN}✓ 代码已更新${NC}"
        else
            echo -e "${YELLOW}非 git 仓库，尝试重新克隆...${NC}"
            # 备份 .env 和 data
            [ -f "${BOT_DIR}/.env" ] && cp "${BOT_DIR}/.env" /tmp/.env.bak
            [ -d "${BOT_DIR}/data" ] && cp -r "${BOT_DIR}/data" /tmp/data.bak
            rm -rf "${BOT_DIR}"
            git clone --depth 1 "${REPO_URL}" "${BOT_DIR}"
            [ -f /tmp/.env.bak ] && mv /tmp/.env.bak "${BOT_DIR}/.env"
            [ -d /tmp/data.bak ] && rm -rf "${BOT_DIR}/data" && mv /tmp/data.bak "${BOT_DIR}/data"
            echo -e "${GREEN}✓ 代码已重新克隆${NC}"
        fi

        # 更新依赖
        "${VENV}/bin/pip" install -r "${BOT_DIR}/requirements.txt" -q
        echo -e "${GREEN}✓ 依赖已更新${NC}"

        # 重启
        systemctl restart "${SERVICE}"
        sleep 2
        if systemctl is-active --quiet "${SERVICE}"; then
            echo -e "${GREEN}✅ 更新完成并已重启${NC}"
        else
            echo -e "${RED}❌ 重启失败，查看日志${NC}"
            journalctl -u "${SERVICE}" -n 20 --no-pager
        fi
        ;;

    # ─── 更新依赖 ───
    deps)
        echo -e "${CYAN}═══ 更新 Python 依赖 ═══${NC}"
        "${VENV}/bin/pip" install --upgrade pip
        "${VENV}/bin/pip" install -r "${BOT_DIR}/requirements.txt" --upgrade
        echo -e "${GREEN}✅ 依赖已更新${NC}"
        ;;

    # ─── 检查健康 ───
    health|check)
        echo -e "${CYAN}═══ 健康检查 ═══${NC}"
        echo ""

        # 服务状态
        if systemctl is-active --quiet "${SERVICE}"; then
            echo -e "  服务状态:  ${GREEN}✅ 运行中${NC}"
        else
            echo -e "  服务状态:  ${RED}❌ 未运行${NC}"
        fi

        # Python
        PY_VER=$("${VENV}/bin/python" --version 2>&1)
        echo -e "  Python:    ${GREEN}${PY_VER}${NC}"

        # .env
        if [ -f "${BOT_DIR}/.env" ]; then
            echo -e "  配置文件:  ${GREEN}✅ 存在${NC}"
        else
            echo -e "  配置文件:  ${RED}❌ 缺失${NC}"
        fi

        # data 目录
        if [ -d "${BOT_DIR}/data" ]; then
            SETTINGS_SIZE=$(stat -c%s "${BOT_DIR}/data/settings.json" 2>/dev/null || echo 0)
            STATS_SIZE=$(stat -c%s "${BOT_DIR}/data/stats.json" 2>/dev/null || echo 0)
            echo -e "  数据:      ${GREEN}settings=${SETTINGS_SIZE}B stats=${STATS_SIZE}B${NC}"
        else
            echo -e "  数据目录:  ${RED}❌ 缺失${NC}"
        fi

        # 模块检查
        cd "${BOT_DIR}"
        if "${VENV}/bin/python" -c "import src.config; import src.handlers" 2>/dev/null; then
            echo -e "  模块导入:  ${GREEN}✅ 正常${NC}"
        else
            echo -e "  模块导入:  ${RED}❌ 失败${NC}"
        fi

        # 磁盘
        DISK_USE=$(du -sh "${BOT_DIR}" 2>/dev/null | cut -f1)
        echo -e "  磁盘占用:  ${CYAN}${DISK_USE}${NC}"

        # 内存
        PID=$(systemctl show -p MainPID "${SERVICE}" --value 2>/dev/null)
        if [ -n "$PID" ] && [ "$PID" != "0" ]; then
            MEM=$(ps -o rss= -p "$PID" 2>/dev/null | awk '{printf "%.1fMB", $1/1024}')
            echo -e "  内存占用:  ${CYAN}${MEM}${NC}"
        fi

        # 运行时长
        UPTIME=$(systemctl show -p ActiveEnterTimestamp "${SERVICE}" --value 2>/dev/null)
        if [ -n "$UPTIME" ]; then
            echo -e "  启动时间:  ${CYAN}${UPTIME}${NC}"
        fi
        echo ""
        ;;

    # ─── 备份 ───
    backup)
        BACKUP_FILE="/tmp/${SERVICE}-backup-$(date +%Y%m%d_%H%M%S).tar.gz"
        tar -czf "${BACKUP_FILE}" \
            -C "$(dirname ${BOT_DIR})" \
            "$(basename ${BOT_DIR})/.env" \
            "$(basename ${BOT_DIR})/data" \
            2>/dev/null
        echo -e "${GREEN}✅ 备份已保存: ${BACKUP_FILE}${NC}"
        ;;

    # ─── 恢复 ───
    restore)
        if [ -z "$2" ]; then
            echo -e "${RED}用法: bot restore <备份文件.tar.gz>${NC}"
            exit 1
        fi
        systemctl stop "${SERVICE}"
        tar -xzf "$2" -C "$(dirname ${BOT_DIR})"
        chown -R botuser:botuser "${BOT_DIR}"
        systemctl start "${SERVICE}"
        echo -e "${GREEN}✅ 已恢复并重启${NC}"
        ;;

    # ─── 卸载 ───
    uninstall)
        echo -e "${RED}⚠️  即将完全卸载机器人！${NC}"
        echo -e "包括: 服务、代码、虚拟环境"
        echo -e "${YELLOW}数据文件将保留在 /tmp/ 下${NC}"
        echo ""
        read -rp "确认卸载? (输入 YES): " confirm
        if [ "$confirm" != "YES" ]; then
            echo "已取消"
            exit 0
        fi

        # 备份数据
        if [ -d "${BOT_DIR}/data" ]; then
            BACKUP="/tmp/${SERVICE}-data-$(date +%Y%m%d).tar.gz"
            tar -czf "${BACKUP}" -C "${BOT_DIR}" data .env 2>/dev/null
            echo -e "${GREEN}数据已备份到: ${BACKUP}${NC}"
        fi

        systemctl stop "${SERVICE}" 2>/dev/null
        systemctl disable "${SERVICE}" 2>/dev/null
        rm -f "/etc/systemd/system/${SERVICE}.service"
        systemctl daemon-reload
        rm -rf "${BOT_DIR}"
        rm -rf "/var/log/${SERVICE}"
        rm -f "/usr/local/bin/bot"
        echo -e "${GREEN}✅ 卸载完成${NC}"
        ;;

    # ─── 帮助 ───
    *)
        echo -e "${CYAN}╔═══════════════════════════════════════════╗${NC}"
        echo -e "${CYAN}║   🌐 AI 翻译机器人 v2.1 — 管理命令        ║${NC}"
        echo -e "${CYAN}╚═══════════════════════════════════════════╝${NC}"
        echo ""
        echo -e "  ${GREEN}bot version${NC}      — 查看版本信息"
        echo -e "  ${GREEN}bot status${NC}       — 查看运行状态"
        echo -e "  ${GREEN}bot start${NC}        — 启动机器人"
        echo -e "  ${GREEN}bot stop${NC}         — 停止机器人"
        echo -e "  ${GREEN}bot restart${NC}      — 重启机器人"
        echo -e "  ${GREEN}bot log${NC}          — 实时日志"
        echo -e "  ${GREEN}bot log-all${NC}      — 全部日志"
        echo -e "  ${GREEN}bot config${NC}       — 编辑配置"
        echo -e "  ${GREEN}bot update${NC}       — 从仓库更新+重启"
        echo -e "  ${GREEN}bot deps${NC}         — 更新依赖"
        echo -e "  ${GREEN}bot health${NC}       — 健康检查"
        echo -e "  ${GREEN}bot backup${NC}       — 备份数据"
        echo -e "  ${GREEN}bot restore${NC} FILE — 恢复备份"
        echo -e "  ${GREEN}bot uninstall${NC}    — 完全卸载"
        echo ""
        ;;
esac
