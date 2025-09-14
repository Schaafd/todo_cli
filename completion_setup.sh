#!/bin/bash

# Shell completion setup for Productivity Ninja CLI
# 
# Usage:
#   source completion_setup.sh
#   
# Or add to your shell profile:
#   echo "source /path/to/completion_setup.sh" >> ~/.zshrc

echo "Setting up shell completion for Productivity Ninja CLI..."

# Detect shell
if [ -n "$ZSH_VERSION" ]; then
    # Zsh completion
    echo "Detected Zsh shell"
    eval "$(_TODO_COMPLETE=zsh_source todo)"
    echo "✅ Zsh completion enabled for 'todo' command"
elif [ -n "$BASH_VERSION" ]; then
    # Bash completion
    echo "Detected Bash shell"
    eval "$(_TODO_COMPLETE=bash_source todo)"
    echo "✅ Bash completion enabled for 'todo' command"
else
    echo "⚠️  Shell not detected. Supported shells: Zsh, Bash"
    echo "To manually enable completion:"
    echo "  Zsh: eval \"\$(_TODO_COMPLETE=zsh_source todo)\""
    echo "  Bash: eval \"\$(_TODO_COMPLETE=bash_source todo)\""
fi

echo ""
echo "🎉 Shell completion is now active!"
echo "Try typing 'todo <TAB>' to see available commands"
echo ""
echo "To make this permanent, add this line to your shell profile:"
if [ -n "$ZSH_VERSION" ]; then
    echo "  echo 'eval \"\$(_TODO_COMPLETE=zsh_source todo)\"' >> ~/.zshrc"
elif [ -n "$BASH_VERSION" ]; then
    echo "  echo 'eval \"\$(_TODO_COMPLETE=bash_source todo)\"' >> ~/.bashrc"
fi