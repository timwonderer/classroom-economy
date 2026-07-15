function stripTrailingSlash(value) {
  return value.replace(/\/+$/, "");
}

const docsSiteUrl = stripTrailingSlash(
  process.env.DOCS_SITE_URL || "http://127.0.0.1:3000",
);
const appDocsOrigin = stripTrailingSlash(
  process.env.APP_DOCS_ORIGIN || "http://127.0.0.1:5000",
);
// Docusaurus config for the external docs/blog site.
// Route base path stays at the site root for migrated public docs.
// Flask only redirects the subset of /docs paths that exist in route-map.json.

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: "Classroom Token Hub",
  tagline: "Guides and reference for the current app",
  url: docsSiteUrl,
  baseUrl: "/",
  future: {
    v4: true,
    faster: true,
  },
  organizationName: "timwonderer",
  projectName: "classroom-economy",
  onBrokenLinks: "throw",
  markdown: {
    hooks: {
      onBrokenMarkdownLinks: "warn",
    },
  },
  i18n: {
    defaultLocale: "en",
    locales: ["en"],
  },
  presets: [
    [
      "classic",
      {
        docs: {
          routeBasePath: "/",
          sidebarPath: require.resolve("./sidebars.js"),
          editUrl: "https://github.com/timwonderer/classroom-economy/tree/main/docs-site/",
        },
        blog: {
          showReadingTime: true,
          editUrl: "https://github.com/timwonderer/classroom-economy/tree/main/docs-site/",
        },
        theme: {
          customCss: require.resolve("./src/css/custom.css"),
        },
      },
    ],
  ],
  themeConfig: {
    navbar: {
      title: "Classroom Token Hub",
      items: [
        {to: "/user-guides", label: "Guides", position: "left"},
        {to: "/technical", label: "Reference", position: "left"},
        {to: "/blog", label: "Notes", position: "left"},
        {
          href: "https://github.com/timwonderer/classroom-economy",
          label: "GitHub",
          position: "right",
        },
      ],
    },
    footer: {
      style: "dark",
      links: [
        {
          title: "Guides",
          items: [
            {label: "User Guides", to: "/user-guides"},
            {label: "Technical Reference", to: "/technical"},
          ],
        },
        {
          title: "Project",
          items: [
            {
              label: "Repository",
              href: "https://github.com/timwonderer/classroom-economy",
            },
            {
              label: "Flask Docs",
              href: `${appDocsOrigin}/docs/`,
            },
          ],
        },
      ],
      copyright: `Copyright ${new Date().getFullYear()} Classroom Token Hub`,
    },
  },
};

module.exports = config;
