#!/bin/bash
# sandbox.sh <clean-folder> <command...>: a stranger's clean machine, near enough. Home is empty, env is scrubbed, nothing of ours is readable.
# The network stays on, so the bot reaches the public queue and the local recording proxy.
C="$1"; shift
exec bwrap --ro-bind / / --dev /dev --proc /proc --tmpfs /tmp --tmpfs $HOME --tmpfs /root \
  --ro-bind $HOME/.local/lib/node_modules/@opencode $HOME/oc --ro-bind $HOME/.codex/packages/standalone/releases/0.166.0-x86_64-unknown-linux-musl/bin/codex $HOME/hbin/codex --ro-bind $TELEION_NOTES/work-2026-11-03/agent-prompt/swarm/bin_curl $HOME/hbin/curl --bind "$C" $HOME/work --chdir $HOME/work --unshare-pid --unshare-ipc --die-with-parent \
  --clearenv --setenv HOME $HOME/work/.home --setenv PATH $HOME/hbin:$HOME/oc/cli/bin:/usr/local/bin:/usr/bin:/bin --setenv TERM dumb --setenv LANG C.UTF-8 "$@"
