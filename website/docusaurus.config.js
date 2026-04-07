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

  headTags: [
    {
      tagName: 'script',
      attributes: { async: 'true', src: 'https://www.googletagmanager.com/gtag/js?id=AW-672519410' },
    },
    {
      tagName: 'script',
      attributes: {},
      innerHTML: `
        window.dataLayer = window.dataLayer || [];
        function gtag(){dataLayer.push(arguments);}
        gtag('js', new Date());
        gtag('config', 'AW-672519410');
        _linkedin_partner_id = "520105121";
        window._linkedin_data_partner_ids = window._linkedin_data_partner_ids || [];
        window._linkedin_data_partner_ids.push(_linkedin_partner_id);
        (function(l){if(!l){window.lintrk=function(a,b){window.lintrk.q.push([a,b])};window.lintrk.q=[]}var s=document.getElementsByTagName("script")[0];var b=document.createElement("script");b.type="text/javascript";b.async=true;b.src="https://snap.licdn.com/li.lms-analytics/insight.min.js";s.parentNode.insertBefore(b,s);})(window.lintrk);
      `,
    },
  ],

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
        gtag: {
          trackingID: 'AW-672519410',
          anonymizeIP: true,
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
