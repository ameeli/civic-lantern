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
    <h3 className="text-2xl font-medium text-center">
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
    <h3 className="text-2xl font-medium text-center">{formatDollars(total)}</h3>
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
      <Suspense fallback="—">{total}</Suspense>
      <div className="-mt-1">
        <section className="space-y-4">
          <h3 className="font-headline text-sm font-medium italic text-center">
            {heading}
          </h3>
          <p className="text-body-justify">{children}</p>
        </section>
      </div>
    </div>
  );
}

export default function ElectionSpendingSection({ cycle }: { cycle: number }) {
  return (
    <div className="col-span-3 space-y-3 px-2">
      <h1 className="font-headline font-semibold text-2xl text-center">
        ELECTION SPENDING
      </h1>
      <div className="space-y-5">
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
          can raise or spend — meaning corporations, billionaires, or special
          interests can pour in millions to support or attack a candidate.
          <br />
          <br />
          While the groups are legally barred from coordinating with campaigns,
          they often operate in ways that closely mirror them, funding
          aggressive ads and outreach. This allows massive, unregulated wealth
          to shape elections from the outside.
        </SpendingCategory>
      </div>
    </div>
  );
}
