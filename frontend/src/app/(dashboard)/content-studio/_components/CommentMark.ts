/**
 * CommentMark — Custom Tiptap Mark for inline review comments.
 *
 * Wraps selected text with a highlight. Each mark carries a `commentId`
 * attribute that maps to a `ReviewComment` stored in React state.
 * Ephemeral — never persisted to the backend.
 */
import { Mark, mergeAttributes } from '@tiptap/core';

export interface CommentMarkOptions {
  HTMLAttributes: Record<string, string>;
}

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    comment: {
      setComment: (attrs: { commentId: string }) => ReturnType;
      unsetComment: () => ReturnType;
      unsetCommentById: (commentId: string) => ReturnType;
    };
  }
}

export const CommentMark = Mark.create<CommentMarkOptions>({
  name: 'comment',

  priority: 1000,

  inclusive: false,

  addOptions() {
    return {
      HTMLAttributes: {},
    };
  },

  addAttributes() {
    return {
      commentId: {
        default: null,
        parseHTML: (el) => el.getAttribute('data-comment-id'),
        renderHTML: (attrs) => {
          if (!attrs.commentId) return {};
          return { 'data-comment-id': attrs.commentId };
        },
      },
    };
  },

  parseHTML() {
    return [{ tag: 'span[data-comment-id]' }];
  },

  renderHTML({ HTMLAttributes }) {
    return [
      'span',
      mergeAttributes(this.options.HTMLAttributes, HTMLAttributes, {
        class: 'review-comment-highlight',
      }),
      0,
    ];
  },

  addCommands() {
    return {
      setComment:
        (attrs) =>
        ({ commands }) => {
          return commands.setMark(this.name, attrs);
        },

      unsetComment:
        () =>
        ({ commands }) => {
          return commands.unsetMark(this.name);
        },

      unsetCommentById:
        (commentId: string) =>
        ({ tr, state, dispatch }) => {
          const markType = state.schema.marks[this.name];
          if (!markType) return false;

          // Walk the document and collect ranges that have this specific commentId
          const ranges: Array<{ from: number; to: number }> = [];

          state.doc.descendants((node, pos) => {
            if (!node.isText) return;
            const mark = node.marks.find(
              (m) => m.type === markType && m.attrs.commentId === commentId,
            );
            if (mark) {
              ranges.push({ from: pos, to: pos + node.nodeSize });
            }
          });

          if (ranges.length === 0) return false;

          if (dispatch) {
            for (const { from, to } of ranges) {
              const mark = markType.create({ commentId });
              tr.removeMark(from, to, mark);
            }
            dispatch(tr);
          }

          return true;
        },
    };
  },
});
