<script setup lang="ts">
/**
 * "Navigating Syntitude" — the site's own documentation, and the loci worth starting from.
 *
 * The prose is the published page's, carried across unchanged (`template.html`, `#view-navigating`);
 * only the example chips are per catalogue. ⚠ A chip is a JUMP, so it faces forward.
 */
import type { ExampleLocusRow } from "@/api/types";

defineProps<{ examples: readonly ExampleLocusRow[] }>();

const emit = defineEmits<{ go: [locusLabel: string] }>();

/** `render_page._examples`: the name, and the family count only where there is more than one. */
function chipText(row: ExampleLocusRow): string {
  const families = row.uniref50_family_count ?? 0;
  return families > 1 ? `${row.display_name} · ${families} UniRef50 families` : row.display_name;
}
</script>

<template>
  <div>
    <p class="track-note">
      Each track shows one whole <em>arrangement</em> — a neighbourhood some set of genomes actually has,
      not a position-by-position consensus — read outward from the focal locus in its own direction of
      transcription, so <span class="mono">A-1</span> is the gene immediately upstream whichever strand it
      sits on.
    </p>
    <ul class="track-key">
      <li>
        <b>Transparency</b> — for each locus, how many genomes its part of the graph reaches. Not every
        locus reaches the whole pangenome.
      </li>
      <li>
        <b>Colour</b> — in contrast, how the divergent genes at a position divide it: deep blue where this
        one always holds it, maroon where several compete. 20 in 100 is an ordinary reading, not a poor one.
      </li>
      <li>
        <b>Click a gene</b> to walk to it. Onto one transcribed the other way, the frame reverses:
        <span class="mono">A+1</span> becomes <span class="mono">A-1</span>, so you carry on along the stream.
      </li>
      <li>
        <b>Click the bar</b> to see how all member genes split at that position. Under the focal gene it is
        the sequence families filling this locus.
      </li>
      <li>
        <b>White blocks</b> are the <em>intergenic regions</em> — the space between two genes, named for the
        RNA gene, origin of replication or CRISPR array Bakta found in it, or by the genes that bracket it.
        <strong>A white block is not a Nuna locus.</strong> It has no cluster and no embedding, it is not in
        the locus count, and you cannot walk to it; its width is a <em>median</em> across genomes that
        disagree. They are white rather than coloured precisely because the divergence measure that colours
        a gene does not exist for them.
      </li>
      <li>
        <b><span class="mono">&middot;1504</span></b> — the locus <strong>id</strong>. Names repeat
        (<span class="mono">tnp</span> on hundreds); search an id, or put it after
        <span class="mono">#</span> in the address bar.
      </li>
    </ul>
    <div class="card">
      <h2>What a locus is</h2>
      <p class="lede">
        A pangenome tool built on sequence identity defines a gene family as sequences similar enough to each
        other, and so has a floor — Panaroo will not merge below 70&nbsp;% amino-acid identity, Roary below
        95&nbsp;%. Genes that diverge past the floor become separate families however obviously they are the
        same thing. Those are not a random sample of the genome: they are the loci under diversifying
        selection — surface antigens, O- and K-locus biosynthesis, flagellin, fimbrial adhesins, anti-phage
        defence — the genes anyone studying a pathogen actually cares about.
      </p>
      <p class="lede">
        A Nuna locus is defined differently: <b>a position in the genome that a genome must fill</b>, whose
        occupants may share no detectable sequence homology at all. Where an identity-threshold tool splits
        divergent families apart, this groups them by position — so a locus here may hold several families
        an alignment would never join.
      </p>
      <p class="lede">
        Whether that is better described as <em>one locus with several alleles</em> or as <em>several
        genes</em> is the open question, and it is the reason for the evidence on each page: how far apart
        the families are, whether their domain architectures agree, and how consistent the neighbourhood is.
        The browser is for inspecting that, not for asserting it.
      </p>
      <div class="chip-row">
        <button
          v-for="row in examples"
          :key="row.label"
          type="button"
          class="chip neutral"
          @click="emit('go', row.label)"
        >
          {{ chipText(row) }}
        </button>
      </div>
      <p class="muted">
        Loci worth starting from: positions this model holds together that UniRef50 files under several
        different families.
      </p>
    </div>
  </div>
</template>
