import Link from "next/link";

export default function HomePage() {
  return (
    <main className="authShell">
      <section className="authCard landingCard">
        <p className="eyebrow">Business Plan Writer · Private beta</p>
        <h1>Build a plan you can come back to.</h1>
        <p>Create an account to keep each intake private, save answers automatically, and resume from any device.</p>
        <div className="landingActions"><Link className="buttonLink" href="/register">Create account</Link><Link className="buttonLink secondary" href="/login">Sign in</Link></div>
        <Link className="demoLink" href="/demo">Open the fictional demo</Link>
      </section>
    </main>
  );
}
