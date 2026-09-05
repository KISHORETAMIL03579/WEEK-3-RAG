Remove-Item .git\index.lock -Force -ErrorAction SilentlyContinue
Remove-Item .git\index -Force -ErrorAction SilentlyContinue
git reset
git status
