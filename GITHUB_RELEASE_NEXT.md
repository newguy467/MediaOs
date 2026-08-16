# GitHub release: 1.01beta

Use `RELEASE_NOTES_1.01beta.md` as the release body.

```bash
git tag -a 1.01beta -m "MediaOS 1.01beta"
git push origin 1.01beta
gh release create 1.01beta -F RELEASE_NOTES_1.01beta.md --title "MediaOS 1.01beta"
```
