const foundations = [
  "Tailnet-only local deployment",
  "Durable workflow boundary",
  "Immutable artifact lineage",
  "Translation is the only paid runtime provider",
];

export default function Home() {
  return (
    <main>
      <section className="hero" aria-labelledby="title">
        <p className="eyebrow">Phase 1 · Reproducible foundation</p>
        <h1 id="title">Auto Video Sub</h1>
        <p className="lede">
          A local-first workspace for turning Chinese-language videos into editable Vietnamese
          subtitles and speech.
        </p>
        <ul>
          {foundations.map((foundation) => (
            <li key={foundation}>{foundation}</li>
          ))}
        </ul>
        <p className="status">
          <span aria-hidden="true" /> Product workflows begin only after this foundation passes
          review.
        </p>
      </section>
    </main>
  );
}
