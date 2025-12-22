# GitHub Pages Setup Instructions

This document explains how to set up and customize the GitHub Pages site for Classroom Token Hub.

## Quick Setup

1. **Enable GitHub Pages**
   - Go to your repository settings on GitHub
   - Navigate to "Pages" in the left sidebar
   - Under "Source", select "Deploy from a branch"
   - Choose branch: `main` (or your default branch)
   - Choose folder: `/docs`
   - Click "Save"

2. **Wait for deployment**
   - GitHub will automatically build and deploy your site
   - This usually takes 1-2 minutes
   - Your site will be available at: `https://[username].github.io/[repository-name]/`

## Customizing the Landing Page

### Adding Your Google Form

The landing page includes a placeholder for a Google Form to collect access requests. To add your form:

1. **Create your Google Form**
   - Go to [Google Forms](https://forms.google.com)
   - Create a new form with fields for:
     - Name
     - Email
     - Institution/School
     - Intended use case
     - Any other relevant information

2. **Get the embed code**
   - Click the "Send" button in your form
   - Click the embed icon (`< >`)
   - Copy the iframe URL (it will look like: `https://docs.google.com/forms/d/e/YOUR_FORM_ID/viewform?embedded=true`)

3. **Update index.html**
   - Open `docs/index.html`
   - Find the "Request Access" section (search for `id="access"`)
   - Replace the placeholder section with:
   ```html
   <iframe
       src="https://docs.google.com/forms/d/e/YOUR_FORM_ID/viewform?embedded=true"
       class="form-embed"
       frameborder="0"
       marginheight="0"
       marginwidth="0">
       Loading…
   </iframe>
   ```

### Adding Screenshots

The landing page includes placeholder cards for screenshots. To add real screenshots:

1. **Capture screenshots**
   - Teacher dashboard
   - Student portal
   - Mobile interface
   - Store management
   - Any other key features

2. **Add screenshots to the repository**
   - Create a folder: `docs/images/` (or use `static/images/`)
   - Add your screenshot files (PNG or JPG format recommended)
   - Optimize images for web (consider using tools like TinyPNG)

3. **Update the HTML**
   - Open `docs/index.html`
   - Find the screenshots section (search for `id="screenshots"`)
   - Replace each `<div class="screenshot-placeholder">` with:
   ```html
   <img src="images/your-screenshot.png" alt="Description of screenshot">
   ```

### Customizing Links

Update these links in `index.html` to point to your actual deployment:

- **Live App Link**: Search for `btn-primary` buttons and add your app URL
- **GitHub Repository**: Already points to `https://github.com/timwonderer/classroom-economy`
- **Demo Site**: Add a link to your demo instance if available

### Custom Domain (Optional)

To use a custom domain like `classroomtokenhub.com`:

1. **Configure DNS**
   - Add a CNAME record pointing to `[username].github.io`
   - Or add A records pointing to GitHub's IP addresses

2. **Update GitHub Pages settings**
   - Go to repository Settings → Pages
   - Enter your custom domain in the "Custom domain" field
   - Enable "Enforce HTTPS"

3. **Add CNAME file**
   - Create `docs/CNAME` with your domain name
   - Commit and push

## Updating Content

### Changing Colors and Styling

All styles are contained in the `<style>` section of `index.html`. Key CSS variables you can customize:

```css
:root {
    --primary-color: #2563eb;      /* Main brand color */
    --primary-dark: #1e40af;       /* Darker shade for hovers */
    --secondary-color: #10b981;    /* Accent color */
    --accent-color: #f59e0b;       /* Additional accent */
}
```

### Updating Features

Find the `features-grid` section and modify the feature cards. Each card follows this structure:

```html
<div class="feature-card">
    <div class="feature-icon">🎯</div>
    <h3>Feature Title</h3>
    <p>Feature description goes here.</p>
</div>
```

### Updating Statistics

The stats section displays key metrics. Update the numbers and labels in the `stats-grid`:

```html
<div class="stat">
    <h4>35+</h4>
    <p>Database Models</p>
</div>
```

## Testing Locally

To preview the GitHub Pages site locally:

1. **Using Python's built-in server**:
   ```bash
   cd docs
   python3 -m http.server 8000
   ```
   Visit `http://localhost:8000`

2. **Using Jekyll** (if you add Jekyll support):
   ```bash
   bundle exec jekyll serve
   ```

## Troubleshooting

### Site not updating
- Clear your browser cache
- Check GitHub Actions for build errors
- Ensure the correct branch and folder are selected in Pages settings

### Images not loading
- Check file paths are relative to `index.html`
- Ensure images are committed to the repository
- Verify image files are in the correct location

### Form not embedding
- Verify the Google Form is set to "Anyone with the link can respond"
- Check that the embed URL is correct
- Try the form URL directly in a browser first

## Maintenance

- **Keep version up to date**: Update the version badge in the hero section when releasing new versions
- **Update screenshots**: Refresh screenshots when the UI changes significantly
- **Monitor form responses**: Regularly check your Google Form for access requests
- **Update documentation links**: Ensure all links to docs remain valid as the project evolves

## Resources

- [GitHub Pages Documentation](https://docs.github.com/en/pages)
- [Google Forms Help](https://support.google.com/docs/topic/9054603)
- [Web Accessibility Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)

---

**Last Updated:** 2025-12-22
