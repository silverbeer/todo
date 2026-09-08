#!/bin/bash
# Build the telegram bot image and (re)deploy it to k3s on this machine.
# Mirrors missing-table's k3s/worker/rebuild-and-deploy.sh: local build,
# imported straight into the node's containerd (no registry).
#
# Run this ON the k3s node (the mac mini) — `docker build` here has to be the
# same Docker/Rancher Desktop instance the node's containerd reads from.
#
# Usage:
#   ./build-and-deploy.sh              # build, import, apply, restart
#   ./build-and-deploy.sh --build-only

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
IMAGE_NAME="todo-telegram-bot:local"
NAMESPACE="todo-bot"
# Set to your k3s context if kubectl needs an explicit one, e.g. "rancher-desktop".
KUBE_CONTEXT="${KUBE_CONTEXT:-}"

kctl() {
    if [ -n "$KUBE_CONTEXT" ]; then
        kubectl --context "$KUBE_CONTEXT" "$@"
    else
        kubectl "$@"
    fi
}

echo "Building $IMAGE_NAME..."
docker build -t "$IMAGE_NAME" "$REPO_ROOT"

if [ "${1:-}" = "--build-only" ]; then
    echo "Built $IMAGE_NAME (not imported/deployed)."
    exit 0
fi

echo "Importing into k3s containerd..."
docker save "$IMAGE_NAME" | nerdctl --namespace k8s.io load

echo "Applying manifests..."
kctl apply -f "$SCRIPT_DIR/namespace.yaml"
if [ -f "$SCRIPT_DIR/secret.yaml" ]; then
    kctl apply -f "$SCRIPT_DIR/secret.yaml"
else
    echo "WARNING: $SCRIPT_DIR/secret.yaml not found — copy secret.yaml.template, fill it in, apply it first." >&2
fi
kctl apply -f "$SCRIPT_DIR/deployment.yaml"

if kctl get deployment -n "$NAMESPACE" todo-telegram-bot &>/dev/null; then
    echo "Restarting deployment..."
    kctl rollout restart deployment -n "$NAMESPACE" todo-telegram-bot
    kctl rollout status deployment -n "$NAMESPACE" todo-telegram-bot
fi
