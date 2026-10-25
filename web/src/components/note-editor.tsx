import type { ReactNode } from "react";
import { useEditor, EditorContent, type Editor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { TableKit } from "@tiptap/extension-table";
import { Markdown } from "tiptap-markdown";
import {
  Bold,
  Italic,
  Heading1,
  Heading2,
  List,
  ListOrdered,
  Quote,
  Link2,
  Undo2,
  Redo2,
  Strikethrough,
  Minus,
  Table,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

/** TipTap markdown storage helper. */
export function getMarkdown(editor: Editor): string {
  const storage = editor.storage as { markdown?: { getMarkdown?: () => string } };
  return storage.markdown?.getMarkdown?.() ?? editor.getText();
}

/**
 * Scheme A: in-place rich text. Parent remounts via key on enter/exit edit.
 * Citation markers [n] stay plain text. GFM tables round-trip via TableKit + tiptap-markdown.
 */
export function NoteRichEditor({
  initialMarkdown,
  onEditor,
  className,
}: {
  initialMarkdown: string;
  onEditor?: (editor: Editor | null) => void;
  className?: string;
}) {
  const editor = useEditor({
    immediatelyRender: false,
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
        link: {
          openOnClick: false,
          HTMLAttributes: { class: "underline underline-offset-2" },
        },
      }),
      TableKit.configure({
        table: {
          resizable: false,
          HTMLAttributes: { class: "note-editor-table" },
        },
      }),
      Markdown.configure({
        html: false,
        transformPastedText: true,
        transformCopiedText: true,
      }),
    ],
    content: initialMarkdown,
    onCreate: ({ editor: ed }) => onEditor?.(ed),
    onDestroy: () => onEditor?.(null),
    editorProps: {
      attributes: {
        class:
          "note-rich-editor min-h-[12rem] max-w-none text-sm leading-6 outline-none focus:outline-none",
      },
    },
  });

  if (!editor) return null;

  return (
    <div className={cn("flex min-h-0 flex-1 flex-col", className)}>
      <NoteToolbar editor={editor} />
      <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-6 pt-2">
        <EditorContent editor={editor} />
      </div>
    </div>
  );
}

function NoteToolbar({ editor }: { editor: Editor }) {
  function setLink() {
    const previous = editor.getAttributes("link").href as string | undefined;
    const next = window.prompt("链接地址", previous ?? "https://");
    if (next === null) return;
    const href = next.trim();
    if (!href) {
      editor.chain().focus().extendMarkRange("link").unsetLink().run();
      return;
    }
    editor.chain().focus().extendMarkRange("link").setLink({ href }).run();
  }

  return (
    <div className="flex shrink-0 flex-wrap items-center gap-0.5 border-b border-border/60 px-3 py-1.5">
      <ToolBtn
        title="撤销"
        active={false}
        disabled={!editor.can().undo()}
        onClick={() => editor.chain().focus().undo().run()}
      >
        <Undo2 className="h-3.5 w-3.5" />
      </ToolBtn>
      <ToolBtn
        title="重做"
        active={false}
        disabled={!editor.can().redo()}
        onClick={() => editor.chain().focus().redo().run()}
      >
        <Redo2 className="h-3.5 w-3.5" />
      </ToolBtn>
      <Sep />
      <ToolBtn
        title="标题 1"
        active={editor.isActive("heading", { level: 1 })}
        onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
      >
        <Heading1 className="h-3.5 w-3.5" />
      </ToolBtn>
      <ToolBtn
        title="标题 2"
        active={editor.isActive("heading", { level: 2 })}
        onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
      >
        <Heading2 className="h-3.5 w-3.5" />
      </ToolBtn>
      <Sep />
      <ToolBtn
        title="粗体"
        active={editor.isActive("bold")}
        onClick={() => editor.chain().focus().toggleBold().run()}
      >
        <Bold className="h-3.5 w-3.5" />
      </ToolBtn>
      <ToolBtn
        title="斜体"
        active={editor.isActive("italic")}
        onClick={() => editor.chain().focus().toggleItalic().run()}
      >
        <Italic className="h-3.5 w-3.5" />
      </ToolBtn>
      <ToolBtn
        title="删除线"
        active={editor.isActive("strike")}
        onClick={() => editor.chain().focus().toggleStrike().run()}
      >
        <Strikethrough className="h-3.5 w-3.5" />
      </ToolBtn>
      <ToolBtn title="链接" active={editor.isActive("link")} onClick={setLink}>
        <Link2 className="h-3.5 w-3.5" />
      </ToolBtn>
      <Sep />
      <ToolBtn
        title="无序列表"
        active={editor.isActive("bulletList")}
        onClick={() => editor.chain().focus().toggleBulletList().run()}
      >
        <List className="h-3.5 w-3.5" />
      </ToolBtn>
      <ToolBtn
        title="有序列表"
        active={editor.isActive("orderedList")}
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
      >
        <ListOrdered className="h-3.5 w-3.5" />
      </ToolBtn>
      <ToolBtn
        title="引用"
        active={editor.isActive("blockquote")}
        onClick={() => editor.chain().focus().toggleBlockquote().run()}
      >
        <Quote className="h-3.5 w-3.5" />
      </ToolBtn>
      <ToolBtn
        title="分隔线"
        active={false}
        onClick={() => editor.chain().focus().setHorizontalRule().run()}
      >
        <Minus className="h-3.5 w-3.5" />
      </ToolBtn>
      <Sep />
      <ToolBtn
        title="插入表格"
        active={editor.isActive("table")}
        onClick={() =>
          editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()
        }
      >
        <Table className="h-3.5 w-3.5" />
      </ToolBtn>
    </div>
  );
}

function ToolBtn({
  title,
  active,
  disabled,
  onClick,
  children,
}: {
  title: string;
  active: boolean;
  disabled?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <Button
      type="button"
      size="icon"
      variant="ghost"
      title={title}
      disabled={disabled}
      className={cn("h-7 w-7 rounded-md", active && "bg-accent text-foreground")}
      onClick={onClick}
    >
      {children}
    </Button>
  );
}

function Sep() {
  return <span className="mx-0.5 h-4 w-px bg-border/80" aria-hidden />;
}
