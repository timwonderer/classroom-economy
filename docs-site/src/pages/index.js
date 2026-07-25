import clsx from "clsx";
import Heading from "@theme/Heading";
import Link from "@docusaurus/Link";
import Layout from "@theme/Layout";

export default function Home() {
  return (
    <Layout
      title="Classroom Token Hub Guides"
      description="Current student and teacher guidance for Classroom Token Hub"
    >
      <header className="hero">
        <div className="container">
          <div className="row">
            <div className="col col--7">
              <Heading as="h1" className="hero__title">
                Classroom Token Hub Guides
              </Heading>
              <p className="hero__subtitle">
                Clear guidance for students and teachers, written for the current app.
              </p>
              <div className={clsx("margin-top--md")}>
                <Link className="button button--secondary button--lg" to="/user-guides">
                  Open user guides
                </Link>
              </div>
            </div>
            <div className="col col--5">
              <div className="card padding--lg hero-card">
                <Heading as="h2" className="hero-card__title">
                  What you’ll find
                </Heading>
                <ul className="clean-list hero-card__list">
                  <li>Student setup, classes, attendance, money, store, and support.</li>
                  <li>Teacher setup, classroom management, payroll, bills, and settings.</li>
                  <li>Reference pages for the active app behavior.</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </header>
    </Layout>
  );
}
