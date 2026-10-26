# Contributing to FitFolio

The team's workflow (branches, pull requests, reviews and issue tracking) is
described in the [Development Plan](docs/DevelopmentPlan/DevelopmentPlan.tex).
Backend setup is in [src/backend/README.md](src/backend/README.md).

## Secret scanning

API keys, passwords and tokens must never be committed. The repository is
public, so a committed key is exposed as soon as it is pushed and has to be
revoked and replaced. Keep secrets in a `.env` file, which Git ignores.

Two checks use [gitleaks](https://github.com/gitleaks/gitleaks):

- **Before each commit, on your machine.** A [pre-commit](https://pre-commit.com)
  hook scans the changes you are committing and stops the commit if they
  contain a secret.
- **In CI.** The `Secret scan` workflow scans the commits in every pull request
  and every push to `main`.

### Set up the pre-commit hook (once per clone)

macOS:

```bash
brew install pre-commit
pre-commit install
```

Windows (PowerShell):

```powershell
uv tool install pre-commit
pre-commit install
```

If PowerShell cannot find `pre-commit` after installing it, run
`uv tool update-shell` and open a new PowerShell window.

Run `pre-commit install` from the repository root. The first commit after
setup takes about a minute while pre-commit downloads and builds gitleaks.
After that, each commit is checked in under a second.

If the setup fails with `CERTIFICATE_VERIFY_FAILED` on macOS, your Python
from python.org has not installed its certificates yet. Run
`Install Certificates.command` in the `Python 3.x` folder in Applications,
or install pre-commit with Homebrew as shown above.

### If a commit is blocked

The hook prints the file, line and rule, with the secret redacted. Remove
the secret from the file (move it to `.env`) and commit again. If the
finding is a false positive, ask the team before ignoring it. If a secret
was ever pushed, revoke it with its provider right away.
