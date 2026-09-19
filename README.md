# insurance-claims-rag

Remove-Item -Recurse -Force .git

git init
git add .
git commit -m "Initial commit"

git branch -M main
git remote add origin https://github.com/hansenguxd/insurance_claims.git
git push -u origin main

## check the changes:
git status
git remote -v

##for update one file
git add agent.py
git commit -m "Update agent.py"
git push origin main