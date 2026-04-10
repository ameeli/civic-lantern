import Gavel from "@/components/Gavel";
import MastheadRule from "@/components/MastheadRule";
import PaperBorder from "@/components/PaperBorder";
import TextSection from "@/components/TextSection";

export default function Home() {
  return (
    <div className="flex flex-col flex-1 items-center bg-dark-wood font-sans">
      <main className="relative isolate grid grid-cols-12 gap-1 flex-1 w-full max-w-7xl my-2 p-15">
        <PaperBorder />
        <div className="col-span-12 flex flex-col items-center gap-5">
          <h1 className="text-masthead text-3xl">The Civic Lantern</h1>
          <MastheadRule>
            <Gavel width={40} height={40} />
          </MastheadRule>
        </div>
        <div className="col-span-5 space-y-2">
          <h1 className="font-headline font-semibold text-2xl">
            SPENDING TOTALS
          </h1>
          <div className="space-y-3">
            <TextSection heading="Candidate Fundraising">
              This is money given directly to a candidate&apos;s official
              campaign. There are strict limits on how much individuals can
              donate, and the candidate controls exactly how it&apos;s spent
              &mdash; ads, staff, travel, everything.
              <br />
              Because the candidate is fully responsible for these decisions,
              this is the money behind the familiar &ldquo;I approve this
              message.&rdquo; It&apos;s regulated, transparent, and designed to
              prevent any single donor from having too much influence.
            </TextSection>

            <TextSection heading="Outside Spending">
              This is money spent by outside groups to influence an election
              without going through the candidate&apos;s campaign. Unlike
              candidate fundraising, there are no limits on how much these
              groups can raise or spend — meaning corporations, billionaires, or
              special interests can pour in millions to support or attack a
              candidate.
              <br />
              While they can&apos;t legally coordinate with campaigns, they
              often operate like a parallel campaign, funding aggressive ads and
              large-scale voter outreach. The result: even though candidate
              fundraising is tightly regulated, outside spending allows massive
              amounts of money to shape elections from the outside.
            </TextSection>
          </div>
        </div>
      </main>
    </div>
  );
}
