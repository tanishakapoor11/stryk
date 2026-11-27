import { PageHeader, Section } from "@/components/layout/page-header";
import { AskPanel } from "@/features/ask/ask-panel";

export const metadata = {
  title: "Ask a question",
  description:
    "Ask a cricket statistics question in plain English and get the leaderboard it describes, computed from the ball-by-ball record.",
};

/**
 * The question box.
 *
 * It is its own page rather than part of the home-page search for one reason:
 * the name search fires as you type, and every question here costs a model
 * call. Typing a surname into this box would bill one call per keystroke, so
 * nothing happens until the reader presses Enter.
 */
const EXAMPLES = [
  "Most runs in a 180+ run chase in the IPL",
  "Best economy at the death in the IPL",
  "Most wickets in the powerplay in the BBL",
  "Highest strike rate batting second in the WPL",
];

export default function AskPage() {
  return (
    <>
      <PageHeader
        title="Ask a question"
        subtitle={
          <>
            Questions are turned into the same filters the rest of STRYK uses, then answered
            from the deliveries. Nothing is estimated and no number is written by a model &mdash;
            whatever a question asks for that STRYK cannot filter on is listed with the answer
            rather than quietly ignored.
          </>
        }
      />
      <Section className="max-w-3xl">
        <AskPanel examples={EXAMPLES} />
      </Section>
    </>
  );
}
