#!/bin/bash
# One Aider run with Muse, inside the same kind of sandbox as the bots: --yes-always would run suggested commands, so nothing of ours may be readable.
C=$PWD/clean/aider1
exec bwrap --ro-bind / / --dev /dev --proc /proc --tmpfs /tmp --tmpfs $HOME --tmpfs /root \
 --ro-bind $HOME/.local/share/uv $HOME/.local/share/uv --ro-bind $PWD/bin_curl $HOME/hbin/curl --bind "$C" $HOME/work --chdir $HOME/work --unshare-pid --unshare-ipc --die-with-parent \
 --clearenv --setenv HOME $HOME/work/.home --setenv PATH $HOME/hbin:/usr/local/bin:/usr/bin:/bin --setenv TERM dumb --setenv LANG C.UTF-8 \
 --setenv OPENAI_API_BASE http://127.0.0.1:8912/b/aider-muse-01/D2/meta/v1 --setenv OPENAI_API_KEY held-by-proxy \
 timeout 600 $HOME/.local/share/uv/tools/aider-chat/bin/aider --no-git --yes-always --no-check-update --no-show-model-warnings --no-analytics --no-gitignore --model openai/muse-spark-1.3-contributor --no-stream --message-file prompt.txt
