// @ts-check
import {themes as prismThemes} from 'prism-react-renderer';

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'Mother AI OS',
  tagline: 'An extensible AI agent operating system that orchestrates CLI tools via natural language',
  favicon: 'img/favicon.ico',

  url: 'https://mother-ai-os.github.io',
  baseUrl: '/mother/',

  organizationName: 'Mother-AI-OS',
  projectName: 'mother',

  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'warn',

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          sidebarPath: './sidebars.js',
          editUrl: 'https://github.com/Mother-AI-OS/mother/tree/main/website/',
        },
        blog: {
          showReadingTime: true,
          feedOptions: {
            type: ['rss', 'atom'],
            xslt: true,
          },
          editUrl: 'https://github.com/Mother-AI-OS/mother/tree/main/website/',
        },
        theme: {
          customCss: './src/css/custom.css',
        },
      }),
    ],
  ],

  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      image: 'img/mother-social-card.png',
      navbar: {
        title: 'Mother AI OS',
        logo: {
          alt: 'Mother AI OS Logo',
          src: 'img/logo.svg',
        },
        items: [
          {
            type: 'docSidebar',
            sidebarId: 'tutorialSidebar',
            position: 'left',
            label: 'Documentation',
          },
          {to: '/blog', label: 'Blog', position: 'left'},
          {to: '/services', label: 'Services', position: 'left'},
          {to: '/pricing', label: 'Pricing', position: 'left'},
          {
            href: 'https://github.com/Mother-AI-OS/mother',
            label: 'GitHub',
            position: 'right',
          },
        ],
      },
      footer: {
        style: 'dark',
        links: [
          {
            title: 'Documentation',
            items: [
              {
                label: 'Getting Started',
                to: '/docs/getting-started/installation',
              },
              {
                label: 'Plugins',
                to: '/docs/plugins/built-in',
              },
              {
                label: 'API Reference',
                to: '/docs/api/rest-endpoints',
              },
            ],
          },
          {
            title: 'Community',
            items: [
              {
                label: 'GitHub Discussions',
                href: 'https://github.com/Mother-AI-OS/mother/discussions',
              },
              {
                label: 'Twitter',
                href: 'https://twitter.com/MotherAIOS',
              },
            ],
          },
          {
            title: 'More',
            items: [
              {
                label: 'Blog',
                to: '/blog',
              },
              {
                label: 'GitHub',
                href: 'https://github.com/Mother-AI-OS/mother',
              },
            ],
          },
        ],
        copyright: `Copyright © ${new Date().getFullYear()} David Sanker. Built with Docusaurus.`,
      },
      prism: {
        theme: prismThemes.github,
        darkTheme: prismThemes.dracula,
        additionalLanguages: ['bash', 'python', 'yaml', 'json'],
      },
      colorMode: {
        defaultMode: 'dark',
        disableSwitch: false,
        respectPrefersColorScheme: true,
      },
    }),
};

export default config;
