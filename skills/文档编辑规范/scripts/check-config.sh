#!/bin/bash
# 配置变更检查脚本
# 用法: ./check-config.sh

set -e

echo "🔍 检查配置文件变更..."

# 检查git diff
CHANGED_CONFIGS=$(git diff --name-only 2>/dev/null | grep -E "application.*\.yml|bootstrap.*\.yml|pom\.xml" || true)

if [ -n "$CHANGED_CONFIGS" ]; then
    echo ""
    echo "⚠️  检测到配置文件变更:"
    echo "$CHANGED_CONFIGS" | sed 's/^/   📄 /'
    echo ""
    echo "📝 请确保已更新 CHANGELOG_CONFIG.md"
    echo ""
    echo "💡 提示:"
    echo "   1. 记录配置项的变更"
    echo "   2. 说明变更原因"
    echo "   3. 提供配置示例"
    echo "   4. 标注影响范围"
    echo ""
    
    # 检查是否有CHANGELOG_CONFIG.md
    if [ ! -f "CHANGELOG_CONFIG.md" ]; then
        echo "❌ 未找到 CHANGELOG_CONFIG.md"
        echo "   请从模板创建: cp skills/文档编辑规范/templates/CHANGELOG_CONFIG.md ."
        exit 1
    fi
    
    # 检查CHANGELOG是否有今天的更新
    TODAY=$(date +%Y-%m-%d)
    if ! grep -q "$TODAY" CHANGELOG_CONFIG.md; then
        echo "⚠️  CHANGELOG_CONFIG.md 中没有今天的更新记录"
        echo "   请添加今天的变更记录"
        exit 1
    fi
    
    echo "✅ CHANGELOG_CONFIG.md 已更新"
else
    echo "✅ 没有配置文件变更"
fi

echo ""
echo "🔍 检查敏感配置..."

# 检查是否有敏感配置硬编码
SENSITIVE_PATTERNS="password|secret|key|token"
SENSITIVE_FILES=$(git diff --name-only 2>/dev/null | grep -E "\.yml$|\.properties$" || true)

if [ -n "$SENSITIVE_FILES" ]; then
    for file in $SENSITIVE_FILES; do
        if git diff "$file" | grep -iE "$SENSITIVE_PATTERNS" | grep -v "\${" | grep -v "CHANGE" > /dev/null 2>&1; then
            echo "⚠️  检测到可能的敏感配置硬编码: $file"
            echo "   请使用环境变量: \${ENV_VAR:default-value}"
        fi
    done
fi

echo "✅ 配置检查完成"
