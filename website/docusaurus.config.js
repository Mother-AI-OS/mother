// @ts-check
import {themes as prismThemes} from 'prism-react-renderer';

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'Mother AI OS',
  tagline: 'An extensible AI agent operating system that orchestrates CLI tools via natural language',
  favicon: 'img/favicon.ico',

  url: 'https://mother-os.info',
  baseUrl: '/',

  organizationName: 'Mother-AI-OS',
  projectName: 'mother',

  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'warn',

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  // Plausible (self-hosted, cookieless) — added 2026-08-12. Ungated by
  // design: no cookie, no identifier, so it needs no consent gate and keeps
  // working for visitors who decline. This site measured nothing before.
  headTags: [
    {
      tagName: 'script',
      attributes: {
        defer: 'true',
        'data-domain': 'mother-ai-os.github.io',
        src: 'https://analytics.david-sanker.com/js/script.js',
      },
    },
  ],

  // Ad tracking removed 2026-08-11.
  //
  // This site loaded AW-672519410 — the Google tag of a DEACTIVATED Ads
  // account — plus the LinkedIn Insight Tag, both unconditionally and with no
  // consent gate. The 2026-08-09 sweep that reported the dead tag "gone from
  // every site" only covered the seven sites on the Projects VM; this one and
  // uapk.info were never touched, so both kept setting cookies for a tag that
  // could never record anything.
  //
  // Nothing replaces it: no campaign points at this domain. Re-add gated, and
  // with the live account, only when one does.

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
        // gtag preset removed 2026-08-11 — same deactivated account as above.
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
              {
                label: 'Imprint',
                to: '/imprint',
              },
            ],
          },
          {
            title: 'Ecosystem',
            items: [
              {
                label: 'Lawkraft — AI Consulting',
                href: 'https://lawkraft.com',
              },
              {
                label: 'UAPK Gateway — AI Governance',
                href: 'https://uapk.info',
              },
              {
                label: 'Morpheus Mark — IP Enforcement',
                href: 'https://morpheusmark.com',
              },
              {
                label: 'Hucke & Sanker — Law Firm',
                href: 'https://huckesanker.com',
              },
              {
                label: 'Quantum AI — Trading Research',
                href: 'https://quantum-ai-trading-bot.info',
              },
              {
                label: 'LinkedIn',
                href: 'https://de.linkedin.com/in/sankerlaw',
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
