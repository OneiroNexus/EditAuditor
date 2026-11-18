# Verification and packaging

The methods paper and original evidence files describe the historical run.
GitHub Actions runs fresh checks on the staging commit and retains receipts
for each environment.

```sh
python tools/validate.py
python tools/build_release.py
python tools/check_artifacts.py build-runs/<build-id>
```

On Windows, add `--allow-windows-platform-skips` to the validation command to account for
the POSIX-only FIFO test and unavailable symbolic-link privileges.
The receipt records any exceptions. The default verifier and Linux CI require
all unit tests to run. Fixtures are synthetic and serve as regression cases.
