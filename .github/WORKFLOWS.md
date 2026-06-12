# GitHub Actions Workflow

This repository includes an automated GitHub Actions workflow that builds and publishes Docker images for the Reolink Enhanced API app.

## Build Workflow: `.github/workflows/builder.yaml`

### What it does:

1. **Triggers automatically** when you push to the `main` branch
2. **Builds Docker images** for multiple architectures:
   - `linux/amd64` (x86-64)
   - `linux/arm64` (ARM 64-bit - for Apple Silicon, Raspberry Pi 4+)
3. **Pushes images** to GitHub Container Registry (ghcr.io)
4. **Tags images** with:
   - `latest` (always points to main branch)
   - Version number from manifest.json

### How it works:

The workflow uses:
- **QEMU**: Enables building for non-native architectures
- **Docker Buildx**: Multi-architecture build tool
- **GitHub Container Registry**: Stores the built images

### Prerequisites:

The workflow automatically uses your GitHub token (`GITHUB_TOKEN`), so no additional setup is needed.

### Images published:

After the workflow completes, Docker images are available at:
```
ghcr.io/marcusmaday/reolink-nvr-enhanced-amd64:latest
ghcr.io/marcusmaday/reolink-nvr-enhanced-amd64:0.2.0  # example versioned tag
```

### Making images public:

By default, images may be private. To make them public:

1. Go to your GitHub repository
2. Click **Packages** (right sidebar)
3. Find `reolink-nvr-enhanced-amd64`
4. Click the package name
5. Click **Package settings**
6. Scroll down and change visibility to **Public**

Or set it when pushing:
```bash
docker push ghcr.io/marcusmaday/reolink-nvr-enhanced-amd64:latest
```

## Testing the workflow:

1. Make a change to the code
2. Commit and push to `main`:
   ```bash
   git add .
   git commit -m "Your message"
   git push origin main
   ```
3. Go to your repository on GitHub
4. Click **Actions** tab
5. See the workflow running
6. Wait for it to complete (usually 5-15 minutes)

## Troubleshooting:

### Workflow fails with "authentication failed"
- Your `GITHUB_TOKEN` should be automatically available
- Check that you have push permissions to your repository

### Images still not showing in Home Assistant
After the workflow completes:
1. Make sure images are public in GitHub Packages
2. In Home Assistant, go to App Store
3. Remove the repository if it exists
4. Hard refresh your browser: `Ctrl+Shift+R`
5. Re-add the repository: `https://github.com/marcusmaday/reolink-nvr-ha-app`
6. Refresh the App Store
7. Search for "Reolink Enhanced"

### Need to rebuild manually?

Click the **Run workflow** button in the Actions tab to manually trigger a build.

## Next steps:

1. **Push your code** to trigger the workflow
2. **Wait for the build** to complete (check Actions tab)
3. **Make images public** in GitHub Packages if needed
4. **Refresh Home Assistant** and the app should appear
