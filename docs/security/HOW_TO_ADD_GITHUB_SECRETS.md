# How to Add SSH Host Key to GitHub Secrets

## Quick Start (5 Minutes)

This guide shows you exactly how to add the `KNOWN_HOSTS` secret to GitHub.

---

## Step 1: Get Your Server's SSH Host Key

### Option A: Use the Automated Script (Easiest)

```bash
# Navigate to your project directory
cd /path/to/classroom-economy

# Run the setup script with your production server IP
./scripts/setup-ssh-security.sh YOUR_PRODUCTION_SERVER_IP

# Example:
./scripts/setup-ssh-security.sh 142.93.123.45
```

**The script will:**
- Retrieve the host keys automatically
- Save them to `known_hosts_github_secret.txt`
- Show you the contents
- Guide you through the next steps

**Output will look like:**
```
========================================
Host Keys Retrieved
========================================

✓ Host keys saved to: known_hosts_github_secret.txt

File contents:
----------------------------------------
|1|abc123def456...= ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAbc...
|1|ghi789jkl012...= ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC...
----------------------------------------
```

**Copy this entire output** (everything between the dashes).

### Option B: Manual Method (If Script Doesn't Work)

```bash
# Get host keys manually
ssh-keyscan -H YOUR_PRODUCTION_SERVER_IP > known_hosts_temp

# View the contents
cat known_hosts_temp
```

Copy the entire contents of the file.

---

## Step 2: Navigate to GitHub Repository Settings

### 2.1 Open Your Repository

1. Go to: https://github.com/YOUR_USERNAME/classroom-economy
   - (Replace YOUR_USERNAME with your actual GitHub username)

### 2.2 Access Settings

1. Click the **"Settings"** tab at the top of the repository page
   ```
   < > Code    Issues    Pull requests    Actions    Projects    Wiki    Security    ⚙️ Settings
                                                                                           ^^^^
   ```

2. You'll see a sidebar on the left with many options

---

## Step 3: Navigate to Actions Secrets

### 3.1 Find Secrets Section

In the left sidebar, look for:

```
Settings
├── General
├── Collaborators
├── ...
├── Secrets and variables    ← Click this
│   ├── Actions              ← Then click this
│   ├── Codespaces
│   └── Dependabot
├── ...
```

**Full path:** Settings → Secrets and variables → Actions

### 3.2 You'll See the Secrets Page

The page shows:
```
Actions secrets / New secret

Secrets are environment variables that are encrypted.

Repository secrets:
[List of existing secrets like DO_DEPLOY_KEY, TURNSTILE_SECRET_KEY, etc.]

[New repository secret] button
```

---

## Step 4: Add the KNOWN_HOSTS Secret

### 4.1 Click "New repository secret"

Click the green **"New repository secret"** button at the top right.

### 4.2 Fill in the Secret Form

You'll see a form with two fields:

**Field 1: Name**
```
Name *
[________________]
```
Type exactly: `KNOWN_HOSTS`
- Must be ALL CAPS
- Must be spelled exactly like this
- No spaces

**Field 2: Secret**
```
Secret *
[_________________________]
[_________________________]
[_________________________]
```

Paste the **ENTIRE contents** from Step 1.

**Should look like:**
```
|1|abc123def456...= ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAbc...
|1|ghi789jkl012...= ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC...
|1|mno345pqr678...= ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTI...
```

**Important:**
- Include ALL lines (usually 2-4 lines)
- Include the entire line including the `|1|...=` prefix
- Do NOT add extra spaces or line breaks
- Do NOT modify the content in any way

### 4.3 Add the Secret

1. Click the green **"Add secret"** button at the bottom
2. You'll be redirected back to the secrets page
3. You should now see `KNOWN_HOSTS` in the list of secrets

---

## Step 5: Verify the Secret Was Added

### 5.1 Check Secrets List

You should see something like:

```
Repository secrets:
┌────────────────────────┬─────────────┬─────────┐
│ Name                   │ Updated     │ Actions │
├────────────────────────┼─────────────┼─────────┤
│ DO_DEPLOY_KEY         │ 1 day ago   │ Update  │
│ KNOWN_HOSTS           │ Just now    │ Update  │  ← New!
│ PRODUCTION_SERVER_IP  │ 3 days ago  │ Update  │
│ TURNSTILE_SECRET_KEY  │ 1 week ago  │ Update  │
└────────────────────────┴─────────────┴─────────┘
```

### 5.2 Secret Value is Hidden

**Note:** GitHub will NOT show you the secret value after you add it. This is normal and expected for security reasons.

If you need to update it later, click the **"Update"** button next to `KNOWN_HOSTS`.

---

## Step 6: Update Your Workflow Files

Now that the secret is added, you need to use it in your workflows.

### 6.1 Replace Workflow Files

```bash
# In your local repository
cp .github/workflows/deploy.yml.FIXED .github/workflows/deploy.yml
cp .github/workflows/toggle-maintenance.yml.FIXED .github/workflows/toggle-maintenance.yml
```

### 6.2 Verify the Changes

Check that the new workflows reference the secret:

```bash
grep -n "KNOWN_HOSTS" .github/workflows/deploy.yml
```

**Should output:**
```
24:        echo "${{ secrets.KNOWN_HOSTS }}" > ~/.ssh/known_hosts
```

### 6.3 Commit and Push

```bash
git add .github/workflows/deploy.yml .github/workflows/toggle-maintenance.yml
git commit -m "SECURITY: Enable SSH host key verification"
git push
```

---

## Step 7: Test the Configuration

### 7.1 Trigger a Test Deployment

**Option A:** Push a commit to main (triggers deploy.yml automatically)

**Option B:** Manually trigger a workflow
1. Go to: **Actions** tab in GitHub
2. Click on **"Deploy to DO on push to main"** workflow
3. Click **"Run workflow"** dropdown
4. Click green **"Run workflow"** button

### 7.2 Check the Logs

1. Click on the running workflow
2. Click on the **"deploy"** job
3. Expand the **"Set up SSH host key verification"** step

**Success looks like:**
```
✓ SSH host key verification enabled
```

4. Expand the **"Deploy to DO Production Server"** step

**Should NOT see:**
```
Warning: Permanently added 'xxx.xxx.xxx.xxx' (ED25519) to the list of known hosts.
```

**Should connect cleanly without warnings**

---

## Troubleshooting

### Issue 1: "Secret name is invalid"

**Problem:** GitHub doesn't accept the secret name

**Solution:**
- Make sure it's exactly: `KNOWN_HOSTS` (all caps, underscore)
- No leading/trailing spaces
- No special characters

### Issue 2: "No host keys retrieved"

**Problem:** The script didn't get any host keys

**Possible causes:**
1. Server IP is wrong
2. Server is not reachable
3. SSH is not running on port 22
4. Firewall is blocking

**Solution:**
```bash
# Test if server is reachable
ping YOUR_SERVER_IP

# Test if SSH port is open
nc -zv YOUR_SERVER_IP 22

# Try manual SSH connection
ssh root@YOUR_SERVER_IP
```

### Issue 3: "Host key verification failed" in Workflow

**Problem:** Workflow still fails with host key error

**Possible causes:**
1. Secret wasn't added correctly
2. Secret has wrong content
3. Workflow file wasn't updated

**Solution:**
1. **Verify secret exists:**
   - Go to Settings → Secrets and variables → Actions
   - Look for `KNOWN_HOSTS` in the list

2. **Re-add the secret:**
   - Click "Update" next to KNOWN_HOSTS
   - Re-paste the host keys
   - Save

3. **Verify workflow references it:**
   ```bash
   grep "secrets.KNOWN_HOSTS" .github/workflows/deploy.yml
   ```
   Should find: `echo "${{ secrets.KNOWN_HOSTS }}" > ~/.ssh/known_hosts`

4. **Check workflow was updated:**
   ```bash
   git log -1 --name-only
   ```
   Should show `.github/workflows/deploy.yml` in changed files

### Issue 4: "Permission denied" accessing secret

**Problem:** Workflow can't read the secret

**Solution:**
- Make sure workflow has `environment: production` (if using environments)
- Check repository settings → Actions → General → Workflow permissions
- Ensure "Read and write permissions" is enabled

### Issue 5: Can't find "Secrets and variables" option

**Problem:** Don't see the option in Settings

**Possible causes:**
- You don't have admin access to the repository
- Wrong repository (looking at a fork?)

**Solution:**
1. Make sure you're the repository owner or have admin access
2. Check you're on the correct repository
3. URL should be: `https://github.com/YOUR_USERNAME/YOUR_REPO/settings`

---

## Visual Guide (What to Look For)

### GitHub Settings Page Layout

```
┌──────────────────────────────────────────────────────────────┐
│  YOUR_USERNAME / classroom-economy                  [Search] │
├──────────────────────────────────────────────────────────────┤
│  < > Code  Issues  PRs  Actions  Projects  Security Settings │
│                                                        ^^^^^^^ │
├─────────────┬────────────────────────────────────────────────┤
│ Sidebar     │ Main Content Area                              │
│             │                                                │
│ General     │ Repository name                                │
│ Access      │ [classroom-economy]                            │
│ Code        │                                                │
│ ...         │ Description                                    │
│             │ [Add description]                              │
│ Secrets >   │                                                │
│  Actions    │ ...                                            │
│  Codespaces │                                                │
│             │                                                │
└─────────────┴────────────────────────────────────────────────┘
```

### Secrets Page Layout

```
┌──────────────────────────────────────────────────────────────┐
│ Actions secrets and variables                                │
├──────────────────────────────────────────────────────────────┤
│                                    [New repository secret]   │
│                                                               │
│ Repository secrets                                            │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ Name                   │ Updated    │ Actions            │ │
│ ├──────────────────────────────────────────────────────────┤ │
│ │ DO_DEPLOY_KEY         │ 1 day ago  │ Update   Remove   │ │
│ │ PRODUCTION_SERVER_IP  │ 3 days ago │ Update   Remove   │ │
│ │ TURNSTILE_SECRET_KEY  │ 1 week ago │ Update   Remove   │ │
│ └──────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### Add Secret Form

```
┌──────────────────────────────────────────────────────────────┐
│ Actions secrets / New secret                                 │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│ Name *                                                        │
│ ┌───────────────────────────────────────────────────────┐    │
│ │ KNOWN_HOSTS                                           │    │
│ └───────────────────────────────────────────────────────┘    │
│                                                               │
│ Secret *                                                      │
│ ┌───────────────────────────────────────────────────────┐    │
│ │ |1|abc123...= ssh-ed25519 AAAAC3NzaC1lZDI1NTE5...    │    │
│ │ |1|def456...= ssh-rsa AAAAB3NzaC1yc2EAAAADAQABA...   │    │
│ │                                                       │    │
│ └───────────────────────────────────────────────────────┘    │
│                                                               │
│                                    [Add secret]              │
└──────────────────────────────────────────────────────────────┘
```

---

## Quick Reference

**Secret Name (exactly):** `KNOWN_HOSTS`

**Secret Value:** Output from one of these:
```bash
./scripts/setup-ssh-security.sh YOUR_IP
# OR
ssh-keyscan -H YOUR_IP
```

**Location in GitHub:**
```
Repository → Settings → Secrets and variables → Actions → New repository secret
```

**Verify it worked:**
```bash
# After committing workflow changes, check Actions tab
# Look for: "✓ SSH host key verification enabled"
```

---

## Next Steps After Adding Secret

1. ✅ Secret added to GitHub
2. ⏭️ Replace workflow files (`.FIXED` → regular)
3. ⏭️ Commit and push changes
4. ⏭️ Test deployment
5. ✅ Security vulnerability fixed!

---

**Last Updated:** 2025-12-22
**Difficulty:** Easy (5 minutes)
**Required Access:** Repository admin/owner
