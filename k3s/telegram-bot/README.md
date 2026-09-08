# Telegram bot on k3s

Runs `todo telegram serve` as a k3s Deployment on the mac mini instead of a
launchd service — see `launchd/` for the alternative if you'd rather not
involve the cluster for this.

## One-time setup (on the mac mini)

1. Check the hostPath assumption in `deployment.yaml` actually holds: k3s's
   VM needs to pass `/Users` through to the node. Rancher Desktop and Colima
   (with `--mount`) do this by default — if not, switch the volume to a PVC
   (`local-path` storage class) instead; that gives the bot its own db,
   separate from the terminal one.
2. Fix ownership so the pod (uid 1000) can write the db one of two ways:
   - `kubectl mini`'s `id -u` differs from 1000: edit `runAsUser` in
     `deployment.yaml` to match your Mac user's `id -u`, or
   - open the directory up: `chmod -R o+rwX ~/.local/share/todo`
3. `cp secret.yaml.template secret.yaml`, fill in the real token/id/keys
   (pull from the `agents` 1Password vault: `op read op://agents/<item>/<field>`),
   `kubectl apply -f secret.yaml`. `secret.yaml` is gitignored — never commit it.
4. `./build-and-deploy.sh`

## Redeploying after a code change

```bash
./build-and-deploy.sh
```

## Logs

```bash
kubectl logs -n todo-bot -l app=todo-telegram-bot -f
```
