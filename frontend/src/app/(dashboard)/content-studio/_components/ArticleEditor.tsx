'use client';

import { useMemo } from 'react';
import { useCreateBlockNote } from '@blocknote/react';
import { BlockNoteView } from '@blocknote/shadcn';
import '@blocknote/shadcn/style.css';
import type { ArticleSection } from './types';

function sectionsToBlocks(sections: ArticleSection[]) {
  const blocks: Array<Record<string, unknown>> = [];

  for (const section of sections) {
    blocks.push({
      type: 'heading',
      props: { level: 2 },
      content: [{ type: 'text', text: section.heading, styles: {} }],
    });

    const paragraphs = section.content.split('\n\n').filter(Boolean);
    for (const para of paragraphs) {
      blocks.push({
        type: 'paragraph',
        content: [{ type: 'text', text: para, styles: {} }],
      });
    }
  }

  return blocks;
}

interface ArticleEditorProps {
  sections: ArticleSection[];
}

export function ArticleEditor({ sections }: ArticleEditorProps) {
  const initialContent = useMemo(() => sectionsToBlocks(sections), [sections]);

  /* eslint-disable @typescript-eslint/no-explicit-any */
  const editor = useCreateBlockNote({
    initialContent: initialContent,
  } as any);

  return (
    <div className="article-editor-wrapper" style={{ maxWidth: 720, margin: '0 auto', padding: '24px 0' }}>
      <BlockNoteView
        editor={editor as any}
        theme="light"
      />
    </div>
  );
  /* eslint-enable @typescript-eslint/no-explicit-any */
}
