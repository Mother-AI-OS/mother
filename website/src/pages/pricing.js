import clsx from 'clsx';
import Link from '@docusaurus/Link';
import Layout from '@theme/Layout';
import Heading from '@theme/Heading';

import styles from './pricing.module.css';

const pricingTiers = [
  {
    name: 'Free',
    price: '$0',
    period: 'forever',
    description: 'Perfect for individual developers and open source projects.',
    features: [
      'Core Mother AI OS',
      'Built-in plugins (filesystem, shell, web)',
      'Self-hosted deployment',
      'Community support via GitHub',
      'MIT licensed',
    ],
    cta: 'Get Started',
    ctaLink: '/docs/getting-started/installation',
    featured: false,
  },
  {
    name: 'Pro',
    price: '$49',
    period: '/month',
    description: 'For professionals and small teams who need more power.',
    features: [
      'Everything in Free',
      'Premium plugins access',
      'Cloud dashboard',
      'Priority email support',
      'Usage analytics',
      'API rate limit increase',
    ],
    cta: 'Coming Soon',
    ctaLink: '#',
    featured: true,
    comingSoon: true,
  },
  {
    name: 'Enterprise',
    price: 'Custom',
    period: '',
    description: 'For organizations with advanced security and support needs.',
    features: [
      'Everything in Pro',
      'Dedicated support engineer',
      'Custom plugin development',
      'On-premise deployment',
      'SSO/LDAP integration',
      'SLA guarantee',
      'Security audit reports',
    ],
    cta: 'Contact Us',
    ctaLink: 'mailto:david@sanker.at',
    featured: false,
  },
];

function PricingCard({name, price, period, description, features, cta, ctaLink, featured, comingSoon}) {
  return (
    <div className={clsx('col col--4')}>
      <div className={clsx('pricing-card', featured && 'featured')}>
        <Heading as="h3" className={styles.tierName}>{name}</Heading>
        <div className={styles.priceContainer}>
          <span className="pricing-price">{price}</span>
          <span className="pricing-period">{period}</span>
        </div>
        <p className={styles.description}>{description}</p>
        <ul className={styles.featureList}>
          {features.map((feature, idx) => (
            <li key={idx}>✓ {feature}</li>
          ))}
        </ul>
        <Link
          className={clsx(
            'button button--lg button--block',
            featured ? 'button--primary' : 'button--outline button--secondary',
            comingSoon && styles.disabled
          )}
          to={ctaLink}>
          {cta}
        </Link>
      </div>
    </div>
  );
}

function FAQ() {
  const faqs = [
    {
      question: 'Is Mother AI OS really free?',
      answer: 'Yes! The core Mother AI OS is open source under the MIT license. You can use it for personal projects, commercial applications, and even modify it to suit your needs.',
    },
    {
      question: 'What are premium plugins?',
      answer: 'Premium plugins are specialized integrations (email, calendar, CRM, etc.) developed and maintained by us. Pro subscribers get access to all premium plugins.',
    },
    {
      question: 'Can I self-host the Pro features?',
      answer: 'The core software is always self-hostable. Pro tier provides cloud dashboard, support, and access to premium plugins that require additional infrastructure.',
    },
    {
      question: 'What kind of support is included?',
      answer: 'Free users get community support via GitHub Discussions. Pro users get priority email support with 24-hour response time. Enterprise gets a dedicated support engineer.',
    },
  ];

  return (
    <section className={styles.faq}>
      <div className="container">
        <Heading as="h2" className="text--center" style={{marginBottom: '2rem'}}>
          Frequently Asked Questions
        </Heading>
        <div className="row">
          <div className="col col--8 col--offset-2">
            {faqs.map((faq, idx) => (
              <div key={idx} className={styles.faqItem}>
                <Heading as="h4">{faq.question}</Heading>
                <p>{faq.answer}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

export default function Pricing() {
  return (
    <Layout
      title="Pricing"
      description="Mother AI OS pricing plans - Free, Pro, and Enterprise">
      <main>
        <section className={styles.pricingHeader}>
          <div className="container">
            <Heading as="h1" className="text--center">
              Simple, Transparent Pricing
            </Heading>
            <p className="text--center" style={{fontSize: '1.2rem', marginTop: '1rem'}}>
              Start free, upgrade when you need more power.
            </p>
          </div>
        </section>

        <section className={styles.pricingCards}>
          <div className="container">
            <div className="row">
              {pricingTiers.map((tier, idx) => (
                <PricingCard key={idx} {...tier} />
              ))}
            </div>
          </div>
        </section>

        <FAQ />

        <section className={styles.enterprise}>
          <div className="container text--center">
            <Heading as="h2">Need Custom Solutions?</Heading>
            <p style={{fontSize: '1.1rem', marginBottom: '2rem'}}>
              We offer consulting services for custom plugin development, integration, and training.
            </p>
            <Link
              className="button button--primary button--lg"
              href="mailto:david@sanker.at">
              Contact for Enterprise
            </Link>
          </div>
        </section>
      </main>
    </Layout>
  );
}
