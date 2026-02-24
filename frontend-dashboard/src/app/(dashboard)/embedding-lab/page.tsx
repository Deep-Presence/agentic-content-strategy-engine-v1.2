import { Dna } from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';

export default function EmbeddingLabPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Deep Embedding Lab"
        description="Immersive visualization workspace for semantic analysis"
      />
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <Dna className="h-12 w-12 text-cream-500 mb-4" />
        <h2 className="font-serif text-heading-3 text-cream-800 mb-2">Coming Soon</h2>
        <p className="text-body text-cream-600 max-w-md">
          The Deep Embedding Lab will feature interactive UMAP, t-SNE, and cluster visualizations
          powered by D3.js and deck.gl.
        </p>
      </div>
    </div>
  );
}
