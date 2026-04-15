export default function TextSection({
  heading,
  children,
}: {
  heading: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-2">
      <h3 className="font-headline font-medium italic text-center">{heading}</h3>
      <p className="text-body-justify">{children}</p>
    </section>
  );
}
