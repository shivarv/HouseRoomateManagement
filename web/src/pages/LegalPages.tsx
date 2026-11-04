import type { ReactNode } from "react";
import { Link } from "react-router";
import { Card, PageTitle } from "../components/ui";

/** Where people write to us. Shown on Support and in the privacy policy; the App Store links both. */
export const SUPPORT_EMAIL = "SUPPORT_EMAIL_TO_CONFIRM";
const UPDATED = "26 October 2026";

/** Public pages (no sign-in): the App Store needs a privacy policy and a support page. */
function LegalLayout({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <Link to="/" className="mb-6 inline-flex items-center gap-2 text-sm font-semibold text-indigo-700 hover:underline">
        🏠 Roommates
      </Link>
      <PageTitle title={title} subtitle={subtitle} />
      <Card className="space-y-5 text-sm leading-relaxed text-slate-700 [&_h2]:text-base [&_h2]:font-semibold [&_h2]:text-slate-900 [&_ul]:list-disc [&_ul]:space-y-1 [&_ul]:pl-5">
        {children}
      </Card>
    </div>
  );
}

const mail = <a className="font-medium text-indigo-700 hover:underline" href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>;

export function PrivacyPage() {
  return (
    <LegalLayout title="Privacy policy" subtitle={`Last updated ${UPDATED}`}>
      <p>
        Roommates (the website and the iPhone app) helps a house share chores, groceries, bills, favours and chat. This page
        says what we keep, why, and how to have it deleted.
      </p>
      <section className="space-y-2">
        <h2>What we keep</h2>
        <ul>
          <li><b>Your account:</b> your name, your email address, and your password, stored only as a secure hash.</li>
          <li><b>What you and your roommates add:</b> houses, chores and turns, grocery lists, bills and who paid them, favours, and chat messages.</li>
          <li><b>Voice commands:</b> if you use the 🎤 button, the words you said (turned into text on your device; the audio never leaves it). Our own server works out what they mean, so they aren't sent to any other company. We keep them to count them and to improve voice. Never shown to your roommates.</li>
          <li><b>Error reports:</b> when something breaks, the time, the screen and the error, with your account and house IDs, so we can fix it. Kept for 30 days.</li>
        </ul>
        <p>We don't use ads, analytics or tracking, and we don't sell or share your data with anyone.</p>
      </section>
      <section className="space-y-2">
        <h2>Who can see it</h2>
        <p>
          The people in a house see that house's chores, lists, bills, favours and chat, and the names of the people in it. Nobody
          outside the house does.
        </p>
      </section>
      <section className="space-y-2">
        <h2>Services we use</h2>
        <ul>
          <li><b>Render</b> runs the app's servers.</li>
          <li><b>Neon</b> stores the database.</li>
          <li><b>An email service</b> (Brevo or Resend) sends the confirmation and invite emails.</li>
        </ul>
        <p>They process the data only to run Roommates for us.</p>
      </section>
      <section className="space-y-2">
        <h2>Deleting your data</h2>
        <p>
          Delete your account any time in <b>Profile → Delete account</b>, in the app or on the website. Your account and email
          are removed for good. Houses where you were the only one are deleted with everything in them. In shared houses, your
          past turns and payments stay under your name so the house's history still adds up, and if you were the only admin, the
          roommate who joined first becomes admin.
        </p>
      </section>
      <section className="space-y-2">
        <h2>Contact</h2>
        <p>Questions about your data: {mail}.</p>
      </section>
    </LegalLayout>
  );
}

export function SupportPage() {
  return (
    <LegalLayout title="Help & support" subtitle="We usually answer within a couple of days.">
      <section className="space-y-2">
        <h2>Get in touch</h2>
        <p>Email {mail} with what happened and, if the app showed one, the error's “ref” code.</p>
      </section>
      <section className="space-y-2">
        <h2>Common questions</h2>
        <ul>
          <li><b>I didn't get the confirmation email.</b> Check spam, then use “Send the link again” on the login screen.</li>
          <li><b>How do my roommates join?</b> Share the invite link or the 8-character code from the house's People page.</li>
          <li><b>Who can change chores, bills or the grocery list setup?</b> The house's admins, under ⚙️ Settings.</li>
          <li><b>The app is slow to open.</b> The first load after a quiet spell can take a few seconds while the server wakes up.</li>
          <li><b>How do I delete my account?</b> Profile → Delete account. See the <Link className="font-medium text-indigo-700 hover:underline" to="/privacy">privacy policy</Link> for what happens to your houses.</li>
        </ul>
      </section>
    </LegalLayout>
  );
}
