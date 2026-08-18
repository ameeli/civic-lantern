import { Suspense } from "react";
import { getElectionSpendingByCycle } from "@/api/spending";

function formatDollars(value: number | null): string {
  if (value === null) return "N/A";
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

async function InsideDisbursements({ cycle }: { cycle: number }) {
  const spending = await getElectionSpendingByCycle(cycle);
  return (
    <h3 className="text-2xl font-semibold text-center">
      {formatDollars(spending.total_inside_disbursements)}
    </h3>
  );
}

async function OutsideTotal({ cycle }: { cycle: number }) {
  const spending = await getElectionSpendingByCycle(cycle);
  const total =
    (spending.total_outside_support ?? 0) +
    (spending.total_outside_oppose ?? 0);
  return (
    <h3 className="text-2xl font-semibold text-center">
      {formatDollars(total)}
    </h3>
  );
}

function IndependentExpenditureTypes() {
  return (
    <section className="space-y-2">
      <h3 className="font-headline text-sm font-semibold">
        The Two Types of Independent Expenditures
      </h3>
      <p className="text-body-justify">
        <strong className="font-bold">Independent Support: </strong>
        Promotes the candidate's record or platform to build voter approval.
        <br />
        <strong className="font-bold">Independent Opposition: </strong>
        Attacks the candidate's character or positions to discourage support.
      </p>
    </section>
  );
}

function SpendingCategory({
  total,
  heading,
  children,
}: {
  total: React.ReactNode;
  heading: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="border-ink-thin py-2">
        <Suspense fallback="—">{total}</Suspense>
        <h3 className="font-headline text-sm font-semibold text-center">
          {heading}
        </h3>
      </div>
      <p className="text-body-justify mt-2">{children}</p>
    </div>
  );
}

export default function ElectionSpendingSection({ cycle }: { cycle: number }) {
  return (
    <div className="col-span-12 sm:col-span-12 lg:col-span-4 space-y-3 px-2">
      <div className="space-y-3">
        <SpendingCategory
          total={<InsideDisbursements cycle={cycle} />}
          heading="Direct Campaign Spending"
        >
          This is money given directly to a candidate&apos;s official campaign.
          There are strict limits on how much individuals can donate, and the
          candidate controls exactly how it&apos;s spent.
          <br />
          <br />
          Because the candidate is fully responsible for these decisions, this
          is the money behind the familiar &ldquo;I approve this message.&rdquo;
          It&apos;s regulated, transparent, and designed to prevent any single
          donor from having too much influence.
        </SpendingCategory>

        <SpendingCategory
          total={<OutsideTotal cycle={cycle} />}
          heading="Independent Expenditures"
        >
          This is money spent by outside groups to influence an election. Unlike
          candidate fundraising, there are no limits on how much these groups
          can raise or spend. This means corporations, billionaires, or special
          interests can pour in millions to support or attack a candidate.
          <br />
          <br />
          Despite strict laws prohibiting direct campaign coordination, these
          organizations mirror candidate operations with aggressive TV, mail,
          and digital ad buys. This allows unregulated wealth to shape elections
          on a massive scale.
        </SpendingCategory>
        <IndependentExpenditureTypes />
      </div>
    </div>
  );
}
