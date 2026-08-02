# Protected documentation deployment

The documentation workflow encrypts the generated MkDocs HTML before GitHub
Pages uploads it. This affects only this repository's project site at
`https://autonlab.org/spectroscopy-tetracorder/`; it does not alter the
organization site or any sibling Pages project.

## Required repository secret

Before merging the workflow change, add a repository Actions secret named
`STATICRYPT_PASSWORD`:

1. Open **Settings → Secrets and variables → Actions** in this repository.
2. Select **New repository secret**.
3. Enter `STATICRYPT_PASSWORD` as the name.
4. Enter the shared passphrase. Any non-empty length is accepted. Shorter
   passphrases are easier to guess, which is suitable only for casual access
   deterrence rather than protection against a targeted attacker.
5. Save the secret. Do not put its value in source, workflow YAML, an issue, or
   a pull-request comment.

Pull-request builds use a public, disposable validation phrase and never
deploy. A push or manual run on `main` fails before upload if the production
secret is missing, leaving the previous Pages deployment intact.

## Browser behavior

The first visit shows the custom unlock screen. Selecting **Remember this
device** stores a salted, derived passphrase value in browser local storage for
14 days. It is reused to decrypt other documentation pages without prompting.
Appending `#staticrypt_logout` to a documentation URL clears the stored value.

The salt in `config.json` is public and is not a credential. Keeping it stable
prevents routine documentation deployments from signing everyone out.

## Local validation

Build the normal documentation first:

```bash
uv sync --locked --no-default-groups --group docs --no-install-project
uv run --locked --no-sync mkdocs build --strict --site-dir site
```

Read a temporary test passphrase without placing it in shell history:

```bash
read -rsp "Test passphrase: " STATICRYPT_PASSWORD
export STATICRYPT_PASSWORD
```

Then run the same encryption used by CI:

```bash
npx --yes staticrypt@3.5.4 site/* -r -d site \
  --config .github/staticrypt/config.json \
  --template .github/staticrypt/password-template.html \
  --short \
  --remember 14 \
  --template-title "Tetracorder documentation" \
  --template-instructions "Enter the shared passphrase to continue." \
  --template-placeholder "Shared passphrase" \
  --template-button "Unlock documentation" \
  --template-error "That passphrase did not work." \
  --template-remember "Remember this device" \
  --template-toggle-show "Show" \
  --template-toggle-hide "Hide"
```

Clear the test value afterward:

```bash
unset STATICRYPT_PASSWORD
```

To rotate access, replace the repository secret and manually run the
documentation workflow on `main`. The next successful deployment will require
the new passphrase.
