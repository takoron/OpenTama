# Pushing this repo to github.com/takoron/OpenTama

This tarball is a complete git repository with tags `v0.3.0` … `v0.3.4`
plus a small URL-fix commit on top. To publish it, run these commands
on a machine that has your GitHub SSH key.

## 1. Create the empty repo on GitHub

Either through the web UI at <https://github.com/new> (owner: `takoron`,
name: `OpenTama`, **leave it empty** — no README, no .gitignore, no
license), or with the GitHub CLI:

```bash
gh repo create takoron/OpenTama --public --description \
  "Office-WiFi-gated Tamagotchi for Claude Code. Mascot: Takoron."
```

## 2. Extract and inspect

```bash
tar -xzf OpenTama.tar.gz
cd OpenTama
git log --oneline       # should show 6 commits ending in the URL fix
git tag --list          # v0.3.0 … v0.3.4
```

## 3. (Optional) Rewrite the commit author

The commits inside the tarball were authored as `OpenTama
<you@example.com>` from the sandbox. If you want your real identity on
the history, do this **before** pushing:

```bash
git -c user.name="takoron" -c user.email="your@email" \
    rebase --root --exec "git commit --amend --reset-author --no-edit"
```

This rewrites every commit's author/committer to your identity. Skip
this step if you don't mind the placeholder author.

## 4. Add the remote and push

```bash
git remote add origin git@github.com:takoron/OpenTama.git
git push -u origin main
git push --tags
```

That's it — the repo, all five release tags, and the URL-fix commit
are now on GitHub.

## 5. (Optional) Create GitHub Releases from the tags

```bash
gh release create v0.3.4 --notes-from-tag
gh release create v0.3.3 --notes-from-tag
# … and so on for older tags if you want release pages
```

## Troubleshooting

* **`Permission denied (publickey)`** — your SSH key isn't registered
  with GitHub. Run `ssh -T git@github.com` to test; if it fails,
  follow <https://docs.github.com/en/authentication/connecting-to-github-with-ssh>.

* **`! [rejected] main -> main (fetch first)`** — the GitHub repo
  isn't empty. Either delete it and recreate empty, or
  `git push -u origin main --force` if you're sure.

* **HTTPS instead of SSH** — swap step 4 for:
  ```bash
  git remote add origin https://github.com/takoron/OpenTama.git
  git push -u origin main
  git push --tags
  ```
  GitHub will prompt for a personal access token.
