export default function TextSection({
  heading,
  children,
}: {
  heading: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h3 className="font-headline font-medium italic">{heading}</h3>
      <p className="text-body-justify">{children}</p>
    </section>
  );
}
